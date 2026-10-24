"""Meter capture ingestion + validation (online API and offline sync share this path)."""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, false, func, or_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound
from asseta.core.outbox import OutboxWriter
from asseta.modules.fleet.models import Machine, MachineAssignment, StaffMember
from asseta.modules.identity.principal import RequestContext
from asseta.modules.jobs.models import Job, JobStatus
from asseta.modules.jobs.scope import (
    METER_OVERSIGHT,
    assigned_machine_ids,
    own_staff,
    restricted_to_own,
    scoped_job_ids,
)
from asseta.modules.meter.dto import CaptureResultDto, FindingDto, MeterCaptureDto, MeterCaptureIn, ResetDto, ResetIn
from asseta.modules.meter.engine_hours import EngineHoursMonitor
from asseta.modules.meter.models import (
    CaptureAttachment,
    CaptureState,
    ExceptionStatus,
    ExceptionType,
    GpsStatus,
    JobException,
    MeterCapture,
    MeterResetEvent,
    ReadingKind,
)
from asseta.modules.meter.rules import (
    Finding,
    GpsEvidence,
    PriorReading,
    capture_findings,
    gps_findings,
    location_findings,
    sequence_findings,
    telemetry_findings,
)
from asseta.modules.policy.schemas import CaptureMode, MeterCapturePolicy, PolicyType
from asseta.modules.policy.service import PolicyService
from asseta.modules.sync.models import DevicePolicySnapshot, DeviceSession

FUTURE_SKEW = timedelta(minutes=5)
SNAPSHOT_CLOCK_TOLERANCE = FUTURE_SKEW  # device clock vs the server's issued_at / valid_until stamps
_ACTIVE = (CaptureState.ACCEPTED, CaptureState.PROVISIONAL)


def capture_list_query(
    job_id: uuid.UUID | None = None,
    machine_id: uuid.UUID | None = None,
    kind: ReadingKind | None = None,
    state: CaptureState | None = None,
    captured_from: datetime | None = None,
    captured_to: datetime | None = None,
) -> Select[MeterCapture]:
    """Meter readings across jobs (latest captured first), shared by the readings endpoint and report."""
    stmt = select(MeterCapture).order_by(MeterCapture.captured_at.desc(), MeterCapture.id)
    for col, val in (
        (MeterCapture.job_id, job_id),
        (MeterCapture.machine_id, machine_id),
        (MeterCapture.kind, kind),
        (MeterCapture.state, state),
    ):
        if val is not None:
            stmt = stmt.where(col == val)
    if captured_from is not None:
        stmt = stmt.where(MeterCapture.captured_at >= captured_from)
    if captured_to is not None:
        stmt = stmt.where(MeterCapture.captured_at < captured_to)
    return stmt


def own_capture_filter(ctx: RequestContext, staff: StaffMember | None) -> Any:
    """A field user's readings: captured by them, or on a job they supervise."""
    return or_(MeterCapture.supervisor_user_id == ctx.user_id, MeterCapture.job_id.in_(scoped_job_ids(staff)))


def own_exception_filter(ctx: RequestContext, staff: StaffMember | None) -> Any:
    """Findings on the caller's readings or on jobs they supervise."""
    own = select(MeterCapture.id).where(own_capture_filter(ctx, staff))
    return or_(JobException.meter_capture_id.in_(own), JobException.job_id.in_(scoped_job_ids(staff)))


def own_reset_filter(ctx: RequestContext, staff: StaffMember | None) -> Any:
    """Resets the caller requested, or on machines currently assigned to them."""
    assigned = MeterResetEvent.machine_id.in_(assigned_machine_ids(staff.id)) if staff is not None else false()
    return or_(MeterResetEvent.requested_by == ctx.user_id, assigned)


