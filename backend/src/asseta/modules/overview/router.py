"""`GET /api/v1/tenant/overview`: owner/console KPIs in permission-gated sections (see `OverviewService`)."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from asseta.core.clock import get_now
from asseta.core.db import get_session
from asseta.core.errors import ERROR_RESPONSES
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.dependencies import requires_any
from asseta.modules.identity.principal import RequestContext
from asseta.modules.overview.dto import TenantOverviewDto
from asseta.modules.overview.service import SECTION_PERMISSIONS, OverviewService

OVERVIEW_READ = requires_any(SECTION_PERMISSIONS, S.TENANT)

router = APIRouter(prefix="/api/v1/tenant", tags=["overview"], responses=ERROR_RESPONSES)


@router.get("/overview", response_model=TenantOverviewDto, operation_id="getTenantOverview")
def get_overview(
    session: Annotated[Session, Depends(get_session)],
    now: Annotated[datetime, Depends(get_now)],
    ctx: Annotated[RequestContext, Depends(OVERVIEW_READ)],
) -> TenantOverviewDto:
    """Fleet, work, money and risk KPIs. A section is omitted (null) when the caller lacks its permission; within
    a section, counts needing another permission are null. `latest_source_at` per section tells offline owner apps
    how fresh the underlying data was; `as_of` is when it was computed."""
    return OverviewService(session, ctx, now).overview()
