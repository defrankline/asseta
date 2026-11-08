"""Writes and maintains the work allocation ledger (DEC-032 A1) day by day: on every reading and sweep, on job start and
completion, and when an explanation is approved. Idempotent: a machine's active entries are compared with what its
readings now give, and only differences are written (the old entry superseded, never edited). An approved correction
stands until the ledger piece it replaced changes under it. Runs in the tenant's RLS scope."""

import uuid
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from asseta.core.audit import AuditActor, AuditService
from asseta.core.db import DbScope, apply_scope
from asseta.modules.fleet.models import Machine
from asseta.modules.hours.models import SIGN, HoursLedgerEntry, LedgerEntryType
from asseta.modules.jobs.models import Job
from asseta.modules.meter.allocation_models import (
    AllocationKind,
    AllocationSource,
    AllocationStatus,
    WorkAllocation,
)
from asseta.modules.meter.allocation_plan import Plan, PlannedEntry, plan_allocations
from asseta.modules.meter.engine_hours import MachineLedger, approved_resets, engine_hours_on, load_machine_ledger
from asseta.modules.meter.models import MeterCapture
from asseta.modules.policy.schemas import BillingMode
from asseta.modules.tenancy.models import Tenant, TenantSettings, TenantStatus

log = structlog.get_logger()
SWEEP = AuditActor(None, [], "scheduler")
T = LedgerEntryType


@dataclass
class AllocationSummary:
    tenants: int = 0
    machines: int = 0
    written: int = 0
    superseded: int = 0
    failures: int = 0


def tenant_zone(s: Session, tenant_id: uuid.UUID) -> ZoneInfo:
    ts = s.get(TenantSettings, tenant_id)
    return ZoneInfo(ts.timezone if ts else "UTC")


def _row_signature(r: WorkAllocation) -> tuple[Any, ...]:
    lots = sorted((str(x["purchase_id"]), str(x["hours"])) for x in r.lots)
    return (
        r.work_date,
        r.start_ref,
        r.end_ref,
        r.start_reading,
        r.end_reading,
        r.meter_epoch,
        r.hours,
        r.kind,
        r.customer_id,
        r.job_id,
        r.activity_type,
        r.reason_id,
        r.classification_id,
        r.changeover_id,
        r.reading_review,
        tuple(lots),
    )


def _plan_signature(e: PlannedEntry) -> tuple[Any, ...]:
    lots = sorted((str(x["purchase_id"]), str(x["hours"])) for x in e.lots)
    return (
        e.work_date,
        e.start_ref,
        e.end_ref,
        e.start_reading,
        e.end_reading,
        e.meter_epoch,
        e.hours,
        e.kind,
        e.customer_id,
        e.job_id,
        e.activity_type,
        e.reason_id,
        e.classification_id,
        e.changeover_id,
        e.reading_review,
        tuple(lots),
    )


def job_lots(s: Session, job_id: uuid.UUID) -> list[tuple[uuid.UUID, Decimal]]:
    """Per lot, the hours this job took from it: final consumption, else the net provisional draw while it runs."""
    rows = list(
        s.execute(
            select(HoursLedgerEntry)
            .where(
                HoursLedgerEntry.job_id == job_id,
                HoursLedgerEntry.entry_type.in_([T.CONSUMED, T.PROVISIONAL, T.PROVISIONAL_REVERSED]),
            )
            .order_by(HoursLedgerEntry.occurred_at, HoursLedgerEntry.id)
        ).scalars()
    )
    consumed = [r for r in rows if r.entry_type is T.CONSUMED]
    held: dict[uuid.UUID, Decimal] = defaultdict(lambda: Decimal(0))
    for r in consumed or rows:
        held[r.purchase_id] += r.hours if r.entry_type is T.CONSUMED else -SIGN[r.entry_type] * r.hours
    return [(p, h) for p, h in held.items() if h > 0]


