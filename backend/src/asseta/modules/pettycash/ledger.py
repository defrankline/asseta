"""The petty cash fund ledger (DEC-033). A fund's balance is derived from its records, never stored:

    balance = funded                     fundings and top-ups the holder acknowledged (the amount received)
            - spent                      approved expenses paid from the fund (not linked to an advance)
            - returned                   returns the office confirmed (the amount it counted)
            + adjustments                approved fund adjustments (signed)
            - written_off                written-off COUNT and RETURN differences (signed: a surplus raises it)
            - advances_issued            cash handed out as advances (phase 3)
            + advance_change_returned    change handed back when an advance is cleared

Nothing is counted twice: an advance leaves the fund once, when issued; the expenses linked to it are paid from the
advance cash, so they are costs (profitability) but never deducted from the fund again (`advance_spending` is shown
for information only), and the change comes back when the advance is cleared. A difference on a funding (sits with the
office, as a float difference does) or on an advance (sits with the recipient) is outside the fund: its write-off never
moves the fund. Fundings, top-ups, returns and advances are transfers, never costs.

Shown apart, never reducing accountability until confirmed: pending_spending, awaiting_acknowledgement,
returns_claimed, open_return_differences, pending_adjustments, advances_outstanding. The cash expected in the box (and
what a holder may still spend) is available_to_spend = balance - pending_spending - returns_claimed -
open_return_differences; a count compares against it. Every figure drills down to its records (`transactions`)."""

import uuid
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from asseta.modules.expenses.models import Expense, ExpenseStatus
from asseta.modules.finance.common import ZERO, local_bounds, tenant_settings
from asseta.modules.finance.custody_models import (
    FUND_WRITE_OFF_SOURCES,
    CashDecisionStatus,
    CashVariance,
    VarianceOutcome,
    VarianceSource,
    VarianceStatus,
)
from asseta.modules.pettycash.dto import (
    FundFigure,
    PettyCashBalanceDto,
    PettyCashStatementDto,
    PettyCashStatementLineDto,
    PettyCashTransactionDto,
    TopUpExpenseDto,
    TopUpSuggestionDto,
)
from asseta.modules.pettycash.models import (
    INBOUND,
    AdvanceStatus,
    MovementKind,
    MovementStatus,
    PettyCashAdjustment,
    PettyCashAdvance,
    PettyCashCount,
    PettyCashFund,
    PettyCashMovement,
)
from asseta.modules.policy.service import PolicyService

F = FundFigure
SIGN: dict[FundFigure, int] = {
    F.FUNDED: 1,
    F.SPENT: -1,
    F.RETURNED: -1,
    F.ADJUSTMENTS: 1,
    F.WRITTEN_OFF: -1,
    F.ADVANCES_ISSUED: -1,
    F.ADVANCE_CHANGE_RETURNED: 1,
}
FOREVER = timedelta(days=3650)
IN_FLIGHT = (MovementStatus.PROPOSED, MovementStatus.APPROVED, MovementStatus.ISSUED)


@dataclass(frozen=True)
class FundMove:
    at: datetime
    figure: FundFigure
    amount: Decimal
    entity_type: str
    entity_id: uuid.UUID
    status: str
    reference: str | None = None
    note: str | None = None
    recorded_by: uuid.UUID | None = None


@dataclass(frozen=True)
class Figures:
    totals: dict[FundFigure, Decimal]

    def __getitem__(self, figure: FundFigure) -> Decimal:
        return self.totals.get(figure, ZERO)

    @property
    def balance(self) -> Decimal:
        return sum((sign * self[fig] for fig, sign in SIGN.items()), ZERO)

    @property
    def available(self) -> Decimal:
        return self.balance - self[F.PENDING_SPENDING] - self[F.RETURNS_CLAIMED] - self[F.OPEN_RETURN_DIFFERENCES]


