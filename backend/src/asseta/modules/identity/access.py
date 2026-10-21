"""Tenant user & role administration (R1-B). Keycloak remains authoritative: changes are made to Keycloak group
membership, then the effective-dated mirror is reconciled. Guards prevent locking the tenant out."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, EmailStr, Field, StringConstraints
from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.db import get_session, utcnow
from asseta.core.errors import ERROR_RESPONSES, BusinessRuleViolation, NotFound
from asseta.modules.identity.authz_sync import AuthzSyncService
from asseta.modules.identity.catalog import CATALOG, MenuDef
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.dependencies import requires
from asseta.modules.identity.idp import IdentityProviderAdmin
from asseta.modules.identity.models import AppUser, Role, RolePermission, TenantMembership
from asseta.modules.identity.principal import RequestContext
from asseta.modules.identity.tokens import tenant_group_path

ACCESS_READ = requires("tenant.access.read", S.TENANT, "View tenant users, roles and permissions")
ACCESS_MANAGE = requires("tenant.access.manage", S.TENANT, "Invite users and grant/revoke tenant roles")
CATALOG.register_menu(MenuDef("tenant.access", S.TENANT, "Users & roles", "/tenant/access", 85, "tenant.access.read"))
OWNER_ROLE = "owner"

router = APIRouter(prefix="/api/v1/tenant/access", tags=["tenant-access"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]
RoleKey = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9-]{1,63}$")]


class RoleDto(BaseModel):
    key: str
    permissions: list[str]


class MemberRoleDto(BaseModel):
    role_key: str
    since: datetime


class MemberDto(BaseModel):
    user_id: uuid.UUID
    email: str
    display_name: str
    roles: list[MemberRoleDto]


class InviteIn(BaseModel):
    email: EmailStr
    first_name: Annotated[str, StringConstraints(min_length=1, max_length=100, strip_whitespace=True)]
    last_name: Annotated[str, StringConstraints(min_length=1, max_length=100, strip_whitespace=True)]
    role_key: RoleKey


class InviteResultDto(BaseModel):
    user_id: uuid.UUID
    created_account: bool
    temporary_password: str | None = Field(default=None, description="Only when a new account was created; shown once")


def _idp(request: Request) -> IdentityProviderAdmin:
    idp: IdentityProviderAdmin = request.app.state.idp_admin
    return idp


def _role(session: Session, tenant_id: uuid.UUID, key: str) -> Role:
    role = session.execute(
        select(Role).where(Role.keycloak_group_path == tenant_group_path(tenant_id, key))
    ).scalar_one_or_none()
    if role is None:
        raise NotFound(f"Role '{key}' not found")
    return role


@router.get("/roles", response_model=list[RoleDto], operation_id="listTenantRoles")
def roles(session: DbSession, ctx: Annotated[RequestContext, Depends(ACCESS_READ)]) -> list[RoleDto]:
    rows = session.execute(select(Role).where(Role.tenant_id == ctx.tenant_id).order_by(Role.key)).scalars()
    return [
        RoleDto(
            key=r.key,
            permissions=sorted(
                session.execute(select(RolePermission.permission_code).where(RolePermission.role_id == r.id)).scalars()
            ),
        )
        for r in rows
    ]


@router.get("/members", response_model=list[MemberDto], operation_id="listTenantMembers")
def members(session: DbSession, ctx: Annotated[RequestContext, Depends(ACCESS_READ)]) -> list[MemberDto]:
    rows = session.execute(
        select(AppUser, Role.key, TenantMembership.effective_from)
        .join(TenantMembership, TenantMembership.user_id == AppUser.id)
        .join(Role, Role.id == TenantMembership.role_id)
        .where(TenantMembership.tenant_id == ctx.tenant_id, TenantMembership.effective_to.is_(None))
        .order_by(AppUser.email)
    ).all()
    out: dict[uuid.UUID, MemberDto] = {}
    for user, key, since in rows:
        out.setdefault(
            user.id, MemberDto(user_id=user.id, email=user.email, display_name=user.display_name, roles=[])
        ).roles.append(MemberRoleDto(role_key=key, since=since))
    return list(out.values())


@router.post("/members", response_model=InviteResultDto, status_code=201, operation_id="inviteTenantMember")
def invite(
    body: InviteIn, request: Request, session: DbSession, ctx: Annotated[RequestContext, Depends(ACCESS_MANAGE)]
) -> InviteResultDto:
    assert ctx.tenant_id is not None
    idp = _idp(request)
    role = _role(session, ctx.tenant_id, body.role_key)
    subject, password = idp.find_user_by_email(str(body.email)), None
    if subject is None:
        created = idp.create_user(str(body.email), body.first_name, body.last_name)
        subject, password = created.subject, created.temporary_password
    idp.add_user_to_group(subject, role.keycloak_group_id)
    AuthzSyncService(idp).pull_role_mirror(session, only_tenant=ctx.tenant_id)
    user = session.execute(select(AppUser).where(AppUser.keycloak_subject == subject)).scalar_one()
    AuditService(session).record(
        actor=ctx.audit_actor(),
        action="tenant.access.role_granted",
        entity_type="app_user",
        entity_id=user.id,
        tenant_id=ctx.tenant_id,
        after={"role": body.role_key, "created_account": password is not None},
    )
    return InviteResultDto(user_id=user.id, created_account=password is not None, temporary_password=password)


@router.post(
    "/members/{user_id}/roles/{role_key}/revoke", response_model=list[MemberDto], operation_id="revokeTenantRole"
)
def revoke(
    user_id: uuid.UUID,
    role_key: RoleKey,
    request: Request,
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(ACCESS_MANAGE)],
) -> list[MemberDto]:
    assert ctx.tenant_id is not None
    role = _role(session, ctx.tenant_id, role_key)
    membership = session.execute(
        select(TenantMembership).where(
            TenantMembership.tenant_id == ctx.tenant_id,
            TenantMembership.user_id == user_id,
            TenantMembership.role_id == role.id,
            TenantMembership.effective_to.is_(None),
        )
    ).scalar_one_or_none()
    if membership is None:
        raise NotFound("Active role membership not found")
    if role_key == OWNER_ROLE:
        owners = session.execute(
            select(TenantMembership.id).where(
                TenantMembership.tenant_id == ctx.tenant_id,
                TenantMembership.role_id == role.id,
                TenantMembership.effective_to.is_(None),
            )
        ).all()
        if len(owners) <= 1:
            raise BusinessRuleViolation("Cannot remove the last tenant owner", code="LAST_OWNER")
    user = session.get(AppUser, user_id)
    assert user is not None
    idp = _idp(request)
    idp.remove_user_from_group(user.keycloak_subject, role.keycloak_group_id)
    AuthzSyncService(idp).pull_role_mirror(session, only_tenant=ctx.tenant_id)
    AuditService(session).record(
        actor=ctx.audit_actor(),
        action="tenant.access.role_revoked",
        entity_type="app_user",
        entity_id=user_id,
        tenant_id=ctx.tenant_id,
        after={"role": role_key},
        reason=f"revoked at {utcnow().isoformat()}",
    )
    return members(session, ctx)
