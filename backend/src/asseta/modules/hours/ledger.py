"""The hours ledger: append entries and derive every balance from them (nothing is stored as a balance).

Purchase level: activated (ACTIVATED) - consumed - expired - reversed = remaining; transfers move hours between
machines of the same purchase and net to zero. Machine level: the signed sum of the entries on that machine.
Expiry is FIFO over activation lots: deductions use the earliest-expiring lots first."""

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import ROUND_FLOOR, Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import Select, case, func, select
from sqlalchemy.orm import Session

from asseta.modules.finance.models import CustomerPayment, SettlementStatus
from asseta.modules.hours.models import (
    SIGN,
    ActivationSource,
    HoursLedgerEntry,
    HoursPaymentAllocation,
    HoursPurchase,
    LedgerEntryType,
)

ZERO = Decimal(0)
T = LedgerEntryType


def floor_to(value: Decimal, step: Decimal) -> Decimal:
    if value <= 0:
        return ZERO
    return ((value / step).to_integral_value(rounding=ROUND_FLOOR) * step).quantize(Decimal("0.01"))


@dataclass
class MachineTotals:
    by_type: dict[LedgerEntryType, Decimal] = field(default_factory=lambda: defaultdict(lambda: ZERO))

    @property
    def remaining(self) -> Decimal:
        return sum((SIGN[t] * h for t, h in self.by_type.items()), ZERO)


@dataclass
class PurchaseTotals:
    hours: Decimal
    machines: dict[uuid.UUID, MachineTotals]
    activated_payment: Decimal
    activated_credit: Decimal

    def total(self, t: LedgerEntryType) -> Decimal:
        return sum((m.by_type[t] for m in self.machines.values()), ZERO)

    @property
    def activated(self) -> Decimal:
        return self.total(T.ACTIVATED)

    @property
    def net_activated(self) -> Decimal:
        """Activated hours still owed for (reversals withdraw activation; expiry does not)."""
        return self.activated - self.total(T.REVERSAL) - self.total(T.REFUNDED)

    @property
    def remaining(self) -> Decimal:
        return sum((m.remaining for m in self.machines.values()), ZERO)

    @property
    def provisional(self) -> Decimal:
        """Hours currently held by running jobs under daily drawdown (drawn provisionally, not yet final)."""
        return self.total(T.PROVISIONAL) - self.total(T.PROVISIONAL_REVERSED)

    def remaining_on(self, machine_id: uuid.UUID) -> Decimal:
        m = self.machines.get(machine_id)
        return m.remaining if m else ZERO


def purchase_totals(session: Session, purchase: HoursPurchase) -> PurchaseTotals:
    machines: dict[uuid.UUID, MachineTotals] = defaultdict(MachineTotals)
    machines[purchase.machine_id]  # the original machine always appears
    paid = credit = ZERO
    rows = session.execute(
        select(
            HoursLedgerEntry.machine_id,
            HoursLedgerEntry.entry_type,
            HoursLedgerEntry.activation_source,
            func.sum(HoursLedgerEntry.hours),
        )
        .where(HoursLedgerEntry.purchase_id == purchase.id)
        .group_by(HoursLedgerEntry.machine_id, HoursLedgerEntry.entry_type, HoursLedgerEntry.activation_source)
    )
    for machine_id, entry_type, source, hours in rows:
        machines[machine_id].by_type[entry_type] += Decimal(hours)
        if source is ActivationSource.PAYMENT:
            paid += Decimal(hours)
        elif source is ActivationSource.CREDIT:
            credit += Decimal(hours)
    return PurchaseTotals(purchase.hours, dict(machines), paid, credit)


