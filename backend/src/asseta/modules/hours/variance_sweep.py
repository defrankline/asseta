"""Customer-hour variances (DEC-032, guideline T8): a scheduled comparison of purchases, ledger consumption and work
allocations. A mismatch opens one `cash_variance` of type CUSTOMER_HOUR (figures in hours): neutral, a difference to
explain, assigned and closed like a cash variance. Re-detection never duplicates: while one is open nothing new is
opened; one that was closed is only reopened when the figures differ from what was closed."""

import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

import structlog
from sqlalchemy import Text, cast, func, select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditActor, AuditService
from asseta.core.db import DbScope, apply_scope
from asseta.core.outbox import OutboxWriter
from asseta.modules.finance.common import tenant_settings
from asseta.modules.finance.custody_models import (
    CashVariance,
    VarianceEventAction,
    VarianceSource,
    VarianceStatus,
    VarianceUnit,
)
from asseta.modules.finance.custody_rules import variance_event
from asseta.modules.hours.ledger import ZERO, purchase_totals
from asseta.modules.hours.models import HoursLedgerEntry, HoursPurchase, LedgerEntryType
from asseta.modules.machine_reports.models import (
    MachineReport,
    MachineReportLine,
    MachineReportStatus,
    ReportLineKind,
)
from asseta.modules.meter.allocation_models import AllocationKind, AllocationSource, AllocationStatus, WorkAllocation
from asseta.modules.policy.capabilities import CUSTOMER_HOURS, ENGINE_HOURS, capability_on
from asseta.modules.policy.service import PolicyService
from asseta.modules.tenancy.models import Tenant, TenantStatus

TOPIC = "asseta.finance"
SWEEP = AuditActor(None, [], "scheduler")
NAMESPACE = uuid.UUID("5c2f9f0a-7b77-4f60-9f2e-41e0c9d7b801")
log = structlog.get_logger()

PURCHASE_OVER_ACTIVATED = "PURCHASE_OVER_ACTIVATED"
NEGATIVE_REMAINING = "NEGATIVE_REMAINING"
CONSUMPTION_MISMATCH = "CONSUMPTION_MISMATCH"
ALLOCATION_MISMATCH = "ALLOCATION_MISMATCH"


@dataclass(frozen=True)
class Mismatch:
    check_code: str
    subject_id: uuid.UUID
    expected: Decimal
    actual: Decimal
    customer_id: uuid.UUID | None
    machine_id: uuid.UUID | None
    purchase_id: uuid.UUID | None = None