def assign_lots(s: Session, entries: list[PlannedEntry], job_customer: dict[uuid.UUID, uuid.UUID]) -> None:
    """Spread each prepaid job's lot hours over its customer-work entries in meter order. Lots follow billable hours,
    so an entry can carry fewer lot hours than engine hours (non-billable time, minimum-hours billing)."""
    work: dict[uuid.UUID, list[PlannedEntry]] = defaultdict(list)
    for e in entries:
        if (
            e.kind is AllocationKind.CUSTOMER_WORK
            and e.job_id is not None
            and e.customer_id == job_customer.get(e.job_id)
        ):
            work[e.job_id].append(e)
    if not work:
        return
    prepaid = set(
        s.execute(
            select(Job.id).where(Job.id.in_(work.keys()), Job.billing_mode == BillingMode.PREPAID_HOURS)
        ).scalars()
    )
    for job_id in prepaid:
        lots = job_lots(s, job_id)
        at = 0
        for entry in work[job_id]:
            left = entry.hours
            while left > 0 and at < len(lots):
                purchase, available = lots[at]
                take = min(left, available)
                entry.lots.append({"purchase_id": str(purchase), "hours": str(take)})
                left -= take
                lots[at] = (purchase, available - take)
                if lots[at][1] <= 0:
                    at += 1


class AllocationWriter:
    def __init__(self, s: Session, tenant_id: uuid.UUID, now: datetime, source: AllocationSource):
        self._s, self._tid, self._now, self._source = s, tenant_id, now, source
        self._tz = tenant_zone(s, tenant_id)

    def build_plan(self, ml: MachineLedger) -> Plan:
        resets = approved_resets(self._s, ml.machine.id)
        plan = plan_allocations(ml.ledger.intervals, resets, self._tz)
        customers = {i.job_id: i.job_customer_id for i in ml.ledger.intervals if i.job_id and i.job_customer_id}
        assign_lots(self._s, plan.entries, customers)
        return plan

    def sync_machine(self, machine_id: uuid.UUID) -> tuple[int, int]:
        """Bring one machine's active entries into line with its ledger; returns (written, superseded)."""
        s = self._s
        machine = s.execute(
            select(Machine).where(Machine.id == machine_id).with_for_update(key_share=True)
        ).scalar_one_or_none()
        if machine is None or not engine_hours_on(s, self._tid, self._now):
            return 0, 0
        ml = load_machine_ledger(s, self._tid, machine, self._now)
        plan = self.build_plan(ml)
        active = list(
            s.execute(
                select(WorkAllocation)
                .where(WorkAllocation.machine_id == machine_id, WorkAllocation.status == AllocationStatus.ACTIVE)
                .order_by(WorkAllocation.work_date, WorkAllocation.start_reading)
            ).scalars()
        )
        by_key: dict[str, list[WorkAllocation]] = defaultdict(list)
        for row in active:
            by_key[row.origin_key].append(row)
        wanted = {e.key: e for e in plan.entries}
        to_write: list[tuple[PlannedEntry, WorkAllocation | None]] = []
        stale: list[WorkAllocation] = []
        for key, rows in by_key.items():
            entry = wanted.get(key)
            corrected = any(r.source is AllocationSource.CORRECTION for r in rows)
            if entry is None:
                stale.extend(rows)
            elif corrected and all(r.origin_hours == entry.hours for r in rows):
                wanted.pop(key)  # the approved correction still describes these hours
            elif not corrected and len(rows) == 1 and _row_signature(rows[0]) == _plan_signature(entry):
                wanted.pop(key)
            else:
                stale.extend(rows)
                to_write.append((entry, rows[0]))
                wanted.pop(key)
        to_write.extend((e, None) for e in wanted.values())
        if not stale and not to_write:
            return 0, 0
        for row in stale:
            row.status, row.superseded_at = AllocationStatus.SUPERSEDED, self._now
        s.flush()  # the old ranges leave the exclusion constraint before the new ones enter it
        version = ml.policy.version_stamp[:80]
        recorders = self._recorders(plan)
        for entry, previous in to_write:
            self._insert(machine_id, entry, previous, version, recorders)
        s.flush()
        return len(to_write), len(stale)

    def _insert(
        self,
        machine_id: uuid.UUID,
        e: PlannedEntry,
        previous: WorkAllocation | None,
        version: str,
        recorders: dict[uuid.UUID, tuple[uuid.UUID | None, list[uuid.UUID]]],
    ) -> None:
        by_end = recorders.get(e.end_ref, (None, []))
        by_start = recorders.get(e.start_ref, (None, []))
        row = WorkAllocation(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            machine_id=machine_id,
            work_date=e.work_date,
            start_ref=e.start_ref,
            start_reading=e.start_reading,
            start_at=e.start_at,
            end_ref=e.end_ref,
            end_reading=e.end_reading,
            end_at=e.end_at,
            meter_epoch=e.meter_epoch,
            hours=e.hours,
            kind=e.kind,
            customer_id=e.customer_id,
            job_id=e.job_id,
            activity_type=e.activity_type,
            reason_id=e.reason_id,
            classification_id=e.classification_id,
            changeover_id=e.changeover_id,
            reading_review=e.reading_review,
            lots=e.lots,
            evidence_attachment_ids=sorted({*by_start[1], *by_end[1]}),
            source=self._source,
            status=AllocationStatus.ACTIVE,
            origin_key=e.key,
            origin_hours=e.hours,
            supersedes_id=previous.id if previous is not None else None,
            recorded_by=by_end[0] or by_start[0],
            policy_version=version,
            created_at=self._now,
        )
        self._s.add(row)
        self._s.flush()
        if self._source is not AllocationSource.BACKFILL:
            AuditService(self._s).record(
                actor=SWEEP,
                action="meter.work_allocation.posted",
                entity_type="work_allocation",
                entity_id=row.id,
                tenant_id=self._tid,
                after={
                    "machine_id": str(row.machine_id),
                    "work_date": row.work_date.isoformat(),
                    "kind": row.kind.value,
                    "hours": str(row.hours),
                    "supersedes_id": str(row.supersedes_id) if row.supersedes_id else None,
                },
            )

    def _recorders(self, plan: Plan) -> dict[uuid.UUID, tuple[uuid.UUID | None, list[uuid.UUID]]]:
        """Who took each boundary reading and its photo, the evidence an entry inherits."""
        refs = {e.start_ref for e in plan.entries} | {e.end_ref for e in plan.entries}
        if not refs:
            return {}
        rows = self._s.execute(
            select(MeterCapture.id, MeterCapture.supervisor_user_id, MeterCapture.photo_attachment_id).where(
                MeterCapture.id.in_(refs)
            )
        ).all()
        return {cid: (user, [photo] if photo else []) for cid, user, photo in rows}


