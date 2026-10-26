"""DEC-031 Phase 5 endpoints: the people scorecard (M1), unbilled work and idle machines (M2) and site check-ins
(M3). Each needs its tenant capability (OVERSIGHT policy; refused with <CAPABILITY>_DISABLED while off)."""

import uuid
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from asseta.core.clock import get_now
from asseta.core.db import get_session
from asseta.core.errors import ERROR_RESPONSES
from asseta.core.paging import Page, PageParams, page_params, paginate
from asseta.modules.accountability.names import named
from asseta.modules.identity.catalog import CATALOG, MenuDef
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.dependencies import gated, requires
from asseta.modules.identity.principal import RequestContext
from asseta.modules.oversight.checkins import SiteCheckinService
from asseta.modules.oversight.dto import (
    IdleMachineDto,
    MySiteCheckinsDto,
    ScorecardDetailDto,
    ScorecardRowDto,
    SiteCheckinDto,
    SiteCheckinIn,
    UnbilledJobDto,
)
from asseta.modules.oversight.idle import idle_machines
from asseta.modules.oversight.service import ScorecardService
from asseta.modules.oversight.unbilled import unbilled_jobs
from asseta.modules.policy.capabilities import IDLE_MACHINES, SCORECARD, SITE_CHECKIN, UNBILLED_WORK
from asseta.modules.policy.schemas import ScorecardItem

SCORECARD_PERMISSION = "tenant.oversight.scorecard.read"
OVERSIGHT_PERMISSION = "tenant.oversight.read"
CHECKIN_PERMISSION = "tenant.site_checkin.record"
_scorecard = requires(SCORECARD_PERMISSION, S.TENANT, "View the people scorecard (per-person items to look at)")
_oversight = requires(OVERSIGHT_PERMISSION, S.TENANT, "View unbilled work, idle machines and site check-ins")
_checkin = requires(CHECKIN_PERMISSION, S.TENANT, "Check in at the site (GPS) and see one's own check-ins")
SCORECARD_READ = gated(_scorecard, SCORECARD)
UNBILLED_READ = gated(_oversight, UNBILLED_WORK)
IDLE_READ = gated(_oversight, IDLE_MACHINES)
CHECKINS_READ = gated(_oversight, SITE_CHECKIN)
CHECKIN_RECORD = gated(_checkin, SITE_CHECKIN)

for _menu in (
    MenuDef(
        "tenant.scorecard",
        S.TENANT,
        "People scorecard",
        "/tenant/scorecard",
        8,
        SCORECARD_PERMISSION,
        group="tenant.overview",
        capability=SCORECARD,
    ),
    MenuDef(
        "tenant.unbilled_work",
        S.TENANT,
        "Unbilled work",
        "/tenant/unbilled-work",
        67,
        OVERSIGHT_PERMISSION,
        group="tenant.finance",
        capability=UNBILLED_WORK,
    ),
    MenuDef(
        "tenant.idle_machines",
        S.TENANT,
        "Idle machines",
        "/tenant/idle-machines",
        36,
        OVERSIGHT_PERMISSION,
        group="tenant.fleet",
        capability=IDLE_MACHINES,
    ),
    MenuDef(
        "tenant.site_checkins",
        S.TENANT,
        "Site check-ins",
        "/tenant/site-checkins",
        24,
        OVERSIGHT_PERMISSION,
        group="tenant.operations",
        capability=SITE_CHECKIN,
    ),
    MenuDef(
        "tenant.field.checkin",
        S.TENANT,
        "Site check-in",
        "/tenant/field/check-in",
        17,
        CHECKIN_PERMISSION,
        group="tenant.field",
        capability=SITE_CHECKIN,
    ),
):
    CATALOG.register_menu(_menu)

router = APIRouter(prefix="/api/v1/tenant", tags=["oversight"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]
Now = Annotated[datetime, Depends(get_now)]
Paging = Annotated[PageParams, Depends(page_params)]
DayFrom = Annotated[date | None, Query(description="First tenant-local day (default: 29 days before day_to)")]
DayTo = Annotated[date | None, Query(description="Last tenant-local day, inclusive (default: today)")]


def _page[T](rows: list[T], paging: PageParams) -> Page[T]:
    start = (paging.page - 1) * paging.page_size
    return Page(
        items=rows[start : start + paging.page_size], total=len(rows), page=paging.page, page_size=paging.page_size
    )


# --- M1 people scorecard -----------------------------------------------------------------------------------------
@router.get("/scorecard", response_model=Page[ScorecardRowDto], operation_id="listScorecard")
@named
def list_scorecard(
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(SCORECARD_READ)],
    paging: Paging,
    day_from: DayFrom = None,
    day_to: DayTo = None,
    staff_id: uuid.UUID | None = None,
    site_id: uuid.UUID | None = None,
) -> Page[ScorecardRowDto]:
    """One row per person (active staff, and anyone with items) for a tenant-local period (default the last 30
    days, at most 93): most items first. `q` searches the name; `site_id` keeps people who worked that site."""
    rows, total = ScorecardService(session, ctx, now).page(
        day_from, day_to, staff_id, site_id, paging.q, (paging.page - 1) * paging.page_size, paging.page_size
    )
    return Page(items=rows, total=total, page=paging.page, page_size=paging.page_size)


