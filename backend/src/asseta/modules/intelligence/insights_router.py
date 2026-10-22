"""Tenant baseline insights and the OCR manual-override audit (Gate 6D). Permissions reuse existing grants so every
role template already gets the right view: fuel efficiency and utilisation need `tenant.fleet.read` (owner,
manager, supervisor), cash flow `tenant.finance.report` (owner, accountant), the override audit `tenant.meter.read`.
"""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from asseta.core.clock import get_now
from asseta.core.db import get_session
from asseta.core.errors import ERROR_RESPONSES, BusinessRuleViolation
from asseta.core.paging import PageParams, page_params
from asseta.modules.finance.permissions import REPORT
from asseta.modules.geospatial.router import FLEET_READ
from asseta.modules.identity.catalog import CATALOG, MenuDef
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.principal import RequestContext
from asseta.modules.intelligence.insights import HISTORY_WEEKS, METHOD, cash_flow, machine_insights
from asseta.modules.intelligence.insights_dto import CashFlowInsightDto, ManualOverrideReportDto, TenantInsightsDto
from asseta.modules.intelligence.overrides import manual_override_report
from asseta.modules.meter.router import METER_READ

CATALOG.register_menu(
    MenuDef("tenant.insights", S.TENANT, "Insights", "/tenant/insights", 64, "tenant.fleet.read", "tenant.risk")
)

router = APIRouter(prefix="/api/v1/tenant/insights", tags=["insights"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]
Now = Annotated[datetime, Depends(get_now)]


@router.get("", response_model=TenantInsightsDto, operation_id="getTenantInsights")
def get_insights(
    session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(FLEET_READ)]
) -> TenantInsightsDto:
    assert ctx.tenant_id is not None
    fuel, utilisation = machine_insights(session, ctx.tenant_id, now)
    flow = cash_flow(session, ctx.tenant_id, now) if "tenant.finance.report" in ctx.permissions else None
    return TenantInsightsDto(
        generated_at=now,
        history_weeks=HISTORY_WEEKS,
        fuel_efficiency=fuel,
        utilisation=utilisation,
        cash_flow=flow,
        method=METHOD,
    )


@router.get("/cash-flow", response_model=CashFlowInsightDto, operation_id="getTenantCashFlowInsight")
def get_cash_flow(session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(REPORT)]) -> CashFlowInsightDto:
    assert ctx.tenant_id is not None
    return cash_flow(session, ctx.tenant_id, now)


@router.get("/manual-overrides", response_model=ManualOverrideReportDto, operation_id="listManualOverrides")
def list_manual_overrides(
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(METER_READ)],
    paging: Annotated[PageParams, Depends(page_params)],
    captured_from: datetime | None = None,
    captured_to: datetime | None = None,
    machine_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> ManualOverrideReportDto:
    """Captures where OCR produced a value but the stored reading was entered by a person."""
    assert ctx.tenant_id is not None
    if captured_from and captured_to and captured_to <= captured_from:
        raise BusinessRuleViolation("captured_to must be after captured_from", code="INVALID_RANGE")
    return manual_override_report(
        session,
        ctx.tenant_id,
        paging,
        captured_from=captured_from,
        captured_to=captured_to,
        machine_id=machine_id,
        user_id=user_id,
    )
