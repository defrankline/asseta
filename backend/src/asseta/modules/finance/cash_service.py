"""Supervisor cash custody (R1-G, §10 #8): floats, cash collections, cash-paid approved expenses and handovers.

Daily reconciliation per supervisor/currency, in tenant local days:
    outstanding = opening + floats + collections - approved spending - VERIFIED handovers
Claimed-but-unverified handovers, pending expenses and unverified collections are reported separately; claims
never reduce accountability until the office verifies them."""

import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound
from asseta.core.outbox import OutboxWriter
from asseta.core.signals import sod_violation
from asseta.modules.expenses.models import Expense, ExpensePaidFrom, ExpenseStatus
from asseta.modules.finance.common import (
    ZERO,
    currency_or_default,
    insert,
    local_bounds,
    local_date,
    resolve_custodian,
    resolve_staff,
    tenant_settings,
)
from asseta.modules.finance.dto import (
    CashCollectionIn,
    CashCustodyBalanceDto,
    CashCustodyEntryDto,
    CashFloatIn,
    CashHandoverDto,
    CashHandoverIn,
    CashReconciliationDayDto,
    CashReconciliationDto,
    CashSupervisorSummaryDto,
    CustomerPaymentDto,
    CustomerPaymentIn,
    SettlementDecisionIn,
)
from asseta.modules.finance.models import (
    CashHandover,
    CustomerPayment,
    HirePaymentMethod,
    SettlementStatus,
    SupervisorCashCustody,
)
from asseta.modules.finance.payment_service import CustomerPaymentService
from asseta.modules.fleet.models import StaffKind, StaffMember
from asseta.modules.identity.principal import RequestContext

TOPIC = "asseta.finance"
# Movement buckets; only the first four move `outstanding`.
FLOAT, COLLECTION, SPEND, HANDOVER = "floats", "collections", "spend", "handover"
CLAIMED_HANDOVER, PENDING_SPEND, UNVERIFIED_COLLECTION = "claimed_handover", "pending_spend", "unverified_collection"
SIGN = {FLOAT: 1, COLLECTION: 1, SPEND: -1, HANDOVER: -1}
_SUMMED = (
    "floats_issued",
    "collections",
    "approved_spending",
    "verified_handovers",
    "claimed_unverified_handovers",
    "pending_spending",
    "unverified_collections",
)


