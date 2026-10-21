"""Managed-service routes: the platform grants, staffs and ends mandates; the client sees and revokes them."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from asseta.core.clock import get_today
from asseta.core.db import get_session
from asseta.core.errors import ERROR_RESPONSES, NotFound, PermissionDenied
from asseta.core.idempotency import IdempotencyGuard, request_hash
from asseta.modules.identity.catalog import CATALOG, MenuDef
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.dependencies import requires
from asseta.modules.identity.principal import RequestContext
from asseta.modules.managed_service.dto import (
    AssignableRoleDto,
    ClientMandateDto,
    MandateAssignmentIn,
    MandateCloseIn,
    MandateDetailDto,
    MandateDto,
    MandateGrantIn,
    PlatformStaffDto,
)
from asseta.modules.managed_service.service import ManagedService

MANDATE_READ = requires("platform.mandate.read", S.PLATFORM, "View managed-service mandates")
MANDATE_MANAGE = requires("platform.mandate.manage", S.PLATFORM, "Grant, staff and end managed-service mandates")
CLIENT_READ = requires("tenant.managed_service.read", S.TENANT, "View the managed-service mandate and its staff")
CLIENT_REVOKE = requires("tenant.managed_service.revoke", S.TENANT, "Revoke the managed-service mandate")
CATALOG.register_menu(
    MenuDef(
        "platform.managed_service",
        S.PLATFORM,
        "Managed service",
        "/platform/managed-service",
        25,
        "platform.mandate.read",
    )
)
CATALOG.register_menu(
    MenuDef(
        "tenant.managed_service",
        S.TENANT,
        "Managed service",
        "/tenant/managed-service",
        95,
        "tenant.managed_service.read",
    )
)

router = APIRouter(prefix="/api/v1", tags=["managed-service"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]


def _svc(session: Session, ctx: RequestContext, request: Request) -> ManagedService:
    return ManagedService(session, ctx.audit_actor(), request.app.state.idp_admin, get_today(request))


@router.get("/platform/mandates", response_model=list[MandateDto], operation_id="listMandates")
def list_mandates(
    request: Request, session: DbSession, ctx: Annotated[RequestContext, Depends(MANDATE_READ)]
) -> list[MandateDto]:
    return _svc(session, ctx, request).list_all()


@router.post("/platform/mandates", response_model=MandateDetailDto, status_code=201, operation_id="grantMandate")
def grant_mandate(
    body: MandateGrantIn,
    request: Request,
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(MANDATE_MANAGE)],
    idempotency_key: Annotated[str | None, Header()] = None,
) -> MandateDetailDto:
    guard = IdempotencyGuard(session, "platform", "grantMandate", idempotency_key, request_hash(body))
    if (replay := guard.begin()) is not None:
        return MandateDetailDto.model_validate(replay)
    svc = _svc(session, ctx, request)
    dto = svc.detail(svc.grant(body))
    guard.complete(dto, 201)
    return dto


@router.get("/platform/mandates/staff", response_model=list[PlatformStaffDto], operation_id="listPlatformStaff")
def platform_staff(
    request: Request, session: DbSession, ctx: Annotated[RequestContext, Depends(MANDATE_MANAGE)]
) -> list[PlatformStaffDto]:
    return _svc(session, ctx, request).platform_staff()


@router.get("/platform/mandates/{mandate_id}", response_model=MandateDetailDto, operation_id="getMandate")
def get_mandate(
    mandate_id: uuid.UUID, request: Request, session: DbSession, ctx: Annotated[RequestContext, Depends(MANDATE_READ)]
) -> MandateDetailDto:
    svc = _svc(session, ctx, request)
    return svc.detail(svc.get(mandate_id))


@router.get(
    "/platform/mandates/{mandate_id}/roles", response_model=list[AssignableRoleDto], operation_id="listMandateRoles"
)
def mandate_roles(
    mandate_id: uuid.UUID, request: Request, session: DbSession, ctx: Annotated[RequestContext, Depends(MANDATE_MANAGE)]
) -> list[AssignableRoleDto]:
    svc = _svc(session, ctx, request)
    return svc.assignable_roles(svc.get(mandate_id))


@router.post(
    "/platform/mandates/{mandate_id}/assignments", response_model=MandateDetailDto, operation_id="assignMandateStaff"
)
def assign_staff(
    mandate_id: uuid.UUID,
    body: MandateAssignmentIn,
    request: Request,
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(MANDATE_MANAGE)],
) -> MandateDetailDto:
    svc = _svc(session, ctx, request)
    mandate = svc.get(mandate_id)
    svc.assign(mandate, body)
    return svc.detail(mandate)


@router.post(
    "/platform/mandates/{mandate_id}/assignments/{assignment_id}/remove",
    response_model=MandateDetailDto,
    operation_id="removeMandateStaff",
)
def remove_staff(
    mandate_id: uuid.UUID,
    assignment_id: uuid.UUID,
    request: Request,
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(MANDATE_MANAGE)],
) -> MandateDetailDto:
    svc = _svc(session, ctx, request)
    mandate = svc.get(mandate_id)
    svc.unassign(mandate, assignment_id)
    return svc.detail(mandate)


@router.post("/platform/mandates/{mandate_id}/end", response_model=MandateDetailDto, operation_id="endMandate")
def end_mandate(
    mandate_id: uuid.UUID,
    body: MandateCloseIn,
    request: Request,
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(MANDATE_MANAGE)],
) -> MandateDetailDto:
    svc = _svc(session, ctx, request)
    mandate = svc.get(mandate_id)
    svc.end(mandate, body)
    return svc.detail(mandate)


@router.get("/tenant/managed-service", response_model=ClientMandateDto, operation_id="getClientMandate")
def client_mandate(
    request: Request, session: DbSession, ctx: Annotated[RequestContext, Depends(CLIENT_READ)]
) -> ClientMandateDto:
    assert ctx.tenant_id is not None
    return _svc(session, ctx, request).client_view(ctx.tenant_id)


@router.post(
    "/tenant/managed-service/{mandate_id}/revoke", response_model=ClientMandateDto, operation_id="revokeClientMandate"
)
def revoke_mandate(
    mandate_id: uuid.UUID,
    body: MandateCloseIn,
    request: Request,
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(CLIENT_REVOKE)],
) -> ClientMandateDto:
    assert ctx.tenant_id is not None
    if ctx.mandate_id is not None:
        raise PermissionDenied("Staff acting under a mandate cannot revoke it", code="MANDATE_SELF_REVOKE")
    svc = _svc(session, ctx, request)
    mandate = svc.get(mandate_id)  # RLS: only this tenant's mandates are visible here
    if mandate.tenant_id != ctx.tenant_id:
        raise NotFound("Mandate not found")
    svc.revoke(mandate, body)
    return svc.client_view(ctx.tenant_id)
