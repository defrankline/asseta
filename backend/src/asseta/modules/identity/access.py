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
from asseta.core.clock import get_now
from asseta.core.db import get_session, utcnow
from asseta.core.errors import ERROR_RESPONSES, BusinessRuleViolation, NotFound, PermissionDenied
from asseta.modules.accountability.security_events import permission_refused
from asseta.modules.identity.authz_sync import AuthzSyncService
from asseta.modules.identity.catalog import CATALOG, MenuDef
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.dependencies import requires
from asseta.modules.identity.idp import IdentityProviderAdmin
from asseta.modules.identity.models import AppUser, Role, RolePermission, TenantMembership
from asseta.modules.identity.principal import RequestContext
from asseta.modules.identity.role_templates import APPROVER_CONTROL_PERMISSIONS, ASSIGN_APPROVERS_PERMISSION
from asseta.modules.identity.tokens import tenant_group_path
from asseta.modules.managed_service.models import ManagedServiceMandate, MandateAssignment, MandateScope

ACCESS_READ = requires("tenant.access.read", S.TENANT, "View tenant users, roles and permissions")
ACCESS_MANAGE = requires("tenant.access.manage", S.TENANT, "Invite users and grant/revoke tenant roles")
# Checked inside the routes below because it depends on the role being assigned, so it is declared here.
CATALOG.register(ASSIGN_APPROVERS_PERMISSION, S.TENANT, "Give or remove roles that carry approvals")
CATALOG.register_menu(
    MenuDef(
        "tenant.access", S.TENANT, "Users & roles", "/tenant/access", 85, "tenant.access.read", group="tenant.admin"
    )
)
OWNER_ROLE = "owner"
APPROVER_ROLE_REFUSED = "Only the company owner can give someone a role that approves things."

router = APIRouter(prefix="/api/v1/tenant/access", tags=["tenant-access"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]
RoleKey = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9-]{1,63}$")]


class MemberRoleDto(BaseModel):
    role_key: str
    since: datetime
    mandate_reference: str | None = Field(default=None, description="Held by platform staff under this mandate")
    carries_approvals: bool = Field(description="Assigning or removing this role needs the approver-assignment right")


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


@router.get("/members", response_model=list[MemberDto], operation_id="listTenantMembers")
def members(session: DbSession, ctx: Annotated[RequestContext, Depends(ACCESS_READ)]) -> list[MemberDto]:
    rows = session.execute(
        select(AppUser, Role.key, TenantMembership.effective_from)
        .join(TenantMembership, TenantMembership.user_id == AppUser.id)
        .join(Role, Role.id == TenantMembership.role_id)
        .where(TenantMembership.tenant_id == ctx.tenant_id, TenantMembership.effective_to.is_(None))
        .order_by(AppUser.email)
    ).all()
    mandated = _mandated(session, ctx.tenant_id)
    approving = set(
        session.execute(
            select(Role.key)
            .join(RolePermission, RolePermission.role_id == Role.id)
            .where(Role.tenant_id == ctx.tenant_id, RolePermission.permission_code.in_(APPROVER_CONTROL_PERMISSIONS))
        ).scalars()
    )
    out: dict[uuid.UUID, MemberDto] = {}
    for user, key, since in rows:
        out.setdefault(
            user.id, MemberDto(user_id=user.id, email=user.email, display_name=user.display_name, roles=[])
        ).roles.append(
            MemberRoleDto(
                role_key=key,
                since=since,
                mandate_reference=mandated.get((user.id, key)),
                carries_approvals=key in approving,
            )
        )
    return list(out.values())


def _mandated(session: Session, tenant_id: uuid.UUID | None) -> dict[tuple[uuid.UUID, str], str]:
    """(user, role) pairs held under an active mandate assignment -> mandate reference."""
    rows = session.execute(
        select(MandateAssignment.user_id, MandateAssignment.role_key, ManagedServiceMandate.reference)
        .join(ManagedServiceMandate, ManagedServiceMandate.id == MandateAssignment.mandate_id)
        .where(MandateAssignment.tenant_id == tenant_id, MandateAssignment.is_active.is_(True))
    ).all()
    return {(u, k): ref for u, k, ref in rows}


