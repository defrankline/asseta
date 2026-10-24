"""Field cash custody (R1-G, §10 #8; accountability design C): floats, cash collections, field-to-field transfers,
cash-paid approved expenses, remittances (cash handovers), approved adjustments and write-offs.

Expected balance per custodian/currency, in tenant local days, derived from every movement (never stored):
    outstanding = opening + floats (acknowledged where required) + collections + transfers in (acknowledged amount)
                  - transfers out (acknowledged amount) - approved spending - remittances (amount received)
                  + approved adjustments - written-off variances
Claims (unverified remittances, pending spending, unverified collections), transfers in transit, floats awaiting
acknowledgement and adjustments awaiting approval are reported separately; claims never reduce accountability
until confirmed. Every figure drills down to the transactions behind it (`transactions`)."""

import uuid
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound
from asseta.core.outbox import OutboxWriter
from asseta.modules.expenses.models import Expense, ExpensePaidFrom, ExpenseStatus
from asseta.modules.finance.common import (
    ZERO,
    currency_or_default,
    insert,
    local_bounds,
    local_date,
    resolve_staff,
    tenant_settings,
)
from asseta.modules.finance.custody_dto import CustodyTransactionDto, ReconciliationFigure
from asseta.modules.finance.custody_models import (
    CashDecisionStatus,
    CashFloatAcknowledgement,
    CashRetention,
    CashTransfer,
    CashTransferStatus,
    CashVariance,
    CustodyAdjustment,
    VarianceOutcome,
    VarianceSource,
)
from asseta.modules.finance.custody_rules import cash_policy, open_variance, refuse_sod, resolve_recorded_custodian
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
    RemittanceDecisionIn,
)
from asseta.modules.finance.models import (
    CashHandover,
    CustodyEntryType,
    CustomerPayment,
    HirePaymentMethod,
    SettlementStatus,
    SupervisorCashCustody,
)
from asseta.modules.finance.payment_service import CustomerPaymentService
from asseta.modules.fleet.models import StaffKind, StaffMember
from asseta.modules.identity.principal import RequestContext
from asseta.modules.policy.schemas import CashCustodyPolicy
from asseta.modules.policy.service import EffectivePolicy

TOPIC = "asseta.finance"
F = ReconciliationFigure
# Figures that move `outstanding`, with their sign (adjustment and write-off amounts are already signed).
SIGN: dict[str, int] = {
    F.FLOATS_ISSUED: 1,
    F.COLLECTIONS: 1,
    F.TRANSFERS_IN: 1,
    F.TRANSFERS_OUT: -1,
    F.APPROVED_SPENDING: -1,
    F.VERIFIED_HANDOVERS: -1,
    F.ADJUSTMENTS: 1,
    F.WRITTEN_OFF: -1,
}
_SUMMED = (
    "floats_issued",
    "collections",
    "transfers_in",
    "transfers_out",
    "approved_spending",
    "verified_handovers",
    "adjustments",
    "written_off",
    "claimed_unverified_handovers",
    "pending_spending",
    "unverified_collections",
)
FOREVER = timedelta(days=3650)


@dataclass(frozen=True)
class Movement:
    at: datetime
    figure: ReconciliationFigure
    amount: Decimal
    entity_type: str
    entity_id: uuid.UUID
    status: str
    reference: str | None = None
    note: str | None = None
    recorded_by: uuid.UUID | None = None
    counterparty_staff_id: uuid.UUID | None = None


def float_ack_status(entry: SupervisorCashCustody, ack: CashFloatAcknowledgement | None) -> str:
    if not entry.ack_required:
        return "NOT_REQUIRED"
    if ack is None:
        return "PENDING"
    return "DISPUTED" if ack.disputed else "ACKNOWLEDGED"


