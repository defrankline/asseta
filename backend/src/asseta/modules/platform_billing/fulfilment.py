"""Exactly-once fulfilment of fully paid ad-hoc invoice lines (DEC-022), and its reversal when an invoice is voided.

* SMS_BUNDLE      -> credits the tenant SMS wallet (ledger entry referenced by the fulfilment id).
* SUBSCRIPTION_FEE -> the period is settled; entitlement is re-evaluated with the existing rules.
* SERVICE         -> recorded (the service itself is delivered outside the system).

The fulfilment row is claimed with INSERT .. ON CONFLICT DO NOTHING on a unique line id, so duplicate events,
retries and concurrent verifications produce one effect. Reversal: unused SMS credits are debited back; credits
already spent and delivered services cannot be undone and are flagged (REVERSAL_FLAGGED) for platform review.
"""

import uuid
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from asseta.core.audit import AuditActor, AuditService
from asseta.core.db import utcnow
from asseta.core.outbox import OutboxWriter
from asseta.modules.platform_billing.enums import (
    FULFILLABLE_LINE_TYPES,
    FulfilmentStatus,
    InvoiceLineType,
    InvoiceStatus,
    SmsWalletEntryType,
)
from asseta.modules.platform_billing.models_catalog import PlatformLineFulfilment
from asseta.modules.platform_billing.models_ledger import PlatformInvoice, PlatformInvoiceLine
from asseta.modules.platform_billing.repository import BillingRepository
from asseta.modules.platform_billing.settlement import LineState
from asseta.modules.platform_billing.sms_wallet import SmsWalletService
from asseta.modules.platform_billing.subscription_service import SubscriptionService

TOPIC = "asseta.platform.invoice"
REFERENCE = "platform_line_fulfilment"


class FulfilmentService:
    def __init__(self, session: Session, actor: AuditActor, today: date):
        self._s, self._actor, self._today = session, actor, today
        self._repo = BillingRepository(session)
        self._wallet = SmsWalletService(session)

    def fulfil_settled(self, inv: PlatformInvoice, states: list[LineState]) -> list[PlatformLineFulfilment]:
        if inv.status is InvoiceStatus.VOIDED:
            return []
        settled = {st.line_id for st in states if st.settled}
        done = []
        for line in self._repo.invoice_lines(inv.id):
            if line.id in settled and line.line_type in FULFILLABLE_LINE_TYPES:
                row = self._claim(inv, line)
                if row is not None:
                    done.append(row)
        return done

    def _effect(self, line: PlatformInvoiceLine) -> dict[str, Any]:
        if line.line_type is InvoiceLineType.SMS_BUNDLE:
            return {"sms_credits": line.sms_credits or 0}
        if line.line_type is InvoiceLineType.SUBSCRIPTION_FEE:
            return {
                "subscription_id": str(line.subscription_id),
                "period_start": line.service_from.isoformat() if line.service_from else None,
                "period_end": line.service_to.isoformat() if line.service_to else None,
            }
        return {"description": line.description}

    def _claim(self, inv: PlatformInvoice, line: PlatformInvoiceLine) -> PlatformLineFulfilment | None:
        fid = self._s.execute(
            insert(PlatformLineFulfilment)
            .values(
                id=uuid.uuid4(),
                tenant_id=inv.tenant_id,
                invoice_id=inv.id,
                line_id=line.id,
                line_type=line.line_type,
                status=FulfilmentStatus.FULFILLED,
                effect=self._effect(line),
                fulfilled_at=utcnow(),
            )
            .on_conflict_do_nothing(constraint="uq_platform_fulfilment_line")
            .returning(PlatformLineFulfilment.id)
        ).scalar_one_or_none()
        if fid is None:
            return None  # already fulfilled: exactly once
        row = self._s.get(PlatformLineFulfilment, fid)
        assert row is not None
        if line.line_type is InvoiceLineType.SMS_BUNDLE and line.sms_credits:
            self._wallet.post(
                inv.tenant_id,
                SmsWalletEntryType.BUNDLE_CREDIT,
                line.sms_credits,
                REFERENCE,
                row.id,
                f"{inv.invoice_number} line {line.line_no}: {line.description}",
                self._actor.user_id,
            )
        elif line.line_type is InvoiceLineType.SUBSCRIPTION_FEE and line.subscription_id is not None:
            sub = self._repo.subscription(line.subscription_id, for_update=True)
            SubscriptionService(self._s, self._actor).evaluate_entitlement(sub, self._today)
        self._record(inv, line, row, "platform.invoice_line.fulfilled", "PlatformInvoiceLineFulfilled")
        return row

    def reverse_for_void(self, inv: PlatformInvoice, reason: str) -> list[PlatformLineFulfilment]:
        rows = list(
            self._s.execute(
                select(PlatformLineFulfilment)
                .where(
                    PlatformLineFulfilment.invoice_id == inv.id,
                    PlatformLineFulfilment.status == FulfilmentStatus.FULFILLED,
                )
                .with_for_update()
            ).scalars()
        )
        for row in rows:
            line = self._s.get(PlatformInvoiceLine, row.line_id)
            assert line is not None
            status, note = FulfilmentStatus.REVERSED, f"Invoice voided: {reason}"
            if row.line_type is InvoiceLineType.SMS_BUNDLE:
                wanted = int(row.effect.get("sms_credits", 0))
                taken = self._wallet.debit_unused(inv.tenant_id, wanted, REFERENCE, row.id, note) if wanted else 0
                row.effect = {**row.effect, "reversed_credits": taken}
                if taken < wanted:
                    status = FulfilmentStatus.REVERSAL_FLAGGED
                    note += f" ({wanted - taken} credits already used: review)"
            elif row.line_type is InvoiceLineType.SERVICE:
                status = FulfilmentStatus.REVERSAL_FLAGGED
                note += " (service already delivered: review)"
            row.status, row.reversed_at, row.reversal_note = status, utcnow(), note[:1000]
            self._s.flush()
            self._record(inv, line, row, "platform.invoice_line.fulfilment_reversed", "PlatformInvoiceLineReversed")
        return rows

    def _record(
        self, inv: PlatformInvoice, line: PlatformInvoiceLine, row: PlatformLineFulfilment, action: str, event: str
    ) -> None:
        payload = {
            "fulfilment_id": str(row.id),
            "invoice_id": str(inv.id),
            "invoice_number": inv.invoice_number,
            "line_id": str(line.id),
            "line_no": line.line_no,
            "line_type": line.line_type.value,
            "status": row.status.value,
            "description": line.description,
            "effect": row.effect,
        }
        AuditService(self._s).record(
            actor=self._actor,
            action=action,
            entity_type="platform_invoice_line",
            entity_id=line.id,
            tenant_id=inv.tenant_id,
            after=payload,
            reason=row.reversal_note,
        )
        OutboxWriter(self._s).emit(
            topic=TOPIC, event_type=event, key=str(inv.tenant_id), payload=payload, tenant_id=inv.tenant_id
        )