def purchase_totals_bulk(session: Session, purchases: list[HoursPurchase]) -> dict[uuid.UUID, PurchaseTotals]:
    """`purchase_totals` for many purchases in one query."""
    if not purchases:
        return {}
    wanted = {p.id for p in purchases}
    machines: dict[uuid.UUID, dict[uuid.UUID, MachineTotals]] = {
        p.id: defaultdict(MachineTotals, {p.machine_id: MachineTotals()}) for p in purchases
    }
    paid: dict[uuid.UUID, Decimal] = defaultdict(lambda: ZERO)
    credit: dict[uuid.UUID, Decimal] = defaultdict(lambda: ZERO)
    for purchase_id, machine_id, entry_type, source, hours in session.execute(
        select(
            HoursLedgerEntry.purchase_id,
            HoursLedgerEntry.machine_id,
            HoursLedgerEntry.entry_type,
            HoursLedgerEntry.activation_source,
            func.sum(HoursLedgerEntry.hours),
        )
        .where(HoursLedgerEntry.purchase_id.in_(wanted))
        .group_by(
            HoursLedgerEntry.purchase_id,
            HoursLedgerEntry.machine_id,
            HoursLedgerEntry.entry_type,
            HoursLedgerEntry.activation_source,
        )
    ):
        machines[purchase_id][machine_id].by_type[entry_type] += Decimal(hours)
        if source is ActivationSource.PAYMENT:
            paid[purchase_id] += Decimal(hours)
        elif source is ActivationSource.CREDIT:
            credit[purchase_id] += Decimal(hours)
    return {p.id: PurchaseTotals(p.hours, dict(machines[p.id]), paid[p.id], credit[p.id]) for p in purchases}


class PurchaseQueue(StrEnum):
    AWAITING_ACTIVATION = "AWAITING_ACTIVATION"  # hours bought and not yet activated
    UNPAID = "UNPAID"  # awaiting activation with no payment waiting to be confirmed
    UNCONFIRMED = "UNCONFIRMED"  # awaiting activation with a claimed payment the office has not confirmed


def purchase_queue_select() -> Any:
    """One row per open purchase with hours still awaiting activation: (purchase, awaiting, verified, claimed)."""
    e, a, p, c = HoursLedgerEntry, HoursPaymentAllocation, HoursPurchase, CustomerPayment
    signed = case(
        (e.entry_type == T.ACTIVATED, e.hours),
        (e.entry_type.in_((T.REVERSAL, T.REFUNDED)), -e.hours),
        else_=ZERO,
    )
    net = select(e.purchase_id.label("id"), func.sum(signed).label("net")).group_by(e.purchase_id).subquery("net")
    money = (
        select(
            a.purchase_id.label("id"),
            func.sum(case((c.status == SettlementStatus.VERIFIED, a.amount), else_=ZERO)).label("verified"),
            func.sum(case((c.status == SettlementStatus.CLAIMED, a.amount), else_=ZERO)).label("claimed"),
        )
        .join(c, c.id == a.payment_id)
        .where(a.released_at.is_(None))
        .group_by(a.purchase_id)
        .subquery("money")
    )
    awaiting = p.hours - func.coalesce(net.c.net, ZERO)
    return (
        select(
            p,
            awaiting.label("awaiting"),
            func.coalesce(money.c.verified, ZERO).label("verified"),
            func.coalesce(money.c.claimed, ZERO).label("claimed"),
        )
        .outerjoin(net, net.c.id == p.id)
        .outerjoin(money, money.c.id == p.id)
        .where(p.cancelled_at.is_(None), awaiting > 0)
    )


def purchase_queue_ids(queue: PurchaseQueue) -> Select[Any]:
    """Purchase ids in a queue (the filter behind the dashboard's purchase figures)."""
    sub = purchase_queue_select().subquery("queue")
    stmt = select(sub.c.id)
    if queue is PurchaseQueue.UNPAID:
        return stmt.where(sub.c.claimed <= 0)
    if queue is PurchaseQueue.UNCONFIRMED:
        return stmt.where(sub.c.claimed > 0)
    return stmt


def allocated_amounts(session: Session, purchase_id: uuid.UUID) -> tuple[Decimal, Decimal]:
    """(verified, claimed-unverified) money linked to the purchase by active allocations."""
    rows = session.execute(
        select(CustomerPayment.status, func.sum(HoursPaymentAllocation.amount))
        .join(CustomerPayment, CustomerPayment.id == HoursPaymentAllocation.payment_id)
        .where(HoursPaymentAllocation.purchase_id == purchase_id, HoursPaymentAllocation.released_at.is_(None))
        .group_by(CustomerPayment.status)
    )
    by = {status: Decimal(total) for status, total in rows}
    return by.get(SettlementStatus.VERIFIED, ZERO), by.get(SettlementStatus.CLAIMED, ZERO)


