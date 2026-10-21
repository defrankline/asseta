"""Tracker endpoints: platform driver catalog + tenant tracker registry/assignments."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.clock import get_now
from asseta.core.db import get_session
from asseta.core.errors import ERROR_RESPONSES
from asseta.core.idempotency import IdempotencyGuard, request_hash
from asseta.core.paging import Page, PageParams, page_params, paginate
from asseta.core.search import ilike_any
from asseta.modules.identity.catalog import CATALOG, MenuDef
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.dependencies import requires
from asseta.modules.identity.principal import RequestContext
from asseta.modules.tracker.dto import (
    AssignTrackerIn,
    TrackerAssignmentDto,
    TrackerDto,
    TrackerIn,
    TrackerModelDto,
    TrackerModelIn,
    TrackerStateIn,
    UnassignTrackerIn,
)
from asseta.modules.tracker.models import ProvisioningState, TrackerModel
from asseta.modules.tracker.service import TrackerService, create_tracker_model

PLATFORM_MODELS = requires("platform.tracker_model.manage", S.PLATFORM, "Manage approved tracker drivers/models")
TRACKER_READ = requires("tenant.tracker.read", S.TENANT, "View trackers, capabilities and assignments")
TRACKER_WRITE = requires("tenant.tracker.write", S.TENANT, "Register, assign and retire trackers")
CATALOG.register_menu(MenuDef("tenant.trackers", S.TENANT, "Trackers", "/tenant/trackers", 40, "tenant.tracker.read"))

router = APIRouter(prefix="/api/v1", tags=["trackers"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]
Read = Annotated[RequestContext, Depends(TRACKER_READ)]
Write = Annotated[RequestContext, Depends(TRACKER_WRITE)]


def _svc(session: Session, ctx: RequestContext) -> TrackerService:
    assert ctx.tenant_id is not None
    return TrackerService(session, ctx.tenant_id, ctx.audit_actor())


@router.post(
    "/platform/tracker-models", response_model=TrackerModelDto, status_code=201, operation_id="createTrackerModel"
)
def create_model(
    body: TrackerModelIn, session: DbSession, ctx: Annotated[RequestContext, Depends(PLATFORM_MODELS)]
) -> TrackerModelDto:
    return create_tracker_model(session, body, ctx.audit_actor())


@router.get("/tenant/tracker-models", response_model=list[TrackerModelDto], operation_id="listApprovedTrackerModels")
def approved_models(
    session: DbSession, _: Read, q: Annotated[str | None, Query(max_length=100)] = None
) -> list[TrackerModelDto]:
    stmt = (
        select(TrackerModel)
        .where(TrackerModel.approved.is_(True))
        .order_by(TrackerModel.manufacturer, TrackerModel.model)
    )
    if (match := ilike_any(q, TrackerModel.manufacturer, TrackerModel.model)) is not None:
        stmt = stmt.where(match)
    rows = session.execute(stmt).scalars()
    return [TrackerModelDto.model_validate(r) for r in rows]


@router.post("/tenant/trackers", response_model=TrackerDto, status_code=201, operation_id="registerTracker")
def register(
    body: TrackerIn, session: DbSession, ctx: Write, idempotency_key: Annotated[str | None, Header()] = None
) -> TrackerDto:
    guard = IdempotencyGuard(session, str(ctx.tenant_id), "registerTracker", idempotency_key, request_hash(body))
    if (replay := guard.begin()) is not None:
        return TrackerDto.model_validate(replay)
    dto = _svc(session, ctx).register(body)
    guard.complete(dto, 201)
    return dto


@router.get("/tenant/trackers", response_model=Page[TrackerDto], operation_id="listTrackers")
def list_trackers(
    session: DbSession,
    ctx: Read,
    paging: Annotated[PageParams, Depends(page_params)],
    state: ProvisioningState | None = None,
) -> Page[TrackerDto]:
    svc = _svc(session, ctx)
    rows, total = paginate(session, svc.list_query(paging.q, state), paging)
    return Page(items=[svc.to_dto(t) for t in rows], total=total, page=paging.page, page_size=paging.page_size)


@router.get("/tenant/trackers/{tracker_id}", response_model=TrackerDto, operation_id="getTracker")
def get_tracker(tracker_id: uuid.UUID, session: DbSession, ctx: Read) -> TrackerDto:
    svc = _svc(session, ctx)
    return svc.to_dto(svc.tracker(tracker_id))


@router.post(
    "/tenant/trackers/{tracker_id}/assign",
    response_model=TrackerAssignmentDto,
    status_code=201,
    operation_id="assignTracker",
)
def assign(tracker_id: uuid.UUID, body: AssignTrackerIn, session: DbSession, ctx: Write) -> TrackerAssignmentDto:
    return _svc(session, ctx).assign(tracker_id, body)


@router.post("/tenant/trackers/{tracker_id}/unassign", response_model=TrackerDto, operation_id="unassignTracker")
def unassign(tracker_id: uuid.UUID, body: UnassignTrackerIn, session: DbSession, ctx: Write) -> TrackerDto:
    return _svc(session, ctx).unassign(tracker_id, body.effective_to, body.reason)


@router.post("/tenant/trackers/{tracker_id}/state", response_model=TrackerDto, operation_id="changeTrackerState")
def change_state(
    tracker_id: uuid.UUID,
    body: TrackerStateIn,
    session: DbSession,
    ctx: Write,
    now: Annotated[datetime, Depends(get_now)],
) -> TrackerDto:
    return _svc(session, ctx).change_state(tracker_id, body.state, body.reason, now)


@router.get(
    "/tenant/machines/{machine_id}/trackers",
    response_model=list[TrackerAssignmentDto],
    operation_id="listMachineTrackerAssignments",
)
def machine_trackers(machine_id: uuid.UUID, session: DbSession, ctx: Read) -> list[TrackerAssignmentDto]:
    return _svc(session, ctx).assignments_for_machine(machine_id)
