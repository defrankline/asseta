"""The hours ledger: append entries and derive every balance from them (nothing is stored as a balance).

Purchase level: activated (ACTIVATED) - consumed - expired - reversed = remaining; transfers move hours between
machines of the same purchase and net to zero. Machine level: the signed sum of the entries on that machine.
Expiry is FIFO over activation lots: deductions use the earliest-expiring lots first."""

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import ROUND_FLOOR, Decimal

from sqlalchemy import func, select
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
        return self.activated - self.total(T.REVERSAL)

    @property
    def remaining(self) -> Decimal:
        return sum((m.remaining for m in self.machines.values()), ZERO)

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
    return "EXPIRED" if totals.total(T.EXPIRED) > 0 and totals.total(T.CONSUMED) <= 0 else "CONSUMED"


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
        reason: str | None = None,
        policy_version: str | None = None,
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
            reason=reason,
            policy_version=policy_version,
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
    used = totals.total(T.CONSUMED) + totals.total(T.REVERSAL) + totals.total(T.EXPIRED)
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