class HourVarianceSweep:
    def __init__(self, session: Session, tenant_id: uuid.UUID, now: datetime):
        self._s, self._tid, self._now = session, tenant_id, now
        self._audit = AuditService(session)

    def run(self) -> int:
        if not capability_on(self._s, self._tid, CUSTOMER_HOURS, self._now):
            return 0
        eff = PolicyService(self._s).customer_hours(self._tid, at=self._now)
        if not eff.policy.variance_sweep_enabled:
            return 0
        self._stamp = eff.version_stamp
        self._tolerance = eff.policy.variance_tolerance_hours
        self._currency = tenant_settings(self._s, self._tid).currency
        opened = 0
        for m in self._mismatches():
            if self._open(m):
                opened += 1
        return opened

    def _over(self, expected: Decimal, actual: Decimal) -> bool:
        return abs(expected - actual) > self._tolerance

    def _mismatches(self) -> Iterator[Mismatch]:
        yield from self._purchase_checks()
        yield from self._report_checks()

    def _purchase_checks(self) -> Iterator[Mismatch]:
        for p in self._s.execute(select(HoursPurchase).where(HoursPurchase.cancelled_at.is_(None))).scalars():
            totals = purchase_totals(self._s, p)
            if totals.net_activated > p.hours + self._tolerance:
                yield Mismatch(
                    PURCHASE_OVER_ACTIVATED, p.id, p.hours, totals.net_activated, p.customer_id, p.machine_id, p.id
                )
            for machine_id, m in totals.machines.items():
                if m.remaining < -self._tolerance:
                    yield Mismatch(
                        NEGATIVE_REMAINING,
                        uuid.uuid5(p.id, str(machine_id)),
                        ZERO,
                        m.remaining,
                        p.customer_id,
                        machine_id,
                        p.id,
                    )

    def _report_checks(self) -> Iterator[Mismatch]:
        """Per approved machine report: the customers' hours it gives = the hours consumed from their orders = the lot
        hours its allocation-ledger entries carry."""
        consumed_of = dict(
            self._s.execute(
                select(HoursLedgerEntry.machine_report_id, func.coalesce(func.sum(HoursLedgerEntry.hours), 0))
                .where(
                    HoursLedgerEntry.entry_type == LedgerEntryType.CONSUMED,
                    HoursLedgerEntry.machine_report_id.is_not(None),
                )
                .group_by(HoursLedgerEntry.machine_report_id)
            )
            .tuples()
            .all()
        )
        lots_of = self._lots_by_report() if capability_on(self._s, self._tid, ENGINE_HOURS, self._now) else {}
        rows = self._s.execute(
            # Postgres has no min(uuid): the first customer (by text) names the variance.
            select(
                MachineReport, func.sum(MachineReportLine.hours), func.min(cast(MachineReportLine.customer_id, Text))
            )
            .join(MachineReportLine, MachineReportLine.report_id == MachineReport.id)
            .where(
                MachineReport.status == MachineReportStatus.APPROVED,
                MachineReportLine.kind == ReportLineKind.CUSTOMER,
            )
            .group_by(MachineReport.id)
        ).all()
        for report, given, first_customer in rows:
            customer_id = uuid.UUID(first_customer) if first_customer else None
            consumed = Decimal(consumed_of.get(report.id, 0))
            if self._over(Decimal(given), consumed):
                yield Mismatch(
                    CONSUMPTION_MISMATCH, report.id, Decimal(given), consumed, customer_id, report.machine_id
                )
            if report.id in lots_of and self._over(consumed, lots_of[report.id]):
                yield Mismatch(
                    ALLOCATION_MISMATCH, report.id, consumed, lots_of[report.id], customer_id, report.machine_id
                )

    def _lots_by_report(self) -> dict[uuid.UUID, Decimal]:
        """Customer hours Ledger 3 says were drawn, per approved machine report (active customer-work entries)."""
        out: dict[uuid.UUID, Decimal] = {}
        for refs, lots in self._s.execute(
            select(WorkAllocation.approval_ref_ids, WorkAllocation.lots).where(
                WorkAllocation.status == AllocationStatus.ACTIVE,
                WorkAllocation.kind == AllocationKind.CUSTOMER_WORK,
                WorkAllocation.source == AllocationSource.MACHINE_REPORT,
            )
        ).all():
            if lots and refs:
                out[refs[0]] = out.get(refs[0], ZERO) + sum((Decimal(str(x["hours"])) for x in lots), ZERO)
        return out

    def _open(self, m: Mismatch) -> bool:
        rows = list(
            self._s.execute(
                select(CashVariance).where(
                    CashVariance.source_type == VarianceSource.CUSTOMER_HOUR,
                    CashVariance.check_code == m.check_code,
                    CashVariance.source_id.in_(self._source_ids(m)),
                )
            ).scalars()
        )
        if any(r.status is not VarianceStatus.RESOLVED for r in rows):
            return False  # one at a time; the open one shows the first difference
        if any(r.declared_amount == m.expected and r.received_amount == m.actual for r in rows):
            return False  # the same figures were already explained and closed
        row = CashVariance(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            source_type=VarianceSource.CUSTOMER_HOUR,
            source_id=self._source_id(m, len(rows)),
            unit=VarianceUnit.HOURS,
            currency=self._currency,
            declared_amount=m.expected,
            received_amount=m.actual,
            amount=m.expected - m.actual,
            policy_version=self._stamp,
            opened_at=self._now,
            opened_by=None,
            status=VarianceStatus.OPEN,
            check_code=m.check_code,
            customer_id=m.customer_id,
            machine_id=m.machine_id,
            purchase_id=m.purchase_id,
            evidence_attachment_ids=[],
        )
        self._s.add(row)
        self._s.flush()
        variance_event(self._s, row, VarianceEventAction.OPENED, None, self._now, None, {"check_code": m.check_code})
        self._audit.record(
            actor=SWEEP,
            action="hours.variance.opened",
            entity_type="cash_variance",
            entity_id=row.id,
            tenant_id=self._tid,
            after={"check_code": m.check_code, "expected": str(m.expected), "actual": str(m.actual)},
            policy_version=self._stamp[:64],
        )
        OutboxWriter(self._s).emit(
            topic=TOPIC,
            event_type="CustomerHourVarianceOpened",
            key=str(m.customer_id or self._tid),
            payload={
                "variance_id": str(row.id),
                "check_code": m.check_code,
                "expected": str(m.expected),
                "actual": str(m.actual),
                "customer_id": str(m.customer_id) if m.customer_id else None,
            },
            tenant_id=self._tid,
        )
        return True

    def _source_id(self, m: Mismatch, occurrence: int) -> uuid.UUID:
        return uuid.uuid5(NAMESPACE, f"{self._tid}:{m.check_code}:{m.subject_id}:{occurrence}")

    def _source_ids(self, m: Mismatch) -> list[uuid.UUID]:
        return [self._source_id(m, n) for n in range(200)]  # occurrences are bounded (reopens only on new figures)


def sweep_tenant(session: Session, tenant_id: uuid.UUID, now: datetime) -> int:
    return HourVarianceSweep(session, tenant_id, now).run()


def run_hour_variances(session_factory: Callable[[], Session], now: datetime) -> int:
    """One pass over every non-closed tenant; one tenant's failure never blocks the others."""
    opened = 0
    with session_factory() as s, s.begin():
        apply_scope(s, DbScope.SYSTEM, None, None)
        tenants = list(s.execute(select(Tenant.id).where(Tenant.status != TenantStatus.CLOSED)).scalars())
    for tid in tenants:
        try:
            with session_factory() as s, s.begin():
                apply_scope(s, DbScope.TENANT, tid, None)
                opened += sweep_tenant(s, tid, now)
        except Exception:
            log.exception("hour_variance_tenant_failed", tenant_id=str(tid))
    log.info("hour_variances_completed", tenants=len(tenants), opened=opened)
    return opened
