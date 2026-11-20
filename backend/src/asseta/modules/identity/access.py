"""Tenant user & role administration (R1-B). Keycloak remains authoritative: changes are made to Keycloak group
membership, then the effective-dated mirror is reconciled. Guards prevent locking the tenant out."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, EmailStr, Field, StringConstraints
from sqlalchemy import func, select
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


class MemberStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class MemberDto(BaseModel):
    user_id: uuid.UUID
    email: str
    display_name: str
    status: MemberStatus = Field(description="INACTIVE: deactivated here; `roles` are the roles they had then")
    roles: list[MemberRoleDto]
    deactivated_at: datetime | None = None


class MemberStatusFilter(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ALL = "ALL"


Name = Annotated[str, StringConstraints(min_length=1, max_length=100, strip_whitespace=True)]


class MemberNameIn(BaseModel):
    first_name: Name
    last_name: Name


class PasswordResetDto(BaseModel):
    temporary_password: str = Field(description="One-time password, shown once; changed at the next sign-in")


class InviteIn(BaseModel):
    email: EmailStr
    first_name: Name
    last_name: Name
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


class TenantRoleDto(BaseModel):
    role_key: str
    carries_approvals: bool = Field(description="Giving or removing it needs the approver-assignment right")


@router.get("/roles", response_model=list[TenantRoleDto], operation_id="listTenantRoles")
def roles(session: DbSession, ctx: Annotated[RequestContext, Depends(ACCESS_READ)]) -> list[TenantRoleDto]:
    """The company's roles, to give to people."""
    assert ctx.tenant_id is not None
    approving = _approving_roles(session, ctx.tenant_id)
    keys = session.execute(select(Role.key).where(Role.tenant_id == ctx.tenant_id).order_by(Role.key)).scalars()
    return [TenantRoleDto(role_key=k, carries_approvals=k in approving) for k in keys]


@router.get("/members", response_model=list[MemberDto], operation_id="listTenantMembers")
def members(
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(ACCESS_READ)],
    status: Annotated[MemberStatusFilter, Query()] = MemberStatusFilter.ACTIVE,
) -> list[MemberDto]:
    """ACTIVE: people with a role here now. INACTIVE: people deactivated here (no role now), with the roles they had
    when they were deactivated."""
    assert ctx.tenant_id is not None
    rows = session.execute(
        select(AppUser, Role.key, TenantMembership.effective_from, TenantMembership.effective_to)
        .join(TenantMembership, TenantMembership.user_id == AppUser.id)
        .join(Role, Role.id == TenantMembership.role_id)
        .where(TenantMembership.tenant_id == ctx.tenant_id, AppUser.deleted_at.is_(None))
        .order_by(AppUser.email, Role.key)
    ).all()
    mandated = _mandated(session, ctx.tenant_id)
    approving = _approving_roles(session, ctx.tenant_id)
    by_user: dict[uuid.UUID, tuple[AppUser, list[tuple[str, datetime, datetime | None]]]] = {}
    for user, key, since, until in rows:
        by_user.setdefault(user.id, (user, []))[1].append((key, since, until))
    out: list[MemberDto] = []
    for user, held in by_user.values():
        open_roles = [(k, f) for k, f, t in held if t is None]
        if open_roles:
            if status is MemberStatusFilter.INACTIVE:
                continue
            chosen, member_status, ended = open_roles, MemberStatus.ACTIVE, None
        else:
            if status is MemberStatusFilter.ACTIVE:
                continue
            ended = max(t for _, _, t in held if t is not None)
            chosen = [(k, f) for k, f, t in held if t == ended]
            member_status = MemberStatus.INACTIVE
        roles: dict[str, MemberRoleDto] = {}
        for key, since in chosen:
            roles.setdefault(
                key,
                MemberRoleDto(
                    role_key=key,
                    since=since,
                    mandate_reference=mandated.get((user.id, key)),
                    carries_approvals=key in approving,
                ),
            )
        out.append(
            MemberDto(
                user_id=user.id,
                email=user.email,
                display_name=user.display_name,
                status=member_status,
                roles=list(roles.values()),
                deactivated_at=ended,
            )
        )
    return out


def _approving_roles(session: Session, tenant_id: uuid.UUID) -> set[str]:
    return set(
        session.execute(
            select(Role.key)
            .join(RolePermission, RolePermission.role_id == Role.id)
            .where(Role.tenant_id == tenant_id, RolePermission.permission_code.in_(APPROVER_CONTROL_PERMISSIONS))
        ).scalars()
    )


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
    if subject is not None and _only_here(idp, subject, ctx.tenant_id):
        # Someone deactivated here (their sign-in was disabled) comes back with the role given now.
        idp.enable_user(subject)
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
    _require_owner_left(session, ctx.tenant_id, role, mandated)
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


