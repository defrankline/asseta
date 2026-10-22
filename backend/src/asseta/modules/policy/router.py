"""Policy endpoints: platform defaults (platform scope) and tenant/machine/site overrides (tenant scope)."""

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from asseta.core.db import get_session
from asseta.core.errors import ERROR_RESPONSES, BusinessRuleViolation, NotFound
from asseta.modules.identity.catalog import CATALOG, MenuDef, PermissionScope
from asseta.modules.identity.dependencies import requires
from asseta.modules.identity.principal import RequestContext
from asseta.modules.policy.models import PolicyVersion
from asseta.modules.policy.schemas import PolicyScope, PolicyType
from asseta.modules.policy.service import PolicyService

POLICY_READ = requires("tenant.policy.read", PermissionScope.TENANT, "View effective operating policies")
POLICY_MANAGE = requires("tenant.policy.manage", PermissionScope.TENANT, "Version tenant/machine/site policies")
PLATFORM_POLICY = requires("platform.policy.manage", PermissionScope.PLATFORM, "Version platform default policies")
CATALOG.register_menu(
    MenuDef(
        "tenant.policies",
        PermissionScope.TENANT,
        "Policies",
        "/tenant/policies",
        80,
        "tenant.policy.read",
        group="tenant.admin",
    )
)

router = APIRouter(prefix="/api/v1", tags=["policy"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]


class PolicyVersionIn(BaseModel):
    scope: PolicyScope
    scope_ref_id: uuid.UUID | None = None
    values: dict[str, Any]
    effective_from: datetime | None = None
    reason: str = Field(min_length=3, max_length=1000)


class PolicyVersionDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    policy_type: PolicyType
    scope: PolicyScope
    scope_ref_id: uuid.UUID | None
    version: int
    effective_from: datetime
    values: dict[str, Any]
    reason: str
    created_at: datetime


class EffectivePolicyDto(BaseModel):
    policy_type: PolicyType
    version_stamp: str
    values: dict[str, Any]


@router.get("/tenant/policies/{ptype}/effective", response_model=EffectivePolicyDto, operation_id="getEffectivePolicy")
def effective(
    ptype: PolicyType,
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(POLICY_READ)],
    machine_id: uuid.UUID | None = None,
    site_id: uuid.UUID | None = None,
    at: datetime | None = None,
) -> EffectivePolicyDto:
    eff = PolicyService(session).resolve(ptype, ctx.tenant_id, machine_id=machine_id, site_id=site_id, at=at)
    return EffectivePolicyDto(policy_type=ptype, version_stamp=eff.version_stamp, values=eff.policy.model_dump())


@router.get(
    "/tenant/policies/{ptype}/versions", response_model=list[PolicyVersionDto], operation_id="listPolicyVersions"
)
def versions(
    ptype: PolicyType, session: DbSession, _: Annotated[RequestContext, Depends(POLICY_READ)]
) -> list[PolicyVersionDto]:
    rows = session.execute(
        select(PolicyVersion)
        .where(PolicyVersion.policy_type == ptype)
        .order_by(PolicyVersion.scope, PolicyVersion.effective_from.desc())
    ).scalars()
    return [PolicyVersionDto.model_validate(r) for r in rows]


@router.post(
    "/tenant/policies/{ptype}/versions",
    response_model=PolicyVersionDto,
    status_code=201,
    operation_id="createTenantPolicyVersion",
)
def create_tenant_version(
    ptype: PolicyType, body: PolicyVersionIn, session: DbSession, ctx: Annotated[RequestContext, Depends(POLICY_MANAGE)]
) -> PolicyVersionDto:
    if body.scope is PolicyScope.PLATFORM:
        raise BusinessRuleViolation("Tenants cannot change platform policies", code="POLICY_SCOPE")
    ref_sql = {
        PolicyScope.MACHINE: "SELECT 1 FROM machine WHERE id = :i",
        PolicyScope.SITE: "SELECT 1 FROM job_site WHERE id = :i",
    }.get(body.scope)
    if ref_sql and (
        body.scope_ref_id is None or session.execute(text(ref_sql), {"i": body.scope_ref_id}).first() is None
    ):
        ref_table = "machine" if body.scope is PolicyScope.MACHINE else "job_site"
        raise NotFound(f"{ref_table} not found")  # RLS-scoped: only the tenant's own records resolve
    row = PolicyService(session).create_version(
        ptype=ptype,
        scope=body.scope,
        tenant_id=ctx.tenant_id,
        scope_ref_id=body.scope_ref_id,
        values=body.values,
        effective_from=body.effective_from,
        reason=body.reason,
        actor=ctx.audit_actor(),
    )
    return PolicyVersionDto.model_validate(row)


@router.post(
    "/platform/policies/{ptype}/versions",
    response_model=PolicyVersionDto,
    status_code=201,
    operation_id="createPlatformPolicyVersion",
)
def create_platform_version(
    ptype: PolicyType,
    body: PolicyVersionIn,
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(PLATFORM_POLICY)],
) -> PolicyVersionDto:
    row = PolicyService(session).create_version(
        ptype=ptype,
        scope=PolicyScope.PLATFORM,
        tenant_id=None,
        scope_ref_id=None,
        values=body.values,
        effective_from=body.effective_from,
        reason=body.reason,
        actor=ctx.audit_actor(),
    )
    return PolicyVersionDto.model_validate(row)