class MeterService:
    def __init__(self, session: Session, ctx: RequestContext, now: datetime):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid, self._now = session, ctx, ctx.tenant_id, now

    def _policy(
        self, body: MeterCaptureIn, machine_id: uuid.UUID, site_id: uuid.UUID | None
    ) -> tuple[MeterCapturePolicy, str]:
        svc = PolicyService(self._s)
        server = svc.meter_capture(self._tid, machine_id, site_id, at=body.captured_at)
        if not body.policy_version_ids:
            return server.policy, server.version_stamp
        snapshot = MeterCapturePolicy.model_validate(svc.by_stamp(PolicyType.METER_CAPTURE, body.policy_version_ids))
        # The device enforced its offline snapshot; record both so later policy changes never rewrite history.
        return snapshot, f"{server.version_stamp}|device:{len(body.policy_version_ids)}v"

    def _snapshot_finding(self, body: MeterCaptureIn, device_session_id: uuid.UUID | None) -> Finding | None:
        """F-8: the snapshot a device says it enforced must have been issued to that device and valid at capture
        time (issued_at <= captured_at <= valid_until, within clock tolerance). Otherwise a modified client could
        apply an older, more lenient version of its own tenant's policy. The capture is still kept (field
        continuity) but held for review with a blocking exception, never rejected."""
        ids = sorted({str(v) for v in body.policy_version_ids})
        snap = DevicePolicySnapshot
        issued = select(snap.issued_at, snap.valid_until).where(
            snap.policy_type == PolicyType.METER_CAPTURE.value,
            snap.version_ids.contains(ids),
            snap.version_ids.contained_by(ids),  # both ways: the same set of versions
        )
        if device_session_id is not None:  # offline push: the device session that sent it
            issued = issued.where(snap.device_session_id == device_session_id)
        else:  # online submission: the caller's own registered device with the capture's device id
            issued = issued.join(DeviceSession, DeviceSession.id == snap.device_session_id).where(
                DeviceSession.device_id == body.device_id, DeviceSession.user_id == self._ctx.user_id
            )
        at = body.captured_at
        valid = issued.where(
            snap.issued_at <= at + SNAPSHOT_CLOCK_TOLERANCE, snap.valid_until >= at - SNAPSHOT_CLOCK_TOLERANCE
        )
        if self._s.execute(valid.limit(1)).first() is not None:
            return None
        nearest = self._s.execute(
            issued.order_by(func.abs(func.extract("epoch", snap.issued_at - at))).limit(1)
        ).first()
        evidence: dict[str, Any] = {
            "reason": "OUTSIDE_VALIDITY" if nearest else "NOT_ISSUED_TO_DEVICE",
            "device_id": body.device_id,
            "captured_at": at.isoformat(),
            "policy_version_ids": ids,
        }
        if nearest is not None:
            evidence |= {"issued_at": nearest.issued_at.isoformat(), "valid_until": nearest.valid_until.isoformat()}
        return Finding(ExceptionType.POLICY_SNAPSHOT_UNVERIFIED, "WARNING", True, evidence)

    def _target(self, body: MeterCaptureIn, correction: bool) -> tuple[Job | None, uuid.UUID, uuid.UUID | None]:
        """The job (locked) and machine a reading belongs to. A DAILY reading may name only its machine; a field
        user may only read machines assigned to them (others are "not found"). An approved correction replaces a
        historical reading, so the job-status window that applies to new readings does not apply to it."""
        if body.job_id is not None:
            job = self._s.execute(select(Job).where(Job.id == body.job_id).with_for_update()).scalar_one_or_none()
            if job is None:
                raise NotFound("Job not found")
            allowed = {
                ReadingKind.OPENING: (JobStatus.APPROVED,),
                ReadingKind.CLOSING: (JobStatus.IN_PROGRESS,),
                ReadingKind.DAILY: (JobStatus.APPROVED, JobStatus.IN_PROGRESS),
            }
            if not correction and job.status not in allowed[body.kind]:
                raise BusinessRuleViolation(
                    f"{body.kind.value} reading not allowed while job is {job.status.value}",
                    code="READING_NOT_ALLOWED",
                )
            if body.machine_id is not None and body.machine_id != job.machine_id:
                raise BusinessRuleViolation("machine_id is not the job's machine", code="READING_MACHINE_MISMATCH")
            return job, job.machine_id, job.job_site_id
        machine = self._s.get(Machine, body.machine_id)
        if machine is None:
            raise NotFound("Machine not found", code="MACHINE_NOT_FOUND")
        if not correction and restricted_to_own(self._ctx, METER_OVERSIGHT):
            staff = own_staff(self._s, self._ctx)
            assigned = (
                self._s.execute(
                    assigned_machine_ids(staff.id).where(MachineAssignment.machine_id == machine.id)
                ).first()
                if staff is not None
                else None
            )
            if assigned is None:
                raise NotFound("Machine not found", code="MACHINE_NOT_FOUND")
        return None, machine.id, None

    def submit(
        self,
        body: MeterCaptureIn,
        device_session_id: uuid.UUID | None = None,
        *,
        correction_of: MeterCapture | None = None,
        recorded_by: uuid.UUID | None = None,
    ) -> CaptureResultDto:
        """Record a reading (online API and offline sync). `correction_of` (with `recorded_by`, the proposer) is
        used only when an approved correction is applied: the old reading becomes SUPERSEDED and this replaces it."""
        existing = self._s.get(MeterCapture, body.id)
        if existing is not None:  # idempotent replay of the same device operation
            if existing.reading != body.reading or existing.job_id != body.job_id or existing.kind != body.kind:
                raise Conflict("Capture id reused with different content", code="CAPTURE_ID_CONFLICT")
            return self._result(existing)
        job, machine_id, site_id = self._target(body, correction_of is not None)
        now = self._now  # injected clock: server receive time and skew checks are deterministic
        policy, stamp = self._policy(body, machine_id, site_id)
        photo = self._s.get(CaptureAttachment, body.photo_attachment_id) if body.photo_attachment_id else None
        if body.photo_attachment_id and photo is None:
            raise NotFound("Photo attachment not found")
        if correction_of is not None:
            correction_of.state = CaptureState.SUPERSEDED  # status-only change, audited by the correction
            self._s.flush()
        elif body.supersedes_id:
            self._supersede(body.supersedes_id, machine_id, job)

        # A DAILY reading carries the same evidence rules as a closing reading.
        expected = CaptureMode(policy.opening_mode if body.kind is ReadingKind.OPENING else policy.closing_mode)
        gps = GpsEvidence(body.gps.status, body.gps.accuracy_m, body.gps.captured_at)
        findings, reject = gps_findings(policy, gps, body.captured_at)
        if body.policy_version_ids and (unverified := self._snapshot_finding(body, device_session_id)):
            findings.append(unverified)
        findings += capture_findings(
            policy, expected, body.capture_mode, photo is not None, body.reading, body.ocr_value, body.ocr_confidence
        )
        if body.captured_at > now + FUTURE_SKEW:
            findings.append(
                Finding(
                    ExceptionType.CLOCK_SKEW,
                    "WARNING",
                    True,
                    {"device_time": body.captured_at.isoformat(), "server_time": now.isoformat()},
                )
            )
        if photo is not None and self._image_reused(photo.sha256, body.id):
            findings.append(Finding(ExceptionType.DUPLICATE_IMAGE, "CRITICAL", True, {"sha256": photo.sha256}))
        prior, reset = self._prior(machine_id, body.captured_at)
        findings += sequence_findings(
            policy, body.reading, body.captured_at, prior, reset, body.kind is ReadingKind.OPENING
        )
        loc, comparison = self._location(machine_id, body, policy)
        findings += loc
        if body.kind is ReadingKind.CLOSING and job is not None:
            findings += self._telemetry(job, body, policy)

        state = (
            CaptureState.REJECTED
            if reject
            else (CaptureState.PROVISIONAL if any(f.blocking for f in findings) else CaptureState.ACCEPTED)
        )
        capture = MeterCapture(
            id=body.id,
            tenant_id=self._tid,
            job_id=job.id if job else None,
            machine_id=machine_id,
            kind=body.kind,
            capture_mode=body.capture_mode.value,
            reading=body.reading,
            ocr_raw_text=body.ocr_raw_text,
            ocr_value=body.ocr_value,
            ocr_confidence=body.ocr_confidence,
            ocr_engine=body.ocr_engine,
            manually_corrected=body.ocr_value is not None and body.ocr_value != body.reading,
            photo_attachment_id=photo.id if photo else None,
            photo_sha256=photo.sha256 if photo else None,
            gps_status=body.gps.status,
            latitude=body.gps.latitude,
            longitude=body.gps.longitude,
            accuracy_m=body.gps.accuracy_m,
            location_captured_at=body.gps.captured_at,
            location_provider=body.gps.provider,
            device_id=body.device_id,
            captured_at=body.captured_at,
            received_at=now,
            supervisor_user_id=recorded_by or self._ctx.user_id,
            policy_version=stamp,
            state=state,
            tracker_comparison=comparison,
            supersedes_id=body.supersedes_id,
        )
        self._s.add(capture)
        self._s.flush()
        for f in findings:
            self._s.execute(
                insert(JobException)
                .values(
                    id=uuid.uuid4(),
                    tenant_id=self._tid,
                    job_id=job.id if job else None,
                    machine_id=machine_id,
                    meter_capture_id=capture.id,
                    exception_type=f.type,
                    severity=f.severity,
                    blocking=f.blocking,
                    dedupe_key=f"{capture.id}:{f.type.value}",
                    evidence=f.evidence,
                    policy_version=stamp,
                    status=ExceptionStatus.OPEN,
                    created_at=now,
                )
                .on_conflict_do_nothing()
            )
        AuditService(self._s).record(
            actor=self._ctx.audit_actor("mobile" if body.device_id else "api"),
            action="meter.capture.recorded",
            entity_type="meter_capture",
            entity_id=capture.id,
            tenant_id=self._tid,
            policy_version=stamp,
            after={
                "kind": body.kind.value,
                "reading": str(body.reading),
                "state": state.value,
                "findings": [f.type.value for f in findings],
                "supersedes_id": str(body.supersedes_id) if body.supersedes_id else None,
            },
        )
        job_ref = str(job.id) if job else None
        OutboxWriter(self._s).emit(
            topic="asseta.meter",
            event_type="MeterCaptured",
            key=str(machine_id),
            payload={
                "capture_id": str(capture.id),
                "job_id": job_ref,
                "machine_id": str(machine_id),
                "kind": body.kind.value,
                "state": state.value,
            },
            tenant_id=self._tid,
        )
        if findings:
            OutboxWriter(self._s).emit(
                topic="asseta.meter",
                event_type="MeterExceptionRaised",
                key=str(machine_id),
                payload={
                    "capture_id": str(capture.id),
                    "job_id": job_ref,
                    "machine_id": str(machine_id),
                    "exception_types": sorted({f.type.value for f in findings}),
                    "blocking": any(f.blocking for f in findings),
                },
                tenant_id=self._tid,
            )
        EngineHoursMonitor(self._s, self._tid, now).flag_machine(machine_id)
        return self._result(capture)

    def _result(self, capture: MeterCapture) -> CaptureResultDto:
        rows = self._s.execute(select(JobException).where(JobException.meter_capture_id == capture.id)).scalars()
        return CaptureResultDto(
            capture=MeterCaptureDto.model_validate(capture),
            findings=[
                FindingDto(type=r.exception_type, severity=r.severity, blocking=r.blocking, evidence=r.evidence)
                for r in rows
            ],
        )

    def request_reset(self, body: ResetIn) -> ResetDto:
        """Documented meter replacement/rollover, PENDING until a different user with approval permission decides
        (online API and the offline METER_RESET_REQUEST operation share this path)."""
        if self._s.get(Machine, body.machine_id) is None:
            raise NotFound("Machine not found", code="MACHINE_NOT_FOUND")
        evidence = body.evidence_attachment_id
        if evidence is not None and self._s.get(CaptureAttachment, evidence) is None:
            raise NotFound("Evidence attachment not found", code="ATTACHMENT_NOT_FOUND")
        row = MeterResetEvent(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            status="PENDING",
            requested_by=self._ctx.user_id,
            created_at=self._now,
            **body.model_dump(),
        )
        self._s.add(row)
        self._s.flush()
        return ResetDto.model_validate(row)

    def _supersede(self, capture_id: uuid.UUID, machine_id: uuid.UUID, job: Job | None) -> None:
        """Inline supersession (the behaviour before two-person corrections), only when the tenant's policy does not
        require a second person; otherwise corrections go through `POST /meter-corrections`."""
        eff = PolicyService(self._s).engine_hours(self._tid, machine_id, at=self._now)
        if eff.policy.correction_requires_second_person:
            raise BusinessRuleViolation(
                "Reading corrections need a second person's approval: propose a correction instead",
                code="CORRECTION_APPROVAL_REQUIRED",
            )
        if "tenant.meter.approve" not in self._ctx.permissions:
            raise BusinessRuleViolation("Corrections require meter approval permission", code="CORRECTION_FORBIDDEN")
        stmt = select(MeterCapture).where(MeterCapture.id == capture_id, MeterCapture.machine_id == machine_id)
        if job is not None:
            stmt = stmt.where(MeterCapture.job_id == job.id)
        old = self._s.execute(stmt.with_for_update()).scalar_one_or_none()
        if old is None or old.state not in _ACTIVE:
            raise NotFound("Active capture to supersede not found")
        old.state = CaptureState.SUPERSEDED  # status-only change on an otherwise immutable record (audited)
        self._s.flush()

    def _image_reused(self, sha256: str, capture_id: uuid.UUID) -> bool:
        return (
            self._s.execute(
                select(MeterCapture.id).where(MeterCapture.photo_sha256 == sha256, MeterCapture.id != capture_id)
            ).first()
            is not None
        )

    def _prior(self, machine_id: uuid.UUID, at: datetime) -> tuple[PriorReading | None, Decimal | None]:
        row = self._s.execute(
            select(MeterCapture)
            .where(
                MeterCapture.machine_id == machine_id, MeterCapture.captured_at < at, MeterCapture.state.in_(_ACTIVE)
            )
            .order_by(MeterCapture.captured_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if row is None:
            return None, None
        reset = self._s.execute(
            select(MeterResetEvent.new_reading)
            .where(
                MeterResetEvent.machine_id == machine_id,
                MeterResetEvent.status == "APPROVED",
                MeterResetEvent.effective_at > row.captured_at,
                MeterResetEvent.effective_at <= at,
            )
            .order_by(MeterResetEvent.effective_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        job_ref = str(row.job_id) if row.job_id else ""
        return PriorReading(row.reading, row.captured_at, job_ref, row.kind.value), reset

    def _location(
        self, machine_id: uuid.UUID, body: MeterCaptureIn, policy: MeterCapturePolicy
    ) -> tuple[list[Finding], dict[str, object]]:
        if body.gps.status is not GpsStatus.FIX or body.gps.captured_at is None:
            return [], {"compared": False, "reason": "no phone GPS fix"}
        window = timedelta(seconds=policy.tracker_comparison_window_seconds)
        row = self._s.execute(
            text("""
            SELECT event_time, accuracy_m, ST_Y(location) AS lat, ST_X(location) AS lon,
                   ST_Distance(location::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography) AS d
            FROM machine_position_event
            WHERE machine_id = :m AND event_time BETWEEN :f AND :t AND quality = 'GOOD'
            ORDER BY abs(extract(epoch FROM event_time - :at)) LIMIT 1"""),
            {
                "m": machine_id,
                "lat": body.gps.latitude,
                "lon": body.gps.longitude,
                "at": body.gps.captured_at,
                "f": body.gps.captured_at - window,
                "t": body.gps.captured_at + window,
            },
        ).first()
        if row is None:
            return location_findings(policy, None, body.gps.accuracy_m, None, None, body.gps.captured_at)
        findings, comparison = location_findings(
            policy, float(row.d), body.gps.accuracy_m, row.accuracy_m, row.event_time, body.gps.captured_at
        )
        comparison.update(
            {"tracker_latitude": row.lat, "tracker_longitude": row.lon, "tracker_accuracy_m": row.accuracy_m}
        )
        return findings, comparison

    def _telemetry(self, job: Job, body: MeterCaptureIn, policy: MeterCapturePolicy) -> list[Finding]:
        opening = self._s.execute(
            select(MeterCapture).where(
                MeterCapture.job_id == job.id, MeterCapture.kind == ReadingKind.OPENING, MeterCapture.state.in_(_ACTIVE)
            )
        ).scalar_one_or_none()
        if opening is None:
            return []
        hours = self._s.execute(
            text("""
            SELECT (SELECT engine_hours FROM machine_position_event WHERE machine_id = :m AND engine_hours IS NOT NULL
                      AND event_time <= :b ORDER BY event_time DESC LIMIT 1),
                   (SELECT engine_hours FROM machine_position_event WHERE machine_id = :m AND engine_hours IS NOT NULL
                      AND event_time <= :e ORDER BY event_time DESC LIMIT 1)"""),
            {"m": job.machine_id, "b": opening.captured_at, "e": body.captured_at},
        ).one()
        if hours[0] is None or hours[1] is None:
            return []  # capability not reporting: no comparison, no claim
        return telemetry_findings(policy, body.reading - opening.reading, Decimal(hours[1]) - Decimal(hours[0]))
