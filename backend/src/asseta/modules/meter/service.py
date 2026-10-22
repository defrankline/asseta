"""Meter capture ingestion + validation (online API and offline sync share this path)."""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound
from asseta.core.outbox import OutboxWriter
from asseta.modules.identity.principal import RequestContext
from asseta.modules.jobs.models import Job, JobStatus
from asseta.modules.meter.dto import CaptureResultDto, FindingDto, MeterCaptureDto, MeterCaptureIn
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

FUTURE_SKEW = timedelta(minutes=5)
_ACTIVE = (CaptureState.ACCEPTED, CaptureState.PROVISIONAL)


class MeterService:
    def __init__(self, session: Session, ctx: RequestContext, now: datetime):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid, self._now = session, ctx, ctx.tenant_id, now

    def _policy(self, body: MeterCaptureIn, job: Job) -> tuple[MeterCapturePolicy, str]:
        svc = PolicyService(self._s)
        server = svc.meter_capture(self._tid, job.machine_id, job.job_site_id, at=body.captured_at)
        if not body.policy_version_ids:
            return server.policy, server.version_stamp
        snapshot = MeterCapturePolicy.model_validate(svc.by_stamp(PolicyType.METER_CAPTURE, body.policy_version_ids))
        # The device enforced its offline snapshot; record both so later policy changes never rewrite history.
        return snapshot, f"{server.version_stamp}|device:{len(body.policy_version_ids)}v"

    def submit(self, body: MeterCaptureIn) -> CaptureResultDto:
        existing = self._s.get(MeterCapture, body.id)
        if existing is not None:  # idempotent replay of the same device operation
            if existing.reading != body.reading or existing.job_id != body.job_id or existing.kind != body.kind:
                raise Conflict("Capture id reused with different content", code="CAPTURE_ID_CONFLICT")
            return self._result(existing)
        job = self._s.execute(select(Job).where(Job.id == body.job_id).with_for_update()).scalar_one_or_none()
        if job is None:
            raise NotFound("Job not found")
        allowed = {ReadingKind.OPENING: (JobStatus.APPROVED,), ReadingKind.CLOSING: (JobStatus.IN_PROGRESS,)}
        if job.status not in allowed[body.kind]:
            raise BusinessRuleViolation(
                f"{body.kind.value} reading not allowed while job is {job.status.value}", code="READING_NOT_ALLOWED"
            )
        now = self._now  # injected clock: server receive time and skew checks are deterministic
        policy, stamp = self._policy(body, job)
        photo = self._s.get(CaptureAttachment, body.photo_attachment_id) if body.photo_attachment_id else None
        if body.photo_attachment_id and photo is None:
            raise NotFound("Photo attachment not found")
        if body.supersedes_id:
            self._supersede(body.supersedes_id, job)

        expected = CaptureMode(policy.opening_mode if body.kind is ReadingKind.OPENING else policy.closing_mode)
        gps = GpsEvidence(body.gps.status, body.gps.accuracy_m, body.gps.captured_at)
        findings, reject = gps_findings(policy, gps, body.captured_at)
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
        prior, reset = self._prior(job.machine_id, body.captured_at)
        findings += sequence_findings(
            policy, body.reading, body.captured_at, prior, reset, body.kind is ReadingKind.OPENING
        )
        loc, comparison = self._location(job.machine_id, body, policy)
        findings += loc
        if body.kind is ReadingKind.CLOSING:
            findings += self._telemetry(job, body, policy)

        state = (
            CaptureState.REJECTED
            if reject
            else (CaptureState.PROVISIONAL if any(f.blocking for f in findings) else CaptureState.ACCEPTED)
        )
        capture = MeterCapture(
            id=body.id,
            tenant_id=self._tid,
            job_id=job.id,
            machine_id=job.machine_id,
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
            supervisor_user_id=self._ctx.user_id,
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
                    job_id=job.id,
                    machine_id=job.machine_id,
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
            },
        )
        OutboxWriter(self._s).emit(
            topic="asseta.meter",
            event_type="MeterCaptured",
            key=str(job.machine_id),
            payload={"capture_id": str(capture.id), "job_id": str(job.id), "state": state.value},
            tenant_id=self._tid,
        )
        if findings:
            OutboxWriter(self._s).emit(
                topic="asseta.meter",
                event_type="MeterExceptionRaised",
                key=str(job.machine_id),
                payload={
                    "capture_id": str(capture.id),
                    "job_id": str(job.id),
                    "machine_id": str(job.machine_id),
                    "exception_types": sorted({f.type.value for f in findings}),
                    "blocking": any(f.blocking for f in findings),
                },
                tenant_id=self._tid,
            )
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

    def _supersede(self, capture_id: uuid.UUID, job: Job) -> None:
        if "tenant.meter.approve" not in self._ctx.permissions:
            raise BusinessRuleViolation("Corrections require meter approval permission", code="CORRECTION_FORBIDDEN")
        old = self._s.execute(
            select(MeterCapture).where(MeterCapture.id == capture_id, MeterCapture.job_id == job.id).with_for_update()
        ).scalar_one_or_none()
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
        return PriorReading(row.reading, row.captured_at, str(row.job_id), row.kind.value), reset

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
