"""Daily operational reports (DEC-032 A4): one per machine and tenant-local day, a real append-only record. Hours come
from the two readings it names; billable and unbillable hours (by the tenant's reason list) are declared and any gap
is shown as a difference. A repeat for the same machine-day is kept and flagged (never overwritten); reviewing is by
permission and never by the person who submitted it. The online endpoint and offline op DAILY_REPORT share this path."""

import uuid
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound
from asseta.core.outbox import OutboxWriter
from asseta.core.search import ilike_any
from asseta.core.signals import sod_violation
from asseta.modules.fleet.models import Machine
from asseta.modules.identity.principal import RequestContext
from asseta.modules.jobs.scope import METER_OVERSIGHT, assigned_machine_ids, own_staff, restricted_to_own
from asseta.modules.meter.allocation_dto import (
    DailyReportDto,
    DailyReportIn,
    DailyReportPrefillDto,
    DailyReportReviewIn,
    ReportAllocationDto,
    UnbillableLineDto,
)
from asseta.modules.meter.allocation_models import (
    AllocationKind,
    AllocationStatus,
    DailyOperationalReport,
    DailyReportStatus,
    WorkAllocation,
)
from asseta.modules.meter.allocation_writer import tenant_zone
from asseta.modules.meter.engine_hours import LIVE, TOPIC, EngineHoursMonitor, approved_resets
from asseta.modules.meter.engine_models import EngineHourReason, EngineHourReasonKind
from asseta.modules.meter.ledger import LedgerPoint, elapsed_hours
from asseta.modules.meter.models import CaptureAttachment, MeterCapture
from asseta.modules.policy.service import PolicyService

ZERO = Decimal(0)
ACTIVE = (DailyReportStatus.SUBMITTED, DailyReportStatus.REVIEWED)


def _point(c: MeterCapture) -> LedgerPoint:
    return LedgerPoint(c.id, c.kind.value, c.captured_at, c.reading, c.received_at, True, c.job_id)