@router.get("/scorecard/{staff_member_id}", response_model=ScorecardDetailDto, operation_id="getScorecard")
@named
def get_scorecard(
    staff_member_id: uuid.UUID,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(SCORECARD_READ)],
    day_from: DayFrom = None,
    day_to: DayTo = None,
    item: ScorecardItem | None = None,
) -> ScorecardDetailDto:
    """One person's figures with every record behind them (newest first; `item` filters one kind)."""
    return ScorecardService(session, ctx, now).detail(staff_member_id, day_from, day_to, item)


# --- M2 unbilled work and idle machines ---------------------------------------------------------------------------
@router.get("/unbilled-work", response_model=Page[UnbilledJobDto], operation_id="listUnbilledWork")
@named
def list_unbilled_work(
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(UNBILLED_READ)],
    paging: Paging,
    customer_id: uuid.UUID | None = None,
    machine_id: uuid.UUID | None = None,
    site_id: uuid.UUID | None = None,
) -> Page[UnbilledJobDto]:
    """Completed, billing-ready jobs not on an issued invoice after OVERSIGHT.unbilled_after_days (oldest first;
    `q`: job number or customer)."""
    assert ctx.tenant_id is not None
    rows = unbilled_jobs(
        session, ctx.tenant_id, now, q=paging.q, customer_id=customer_id, machine_id=machine_id, site_id=site_id
    )
    return _page(rows, paging)


@router.get("/idle-machines", response_model=Page[IdleMachineDto], operation_id="listIdleMachines")
@named
def list_idle_machines(
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(IDLE_READ)],
    paging: Paging,
    category_id: uuid.UUID | None = None,
) -> Page[IdleMachineDto]:
    """Active machines with no running job and no engine hours for OVERSIGHT.idle_after_days (longest idle first;
    `q`: asset code or name)."""
    assert ctx.tenant_id is not None
    return _page(idle_machines(session, ctx.tenant_id, now, q=paging.q, category_id=category_id), paging)


# --- M3 site check-ins ------------------------------------------------------------------------------------------
@router.post("/site-checkins", response_model=SiteCheckinDto, status_code=201, operation_id="recordSiteCheckin")
@named
def record_site_checkin(
    body: SiteCheckinIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(CHECKIN_RECORD)],
) -> SiteCheckinDto:
    """The caller checks in at the site (same as the sync op SITE_CHECKIN). Replaying a client_id returns the
    stored check-in."""
    return SiteCheckinService(session, ctx, now).record(body, "API")


@router.get("/site-checkins/mine", response_model=MySiteCheckinsDto, operation_id="getMySiteCheckins")
@named
def my_site_checkins(
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(CHECKIN_RECORD)],
    day_from: Annotated[date | None, Query(description="Default: 6 days before day_to")] = None,
    day_to: DayTo = None,
) -> MySiteCheckinsDto:
    """The caller's schedule (MADE / MISSED / DUE / UPCOMING) and check-ins."""
    return SiteCheckinService(session, ctx, now).mine(day_from, day_to)


@router.get("/site-checkins", response_model=Page[SiteCheckinDto], operation_id="listSiteCheckins")
@named
def list_site_checkins(
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(CHECKINS_READ)],
    paging: Paging,
    staff_id: uuid.UUID | None = None,
    job_site_id: uuid.UUID | None = None,
    day_from: date | None = None,
    day_to: date | None = None,
) -> Page[SiteCheckinDto]:
    """Everyone's check-ins, newest first (`q`: person's name)."""
    svc = SiteCheckinService(session, ctx, now)
    rows, total = paginate(session, svc.query(staff_id, job_site_id, day_from, day_to, paging.q), paging)
    return Page(items=[svc.dto(r) for r in rows], total=total, page=paging.page, page_size=paging.page_size)


@router.get("/site-checkins/{checkin_id}", response_model=SiteCheckinDto, operation_id="getSiteCheckin")
@named
def get_site_checkin(
    checkin_id: uuid.UUID,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(CHECKINS_READ)],
) -> SiteCheckinDto:
    return SiteCheckinService(session, ctx, now).get(checkin_id)
