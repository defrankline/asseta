"""Accountability oversight endpoints (design D): refused attempts (security events), the review of conflicted or
rejected offline operations, and the accountability dashboard summary."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from asseta.core.clock import get_now
from asseta.core.db import get_session
from asseta.core.errors import ERROR_RESPONSES, BusinessRuleViolation
from asseta.core.paging import Page, PageParams, page_params, paginate
from asseta.modules.accountability.dto import (
    AccountabilitySummaryDto,
    SecurityEventDto,
    SyncConflictDto,
    SyncResolutionIn,
)
from asseta.modules.accountability.models import SecurityEventKind
from asseta.modules.accountability.service import AccountabilityDashboard, SecurityEventService, SyncConflictService
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.dependencies import requires
from asseta.modules.identity.principal import RequestContext
from asseta.modules.sync.models import OperationStatus

SECURITY_READ = requires(
    "tenant.security_event.read", S.TENANT, "View refused attempts (missing permission, segregation of duties)"
)
SYNC_CONFLICT_READ = requires(
    "tenant.sync_conflict.read", S.TENANT, "View conflicted or rejected offline field operations"
)
SYNC_CONFLICT_RESOLVE = requires(
    "tenant.sync_conflict.resolve", S.TENANT, "Resolve conflicted or rejected offline operations (dismiss/re-captured)"
)
ACCOUNTABILITY_READ = requires("tenant.accountability.read", S.TENANT, "View the accountability dashboard summary")

router = APIRouter(prefix="/api/v1/tenant", tags=["accountability"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]
Now = Annotated[datetime, Depends(get_now)]
Paging = Annotated[PageParams, Depends(page_params)]


@router.get("/security-events", response_model=Page[SecurityEventDto], operation_id="listSecurityEvents")
def list_security_events(
    session: DbSession,
    _: Annotated[RequestContext, Depends(SECURITY_READ)],
    paging: Paging,
    kind: SecurityEventKind | None = None,
    actor_user_id: uuid.UUID | None = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
) -> Page[SecurityEventDto]:
    """Refused attempts, latest first. `q` searches permission, action, record type and request path."""
    if occurred_from and occurred_to and occurred_to <= occurred_from:
        raise BusinessRuleViolation("occurred_to must be after occurred_from", code="INVALID_RANGE")
    svc = SecurityEventService(session)
    rows, total = paginate(session, svc.query(kind, actor_user_id, occurred_from, occurred_to, paging.q), paging)
    return Page(items=svc.dtos(rows), total=total, page=paging.page, page_size=paging.page_size)


@router.get("/sync/conflicts", response_model=Page[SyncConflictDto], operation_id="listSyncConflicts")
def list_sync_conflicts(
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(SYNC_CONFLICT_READ)],
    paging: Paging,
    status: OperationStatus | None = None,
    op_type: str | None = None,
    resolved: bool | None = None,
) -> Page[SyncConflictDto]:
    """Field operations the server did not apply, with the device payload (evidence), the reason and server state.
    `resolved=false` lists those still awaiting the office's outcome."""
    svc = SyncConflictService(session, ctx, now)
    rows, total = paginate(session, svc.query(status, op_type, resolved, paging.q), paging)
    return Page(items=svc.dtos(rows), total=total, page=paging.page, page_size=paging.page_size)


@router.get("/sync/conflicts/{operation_id}", response_model=SyncConflictDto, operation_id="getSyncConflict")
def get_sync_conflict(
    operation_id: uuid.UUID,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(SYNC_CONFLICT_READ)],
) -> SyncConflictDto:
    svc = SyncConflictService(session, ctx, now)
    return svc.dtos([svc.get(operation_id)])[0]


@router.post(
    "/sync/conflicts/{operation_id}/resolution",
    response_model=SyncConflictDto,
    operation_id="resolveSyncConflict",
)
def resolve_sync_conflict(
    operation_id: uuid.UUID,
    body: SyncResolutionIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(SYNC_CONFLICT_RESOLVE)],
) -> SyncConflictDto:
    """Record the outcome once: DISMISSED (reason) or RECAPTURED (optionally naming the new record). Audited; never
    by the person who submitted the operation."""
    return SyncConflictService(session, ctx, now).resolve(operation_id, body)


@router.get("/accountability/summary", response_model=AccountabilitySummaryDto, operation_id="getAccountabilitySummary")
def accountability_summary(
    session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(ACCOUNTABILITY_READ)]
) -> AccountabilitySummaryDto:
    """The 3.6 oversight list in one call (web dashboard and Owner app summary). Tiles hidden by the tenant's
    OVERSIGHT policy are null and listed in `hidden_tiles`."""
    return AccountabilityDashboard(session, ctx, now).summary()