class DailyReportService:
    def __init__(self, session: Session, ctx: RequestContext, now: datetime):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid, self._now = session, ctx, ctx.tenant_id, now
        self._tz: ZoneInfo = tenant_zone(session, ctx.tenant_id)

    def _visible(self) -> set[uuid.UUID] | None:
        if not restricted_to_own(self._ctx, METER_OVERSIGHT):
            return None
        staff = own_staff(self._s, self._ctx)
        return set() if staff is None else set(self._s.execute(assigned_machine_ids(staff.id)).scalars())

    def _machine(self, machine_id: uuid.UUID) -> Machine:
        row = self._s.get(Machine, machine_id)
        visible = self._visible()
        if row is None or (visible is not None and machine_id not in visible):
            raise NotFound("Machine not found", code="MACHINE_NOT_FOUND")
        return row

    # --- reads -------------------------------------------------------------------------------------------------
    def query(
        self,
        q: str | None,
        machine_id: uuid.UUID | None,
        day_from: date | None,
        day_to: date | None,
        status: DailyReportStatus | None,
    ) -> Select[DailyOperationalReport]:
        stmt = (
            select(DailyOperationalReport)
            .join(Machine, Machine.id == DailyOperationalReport.machine_id)
            .order_by(DailyOperationalReport.report_date.desc(), Machine.asset_code, DailyOperationalReport.id)
        )
        if machine_id is not None:
            stmt = stmt.where(DailyOperationalReport.machine_id == machine_id)
        if status is not None:
            stmt = stmt.where(DailyOperationalReport.status == status)
        if day_from is not None:
            stmt = stmt.where(DailyOperationalReport.report_date >= day_from)
        if day_to is not None:
            stmt = stmt.where(DailyOperationalReport.report_date <= day_to)
        if (match := ilike_any(q, Machine.asset_code, Machine.name)) is not None:
            stmt = stmt.where(match)
        visible = self._visible()
        if visible is not None:
            stmt = stmt.where(DailyOperationalReport.machine_id.in_(visible))
        return stmt

    def row(self, report_id: uuid.UUID, lock: bool = False) -> DailyOperationalReport:
        stmt = select(DailyOperationalReport).where(DailyOperationalReport.id == report_id)
        row = self._s.execute(stmt.with_for_update() if lock else stmt).scalar_one_or_none()
        visible = self._visible()
        if row is None or (visible is not None and row.machine_id not in visible):
            raise NotFound("Daily report not found", code="DAILY_REPORT_NOT_FOUND")
        return row

    def dtos(self, rows: list[DailyOperationalReport]) -> list[DailyReportDto]:
        reasons = {uuid.UUID(str(u["reason_id"])) for r in rows for u in r.unbillable}
        names = (
            dict(
                self._s.execute(
                    select(EngineHourReason.id, EngineHourReason.name).where(EngineHourReason.id.in_(reasons))
                ).all()
            )
            if reasons
            else {}
        )
        return [
            DailyReportDto.model_validate(r).model_copy(
                update={
                    "unbillable": [
                        UnbillableLineDto(
                            reason_id=u["reason_id"],
                            reason_name=names.get(uuid.UUID(str(u["reason_id"]))),
                            hours=u["hours"],
                        )
                        for u in r.unbillable
                    ],
                    "is_duplicate": r.duplicate_of_id is not None,
                }
            )
            for r in rows
        ]

    def _day_allocations(self, machine_id: uuid.UUID, day: date) -> list[WorkAllocation]:
        return list(
            self._s.execute(
                select(WorkAllocation)
                .where(
                    WorkAllocation.machine_id == machine_id,
                    WorkAllocation.work_date == day,
                    WorkAllocation.status == AllocationStatus.ACTIVE,
                )
                .order_by(WorkAllocation.start_reading)
            ).scalars()
        )

    @staticmethod
    def _allocation_view(rows: list[WorkAllocation]) -> list[ReportAllocationDto]:
        return [
            ReportAllocationDto(
                allocation_id=r.id,
                kind=r.kind,
                customer_id=r.customer_id,
                job_id=r.job_id,
                activity_type=r.activity_type,
                start_reading=r.start_reading,
                end_reading=r.end_reading,
                hours=r.hours,
            )
            for r in rows
        ]

    def _day_window(self, day: date) -> tuple[datetime, datetime]:
        start = datetime.combine(day, time(), self._tz)
        return start, start + timedelta(days=1)

    def prefill(self, machine_id: uuid.UUID, day: date) -> DailyReportPrefillDto:
        machine = self._machine(machine_id)
        start, end = self._day_window(day)
        captures = list(
            self._s.execute(
                select(MeterCapture)
                .where(
                    MeterCapture.machine_id == machine_id,
                    MeterCapture.state.in_(LIVE),
                    MeterCapture.captured_at >= start,
                    MeterCapture.captured_at < end,
                )
                .order_by(MeterCapture.captured_at, MeterCapture.reading)
            ).scalars()
        )
        opening = captures[0] if len(captures) > 1 else self._reading_before(machine_id, start)
        closing = captures[-1] if captures else None
        rows = self._day_allocations(machine_id, day)
        hours = {k: sum((r.hours for r in rows if r.kind is k), ZERO) for k in AllocationKind}
        total = self._total(machine_id, opening, closing) if opening and closing else None
        existing = list(
            self._s.execute(
                select(DailyOperationalReport.id).where(
                    DailyOperationalReport.machine_id == machine_id,
                    DailyOperationalReport.report_date == day,
                    DailyOperationalReport.status.in_(ACTIVE),
                )
            ).scalars()
        )
        return DailyReportPrefillDto(
            machine_id=machine.id,
            machine_code=machine.asset_code,
            machine_name=machine.name,
            report_date=day,
            opening_ref=opening.id if opening else None,
            opening_reading=opening.reading if opening else None,
            opening_at=opening.captured_at if opening else None,
            closing_ref=closing.id if closing else None,
            closing_reading=closing.reading if closing else None,
            closing_at=closing.captured_at if closing else None,
            total_hours=total,
            customer_hours=hours[AllocationKind.CUSTOMER_WORK],
            authorized_hours=hours[AllocationKind.AUTHORIZED_ACTIVITY],
            unexplained_hours=hours[AllocationKind.UNEXPLAINED],
            allocations=self._allocation_view(rows),
            existing_report_ids=existing,
        )

    def _reading_before(self, machine_id: uuid.UUID, at: datetime) -> MeterCapture | None:
        return self._s.execute(
            select(MeterCapture)
            .where(MeterCapture.machine_id == machine_id, MeterCapture.state.in_(LIVE), MeterCapture.captured_at < at)
            .order_by(MeterCapture.captured_at.desc())
            .limit(1)
        ).scalar_one_or_none()

    def _total(self, machine_id: uuid.UUID, opening: MeterCapture, closing: MeterCapture) -> Decimal | None:
        hours, _ = elapsed_hours(_point(opening), _point(closing), approved_resets(self._s, machine_id))
        return hours if hours >= ZERO else None

    # --- submit ------------------------------------------------------------------------------------------------
    def _capture(self, capture_id: uuid.UUID, machine_id: uuid.UUID) -> MeterCapture:
        row = self._s.get(MeterCapture, capture_id)
        if row is None or row.machine_id != machine_id or row.state not in LIVE:
            raise BusinessRuleViolation("The report names a reading that is not live", code="REPORT_READINGS_INVALID")
        return row

    def _unbillable(self, body: DailyReportIn) -> list[dict[str, Any]]:
        lines = []
        for line in body.unbillable:
            reason = self._s.get(EngineHourReason, line.reason_id)
            if reason is None or reason.kind is not EngineHourReasonKind.UNBILLABLE_REASON or not reason.is_active:
                raise BusinessRuleViolation(
                    "Unbillable hours need an active unbillable reason", code="REASON_NOT_ALLOWED"
                )
            lines.append({"reason_id": str(line.reason_id), "hours": str(line.hours)})
        return lines

    def _previous(self, body: DailyReportIn) -> DailyOperationalReport | None:
        if body.supersedes_id is None:
            return None
        old = self.row(body.supersedes_id, lock=True)
        if (
            old.machine_id != body.machine_id
            or old.report_date != body.report_date
            or old.status not in (DailyReportStatus.SUBMITTED, DailyReportStatus.RETURNED)
        ):
            raise BusinessRuleViolation("This report cannot be replaced", code="REPORT_NOT_SUPERSEDABLE")
        return old

    def submit(self, body: DailyReportIn, source: str) -> DailyReportDto:
        existing = self._s.get(DailyOperationalReport, body.id)
        if existing is not None:  # offline retry of the same operation
            if (
                existing.machine_id != body.machine_id
                or existing.report_date != body.report_date
                or existing.opening_ref != body.opening_ref
                or existing.closing_ref != body.closing_ref
            ):
                raise Conflict("Report id reused with different content", code="REPORT_ID_CONFLICT")
            return self.dtos([existing])[0]
        machine = self._machine(body.machine_id)
        eff = PolicyService(self._s).engine_hours(self._tid, machine.id, at=self._now)
        opening = self._capture(body.opening_ref, machine.id)
        closing = self._capture(body.closing_ref, machine.id)
        _, end = self._day_window(body.report_date)
        if (
            opening.captured_at > closing.captured_at
            or closing.captured_at >= end
            or not (closing.captured_at.astimezone(self._tz).date() == body.report_date)
        ):
            raise BusinessRuleViolation("The readings do not fit the report date", code="REPORT_READINGS_INVALID")
        total = self._total(machine.id, opening, closing)
        if total is None:
            raise BusinessRuleViolation("The readings went backwards", code="REPORT_READINGS_INVALID")
        lines = self._unbillable(body)
        unbillable = sum((line.hours for line in body.unbillable), ZERO)
        billable = body.billable_hours if body.billable_hours is not None else max(total - unbillable, ZERO)
        difference = total - billable - unbillable
        if difference < ZERO:
            raise BusinessRuleViolation(
                "Billable and unbillable hours exceed the hours between the readings", code="REPORT_HOURS_EXCEED_TOTAL"
            )
        if eff.policy.daily_report_evidence_required and not body.evidence_attachment_ids:
            raise BusinessRuleViolation("This report needs a photo", code="REPORT_EVIDENCE_REQUIRED")
        for attachment_id in body.evidence_attachment_ids:
            if self._s.get(CaptureAttachment, attachment_id) is None:
                raise NotFound("Evidence attachment not found", code="ATTACHMENT_NOT_FOUND")
        previous = self._previous(body)
        duplicate_of = self._active_for_day(body) if previous is None else None
        allocations = self._day_allocations(machine.id, body.report_date)
        row = DailyOperationalReport(
            id=body.id,
            tenant_id=self._tid,
            machine_id=machine.id,
            report_date=body.report_date,
            opening_ref=opening.id,
            opening_reading=opening.reading,
            closing_ref=closing.id,
            closing_reading=closing.reading,
            total_hours=total,
            billable_hours=billable,
            unbillable_hours=unbillable,
            difference_hours=difference,
            unbillable=lines,
            allocations=[a.model_dump(mode="json") for a in self._allocation_view(allocations)],
            evidence_attachment_ids=list(body.evidence_attachment_ids),
            note=body.note,
            status=DailyReportStatus.SUBMITTED,
            supersedes_id=previous.id if previous else None,
            duplicate_of_id=duplicate_of,
            submitted_by=self._ctx.user_id,
            submitted_at=self._now,
            client_created_at=body.client_created_at,
            source=source,
            policy_version=eff.version_stamp[:80],
            is_late=self._is_late(body, eff.policy.daily_report_cutoff_hour),
        )
        if previous is not None:
            previous.status = DailyReportStatus.SUPERSEDED
            self._s.flush()
        self._s.add(row)
        self._s.flush()
        self._audit(row, "meter.daily_report.submitted", {"status": row.status.value, "total_hours": str(total)}, None)
        OutboxWriter(self._s).emit(
            topic=TOPIC,
            event_type="DailyReportSubmitted",
            key=str(machine.id),
            payload={
                "report_id": str(row.id),
                "machine_id": str(machine.id),
                "report_date": body.report_date.isoformat(),
                "total_hours": str(total),
            },
            tenant_id=self._tid,
        )
        if duplicate_of is not None:
            EngineHoursMonitor(self._s, self._tid, self._now).flag_duplicate_report(row)
        return self.dtos([row])[0]

    def _active_for_day(self, body: DailyReportIn) -> uuid.UUID | None:
        return self._s.execute(
            select(DailyOperationalReport.id)
            .where(
                DailyOperationalReport.machine_id == body.machine_id,
                DailyOperationalReport.report_date == body.report_date,
                DailyOperationalReport.status.in_(ACTIVE),
            )
            .limit(1)
        ).scalar_one_or_none()

    def _is_late(self, body: DailyReportIn, cutoff_hour: int) -> bool:
        cutoff = datetime.combine(body.report_date, time(hour=cutoff_hour), self._tz)
        return body.client_created_at.astimezone(self._tz) > cutoff

    def review(self, report_id: uuid.UUID, body: DailyReportReviewIn) -> DailyReportDto:
        row = self.row(report_id, lock=True)
        if row.status is not DailyReportStatus.SUBMITTED:
            raise Conflict("This report was already reviewed or replaced", code="REPORT_ALREADY_REVIEWED")
        if row.submitted_by == self._ctx.user_id:
            sod_violation(self._tid, self._ctx.user_id, "review", "daily_operational_report", row.id)
            raise BusinessRuleViolation("The submitter cannot review their own report", code="SEGREGATION_OF_DUTIES")
        before = row.status.value
        row.status = DailyReportStatus(body.decision)
        row.reviewed_by, row.reviewed_at, row.review_note = self._ctx.user_id, self._now, body.note
        self._s.flush()
        self._audit(
            row,
            f"meter.daily_report.{body.decision.lower()}",
            {"status": row.status.value, "before": before},
            body.note,
        )
        if row.status is DailyReportStatus.RETURNED and row.submitted_by is not None:
            OutboxWriter(self._s).emit(
                topic=TOPIC,
                event_type="DailyReportReturned",
                key=str(row.machine_id),
                payload={
                    "report_id": str(row.id),
                    "machine_id": str(row.machine_id),
                    "report_date": row.report_date.isoformat(),
                    "submitted_by": str(row.submitted_by),
                    "note": body.note,
                },
                tenant_id=self._tid,
            )
        return self.dtos([row])[0]

    def _audit(self, row: DailyOperationalReport, action: str, after: dict[str, Any], reason: str | None) -> None:
        AuditService(self._s).record(
            actor=self._ctx.audit_actor(),
            action=action,
            entity_type="daily_operational_report",
            entity_id=row.id,
            tenant_id=self._tid,
            after={"machine_id": str(row.machine_id), "report_date": row.report_date.isoformat(), **after},
            reason=reason,
        )