def active_allocated(
    session: Session, *, purchase_id: uuid.UUID | None = None, payment_id: uuid.UUID | None = None
) -> Decimal:
    """Allocations of non-rejected payments that are still active (claimed allocations reserve capacity)."""
    stmt = (
        select(func.coalesce(func.sum(HoursPaymentAllocation.amount), 0))
        .join(CustomerPayment, CustomerPayment.id == HoursPaymentAllocation.payment_id)
        .where(HoursPaymentAllocation.released_at.is_(None), CustomerPayment.status != SettlementStatus.REJECTED)
    )
    if purchase_id is not None:
        stmt = stmt.where(HoursPaymentAllocation.purchase_id == purchase_id)
    if payment_id is not None:
        stmt = stmt.where(HoursPaymentAllocation.payment_id == payment_id)
    return Decimal(session.execute(stmt).scalar_one())


def derived_status(purchase: HoursPurchase, totals: PurchaseTotals) -> str:
    if purchase.cancelled_at is not None:
        return "CANCELLED"
    activated = totals.activated
    if activated <= 0:
        return "AWAITING_PAYMENT"
    if activated < purchase.hours:
        return "PARTLY_ACTIVE"
    if totals.remaining > 0:
        return "ACTIVE"
    used = totals.total(T.CONSUMED) + totals.provisional
    return "EXPIRED" if totals.total(T.EXPIRED) > 0 and used <= 0 else "CONSUMED"


class LedgerWriter:
    def __init__(self, session: Session, tenant_id: uuid.UUID, actor: uuid.UUID | None, now: datetime):
        self._s, self._tid, self._actor, self._now = session, tenant_id, actor, now

    def add(
        self,
        purchase: HoursPurchase,
        machine_id: uuid.UUID,
        entry_type: LedgerEntryType,
        hours: Decimal,
        *,
        source: ActivationSource | None = None,
        expires_at: datetime | None = None,
        payment_id: uuid.UUID | None = None,
        job_id: uuid.UUID | None = None,
        allocation_id: uuid.UUID | None = None,
        transfer_id: uuid.UUID | None = None,
        cancellation_id: uuid.UUID | None = None,
        adjustment_request_id: uuid.UUID | None = None,
        reason: str | None = None,
        policy_version: str | None = None,
        usage_day: date | None = None,
    ) -> HoursLedgerEntry:
        entry = HoursLedgerEntry(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            purchase_id=purchase.id,
            customer_id=purchase.customer_id,
            machine_id=machine_id,
            entry_type=entry_type,
            hours=hours,
            occurred_at=self._now,
            activation_source=source,
            expires_at=expires_at,
            payment_id=payment_id,
            job_id=job_id,
            allocation_id=allocation_id,
            transfer_id=transfer_id,
            cancellation_id=cancellation_id,
            adjustment_request_id=adjustment_request_id,
            reason=reason,
            policy_version=policy_version,
            usage_day=usage_day,
            created_by=self._actor,
            created_at=self._now,
        )
        self._s.add(entry)
        self._s.flush()
        return entry


def expiry_of(now: datetime, expiry_days: int | None) -> datetime | None:
    return now + timedelta(days=expiry_days) if expiry_days else None


def due_to_expire(session: Session, purchase: HoursPurchase, totals: PurchaseTotals, at: datetime) -> Decimal:
    """Activated hours in lots expiring at or before `at` that FIFO deductions have not already used."""
    lots_due = Decimal(
        session.execute(
            select(func.coalesce(func.sum(HoursLedgerEntry.hours), 0)).where(
                HoursLedgerEntry.purchase_id == purchase.id,
                HoursLedgerEntry.entry_type == T.ACTIVATED,
                HoursLedgerEntry.expires_at.is_not(None),
                HoursLedgerEntry.expires_at <= at,
            )
        ).scalar_one()
    )
    used = (
        totals.total(T.CONSUMED)
        + totals.total(T.REVERSAL)
        + totals.total(T.REFUNDED)
        + totals.total(T.EXPIRED)
        + totals.total(T.CORRECTION_DEDUCT)
        - totals.total(T.CORRECTION_ADD)
        + totals.provisional
    )
    return min(max(ZERO, lots_due - used), max(ZERO, totals.remaining))


def next_expiry(session: Session, purchase_id: uuid.UUID, after: datetime) -> datetime | None:
    value: datetime | None = session.execute(
        select(func.min(HoursLedgerEntry.expires_at)).where(
            HoursLedgerEntry.purchase_id == purchase_id,
            HoursLedgerEntry.entry_type == T.ACTIVATED,
            HoursLedgerEntry.expires_at > after,
        )
    ).scalar_one_or_none()
    return value
