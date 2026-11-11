"""Personal account deletion (any signed-in user, from the web or the phone apps): `POST /api/v1/me/account-deletion`.

The Keycloak login is disabled and then deleted, every open tenant membership is closed, and the person's app-user row
is anonymised to "Former user <short id>" (name and email; their notification phone number is cleared, their push
registrations switched off and their phones' sync sessions revoked so the apps wipe their local data). Records the
person created stay, attributed to that anonymised row, for each company's audit trail. A staff record linked to the
login keeps the person's role history but loses its contact phone. Refused for the last owner of a company (close the
company instead) and for platform staff (closed through a platform process). Each company's user managers are
notified; every step is audited.

`anonymise_user` is also used by the company deletion for the accounts it deletes."""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from asseta.core.audit import AuditActor, AuditService
from asseta.core.clock import get_now
from asseta.core.db import DbScope, apply_scope, get_session
from asseta.core.errors import ERROR_RESPONSES, BusinessRuleViolation, PermissionDenied
from asseta.core.outbox import OutboxWriter
from asseta.modules.fleet.models import StaffMember
from asseta.modules.identity.dependencies import get_claims, is_platform_staff
from asseta.modules.identity.idp import IdentityProviderAdmin
from asseta.modules.identity.models import AppUser, PlatformMembership, Role, TenantMembership
from asseta.modules.identity.principal import TokenClaims
from asseta.modules.identity.repository import IdentityRepository
from asseta.modules.managed_service.models import MandateAssignment
from asseta.modules.notification.channel_models import DeviceDeactivation, PushDevice
from asseta.modules.notification.models import NotificationProfile
from asseta.modules.sync.models import DeviceSession, DeviceStatus
from asseta.modules.tenancy.models import Tenant, TenantStatus

OWNER_ROLE = "owner"
TOPIC = "asseta.identity.account"
# Answered to the phone's next sync call: wipe local data (the account no longer exists).
ACCOUNT_DELETED_REVOKE_REASON = "ACCOUNT_DELETED: the account was deleted; local data is wiped"

router = APIRouter(prefix="/api/v1/me", tags=["identity"], responses=ERROR_RESPONSES)


class AccountDeletionIn(BaseModel):
    confirm: Literal[True] = Field(description="Must be true: the person confirms the account is deleted for good")
    reason: Annotated[str, StringConstraints(max_length=1000, strip_whitespace=True)] | None = None


class AccountDeletionDto(BaseModel):
    user_id: uuid.UUID
    display_name: str = Field(description="The anonymised name the person's records now show")
    deleted_at: datetime
    companies: list[str] = Field(description="Companies whose membership was closed")


def anonymised_name(user_id: uuid.UUID) -> str:
    return f"Former user {user_id.hex[:8]}"


def anonymise_user(session: Session, user: AppUser, now: datetime, revoked_by: uuid.UUID | None) -> None:
    """Personal fields gone for good (the row stays: records the person made point at it). Needs the SYSTEM scope."""
    user.display_name = anonymised_name(user.id)
    user.email = f"former-user-{user.id.hex[:8]}@deleted.invalid"  # never deliverable (RFC 6761 .invalid)
    user.is_active = False
    user.deleted_at = user.deleted_at or now
    session.execute(update(NotificationProfile).where(NotificationProfile.user_id == user.id).values(msisdn=None))
    session.execute(
        update(PushDevice)
        .where(PushDevice.user_id == user.id, PushDevice.deactivated_at.is_(None))
        .values(deactivated_at=now, deactivation_reason=DeviceDeactivation.USER, updated_at=now)
    )
    session.execute(
        update(DeviceSession)
        .where(DeviceSession.user_id == user.id, DeviceSession.status == DeviceStatus.ACTIVE)
        .values(
            status=DeviceStatus.REVOKED,
            revoked_at=now,
            revoked_by=revoked_by,
            revoke_reason=ACCOUNT_DELETED_REVOKE_REASON,
        )
    )
    session.flush()


def _idp(request: Request) -> IdentityProviderAdmin:
    idp: IdentityProviderAdmin = request.app.state.idp_admin
    return idp


def _owned_alone(session: Session, user_id: uuid.UUID) -> list[str]:
    """Companies (not closed) where this user is the only owner of their own (mandate staff never count)."""
    mine = session.execute(
        select(TenantMembership.tenant_id)
        .join(Role, Role.id == TenantMembership.role_id)
        .where(TenantMembership.user_id == user_id, TenantMembership.effective_to.is_(None), Role.key == OWNER_ROLE)
    ).scalars()
    alone: list[str] = []
    for tenant_id in set(mine):
        tenant = session.get(Tenant, tenant_id)
        if tenant is None or tenant.status is TenantStatus.CLOSED:
            continue
        others = session.execute(
            select(TenantMembership.user_id)
            .join(Role, Role.id == TenantMembership.role_id)
            .join(AppUser, AppUser.id == TenantMembership.user_id)
            .where(
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.effective_to.is_(None),
                Role.key == OWNER_ROLE,
                TenantMembership.user_id != user_id,
                AppUser.is_active.is_(True),
            )
        ).scalars()
        mandated = set(
            session.execute(
                select(MandateAssignment.user_id).where(
                    MandateAssignment.tenant_id == tenant_id,
                    MandateAssignment.role_key == OWNER_ROLE,
                    MandateAssignment.is_active.is_(True),
                )
            ).scalars()
        )
        if not set(others) - mandated:
            alone.append(tenant.display_name)
    return sorted(alone)


