"""What approving a request would do (never stored while it is pending) and how a decided request posts to Ledger 6."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound
from asseta.modules.adjustments.hours_effects import HoursEffects
from asseta.modules.adjustments.models import (
    AdjustmentEntryStatus,
    AdjustmentRequest,
    AdjustmentRequestStatus,
    AdjustmentRequestType,
    AdjustmentType,
    AdjustmentUnit,
)
from asseta.modules.adjustments.money import ZERO, custody_outstanding, customer_balance
from asseta.modules.adjustments.posting import AdjustmentPosting, post_adjustment
from asseta.modules.adjustments.reversals import ReversalEngine
from asseta.modules.finance.models import CustomerPayment, HirePaymentMethod
from asseta.modules.hours.engine import HoursEngine
from asseta.modules.hours.ledger import purchase_totals
from asseta.modules.hours.models import HoursPurchase, HoursReasonCode
from asseta.modules.identity.principal import RequestContext

LEDGER_TYPES = {t: AdjustmentType(t.value) for t in AdjustmentRequestType}


def _uuid(value: object) -> uuid.UUID | None:
    return uuid.UUID(str(value)) if value else None


def _decimal(value: object) -> Decimal | None:
    return Decimal(str(value)) if value is not None else None


class RequestPosting:
    """Forecast and Ledger 6 posting of the request flow (the AdjustmentRequests service composes this)."""

    def __init__(
        self,
        session: Session,
        ctx: RequestContext,
        now: datetime,
        engine: HoursEngine,
        hours: HoursEffects,
        reversals: ReversalEngine,
    ):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid, self._now = session, ctx, ctx.tenant_id, now
        self.engine, self.hours, self.reversals = engine, hours, reversals

    def reason_label(self, code_id: uuid.UUID | None) -> str | None:
        if code_id is None:
            return None
        code = self._s.get(HoursReasonCode, code_id)
        return code.label if code else None

    def forecast(self, row: AdjustmentRequest) -> dict[str, Any]:
        """What approving this would do, as of now (a forecast for the decider; never stored)."""
        try:
            return self._forecast(row)
        except (BusinessRuleViolation, Conflict, NotFound) as exc:
            return {"refused": exc.code}

    def _forecast(self, row: AdjustmentRequest) -> dict[str, Any]:
        t = row.request_type
        if t is AdjustmentRequestType.HOURS_CORRECTION:
            assert row.purchase_id is not None and row.machine_id is not None and row.hours is not None
            purchase = self._s.get(HoursPurchase, row.purchase_id)
            assert purchase is not None
            totals = purchase_totals(self._s, purchase)
            self.hours.check_correction(
                purchase, row.machine_id, row.hours, totals, _uuid(row.params.get("consumed_entry_id"))
            )
            before = totals.remaining_on(row.machine_id)
            return {"lot_hours_before": str(before), "lot_hours_after": str(before + row.hours)}
        if t is AdjustmentRequestType.HOURS_REFUND:
            assert row.purchase_id is not None and row.machine_id is not None and row.hours is not None
            purchase = self._s.get(HoursPurchase, row.purchase_id)
            assert purchase is not None
            totals = purchase_totals(self._s, purchase)
            value = self.hours.check_refund(purchase, row.machine_id, row.hours, totals)
            return {
                "value": str(value),
                "lot_hours_after": str(totals.remaining_on(row.machine_id) - row.hours),
                "settlement": row.settlement.value if row.settlement else None,
            }
        if t in (AdjustmentRequestType.PAYMENT_REVERSAL, AdjustmentRequestType.COLLECTION_REVERSAL):
            payment = self._s.get(CustomerPayment, row.original_id)
            assert payment is not None
            plan = self.reversals.plan_payment(payment, lock=False)
            out = {**plan.summary(), "treatment": self.engine.policy.reversal_used_hours_treatment.value}
            if payment.method is HirePaymentMethod.CASH and payment.received_by_staff_id is not None:
                held = custody_outstanding(
                    self._s, self._ctx, self._now, payment.received_by_staff_id, payment.currency
                )
                out["custody_staff_id"] = str(payment.received_by_staff_id)
                out["custody_balance_after"] = str(held - payment.amount)
            return out
        if t is AdjustmentRequestType.PURCHASE_REVERSAL:
            purchase = self._s.get(HoursPurchase, row.original_id)
            assert purchase is not None
            plan_p = self.reversals.plan_purchase_reversal(purchase)
            return {
                "unused_hours_removed": str(sum(plan_p.unused.values(), ZERO)),
                "used_hours": str(plan_p.used_hours),
                "money_owed": str(plan_p.money_owed),
                "treatment": self.engine.policy.reversal_used_hours_treatment.value,
            }
        if t is AdjustmentRequestType.ZERO_AMOUNT_ACTIVATION:
            purchase = self._s.get(HoursPurchase, row.original_id)
            assert purchase is not None
            totals = purchase_totals(self._s, purchase)
            return {"hours_to_activate": str(purchase.hours - totals.net_activated)}
        return {"invoice_id": str(row.original_id)}

    def post(self, row: AdjustmentRequest, note: str | None, result: dict[str, Any]) -> None:
        approved = row.status is AdjustmentRequestStatus.APPROVED
        unit = AdjustmentUnit.MONEY if row.hours is None else AdjustmentUnit.HOURS
        balance = self._resulting(row, result, approved)
        original_value = (
            row.amount
            if unit is AdjustmentUnit.MONEY
            else _decimal(result.get("lot_hours_before"))
            if result.get("lot_hours_before") is not None
            else None
        )
        new_value: Any = None
        amount: Any = row.amount
        if unit is AdjustmentUnit.HOURS and row.hours is not None:
            amount = row.hours
            if result.get("lot_hours_after") is not None:
                new_value = _decimal(result.get("lot_hours_after"))
        elif approved:
            new_value = ZERO
            amount = -row.amount if row.amount is not None else None
        post_adjustment(
            self._s,
            self._tid,
            self._now,
            AdjustmentPosting(
                adjustment_type=LEDGER_TYPES[row.request_type],
                status=AdjustmentEntryStatus.APPROVED if approved else AdjustmentEntryStatus.REJECTED,
                original_type=row.original_type,
                original_id=row.original_id,
                original_reference=row.original_reference,
                source_type="adjustment_request",
                source_id=row.id,
                unit=unit,
                original_value=original_value,
                new_value=new_value,
                amount=amount,
                currency=row.currency,
                resulting_balance=balance,
                reason_id=row.reason_code_id,
                reason_label=self.reason_label(row.reason_code_id),
                reason=row.reason,
                evidence_attachment_ids=list(row.evidence_attachment_ids),
                customer_id=row.customer_id,
                machine_id=row.machine_id,
                staff_member_id=_uuid(result.get("custody_staff_id")),
                requested_by=row.proposed_by,
                requested_at=row.proposed_at,
                approved_by=self._ctx.user_id,
                approved_at=self._now,
                decision_note=note,
                details=result,
                policy_version=row.policy_version,
            ),
        )

    def _resulting(self, row: AdjustmentRequest, result: dict[str, Any], approved: bool) -> Any:
        if not approved:
            return None
        if row.request_type is AdjustmentRequestType.ZERO_AMOUNT_ACTIVATION:
            return None
        if row.hours is not None:
            return _decimal(result.get("lot_hours_after"))
        if row.customer_id is not None and row.currency is not None:
            return customer_balance(self._s, self._tid, row.customer_id, row.currency)
        return None