class FundLedger:
    def __init__(self, session: Session, now: datetime):
        self._s, self._now = session, now

    def moves(self, fund: PettyCashFund, end: datetime | None = None) -> list[FundMove]:
        end = end or self._now + FOREVER
        out: list[FundMove] = []
        for m in self._s.execute(select(PettyCashMovement).where(PettyCashMovement.fund_id == fund.id)).scalars():
            base = ("petty_cash_movement", m.id, m.status.value, m.number, m.note)
            if m.kind in INBOUND:
                if m.status is MovementStatus.ACKNOWLEDGED and m.received_at is not None and m.received_at < end:
                    if m.amount_received:
                        out.append(FundMove(m.received_at, F.FUNDED, m.amount_received, *base, m.received_by))
                elif m.status is MovementStatus.ISSUED and m.issued_at is not None and m.issued_at < end:
                    out.append(FundMove(m.issued_at, F.AWAITING_ACKNOWLEDGEMENT, m.amount, *base, m.issued_by))
            elif m.status is MovementStatus.CONFIRMED and m.received_at is not None and m.received_at < end:
                if m.amount_received:
                    out.append(FundMove(m.received_at, F.RETURNED, m.amount_received, *base, m.received_by))
            elif m.status is MovementStatus.CLAIMED and m.created_at < end:
                out.append(FundMove(m.created_at, F.RETURNS_CLAIMED, m.amount, *base, m.created_by))
        for e in self._s.execute(
            select(Expense).where(
                Expense.petty_cash_fund_id == fund.id,
                Expense.status != ExpenseStatus.REJECTED,
                Expense.incurred_at < end,
            )
        ).scalars():
            if e.petty_cash_advance_id is not None:
                if e.status is ExpenseStatus.APPROVED:
                    out.append(self._expense(e, F.ADVANCE_SPENDING))
                continue
            out.append(self._expense(e, F.SPENT if e.status is ExpenseStatus.APPROVED else F.PENDING_SPENDING))
        for a in self._s.execute(
            select(PettyCashAdjustment).where(
                PettyCashAdjustment.fund_id == fund.id, PettyCashAdjustment.status != CashDecisionStatus.REJECTED
            )
        ).scalars():
            base = ("petty_cash_adjustment", a.id, a.status.value, a.number, a.reason)
            if a.status is CashDecisionStatus.APPROVED and a.decided_at is not None:
                if a.decided_at < end:
                    out.append(FundMove(a.decided_at, F.ADJUSTMENTS, a.amount, *base, a.decided_by))
            elif a.created_at < end:
                out.append(FundMove(a.created_at, F.PENDING_ADJUSTMENTS, a.amount, *base, a.created_by))
        for v in self._s.execute(select(CashVariance).where(CashVariance.petty_cash_fund_id == fund.id)).scalars():
            if (
                v.outcome is VarianceOutcome.WRITTEN_OFF
                and v.source_type in FUND_WRITE_OFF_SOURCES
                and v.resolved_at is not None
                and v.resolved_at < end
            ):
                out.append(
                    FundMove(
                        v.resolved_at,
                        F.WRITTEN_OFF,
                        v.amount,
                        "cash_variance",
                        v.id,
                        v.status.value,
                        None,
                        v.resolution_note,
                        v.resolved_by,
                    )
                )
            elif (
                v.source_type is VarianceSource.PETTY_CASH_RETURN
                and v.status is not VarianceStatus.RESOLVED
                and v.opened_at < end
            ):
                out.append(
                    FundMove(
                        v.opened_at,
                        F.OPEN_RETURN_DIFFERENCES,
                        v.amount,
                        "cash_variance",
                        v.id,
                        v.status.value,
                        None,
                        None,
                        v.opened_by,
                    )
                )
        for adv in self._s.execute(select(PettyCashAdvance).where(PettyCashAdvance.fund_id == fund.id)).scalars():
            if adv.issued_at >= end:
                continue
            base = ("petty_cash_advance", adv.id, adv.status.value, adv.number, adv.purpose)
            out.append(FundMove(adv.issued_at, F.ADVANCES_ISSUED, adv.amount, *base, adv.issued_by))
            if adv.status is AdvanceStatus.OUTSTANDING:
                out.append(FundMove(adv.issued_at, F.ADVANCES_OUTSTANDING, adv.amount, *base, adv.issued_by))
            elif adv.cleared_at is not None and adv.cleared_at < end and adv.change_returned:
                out.append(
                    FundMove(adv.cleared_at, F.ADVANCE_CHANGE_RETURNED, adv.change_returned, *base, adv.cleared_by)
                )
        return out

    @staticmethod
    def _expense(e: Expense, figure: FundFigure) -> FundMove:
        return FundMove(
            e.incurred_at, figure, e.amount, "expense", e.id, e.status.value, None, e.description, e.submitted_by
        )

    def figures(self, fund: PettyCashFund, end: datetime | None = None) -> Figures:
        totals: dict[FundFigure, Decimal] = defaultdict(Decimal)
        for m in self.moves(fund, end):
            totals[m.figure] += m.amount
        return Figures(dict(totals))

    def balance(self, fund: PettyCashFund) -> PettyCashBalanceDto:
        fig = self.figures(fund)
        last_count = self.last_count_at(fund.id)
        every = PolicyService(self._s).petty_cash(fund.tenant_id, at=self._now).policy.count_every_days
        due = None
        if every is not None and fund.is_active:
            due = (last_count or fund.created_at) + timedelta(days=every)
        balance = fig.balance
        return PettyCashBalanceDto(
            fund_id=fund.id,
            fund_code=fund.code,
            fund_name=fund.name,
            currency=fund.currency,
            holder_staff_id=fund.holder_staff_id,
            is_active=fund.is_active,
            approved_limit=fund.approved_limit,
            low_balance_level=fund.low_balance_level,
            balance=balance,
            available_to_spend=fig.available,
            below_low_balance=fund.low_balance_level is not None and balance < fund.low_balance_level,
            funded=fig[F.FUNDED],
            spent=fig[F.SPENT],
            returned=fig[F.RETURNED],
            adjustments=fig[F.ADJUSTMENTS],
            written_off=fig[F.WRITTEN_OFF],
            advances_issued=fig[F.ADVANCES_ISSUED],
            advance_change_returned=fig[F.ADVANCE_CHANGE_RETURNED],
            pending_spending=fig[F.PENDING_SPENDING],
            awaiting_acknowledgement=fig[F.AWAITING_ACKNOWLEDGEMENT],
            returns_claimed=fig[F.RETURNS_CLAIMED],
            open_return_differences=fig[F.OPEN_RETURN_DIFFERENCES],
            pending_adjustments=fig[F.PENDING_ADJUSTMENTS],
            advances_outstanding=fig[F.ADVANCES_OUTSTANDING],
            advance_spending=fig[F.ADVANCE_SPENDING],
            last_count_at=last_count,
            next_count_due_at=due,
            as_of=self._now,
        )

    def last_count_at(self, fund_id: uuid.UUID) -> datetime | None:
        return self._s.execute(
            select(func.max(PettyCashCount.counted_at)).where(PettyCashCount.fund_id == fund_id)
        ).scalar_one_or_none()

    # --- drill-down and statement -----------------------------------------------------------------------------
    def _window(self, fund: PettyCashFund, first: date, last: date) -> tuple[str, datetime, datetime]:
        tz = tenant_settings(self._s, fund.tenant_id).timezone
        start, end = local_bounds(tz, first, last)
        return tz, start, end

    def transactions(
        self, fund: PettyCashFund, first: date, last: date, figures: Iterable[FundFigure] | None = None
    ) -> list[PettyCashTransactionDto]:
        _, start, end = self._window(fund, first, last)
        wanted = set(figures or F)
        rows = [m for m in self.moves(fund, end) if m.at >= start and m.figure in wanted]
        rows.sort(key=lambda m: (m.at, m.entity_id), reverse=True)
        return [
            PettyCashTransactionDto(
                figure=m.figure,
                occurred_at=m.at,
                amount=m.amount,
                currency=fund.currency,
                entity_type=m.entity_type,
                entity_id=m.entity_id,
                status=m.status,
                reference=m.reference,
                note=m.note,
                recorded_by=m.recorded_by,
            )
            for m in rows
        ]

    def statement(self, fund: PettyCashFund, first: date, last: date) -> PettyCashStatementDto:
        """Every movement of the balance over [first, last] (tenant-local days) with the running balance."""
        tz, start, end = self._window(fund, first, last)
        moves = sorted((m for m in self.moves(fund, end) if m.figure in SIGN), key=lambda m: (m.at, m.entity_id))
        opening = sum((SIGN[m.figure] * m.amount for m in moves if m.at < start), ZERO)
        running, lines = opening, []
        for m in moves:
            if m.at < start:
                continue
            delta = SIGN[m.figure] * m.amount
            running += delta
            lines.append(
                PettyCashStatementLineDto(
                    occurred_at=m.at,
                    figure=m.figure,
                    entity_type=m.entity_type,
                    entity_id=m.entity_id,
                    reference=m.reference,
                    note=m.note,
                    money_in=delta if delta > 0 else ZERO,
                    money_out=-delta if delta < 0 else ZERO,
                    running_balance=running,
                )
            )
        return PettyCashStatementDto(
            fund_id=fund.id,
            currency=fund.currency,
            timezone=tz,
            date_from=first,
            date_to=last,
            opening_balance=opening,
            closing_balance=running,
            lines=lines,
        )

    # --- imprest top-up ----------------------------------------------------------------------------------------
    def last_issued_at(self, fund_id: uuid.UUID) -> datetime | None:
        return self._s.execute(
            select(func.max(PettyCashMovement.issued_at)).where(
                PettyCashMovement.fund_id == fund_id,
                PettyCashMovement.kind.in_(INBOUND),
                PettyCashMovement.status.in_(
                    (MovementStatus.ISSUED, MovementStatus.ACKNOWLEDGED, MovementStatus.DISPUTED)
                ),
            )
        ).scalar_one_or_none()

    def in_flight(self, fund_id: uuid.UUID, exclude: uuid.UUID | None = None) -> Decimal:
        stmt = select(func.coalesce(func.sum(PettyCashMovement.amount), 0)).where(
            PettyCashMovement.fund_id == fund_id,
            PettyCashMovement.kind.in_(INBOUND),
            PettyCashMovement.status.in_(IN_FLIGHT),
        )
        if exclude is not None:
            stmt = stmt.where(PettyCashMovement.id != exclude)
        return Decimal(self._s.execute(stmt).scalar_one())

    def spending_since(self, fund_id: uuid.UUID, since: datetime | None, until: datetime) -> list[Expense]:
        """Approved fund expenses decided in (since, until], plus those of advances (the fund paid them as advances)."""
        stmt = select(Expense).where(
            Expense.petty_cash_fund_id == fund_id,
            Expense.status == ExpenseStatus.APPROVED,
            Expense.decided_at <= until,
        )
        if since is not None:
            stmt = stmt.where(Expense.decided_at > since)
        return list(self._s.execute(stmt.order_by(Expense.decided_at, Expense.id)).scalars())

    def top_up_suggestion(self, fund: PettyCashFund) -> TopUpSuggestionDto:
        balance = self.figures(fund).balance
        flight = self.in_flight(fund.id)
        cap = max(ZERO, fund.approved_limit - balance - flight)
        since = self.last_issued_at(fund.id)
        expenses = self.spending_since(fund.id, since, self._now)
        spent = sum((e.amount for e in expenses), ZERO)
        return TopUpSuggestionDto(
            fund_id=fund.id,
            currency=fund.currency,
            balance=balance,
            approved_limit=fund.approved_limit,
            in_flight=flight,
            cap=cap,
            since=since,
            spending_since=spent,
            suggested=min(spent, cap),
            expenses=[
                TopUpExpenseDto(
                    id=e.id,
                    description=e.description,
                    amount=e.amount,
                    incurred_at=e.incurred_at,
                    decided_at=e.decided_at,
                    category_id=e.category_id,
                    machine_id=e.machine_id,
                    job_id=e.job_id,
                )
                for e in expenses
            ],
        )

    # --- advances ---------------------------------------------------------------------------------------------
    def advance_spending(self, advance_id: uuid.UUID) -> tuple[Decimal, Decimal]:
        """(approved, pending) expenses linked to the advance."""
        rows = self._s.execute(
            select(Expense.status, func.sum(Expense.amount))
            .where(Expense.petty_cash_advance_id == advance_id, Expense.status != ExpenseStatus.REJECTED)
            .group_by(Expense.status)
        ).all()
        totals = {status: Decimal(amount) for status, amount in rows}
        return totals.get(ExpenseStatus.APPROVED, ZERO), totals.get(ExpenseStatus.PENDING_APPROVAL, ZERO)

    def held_by_currency(self, funds: Iterable[PettyCashFund]) -> dict[str, Decimal]:
        out: dict[str, Decimal] = defaultdict(Decimal)
        for fund in funds:
            out[fund.currency] += self.figures(fund).balance
        return dict(out)


__all__ = ["SIGN", "FundLedger", "FundMove", "MovementKind"]
