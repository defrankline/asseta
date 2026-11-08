"""Reversal of posted transactions (DEC-032 B4): a verified customer payment (bounced), a cash collection, an hours
purchase. Offsetting records only: the originals stay as recorded and receive a single reversal stamp (payment) or the
existing cancellation stamp (purchase). Forecast (`plan_*`) and application share the same computation."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.errors import BusinessRuleViolation, Conflict
from asseta.core.money import quantize
from asseta.modules.adjustments.models import AdjustmentRequest
from asseta.modules.adjustments.money import (
    ZERO,
    custody_offset,
    custody_outstanding,
    customer_balance,
    money_record,
    release_hire_allocations,
)
from asseta.modules.finance.invoice_service import HireInvoiceService, RecoveryLine
from asseta.modules.finance.models import (
    AdjustmentKind,
    CustomerPayment,
    HirePaymentAllocation,
    HirePaymentMethod,
    SettlementStatus,
)
from asseta.modules.hours.engine import HoursEngine, minor_units
from asseta.modules.hours.ledger import LedgerWriter, PurchaseTotals, allocated_amounts, floor_to, purchase_totals
from asseta.modules.hours.models import (
    HoursCancellation,
    HoursLedgerEntry,
    HoursPaymentAllocation,
    HoursPurchase,
    HoursTransfer,
    LedgerEntryType,
    RequestStatus,
)
from asseta.modules.identity.principal import RequestContext
from asseta.modules.intelligence.linking import CaseItem, CaseLinker
from asseta.modules.intelligence.models import CaseSourceType, SignalSeverity, SubjectType
from asseta.modules.policy.schemas import UsedHoursTreatment
from asseta.modules.policy.service import PolicyService

T = LedgerEntryType
USED_TITLE = "Hours were used on a payment that was later reversed"


@dataclass
class PurchasePlan:
    purchase: HoursPurchase
    unused: dict[uuid.UUID, Decimal] = field(default_factory=dict)  # hours to take off, per machine
    used_hours: Decimal = ZERO  # hours already used that no money now covers
    money_owed: Decimal = ZERO
    allocations: list[HoursPaymentAllocation] = field(default_factory=list)


@dataclass
class ReversalPlan:
    purchases: list[PurchasePlan]
    hire_released: Decimal = ZERO

    @property
    def unused_hours(self) -> Decimal:
        return sum((h for p in self.purchases for h in p.unused.values()), ZERO)

    @property
    def used_hours(self) -> Decimal:
        return sum((p.used_hours for p in self.purchases), ZERO)

    @property
    def money_owed(self) -> Decimal:
        return sum((p.money_owed for p in self.purchases), ZERO)

    def summary(self) -> dict[str, Any]:
        return {
            "unused_hours_removed": str(self.unused_hours),
            "used_hours": str(self.used_hours),
            "money_owed": str(self.money_owed),
            "hire_allocations_released": str(self.hire_released),
            "purchases": [
                {
                    "purchase_id": str(p.purchase.id),
                    "purchase_number": p.purchase.purchase_number,
                    "unused_hours": str(sum(p.unused.values(), ZERO)),
                    "used_hours": str(p.used_hours),
                    "money_owed": str(p.money_owed),
                }
                for p in self.purchases
            ],
        }


def used_hours_of(totals: PurchaseTotals) -> Decimal:
    return totals.total(T.CONSUMED) + totals.provisional


def _unused_by_machine(totals: PurchaseTotals, take: Decimal) -> dict[uuid.UUID, Decimal]:
    """Remaining hours per machine, largest balance first, up to `take`."""
    out: dict[uuid.UUID, Decimal] = {}
    left = take
    for machine_id, m in sorted(totals.machines.items(), key=lambda kv: (-kv[1].remaining, str(kv[0]))):
        if left <= 0:
            break
        if m.remaining <= 0:
            continue
        h = min(left, m.remaining)
        out[machine_id] = h
        left -= h
    return out


class ReversalEngine:
    def __init__(self, session: Session, ctx: RequestContext, now: datetime, engine: HoursEngine):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid, self._now = session, ctx, ctx.tenant_id, now
        self.engine = engine
        self._ledger = LedgerWriter(session, ctx.tenant_id, ctx.user_id, now)

    # --- planning (no writes) ---------------------------------------------------------------------------------
    def plan_payment(self, payment: CustomerPayment, lock: bool = True) -> ReversalPlan:
        """Per purchase the payment paid for: what its verified money would still activate without this payment; the
        unused hours above that come off, hours already used become money owed (the part this money was covering)."""
        allocs = list(
            self._s.execute(
                select(HoursPaymentAllocation)
                .where(HoursPaymentAllocation.payment_id == payment.id, HoursPaymentAllocation.released_at.is_(None))
                .order_by(HoursPaymentAllocation.purchase_id)
            ).scalars()
        )
        by_purchase: dict[uuid.UUID, list[HoursPaymentAllocation]] = {}
        for a in allocs:
            by_purchase.setdefault(a.purchase_id, []).append(a)
        plans = []
        for purchase_id, rows in by_purchase.items():
            purchase = self.engine.lock_purchase(purchase_id) if lock else self._s.get(HoursPurchase, purchase_id)
            assert purchase is not None
            amount = sum((a.amount for a in rows), ZERO)
            plan = self._plan_purchase(purchase, amount)
            plan.allocations = rows
            plans.append(plan)
        hire = sum(
            self._s.execute(
                select(HirePaymentAllocation.amount).where(
                    HirePaymentAllocation.payment_id == payment.id, HirePaymentAllocation.released_at.is_(None)
                )
            ).scalars(),
            ZERO,
        )
        return ReversalPlan(plans, hire)

    def _plan_purchase(self, purchase: HoursPurchase, money_removed: Decimal) -> PurchasePlan:
        totals = purchase_totals(self._s, purchase)
        plan = PurchasePlan(purchase)
        if purchase.amount <= 0 or purchase.effective_rate <= 0:
            return plan  # nothing was paid for these hours
        p = self.engine.policy
        verified, _ = allocated_amounts(self._s, purchase.id)
        after = max(ZERO, verified - money_removed)
        if p.partial_activation:
            funded = min(purchase.hours, floor_to(after / purchase.effective_rate, p.hours_increment))
        else:
            funded = purchase.hours if after >= purchase.amount else ZERO
        target = min(purchase.hours, funded + totals.activated_credit)
        remove = max(ZERO, totals.net_activated - target)
        unused = min(remove, max(ZERO, totals.remaining))
        plan.unused = _unused_by_machine(totals, unused)
        used = min(max(ZERO, remove - unused), max(ZERO, used_hours_of(totals)))
        plan.used_hours = used
        plan.money_owed = min(
            money_removed, quantize(used * purchase.effective_rate, minor_units(self._s, purchase.currency))
        )
        return plan

    def plan_purchase_reversal(self, purchase: HoursPurchase) -> PurchasePlan:
        """Reversing a purchase takes back all unused hours; money stays with the used hours it paid for, the rest
        returns to the customer's credit; used hours no money covers become money owed."""
        totals = purchase_totals(self._s, purchase)
        plan = PurchasePlan(purchase)
        plan.unused = _unused_by_machine(totals, max(ZERO, totals.remaining))
        used = max(ZERO, used_hours_of(totals))
        verified, _ = allocated_amounts(self._s, purchase.id)
        units = minor_units(self._s, purchase.currency)
        value_used = quantize(used * purchase.effective_rate, units)
        owed = max(ZERO, value_used - verified)
        if owed > 0:  # some used hours were never paid for (activated on credit, say)
            plan.used_hours = (
                (owed / purchase.effective_rate).quantize(Decimal("0.01")) if purchase.effective_rate > 0 else ZERO
            )
            plan.money_owed = owed
        return plan

    # --- application ------------------------------------------------------------------------------------------
    def _reversal_entries(self, plan: PurchasePlan, req: AdjustmentRequest) -> None:
        for machine_id, hours in plan.unused.items():
            self._ledger.add(
                plan.purchase,
                machine_id,
                T.REVERSAL,
                hours,
                adjustment_request_id=req.id,
                reason=f"Reversal: {req.reason}"[:1000],
                policy_version=self.engine.eff.version_stamp,
            )

    def _recovery_lines(self, plan: PurchasePlan) -> list[RecoveryLine]:
        """Who used the hours: newest jobs first, one line per job, summing to the plan's used hours and money."""
        rows = self._s.execute(
            select(
                HoursLedgerEntry.job_id,
                HoursLedgerEntry.machine_id,
                HoursLedgerEntry.entry_type,
                HoursLedgerEntry.hours,
            )
            .where(
                HoursLedgerEntry.purchase_id == plan.purchase.id,
                HoursLedgerEntry.job_id.is_not(None),
                HoursLedgerEntry.entry_type.in_([T.CONSUMED, T.PROVISIONAL, T.PROVISIONAL_REVERSED]),
            )
            .order_by(HoursLedgerEntry.occurred_at.desc(), HoursLedgerEntry.id)
        ).all()
        by_job: dict[tuple[uuid.UUID, uuid.UUID], Decimal] = {}
        for job_id, machine_id, entry_type, hours in rows:
            sign = 1 if entry_type in (T.CONSUMED, T.PROVISIONAL) else -1
            assert job_id is not None
            key = (job_id, machine_id)
            by_job[key] = by_job.get(key, ZERO) + sign * hours
        lines, left, money_left = [], plan.used_hours, plan.money_owed
        units = minor_units(self._s, plan.purchase.currency)
        number = plan.purchase.purchase_number
        for (job_id, machine_id), hours in by_job.items():
            if left <= 0:
                break
            take = min(hours, left)
            if take <= 0:
                continue
            amount = quantize(take * plan.purchase.effective_rate, units)
            amount = min(amount, money_left)
            lines.append(
                RecoveryLine(
                    job_id,
                    machine_id,
                    f"Hours used from {number} whose payment was reversed",
                    take,
                    plan.purchase.effective_rate,
                    amount,
                )
            )
            left -= take
            money_left -= amount
        if lines and money_left > 0:
            last = lines[-1]
            lines[-1] = RecoveryLine(
                last.job_id, last.machine_id, last.description, last.quantity, last.unit_price, last.amount + money_left
            )
        return lines

    def _owed(
        self, req: AdjustmentRequest, customer_id: uuid.UUID, currency: str, plans: list[PurchasePlan]
    ) -> dict[str, Any]:
        """Used hours that money no longer covers: a receivable or an investigation case (tenant policy)."""
        owed = [p for p in plans if p.money_owed > 0]
        if not owed:
            return {}
        total = sum((p.money_owed for p in owed), ZERO)
        hours = sum((p.used_hours for p in owed), ZERO)
        if self.engine.policy.reversal_used_hours_treatment is UsedHoursTreatment.CASE:
            return self._owed_case(req, customer_id, currency, total, hours)
        lines = [line for p in owed for line in self._recovery_lines(p)]
        inv = HireInvoiceService(self._s, self._ctx, self._now).issue_recovery(
            customer_id, currency, lines, f"Prepaid hours used; payment reversed (request {req.id}): {req.reason}"
        )
        return {
            "treatment": UsedHoursTreatment.RECEIVABLE.value,
            "recovery_invoice_id": str(inv.id),
            "recovery_invoice_number": inv.invoice_number,
            "money_owed": str(total),
            "used_hours": str(hours),
        }

    def _owed_case(
        self, req: AdjustmentRequest, customer_id: uuid.UUID, currency: str, total: Decimal, hours: Decimal
    ) -> dict[str, Any]:
        fraud = PolicyService(self._s).fraud_controls(self._tid, at=self._now)
        linker = CaseLinker(self._s, self._tid, self._now, fraud.policy.case_grouping_window_hours)
        case = linker.link(
            CaseItem(
                CaseSourceType.ADJUSTMENT,
                req.id,
                "REVERSAL_USED_HOURS",
                USED_TITLE,
                SignalSeverity.WARNING,
                self._now,
                {
                    "request_id": str(req.id),
                    "request_type": req.request_type.value,
                    "original_id": str(req.original_id),
                    "original_reference": req.original_reference,
                    "used_hours": str(hours),
                    "money_owed": str(total),
                    "currency": currency,
                },
                SubjectType.CUSTOMER,
                customer_id,
                self.engine.eff.version_stamp,
            )
        )
        return {
            "treatment": UsedHoursTreatment.CASE.value,
            "case_id": str(case.id) if case else None,
            "money_owed": str(total),
            "used_hours": str(hours),
        }

    def check_payment_reversible(self, payment: CustomerPayment) -> None:
        if payment.status is not SettlementStatus.VERIFIED:
            raise BusinessRuleViolation(
                "Only a verified payment can be reversed; reject a payment that is still claimed",
                code="PAYMENT_NOT_VERIFIED",
            )
        if payment.reversed_at is not None:
            raise Conflict("This payment is already reversed", code="PAYMENT_ALREADY_REVERSED")

    def apply_payment_reversal(self, req: AdjustmentRequest, payment: CustomerPayment) -> dict[str, Any]:
        self.check_payment_reversible(payment)
        assert req.customer_id is not None and req.currency is not None
        plan = self.plan_payment(payment)
        reason = f"Payment reversed (request {req.id}): {req.reason}"[:1000]
        payment.reversed_at, payment.reversal_id = self._now, req.id
        self._s.flush()
        hire = release_hire_allocations(self._s, self._ctx, self._now, payment.id, reason)
        for p in plan.purchases:
            for a in p.allocations:
                a.released_at, a.release_reason = self._now, reason
            self._s.flush()
            self._reversal_entries(p, req)
        record = money_record(
            self._s,
            self._ctx,
            self._now,
            kind=AdjustmentKind.PAYMENT_REVERSAL,
            customer_id=req.customer_id,
            amount=payment.amount,
            currency=req.currency,
            reason=req.reason,
            request_id=req.id,
        )
        out: dict[str, Any] = {
            **plan.summary(),
            "hire_allocations_released": str(hire),
            "money_record_id": str(record.id),
            "payment_amount": str(payment.amount),
        }
        out.update(self._owed(req, req.customer_id, req.currency, plan.purchases))
        if payment.method is HirePaymentMethod.CASH and payment.received_by_staff_id is not None:
            custody_offset(
                self._s,
                self._ctx,
                self._now,
                staff_id=payment.received_by_staff_id,
                amount=-payment.amount,
                currency=req.currency,
                reason=f"Collection reversed: {req.reason}"[:1000],
                entity_type="customer_payment",
                entity_id=payment.id,
                approved_by=self._ctx.user_id,
                requested_by=req.proposed_by,
            )
            out["custody_staff_id"] = str(payment.received_by_staff_id)
            out["custody_balance_after"] = str(
                custody_outstanding(self._s, self._ctx, self._now, payment.received_by_staff_id, req.currency)
            )
        out["customer_balance"] = str(customer_balance(self._s, self._tid, req.customer_id, req.currency))
        return out

    def apply_purchase_reversal(self, req: AdjustmentRequest, purchase: HoursPurchase) -> dict[str, Any]:
        if purchase.cancelled_at is not None:
            raise Conflict("The purchase is already cancelled", code="PURCHASE_CANCELLED")
        plan = self.plan_purchase_reversal(purchase)
        totals = purchase_totals(self._s, purchase)
        used = max(ZERO, used_hours_of(totals))
        verified, _ = allocated_amounts(self._s, purchase.id)
        units = minor_units(self._s, purchase.currency)
        keep = min(verified, quantize(used * purchase.effective_rate, units))
        reason = f"Purchase reversed (request {req.id}): {req.reason}"[:1000]
        released = self._release_all_but(purchase.id, keep, reason)
        self._reversal_entries(plan, req)
        for pending in self._s.execute(
            select(HoursTransfer)
            .where(HoursTransfer.purchase_id == purchase.id, HoursTransfer.status == RequestStatus.PENDING)
            .with_for_update()
        ).scalars():
            pending.status, pending.decided_by, pending.decided_at, pending.decision_note = (
                RequestStatus.REJECTED,
                self._ctx.user_id,
                self._now,
                "Purchase reversed",
            )
        for pending_c in self._s.execute(
            select(HoursCancellation)
            .where(HoursCancellation.purchase_id == purchase.id, HoursCancellation.status == RequestStatus.PENDING)
            .with_for_update()
        ).scalars():
            pending_c.status, pending_c.decided_by, pending_c.decided_at, pending_c.decision_note = (
                RequestStatus.REJECTED,
                self._ctx.user_id,
                self._now,
                "Purchase reversed",
            )
        purchase.cancelled_at, purchase.cancelled_by, purchase.cancellation_id = self._now, self._ctx.user_id, req.id
        self._s.flush()
        assert req.customer_id is not None and req.currency is not None
        out: dict[str, Any] = {
            "unused_hours_removed": str(sum(plan.unused.values(), ZERO)),
            "used_hours_kept": str(used),
            "money_released_to_credit": str(released),
        }
        out.update(self._owed(req, req.customer_id, req.currency, [plan]))
        out["customer_balance"] = str(customer_balance(self._s, self._tid, req.customer_id, req.currency))
        return out

    def _release_all_but(self, purchase_id: uuid.UUID, keep: Decimal, reason: str) -> Decimal:
        """Release every allocation of the purchase except `keep` of verified money (claimed links too: never kept)."""
        released = ZERO
        rows = list(
            self._s.execute(
                select(HoursPaymentAllocation, CustomerPayment.status)
                .join(CustomerPayment, CustomerPayment.id == HoursPaymentAllocation.payment_id)
                .where(HoursPaymentAllocation.purchase_id == purchase_id, HoursPaymentAllocation.released_at.is_(None))
                .with_for_update(of=HoursPaymentAllocation)
                .order_by(HoursPaymentAllocation.created_at)
            )
        )
        left = keep
        for alloc, status in rows:
            if status is SettlementStatus.VERIFIED and left > 0:
                kept = min(alloc.amount, left)
                left -= kept
                if kept == alloc.amount:
                    continue
                self._split(alloc, alloc.amount - kept, reason)
                released += alloc.amount - kept
                continue
            alloc.released_at, alloc.release_reason = self._now, reason
            released += alloc.amount
        self._s.flush()
        return released

    def _split(self, alloc: HoursPaymentAllocation, part_released: Decimal, reason: str) -> None:
        """Release an allocation whole and re-write the kept part as a new row (amounts never change)."""
        assert self._ctx.tenant_id is not None
        kept = alloc.amount - part_released
        alloc.released_at, alloc.release_reason = self._now, reason
        self._s.flush()
        self._s.add(
            HoursPaymentAllocation(
                id=uuid.uuid4(),
                tenant_id=self._ctx.tenant_id,
                payment_id=alloc.payment_id,
                purchase_id=alloc.purchase_id,
                amount=kept,
                created_by=self._ctx.user_id,
                created_at=self._now,
            )
        )
        self._s.flush()


__all__ = ["PurchasePlan", "ReversalEngine", "ReversalPlan", "used_hours_of"]
