"""Machine photos (R1-B): immutable, content-hashed evidence in object storage; short-lived download URLs."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from pydantic import BaseModel, ConfigDict
from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from asseta.core.audit import AuditService
from asseta.core.config import get_settings
from asseta.core.db import Base, UuidPk, get_session, utcnow
from asseta.core.errors import ERROR_RESPONSES, BusinessRuleViolation, NotFound
from asseta.core.storage import ObjectStore, sha256_hex, sniff_image
from asseta.modules.fleet.router import MACHINE_READ, MACHINE_WRITE
from asseta.modules.fleet.service import MachineService
from asseta.modules.identity.principal import RequestContext


class MachinePhoto(UuidPk, Base):
    __tablename__ = "machine_photo"
    __table_args__ = (UniqueConstraint("machine_id", "sha256", name="uq_machine_photo_hash"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenant.id"), nullable=False, index=True)
    machine_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("machine.id"), nullable=False, index=True)
    object_key: Mapped[str] = mapped_column(String(300), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    content_type: Mapped[str] = mapped_column(String(40), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    caption: Mapped[str | None] = mapped_column(String(200))
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class MachinePhotoDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    machine_id: uuid.UUID
    sha256: str
    content_type: str
    size_bytes: int
    caption: str | None
    uploaded_at: datetime


class PhotoUrlDto(BaseModel):
    url: str
    expires_in_seconds: int


router = APIRouter(prefix="/api/v1/tenant/machines", tags=["fleet"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]


def get_object_store(request: Request) -> ObjectStore:
    store: ObjectStore = request.app.state.object_store
    return store


@router.post("/{machine_id}/photos", response_model=MachinePhotoDto, status_code=201, operation_id="uploadMachinePhoto")
async def upload(
    machine_id: uuid.UUID,
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(MACHINE_WRITE)],
    store: Annotated[ObjectStore, Depends(get_object_store)],
    file: Annotated[UploadFile, File()],
    caption: Annotated[str | None, Form(max_length=200)] = None,
) -> MachinePhotoDto:
    limit = get_settings().max_image_bytes
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise BusinessRuleViolation(f"Image exceeds {limit} bytes", code="FILE_TOO_LARGE")
    content_type = sniff_image(data)
    MachineService(session, ctx).machine(machine_id)  # 404 for other tenants' machines (RLS)
    digest = sha256_hex(data)
    existing = session.execute(
        select(MachinePhoto).where(MachinePhoto.machine_id == machine_id, MachinePhoto.sha256 == digest)
    ).scalar_one_or_none()
    if existing is not None:
        return MachinePhotoDto.model_validate(existing)  # same image re-uploaded: idempotent
    key = f"tenants/{ctx.tenant_id}/machines/{machine_id}/photos/{digest}"
    store.put_immutable(key, data, content_type, digest)
    photo = MachinePhoto(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        machine_id=machine_id,
        object_key=key,
        sha256=digest,
        content_type=content_type,
        size_bytes=len(data),
        caption=caption,
        uploaded_by=ctx.user_id,
    )
    session.add(photo)
    session.flush()
    AuditService(session).record(
        actor=ctx.audit_actor(),
        action="fleet.machine_photo.uploaded",
        entity_type="machine_photo",
        entity_id=photo.id,
        tenant_id=ctx.tenant_id,
        after={"machine_id": str(machine_id), "sha256": digest, "size_bytes": len(data)},
    )
    return MachinePhotoDto.model_validate(photo)


@router.get("/{machine_id}/photos", response_model=list[MachinePhotoDto], operation_id="listMachinePhotos")
def list_photos(
    machine_id: uuid.UUID, session: DbSession, ctx: Annotated[RequestContext, Depends(MACHINE_READ)]
) -> list[MachinePhotoDto]:
    MachineService(session, ctx).machine(machine_id)
    rows = session.execute(
        select(MachinePhoto).where(MachinePhoto.machine_id == machine_id).order_by(MachinePhoto.uploaded_at.desc())
    ).scalars()
    return [MachinePhotoDto.model_validate(p) for p in rows]


@router.get("/{machine_id}/photos/{photo_id}/url", response_model=PhotoUrlDto, operation_id="getMachinePhotoUrl")
def photo_url(
    machine_id: uuid.UUID,
    photo_id: uuid.UUID,
    session: DbSession,
    _: Annotated[RequestContext, Depends(MACHINE_READ)],
    store: Annotated[ObjectStore, Depends(get_object_store)],
) -> PhotoUrlDto:
    photo = session.execute(
        select(MachinePhoto).where(MachinePhoto.id == photo_id, MachinePhoto.machine_id == machine_id)
    ).scalar_one_or_none()
    if photo is None:  # RLS hides other tenants' photos
        raise NotFound("Photo not found")
    ttl = get_settings().presigned_url_ttl_seconds
    return PhotoUrlDto(url=store.presigned_get(photo.object_key, ttl), expires_in_seconds=ttl)
