"""Idempotent, dependency-ordered push of offline operations.

Each operation: (1) replay -> stored result (DUPLICATE), (2) unmet dependency -> DEFERRED (not stored; device
retries), (3) read-only/suspended tenant -> QUARANTINED (stored, never applied, replayed when the device re-sends
after reactivation), (4) dispatched to the same domain service the online API uses, inside a savepoint.
Domain conflicts are returned as structured CONFLICT results with server state — never last-write-wins.
"""

import hashlib
import json
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.errors import AppError, BusinessRuleViolation, DependencyUnavailable
from asseta.modules.identity.principal import RequestContext
from asseta.modules.jobs.dto import AcknowledgementIn, ActivityIn
from asseta.modules.jobs.models import Job
from asseta.modules.jobs.service import JobService
from asseta.modules.meter.dto import MeterCaptureIn
from asseta.modules.meter.service import MeterService
from asseta.modules.policy.service import PolicyService
from asseta.modules.sync.dto import OperationIn, OperationResultDto, PushIn, PushResultDto
from asseta.modules.sync.models import ClientOperation, DeviceSession, OperationStatus
from asseta.modules.sync.service import SyncService

CONFLICT_CODES = {
    "INVALID_JOB_TRANSITION",
    "READING_NOT_ALLOWED",
    "MACHINE_BUSY",
    "CAPTURE_ID_CONFLICT",
    "JOB_NOT_ACTIVE",
    "STALE_VERSION",
}
REQUIRED_PERMISSION = {
    "METER_CAPTURE": "tenant.meter.capture",
    "JOB_ACTIVITY": "tenant.job.log",
    "JOB_ACKNOWLEDGEMENT": "tenant.job.log",
    "JOB_TRANSITION": "tenant.job.log",
}


class JobTransitionOp(BaseModel):
    job_id: uuid.UUID
    action: str


def _hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