def _require_owner_left(
    session: Session, tenant_id: uuid.UUID, role: Role, mandated: dict[tuple[uuid.UUID, str], str]
) -> None:
    """Removing the owner role from someone who holds it: the client must keep an owner of its own (mandate staff
    never count)."""
    if role.key != OWNER_ROLE:
        return
    owners = session.execute(
        select(TenantMembership.user_id).where(
            TenantMembership.tenant_id == tenant_id,
            TenantMembership.role_id == role.id,
            TenantMembership.effective_to.is_(None),
        )
    ).scalars()
    if len([u for u in owners if (u, OWNER_ROLE) not in mandated]) <= 1:
        raise BusinessRuleViolation("Cannot remove the last tenant owner", code="LAST_OWNER")


ELSEWHERE_REFUSED = (
    "This person also uses Asseta elsewhere, so their sign-in can't be changed from here; "
    "ask them to use Forgot password."
)
SELF_REFUSED = "You can't do this to your own account here; use Forgot password or ask another owner."


def _member(session: Session, tenant_id: uuid.UUID, user_id: uuid.UUID) -> AppUser:
    """Someone who has (or had) a role in this company; never a deleted account."""
    user = session.get(AppUser, user_id)
    held = session.execute(
        select(func.count())
        .select_from(TenantMembership)
        .where(TenantMembership.tenant_id == tenant_id, TenantMembership.user_id == user_id)
    ).scalar_one()
    if user is None or user.deleted_at is not None or held == 0:
        raise NotFound("User not found in this company")
    return user


def _open_roles(session: Session, tenant_id: uuid.UUID, user_id: uuid.UUID) -> list[Role]:
    return list(
        session.execute(
            select(Role)
            .join(TenantMembership, TenantMembership.role_id == Role.id)
            .where(
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.user_id == user_id,
                TenantMembership.effective_to.is_(None),
            )
            .order_by(Role.key)
        )
        .scalars()
        .unique()
    )


def _only_here(idp: IdentityProviderAdmin, subject: str, tenant_id: uuid.UUID) -> bool:
    """The account belongs to this company alone (no other company, no platform role), so this company may change
    its name, password and whether it can sign in. Asked of Keycloak, which sees every company."""
    prefix = f"/tenants/{tenant_id}/"
    return all(p.startswith(prefix) for p in idp.user_group_paths(subject))


def _require_only_here(idp: IdentityProviderAdmin, user: AppUser, tenant_id: uuid.UUID) -> None:
    if not _only_here(idp, user.keycloak_subject, tenant_id):
        raise BusinessRuleViolation(ELSEWHERE_REFUSED, code="ACCOUNT_USED_ELSEWHERE")


def _require_not_self(ctx: RequestContext, user_id: uuid.UUID) -> None:
    if user_id == ctx.user_id:
        raise BusinessRuleViolation(SELF_REFUSED, code="SELF_NOT_ALLOWED")


@router.post("/members/{user_id}/roles/{role_key}", response_model=list[MemberDto], operation_id="grantTenantRole")
def grant(
    user_id: uuid.UUID,
    role_key: RoleKey,
    request: Request,
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(ACCESS_MANAGE)],
) -> list[MemberDto]:
    """Gives an active member another role (to bring back a deactivated person, use reactivate)."""
    assert ctx.tenant_id is not None
    user = _member(session, ctx.tenant_id, user_id)
    if not _open_roles(session, ctx.tenant_id, user_id):
        raise BusinessRuleViolation("Reactivate this person first", code="MEMBER_INACTIVE")
    role = _role(session, ctx.tenant_id, role_key)
    _require_approver_authority(
        session, request, ctx, role, change="grant", target=str(user_id), is_self=user_id == ctx.user_id
    )
    idp = _idp(request)
    idp.add_user_to_group(user.keycloak_subject, role.keycloak_group_id)
    AuthzSyncService(idp).pull_role_mirror(session, only_tenant=ctx.tenant_id)
    AuditService(session).record(
        actor=ctx.audit_actor(),
        action="tenant.access.role_granted",
        entity_type="app_user",
        entity_id=user_id,
        tenant_id=ctx.tenant_id,
        after={"role": role_key, "created_account": False},
    )
    return members(session, ctx)


@router.put("/members/{user_id}/name", response_model=list[MemberDto], operation_id="renameTenantMember")
def rename(
    user_id: uuid.UUID,
    body: MemberNameIn,
    request: Request,
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(ACCESS_MANAGE)],
) -> list[MemberDto]:
    """Corrects a person's name. Only for an account that belongs to this company alone."""
    assert ctx.tenant_id is not None
    user = _member(session, ctx.tenant_id, user_id)
    idp = _idp(request)
    _require_only_here(idp, user, ctx.tenant_id)
    before = user.display_name
    idp.update_user_name(user.keycloak_subject, body.first_name, body.last_name)
    user.display_name = f"{body.first_name} {body.last_name}"
    AuditService(session).record(
        actor=ctx.audit_actor(),
        action="tenant.access.member_renamed",
        entity_type="app_user",
        entity_id=user_id,
        tenant_id=ctx.tenant_id,
        before={"display_name": before},
        after={"display_name": user.display_name},
    )
    session.flush()
    return members(session, ctx, MemberStatusFilter.ALL)


