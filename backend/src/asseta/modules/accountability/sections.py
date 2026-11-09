"""Builds the section 8 dashboard groups (see sections_dto). A fixed number of grouped queries per call: nothing here
runs one query per customer, machine, person or purchase."""

import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from asseta.modules.accountability.dto import ApprovalsTileDto
from asseta.modules.accountability.flows import PendingCount, adjustment_keys, pending_union
from asseta.modules.accountability.links import CASH, list_route, record_route
from asseta.modules.accountability.models import SecurityEvent, SecurityEventKind
from asseta.modules.accountability.sections_dto import (
    AttemptsFigureDto,
    CashSectionDto,
    ChangeoverJobDto,
    ChangeoverJobsDto,
    CountFigureDto,
    CustomerHoursSectionDto,
    CustomerRemainingDto,
    DiscrepanciesFigureDto,
    EmployeeCashDto,
    ExcavatorHoursDto,
    ExcavatorOperationsSectionDto,
    ExceptionsSectionDto,
    HoursFigureDto,
    KindCountDto,
    MoneyFigureDto,
    MoneyLineDto,
    OutstandingApprovalsDto,
    OverdueReportsDto,
    PendingAdjustmentsDto,
    PendingItemDto,
    PurchaseQueueDto,
    PurchaseQueueItemDto,
    TypeCountDto,
    UnresolvedVariancesDto,
    VarianceSourceDto,
)
from asseta.modules.finance.common import local_bounds, local_date, period_conditions, tenant_settings
from asseta.modules.finance.custody_models import (
    CashTransfer,
    CashTransferStatus,
    CashVariance,
    RemittanceOverdue,
    VarianceStatus,
    VarianceUnit,
)
from asseta.modules.finance.custody_totals import CustodianBalance
from asseta.modules.finance.models import CashHandover, CustomerPayment, HirePaymentMethod, SettlementStatus
from asseta.modules.hours.ledger import PurchaseQueue, purchase_queue_select
from asseta.modules.hours.models import SIGN, HoursLedgerEntry, HoursPurchase, LedgerEntryType
from asseta.modules.meter.allocation_models import (
    AllocationKind,
    AllocationStatus,
    DailyOperationalReport,
    DailyReportStatus,
    WorkAllocation,
)
from asseta.modules.meter.engine_hours import missing_daily_reports
from asseta.modules.meter.models import ExceptionStatus, ExceptionType, JobException
from asseta.modules.oversight.unbilled import changeovers_awaiting_approval
from asseta.modules.policy.capabilities import ENGINE_HOURS, REVENUE_RECONCILIATION
from asseta.modules.revenue.models import RevenueDifference, RevenueDifferenceStatus

ZERO = Decimal(0)
TOP = 200  # most customers listed; the total says how many there are
OLDEST = 20  # records shown under a queue; its route lists them all
OPEN_VARIANCE = (VarianceStatus.OPEN, VarianceStatus.WRITE_OFF_PROPOSED, VarianceStatus.CLOSURE_PROPOSED)
UNRESOLVED_REVENUE = (RevenueDifferenceStatus.OPEN, RevenueDifferenceStatus.EXPLANATION_PROPOSED)
# Reading problems: what the meter says does not add up (evidence-quality flags are reviewed under exceptions).
METER_DISCREPANCIES = (
    ExceptionType.METER_DECREASE,
    ExceptionType.IMPOSSIBLE_INCREMENT,
    ExceptionType.CONTINUITY_GAP,
    ExceptionType.TELEMETRY_MISMATCH,
    ExceptionType.OVERLAPPING_ALLOCATION,
)
KIND_ROUTES: dict[str, str] = {
    "adjustment_requests": list_route("/tenant/finance/adjustments/requests", status="PROPOSED"),
    "hours_transfers": list_route("/tenant/hours/transfers", status="PENDING"),
    "hours_cancellations": list_route("/tenant/hours/cancellations", status="PENDING"),
    "credit_arrangements": list_route("/tenant/hours/credit", status="PROPOSED"),
    "discounts": list_route("/tenant/hours/discounts", status="PROPOSED"),
    "meter_corrections": list_route("/tenant/meter-corrections", status="PROPOSED"),
    "allocation_corrections": "/tenant/work-allocations/corrections",
    "classifications": list_route("/tenant/engine-hours/classifications", status="PROPOSED"),
    "non_revenue_approvals": list_route("/tenant/non-revenue-approvals", status="PROPOSED"),
    "custody_adjustments": list_route(f"{CASH}/adjustments", status="PENDING"),
    "write_offs": list_route(f"{CASH}/variances", status="WRITE_OFF_PROPOSED"),
    "variance_closures": list_route(f"{CASH}/variances", status="CLOSURE_PROPOSED"),
    "meter_baselines": list_route("/tenant/meter-baselines", status="PROPOSED"),
    "meter_resets": list_route("/tenant/meter-resets", status="PENDING"),
    "cash_retentions": list_route(f"{CASH}/retentions", status="PENDING"),
    "partial_reasons": list_route(f"{CASH}/remittances", partial_reason_pending="true"),
    "approval_requests": list_route("/tenant/approvals", status="PENDING"),
    "payments_to_verify": list_route("/tenant/customer-payments", status="CLAIMED"),
    "remittances_to_verify": list_route(f"{CASH}/remittances", status="CLAIMED"),
    "jobs_awaiting_approval": list_route("/tenant/jobs", status="PENDING_APPROVAL"),
    "daily_reports_to_review": list_route("/tenant/daily-reports", status="SUBMITTED"),
    "case_closures": list_route("/tenant/cases", closure_proposed="true"),
    "revenue_decisions": list_route("/tenant/revenue-differences", status="EXPLANATION_PROPOSED"),
}


