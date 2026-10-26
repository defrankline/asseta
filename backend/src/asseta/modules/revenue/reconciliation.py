"""Hours-to-money reconciliation sweep (DEC-031 R3). After each reconciliation period closes in the tenant's time zone
(DAY, WEEK, or each completed JOB — tenant policy), every machine's expected revenue (engine-hour ledger x locked job
terms) is compared with the money attributed to that work (issued invoice lines, prepaid consumption). A shortfall
beyond the tenant's tolerance becomes one revenue difference per machine, period and currency — idempotent (unique
key); above the case threshold it opens or joins an investigation case (for review, never a verdict), and
REVENUE_DIFFERENCE notifies holders of `tenant.revenue.decide`.

Closed periods ending within `recheck_days` are re-examined on every run: an OPEN difference whose money arrived
later is CLEARED (system), and the figures of a difference still awaiting a decision are refreshed. Explained,
confirmed and cleared differences are final."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import exists, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from asseta.core.audit import AuditActor, AuditService
from asseta.core.db import DbScope, apply_scope
from asseta.core.money import quantize
from asseta.core.outbox import OutboxWriter
from asseta.modules.fleet.models import Machine
from asseta.modules.intelligence.linking import CaseItem, CaseLinker
from asseta.modules.intelligence.models import CaseSourceType, SignalSeverity, SubjectType
from asseta.modules.jobs.models import JobStatus
from asseta.modules.meter.ledger import ZERO, SegmentKind
from asseta.modules.meter.models import MeterCapture
from asseta.modules.policy.revenue import ReconciliationPeriod, RevenueReconciliationPolicy
from asseta.modules.policy.service import EffectivePolicy, PolicyService
from asseta.modules.revenue.compute import overlap_fraction
from asseta.modules.revenue.models import RevenueDifference, RevenueDifferenceAdjustment, RevenueDifferenceStatus
from asseta.modules.revenue.sheet import MachineModel, load_machine_model, tenant_zone
from asseta.modules.tenancy.models import Tenant, TenantStatus

log = structlog.get_logger()
SWEEP = AuditActor(None, [], "scheduler")
TOPIC = "asseta.revenue"
TITLE = "Revenue difference to explain"
REFRESHABLE = (RevenueDifferenceStatus.OPEN, RevenueDifferenceStatus.EXPLANATION_PROPOSED)


@dataclass(frozen=True)
class Period:
    kind: ReconciliationPeriod
    key: str
    start: datetime
    end: datetime
    local_from: date
    local_to: date
    job_id: uuid.UUID | None = None


@dataclass
class SweepSummary:
    tenants: int = 0
    opened: int = 0
    refreshed: int = 0
    cleared: int = 0
    adjusted: int = 0
    failures: int = 0


def closed_periods(policy: RevenueReconciliationPolicy, tz: ZoneInfo, now: datetime) -> list[Period]:
    """DAY / WEEK periods that have closed (end <= now) and end within the policy's re-check window."""
    since = now - timedelta(days=policy.recheck_days)
    local = now.astimezone(tz).date()
    out: list[Period] = []
    if policy.period is ReconciliationPeriod.DAY:
        day = local - timedelta(days=1)
        while True:
            start, end = datetime.combine(day, time(), tz), datetime.combine(day + timedelta(days=1), time(), tz)
            if end < since:
                break
            out.append(Period(policy.period, f"DAY:{day.isoformat()}", start, end, day, day))
            day -= timedelta(days=1)
    elif policy.period is ReconciliationPeriod.WEEK:
        monday = local - timedelta(days=local.weekday()) - timedelta(days=7)
        while True:
            start = datetime.combine(monday, time(), tz)
            end = datetime.combine(monday + timedelta(days=7), time(), tz)
            if end < since:
                break
            out.append(Period(policy.period, f"WEEK:{monday.isoformat()}", start, end, monday, monday + timedelta(6)))
            monday -= timedelta(days=7)
    return out


def _job_periods(model: MachineModel, tz: ZoneInfo, since: datetime) -> list[Period]:
    out = []
    for meta in model.jobs.values():
        job = meta.job
        if job.status is not JobStatus.COMPLETED or job.completed_at is None or job.completed_at < since:
            continue
        start = job.started_at or job.completed_at
        out.append(
            Period(
                ReconciliationPeriod.JOB,
                f"JOB:{job.id}",
                start,
                job.completed_at,
                start.astimezone(tz).date(),
                job.completed_at.astimezone(tz).date(),
                job.id,
            )
        )
    return out