@router.post("/members/{user_id}/deactivate", response_model=list[MemberDto], operation_id="deactivateTenantMember")
def deactivate(
    user_id: uuid.UUID,
    request: Request,
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(ACCESS_MANAGE)],
) -> list[MemberDto]:
    """Removes all the person's roles here; their records stay. An account that belongs to this company alone is
    also disabled and signed out everywhere (apps included). Reactivate brings the same roles back."""
    assert ctx.tenant_id is not None
    _require_not_self(ctx, user_id)
    user = _member(session, ctx.tenant_id, user_id)
    roles = _open_roles(session, ctx.tenant_id, user_id)
    if not roles:
        raise BusinessRuleViolation("This person is already inactive", code="MEMBER_INACTIVE")
    mandated = _mandated(session, ctx.tenant_id)
    if any((user_id, r.key) in mandated for r in roles):
        raise BusinessRuleViolation(
            "This person holds a role under a managed-service mandate; end the mandate instead", code="MANDATE_MANAGED"
        )
    for role in roles:
        _require_approver_authority(session, request, ctx, role, change="revoke", target=str(user_id), is_self=False)
        _require_owner_left(session, ctx.tenant_id, role, mandated)
        _require_another_holder(session, ctx.tenant_id, user_id, role, mandated)
    idp = _idp(request)
    only_here = _only_here(idp, user.keycloak_subject, ctx.tenant_id)
    for role in roles:
        idp.remove_user_from_group(user.keycloak_subject, role.keycloak_group_id)
    if only_here:
        idp.disable_user(user.keycloak_subject)
        idp.logout_user(user.keycloak_subject)
    AuthzSyncService(idp).pull_role_mirror(session, only_tenant=ctx.tenant_id)
    AuditService(session).record(
        actor=ctx.audit_actor(),
        action="tenant.access.member_deactivated",
        entity_type="app_user",
        entity_id=user_id,
        tenant_id=ctx.tenant_id,
        before={"roles": [r.key for r in roles]},
        after={"roles": [], "sign_in_disabled": only_here},
    )
    return members(session, ctx, MemberStatusFilter.ALL)


@router.post("/members/{user_id}/reactivate", response_model=list[MemberDto], operation_id="reactivateTenantMember")
def reactivate(
    user_id: uuid.UUID,
    request: Request,
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(ACCESS_MANAGE)],
) -> list[MemberDto]:
    """Gives a deactivated person back the roles they had when they were deactivated."""
    assert ctx.tenant_id is not None
    user = _member(session, ctx.tenant_id, user_id)
    if _open_roles(session, ctx.tenant_id, user_id):
        raise BusinessRuleViolation("This person is already active", code="MEMBER_ACTIVE")
    ended = session.execute(
        select(func.max(TenantMembership.effective_to)).where(
            TenantMembership.tenant_id == ctx.tenant_id, TenantMembership.user_id == user_id
        )
    ).scalar_one()
    roles = list(
        session.execute(
            select(Role)
            .join(TenantMembership, TenantMembership.role_id == Role.id)
            .where(
                TenantMembership.tenant_id == ctx.tenant_id,
                TenantMembership.user_id == user_id,
                TenantMembership.effective_to == ended,
            )
            .order_by(Role.key)
        )
        .scalars()
        .unique()
    )
    for role in roles:
        _require_approver_authority(session, request, ctx, role, change="grant", target=str(user_id), is_self=False)
    idp = _idp(request)
    if _only_here(idp, user.keycloak_subject, ctx.tenant_id):
        idp.enable_user(user.keycloak_subject)
    for role in roles:
        idp.add_user_to_group(user.keycloak_subject, role.keycloak_group_id)
    AuthzSyncService(idp).pull_role_mirror(session, only_tenant=ctx.tenant_id)
    AuditService(session).record(
        actor=ctx.audit_actor(),
        action="tenant.access.member_reactivated",
        entity_type="app_user",
        entity_id=user_id,
        tenant_id=ctx.tenant_id,
        after={"roles": [r.key for r in roles]},
    )
    return members(session, ctx, MemberStatusFilter.ALL)


@router.post(
    "/members/{user_id}/reset-password", response_model=PasswordResetDto, operation_id="resetTenantMemberPassword"
)
def reset_password(
    user_id: uuid.UUID,
    request: Request,
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(ACCESS_MANAGE)],
) -> PasswordResetDto:
    """A new one-time password, shown once; the person is signed out everywhere and sets their own password at the
    next sign-in. Only for an active account that belongs to this company alone, never one's own."""
    assert ctx.tenant_id is not None
    _require_not_self(ctx, user_id)
    user = _member(session, ctx.tenant_id, user_id)
    if not _open_roles(session, ctx.tenant_id, user_id):
        raise BusinessRuleViolation("Reactivate this person first", code="MEMBER_INACTIVE")
    idp = _idp(request)
    _require_only_here(idp, user, ctx.tenant_id)
    password = idp.reset_password(user.keycloak_subject)
    idp.logout_user(user.keycloak_subject)
    AuditService(session).record(
        actor=ctx.audit_actor(),
        action="tenant.access.password_reset",
        entity_type="app_user",
        entity_id=user_id,
        tenant_id=ctx.tenant_id,
        after={"signed_out": True},
    )
    return PasswordResetDto(temporary_password=password)