def _may_assign_approvers(session: Session, ctx: RequestContext) -> bool:
    """Holding the permission is enough for a client's own people. Platform staff also need a mandate whose scope lets
    them administer the client's access: a role edited after they were assigned cannot extend an OPERATIONS mandate."""
    if ASSIGN_APPROVERS_PERMISSION not in ctx.permissions:
        return False
    if ctx.mandate_id is None:
        return True
    mandate = session.get(ManagedServiceMandate, ctx.mandate_id)
    return mandate is not None and MandateScope(mandate.scope) is MandateScope.FULL


def _require_approver_authority(
    session: Session, request: Request, ctx: RequestContext, role: Role, *, change: str, target: str, is_self: bool
) -> None:
    """A role that carries approvals is assigned or removed only by a holder of the permission. Run before any change
    at the identity provider; the refusal is kept as a security event."""
    codes = set(
        session.execute(select(RolePermission.permission_code).where(RolePermission.role_id == role.id)).scalars()
    )
    if not codes & APPROVER_CONTROL_PERMISSIONS or _may_assign_approvers(session, ctx):
        return
    permission_refused(
        ctx.tenant_id,
        ctx.user_id,
        ASSIGN_APPROVERS_PERMISSION,
        request.method,
        request.url.path,
        detail={
            "code": "APPROVER_ROLE_ASSIGN_FORBIDDEN",
            "change": change,
            "role": role.key,
            "target": target,
            "self": is_self,
        },
        occurred_at=get_now(request),
        actor_subject=ctx.subject,
    )
    raise PermissionDenied(APPROVER_ROLE_REFUSED, code="APPROVER_ROLE_ASSIGN_FORBIDDEN")


def _require_another_holder(
    session: Session,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    role: Role,
    mandated: dict[tuple[uuid.UUID, str], str],
) -> None:
    """Someone at the client must always be able to give approval roles; mandate staff never count."""
    holders = session.execute(
        select(TenantMembership.user_id, Role.key)
        .join(Role, Role.id == TenantMembership.role_id)
        .join(RolePermission, RolePermission.role_id == Role.id)
        .join(AppUser, AppUser.id == TenantMembership.user_id)
        .where(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.effective_to.is_(None),
            RolePermission.permission_code == ASSIGN_APPROVERS_PERMISSION,
            AppUser.is_active.is_(True),
        )
    ).all()
    keys = {key for _, key in holders}
    remaining = {u for u, k in holders if (u, k) not in mandated and (u, k) != (user_id, role.key)}
    if role.key in keys and not remaining:
        raise BusinessRuleViolation(
            "Give someone else this right before removing the last person who holds it", code="LAST_APPROVER_ASSIGNER"
        )


@router.post("/members", response_model=InviteResultDto, status_code=201, operation_id="inviteTenantMember")
def invite(
    body: InviteIn, request: Request, session: DbSession, ctx: Annotated[RequestContext, Depends(ACCESS_MANAGE)]
) -> InviteResultDto:
    assert ctx.tenant_id is not None
    idp = _idp(request)
    role = _role(session, ctx.tenant_id, body.role_key)
    subject, password = idp.find_user_by_email(str(body.email)), None
    _require_approver_authority(
        session, request, ctx, role, change="grant", target=str(body.email), is_self=subject == ctx.subject
    )
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
    mandated = _mandated(session, ctx.tenant_id)
    if (user_id, role_key) in mandated:
        raise BusinessRuleViolation(
            "This role is held under a managed-service mandate; revoke the mandate instead", code="MANDATE_MANAGED"
        )
    _require_approver_authority(
        session, request, ctx, role, change="revoke", target=str(user_id), is_self=user_id == ctx.user_id
    )
    if role_key == OWNER_ROLE:
        owners = session.execute(
            select(TenantMembership.user_id).where(
                TenantMembership.tenant_id == ctx.tenant_id,
                TenantMembership.role_id == role.id,
                TenantMembership.effective_to.is_(None),
            )
        ).scalars()
        # Mandate staff never count: the client must always keep an owner of its own.
        if len([u for u in owners if (u, OWNER_ROLE) not in mandated]) <= 1:
            raise BusinessRuleViolation("Cannot remove the last tenant owner", code="LAST_OWNER")
    _require_another_holder(session, ctx.tenant_id, user_id, role, mandated)
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
