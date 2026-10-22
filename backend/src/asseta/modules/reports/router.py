"""Report exports (R1-I): `GET /api/v1/tenant/reports/{code}.csv|.pdf` (+ platform equivalents) with the list
endpoint's filters and permission, a row cap with an explicit truncation note, and an audit record per export.
`GET .../reports` lists the definitions the caller may export so clients can render export menus."""

from collections.abc import Callable
from datetime import datetime
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.clock import get_now
from asseta.core.db import get_session
from asseta.core.errors import ERROR_RESPONSES
from asseta.modules.expenses.router import EXPENSE_READ
from asseta.modules.finance.common import tenant_settings
from asseta.modules.finance.permissions import FINANCE_READ
from asseta.modules.geospatial.router import FLEET_READ
from asseta.modules.identity.catalog import PermissionScope
from asseta.modules.identity.dependencies import requires_any
from asseta.modules.identity.models import AppUser
from asseta.modules.identity.principal import RequestContext
from asseta.modules.jobs.router import JOB_READ
from asseta.modules.meter.router import METER_READ
from asseta.modules.notification.settings import get_notification_settings
from asseta.modules.platform_billing.permissions import INVOICE_READ, TENANT_BILLING_READ
from asseta.modules.reports.definitions import (
    CSV_ROW_CAP,
    PDF_ROW_CAP,
    ReportDefinition,
    ReportEnv,
    applied_filters,
)
from asseta.modules.reports.render import csv_chunks, pdf_bytes
from asseta.modules.reports.sources_money import CASH, EXPENSES, PLATFORM_SUBSCRIPTION, SUBSCRIPTION
from asseta.modules.reports.sources_ops import ALERTS, FLEET, JOBS, READINGS, UTILISATION
from asseta.modules.tenancy.models import Tenant

TENANT_REPORTS: tuple[ReportDefinition, ...] = (
    FLEET,
    JOBS,
    READINGS,
    CASH,
    EXPENSES,
    ALERTS,
    SUBSCRIPTION,
    UTILISATION,
)
PLATFORM_REPORTS: tuple[ReportDefinition, ...] = (PLATFORM_SUBSCRIPTION,)
# Each report reuses its list endpoint's permission dependency (declared by the owning module).
PERMISSIONS: dict[str, Callable[..., RequestContext]] = {
    "tenant.fleet.read": FLEET_READ,
    "tenant.job.read": JOB_READ,
    "tenant.meter.read": METER_READ,
    "tenant.finance.read": FINANCE_READ,
    "tenant.expense.read": EXPENSE_READ,
    "tenant.billing.read": TENANT_BILLING_READ,
    "platform.invoice.read": INVOICE_READ,
}
FORMATS = {"csv": ("text/csv; charset=utf-8", CSV_ROW_CAP), "pdf": ("application/pdf", PDF_ROW_CAP)}
DbSession = Annotated[Session, Depends(get_session)]
Now = Annotated[datetime, Depends(get_now)]


class ReportColumnDto(BaseModel):
    key: str
    label: str
    kind: str


class ReportDefinitionDto(BaseModel):
    code: str
    title: str
    description: str
    formats: list[str]
    csv_path: str
    pdf_path: str
    list_operation: str
    filters: list[str]
    columns: list[ReportColumnDto]
    csv_row_cap: int
    pdf_row_cap: int


def _definition_dto(base: str, d: ReportDefinition) -> ReportDefinitionDto:
    return ReportDefinitionDto(
        code=d.code,
        title=d.title,
        description=d.description,
        formats=list(FORMATS),
        csv_path=f"{base}/{d.code}.csv",
        pdf_path=f"{base}/{d.code}.pdf",
        list_operation=d.list_operation,
        filters=[f.alias or name for name, f in d.filters.model_fields.items()],
        columns=[ReportColumnDto(key=c.key, label=c.label, kind=c.kind) for c in d.columns],
        csv_row_cap=CSV_ROW_CAP,
        pdf_row_cap=PDF_ROW_CAP,
    )


