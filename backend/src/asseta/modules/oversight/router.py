"""DEC-031 Phase 5 endpoints: the people scorecard (M1) and idle machines (M2). Each needs its tenant capability
(OVERSIGHT policy; refused with <CAPABILITY>_DISABLED while off)."""

import uuid
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from asseta.core.clock import get_now
from asseta.core.db import get_session
from asseta.core.errors import ERROR_RESPONSES
from asseta.core.paging import Page, PageParams, page_params
from asseta.modules.accountability.names import named
from asseta.modules.identity.catalog import CATALOG, MenuDef
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.dependencies import gated, requires
from asseta.modules.identity.principal import RequestContext
from asseta.modules.oversight.dto import IdleMachineDto, ScorecardDetailDto, ScorecardRowDto
from asseta.modules.oversight.idle import idle_machines
from asseta.modules.oversight.service import ScorecardService
from asseta.modules.policy.capabilities import IDLE_MACHINES, SCORECARD
from asseta.modules.policy.schemas import ScorecardItem

SCORECARD_PERMISSION = "tenant.oversight.scorecard.read"
OVERSIGHT_PERMISSION = "tenant.oversight.read"
_scorecard = requires(SCORECARD_PERMISSION, S.TENANT, "View the people scorecard (per-person items to look at)")
_oversight = requires(OVERSIGHT_PERMISSION, S.TENANT, "View idle machines")
SCORECARD_READ = gated(_scorecard, SCORECARD)
IDLE_READ = gated(_oversight, IDLE_MACHINES)

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
        "tenant.idle_machines",
        S.TENANT,
        "Idle machines",
        "/tenant/idle-machines",
        36,
        OVERSIGHT_PERMISSION,
        group="tenant.fleet",
        capability=IDLE_MACHINES,
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


# --- M2 idle machines -------------------------------------------------------------------------------------------
@router.get("/idle-machines", response_model=Page[IdleMachineDto], operation_id="listIdleMachines")
@named
def list_idle_machines(
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(IDLE_READ)],
    paging: Paging,
    category_id: uuid.UUID | None = None,
) -> Page[IdleMachineDto]:
    """Active machines with no approved machine-report hours for OVERSIGHT.idle_after_days (longest idle first;
    `q`: asset code or name)."""
    assert ctx.tenant_id is not None
    return _page(idle_machines(session, ctx.tenant_id, now, q=paging.q, category_id=category_id), paging)
