"""Administration -> Data export and Balance verification (tenant) and the platform's balance verification view."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.clock import get_now
from asseta.core.db import DbScope, apply_scope, get_session
from asseta.core.errors import ERROR_RESPONSES, BusinessRuleViolation, Conflict, NotFound
from asseta.core.paging import Page, PageParams, page_params, paginate
from asseta.core.search import ilike_any
from asseta.core.storage import ObjectStore
from asseta.modules.dataprotection import permissions as P
from asseta.modules.dataprotection.dto import (
    DataExportDto,
    DataExportIn,
    DownloadLinkDto,
    GoLiveIn,
    TenantVerificationDto,
    VerificationRunDto,
    VerificationRunSummaryDto,
)
from asseta.modules.dataprotection.export_service import DataExportService
from asseta.modules.dataprotection.models import BalanceVerificationRun, VerificationTrigger
from asseta.modules.dataprotection.verification import run_verification
from asseta.modules.fleet.photos import get_object_store
from asseta.modules.identity.principal import RequestContext
from asseta.modules.tenancy.dto import TenantDto
from asseta.modules.tenancy.models import Tenant, TenantStatus

router = APIRouter(prefix="/api/v1/tenant", tags=["data-protection"], responses=ERROR_RESPONSES)
platform_router = APIRouter(prefix="/api/v1/platform", tags=["platform-data-protection"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]
Now = Annotated[datetime, Depends(get_now)]
Store = Annotated[ObjectStore, Depends(get_object_store)]
Exporter = Annotated[RequestContext, Depends(P.DATA_EXPORT)]
ExporterOnReadOnly = Annotated[RequestContext, Depends(P.DATA_EXPORT_READ_ONLY_EXEMPT)]
Paging = Annotated[PageParams, Depends(page_params)]


def _tid(ctx: RequestContext) -> uuid.UUID:
    assert ctx.tenant_id is not None
    return ctx.tenant_id


@router.post("/data-exports", response_model=DataExportDto, status_code=201, operation_id="requestDataExport")
def request_export(body: DataExportIn, session: DbSession, ctx: ExporterOnReadOnly, now: Now) -> DataExportDto:
    """Queues a full export of the company's records; the export worker builds the ZIP in the background. Stays open
    on a read-only subscription (guideline 9), audited as such."""
    return DataExportDto.model_validate(DataExportService(session, ctx, now).request(body.format))


@router.get("/data-exports", response_model=Page[DataExportDto], operation_id="listDataExports")
def list_exports(session: DbSession, ctx: Exporter, now: Now, paging: Paging) -> Page[DataExportDto]:
    rows, total = paginate(session, DataExportService(session, ctx, now).list_query(), paging)
    return Page(
        items=[DataExportDto.model_validate(r) for r in rows], total=total, page=paging.page, page_size=paging.page_size
    )


@router.get("/data-exports/{export_id}", response_model=DataExportDto, operation_id="getDataExport")
def get_export(export_id: uuid.UUID, session: DbSession, ctx: Exporter, now: Now) -> DataExportDto:
    return DataExportDto.model_validate(DataExportService(session, ctx, now).get(export_id))


@router.post("/data-exports/{export_id}/download", response_model=DownloadLinkDto, operation_id="getDataExportDownload")
def download_export(
    export_id: uuid.UUID, session: DbSession, ctx: ExporterOnReadOnly, now: Now, store: Store
) -> DownloadLinkDto:
    """A short-lived link to the finished ZIP. Every request for a link is audited. Stays open on a read-only
    subscription (guideline 9), audited as such."""
    return DataExportService(session, ctx, now).download_link(export_id, store)


@router.get(
    "/data-exports/evidence/{source}/{row_id}/url", response_model=DownloadLinkDto, operation_id="getDataExportEvidence"
)
def evidence_url(
    source: str, row_id: uuid.UUID, session: DbSession, ctx: Exporter, now: Now, store: Store
) -> DownloadLinkDto:
    """Fetch one evidence file listed in `evidence/manifest.csv` (a short-lived link; audited)."""
    return DataExportService(session, ctx, now).evidence_link(source, row_id, store)


@router.post(
    "/balance-verification/runs",
    response_model=VerificationRunDto,
    status_code=201,
    operation_id="runBalanceVerification",
)
def run_now(
    session: DbSession, ctx: Annotated[RequestContext, Depends(P.BALANCE_VERIFY)], now: Now
) -> VerificationRunDto:
    """Recomputes every balance from its records and reports differences. Nothing is corrected: the ledger prevails."""
    run = run_verification(session, _tid(ctx), VerificationTrigger.MANUAL, ctx.audit_actor(), ctx.user_id, now)
    return VerificationRunDto.model_validate(run)


@router.get(
    "/balance-verification/runs",
    response_model=Page[VerificationRunSummaryDto],
    operation_id="listBalanceVerifications",
)
def list_runs(
    session: DbSession, _: Annotated[RequestContext, Depends(P.BALANCE_READ)], paging: Paging
) -> Page[VerificationRunSummaryDto]:
    stmt = select(BalanceVerificationRun).order_by(BalanceVerificationRun.started_at.desc(), BalanceVerificationRun.id)
    rows, total = paginate(session, stmt, paging)
    return Page(
        items=[VerificationRunSummaryDto.model_validate(r) for r in rows],
        total=total,
        page=paging.page,
        page_size=paging.page_size,
    )


@router.get(
    "/balance-verification/runs/{run_id}", response_model=VerificationRunDto, operation_id="getBalanceVerification"
)
def get_run(
    run_id: uuid.UUID, session: DbSession, _: Annotated[RequestContext, Depends(P.BALANCE_READ)]
) -> VerificationRunDto:
    run = session.get(BalanceVerificationRun, run_id)
    if run is None:
        raise NotFound("Verification run not found")
    return VerificationRunDto.model_validate(run)


# --- platform: counts only -------------------------------------------------------------------------------------------
@platform_router.get(
    "/balance-verification", response_model=Page[TenantVerificationDto], operation_id="listTenantBalanceVerifications"
)
def platform_overview(
    session: DbSession, _: Annotated[RequestContext, Depends(P.PLATFORM_BALANCE_READ)], paging: Paging
) -> Page[TenantVerificationDto]:
    stmt = select(Tenant).order_by(Tenant.display_name, Tenant.id)
    if (match := ilike_any(paging.q, Tenant.legal_name, Tenant.display_name)) is not None:
        stmt = stmt.where(match)
    tenants, total = paginate(session, stmt, paging)
    latest_at = (
        select(BalanceVerificationRun.tenant_id, func.max(BalanceVerificationRun.started_at).label("at"))
        .where(BalanceVerificationRun.tenant_id.in_([t.id for t in tenants]))
        .group_by(BalanceVerificationRun.tenant_id)
        .subquery()
    )
    runs = session.execute(
        select(BalanceVerificationRun).join(
            latest_at,
            (BalanceVerificationRun.tenant_id == latest_at.c.tenant_id)
            & (BalanceVerificationRun.started_at == latest_at.c.at),
        )
    ).scalars()
    by_tenant = {r.tenant_id: r for r in runs}
    items = [
        TenantVerificationDto(
            tenant_id=t.id,
            tenant_name=t.display_name,
            registration_number=t.registration_number,
            live_at=t.live_at,
            latest=VerificationRunSummaryDto.model_validate(by_tenant[t.id]) if t.id in by_tenant else None,
        )
        for t in tenants
    ]
    return Page(items=items, total=total, page=paging.page, page_size=paging.page_size)


@platform_router.post(
    "/tenants/{tenant_id}/balance-verification",
    response_model=VerificationRunSummaryDto,
    status_code=201,
    operation_id="runTenantBalanceVerification",
)
def platform_run(
    tenant_id: uuid.UUID,
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(P.PLATFORM_BALANCE_VERIFY)],
    now: Now,
) -> VerificationRunSummaryDto:
    """Runs a verification for one tenant; the platform sees the counts, the findings stay in the tenant's scope."""
    if session.get(Tenant, tenant_id) is None:
        raise NotFound("Tenant not found")
    apply_scope(session, DbScope.TENANT, tenant_id, ctx.user_id)
    run = run_verification(session, tenant_id, VerificationTrigger.PLATFORM, ctx.audit_actor(), ctx.user_id, now)
    return VerificationRunSummaryDto.model_validate(run)