@router.post("/account-deletion", response_model=AccountDeletionDto, operation_id="deleteMyAccount")
def delete_my_account(
    body: AccountDeletionIn,
    request: Request,
    claims: Annotated[TokenClaims, Depends(get_claims)],
    session: Annotated[Session, Depends(get_session)],
    now: Annotated[datetime, Depends(get_now)],
) -> AccountDeletionDto:
    """Delete my account: my login is removed for good and my name and email are anonymised. My records stay with
    each company, shown under the anonymised name. Refused (LAST_OWNER) while I am the last owner of a company: give
    someone else the owner role, or close the company instead. Platform staff are refused (PLATFORM_ACCOUNT)."""
    user = IdentityRepository(session).upsert_user_from_claims(claims)
    if not user.is_active:
        raise PermissionDenied("User is deactivated", code="USER_INACTIVE")
    apply_scope(session, DbScope.SYSTEM, None, user.id)  # the person's rows across every company they belong to
    platform_member = session.execute(
        select(PlatformMembership.id).where(
            PlatformMembership.user_id == user.id, PlatformMembership.effective_to.is_(None)
        )
    ).first()
    if is_platform_staff(claims) or platform_member is not None:
        raise BusinessRuleViolation(
            "Platform accounts are closed through the platform's own process", code="PLATFORM_ACCOUNT"
        )
    if alone := _owned_alone(session, user.id):
        raise BusinessRuleViolation(
            f"You are the last owner of {', '.join(alone)}. Give someone else the owner role first, or close the "
            "company instead (Administration, Close company).",
            code="LAST_OWNER",
        )
    former_name = user.display_name
    memberships = list(
        session.execute(
            select(TenantMembership).where(TenantMembership.user_id == user.id, TenantMembership.effective_to.is_(None))
        ).scalars()
    )
    tenant_ids = sorted({m.tenant_id for m in memberships} | set(_claim_tenants(claims)))
    for m in memberships:
        m.effective_to = now
    staff = list(session.execute(select(StaffMember).where(StaffMember.keycloak_subject == claims.subject)).scalars())
    staff_by_tenant = {s.tenant_id: s.id for s in staff}
    for s in staff:
        s.phone = None  # the role history stays; contact details go
    anonymise_user(session, user, now, user.id)
    actor = AuditActor(user_id=user.id, roles=["self"], source="api")
    audit, outbox = AuditService(session), OutboxWriter(session)
    names: list[str] = []
    for tid in tenant_ids:
        tenant = session.get(Tenant, tid)
        if tenant is None:
            continue
        names.append(tenant.display_name)
        audit.record(
            actor=actor,
            action="identity.account.deleted",
            entity_type="app_user",
            entity_id=user.id,
            tenant_id=tid,
            after={
                "display_name": user.display_name,
                "memberships_closed": sum(1 for m in memberships if m.tenant_id == tid),
                "staff_member_id": str(staff_by_tenant[tid]) if tid in staff_by_tenant else None,
            },
            reason=body.reason,
        )
        outbox.emit(
            topic=TOPIC,
            event_type="AccountDeleted",
            key=str(tid),
            payload={
                "user_id": str(user.id),
                "former_name": former_name,
                "anonymised_name": user.display_name,
                "staff_member_id": str(staff_by_tenant[tid]) if tid in staff_by_tenant else None,
            },
            tenant_id=tid,
        )
    audit.record(
        actor=actor,
        action="platform.account.deleted",
        entity_type="app_user",
        entity_id=user.id,
        tenant_id=None,
        after={"display_name": user.display_name, "companies": len(names)},
        reason=body.reason,
    )
    session.flush()
    # The identity provider last: if it fails, nothing above is committed and the person can retry.
    idp = _idp(request)
    idp.disable_user(claims.subject)
    idp.delete_user(claims.subject)
    return AccountDeletionDto(
        user_id=user.id, display_name=user.display_name, deleted_at=user.deleted_at or now, companies=sorted(names)
    )


def _claim_tenants(claims: TokenClaims) -> list[uuid.UUID]:
    out: list[uuid.UUID] = []
    for g in claims.groups:
        parts = [p for p in g.split("/") if p]
        if len(parts) == 3 and parts[0] == "tenants":
            try:
                out.append(uuid.UUID(parts[1]))
            except ValueError:
                continue
    return out
