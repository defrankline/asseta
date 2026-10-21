"""Telemetry endpoints.

* `POST /api/v1/telemetry/traccar` — gateway-authenticated (X-Asseta-Gateway-Key, constant-time hash lookup);
  no end-user token. Always 202 for authenticated requests so gateways do not retry-storm on quarantined input.
* Platform gateway management (key shown once) and tenant views of ingestion outcomes.
"""

import hashlib
import secrets
import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Header, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.clock import get_now
from asseta.core.db import DbScope, apply_scope, get_session
from asseta.core.errors import ERROR_RESPONSES, Conflict, NotAuthenticated
from asseta.core.paging import Page, PageParams, page_params, paginate
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.dependencies import requires
from asseta.modules.identity.principal import RequestContext
from asseta.modules.telemetry.ingestion import IngestionService
from asseta.modules.telemetry.models import IngestionStatus, QuarantineReason, TelemetryGateway, TrackerIngestionEvent
from asseta.modules.telemetry.traccar import TraccarAdapter
from asseta.modules.tracker.models import TelemetryAdapterKind

GATEWAY_MANAGE = requires("platform.gateway.manage", S.PLATFORM, "Manage telemetry gateways and keys")
TRACKER_READ = requires("tenant.tracker.read", S.TENANT, "View trackers, capabilities and assignments")

router = APIRouter(prefix="/api/v1", tags=["telemetry"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


class IngestResultDto(BaseModel):
    accepted: int
    duplicates: int
    quarantined: int
    reasons: list[QuarantineReason]


class GatewayIn(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    adapter: TelemetryAdapterKind


class GatewayCreatedDto(BaseModel):
    id: uuid.UUID
    name: str
    adapter: TelemetryAdapterKind
    gateway_key: str = Field(description="Shown once. Configure as X-Asseta-Gateway-Key on the gateway.")


class IngestionEventDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    received_at: datetime
    external_device_id: str | None
    tracker_id: uuid.UUID | None
    machine_id: uuid.UUID | None
    event_time: datetime | None
    status: IngestionStatus
    quarantine_reason: QuarantineReason | None
    detail: str | None


@router.post(
    "/telemetry/traccar",
    response_model=IngestResultDto,
    status_code=202,
    operation_id="ingestTraccar",
    tags=["telemetry-gateway"],
)
def ingest_traccar(
    request: Request,
    session: DbSession,
    now: Annotated[datetime, Depends(get_now)],
    payload: Annotated[dict[str, Any], Body()],
    x_asseta_gateway_key: Annotated[str | None, Header()] = None,
) -> IngestResultDto:
    if not x_asseta_gateway_key:
        raise NotAuthenticated("Gateway key required")
    apply_scope(session, DbScope.SYSTEM, None, None)
    gateway = session.execute(
        select(TelemetryGateway).where(
            TelemetryGateway.key_hash == _hash(x_asseta_gateway_key),
            TelemetryGateway.active.is_(True),
            TelemetryGateway.adapter == TelemetryAdapterKind.TRACCAR,
        )
    ).scalar_one_or_none()
    if gateway is None:
        raise NotAuthenticated("Unknown or inactive gateway key")
    gateway.last_seen_at = now
    session.flush()  # system-scope write must land before ingestion narrows the transaction to a tenant scope
    outcomes = IngestionService(session, TraccarAdapter(), gateway.id, now).ingest(payload)
    return IngestResultDto(
        accepted=sum(o.status in (IngestionStatus.ACCEPTED, IngestionStatus.ACCEPTED_NO_FIX) for o in outcomes),
        duplicates=sum(o.status is IngestionStatus.DUPLICATE for o in outcomes),
        quarantined=sum(o.status is IngestionStatus.QUARANTINED for o in outcomes),
        reasons=[o.reason for o in outcomes if o.reason is not None],
    )


@router.post(
    "/platform/telemetry-gateways",
    response_model=GatewayCreatedDto,
    status_code=201,
    operation_id="createTelemetryGateway",
)
def create_gateway(
    body: GatewayIn, session: DbSession, ctx: Annotated[RequestContext, Depends(GATEWAY_MANAGE)]
) -> GatewayCreatedDto:
    if session.execute(select(TelemetryGateway.id).where(TelemetryGateway.name == body.name)).first():
        raise Conflict("Gateway name already exists", code="DUPLICATE_GATEWAY")
    key = secrets.token_urlsafe(32)
    gw = TelemetryGateway(id=uuid.uuid4(), name=body.name, adapter=body.adapter, key_hash=_hash(key), active=True)
    session.add(gw)
    session.flush()
    AuditService(session).record(
        actor=ctx.audit_actor(),
        action="platform.gateway.created",
        entity_type="telemetry_gateway",
        entity_id=gw.id,
        tenant_id=None,
        after={"name": gw.name, "adapter": gw.adapter.value},
    )
    return GatewayCreatedDto(id=gw.id, name=gw.name, adapter=gw.adapter, gateway_key=key)


@router.get(
    "/tenant/telemetry/ingestion-events", response_model=Page[IngestionEventDto], operation_id="listIngestionEvents"
)
def ingestion_events(
    session: DbSession,
    _: Annotated[RequestContext, Depends(TRACKER_READ)],
    paging: Annotated[PageParams, Depends(page_params)],
    status: IngestionStatus | None = None,
    tracker_id: uuid.UUID | None = None,
) -> Page[IngestionEventDto]:
    stmt = select(TrackerIngestionEvent).order_by(TrackerIngestionEvent.received_at.desc())
    if status:
        stmt = stmt.where(TrackerIngestionEvent.status == status)
    if tracker_id:
        stmt = stmt.where(TrackerIngestionEvent.tracker_id == tracker_id)
    rows, total = paginate(session, stmt, paging)
    return Page(
        items=[IngestionEventDto.model_validate(r) for r in rows],
        total=total,
        page=paging.page,
        page_size=paging.page_size,
    )