@platform_router.post("/tenants/{tenant_id}/go-live", response_model=TenantDto, operation_id="markTenantLive")
def go_live(
    tenant_id: uuid.UUID,
    body: GoLiveIn,
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(P.GO_LIVE)],
    now: Now,
) -> TenantDto:
    """Marks a tenant live: from now on the data reset tool refuses it unless deliberately overridden on the server."""
    tenant = session.get(Tenant, tenant_id)
    if tenant is None:
        raise NotFound("Tenant not found")
    if tenant.status is TenantStatus.CLOSED:
        raise BusinessRuleViolation("A closed tenant cannot go live", code="TENANT_CLOSED")
    if tenant.live_at is not None:
        raise Conflict("This tenant is already marked live", code="TENANT_ALREADY_LIVE")
    if body.confirm_name != tenant.display_name:
        raise BusinessRuleViolation("The name typed does not match the tenant", code="CONFIRMATION_MISMATCH")
    tenant.live_at, tenant.live_marked_by, tenant.live_note = now, ctx.user_id, body.note
    AuditService(session).record(
        actor=ctx.audit_actor(),
        action="platform.tenant.go_live",
        entity_type="tenant",
        entity_id=tenant.id,
        tenant_id=tenant.id,
        before={"live_at": None},
        after={"live_at": now.isoformat(), "note": body.note},
    )
    session.flush()
    return TenantDto.model_validate(tenant)