def _hours(model: MachineModel, p: Period) -> tuple[Decimal, Decimal]:
    customer = non_revenue = ZERO
    for i in model.ledger.ledger.intervals:
        if i.kind is not SegmentKind.CUSTOMER_WORK or (p.job_id is not None and i.job_id != p.job_id):
            continue
        f = Decimal(1) if p.job_id is not None else overlap_fraction(i.start.at, i.end.at, p.start, p.end)
        customer += i.customer_work_hours * f
        non_revenue += i.non_revenue_hours * f
    return customer.quantize(Decimal("0.01")), non_revenue.quantize(Decimal("0.01"))


def _detail(model: MachineModel, p: Period, job_ids: list[uuid.UUID]) -> dict[str, Any]:
    w0, w1 = (None, None) if p.job_id is not None else (p.start, p.end)
    jobs = []
    for jid in job_ids:
        per = model.revenue.window(w0, w1, {jid})
        for currency, w in per.items():
            jobs.append(
                {
                    "job_id": str(jid),
                    "job_number": model.jobs[jid].job.job_number if jid in model.jobs else None,
                    "currency": currency,
                    "expected": str(w.expected.quantize(Decimal("0.0001"))),
                    "in_progress": str(w.in_progress.quantize(Decimal("0.0001"))),
                    "attributed": str(w.attributed.quantize(Decimal("0.0001"))),
                    "completed": jid in model.jobs and model.jobs[jid].job.status is JobStatus.COMPLETED,
                }
            )
    sources = [
        {
            "source": m.source,
            "ref_id": str(m.ref_id),
            "parent_id": str(m.parent_id),
            "job_id": str(m.job_id),
            "currency": m.currency,
            "amount": str(m.amount),
            "hours": str(m.hours) if m.hours is not None else None,
        }
        for m in model.revenue.money
        if m.job_id in job_ids
    ]
    return {"jobs": jobs, "money_sources": sources}


def _zero_values(now: datetime) -> dict[str, Any]:
    return {
        "expected_amount": ZERO,
        "in_progress_amount": ZERO,
        "attributed_amount": ZERO,
        "difference": ZERO,
        "customer_work_hours": ZERO,
        "non_revenue_hours": ZERO,
        "unexplained_hours": ZERO,
        "unexplained_expected_amount": ZERO,
        "computed_at": now,
    }


def period_values(model: MachineModel, p: Period, now: datetime) -> dict[str, dict[str, Any]]:
    """Per currency: the figures of one machine-period (JOB periods: that job only, no unexplained hours)."""
    w0, w1 = (None, None) if p.job_id is not None else (p.start, p.end)
    windows = model.revenue.window(w0, w1, {p.job_id} if p.job_id else None, include_unexplained=p.job_id is None)
    customer, non_revenue = _hours(model, p)
    out: dict[str, dict[str, Any]] = {}
    for currency, w in sorted(windows.items()):
        mu = model.minor_units.get(currency, 2)
        expected, progress, attributed = (quantize(v, mu) for v in (w.expected, w.in_progress, w.attributed))
        detail = _detail(model, p, w.job_ids)
        detail["unexplained"] = {
            "hours": str(w.unexplained_hours.quantize(Decimal("0.01"))),
            "expected": str(quantize(w.unexplained_expected, mu)),
        }
        out[currency] = {
            "expected_amount": expected,
            "in_progress_amount": progress,
            "attributed_amount": attributed,
            "difference": expected - progress - attributed,
            "customer_work_hours": customer,
            "non_revenue_hours": non_revenue,
            "unexplained_hours": w.unexplained_hours.quantize(Decimal("0.01")),
            "unexplained_expected_amount": quantize(w.unexplained_expected, mu),
            "detail": detail,
            "computed_at": now,
        }
    return out


