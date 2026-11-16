"""Machine reports (ADR-008 §2): submit (online and offline share this path), approve, reject, read.

Rules, all enforced here (the phone checks the sum and its cached available hours; the server decides):
- A supervisor reports only on machines currently assigned to them (open SUPERVISOR assignment); holders of the
  approve permission may report on any machine, but never decide their own report.
- The previous reading is the machine's last approved one (else its approved baseline); the new reading must be
  higher; the lines (customers' hours and non-productive hours with a reason and a note) add up to the difference
  exactly, in the machine's meter precision.
- A customer's total in a report is at most the customer's available hours: activated - used - reserved by other
  SUBMITTED reports. One SUBMITTED report per machine at a time (the next waits).
- Approval consumes the customers' hours FIFO (hours ledger CONSUMED), writes the allocation ledger and makes the
  reading the machine's last approved one. Rejection (with a reason) releases the reservation; a corrected report on
  the same reading follows."""

import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import ColumnElement, Select, false, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound
from asseta.core.outbox import OutboxWriter
from asseta.core.signals import sod_violation
from asseta.modules.finance.common import tenant_settings
from asseta.modules.fleet.models import AssignmentRole, Machine, MachineAssignment, StaffMember
from asseta.modules.hours.engine import HoursEngine
from asseta.modules.hours.ledger import ZERO
from asseta.modules.hours.models import HoursLedgerEntry, HoursPurchase, LedgerEntryType
from asseta.modules.hours.numbering import next_number
from asseta.modules.identity.principal import RequestContext
from asseta.modules.jobs.models import Customer
from asseta.modules.machine_reports.dto import (
    AvailableHoursDto,
    LotDto,
    MachineReportContextDto,
    MachineReportDecisionIn,
    MachineReportDto,
    MachineReportIn,
    MachineReportLineDto,
    MachineReportReasonDto,
    MachineReportRejectIn,
    MachineReportStatusDto,
    TrackerCheckDto,
)
from asseta.modules.machine_reports.hours import available_hours, consume, scoped_machine
from asseta.modules.machine_reports.models import (
    MachineReport,
    MachineReportLine,
    MachineReportStatus,
    ReportLineKind,
)
from asseta.modules.machine_reports.permissions import APPROVE_PERMISSION
from asseta.modules.machine_reports.readings import last_approved, start_point, tracker_hours, write_allocations
from asseta.modules.meter.dto import FindingDto
from asseta.modules.meter.engine_models import EngineHourReason, EngineHourReasonKind
from asseta.modules.meter.models import CaptureState, JobException, MeterCapture
from asseta.modules.meter.service import MeterService
from asseta.modules.policy.capabilities import CUSTOMER_HOURS, require_capability
from asseta.modules.policy.schemas import ReportHoursScope

TOPIC = "asseta.machine_reports"
SERIES = "MR"
LIVE_CAPTURE = (CaptureState.ACCEPTED, CaptureState.PROVISIONAL)
# Holding any of these, a person reads every machine report of the tenant; others read their own and their machines'.
OVERSIGHT = frozenset({APPROVE_PERMISSION, "tenant.finance.report"})


def own_staff(session: Session, ctx: RequestContext) -> StaffMember | None:
    return session.execute(
        select(StaffMember).where(StaffMember.keycloak_subject == ctx.subject, StaffMember.is_active.is_(True))
    ).scalar_one_or_none()


def supervised_machine_ids(staff_id: uuid.UUID) -> Select[uuid.UUID]:
    """Machines the staff member is the open SUPERVISOR assignment of."""
    return select(MachineAssignment.machine_id).where(
        MachineAssignment.staff_member_id == staff_id,
        MachineAssignment.role == AssignmentRole.SUPERVISOR,
        MachineAssignment.effective_to.is_(None),
    )


def oversees(ctx: RequestContext) -> bool:
    return bool(OVERSIGHT & set(ctx.permissions))


