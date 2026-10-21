"""Meter captures, evidence attachments, meter resets and exception review."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.clock import get_now
from asseta.core.config import get_settings
from asseta.core.db import get_session, utcnow
from asseta.core.errors import ERROR_RESPONSES, BusinessRuleViolation, Conflict, NotFound
from asseta.core.paging import Page, PageParams, page_params, paginate
from asseta.core.storage import ObjectStore, sha256_hex, sniff_image
from asseta.modules.fleet.photos import PhotoUrlDto, get_object_store
from asseta.modules.identity.catalog import CATALOG, MenuDef
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.dependencies import requires
from asseta.modules.identity.principal import RequestContext
from asseta.modules.meter.dto import (
    AttachmentDto,
    CaptureResultDto,
    ExceptionDto,
    MeterCaptureDto,
    MeterCaptureIn,
    ResetDto,
    ResetIn,
    ReviewIn,
)
from asseta.modules.meter.models import (
    CaptureAttachment,
    ExceptionStatus,
    ExceptionType,
    JobException,
    MeterCapture,
    MeterResetEvent,
)
from asseta.modules.meter.service import MeterService

CAPTURE = requires("tenant.meter.capture", S.TENANT, "Capture hour-meter readings and evidence")
METER_READ = requires("tenant.meter.read", S.TENANT, "View meter readings, evidence and exceptions")
REVIEW = requires("tenant.meter.review", S.TENANT, "Review meter/GPS exceptions")
APPROVE = requires("tenant.meter.approve", S.TENANT, "Approve meter resets and reading corrections")
CATALOG.register_menu(
    MenuDef("tenant.exceptions", S.TENANT, "Exceptions", "/tenant/exceptions", 62, "tenant.meter.read")
)
PURPOSES = {"METER_PHOTO", "SIGNATURE", "RESET_EVIDENCE"}

router = APIRouter(prefix="/api/v1/tenant", tags=["meter"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]
Store = Annotated[ObjectStore, Depends(get_object_store)]


@router.post("/attachments", response_model=AttachmentDto, status_code=201, operation_id="uploadAttachment")
async def upload(
    session: DbSession,
    store: Store,
    ctx: Annotated[RequestContext, Depends(CAPTURE)],
    file: Annotated[UploadFile, File()],
    purpose: Annotated[str, Form()],
) -> AttachmentDto:
    if purpose not in PURPOSES:
        raise BusinessRuleViolation(f"purpose must be one of {sorted(PURPOSES)}", code="BAD_PURPOSE")
    limit = get_settings().max_image_bytes
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise BusinessRuleViolation(f"File exceeds {limit} bytes", code="FILE_TOO_LARGE")
    content_type, digest = sniff_image(data), sha256_hex(data)
    key = f"tenants/{ctx.tenant_id}/evidence/{digest}"
    store.put_immutable(key, data, content_type, digest)  # original image preserved, content-addressed
    row = CaptureAttachment(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        object_key=key,
        sha256=digest,
        content_type=content_type,
        size_bytes=len(data),
        purpose=purpose,
        uploaded_by=ctx.user_id,
    )
    session.add(row)
    session.flush()
    return AttachmentDto.model_validate(row)


@router.get("/attachments/{attachment_id}/url", response_model=PhotoUrlDto, operation_id="getAttachmentUrl")
def attachment_url(
    attachment_id: uuid.UUID, session: DbSession, store: Store, _: Annotated[RequestContext, Depends(METER_READ)]
) -> PhotoUrlDto:
    row = session.get(CaptureAttachment, attachment_id)
    if row is None:
        raise NotFound("Attachment not found")
    ttl = get_settings().presigned_url_ttl_seconds
    return PhotoUrlDto(url=store.presigned_get(row.object_key, ttl), expires_in_seconds=ttl)


@router.post("/meter-captures", response_model=CaptureResultDto, status_code=201, operation_id="submitMeterCapture")
def submit(
    body: MeterCaptureIn,
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(CAPTURE)],
    now: Annotated[datetime, Depends(get_now)],
) -> CaptureResultDto:
    return MeterService(session, ctx, now).submit(body)


@router.get("/jobs/{job_id}/meter-captures", response_model=list[MeterCaptureDto], operation_id="listJobCaptures")
def captures(
    job_id: uuid.UUID, session: DbSession, _: Annotated[RequestContext, Depends(METER_READ)]
) -> list[MeterCaptureDto]:
    rows = session.execute(
        select(MeterCapture).where(MeterCapture.job_id == job_id).order_by(MeterCapture.captured_at)
    ).scalars()
    return [MeterCaptureDto.model_validate(c) for c in rows]


@router.post("/meter-resets", response_model=ResetDto, status_code=201, operation_id="requestMeterReset")
def request_reset(body: ResetIn, session: DbSession, ctx: Annotated[RequestContext, Depends(CAPTURE)]) -> ResetDto:
    row = MeterResetEvent(
        id=uuid.uuid4(), tenant_id=ctx.tenant_id, status="PENDING", requested_by=ctx.user_id, **body.model_dump()
    )
    session.add(row)
    session.flush()
    return ResetDto.model_validate(row)


@router.post("/meter-resets/{reset_id}/decision", response_model=ResetDto, operation_id="decideMeterReset")
def decide_reset(
    reset_id: uuid.UUID, body: ReviewIn, session: DbSession, ctx: Annotated[RequestContext, Depends(APPROVE)]
) -> ResetDto:
    row = session.execute(
        select(MeterResetEvent).where(MeterResetEvent.id == reset_id).with_for_update()
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("Reset not found")
    if row.status != "PENDING":
        raise Conflict("Reset already decided", code="RESET_DECIDED")
    if row.requested_by == ctx.user_id:
        raise BusinessRuleViolation("Requester cannot approve their own reset", code="SEGREGATION_OF_DUTIES")
    row.status = "APPROVED" if body.outcome == "EXPLAINED" else "REJECTED"
    row.decided_by, row.decided_at = ctx.user_id, utcnow()
    AuditService(session).record(
        actor=ctx.audit_actor(),
        action="meter.reset.decided",
        entity_type="meter_reset",
        entity_id=row.id,
        tenant_id=ctx.tenant_id,
        after={"status": row.status},
        reason=body.note,
    )
    session.flush()
    return ResetDto.model_validate(row)


@router.get("/exceptions", response_model=Page[ExceptionDto], operation_id="listJobExceptions")
def exceptions(
    session: DbSession,
    _: Annotated[RequestContext, Depends(METER_READ)],
    paging: Annotated[PageParams, Depends(page_params)],
    status: ExceptionStatus | None = None,
    exception_type: ExceptionType | None = None,
    job_id: uuid.UUID | None = None,
) -> Page[ExceptionDto]:
    stmt = select(JobException).order_by(JobException.created_at.desc())
    if status:
        stmt = stmt.where(JobException.status == status)
    if exception_type:
        stmt = stmt.where(JobException.exception_type == exception_type)
    if job_id:
        stmt = stmt.where(JobException.job_id == job_id)
    rows, total = paginate(session, stmt, paging)
    return Page(
        items=[ExceptionDto.model_validate(e) for e in rows], total=total, page=paging.page, page_size=paging.page_size
    )


@router.post("/exceptions/{exception_id}/review", response_model=ExceptionDto, operation_id="reviewJobException")
def review(
    exception_id: uuid.UUID, body: ReviewIn, session: DbSession, ctx: Annotated[RequestContext, Depends(REVIEW)]
) -> ExceptionDto:
    row = session.execute(
        select(JobException).where(JobException.id == exception_id).with_for_update()
    ).scalar_one_or_none()
    if row is None:
        raise NotFound("Exception not found")
    if row.status is not ExceptionStatus.OPEN:
        raise Conflict("Exception already reviewed", code="ALREADY_REVIEWED")
    row.status = ExceptionStatus(body.outcome)
    row.reviewed_by, row.reviewed_at, row.review_note = ctx.user_id, utcnow(), body.note
    AuditService(session).record(
        actor=ctx.audit_actor(),
        action="meter.exception.reviewed",
        entity_type="job_exception",
        entity_id=row.id,
        tenant_id=ctx.tenant_id,
        before={"status": "OPEN"},
        after={"status": row.status.value},
        reason=body.note,
    )
    session.flush()
    return ExceptionDto.model_validate(row)


@router.get("/meter-resets", response_model=list[ResetDto], operation_id="listMeterResets")
def resets(
    session: DbSession,
    _: Annotated[RequestContext, Depends(METER_READ)],
    machine_id: uuid.UUID | None = None,
    status: str | None = None,
) -> list[ResetDto]:
    stmt = select(MeterResetEvent).order_by(MeterResetEvent.created_at.desc())
    if machine_id:
        stmt = stmt.where(MeterResetEvent.machine_id == machine_id)
    if status:
        stmt = stmt.where(MeterResetEvent.status == status)
    return [ResetDto.model_validate(r) for r in session.execute(stmt).scalars()]