class PushService:
    def __init__(self, session: Session, ctx: RequestContext, now: datetime):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid, self._now = session, ctx, ctx.tenant_id, now

    def push(self, device_id: str | None, body: PushIn) -> PushResultDto:
        sync = SyncService(self._s, self._ctx, self._now)
        device = sync.active_device(device_id)
        policy = PolicyService(self._s).device_sync(self._tid, at=self._now).policy
        if len(body.operations) > policy.max_batch_operations:
            raise BusinessRuleViolation(
                f"Batch exceeds {policy.max_batch_operations} operations", code="BATCH_TOO_LARGE"
            )
        offset = (self._now - body.device_now).total_seconds()
        results = [self._one(device, op) for op in body.operations]
        sync.touch(device, offset)
        return PushResultDto(
            server_time=self._now,
            clock_offset_s=round(offset, 1),
            clock_skew_alert=abs(offset) > policy.clock_skew_alert_seconds,
            results=results,
        )

    def _one(self, device: DeviceSession, op: OperationIn) -> OperationResultDto:
        digest = _hash(op.payload)
        existing = self._s.get(ClientOperation, op.id)
        if existing is not None:
            if existing.payload_sha256 != digest or existing.op_type != op.op_type:
                return OperationResultDto(
                    id=op.id,
                    status="REJECTED",
                    error={"code": "OPERATION_ID_REUSED", "message": "Same id, different content"},
                )
            if existing.status is not OperationStatus.QUARANTINED or self._ctx.read_only:
                existing.attempts += 1
                return OperationResultDto(
                    id=op.id, status="DUPLICATE", result=existing.result, error=existing.result.get("error")
                )
        unmet = [
            d
            for d in op.depends_on
            if self._s.execute(select(ClientOperation.status).where(ClientOperation.id == d)).scalar_one_or_none()
            is not OperationStatus.ACKED
        ]
        if unmet:
            return OperationResultDto(
                id=op.id, status="DEFERRED", error={"code": "DEPENDENCY_PENDING", "depends_on": [str(u) for u in unmet]}
            )
        if self._ctx.read_only:
            result = {
                "error": {
                    "code": "SUBSCRIPTION_READ_ONLY",
                    "message": "Tenant is read-only; operation kept and will apply after reactivation",
                }
            }
            self._store(device, op, digest, OperationStatus.QUARANTINED, result, existing)
            return OperationResultDto(id=op.id, status="QUARANTINED", result=result, error=result["error"])
        status, result = self._dispatch(op)
        self._store(device, op, digest, status, result, existing)
        return OperationResultDto.model_validate(
            {"id": op.id, "status": status.value, "result": result, "error": result.get("error")}
        )

    def _store(
        self,
        device: DeviceSession,
        op: OperationIn,
        digest: str,
        status: OperationStatus,
        result: dict[str, Any],
        existing: ClientOperation | None,
    ) -> None:
        if existing is not None:  # a previously quarantined op being replayed after reactivation
            existing.status, existing.result, existing.attempts = status, result, existing.attempts + 1
        else:
            self._s.add(
                ClientOperation(
                    id=op.id,
                    tenant_id=self._tid,
                    device_session_id=device.id,
                    op_type=op.op_type,
                    payload_sha256=digest,
                    payload=op.payload,
                    status=status,
                    result=result,
                    created_at_device=op.created_at_device,
                    received_at=self._now,
                )
            )
        self._s.flush()

    def _dispatch(self, op: OperationIn) -> tuple[OperationStatus, dict[str, Any]]:
        needed = REQUIRED_PERMISSION[op.op_type]
        if needed not in self._ctx.permissions:
            return OperationStatus.REJECTED, {"error": {"code": "PERMISSION_DENIED", "message": f"Missing {needed}"}}
        handlers: dict[str, Callable[[], BaseModel]] = {
            "METER_CAPTURE": lambda: MeterService(self._s, self._ctx, self._now).submit(
                MeterCaptureIn.model_validate(op.payload)
            ),
            "JOB_ACTIVITY": lambda: JobService(self._s, self._ctx).add_activity(
                uuid.UUID(str(op.payload["job_id"])), ActivityIn.model_validate(op.payload)
            ),
            "JOB_ACKNOWLEDGEMENT": lambda: JobService(self._s, self._ctx).acknowledge(
                uuid.UUID(str(op.payload["job_id"])), AcknowledgementIn.model_validate(op.payload)
            ),
            "JOB_TRANSITION": lambda: self._transition(JobTransitionOp.model_validate(op.payload)),
        }
        try:
            with self._s.begin_nested():
                dto = handlers[op.op_type]()
                return OperationStatus.ACKED, {"entity": dto.model_dump(mode="json")}
        except DependencyUnavailable:
            raise  # infrastructure failure: whole push fails, device retries everything (idempotent)
        except ValidationError as exc:
            return OperationStatus.REJECTED, {"error": {"code": "VALIDATION_FAILED", "message": str(exc)[:500]}}
        except (KeyError, ValueError) as exc:
            return OperationStatus.REJECTED, {"error": {"code": "BAD_PAYLOAD", "message": str(exc)[:500]}}
        except AppError as exc:
            status = OperationStatus.CONFLICT if exc.code in CONFLICT_CODES else OperationStatus.REJECTED
            return status, {"error": {"code": exc.code, "message": exc.message}, "server_state": self._state(op)}

    def _transition(self, body: JobTransitionOp) -> BaseModel:
        if body.action not in ("START", "COMPLETE"):
            raise ValueError("devices may only START or COMPLETE jobs")
        return JobService(self._s, self._ctx).transition(body.job_id, body.action, None)

    def _state(self, op: OperationIn) -> dict[str, Any]:
        job_id = op.payload.get("job_id")
        if not job_id:
            return {}
        job = self._s.get(Job, uuid.UUID(str(job_id)))
        return {
            "job_id": str(job_id),
            "job_status": job.status.value if job else "NOT_FOUND",
            "job_version": job.version if job else None,
        }
