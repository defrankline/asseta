"""Administration -> Close company (tenant) and Tenants -> Deletion requests (platform)."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from asseta.core.clock import get_now
from asseta.core.db import get_session
from asseta.core.errors import ERROR_RESPONSES, NotFound
from asseta.core.paging import Page, PageParams, page_params, paginate
from asseta.modules.dataprotection import permissions as P
from asseta.modules.dataprotection.closure_dto import (
    CompanyDeletionIn,
    CompanyDeletionRequestDto,
    CompanyDeletionStatusDto,
    DeletionReasonIn,
)
from asseta.modules.dataprotection.closure_service import ClosureService, list_query, to_dto
from asseta.modules.dataprotection.models import CompanyDeletionRequest, DeletionStatus
from asseta.modules.identity.principal import RequestContext

router = APIRouter(prefix="/api/v1/tenant/company", tags=["company-closure"], responses=ERROR_RESPONSES)
platform_router = APIRouter(
    prefix="/api/v1/platform/deletion-requests", tags=["platform-company-closure"], responses=ERROR_RESPONSES
)
DbSession = Annotated[Session, Depends(get_session)]
Now = Annotated[datetime, Depends(get_now)]


def _tid(ctx: RequestContext) -> uuid.UUID:
    assert ctx.tenant_id is not None
    return ctx.tenant_id


@router.get("/deletion-request", response_model=CompanyDeletionStatusDto, operation_id="getCompanyDeletion")
def get_status(
    session: DbSession, ctx: Annotated[RequestContext, Depends(P.COMPANY_CLOSE_VIEW)], now: Now
) -> CompanyDeletionStatusDto:
    """The company name to type, the waiting period, and the active (else latest) closure request."""
    return ClosureService(session, now).status(_tid(ctx))


@router.post(
    "/deletion-request",
    response_model=CompanyDeletionRequestDto,
    status_code=201,
    operation_id="requestCompanyDeletion",
)
def request_deletion(
    body: CompanyDeletionIn, session: DbSession, ctx: Annotated[RequestContext, Depends(P.COMPANY_CLOSE)], now: Now
) -> CompanyDeletionRequestDto:
    """Close the company: it turns read-only now and ALL its data is deleted after the platform-wide waiting period.
    `confirm_name` must equal the company's display name (case does not matter). Download the data export first."""
    row = ClosureService(session, now).request(ctx, body.confirm_name, body.reason)
    return to_dto(session, row)


@router.post("/deletion-request/cancel", response_model=CompanyDeletionRequestDto, operation_id="cancelCompanyDeletion")
def cancel_deletion(
    body: DeletionReasonIn, session: DbSession, ctx: Annotated[RequestContext, Depends(P.COMPANY_CLOSE)], now: Now
) -> CompanyDeletionRequestDto:
    """Cancel a requested closure before the deletion starts; normal access is restored."""
    row = ClosureService(session, now).cancel(ctx, body.reason)
    return to_dto(session, row)


# --- platform --------------------------------------------------------------------------------------------------------
@platform_router.get("", response_model=Page[CompanyDeletionRequestDto], operation_id="listCompanyDeletionRequests")
def list_requests(
    session: DbSession,
    _: Annotated[RequestContext, Depends(P.PLATFORM_DELETION_READ)],
    paging: Annotated[PageParams, Depends(page_params)],
    status: Annotated[DeletionStatus | None, Query()] = None,
) -> Page[CompanyDeletionRequestDto]:
    rows, total = paginate(session, list_query(status), paging)
    return Page(
        items=[to_dto(session, row) for row in rows],
        total=total,
        page=paging.page,
        page_size=paging.page_size,
    )


@platform_router.get(
    "/{request_id}", response_model=CompanyDeletionRequestDto, operation_id="getCompanyDeletionRequest"
)
def get_request(
    request_id: uuid.UUID, session: DbSession, _: Annotated[RequestContext, Depends(P.PLATFORM_DELETION_READ)]
) -> CompanyDeletionRequestDto:
    row = session.get(CompanyDeletionRequest, request_id)
    if row is None:
        raise NotFound("Deletion request not found")
    return to_dto(session, row)


@platform_router.post(
    "/{request_id}/execute", response_model=CompanyDeletionRequestDto, operation_id="executeCompanyDeletionNow"
)
def execute_now(
    request_id: uuid.UUID,
    body: DeletionReasonIn,
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(P.PLATFORM_DELETION_EXECUTE)],
    now: Now,
) -> CompanyDeletionRequestDto:
    """Run the deletion before the waiting period ends, only when the owner asked for it in writing (say so in the
    reason). The data protection worker starts it within a minute; audited."""
    row = ClosureService(session, now).execute_now(request_id, ctx, body.reason)
    return to_dto(session, row)