class RevenueSweep:
    def __init__(self, s: Session, tenant_id: uuid.UUID, now: datetime):
        self._s, self._tid, self._now = s, tenant_id, now
        self.summary = SweepSummary()

    def run(self) -> SweepSummary:
        eff = PolicyService(self._s).revenue_reconciliation(self._tid, at=self._now)
        policy = eff.policy
        if not policy.enabled:
            return self.summary  # capability off: no reconciliation (today's behaviour)
        tz = tenant_zone(self._s, self._tid)
        periods = closed_periods(policy, tz, self._now)
        since = self._now - timedelta(days=policy.recheck_days)
        machines = self._s.execute(
            select(Machine).where(exists().where(MeterCapture.machine_id == Machine.id)).order_by(Machine.asset_code)
        ).scalars()
        for machine in machines:
            model = load_machine_model(self._s, self._tid, machine, self._now)
            todo = _job_periods(model, tz, since) if policy.period is ReconciliationPeriod.JOB else periods
            for p in todo:
                self._period(model, p, eff)
        return self.summary

    def _period(self, model: MachineModel, p: Period, eff: EffectivePolicy[RevenueReconciliationPolicy]) -> None:
        policy = eff.policy
        for currency, values in period_values(model, p, self._now).items():
            exceeds = policy.exceeds_tolerance(
                values["expected_amount"] - values["in_progress_amount"], values["difference"]
            )
            existing = self._s.execute(
                select(RevenueDifference).where(
                    RevenueDifference.machine_id == model.machine.id,
                    RevenueDifference.period_key == p.key,
                    RevenueDifference.currency == currency,
                )
            ).scalar_one_or_none()
            if existing is None:
                if exceeds:
                    self._open(model, p, currency, values, eff)
                continue
            if existing.status not in REFRESHABLE:
                continue  # decided: final (later classification approvals record adjustments instead)
            self._refresh(existing, values, exceeds)

    def _refresh(self, existing: RevenueDifference, values: dict[str, Any], exceeds: bool) -> None:
        for k, v in values.items():
            setattr(existing, k, v)
        if existing.status is RevenueDifferenceStatus.OPEN and not exceeds:
            existing.status = RevenueDifferenceStatus.CLEARED
            existing.decided_at = self._now
            existing.decision_note = "Money attributed on a later check is within the tolerance"
            self.summary.cleared += 1
            self._audit("revenue.difference.cleared", existing, {"difference": str(existing.difference)})
        else:
            self.summary.refreshed += 1
        self._s.flush()

    def recompute(
        self,
        machine_id: uuid.UUID,
        start: datetime,
        end: datetime,
        cause_type: str,
        cause_id: uuid.UUID,
        actor: uuid.UUID | None,
    ) -> None:
        """Re-evaluate this machine's recorded differences whose period overlaps [start, end] after a change to the
        hours behind them (an approved classification or non-revenue approval). Open ones are refreshed (and cleared
        when back within tolerance); decided ones (EXPLAINED / CONFIRMED) keep their figures and get an adjustment
        entry for the change — history is never rewritten."""
        policy = PolicyService(self._s).revenue_reconciliation(self._tid, at=self._now).policy
        if not policy.enabled:
            return
        rows = list(
            self._s.execute(
                select(RevenueDifference).where(
                    RevenueDifference.machine_id == machine_id,
                    RevenueDifference.status != RevenueDifferenceStatus.CLEARED,
                    RevenueDifference.period_start < end,
                    RevenueDifference.period_end > start,
                )
            ).scalars()
        )
        if not rows:
            return
        machine = self._s.get(Machine, machine_id)
        assert machine is not None
        model = load_machine_model(self._s, self._tid, machine, self._now)
        for row in rows:
            p = Period(
                ReconciliationPeriod(row.period_kind),
                row.period_key,
                row.period_start,
                row.period_end,
                row.local_from,
                row.local_to,
                row.job_id,
            )
            values = period_values(model, p, self._now).get(row.currency)
            if values is None:
                values = {**_zero_values(self._now), "detail": row.detail}
            if row.status in REFRESHABLE:
                exceeds = policy.exceeds_tolerance(
                    values["expected_amount"] - values["in_progress_amount"], values["difference"]
                )
                self._refresh(row, values, exceeds)
                continue
            previous = row.difference + sum(
                self._s.execute(
                    select(RevenueDifferenceAdjustment.amount).where(
                        RevenueDifferenceAdjustment.difference_id == row.id
                    )
                ).scalars(),
                ZERO,
            )
            delta = values["difference"] - previous
            if delta == 0:
                continue
            self._s.add(
                RevenueDifferenceAdjustment(
                    id=uuid.uuid4(),
                    tenant_id=self._tid,
                    difference_id=row.id,
                    previous_difference=previous,
                    new_difference=values["difference"],
                    amount=delta,
                    cause_type=cause_type,
                    cause_id=cause_id,
                    detail={
                        k: str(values[k])
                        for k in ("expected_amount", "attributed_amount", "unexplained_hours", "non_revenue_hours")
                    },
                    created_by=actor,
                    created_at=self._now,
                )
            )
            self._s.flush()
            self.summary.adjusted += 1
            self._audit(
                "revenue.difference.adjusted",
                row,
                {"previous": str(previous), "new": str(values["difference"]), "cause": f"{cause_type}:{cause_id}"},
            )

    def _open(
        self,
        model: MachineModel,
        p: Period,
        currency: str,
        values: dict[str, Any],
        eff: EffectivePolicy[RevenueReconciliationPolicy],
    ) -> None:
        row_id = uuid.uuid4()
        inserted = self._s.execute(
            insert(RevenueDifference)
            .values(
                id=row_id,
                tenant_id=self._tid,
                machine_id=model.machine.id,
                period_kind=p.kind.value,
                period_key=p.key,
                period_start=p.start,
                period_end=p.end,
                local_from=p.local_from,
                local_to=p.local_to,
                job_id=p.job_id,
                currency=currency,
                status=RevenueDifferenceStatus.OPEN,
                policy_version=eff.version_stamp[:80],
                opened_at=self._now,
                **values,
            )
            .on_conflict_do_nothing(constraint="uq_revenue_difference_period")
            .returning(RevenueDifference.id)
        ).scalar_one_or_none()
        if inserted is None:
            return  # a concurrent sweep opened it
        row = self._s.get(RevenueDifference, row_id)
        assert row is not None
        threshold = eff.policy.case_threshold_amount
        if threshold is not None and abs(row.difference) > threshold:
            fraud = PolicyService(self._s).fraud_controls(self._tid, at=self._now)
            case = CaseLinker(self._s, self._tid, self._now, fraud.policy.case_grouping_window_hours).link(
                CaseItem(
                    CaseSourceType.REVENUE_DIFFERENCE,
                    row.id,
                    "REVENUE_DIFFERENCE",
                    TITLE,
                    SignalSeverity.WARNING,
                    self._now,
                    {
                        "period": p.key,
                        "currency": currency,
                        "expected_amount": str(row.expected_amount),
                        "attributed_amount": str(row.attributed_amount),
                        "difference": str(row.difference),
                        "case_threshold": str(threshold),
                    },
                    SubjectType.MACHINE,
                    model.machine.id,
                    eff.version_stamp,
                    machine_id=model.machine.id,
                    job_id=p.job_id,
                )
            )
            row.case_id = case.id if case else None
            self._s.flush()
        self.summary.opened += 1
        self._audit(
            "revenue.difference.opened",
            row,
            {
                "period": p.key,
                "currency": currency,
                "expected_amount": str(row.expected_amount),
                "attributed_amount": str(row.attributed_amount),
                "difference": str(row.difference),
                "case_id": str(row.case_id) if row.case_id else None,
            },
        )
        OutboxWriter(self._s).emit(
            topic=TOPIC,
            event_type="RevenueDifferenceOpened",
            key=str(model.machine.id),
            payload={
                "difference_id": str(row.id),
                "machine_id": str(model.machine.id),
                "period_key": p.key,
                "local_from": p.local_from.isoformat(),
                "local_to": p.local_to.isoformat(),
                "currency": currency,
                "expected_amount": str(row.expected_amount),
                "attributed_amount": str(row.attributed_amount),
                "difference": str(row.difference),
            },
            tenant_id=self._tid,
        )

    def _audit(self, action: str, row: RevenueDifference, after: dict[str, Any]) -> None:
        AuditService(self._s).record(
            actor=SWEEP,
            action=action,
            entity_type="revenue_difference",
            entity_id=row.id,
            tenant_id=self._tid,
            after={"machine_id": str(row.machine_id), **after},
            policy_version=row.policy_version[:64],
        )