def report_scope(session: Session, ctx: RequestContext) -> ColumnElement[bool] | None:
    """None: every report. Otherwise the caller's own reports and reports on machines assigned to them."""
    if oversees(ctx):
        return None
    staff = own_staff(session, ctx)
    mine = MachineReport.submitted_by == ctx.user_id
    if staff is None:
        return mine
    return or_(mine, MachineReport.machine_id.in_(supervised_machine_ids(staff.id)))


def report_query(
    session: Session,
    ctx: RequestContext,
    *,
    q: str | None = None,
    machine_id: uuid.UUID | None = None,
    status: MachineReportStatus | None = None,
    customer_id: uuid.UUID | None = None,
    submitted_by: uuid.UUID | None = None,
    period: list[ColumnElement[bool]] | None = None,
) -> Select[MachineReport]:
    stmt = select(MachineReport).order_by(MachineReport.submitted_at.desc(), MachineReport.report_number.desc())
    if (scope := report_scope(session, ctx)) is not None:
        stmt = stmt.where(scope)
    if machine_id is not None:
        stmt = stmt.where(MachineReport.machine_id == machine_id)
    if status is not None:
        stmt = stmt.where(MachineReport.status == status)
    if submitted_by is not None:
        stmt = stmt.where(MachineReport.submitted_by == submitted_by)
    if customer_id is not None:
        stmt = stmt.where(
            MachineReport.id.in_(
                select(MachineReportLine.report_id).where(MachineReportLine.customer_id == customer_id)
            )
        )
    if period:
        stmt = stmt.where(*period)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.join(Machine, Machine.id == MachineReport.machine_id).where(
            or_(MachineReport.report_number.ilike(like), Machine.asset_code.ilike(like), Machine.name.ilike(like))
        )
    return stmt


def _decimals(machine: Machine) -> int:
    return max(1, machine.meter_decimal_places)