def approvals_tile(counts: dict[str, PendingCount]) -> ApprovalsTileDto:
    """Every kind of outstanding approval, one number each (the total is their sum)."""
    values = {name: counts[name].count if name in counts else 0 for name in KIND_ROUTES}
    return ApprovalsTileDto(**values, total=sum(values.values()))


def _kinds(counts: dict[str, PendingCount], only: frozenset[str] | None = None) -> list[KindCountDto]:
    return sorted(
        (
            KindCountDto(kind=k, count=c.count, oldest_at=c.oldest_at, route=KIND_ROUTES[k])
            for k, c in counts.items()
            if only is None or k in only
        ),
        key=lambda r: (-r.count, r.kind),
    )


def pending_item(row: Any) -> PendingItemDto:
    return PendingItemDto(
        kind=row.key,
        record_type=row.record_type,
        id=row.id,
        reference=row.reference,
        status=row.status,
        requested_by=row.requested_by,
        requested_at=row.requested_at,
        amount=row.amount,
        unit=row.unit,
        currency=row.currency,
        customer_id=row.customer_id,
        machine_id=row.machine_id,
        staff_member_id=row.staff_member_id,
        route=record_route(row.record_type, row.id),
    )


class ManagementSections:
    def __init__(
        self,
        s: Session,
        tenant_id: uuid.UUID,
        now: datetime,
        date_from: date | None,
        date_to: date | None,
        disabled: frozenset[str],
    ):
        if date_from is not None and date_to is not None:
            local_bounds(
                tenant_settings(s, tenant_id).timezone, date_from, date_to
            )  # refuses a bad or over-long period
        self._s, self._tid, self._now, self._from, self._to, self._disabled = (
            s,
            tenant_id,
            now,
            date_from,
            date_to,
            disabled,
        )
        self._period = {"date_from": date_from, "date_to": date_to}
        self._allocations: dict[uuid.UUID, dict[AllocationKind, list[Any]]] | None = None

    def _in_period(self, column: Any) -> list[ColumnElement[bool]]:
        return period_conditions(self._s, self._tid, column, self._from, self._to)

    def _money(self, currency: Any, amount: Any, conds: list[Any], route: str) -> MoneyFigureDto:
        rows = self._s.execute(
            select(currency, func.count(), func.coalesce(func.sum(amount), 0))
            .where(*conds)
            .group_by(currency)
            .order_by(currency)
        ).all()
        return MoneyFigureDto(
            lines=[MoneyLineDto(currency=c, count=int(n), amount=a) for c, n, a in rows],
            count=sum(int(n) for _, n, _ in rows),
            route=route,
        )

    def _count(self, stmt: Any) -> int:
        return int(self._s.execute(stmt).scalar_one())

    # --- customer hours -------------------------------------------------------------------------------------------
    def _ledger_figure(self, entry_type: LedgerEntryType) -> HoursFigureDto:
        e = HoursLedgerEntry
        count, hours = self._s.execute(
            select(func.count(), func.coalesce(func.sum(e.hours), 0)).where(
                e.entry_type == entry_type, *self._in_period(e.occurred_at)
            )
        ).one()
        route = list_route("/tenant/hours/ledger", entry_type=entry_type.value, **self._period)
        return HoursFigureDto(hours=hours, count=int(count), route=route)

    def _queue(self, rows: list[Any], queue: PurchaseQueue) -> PurchaseQueueDto:
        amounts: dict[str, list[Any]] = defaultdict(lambda: [0, ZERO])
        hours = ZERO
        for p, awaiting, verified, _ in rows:
            hours += awaiting
            amounts[p.currency][0] += 1
            amounts[p.currency][1] += max(ZERO, p.amount - verified)
        items = [
            PurchaseQueueItemDto(
                purchase_id=p.id,
                purchase_number=p.purchase_number,
                customer_id=p.customer_id,
                hours_awaiting=awaiting,
                amount_open=max(ZERO, p.amount - verified),
                currency=p.currency,
                created_at=p.created_at,
                route=record_route("hours_purchase", p.id) or "",
            )
            for p, awaiting, verified, _ in rows[:OLDEST]
        ]
        return PurchaseQueueDto(
            count=len(rows),
            hours=hours,
            amounts=[MoneyLineDto(currency=c, count=n, amount=a) for c, (n, a) in sorted(amounts.items())],
            route=list_route("/tenant/hours/purchases", queue=queue.value),
            items=items,
        )

    def customer_hours(self) -> CustomerHoursSectionDto:
        p, e = HoursPurchase, HoursLedgerEntry
        bought = [p.cancelled_at.is_(None), *self._in_period(p.created_at)]
        purchases_route = list_route("/tenant/hours/purchases", cancelled="false", **self._period)
        count, hours = self._s.execute(select(func.count(), func.coalesce(func.sum(p.hours), 0)).where(*bought)).one()
        by_customer: dict[uuid.UUID, dict[str, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
        entries: dict[uuid.UUID, int] = defaultdict(int)
        for customer, entry_type, total, n in self._s.execute(
            select(e.customer_id, e.entry_type, func.sum(e.hours), func.count()).group_by(e.customer_id, e.entry_type)
        ):
            row = by_customer[customer]
            row["remaining"] += SIGN[entry_type] * Decimal(total)
            entries[customer] += int(n)
            if entry_type is LedgerEntryType.ACTIVATED:
                row["activated"] += Decimal(total)
            elif entry_type is LedgerEntryType.CONSUMED:
                row["consumed"] += Decimal(total)
        ranked = sorted(by_customer.items(), key=lambda kv: (-kv[1]["remaining"], str(kv[0])))
        queue = list(self._s.execute(purchase_queue_select().order_by(p.created_at, p.id)).all())
        return CustomerHoursSectionDto(
            purchased=HoursFigureDto(hours=hours, count=int(count), route=purchases_route),
            purchased_value=self._money(p.currency, p.amount, bought, purchases_route),
            activated=self._ledger_figure(LedgerEntryType.ACTIVATED),
            consumed=self._ledger_figure(LedgerEntryType.CONSUMED),
            remaining=HoursFigureDto(
                hours=sum((r["remaining"] for r in by_customer.values()), ZERO),
                count=len(by_customer),
                route="/tenant/hours/balances",
            ),
            remaining_by_customer=[
                CustomerRemainingDto(
                    customer_id=customer,
                    remaining=r["remaining"],
                    activated=r["activated"],
                    consumed=r["consumed"],
                    route=list_route("/tenant/hours/balances", customer_id=customer),
                )
                for customer, r in ranked[:TOP]
            ],
            remaining_customers_total=len(ranked),
            unpaid_purchases=self._queue([r for r in queue if r[3] <= 0], PurchaseQueue.UNPAID),
            unconfirmed_purchases=self._queue([r for r in queue if r[3] > 0], PurchaseQueue.UNCONFIRMED),
            awaiting_activation=self._queue(queue, PurchaseQueue.AWAITING_ACTIVATION),
        )

    # --- excavator operations -------------------------------------------------------------------------------------
    def _allocation_rows(self) -> dict[uuid.UUID, dict[AllocationKind, list[Any]]]:
        """Active allocations per machine and kind over the period: (hours, entries). Read once per call."""
        if self._allocations is None:
            w = WorkAllocation
            conds: list[Any] = [w.status == AllocationStatus.ACTIVE]
            if self._from is not None:
                conds.append(w.work_date >= self._from)
            if self._to is not None:
                conds.append(w.work_date <= self._to)
            out: dict[uuid.UUID, dict[AllocationKind, list[Any]]] = defaultdict(dict)
            for machine, kind, hours, n in self._s.execute(
                select(w.machine_id, w.kind, func.sum(w.hours), func.count())
                .where(*conds)
                .group_by(w.machine_id, w.kind)
            ):
                out[machine][kind] = [Decimal(hours), int(n)]
            self._allocations = out
        return self._allocations

    def _allocation_figure(self, kind: AllocationKind | None) -> HoursFigureDto:
        pairs = [v for by in self._allocation_rows().values() for k, v in by.items() if kind is None or k is kind]
        route = list_route(
            "/tenant/work-allocations",
            kind=kind.value if kind else None,
            **{"from": self._from, "to": self._to},
        )
        return HoursFigureDto(
            hours=sum((p[0] for p in pairs), ZERO),
            count=sum(p[1] for p in pairs),
            route=route,
        )

    def operations(self) -> ExcavatorOperationsSectionDto:
        def hours(by: dict[AllocationKind, list[Any]], kind: AllocationKind) -> Decimal:
            return by[kind][0] if kind in by else ZERO

        rows = [
            ExcavatorHoursDto(
                machine_id=machine,
                operating_hours=sum((v[0] for v in by.values()), ZERO),
                customer_hours=hours(by, AllocationKind.CUSTOMER_WORK),
                authorized_hours=hours(by, AllocationKind.AUTHORIZED_ACTIVITY),
                unexplained_hours=hours(by, AllocationKind.UNEXPLAINED),
                route=list_route(
                    "/tenant/work-allocations", machine_id=machine, **{"from": self._from, "to": self._to}
                ),
            )
            for machine, by in self._allocation_rows().items()
        ]
        rows.sort(key=lambda r: (-r.operating_hours, str(r.machine_id)))
        x = JobException
        types = self._s.execute(
            select(x.exception_type, func.count())
            .where(x.status == ExceptionStatus.OPEN, x.exception_type.in_(METER_DISCREPANCIES))
            .group_by(x.exception_type)
            .order_by(x.exception_type)
        ).all()
        d = DailyOperationalReport
        reports = dict(
            self._s.execute(
                select(d.status, func.count())
                .where(d.status.in_((DailyReportStatus.SUBMITTED, DailyReportStatus.RETURNED)))
                .group_by(d.status)
            ).all()
        )
        return ExcavatorOperationsSectionDto(
            operating_hours=self._allocation_figure(None),
            customer_hours=self._allocation_figure(AllocationKind.CUSTOMER_WORK),
            authorized_non_customer_hours=self._allocation_figure(AllocationKind.AUTHORIZED_ACTIVITY),
            unexplained_hours=self._allocation_figure(AllocationKind.UNEXPLAINED),
            by_excavator=rows,
            meter_discrepancies=DiscrepanciesFigureDto(
                count=sum(int(n) for _, n in types),
                by_type=[
                    TypeCountDto(
                        type=t.value,
                        count=int(n),
                        route=list_route("/tenant/exceptions", status="OPEN", exception_type=t.value),
                    )
                    for t, n in types
                ],
                route=list_route("/tenant/exceptions", status="OPEN"),
            ),
            pending_reports=CountFigureDto(
                count=int(reports.get(DailyReportStatus.SUBMITTED, 0)),
                route=list_route("/tenant/daily-reports", status="SUBMITTED"),
            ),
            returned_reports=CountFigureDto(
                count=int(reports.get(DailyReportStatus.RETURNED, 0)),
                route=list_route("/tenant/daily-reports", status="RETURNED"),
            ),
        )

    # --- cash -----------------------------------------------------------------------------------------------------
    def cash(self, balances: list[CustodianBalance]) -> CashSectionDto:
        p, h, t = CustomerPayment, CashHandover, CashTransfer
        held = [
            b
            for b in balances
            if b.outstanding or b.in_transit_out or b.claimed_unverified_handovers or b.pending_floats
        ]
        held.sort(key=lambda b: (-b.outstanding, str(b.staff_member_id)))
        outstanding: dict[str, list[Any]] = defaultdict(lambda: [0, ZERO])
        for b in balances:
            if b.outstanding:
                outstanding[b.currency][0] += 1
                outstanding[b.currency][1] += b.outstanding
        remittances, transfers = f"{CASH}/remittances", f"{CASH}/transfers"
        confirmed = func.coalesce(h.amount_received, h.amount)
        return CashSectionDto(
            collected=self._money(
                p.currency,
                p.amount,
                [
                    p.method == HirePaymentMethod.CASH,
                    p.status != SettlementStatus.REJECTED,
                    p.reversed_at.is_(None),
                    *self._in_period(p.received_at),
                ],
                list_route("/tenant/customer-payments", method="CASH", **self._period),
            ),
            held_by_employee=[
                EmployeeCashDto(
                    staff_member_id=b.staff_member_id,
                    currency=b.currency,
                    outstanding=b.outstanding,
                    in_transit_out=b.in_transit_out,
                    claimed_unverified_handovers=b.claimed_unverified_handovers,
                    pending_floats=b.pending_floats,
                    approved_retention=b.approved_retention,
                    route=f"/tenant/staff/{b.staff_member_id}/accountability",
                )
                for b in held
            ],
            transferred=self._money(
                t.currency,
                t.amount_received,
                [t.status == CashTransferStatus.ACKNOWLEDGED, *self._in_period(t.transferred_at)],
                list_route(transfers, status="ACKNOWLEDGED", **self._period),
            ),
            in_transit=self._money(
                t.currency,
                t.amount_declared,
                [t.status == CashTransferStatus.PENDING_ACKNOWLEDGEMENT],
                list_route(transfers, status="PENDING_ACKNOWLEDGEMENT"),
            ),
            declared_for_remittance=self._money(
                h.currency,
                h.amount,
                [h.status != SettlementStatus.REJECTED, *self._in_period(h.handed_at)],
                list_route(remittances, **self._period),
            ),
            confirmed_by_company=self._money(
                h.currency,
                confirmed,
                [h.status == SettlementStatus.VERIFIED, *self._in_period(h.verified_at)],
                list_route(remittances, status="VERIFIED", **self._period),
            ),
            outstanding=MoneyFigureDto(
                lines=[MoneyLineDto(currency=c, count=n, amount=a) for c, (n, a) in sorted(outstanding.items())],
                count=sum(n for n, _ in outstanding.values()),
                route=f"{CASH}",
            ),
            unconfirmed_remittances=self._money(
                h.currency, h.amount, [h.status == SettlementStatus.CLAIMED], list_route(remittances, status="CLAIMED")
            ),
            disputed_remittances=self._money(
                h.currency,
                h.amount,
                [h.status == SettlementStatus.REJECTED, *self._in_period(h.handed_at)],
                list_route(remittances, status="REJECTED", **self._period),
            ),
            disputed_transfers=self._money(
                t.currency,
                t.amount_declared,
                [t.status == CashTransferStatus.DISPUTED, *self._in_period(t.transferred_at)],
                list_route(transfers, status="DISPUTED", **self._period),
            ),
        )

    # --- exceptions -----------------------------------------------------------------------------------------------
    def _variance_money(self, sign: int, direction: str, conds: list[Any], **filters: Any) -> MoneyFigureDto:
        v = CashVariance
        side = v.amount > 0 if sign > 0 else v.amount < 0
        return self._money(
            v.currency,
            func.abs(v.amount),
            [v.unit == VarianceUnit.MONEY, side, *conds],
            list_route(f"{CASH}/variances", direction=direction, **filters),
        )

    def _unresolved_variances(self) -> UnresolvedVariancesDto:
        v, rd = CashVariance, RevenueDifference
        rows: dict[tuple[str, str], list[Any]] = {}
        for source, unit, currency, n, amount in self._s.execute(
            select(v.source_type, v.unit, v.currency, func.count(), func.sum(func.abs(v.amount)))
            .where(v.status.in_(OPEN_VARIANCE))
            .group_by(v.source_type, v.unit, v.currency)
        ):
            row = rows.setdefault((source.value, unit.value), [0, []])
            row[0] += int(n)
            row[1].append(MoneyLineDto(currency=currency, count=int(n), amount=amount))
        out = [
            VarianceSourceDto(
                source=source,
                unit=unit,
                count=n,
                # Hour variances keep the tenant currency only as a column default: their figures are hours.
                amounts=lines if unit == VarianceUnit.MONEY.value else [],
                route=list_route(f"{CASH}/variances", source_type=source),
            )
            for (source, unit), (n, lines) in sorted(rows.items())
        ]
        if REVENUE_RECONCILIATION not in self._disabled:
            revenue = self._s.execute(
                select(rd.currency, func.count(), func.sum(func.abs(rd.difference)))
                .where(rd.status.in_(UNRESOLVED_REVENUE))
                .group_by(rd.currency)
                .order_by(rd.currency)
            ).all()
            if revenue:
                out.append(
                    VarianceSourceDto(
                        source="REVENUE_DIFFERENCE",
                        unit=VarianceUnit.MONEY.value,
                        count=sum(int(n) for _, n, _ in revenue),
                        amounts=[MoneyLineDto(currency=c, count=int(n), amount=a) for c, n, a in revenue],
                        route="/tenant/revenue-differences",
                    )
                )
        return UnresolvedVariancesDto(total=sum(r.count for r in out), by_source=out)

    def _overdue(self) -> OverdueReportsDto:
        missing = len(missing_daily_reports(self._s, self._tid, self._now)) if ENGINE_HOURS not in self._disabled else 0
        today = local_date(tenant_settings(self._s, self._tid).timezone, self._now)
        overdue = self._count(select(func.count()).where(RemittanceOverdue.local_day == today))
        return OverdueReportsDto(
            missing_daily_reports=CountFigureDto(count=missing, route="/tenant/daily-reports"),
            remittances_overdue_today=CountFigureDto(
                count=overdue, route=list_route(f"{CASH}/remittance-overdue", local_day=today)
            ),
            total=missing + overdue,
        )

    def _attempts(self, window_days: int) -> AttemptsFigureDto:
        since = self._now - timedelta(days=window_days)
        conds = self._in_period(SecurityEvent.occurred_at) or [SecurityEvent.occurred_at >= since]
        counts = dict(
            self._s.execute(select(SecurityEvent.kind, func.count()).where(*conds).group_by(SecurityEvent.kind)).all()
        )
        return AttemptsFigureDto(
            since=since,
            permission_denied=int(counts.get(SecurityEventKind.PERMISSION_DENIED, 0)),
            segregation_of_duties=int(counts.get(SecurityEventKind.SEGREGATION_OF_DUTIES, 0)),
            route="/tenant/security-events",
        )

    def _changeovers(self) -> ChangeoverJobsDto:
        rows = changeovers_awaiting_approval(self._s, self._now) if ENGINE_HOURS not in self._disabled else []
        return ChangeoverJobsDto(
            count=len(rows),
            oldest_days=max((r["days_waiting"] for r in rows), default=None),
            items=[
                ChangeoverJobDto(
                    job_id=r["job_id"],
                    job_number=r["job_number"],
                    machine_id=r["machine_id"],
                    customer_id=r["customer_id"],
                    changed_over_at=r["changed_over_at"],
                    days_waiting=r["days_waiting"],
                    route=record_route("job", r["job_id"]) or "",
                )
                for r in rows[:OLDEST]
            ],
        )

    def exceptions(self, counts: dict[str, PendingCount], window_days: int) -> ExceptionsSectionDto:
        v, p = CashVariance, CustomerPayment
        adjustments = adjustment_keys()
        sub = pending_union(self._disabled, adjustments_only=True)
        oldest = self._s.execute(select(sub).order_by(sub.c.requested_at, sub.c.id).limit(OLDEST)).all()
        open_now = [v.status.in_(OPEN_VARIANCE)]
        opened = self._in_period(v.opened_at)
        pending_total = sum(c.count for k, c in counts.items() if k in adjustments)
        return ExceptionsSectionDto(
            unexplained_engine_hours=self._allocation_figure(AllocationKind.UNEXPLAINED),
            shortages=self._variance_money(1, "SHORTAGE", open_now),
            overages=self._variance_money(-1, "OVERAGE", open_now),
            shortages_opened_in_period=self._variance_money(1, "SHORTAGE", opened, **self._period),
            overages_opened_in_period=self._variance_money(-1, "OVERAGE", opened, **self._period),
            pending_adjustments=PendingAdjustmentsDto(
                total=pending_total,
                by_kind=_kinds(counts, adjustments),
                oldest=[pending_item(r) for r in oldest],
                route="/tenant/accountability/pending-adjustments",
            ),
            unauthorized_attempts=self._attempts(window_days),
            unconfirmed_payments=self._money(
                p.currency,
                p.amount,
                [p.status == SettlementStatus.CLAIMED],
                list_route("/tenant/customer-payments", status="CLAIMED"),
            ),
            outstanding_approvals=OutstandingApprovalsDto(
                total=sum(c.count for c in counts.values()), by_kind=_kinds(counts)
            ),
            overdue_reports=self._overdue(),
            unresolved_variances=self._unresolved_variances(),
            changeover_jobs_awaiting_approval=self._changeovers(),
        )