def sweep_tenant(s: Session, tenant_id: uuid.UUID, now: datetime) -> SweepSummary:
    """Reconcile one tenant's closed periods (inside its RLS scope)."""
    return RevenueSweep(s, tenant_id, now).run()


def run_revenue_reconciliation(session_factory: Callable[[], Session], now: datetime) -> SweepSummary:
    """One sweep over every non-closed tenant; one tenant's failure never blocks the others."""
    total = SweepSummary()
    with session_factory() as s, s.begin():
        apply_scope(s, DbScope.SYSTEM, None, None)
        tenants = list(s.execute(select(Tenant.id).where(Tenant.status != TenantStatus.CLOSED)).scalars())
    for tid in tenants:
        total.tenants += 1
        try:
            with session_factory() as s, s.begin():
                apply_scope(s, DbScope.TENANT, tid, None)
                one = sweep_tenant(s, tid, now)
                total.opened += one.opened
                total.refreshed += one.refreshed
                total.cleared += one.cleared
        except Exception:
            log.exception("revenue_reconciliation_tenant_failed", tenant_id=str(tid))
            total.failures += 1
    log.info("revenue_reconciliation_completed", **total.__dict__)
    return total


def recompute_after_change(
    s: Session,
    tenant_id: uuid.UUID,
    machine_id: uuid.UUID,
    start: datetime,
    end: datetime,
    cause_type: str,
    cause_id: uuid.UUID,
    actor: uuid.UUID | None,
    now: datetime,
) -> None:
    """Hook for approvals that change which hours are revenue (owner rule, 2026-10-26)."""
    RevenueSweep(s, tenant_id, now).recompute(machine_id, start, end, cause_type, cause_id, actor)