def sync_allocations(s: Session, tenant_id: uuid.UUID, machine_id: uuid.UUID, now: datetime) -> None:
    """On-event hook (capture/sync, job start/complete, approved explanation). It must never fail the action that
    triggered it: a refusal by the exclusion constraint is logged and the next sweep retries."""
    try:
        with s.begin_nested():
            AllocationWriter(s, tenant_id, now, AllocationSource.DERIVED).sync_machine(machine_id)
    except IntegrityError:
        log.exception("work_allocation_sync_refused", machine_id=str(machine_id))


def sweep_tenant(
    s: Session, tenant_id: uuid.UUID, now: datetime, summary: AllocationSummary, source: AllocationSource
) -> None:
    if not engine_hours_on(s, tenant_id, now):
        return
    machines = list(s.execute(select(MeterCapture.machine_id).distinct()).scalars())
    writer = AllocationWriter(s, tenant_id, now, source)
    for machine_id in machines:
        summary.machines += 1
        written, superseded = writer.sync_machine(machine_id)
        summary.written += written
        summary.superseded += superseded


def run_work_allocations(session_factory: Callable[[], Session], now: datetime) -> AllocationSummary:
    """One pass over every non-closed tenant; one tenant's failure never blocks the others."""
    summary = AllocationSummary()
    with session_factory() as s, s.begin():
        apply_scope(s, DbScope.SYSTEM, None, None)
        tenants = list(s.execute(select(Tenant.id).where(Tenant.status != TenantStatus.CLOSED)).scalars())
    for tid in tenants:
        summary.tenants += 1
        try:
            with session_factory() as s, s.begin():
                apply_scope(s, DbScope.TENANT, tid, None)
                sweep_tenant(s, tid, now, summary, AllocationSource.DERIVED)
        except Exception:
            log.exception("work_allocation_tenant_failed", tenant_id=str(tid))
            summary.failures += 1
    log.info("work_allocations_completed", **summary.__dict__)
    return summary
