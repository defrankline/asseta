import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.db import get_session
from asseta.core.errors import ERROR_RESPONSES, NotFound
from asseta.core.idempotency import IdempotencyGuard, request_hash
from asseta.core.paging import Page, PageParams, page_params, paginate
from asseta.core.search import ilike_any
from asseta.modules.identity.principal import RequestContext
from asseta.modules.platform_billing import permissions as P
from asseta.modules.tenancy.dto import OnboardResultDto, TenantDto, TenantOnboardIn, TenantUpdateIn, VerificationIn
from asseta.modules.tenancy.models import Tenant
from asseta.modules.tenancy.service import TenantOnboardingService

router = APIRouter(prefix="/api/v1/platform/tenants", tags=["platform-tenants"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]


@router.post("", response_model=OnboardResultDto, status_code=201, operation_id="onboardTenant")
def onboard(
    body: TenantOnboardIn,
    request: Request,
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(P.TENANT_CREATE)],
    idempotency_key: Annotated[str | None, Header()] = None,
) -> OnboardResultDto:
    guard = IdempotencyGuard(session, "platform", "onboardTenant", idempotency_key, request_hash(body))
    if (replay := guard.begin()) is not None:
        return OnboardResultDto.model_validate(replay)
    result = TenantOnboardingService(session, ctx.audit_actor(), request.app.state.idp_admin).onboard(body)
    # Never persist the temporary password in the idempotency store.
    guard.complete(result.model_copy(update={"owner_temporary_password": "<redacted: shown once>"}), 201)
    return result


@router.get("", response_model=Page[TenantDto], operation_id="listTenants")
def list_tenants(
    session: DbSession,
    _: Annotated[RequestContext, Depends(P.TENANT_READ)],
    paging: Annotated[PageParams, Depends(page_params)],
) -> Page[TenantDto]:
    stmt = select(Tenant)
    if (match := ilike_any(paging.q, Tenant.legal_name, Tenant.display_name)) is not None:
        stmt = stmt.where(match)
    sort_col = {"name": Tenant.display_name, "created_at": Tenant.created_at}.get(
        (paging.sort or "-created_at").lstrip("-"), Tenant.created_at
    )
    stmt = stmt.order_by(sort_col.desc() if (paging.sort or "-").startswith("-") else sort_col.asc())
    rows, total = paginate(session, stmt, paging)
    return Page(
        items=[TenantDto.model_validate(t) for t in rows], total=total, page=paging.page, page_size=paging.page_size
    )


@router.get("/{tenant_id}", response_model=TenantDto, operation_id="getTenant")
def get_tenant(
    tenant_id: uuid.UUID, session: DbSession, _: Annotated[RequestContext, Depends(P.TENANT_READ)]
) -> TenantDto:
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise NotFound("Tenant not found")
    return TenantDto.model_validate(tenant)


@router.put("/{tenant_id}", response_model=TenantDto, operation_id="updateTenant")
def update_tenant(
    tenant_id: uuid.UUID,
    body: TenantUpdateIn,
    request: Request,
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(P.TENANT_UPDATE)],
) -> TenantDto:
    """Edit company details (optimistic `version`). Currency/timezone are not editable after onboarding."""
    return TenantOnboardingService(session, ctx.audit_actor(), request.app.state.idp_admin).update(tenant_id, body)


@router.post("/{tenant_id}/verification", response_model=TenantDto, operation_id="verifyTenant")
def verify(
    tenant_id: uuid.UUID,
    body: VerificationIn,
    request: Request,
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(P.TENANT_VERIFY)],
) -> TenantDto:
    return TenantOnboardingService(session, ctx.audit_actor(), request.app.state.idp_admin).verify(tenant_id, body)
