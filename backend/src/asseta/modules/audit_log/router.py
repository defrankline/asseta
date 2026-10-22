"""Audit log views over the append-only `audit_event` trail.

Tenant (`tenant.audit.read`): RLS returns only the tenant's own events. Platform (`platform.audit.read`): RLS returns
only platform/billing actions (`platform.%`, `billing.%`) — tenant business audit stays invisible to the platform
console by design (ADR-002); platform staff see a client's audit only inside that tenant under a mandate. The actor
is shown by display name, and events recorded under a managed-service mandate carry the mandate reference."""

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditEvent
from asseta.core.db import get_session
from asseta.core.errors import ERROR_RESPONSES, BusinessRuleViolation
from asseta.core.paging import Page, PageParams, page_params
from asseta.core.search import ESCAPE, ilike_any, like_pattern
from asseta.modules.identity.catalog import CATALOG, MenuDef
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.dependencies import requires
from asseta.modules.identity.models import AppUser
from asseta.modules.identity.principal import RequestContext
from asseta.modules.managed_service.models import ManagedServiceMandate

TENANT_AUDIT_READ = requires("tenant.audit.read", S.TENANT, "View the tenant's audit log (who changed what, when)")
PLATFORM_AUDIT_READ = requires("platform.audit.read", S.PLATFORM, "View the platform audit log")
for menu in (
    MenuDef("tenant.audit", S.TENANT, "Audit log", "/tenant/audit", 88, "tenant.audit.read", group="tenant.admin"),
    MenuDef(
        "platform.audit", S.PLATFORM, "Audit log", "/platform/audit", 92, "platform.audit.read", group="platform.admin"
    ),
):
    CATALOG.register_menu(menu)

DbSession = Annotated[Session, Depends(get_session)]
ActionPrefix = Annotated[str | None, Query(max_length=128, pattern=r"^[a-z0-9_.]+$", description="e.g. finance.")]


class AuditEventDto(BaseModel):
    id: uuid.UUID
    occurred_at: datetime
    tenant_id: uuid.UUID | None
    actor_user_id: uuid.UUID | None
    actor_display_name: str | None = Field(description="Null for system/worker actions")
    actor_roles: list[str]
    source: str
    device_id: str | None
    action: str
    entity_type: str
    entity_id: str
    reason: str | None
    policy_version: str | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    correlation_id: str
    mandate_id: uuid.UUID | None
    mandate_reference: str | None = Field(description="Set when platform staff acted under a managed-service mandate")


def _query(
    actor_user_id: uuid.UUID | None,
    action_prefix: str | None,
    entity_type: str | None,
    entity_id: str | None,
    occurred_from: datetime | None,
    occurred_to: datetime | None,
    q: str | None,
) -> Select[AuditEvent, str, str]:
    if occurred_from and occurred_to and occurred_to <= occurred_from:
        raise BusinessRuleViolation("occurred_to must be after occurred_from", code="INVALID_RANGE")
    stmt = (
        select(AuditEvent, AppUser.display_name, ManagedServiceMandate.reference)
        .outerjoin(AppUser, AppUser.id == AuditEvent.actor_user_id)
        .outerjoin(ManagedServiceMandate, ManagedServiceMandate.id == AuditEvent.mandate_id)
        .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id)
    )
    for col, value in (
        (AuditEvent.actor_user_id, actor_user_id),
        (AuditEvent.entity_type, entity_type),
        (AuditEvent.entity_id, entity_id),
    ):
        if value is not None:
            stmt = stmt.where(col == value)
    if action_prefix:
        stmt = stmt.where(AuditEvent.action.like(like_pattern(action_prefix)[1:], escape=ESCAPE))
    if occurred_from is not None:
        stmt = stmt.where(AuditEvent.occurred_at >= occurred_from)
    if occurred_to is not None:
        stmt = stmt.where(AuditEvent.occurred_at < occurred_to)
    if (match := ilike_any(q, AuditEvent.action, AuditEvent.entity_type, AuditEvent.entity_id)) is not None:
        stmt = stmt.where(match)
    return stmt


def _page(session: Session, stmt: Select[AuditEvent, str, str], paging: PageParams) -> Page[AuditEventDto]:
    total = int(session.execute(select(func.count()).select_from(stmt.order_by(None).subquery())).scalar_one())
    rows = session.execute(stmt.limit(paging.page_size).offset((paging.page - 1) * paging.page_size)).all()
    items = [
        AuditEventDto(
            id=e.id,
            occurred_at=e.occurred_at,
            tenant_id=e.tenant_id,
            actor_user_id=e.actor_user_id,
            actor_display_name=name,
            actor_roles=list(e.actor_roles or []),
            source=e.source,
            device_id=e.device_id,
            action=e.action,
            entity_type=e.entity_type,
            entity_id=e.entity_id,
            reason=e.reason,
            policy_version=e.policy_version,
            before=e.before,
            after=e.after,
            correlation_id=e.correlation_id,
            mandate_id=e.mandate_id,
            mandate_reference=reference,
        )
        for e, name, reference in rows
    ]
    return Page(items=items, total=total, page=paging.page, page_size=paging.page_size)


tenant_router = APIRouter(prefix="/api/v1/tenant/audit-events", tags=["audit"], responses=ERROR_RESPONSES)
platform_router = APIRouter(prefix="/api/v1/platform/audit-events", tags=["platform-audit"], responses=ERROR_RESPONSES)


@tenant_router.get("", response_model=Page[AuditEventDto], operation_id="listTenantAuditEvents")
def tenant_audit_events(
    session: DbSession,
    _: Annotated[RequestContext, Depends(TENANT_AUDIT_READ)],
    paging: Annotated[PageParams, Depends(page_params)],
    actor_user_id: uuid.UUID | None = None,
    action_prefix: ActionPrefix = None,
    entity_type: Annotated[str | None, Query(max_length=64)] = None,
    entity_id: Annotated[str | None, Query(max_length=64)] = None,
    occurred_from: datetime | None = None,
    occurred_to: Annotated[datetime | None, Query(description="Exclusive")] = None,
) -> Page[AuditEventDto]:
    """The tenant's audit trail, newest first (RLS: this tenant's events only)."""
    stmt = _query(actor_user_id, action_prefix, entity_type, entity_id, occurred_from, occurred_to, paging.q)
    return _page(session, stmt, paging)


@platform_router.get("", response_model=Page[AuditEventDto], operation_id="listPlatformAuditEvents")
def platform_audit_events(
    session: DbSession,
    _: Annotated[RequestContext, Depends(PLATFORM_AUDIT_READ)],
    paging: Annotated[PageParams, Depends(page_params)],
    tenant_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    action_prefix: ActionPrefix = None,
    entity_type: Annotated[str | None, Query(max_length=64)] = None,
    entity_id: Annotated[str | None, Query(max_length=64)] = None,
    occurred_from: datetime | None = None,
    occurred_to: Annotated[datetime | None, Query(description="Exclusive")] = None,
) -> Page[AuditEventDto]:
    """Platform and billing actions (RLS), newest first; `tenant_id` narrows to actions about one tenant."""
    stmt = _query(actor_user_id, action_prefix, entity_type, entity_id, occurred_from, occurred_to, paging.q)
    if tenant_id is not None:
        stmt = stmt.where(AuditEvent.tenant_id == tenant_id)
    return _page(session, stmt, paging)
