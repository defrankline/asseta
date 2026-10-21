"""Versioned offline sync API (`/api/v1/sync`, protocol 1) + tenant device administration."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.clock import get_now
from asseta.core.db import get_session
from asseta.core.errors import ERROR_RESPONSES
from asseta.core.storage import ObjectStore
from asseta.modules.fleet.photos import get_object_store
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.dependencies import requires
from asseta.modules.identity.principal import RequestContext
from asseta.modules.sync.blobs import BlobService
from asseta.modules.sync.dto import (
    BlobSessionDto,
    BlobStartIn,
    BootstrapDto,
    ChangesDto,
    DeviceRegisterIn,
    DeviceSessionDto,
    PushIn,
    PushResultDto,
    RevokeIn,
)
from asseta.modules.sync.models import DeviceSession
from asseta.modules.sync.push import PushService
from asseta.modules.sync.service import SyncService

SYNC_READ = requires("tenant.sync.read", S.TENANT, "Device bootstrap and delta pull")
SYNC_PUSH = requires(
    "tenant.sync.push", S.TENANT, "Device offline operation push and evidence upload", quarantine_when_read_only=True
)
DEVICE_ADMIN = requires("tenant.device.manage", S.TENANT, "View and revoke field devices")

router = APIRouter(prefix="/api/v1", tags=["sync"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]
Now = Annotated[datetime, Depends(get_now)]
DeviceId = Annotated[str | None, Header(alias="X-Device-Id")]


@router.post("/sync/devices", response_model=DeviceSessionDto, status_code=201, operation_id="registerDevice")
def register(
    body: DeviceRegisterIn, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(SYNC_READ)]
) -> DeviceSessionDto:
    return DeviceSessionDto.model_validate(SyncService(session, ctx, now).register(body))


@router.get("/sync/bootstrap", response_model=BootstrapDto, operation_id="syncBootstrap")
def bootstrap(
    session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(SYNC_READ)], device_id: DeviceId = None
) -> BootstrapDto:
    return SyncService(session, ctx, now).bootstrap(device_id)


@router.get("/sync/changes", response_model=ChangesDto, operation_id="syncChanges")
def changes(
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(SYNC_READ)],
    cursor: Annotated[int, Query(ge=0)],
    device_id: DeviceId = None,
) -> ChangesDto:
    return SyncService(session, ctx, now).changes(device_id, cursor)


@router.post("/sync/push", response_model=PushResultDto, operation_id="syncPush")
def push(
    body: PushIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(SYNC_PUSH)],
    device_id: DeviceId = None,
) -> PushResultDto:
    return PushService(session, ctx, now).push(device_id, body)


@router.post("/sync/blobs", response_model=BlobSessionDto, status_code=201, operation_id="startBlobUpload")
def start_blob(
    body: BlobStartIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(SYNC_PUSH)],
    device_id: DeviceId = None,
) -> BlobSessionDto:
    device = SyncService(session, ctx, now).active_device(device_id)
    return BlobService(session, ctx, now).start(device, body)


@router.put("/sync/blobs/{session_id}/chunks/{index}", response_model=BlobSessionDto, operation_id="putBlobChunk")
async def put_chunk(
    session_id: uuid.UUID,
    index: int,
    request: Request,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(SYNC_PUSH)],
    device_id: DeviceId = None,
) -> BlobSessionDto:
    SyncService(session, ctx, now).active_device(device_id)
    return BlobService(session, ctx, now).put_chunk(session_id, index, await request.body())


@router.post("/sync/blobs/{session_id}/complete", response_model=BlobSessionDto, operation_id="completeBlobUpload")
def complete_blob(
    session_id: uuid.UUID,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(SYNC_PUSH)],
    store: Annotated[ObjectStore, Depends(get_object_store)],
    device_id: DeviceId = None,
) -> BlobSessionDto:
    SyncService(session, ctx, now).active_device(device_id)
    return BlobService(session, ctx, now).complete(session_id, store)


@router.get("/tenant/devices", response_model=list[DeviceSessionDto], operation_id="listDevices")
def devices(session: DbSession, _: Annotated[RequestContext, Depends(DEVICE_ADMIN)]) -> list[DeviceSessionDto]:
    rows = session.execute(select(DeviceSession).order_by(DeviceSession.registered_at.desc())).scalars()
    return [DeviceSessionDto.model_validate(r) for r in rows]


@router.post("/tenant/devices/{device_session_id}/revoke", response_model=DeviceSessionDto, operation_id="revokeDevice")
def revoke(
    device_session_id: uuid.UUID,
    body: RevokeIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(DEVICE_ADMIN)],
) -> DeviceSessionDto:
    row = SyncService(session, ctx, now).revoke(device_session_id, body.reason)
    AuditService(session).record(
        actor=ctx.audit_actor(),
        action="sync.device.revoked",
        entity_type="device_session",
        entity_id=row.id,
        tenant_id=ctx.tenant_id,
        reason=body.reason,
    )
    return DeviceSessionDto.model_validate(row)
