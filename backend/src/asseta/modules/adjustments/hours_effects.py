"""What approved customer-hour corrections and refunds do (DEC-032 B2/B3). Offsetting ledger entries only; every check
is re-run at the decision against the ledger as it stands then (a lot can change while a proposal waits)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.errors import BusinessRuleViolation, NotFound
from asseta.core.money import quantize
from asseta.modules.adjustments.models import AdjustmentRequest, RefundSettlement
from asseta.modules.adjustments.money import (
    ZERO,
    custody_offset,
    customer_balance,
    money_record,
    release_money,
    verified_allocations,
)
from asseta.modules.finance.models import AdjustmentKind, HirePaymentMethod
from asseta.modules.fleet.models import Machine
from asseta.modules.hours.engine import HoursEngine, minor_units
from asseta.modules.hours.ledger import LedgerWriter, PurchaseTotals, purchase_totals
from asseta.modules.hours.models import HoursLedgerEntry, HoursPurchase, LedgerEntryType
from asseta.modules.identity.principal import RequestContext

T = LedgerEntryType
CONSUMED_LIKE = (T.CONSUMED, T.PROVISIONAL)


class HoursEffects:
    def __init__(self, session: Session, ctx: RequestContext, now: datetime, engine: HoursEngine):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid, self._now = session, ctx, ctx.tenant_id, now
        self.engine = engine
        self._ledger = LedgerWriter(session, ctx.tenant_id, ctx.user_id, now)

    def resolve_lot(self, purchase_id: uuid.UUID, machine_id: uuid.UUID | None) -> tuple[HoursPurchase, uuid.UUID]:
        """A correction or refund targets one lot: the purchase's hours on one machine."""
        purchase = self._s.get(HoursPurchase, purchase_id)
        if purchase is None:
            raise NotFound("Hours purchase not found")
        if purchase.cancelled_at is not None:
            raise BusinessRuleViolation("The purchase is cancelled", code="PURCHASE_CANCELLED")
        machine = machine_id or purchase.machine_id
        if self._s.get(Machine, machine) is None:
            raise NotFound("Machine not found")
        return purchase, machine

    # --- correction -------------------------------------------------------------------------------------------
    def check_correction(
        self,
        purchase: HoursPurchase,
        machine_id: uuid.UUID,
        hours: Decimal,
        totals: PurchaseTotals,
        consumed_entry_id: uuid.UUID | None = None,
    ) -> None:
        """Cannot take a lot below zero, and cannot lift it above what was activated. A correction of consumption
        names the CONSUMED (or daily) entry it corrects; only its own hours can come back."""
        left = totals.remaining_on(machine_id)
        if hours < 0 and left + hours < 0:
            raise BusinessRuleViolation(
                f"Only {left} hours of {purchase.purchase_number} remain on that machine; a correction cannot take the "
                "lot below zero",
                code="HOURS_CORRECTION_NEGATIVE",
            )
        if hours > 0 and totals.remaining + hours > totals.net_activated:
            raise BusinessRuleViolation(
                "A correction cannot lift a purchase above the hours that were activated on it",
                code="HOURS_CORRECTION_EXCEEDS_LOT",
            )
        if consumed_entry_id is not None and hours > 0:
            entry = self._s.get(HoursLedgerEntry, consumed_entry_id)
            if entry is None or entry.purchase_id != purchase.id or entry.entry_type not in CONSUMED_LIKE:
                raise NotFound("Consumption entry not found on this purchase", code="CONSUMED_ENTRY_NOT_FOUND")
            if hours > entry.hours:
                raise BusinessRuleViolation(
                    f"The entry being corrected is {entry.hours} hours", code="HOURS_CORRECTION_EXCEEDS_ENTRY"
                )

    def apply_correction(self, req: AdjustmentRequest) -> dict[str, Any]:
        assert req.purchase_id is not None and req.machine_id is not None and req.hours is not None
        purchase = self.engine.lock_purchase(req.purchase_id)
        if purchase.cancelled_at is not None:
            raise BusinessRuleViolation("The purchase is cancelled", code="PURCHASE_CANCELLED")
        totals = purchase_totals(self._s, purchase)
        before = totals.remaining_on(req.machine_id)
        consumed_entry = _uuid(req.params.get("consumed_entry_id"))
        self.check_correction(purchase, req.machine_id, req.hours, totals, consumed_entry)
        self._ledger.add(
            purchase,
            req.machine_id,
            T.CORRECTION_ADD if req.hours > 0 else T.CORRECTION_DEDUCT,
            abs(req.hours),
            job_id=_uuid(req.params.get("job_id")),
            adjustment_request_id=req.id,
            reason=req.reason,
            policy_version=self.engine.eff.version_stamp,
        )
        after = before + req.hours
        if req.hours > 0:
            self.engine.cover_overruns(purchase.customer_id, req.machine_id)
        return {
            "machine_id": str(req.machine_id),
            "hours": str(req.hours),
            "lot_hours_before": str(before),
            "lot_hours_after": str(after),
            "purchase_remaining": str(totals.remaining + req.hours),
        }

    # --- refund -----------------------------------------------------------------------------------------------
    def refund_value(self, purchase: HoursPurchase, hours: Decimal) -> Decimal:
        return quantize(hours * purchase.effective_rate, minor_units(self._s, purchase.currency))

    def check_refund(
        self, purchase: HoursPurchase, machine_id: uuid.UUID, hours: Decimal, totals: PurchaseTotals
    ) -> Decimal:
        """Only unused activated hours can be refunded, and only as far as verified money covers them."""
        if hours <= 0:
            raise BusinessRuleViolation("A refund is a positive number of hours", code="HOURS_REFUND_INVALID")
        left = totals.remaining_on(machine_id)
        if hours > left:
            raise BusinessRuleViolation(
                f"Only {left} unused hours of {purchase.purchase_number} remain on that machine",
                code="EXCEEDS_REMAINING_HOURS",
            )
        value = self.refund_value(purchase, hours)
        verified = sum((a.amount for a in verified_allocations(self._s, purchase.id)), ZERO)
        if value <= 0 or value > verified:
            raise BusinessRuleViolation(
                f"Only {verified} {purchase.currency} of verified money is linked to this purchase",
                code="REFUND_EXCEEDS_PAID",
            )
        return value

    def apply_refund(self, req: AdjustmentRequest) -> dict[str, Any]:
        assert req.purchase_id is not None and req.machine_id is not None and req.hours is not None
        assert req.settlement is not None and req.currency is not None and req.customer_id is not None
        if not self.engine.policy.refund_allowed:
            raise BusinessRuleViolation("Refunds are switched off by tenant policy", code="REFUND_NOT_ALLOWED")
        purchase = self.engine.lock_purchase(req.purchase_id)
        if purchase.cancelled_at is not None:
            raise BusinessRuleViolation("The purchase is cancelled", code="PURCHASE_CANCELLED")
        totals = purchase_totals(self._s, purchase)
        value = self.check_refund(purchase, req.machine_id, req.hours, totals)
        released = release_money(
            self._s, self._ctx, self._now, purchase.id, value, f"Refund of {req.hours} hours (request {req.id})"
        )
        self._ledger.add(
            purchase,
            req.machine_id,
            T.REFUNDED,
            req.hours,
            adjustment_request_id=req.id,
            reason=req.reason,
            policy_version=self.engine.eff.version_stamp,
        )
        pay_out = req.settlement is RefundSettlement.PAY_OUT
        kind = AdjustmentKind.HOURS_REFUND_PAYOUT if pay_out else AdjustmentKind.HOURS_REFUND_CREDIT
        record = money_record(
            self._s,
            self._ctx,
            self._now,
            kind=kind,
            customer_id=req.customer_id,
            amount=value,
            currency=req.currency,
            reason=req.reason,
            request_id=req.id,
        )
        payout = req.params.get("payout") or {}
        custodian = _uuid(payout.get("staff_member_id")) if pay_out else None
        if custodian is not None and payout.get("method") == HirePaymentMethod.CASH.value:
            custody_offset(
                self._s,
                self._ctx,
                self._now,
                staff_id=custodian,
                amount=-value,
                currency=req.currency,
                reason=f"Refund paid out in cash: {req.reason}"[:1000],
                entity_type="adjustment_request",
                entity_id=req.id,
                approved_by=self._ctx.user_id,
                requested_by=req.proposed_by,
            )
        return {
            "hours_refunded": str(req.hours),
            "value": str(value),
            "released": str(released),
            "settlement": req.settlement.value,
            "money_record_id": str(record.id),
            "payout": payout or None,
            "lot_hours_after": str(totals.remaining_on(req.machine_id) - req.hours),
            "customer_balance": str(customer_balance(self._s, self._tid, req.customer_id, req.currency)),
        }

    def consumed_entries(self, purchase_id: uuid.UUID) -> list[HoursLedgerEntry]:
        """The lot's consumption, newest first (web picker for correcting consumed hours)."""
        return list(
            self._s.execute(
                select(HoursLedgerEntry)
                .where(HoursLedgerEntry.purchase_id == purchase_id, HoursLedgerEntry.entry_type.in_(CONSUMED_LIKE))
                .order_by(HoursLedgerEntry.occurred_at.desc(), HoursLedgerEntry.id)
            ).scalars()
        )


def _uuid(value: object) -> uuid.UUID | None:
    return uuid.UUID(str(value)) if value else None