def _env(session: Session, ctx: RequestContext, now: datetime) -> ReportEnv:
    user = session.get(AppUser, ctx.user_id)
    who = user.display_name if user else str(ctx.user_id)
    if ctx.tenant_id is None:
        return ReportEnv(get_notification_settings().platform_timezone, "Asseta platform", now, who)
    tenant = session.get(Tenant, ctx.tenant_id)
    tz = tenant_settings(session, ctx.tenant_id).timezone
    return ReportEnv(tz, tenant.display_name if tenant else str(ctx.tenant_id), now, who)


def export(
    session: Session, ctx: RequestContext, now: datetime, d: ReportDefinition, filters: BaseModel, fmt: str
) -> Response:
    media_type, cap = FORMATS[fmt]
    data = d.fetch(session, ctx, now, filters, cap)
    env = _env(session, ctx, now)
    shown = applied_filters(filters)
    AuditService(session).record(
        actor=ctx.audit_actor(),
        action=f"{'platform.' if ctx.tenant_id is None else ''}report.exported",
        entity_type="report",
        entity_id=d.code,
        tenant_id=ctx.tenant_id,
        after={"format": fmt, "filters": shown, "rows": len(data.rows), "truncated": data.truncated},
    )
    session.flush()
    local_day = now.astimezone(ZoneInfo(env.timezone)).date().isoformat()
    headers = {
        "Content-Disposition": f'attachment; filename="asseta-{d.code}-{local_day}.{fmt}"',
        "X-Report-Rows": str(len(data.rows)),
        "X-Report-Truncated": "true" if data.truncated else "false",
        "Cache-Control": "no-store",
    }
    if fmt == "csv":
        return StreamingResponse(csv_chunks(d, data, env, cap), media_type=media_type, headers=headers)
    return Response(pdf_bytes(d, data, env, shown, cap), media_type=media_type, headers=headers)


def _endpoint(d: ReportDefinition, permission: Callable[..., RequestContext], fmt: str) -> Callable[..., Response]:
    Filters: Any = d.filters  # noqa: N806 - the report's query-parameter model

    def endpoint(
        session: DbSession,
        now: Now,
        ctx: Annotated[RequestContext, Depends(permission)],
        filters: Annotated[Filters, Query()],
    ) -> Response:
        return export(session, ctx, now, d, filters, fmt)

    return endpoint


def _register(router: APIRouter, d: ReportDefinition, permission: Callable[..., RequestContext], prefix: str) -> None:
    name = "".join(part.capitalize() for part in d.code.split("_"))
    for fmt, (media_type, cap) in FORMATS.items():
        router.add_api_route(
            f"/{d.code}.{fmt}",
            _endpoint(d, permission, fmt),
            methods=["GET"],
            response_class=Response,
            operation_id=f"export{prefix}{name}Report{fmt.capitalize()}",
            summary=f"{d.title} ({fmt.upper()})",
            description=f"{d.description}. Same filters, sort and permission ({d.permission}) as `{d.list_operation}`;"
            f" at most {cap:,} rows, then a truncation note. Every export is audited.",
            responses={200: {"content": {media_type.split(";")[0]: {}}, "description": f"{fmt.upper()} file"}},
        )


def build_router(base: str, tag: str, prefix: str, reports: tuple[ReportDefinition, ...]) -> APIRouter:
    scope = reports[0].scope
    router = APIRouter(prefix=base, tags=[tag], responses=ERROR_RESPONSES)
    perms = {d.permission: PERMISSIONS[d.permission] for d in reports}
    any_report = requires_any(tuple(perms), scope)

    @router.get("", response_model=list[ReportDefinitionDto], operation_id=f"list{prefix}ReportDefinitions")
    def list_reports(ctx: Annotated[RequestContext, Depends(any_report)]) -> list[ReportDefinitionDto]:
        """Reports the caller may export (each gated by its list endpoint's permission)."""
        return [_definition_dto(base, d) for d in reports if d.permission in ctx.permissions]

    for d in reports:
        _register(router, d, perms[d.permission], prefix)
    return router


tenant_router = build_router("/api/v1/tenant/reports", "reports", "Tenant", TENANT_REPORTS)
platform_router = build_router("/api/v1/platform/reports", "platform-reports", "Platform", PLATFORM_REPORTS)
assert all(d.scope is PermissionScope.TENANT for d in TENANT_REPORTS)
assert all(d.scope is PermissionScope.PLATFORM for d in PLATFORM_REPORTS)