class CashCustodyService:
    def __init__(self, session: Session, ctx: RequestContext, now: datetime):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid, self._now = session, ctx, ctx.tenant_id, now
        self._audit = AuditService(session)

    # --- movements ------------------------------------------------------------------------------------------
    def issue_float(self, body: CashFloatIn) -> CashCustodyEntryDto:
        staff = resolve_staff(self._s, self._ctx, body.staff_member_id)
        row = SupervisorCashCustody(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            staff_member_id=staff.id,
            entry_type=body.entry_type,
            amount=body.amount,
            currency=currency_or_default(self._s, self._tid, body.currency),
            occurred_at=body.occurred_at or self._now,
            reference=body.reference,
            note=body.note,
            created_by=self._ctx.user_id,
            created_at=self._now,
        )
        self._s.add(row)
        self._s.flush()
        self._audit.record(
            actor=self._ctx.audit_actor(),
            action="finance.cash.float_issued",
            entity_type="supervisor_cash_custody",
            entity_id=row.id,
            tenant_id=self._tid,
            after={"staff_member_id": str(staff.id), "amount": str(row.amount), "currency": row.currency},
        )
        return CashCustodyEntryDto.model_validate(row)

    def record_collection(self, body: CashCollectionIn, source: str = "API") -> CustomerPaymentDto:
        staff = resolve_custodian(self._s, self._ctx, body.staff_member_id)
        payment = CustomerPaymentIn(
            customer_id=body.customer_id,
            amount=body.amount,
            currency=body.currency,
            method=HirePaymentMethod.CASH,
            reference=body.reference,
            received_at=body.received_at,
            received_by_staff_id=staff.id,
            note=body.note,
            client_id=body.client_id,
            allocations=body.allocations,
        )
        return CustomerPaymentService(self._s, self._ctx, self._now).record(payment, source)

    def record_handover(self, body: CashHandoverIn, source: str = "API") -> CashHandoverDto:
        if body.client_id is not None:
            existing = self._s.execute(
                select(CashHandover).where(CashHandover.client_id == body.client_id)
            ).scalar_one_or_none()
            if existing is not None:
                return CashHandoverDto.model_validate(existing)
        staff = resolve_custodian(self._s, self._ctx, body.staff_member_id)
        row = CashHandover(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            client_id=body.client_id,
            staff_member_id=staff.id,
            amount=body.amount,
            currency=currency_or_default(self._s, self._tid, body.currency),
            handed_at=body.handed_at,
            reference=body.reference,
            note=body.note,
            status=SettlementStatus.CLAIMED,
            source=source,
            recorded_by=self._ctx.user_id,
            recorded_at=self._now,
        )
        insert(self._s, row, "DUPLICATE_HANDOVER", "Handover already recorded")
        self._audit.record(
            actor=self._ctx.audit_actor(source.lower()),
            action="finance.handover.recorded",
            entity_type="cash_handover",
            entity_id=row.id,
            tenant_id=self._tid,
            after={"staff_member_id": str(staff.id), "amount": str(row.amount), "status": "CLAIMED"},
        )
        OutboxWriter(self._s).emit(
            topic=TOPIC,
            event_type="CashHandoverRecorded",
            key=str(staff.id),
            payload={
                "handover_id": str(row.id),
                "staff_member_id": str(staff.id),
                "amount": str(row.amount),
                "currency": row.currency,
            },
            tenant_id=self._tid,
        )
        return CashHandoverDto.model_validate(row)

    def decide_handover(self, handover_id: uuid.UUID, body: SettlementDecisionIn) -> CashHandoverDto:
        row = self._s.execute(
            select(CashHandover).where(CashHandover.id == handover_id).with_for_update()
        ).scalar_one_or_none()
        if row is None:
            raise NotFound("Handover not found")
        if row.status is not SettlementStatus.CLAIMED:
            raise Conflict(f"Handover already {row.status.value}", code="HANDOVER_ALREADY_DECIDED")
        if row.recorded_by == self._ctx.user_id:
            sod_violation(self._tid, self._ctx.user_id, "verify", "cash_handover", row.id)
            raise BusinessRuleViolation("The recorder of a handover cannot verify it", code="SEGREGATION_OF_DUTIES")
        row.status = SettlementStatus.VERIFIED if body.verified else SettlementStatus.REJECTED
        row.verified_by, row.verified_at, row.decision_note = self._ctx.user_id, self._now, body.note
        self._s.flush()
        self._audit.record(
            actor=self._ctx.audit_actor(),
            action=f"finance.handover.{row.status.value.lower()}",
            entity_type="cash_handover",
            entity_id=row.id,
            tenant_id=self._tid,
            before={"status": "CLAIMED"},
            after={"status": row.status.value, "amount": str(row.amount)},
            reason=body.note,
        )
        if row.status is SettlementStatus.VERIFIED:
            OutboxWriter(self._s).emit(
                topic=TOPIC,
                event_type="CashHandoverVerified",
                key=str(row.staff_member_id),
                payload={
                    "handover_id": str(row.id),
                    "staff_member_id": str(row.staff_member_id),
                    "amount": str(row.amount),
                    "currency": row.currency,
                },
                tenant_id=self._tid,
            )
        return CashHandoverDto.model_validate(row)

    # --- reconciliation -------------------------------------------------------------------------------------
    def _movements(self, staff_id: uuid.UUID, currency: str, end: datetime) -> list[tuple[datetime, str, Decimal]]:
        out: list[tuple[datetime, str, Decimal]] = []
        for c in self._s.execute(
            select(SupervisorCashCustody).where(
                SupervisorCashCustody.staff_member_id == staff_id,
                SupervisorCashCustody.currency == currency,
                SupervisorCashCustody.occurred_at < end,
            )
        ).scalars():
            out.append((c.occurred_at, FLOAT, c.amount))
        for p in self._s.execute(
            select(CustomerPayment).where(
                CustomerPayment.received_by_staff_id == staff_id,
                CustomerPayment.method == HirePaymentMethod.CASH,
                CustomerPayment.currency == currency,
                CustomerPayment.status != SettlementStatus.REJECTED,
                CustomerPayment.received_at < end,
            )
        ).scalars():
            out.append((p.received_at, COLLECTION, p.amount))
            if p.status is SettlementStatus.CLAIMED:
                out.append((p.received_at, UNVERIFIED_COLLECTION, p.amount))
        for e in self._s.execute(
            select(Expense).where(
                Expense.custodian_staff_id == staff_id,
                Expense.paid_from == ExpensePaidFrom.CASH_CUSTODY,
                Expense.currency == currency,
                Expense.status != ExpenseStatus.REJECTED,
                Expense.incurred_at < end,
            )
        ).scalars():
            out.append((e.incurred_at, SPEND if e.status is ExpenseStatus.APPROVED else PENDING_SPEND, e.amount))
        for h in self._s.execute(
            select(CashHandover).where(
                CashHandover.staff_member_id == staff_id,
                CashHandover.currency == currency,
                CashHandover.status != SettlementStatus.REJECTED,
                CashHandover.handed_at < end,
            )
        ).scalars():
            out.append((h.handed_at, HANDOVER if h.status is SettlementStatus.VERIFIED else CLAIMED_HANDOVER, h.amount))
        return out

    def reconciliation(
        self, staff_id: uuid.UUID, currency: str | None, first: date, last: date
    ) -> CashReconciliationDto:
        staff = resolve_staff(self._s, self._ctx, staff_id, require_active=False)
        tz = tenant_settings(self._s, self._tid).timezone
        currency = currency_or_default(self._s, self._tid, currency)
        start, end = local_bounds(tz, first, last)
        opening, claimed_total = ZERO, ZERO
        per_day: dict[date, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
        for at, kind, amount in self._movements(staff.id, currency, end):
            if at < start:
                opening += SIGN.get(kind, 0) * amount
                claimed_total += amount if kind == CLAIMED_HANDOVER else ZERO
            else:
                per_day[local_date(tz, at)][kind] += amount
        days, day = [], first
        while day <= last:
            m = per_day[day]
            closing = opening + m[FLOAT] + m[COLLECTION] - m[SPEND] - m[HANDOVER]
            claimed_total += m[CLAIMED_HANDOVER]
            days.append(
                CashReconciliationDayDto(
                    day=day,
                    opening=opening,
                    floats_issued=m[FLOAT],
                    collections=m[COLLECTION],
                    approved_spending=m[SPEND],
                    verified_handovers=m[HANDOVER],
                    outstanding=closing,
                    claimed_unverified_handovers=m[CLAIMED_HANDOVER],
                    pending_spending=m[PENDING_SPEND],
                    unverified_collections=m[UNVERIFIED_COLLECTION],
                    outstanding_if_claims_verified=closing - claimed_total,
                )
            )
            opening, day = closing, day + timedelta(days=1)
        return CashReconciliationDto(staff_member_id=staff.id, currency=currency, timezone=tz, days=days)

    def outstanding_since(self, staff_id: uuid.UUID, currency: str) -> tuple[Decimal, datetime | None]:
        """Current outstanding custody (the reconciliation formula) and when it last rose above zero (None when
        nothing is held). Used by the Gate 6 cash-handover risk signal."""
        running, since = ZERO, None
        movements = self._movements(staff_id, currency, self._now + timedelta(days=3650))
        for at, kind, amount in sorted(movements, key=lambda m: m[0]):
            if kind not in SIGN:
                continue
            before, running = running, running + SIGN[kind] * amount
            if before <= 0 < running:
                since = at
            elif running <= 0:
                since = None
        return running, since

    def balances(self, staff_id: uuid.UUID | None) -> list[CashCustodyBalanceDto]:
        """Current custody per currency (for the supervisor's device and dashboards)."""
        staff = resolve_staff(self._s, self._ctx, staff_id, require_active=False)
        currencies = {
            *self._s.execute(
                select(SupervisorCashCustody.currency).where(SupervisorCashCustody.staff_member_id == staff.id)
            ).scalars(),
            *self._s.execute(
                select(CustomerPayment.currency).where(CustomerPayment.received_by_staff_id == staff.id)
            ).scalars(),
            *self._s.execute(select(CashHandover.currency).where(CashHandover.staff_member_id == staff.id)).scalars(),
            *self._s.execute(select(Expense.currency).where(Expense.custodian_staff_id == staff.id)).scalars(),
        } or {tenant_settings(self._s, self._tid).currency}
        out = []
        for currency in sorted(currencies):
            totals: dict[str, Decimal] = defaultdict(Decimal)
            for _, kind, amount in self._movements(staff.id, currency, self._now + timedelta(days=3650)):
                totals[kind] += amount
            out.append(
                CashCustodyBalanceDto(
                    staff_member_id=staff.id,
                    currency=currency,
                    outstanding=sum((SIGN[k] * totals[k] for k in SIGN), ZERO),
                    claimed_unverified_handovers=totals[CLAIMED_HANDOVER],
                    pending_spending=totals[PENDING_SPEND],
                    as_of=self._now,
                )
            )
        return out

    # --- the caller's own custody (field supervisor, COLLECT permission) -------------------------------------
    def my_collections(self, status: SettlementStatus | None) -> Select[CustomerPayment]:
        staff = resolve_staff(self._s, self._ctx, None, require_active=False)
        stmt = (
            select(CustomerPayment)
            .where(CustomerPayment.received_by_staff_id == staff.id, CustomerPayment.method == HirePaymentMethod.CASH)
            .order_by(CustomerPayment.received_at.desc(), CustomerPayment.id)
        )
        return stmt.where(CustomerPayment.status == status) if status else stmt

    def my_handovers(self, status: SettlementStatus | None) -> Select[CashHandover]:
        staff = resolve_staff(self._s, self._ctx, None, require_active=False)
        stmt = (
            select(CashHandover)
            .where(CashHandover.staff_member_id == staff.id)
            .order_by(CashHandover.handed_at.desc(), CashHandover.id)
        )
        return stmt.where(CashHandover.status == status) if status else stmt

    def my_reconciliation(self, day: date | None, currency: str | None) -> list[CashReconciliationDto]:
        """The caller's reconciliation for one tenant-local day (default today), one entry per currency held."""
        staff = resolve_staff(self._s, self._ctx, None, require_active=False)
        day = day or local_date(tenant_settings(self._s, self._tid).timezone, self._now)
        currencies = [currency] if currency else [b.currency for b in self.balances(staff.id)]
        return [self.reconciliation(staff.id, cur, day, day) for cur in currencies]

    # --- tenant-wide views (overview, cash report) ----------------------------------------------------------
    def custodians(self, staff_id: uuid.UUID | None = None) -> list[StaffMember]:
        """Active supervisors plus anyone who ever held custody (incl. inactive staff still holding cash)."""
        held = {
            *self._s.execute(select(SupervisorCashCustody.staff_member_id)).scalars(),
            *self._s.execute(
                select(CustomerPayment.received_by_staff_id).where(CustomerPayment.method == HirePaymentMethod.CASH)
            ).scalars(),
            *self._s.execute(select(CashHandover.staff_member_id)).scalars(),
            *self._s.execute(
                select(Expense.custodian_staff_id).where(Expense.paid_from == ExpensePaidFrom.CASH_CUSTODY)
            ).scalars(),
        }
        stmt = select(StaffMember).order_by(StaffMember.full_name, StaffMember.id)
        if staff_id is not None:
            stmt = stmt.where(StaffMember.id == staff_id)
        return [
            s
            for s in self._s.execute(stmt).scalars()
            if s.id in held or (s.kind is StaffKind.SUPERVISOR and s.is_active)
        ]

    def outstanding_by_currency(self) -> dict[str, Decimal]:
        """Cash currently held by all custodians, per currency (sum of `balances`)."""
        totals: dict[str, Decimal] = defaultdict(Decimal)
        for staff in self.custodians():
            for bal in self.balances(staff.id):
                totals[bal.currency] += bal.outstanding
        return dict(sorted(totals.items()))

    def supervisor_summaries(
        self, first: date, last: date, currency: str | None = None, staff_id: uuid.UUID | None = None
    ) -> list[CashSupervisorSummaryDto]:
        """Per custodian and currency: the reconciliation over [first, last] (tenant-local days), totalled."""
        out = []
        for staff in self.custodians(staff_id):
            currencies = [currency] if currency else [b.currency for b in self.balances(staff.id)]
            for cur in currencies:
                days = self.reconciliation(staff.id, cur, first, last).days
                sums: dict[str, Any] = {f: sum((getattr(d, f) for d in days), ZERO) for f in _SUMMED}
                out.append(
                    CashSupervisorSummaryDto(
                        staff_member_id=staff.id,
                        staff_name=staff.full_name,
                        currency=cur,
                        period_from=first,
                        period_to=last,
                        opening=days[0].opening,
                        closing_outstanding=days[-1].outstanding,
                        **sums,
                    )
                )
        return out