def custody_entry_dto(entry: SupervisorCashCustody, ack: CashFloatAcknowledgement | None) -> CashCustodyEntryDto:
    dto = CashCustodyEntryDto.model_validate(entry)
    dto.ack_status = float_ack_status(entry, ack)  # type: ignore[assignment]
    if ack is not None:
        dto.amount_received = ack.amount_received
        dto.acknowledged_by, dto.acknowledged_at = ack.acknowledged_by, ack.acknowledged_at
    return dto


class CashCustodyService:
    def __init__(self, session: Session, ctx: RequestContext, now: datetime):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid, self._now = session, ctx, ctx.tenant_id, now
        self._audit = AuditService(session)

    def _policy(self) -> EffectivePolicy[CashCustodyPolicy]:
        return cash_policy(self._s, self._tid, self._now)

    # --- movements ------------------------------------------------------------------------------------------
    def issue_float(self, body: CashFloatIn) -> CashCustodyEntryDto:
        staff = resolve_staff(self._s, self._ctx, body.staff_member_id)
        eff = self._policy()
        ack_required = body.entry_type is CustodyEntryType.FLOAT_ISSUED and eff.policy.float_ack_required
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
            ack_required=ack_required,
        )
        self._s.add(row)
        self._s.flush()
        self._audit.record(
            actor=self._ctx.audit_actor(),
            action="finance.cash.float_issued",
            entity_type="supervisor_cash_custody",
            entity_id=row.id,
            tenant_id=self._tid,
            after={
                "staff_member_id": str(staff.id),
                "amount": str(row.amount),
                "currency": row.currency,
                "ack_required": ack_required,
            },
            policy_version=eff.version_stamp[:64],
        )
        if ack_required:
            OutboxWriter(self._s).emit(
                topic=TOPIC,
                event_type="CashFloatIssued",
                key=str(staff.id),
                payload={
                    "entry_id": str(row.id),
                    "staff_member_id": str(staff.id),
                    "amount": str(row.amount),
                    "currency": row.currency,
                },
                tenant_id=self._tid,
            )
        return custody_entry_dto(row, None)

    def record_collection(self, body: CashCollectionIn, source: str = "API") -> CustomerPaymentDto:
        staff = resolve_recorded_custodian(self._s, self._ctx, body.staff_member_id, self._policy().policy)
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

    def approved_retention(self, staff_id: uuid.UUID, currency: str) -> Decimal:
        """Cash the custodian is currently authorised to keep (approved, unexpired retentions)."""
        rows = self._s.execute(
            select(CashRetention.amount).where(
                CashRetention.staff_member_id == staff_id,
                CashRetention.currency == currency,
                CashRetention.status == CashDecisionStatus.APPROVED,
                or_(CashRetention.valid_until.is_(None), CashRetention.valid_until > self._now),
            )
        ).scalars()
        return sum(rows, ZERO)

    def record_handover(self, body: CashHandoverIn, source: str = "API") -> CashHandoverDto:
        """Remittance to the company: CLAIMED until the office confirms the amount actually received. Under the
        full-remittance policy, a remittance leaving unretained cash with the custodian is flagged (not refused)."""
        if body.client_id is not None:
            existing = self._s.execute(
                select(CashHandover).where(CashHandover.client_id == body.client_id)
            ).scalar_one_or_none()
            if existing is not None:
                return CashHandoverDto.model_validate(existing)
        eff = self._policy()
        staff = resolve_recorded_custodian(self._s, self._ctx, body.staff_member_id, eff.policy)
        currency = currency_or_default(self._s, self._tid, body.currency)
        balance = self._balance(staff.id, currency)
        shortfall = None
        if eff.policy.remit_full_balance:
            gap = (
                balance.outstanding
                - balance.claimed_unverified_handovers
                - balance.in_transit_out
                - body.amount
                - balance.approved_retention
            )
            shortfall = gap if gap > 0 else None
        row = CashHandover(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            client_id=body.client_id,
            staff_member_id=staff.id,
            amount=body.amount,
            currency=currency,
            handed_at=body.handed_at,
            reference=body.reference,
            note=body.note,
            status=SettlementStatus.CLAIMED,
            source=source,
            recorded_by=self._ctx.user_id,
            recorded_at=self._now,
            expected_balance=balance.outstanding,
            partial_shortfall=shortfall,
        )
        insert(self._s, row, "DUPLICATE_HANDOVER", "Handover already recorded")
        self._audit.record(
            actor=self._ctx.audit_actor(source.lower()),
            action="finance.handover.recorded",
            entity_type="cash_handover",
            entity_id=row.id,
            tenant_id=self._tid,
            after={
                "staff_member_id": str(staff.id),
                "amount": str(row.amount),
                "status": "CLAIMED",
                "expected_balance": str(balance.outstanding),
                "partial_shortfall": str(shortfall) if shortfall is not None else None,
            },
            policy_version=eff.version_stamp[:64],
        )
        outbox = OutboxWriter(self._s)
        payload = {
            "handover_id": str(row.id),
            "staff_member_id": str(staff.id),
            "amount": str(row.amount),
            "currency": row.currency,
        }
        outbox.emit(
            topic=TOPIC, event_type="CashHandoverRecorded", key=str(staff.id), payload=payload, tenant_id=self._tid
        )
        if shortfall is not None:
            outbox.emit(
                topic=TOPIC,
                event_type="PartialRemittanceFlagged",
                key=str(staff.id),
                payload={**payload, "shortfall": str(shortfall), "expected_balance": str(balance.outstanding)},
                tenant_id=self._tid,
            )
        return CashHandoverDto.model_validate(row)

    def decide_handover(self, handover_id: uuid.UUID, body: RemittanceDecisionIn) -> CashHandoverDto:
        row = self._s.execute(
            select(CashHandover).where(CashHandover.id == handover_id).with_for_update()
        ).scalar_one_or_none()
        if row is None:
            raise NotFound("Handover not found")
        if row.status is not SettlementStatus.CLAIMED:
            raise Conflict(f"Handover already {row.status.value}", code="HANDOVER_ALREADY_DECIDED")
        if row.recorded_by == self._ctx.user_id:
            refuse_sod(self._ctx, "verify", "cash_handover", row.id, "The recorder of a handover cannot verify it")
        if not body.verified and body.amount_received is not None:
            raise BusinessRuleViolation("A rejected remittance has no amount received", code="AMOUNT_RECEIVED_INVALID")
        row.status = SettlementStatus.VERIFIED if body.verified else SettlementStatus.REJECTED
        row.verified_by, row.verified_at, row.decision_note = self._ctx.user_id, self._now, body.note
        if body.verified:
            row.amount_received = body.amount_received if body.amount_received is not None else row.amount
        self._s.flush()
        self._audit.record(
            actor=self._ctx.audit_actor(),
            action=f"finance.handover.{row.status.value.lower()}",
            entity_type="cash_handover",
            entity_id=row.id,
            tenant_id=self._tid,
            before={"status": "CLAIMED"},
            after={
                "status": row.status.value,
                "amount": str(row.amount),
                "amount_received": str(row.amount_received) if row.amount_received is not None else None,
            },
            reason=body.note,
        )
        if row.status is SettlementStatus.VERIFIED:
            assert row.amount_received is not None
            open_variance(
                self._s,
                self._ctx,
                self._now,
                source_type=VarianceSource.REMITTANCE,
                source_id=row.id,
                accountable_staff_id=row.staff_member_id,
                counterparty_staff_id=None,
                currency=row.currency,
                declared=row.amount,
                received=row.amount_received,
            )
            OutboxWriter(self._s).emit(
                topic=TOPIC,
                event_type="CashHandoverVerified",
                key=str(row.staff_member_id),
                payload={
                    "handover_id": str(row.id),
                    "staff_member_id": str(row.staff_member_id),
                    "amount": str(row.amount_received),
                    "currency": row.currency,
                },
                tenant_id=self._tid,
            )
        return CashHandoverDto.model_validate(row)

    # --- the ledger -----------------------------------------------------------------------------------------
    def _movements(self, staff_id: uuid.UUID, currency: str, end: datetime) -> list[Movement]:
        out: list[Movement] = []
        floats = list(
            self._s.execute(
                select(SupervisorCashCustody).where(
                    SupervisorCashCustody.staff_member_id == staff_id,
                    SupervisorCashCustody.currency == currency,
                    SupervisorCashCustody.occurred_at < end,
                )
            ).scalars()
        )
        acks = {
            a.custody_entry_id: a
            for a in self._s.execute(
                select(CashFloatAcknowledgement).where(
                    CashFloatAcknowledgement.custody_entry_id.in_([c.id for c in floats if c.ack_required])
                )
            ).scalars()
        }
        for c in floats:
            ack = acks.get(c.id)
            fl = Movement(
                c.occurred_at,
                F.FLOATS_ISSUED,
                c.amount,
                "supervisor_cash_custody",
                c.id,
                float_ack_status(c, ack),
                c.reference,
                c.note,
                c.created_by,
            )
            if not c.ack_required:
                out.append(fl)
            elif ack is None:
                out.append(replace(fl, figure=F.PENDING_FLOATS))
            elif not ack.disputed and ack.amount_received > 0 and ack.acknowledged_at < end:
                out.append(
                    replace(
                        fl,
                        at=ack.acknowledged_at,
                        amount=ack.amount_received,
                        note=ack.note,
                        recorded_by=ack.acknowledged_by,
                    )
                )
        for p in self._s.execute(
            select(CustomerPayment).where(
                CustomerPayment.received_by_staff_id == staff_id,
                CustomerPayment.method == HirePaymentMethod.CASH,
                CustomerPayment.currency == currency,
                CustomerPayment.status != SettlementStatus.REJECTED,
                CustomerPayment.received_at < end,
            )
        ).scalars():
            col = Movement(
                p.received_at,
                F.COLLECTIONS,
                p.amount,
                "customer_payment",
                p.id,
                p.status.value,
                p.reference,
                p.note,
                p.recorded_by,
            )
            out.append(col)
            if p.status is SettlementStatus.CLAIMED:
                out.append(replace(col, figure=F.UNVERIFIED_COLLECTIONS))
        for e in self._s.execute(
            select(Expense).where(
                Expense.custodian_staff_id == staff_id,
                Expense.paid_from == ExpensePaidFrom.CASH_CUSTODY,
                Expense.currency == currency,
                Expense.status != ExpenseStatus.REJECTED,
                Expense.incurred_at < end,
            )
        ).scalars():
            fig = F.APPROVED_SPENDING if e.status is ExpenseStatus.APPROVED else F.PENDING_SPENDING
            out.append(
                Movement(e.incurred_at, fig, e.amount, "expense", e.id, e.status.value, None, e.description, None)
            )
        for h in self._s.execute(
            select(CashHandover).where(
                CashHandover.staff_member_id == staff_id,
                CashHandover.currency == currency,
                CashHandover.status != SettlementStatus.REJECTED,
                CashHandover.handed_at < end,
            )
        ).scalars():
            verified = h.status is SettlementStatus.VERIFIED
            amount = (h.amount_received if h.amount_received is not None else h.amount) if verified else h.amount
            fig = F.VERIFIED_HANDOVERS if verified else F.CLAIMED_UNVERIFIED_HANDOVERS
            if amount > 0:
                out.append(
                    Movement(
                        h.handed_at,
                        fig,
                        amount,
                        "cash_handover",
                        h.id,
                        h.status.value,
                        h.reference,
                        h.note,
                        h.recorded_by,
                    )
                )
        for t in self._s.execute(
            select(CashTransfer).where(
                or_(CashTransfer.from_staff_id == staff_id, CashTransfer.to_staff_id == staff_id),
                CashTransfer.currency == currency,
                CashTransfer.status != CashTransferStatus.DISPUTED,
            )
        ).scalars():
            outgoing = t.from_staff_id == staff_id
            other = t.to_staff_id if outgoing else t.from_staff_id
            tm = Movement(
                t.transferred_at,
                F.IN_TRANSIT_OUT if outgoing else F.IN_TRANSIT_IN,
                t.amount_declared,
                "cash_transfer",
                t.id,
                t.status.value,
                None,
                t.note,
                t.recorded_by,
                other,
            )
            if t.status is CashTransferStatus.ACKNOWLEDGED:
                assert t.acknowledged_at is not None and t.amount_received is not None
                if t.acknowledged_at < end and t.amount_received > 0:
                    fig = F.TRANSFERS_OUT if outgoing else F.TRANSFERS_IN
                    out.append(replace(tm, at=t.acknowledged_at, figure=fig, amount=t.amount_received))
            elif t.transferred_at < end:
                out.append(tm)
        for a in self._s.execute(
            select(CustodyAdjustment).where(
                CustodyAdjustment.staff_member_id == staff_id,
                CustodyAdjustment.currency == currency,
                CustodyAdjustment.status != CashDecisionStatus.REJECTED,
            )
        ).scalars():
            am = Movement(
                a.created_at,
                F.PENDING_ADJUSTMENTS,
                a.amount,
                "custody_adjustment",
                a.id,
                a.status.value,
                None,
                a.reason,
                a.created_by,
            )
            if a.status is CashDecisionStatus.APPROVED:
                assert a.decided_at is not None
                if a.decided_at < end:
                    out.append(replace(am, at=a.decided_at, figure=F.ADJUSTMENTS))
            elif a.created_at < end:
                out.append(am)
        for v in self._s.execute(
            select(CashVariance).where(
                CashVariance.staff_member_id == staff_id,
                CashVariance.currency == currency,
                CashVariance.outcome == VarianceOutcome.WRITTEN_OFF,
            )
        ).scalars():
            assert v.resolved_at is not None
            if v.resolved_at < end:
                out.append(
                    Movement(
                        v.resolved_at,
                        F.WRITTEN_OFF,
                        v.amount,
                        "cash_variance",
                        v.id,
                        v.status.value,
                        None,
                        v.resolution_note,
                        v.resolved_by,
                        v.counterparty_staff_id,
                    )
                )
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
        for m in self._movements(staff.id, currency, end):
            if m.at < start:
                opening += SIGN.get(m.figure, 0) * m.amount
                claimed_total += m.amount if m.figure == F.CLAIMED_UNVERIFIED_HANDOVERS else ZERO
            else:
                per_day[local_date(tz, m.at)][m.figure] += m.amount
        days, day = [], first
        while day <= last:
            figs = per_day[day]
            closing = opening + sum((sign * figs[fig] for fig, sign in SIGN.items()), ZERO)
            claimed_total += figs[F.CLAIMED_UNVERIFIED_HANDOVERS]
            values: dict[str, Any] = {fig.value: figs[fig] for fig in F}
            days.append(
                CashReconciliationDayDto(
                    day=day,
                    opening=opening,
                    **values,
                    outstanding=closing,
                    outstanding_if_claims_verified=closing - claimed_total,
                )
            )
            opening, day = closing, day + timedelta(days=1)
        return CashReconciliationDto(staff_member_id=staff.id, currency=currency, timezone=tz, days=days)

    def transactions(
        self,
        staff_id: uuid.UUID,
        currency: str | None,
        first: date,
        last: date,
        figures: Iterable[ReconciliationFigure] | None = None,
    ) -> list[CustodyTransactionDto]:
        """The transactions behind each reconciliation figure over [first, last] (tenant-local days), latest first."""
        staff = resolve_staff(self._s, self._ctx, staff_id, require_active=False)
        tz = tenant_settings(self._s, self._tid).timezone
        currency = currency_or_default(self._s, self._tid, currency)
        start, end = local_bounds(tz, first, last)
        wanted = set(figures or F)
        rows = [m for m in self._movements(staff.id, currency, end) if m.at >= start and m.figure in wanted]
        rows.sort(key=lambda m: (m.at, m.entity_id), reverse=True)
        return [
            CustodyTransactionDto(
                figure=m.figure,
                occurred_at=m.at,
                amount=m.amount,
                currency=currency,
                entity_type=m.entity_type,
                entity_id=m.entity_id,
                status=m.status,
                reference=m.reference,
                note=m.note,
                recorded_by=m.recorded_by,
                counterparty_staff_id=m.counterparty_staff_id,
            )
            for m in rows
        ]

    def outstanding_since(self, staff_id: uuid.UUID, currency: str) -> tuple[Decimal, datetime | None]:
        """Current outstanding custody (the reconciliation formula) and when it last rose above zero (None when
        nothing is held). Used by the Gate 6 cash-handover risk signal."""
        running, since = ZERO, None
        movements = self._movements(staff_id, currency, self._now + FOREVER)
        for m in sorted(movements, key=lambda m: m.at):
            if m.figure not in SIGN:
                continue
            before, running = running, running + SIGN[m.figure] * m.amount
            if before <= 0 < running:
                since = m.at
            elif running <= 0:
                since = None
        return running, since

    def _currencies(self, staff_id: uuid.UUID) -> set[str]:
        return {
            *self._s.execute(
                select(SupervisorCashCustody.currency).where(SupervisorCashCustody.staff_member_id == staff_id)
            ).scalars(),
            *self._s.execute(
                select(CustomerPayment.currency).where(CustomerPayment.received_by_staff_id == staff_id)
            ).scalars(),
            *self._s.execute(select(CashHandover.currency).where(CashHandover.staff_member_id == staff_id)).scalars(),
            *self._s.execute(select(Expense.currency).where(Expense.custodian_staff_id == staff_id)).scalars(),
            *self._s.execute(
                select(CashTransfer.currency).where(
                    or_(CashTransfer.from_staff_id == staff_id, CashTransfer.to_staff_id == staff_id)
                )
            ).scalars(),
            *self._s.execute(
                select(CustodyAdjustment.currency).where(CustodyAdjustment.staff_member_id == staff_id)
            ).scalars(),
        }

    def _balance(self, staff_id: uuid.UUID, currency: str) -> CashCustodyBalanceDto:
        totals: dict[str, Decimal] = defaultdict(Decimal)
        for m in self._movements(staff_id, currency, self._now + FOREVER):
            totals[m.figure] += m.amount
        return CashCustodyBalanceDto(
            staff_member_id=staff_id,
            currency=currency,
            outstanding=sum((sign * totals[fig] for fig, sign in SIGN.items()), ZERO),
            claimed_unverified_handovers=totals[F.CLAIMED_UNVERIFIED_HANDOVERS],
            pending_spending=totals[F.PENDING_SPENDING],
            in_transit_out=totals[F.IN_TRANSIT_OUT],
            in_transit_in=totals[F.IN_TRANSIT_IN],
            pending_floats=totals[F.PENDING_FLOATS],
            approved_retention=self.approved_retention(staff_id, currency),
            as_of=self._now,
        )

    def balances(self, staff_id: uuid.UUID | None) -> list[CashCustodyBalanceDto]:
        """Current custody per currency (for the custodian's device and dashboards)."""
        staff = resolve_staff(self._s, self._ctx, staff_id, require_active=False)
        currencies = self._currencies(staff.id) or {tenant_settings(self._s, self._tid).currency}
        return [self._balance(staff.id, currency) for currency in sorted(currencies)]

    # --- the caller's own custody (field recorder, COLLECT permission) ---------------------------------------
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

    # --- tenant-wide views (overview, cash report, accountability dashboard) ---------------------------------
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
            *self._s.execute(select(CashTransfer.from_staff_id)).scalars(),
            *self._s.execute(select(CashTransfer.to_staff_id)).scalars(),
            *self._s.execute(select(CustodyAdjustment.staff_member_id)).scalars(),
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
