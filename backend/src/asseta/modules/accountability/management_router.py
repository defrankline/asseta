"""Management view endpoints (guideline sections 8 and 10): the pending list behind the dashboard, the employee view and
the transaction lookup. Included by the accountability router."""

import uuid
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from asseta.core.clock import get_now
from asseta.core.db import get_session
from asseta.core.paging import Page, PageParams, page_params
from asseta.core.search import ilike_any
from asseta.modules.accountability.employee import EmployeeAccountability, EmployeeAccountabilityDto
from asseta.modules.accountability.flows import pending_union
from asseta.modules.accountability.lookup import LookupResultDto, lookup
from asseta.modules.accountability.names import named
from asseta.modules.accountability.sections import pending_item
from asseta.modules.accountability.sections_dto import PendingItemDto
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.dependencies import requires
from asseta.modules.identity.principal import RequestContext
from asseta.modules.policy.capabilities import disabled_capabilities

ACCOUNTABILITY_READ = requires("tenant.accountability.read", S.TENANT, "View the accountability dashboard summary")
EMPLOYEE_READ = requires(
    "tenant.accountability.employee.read", S.TENANT, "View one employee's cash, reports, decisions and adjustments"
)
LOOKUP_READ = requires("tenant.lookup.read", S.TENANT, "Find any transaction by its reference or record id")

router = APIRouter()
DbSession = Annotated[Session, Depends(get_session)]
Now = Annotated[datetime, Depends(get_now)]
Paging = Annotated[PageParams, Depends(page_params)]


@router.get(
    "/accountability/pending-adjustments",
    response_model=Page[PendingItemDto],
    operation_id="listPendingAdjustments",
)
@named
def list_pending_adjustments(
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(ACCOUNTABILITY_READ)],
    paging: Paging,
    record_type: str | None = None,
    all_approvals: Annotated[bool, Query(description="Every outstanding approval, not only adjustments")] = False,
) -> Page[PendingItemDto]:
    """Everything proposed and not yet decided across all flows, oldest first. `q` searches the record's number."""
    assert ctx.tenant_id is not None
    disabled = disabled_capabilities(session, ctx.tenant_id, now)
    sub = pending_union(disabled, adjustments_only=not all_approvals)
    conds = []
    if record_type:
        conds.append(sub.c.record_type == record_type)
    if (match := ilike_any(paging.q, sub.c.reference)) is not None:
        conds.append(match)
    total = int(session.execute(select(func.count()).select_from(sub).where(*conds)).scalar_one())
    rows = session.execute(
        select(sub)
        .where(*conds)
        .order_by(sub.c.requested_at, sub.c.id)
        .limit(paging.page_size)
        .offset((paging.page - 1) * paging.page_size)
    ).all()
    return Page(items=[pending_item(r) for r in rows], total=total, page=paging.page, page_size=paging.page_size)


@router.get(
    "/employees/{staff_member_id}/accountability",
    response_model=EmployeeAccountabilityDto,
    operation_id="getEmployeeAccountability",
)
@named
def employee_accountability(
    staff_member_id: uuid.UUID,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(EMPLOYEE_READ)],
    date_from: Annotated[
        date | None, Query(description="First tenant-local day (default: 29 days before date_to)")
    ] = None,
    date_to: Annotated[date | None, Query(description="Last tenant-local day, inclusive (default: today)")] = None,
) -> EmployeeAccountabilityDto:
    """One person: identity and roles, cash held now, and every record behind it over the period. Scorecard items need
    the scorecard permission (`scorecard_visible`)."""
    return EmployeeAccountability(session, ctx, now).build(staff_member_id, date_from, date_to)


@router.get("/lookup", response_model=LookupResultDto, operation_id="lookupTransaction")
@named
def lookup_transaction(
    session: DbSession,
    _: Annotated[RequestContext, Depends(LOOKUP_READ)],
    reference: Annotated[str, Query(min_length=1, max_length=120)],
) -> LookupResultDto:
    """Any generated number (HP-, HINV-, J-, COL-, PAY-, RMT-, CTR-, HTR-, RET-, CADJ-, ARQ-, ADJ-, case numbers), an
    outside bank or mobile-money reference, or a record id. No match is an empty list."""
    return lookup(session, reference)