class MachineReportService:
    def __init__(self, session: Session, ctx: RequestContext, now: datetime):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid, self._now = session, ctx, ctx.tenant_id, now
        self._audit = AuditService(session)
        self.engine = HoursEngine(session, ctx.tenant_id, ctx.audit_actor(), now)

    # --- reads ------------------------------------------------------------------------------------------------
    def report(self, report_id: uuid.UUID, lock: bool = False) -> MachineReport:
        stmt = select(MachineReport).where(MachineReport.id == report_id)
        if not lock and (scope := report_scope(self._s, self._ctx)) is not None:
            stmt = stmt.where(scope)
        row = self._s.execute(stmt.with_for_update() if lock else stmt).scalar_one_or_none()
        if row is None:
            raise NotFound("Machine report not found", code="REPORT_NOT_FOUND")
        return row

    def dtos(self, reports: list[MachineReport], detail: bool = False) -> list[MachineReportDto]:
        if not reports:
            return []
        ids = [r.id for r in reports]
        lines: dict[uuid.UUID, list[MachineReportLine]] = defaultdict(list)
        for line in self._s.execute(
            select(MachineReportLine)
            .where(MachineReportLine.report_id.in_(ids))
            .order_by(MachineReportLine.report_id, MachineReportLine.line_no)
        ).scalars():
            lines[line.report_id].append(line)
        reasons = {
            r.id: r
            for r in self._s.execute(
                select(EngineHourReason).where(
                    EngineHourReason.id.in_({x.reason_id for ls in lines.values() for x in ls if x.reason_id})
                )
            ).scalars()
        }
        lots: dict[tuple[uuid.UUID, uuid.UUID], list[LotDto]] = defaultdict(list)
        for e, number in self._s.execute(
            select(HoursLedgerEntry, HoursPurchase.purchase_number)
            .join(HoursPurchase, HoursPurchase.id == HoursLedgerEntry.purchase_id)
            .where(
                HoursLedgerEntry.machine_report_id.in_(ids),
                HoursLedgerEntry.entry_type == LedgerEntryType.CONSUMED,
            )
            .order_by(HoursLedgerEntry.created_at, HoursPurchase.created_at, HoursPurchase.purchase_number)
        ):
            assert e.machine_report_id is not None
            lots[(e.machine_report_id, e.customer_id)].append(
                LotDto(purchase_id=e.purchase_id, purchase_number=number, machine_id=e.machine_id, hours=e.hours)
            )
        corrected = dict(
            self._s.execute(
                select(MachineReport.corrects_id, MachineReport.id).where(MachineReport.corrects_id.in_(ids))
            ).all()
        )
        captures = {
            c.id: c
            for c in self._s.execute(
                select(MeterCapture).where(MeterCapture.id.in_({r.capture_id for r in reports}))
            ).scalars()
        }
        out = []
        for r in reports:
            mine = lines[r.id]
            available: dict[uuid.UUID, Decimal] = {}
            if detail and r.status is MachineReportStatus.SUBMITTED:
                scope = scoped_machine(self.engine.policy.report_hours_scope, r.machine_id)
                customers = [x.customer_id for x in mine if x.customer_id is not None]
                available = {cid: a.available for cid, a in available_hours(self._s, customers, scope, r.id).items()}
            capture = captures.get(r.capture_id)
            dto = MachineReportDto(
                id=r.id,
                report_number=r.report_number,
                machine_id=r.machine_id,
                capture_id=r.capture_id,
                start_source=r.start_source,
                start_ref=r.start_ref,
                start_reading=r.start_reading,
                start_at=r.start_at,
                end_reading=r.end_reading,
                end_at=r.end_at,
                hours=r.hours,
                customer_hours=sum((x.hours for x in mine if x.kind is ReportLineKind.CUSTOMER), ZERO),
                non_productive_hours=sum((x.hours for x in mine if x.kind is ReportLineKind.NON_PRODUCTIVE), ZERO),
                status=r.status,
                corrects_id=r.corrects_id,
                corrected_by_id=corrected.get(r.id),
                note=r.note,
                source=r.source,
                submitted_by=r.submitted_by,
                submitted_at=r.submitted_at,
                client_created_at=r.client_created_at,
                decided_by=r.decided_by,
                decided_at=r.decided_at,
                decision_note=r.decision_note,
                policy_version=r.policy_version,
                photo_attachment_id=capture.photo_attachment_id if capture else None,
                capture_state=capture.state.value if capture else None,
                lines=[
                    MachineReportLineDto(
                        id=x.id,
                        line_no=x.line_no,
                        kind=x.kind,
                        customer_id=x.customer_id,
                        reason_id=x.reason_id,
                        reason_code=reasons[x.reason_id].code if x.reason_id in reasons else None,
                        reason_name=reasons[x.reason_id].name if x.reason_id in reasons else None,
                        hours=x.hours,
                        note=x.note,
                        available_hours=available.get(x.customer_id) if x.customer_id else None,
                        lots=lots.get((r.id, x.customer_id), []) if x.customer_id else [],
                    )
                    for x in mine
                ],
            )
            if detail:
                dto.findings = [
                    FindingDto(type=f.exception_type, severity=f.severity, blocking=f.blocking, evidence=f.evidence)
                    for f in self._s.execute(
                        select(JobException).where(JobException.meter_capture_id == r.capture_id)
                    ).scalars()
                ]
                dto.tracker = self.tracker_check(r)
            out.append(dto)
        return out

    def dto(self, report: MachineReport) -> MachineReportDto:
        return self.dtos([report], detail=True)[0]

    def tracker_check(self, r: MachineReport) -> TrackerCheckDto:
        found = tracker_hours(self._s, r.machine_id, r.start_at, r.end_at)
        if found is None:
            return TrackerCheckDto(available=False, tracker_hours=None, meter_hours=r.hours, difference=None)
        hours, from_at, to_at = found
        return TrackerCheckDto(
            available=True,
            tracker_hours=hours,
            meter_hours=r.hours,
            difference=r.hours - hours,
            tracker_from_at=from_at,
            tracker_to_at=to_at,
        )

    def reasons(self, include_inactive: bool = False) -> list[MachineReportReasonDto]:
        stmt = (
            select(EngineHourReason)
            .where(EngineHourReason.kind == EngineHourReasonKind.NON_PRODUCTIVE)
            .order_by(EngineHourReason.name, EngineHourReason.code)
        )
        if not include_inactive:
            stmt = stmt.where(EngineHourReason.is_active.is_(True))
        return [MachineReportReasonDto.model_validate(r) for r in self._s.execute(stmt).scalars()]

    def available(self, machine_id: uuid.UUID, customer_ids: list[uuid.UUID] | None = None) -> list[AvailableHoursDto]:
        """Customers' hours a new report on the machine may draw on (customers with hours, or the ones asked)."""
        scope = scoped_machine(self.engine.policy.report_hours_scope, machine_id)
        rows = available_hours(self._s, customer_ids, scope)
        return [
            AvailableHoursDto(
                customer_id=a.customer_id,
                machine_id=scope,
                remaining=a.remaining,
                reserved=a.reserved,
                available=a.available,
            )
            for a in rows.values()
        ]

    def context(self, machine_id: uuid.UUID) -> MachineReportContextDto:
        machine = self._machine(machine_id)
        self._check_machine_access(machine)
        point = start_point(self._s, machine.id)
        pending = self._pending(machine.id)
        last = self._s.execute(
            select(MachineReport.submitted_at)
            .where(MachineReport.machine_id == machine.id)
            .order_by(MachineReport.submitted_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        return MachineReportContextDto(
            machine_id=machine.id,
            meter_decimal_places=machine.meter_decimal_places,
            previous_reading=point.reading if point else None,
            previous_at=point.at if point else None,
            previous_source=point.source if point else None,
            meter_epoch=point.epoch if point else 0,
            pending_report_id=pending.id if pending else None,
            last_report_at=last,
            hours_scope=self.engine.policy.report_hours_scope.value,
            customers=sorted(
                (a for a in self.available(machine.id) if a.available > 0), key=lambda a: str(a.customer_id)
            ),
            reasons=self.reasons(),
        )

    def statuses(self, machine_ids: list[uuid.UUID] | None = None) -> list[MachineReportStatusDto]:
        """Report status of the caller's machines (field users: those assigned to them; others: every active one)."""
        stmt = select(Machine).where(Machine.status != "DISPOSED").order_by(Machine.asset_code)
        if not oversees(self._ctx):
            staff = own_staff(self._s, self._ctx)
            stmt = stmt.where(Machine.id.in_(supervised_machine_ids(staff.id)) if staff is not None else false())
        if machine_ids:
            stmt = stmt.where(Machine.id.in_(machine_ids))
        machines = list(self._s.execute(stmt).scalars())
        today = self._now.astimezone(ZoneInfo(tenant_settings(self._s, self._tid).timezone)).date()
        out = []
        for m in machines:
            approved = last_approved(self._s, m.id)
            latest = self._s.execute(
                select(MachineReport)
                .where(MachineReport.machine_id == m.id)
                .order_by(MachineReport.submitted_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            pending = self._pending(m.id)
            point = start_point(self._s, m.id)
            tz = ZoneInfo(tenant_settings(self._s, self._tid).timezone)
            out.append(
                MachineReportStatusDto(
                    machine_id=m.id,
                    machine_code=m.asset_code,
                    machine_name=m.name,
                    meter_decimal_places=m.meter_decimal_places,
                    previous_reading=point.reading if point else None,
                    previous_at=point.at if point else None,
                    previous_source=point.source if point else None,
                    last_approved_reading=approved.end_reading if approved else None,
                    last_approved_at=approved.end_at if approved else None,
                    last_report_at=latest.submitted_at if latest else None,
                    days_since_report=(today - latest.submitted_at.astimezone(tz).date()).days if latest else None,
                    pending_report_id=pending.id if pending else None,
                    pending_report_number=pending.report_number if pending else None,
                    rejected_report_id=latest.id
                    if latest is not None and latest.status is MachineReportStatus.REJECTED
                    else None,
                )
            )
        return out

    def sync_snapshot(self, window_days: int = 30) -> dict[str, Any]:
        """What a phone needs to make reports offline (full snapshots, replace the local sets): the reason list, the
        state of the caller's machines, the customers' available hours and the caller's own recent reports."""
        states = self.statuses()
        machine_ids = [s.machine_id for s in states]
        scope = self.engine.policy.report_hours_scope
        hours: list[AvailableHoursDto] = []
        if scope is ReportHoursScope.CUSTOMER:
            hours = [a for a in self.available(machine_ids[0]) if a.available > 0] if machine_ids else []
        else:
            for mid in machine_ids:
                hours += [a for a in self.available(mid) if a.available > 0]
        names = dict(
            self._s.execute(
                select(Customer.id, Customer.name).where(Customer.id.in_({a.customer_id for a in hours}))
            ).all()
        )
        for a in hours:
            a.customer_name = names.get(a.customer_id)
        since = self._now - timedelta(days=window_days)
        mine = list(
            self._s.execute(
                select(MachineReport)
                .where(
                    MachineReport.submitted_by == self._ctx.user_id,
                    or_(MachineReport.submitted_at >= since, MachineReport.status == MachineReportStatus.SUBMITTED),
                )
                .order_by(MachineReport.submitted_at.desc())
                .limit(200)
            ).scalars()
        )
        return {
            "machine_report_reasons": self.reasons(),
            "machine_report_states": states,
            "machine_report_hours": hours,
            "my_machine_reports": self.dtos(mine),
        }

    # --- submit -----------------------------------------------------------------------------------------------
    def _machine(self, machine_id: uuid.UUID, lock: bool = False) -> Machine:
        stmt = select(Machine).where(Machine.id == machine_id)
        machine = self._s.execute(stmt.with_for_update() if lock else stmt).scalar_one_or_none()
        if machine is None:
            raise NotFound("Machine not found", code="MACHINE_NOT_FOUND")
        return machine

    def _check_machine_access(self, machine: Machine) -> None:
        """Supervisors report on machines currently assigned to them; approvers on any machine."""
        if APPROVE_PERMISSION in self._ctx.permissions:
            return
        staff = own_staff(self._s, self._ctx)
        assigned = (
            self._s.execute(supervised_machine_ids(staff.id).where(MachineAssignment.machine_id == machine.id)).first()
            if staff is not None
            else None
        )
        if assigned is None:
            raise BusinessRuleViolation(
                f"{machine.asset_code} is not assigned to you; report on the machines you supervise",
                code="MACHINE_NOT_ASSIGNED",
            )

    def _pending(self, machine_id: uuid.UUID) -> MachineReport | None:
        return self._s.execute(
            select(MachineReport).where(
                MachineReport.machine_id == machine_id, MachineReport.status == MachineReportStatus.SUBMITTED
            )
        ).scalar_one_or_none()

    def _replay(self, body: MachineReportIn) -> MachineReport | None:
        if body.id is None:
            return None
        existing = self._s.get(MachineReport, body.id)
        if existing is None:
            return None
        capture = body.capture.id if body.capture is not None else body.capture_id
        if existing.machine_id != body.machine_id or existing.capture_id != capture:
            raise Conflict("Report id reused with different content", code="REPORT_ID_CONFLICT")
        return existing

    def _reading(self, body: MachineReportIn, machine: Machine, device_session_id: uuid.UUID | None) -> MeterCapture:
        if body.capture is not None:
            reading = body.capture.model_copy(update={"machine_id": machine.id})
            MeterService(self._s, self._ctx, self._now).submit(
                reading, device_session_id=device_session_id, for_machine_report=True
            )
            capture_id = reading.id
        else:
            assert body.capture_id is not None
            capture_id = body.capture_id
        capture = self._s.get(MeterCapture, capture_id)
        if capture is None:
            raise NotFound("Meter reading not found", code="CAPTURE_NOT_FOUND")
        if capture.machine_id != machine.id:
            raise BusinessRuleViolation("The reading is of another machine", code="CAPTURE_MACHINE_MISMATCH")
        if capture.state not in LIVE_CAPTURE:
            raise BusinessRuleViolation(
                f"The reading was {capture.state.value.lower()}; take a new reading", code="CAPTURE_REJECTED"
            )
        live = self._s.execute(
            select(MachineReport.report_number).where(
                MachineReport.capture_id == capture.id,
                MachineReport.status.in_((MachineReportStatus.SUBMITTED, MachineReportStatus.APPROVED)),
            )
        ).scalar_one_or_none()
        if live is not None:
            raise BusinessRuleViolation(f"This reading is already reported in {live}", code="CAPTURE_ALREADY_REPORTED")
        return capture

    def _check_corrects(self, body: MachineReportIn, capture: MeterCapture) -> None:
        if body.corrects_report_id is None:
            return
        old = self._s.get(MachineReport, body.corrects_report_id)
        if (
            old is None
            or old.status is not MachineReportStatus.REJECTED
            or old.machine_id != body.machine_id
            or old.capture_id != capture.id
        ):
            raise BusinessRuleViolation(
                "corrects_report_id must name a rejected report of this machine on the same reading",
                code="CORRECTS_INVALID",
            )

    def _lock_customers(self, customer_ids: set[uuid.UUID]) -> dict[uuid.UUID, Customer]:
        """Customers named in a report, locked in id order: reservations of one customer are serialised across
        machines (two reports may never both take the same available hours)."""
        rows = {
            c.id: c
            for c in self._s.execute(
                select(Customer).where(Customer.id.in_(customer_ids)).order_by(Customer.id).with_for_update()
            ).scalars()
        }
        missing = customer_ids - rows.keys()
        if missing:
            raise NotFound("Customer not found", code="CUSTOMER_NOT_FOUND")
        return rows

    def _check_available(
        self,
        machine_id: uuid.UUID,
        wanted: dict[uuid.UUID, Decimal],
        customers: dict[uuid.UUID, Customer],
        exclude: uuid.UUID | None,
    ) -> None:
        if not wanted:
            return
        scope = scoped_machine(self.engine.policy.report_hours_scope, machine_id)
        found = available_hours(self._s, list(wanted), scope, exclude)
        for cid, hours in sorted(wanted.items(), key=lambda kv: str(kv[0])):
            have = found[cid].available
            if hours > have:
                raise BusinessRuleViolation(
                    f"{customers[cid].name} has {max(have, ZERO)} hours available; the report gives them {hours}",
                    code="HOURS_NOT_AVAILABLE",
                )

    def _check_lines(self, body: MachineReportIn, machine: Machine, difference: Decimal) -> dict[uuid.UUID, Decimal]:
        step = Decimal(1).scaleb(-_decimals(machine))
        if any(line.hours != line.hours.quantize(step) for line in body.lines):
            raise BusinessRuleViolation(
                f"Hours are reported in steps of {step} (the machine's meter precision)", code="HOURS_PRECISION"
            )
        total = sum((line.hours for line in body.lines), ZERO)
        if total != difference:
            raise BusinessRuleViolation(
                f"The lines add up to {total} hours; the meter moved {difference} hours (they must be equal)",
                code="REPORT_SUM_MISMATCH",
            )
        wanted: dict[uuid.UUID, Decimal] = {}
        for line in body.lines:
            if line.kind is ReportLineKind.CUSTOMER:
                assert line.customer_id is not None
                if line.customer_id in wanted:
                    raise BusinessRuleViolation(
                        "Give each customer one line (add their hours together)", code="DUPLICATE_CUSTOMER_LINE"
                    )
                wanted[line.customer_id] = line.hours
            else:
                reason = self._s.get(EngineHourReason, line.reason_id)
                if reason is None:
                    raise NotFound("Reason not found", code="REASON_NOT_FOUND")
                if reason.kind is not EngineHourReasonKind.NON_PRODUCTIVE or not reason.is_active:
                    raise BusinessRuleViolation(
                        "Choose an active reason from the machine-report reason list", code="REASON_INVALID"
                    )
        return wanted

    def submit(
        self, body: MachineReportIn, source: str = "API", device_session_id: uuid.UUID | None = None
    ) -> MachineReportDto:
        if (replay := self._replay(body)) is not None:
            return self.dto(replay)  # offline retry: exactly one report
        machine = self._machine(body.machine_id, lock=True)
        self._check_machine_access(machine)
        pending = self._pending(machine.id)
        if pending is not None:
            raise BusinessRuleViolation(
                f"{pending.report_number} on this machine is waiting for a decision; the next report waits",
                code="REPORT_PENDING",
            )
        capture = self._reading(body, machine, device_session_id)
        self._check_corrects(body, capture)
        point = start_point(self._s, machine.id)
        if point is None:
            raise BusinessRuleViolation(
                "The machine has no approved starting reading (meter baseline) yet", code="BASELINE_REQUIRED"
            )
        difference = capture.reading - point.reading
        if difference < 0:
            raise BusinessRuleViolation(
                f"The new reading {capture.reading} is below the last approved reading {point.reading}",
                code="READING_NOT_HIGHER",
            )
        if difference == 0:
            raise BusinessRuleViolation(
                "The meter has not moved since the last approved reading", code="NOTHING_TO_REPORT"
            )
        wanted = self._check_lines(body, machine, difference)
        customers: dict[uuid.UUID, Customer] = {}
        if wanted:
            require_capability(self._s, self._tid, CUSTOMER_HOURS, self._now)
            customers = self._lock_customers(set(wanted))
            self._check_available(machine.id, wanted, customers, None)
        local = self._now.astimezone(ZoneInfo(tenant_settings(self._s, self._tid).timezone))
        report = MachineReport(
            id=body.id or uuid.uuid4(),
            tenant_id=self._tid,
            report_number=f"{SERIES}-{local.year}-{next_number(self._s, self._tid, SERIES, local.year):05d}",
            machine_id=machine.id,
            capture_id=capture.id,
            start_source=point.source,
            start_ref=point.ref,
            start_reading=point.reading,
            start_at=point.at,
            end_reading=capture.reading,
            end_at=capture.captured_at,
            meter_epoch=point.epoch,
            hours=difference,
            status=MachineReportStatus.SUBMITTED,
            corrects_id=body.corrects_report_id,
            note=body.note,
            source=source,
            submitted_by=self._ctx.user_id,
            submitted_at=self._now,
            client_created_at=body.client_created_at,
            policy_version=self.engine.eff.version_stamp,
            created_at=self._now,
        )
        self._s.add(report)
        try:
            with self._s.begin_nested():
                self._s.flush()
        except IntegrityError as exc:  # a concurrent report on the machine or the reading won the race
            raise BusinessRuleViolation(
                "Another report on this machine or reading was submitted at the same time", code="REPORT_PENDING"
            ) from exc
        for no, line in enumerate(body.lines, start=1):
            self._s.add(
                MachineReportLine(
                    id=uuid.uuid4(),
                    tenant_id=self._tid,
                    report_id=report.id,
                    line_no=no,
                    kind=line.kind,
                    customer_id=line.customer_id,
                    reason_id=line.reason_id,
                    hours=line.hours,
                    note=line.note,
                )
            )
        self._s.flush()
        self._audit.record(
            actor=self._ctx.audit_actor(source.lower()),
            action="machine_report.submitted",
            entity_type="machine_report",
            entity_id=report.id,
            tenant_id=self._tid,
            policy_version=report.policy_version[:64],
            after={
                "report_number": report.report_number,
                "machine_id": str(machine.id),
                "start_reading": str(point.reading),
                "end_reading": str(capture.reading),
                "hours": str(difference),
                "lines": [
                    {
                        "kind": line.kind.value,
                        "customer_id": str(line.customer_id) if line.customer_id else None,
                        "reason_id": str(line.reason_id) if line.reason_id else None,
                        "hours": str(line.hours),
                    }
                    for line in body.lines
                ],
                "corrects_id": str(body.corrects_report_id) if body.corrects_report_id else None,
            },
        )
        self._emit("MachineReportSubmitted", report)
        return self.dto(report)

    # --- decisions --------------------------------------------------------------------------------------------
    def _decidable(self, report_id: uuid.UUID, action: str) -> MachineReport:
        report = self.report(report_id, lock=True)
        if report.status is not MachineReportStatus.SUBMITTED:
            raise BusinessRuleViolation(
                f"{report.report_number} is already {report.status.value.lower()}", code="REPORT_NOT_PENDING"
            )
        if report.submitted_by is not None and report.submitted_by == self._ctx.user_id:
            sod_violation(self._tid, self._ctx.user_id, action, "machine_report", report.id)
            raise BusinessRuleViolation(
                "The person who submitted a report cannot decide it", code="SEGREGATION_OF_DUTIES"
            )
        return report

    def approve(self, report_id: uuid.UUID, body: MachineReportDecisionIn) -> MachineReportDto:
        report = self._decidable(report_id, "machine_report_approve")
        machine = self._machine(report.machine_id, lock=True)
        point = start_point(self._s, machine.id)
        if point is None or point.ref != report.start_ref or point.reading != report.start_reading:
            raise BusinessRuleViolation(
                "The machine's previous reading changed since this report was submitted; reject it so the supervisor "
                "reports again",
                code="REPORT_READINGS_CHANGED",
            )
        lines = list(
            self._s.execute(
                select(MachineReportLine)
                .where(MachineReportLine.report_id == report.id)
                .order_by(MachineReportLine.line_no)
            ).scalars()
        )
        wanted = {x.customer_id: x.hours for x in lines if x.customer_id is not None}
        lots: dict[uuid.UUID, list[dict[str, Any]]] = {}
        touched: set[tuple[uuid.UUID, uuid.UUID]] = set()
        if wanted:
            require_capability(self._s, self._tid, CUSTOMER_HOURS, self._now)
            customers = self._lock_customers(set(wanted))
            self._check_available(machine.id, wanted, customers, report.id)
            scope = scoped_machine(self.engine.policy.report_hours_scope, machine.id)
            for line in lines:
                if line.customer_id is None:
                    continue
                taken = consume(self.engine, self._s, report, line.customer_id, line.hours, scope)
                lots[line.id] = [{"purchase_id": str(p.id), "hours": str(h)} for p, _, h in taken]
                touched |= {(line.customer_id, m) for _, m, _ in taken}
        report.status = MachineReportStatus.APPROVED
        report.decided_by, report.decided_at, report.decision_note = self._ctx.user_id, self._now, body.note
        self._s.flush()
        write_allocations(self._s, self._ctx.audit_actor(), report, lines, lots)
        for customer_id, machine_id in sorted(touched, key=str):
            self.engine.check_low_balance(customer_id, machine_id)
        self._audit.record(
            actor=self._ctx.audit_actor(),
            action="machine_report.approved",
            entity_type="machine_report",
            entity_id=report.id,
            tenant_id=self._tid,
            before={"status": "SUBMITTED"},
            after={
                "status": "APPROVED",
                "report_number": report.report_number,
                "lots": {str(k): v for k, v in lots.items()},
                "note": body.note,
            },
        )
        self._emit("MachineReportApproved", report)
        return self.dto(report)

    def reject(self, report_id: uuid.UUID, body: MachineReportRejectIn) -> MachineReportDto:
        report = self._decidable(report_id, "machine_report_reject")
        report.status = MachineReportStatus.REJECTED
        report.decided_by, report.decided_at, report.decision_note = self._ctx.user_id, self._now, body.reason
        self._s.flush()
        self._audit.record(
            actor=self._ctx.audit_actor(),
            action="machine_report.rejected",
            entity_type="machine_report",
            entity_id=report.id,
            tenant_id=self._tid,
            before={"status": "SUBMITTED"},
            after={"status": "REJECTED", "report_number": report.report_number},
            reason=body.reason,
        )
        self._emit("MachineReportRejected", report)
        return self.dto(report)

    def _emit(self, event_type: str, report: MachineReport) -> None:
        OutboxWriter(self._s).emit(
            topic=TOPIC,
            event_type=event_type,
            key=str(report.machine_id),
            payload={
                "report_id": str(report.id),
                "report_number": report.report_number,
                "machine_id": str(report.machine_id),
                "hours": str(report.hours),
                "status": report.status.value,
                "submitted_by": str(report.submitted_by) if report.submitted_by else None,
                "decided_by": str(report.decided_by) if report.decided_by else None,
                "decision_note": report.decision_note,
            },
            tenant_id=self._tid,
        )
