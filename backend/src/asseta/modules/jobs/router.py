"""Tenant customers, rate cards, contracts, jobs, work logs and acknowledgements."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from asseta.core.db import get_session
from asseta.core.errors import ERROR_RESPONSES, PermissionDenied
from asseta.core.idempotency import IdempotencyGuard, request_hash
from asseta.core.paging import Page, PageParams, page_params, paginate
from asseta.modules.identity.catalog import CATALOG, MenuDef
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.dependencies import requires
from asseta.modules.identity.principal import RequestContext
from asseta.modules.jobs.dto import (
    AcknowledgementDto,
    AcknowledgementIn,
    ActivityDto,
    ActivityIn,
    ContractDto,
    ContractIn,
    CustomerDto,
    CustomerIn,
    JobDto,
    JobIn,
    JobSummaryDto,
    JobTransitionIn,
    RateCardDto,
    RateCardIn,
)
from asseta.modules.jobs.models import Customer, Job, JobActivity, JobStatus, RentalContract
from asseta.modules.jobs.service import JobService

CUSTOMER_READ = requires("tenant.customer.read", S.TENANT, "View customers and contracts")
CUSTOMER_WRITE = requires("tenant.customer.write", S.TENANT, "Manage customers, contracts and rate cards")
JOB_READ = requires("tenant.job.read", S.TENANT, "View jobs, work logs and job summaries")
JOB_WRITE = requires("tenant.job.write", S.TENANT, "Create jobs and submit them for approval")
JOB_APPROVE = requires("tenant.job.approve", S.TENANT, "Approve job prices and authorize start/completion")
JOB_LOG = requires("tenant.job.log", S.TENANT, "Record work logs, start/stop and customer acknowledgements")
for menu in (
    MenuDef("tenant.customers", S.TENANT, "Customers", "/tenant/customers", 65, "tenant.customer.read"),
    MenuDef("tenant.jobs", S.TENANT, "Jobs", "/tenant/jobs", 15, "tenant.job.read"),
):
    CATALOG.register_menu(menu)

router = APIRouter(prefix="/api/v1/tenant", tags=["jobs"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]


@router.post("/customers", response_model=CustomerDto, status_code=201, operation_id="createCustomer")
def create_customer(
    body: CustomerIn, session: DbSession, ctx: Annotated[RequestContext, Depends(CUSTOMER_WRITE)]
) -> CustomerDto:
    return JobService(session, ctx).create_customer(body)


@router.get("/customers", response_model=Page[CustomerDto], operation_id="listCustomers")
def customers(
    session: DbSession,
    _: Annotated[RequestContext, Depends(CUSTOMER_READ)],
    paging: Annotated[PageParams, Depends(page_params)],
) -> Page[CustomerDto]:
    stmt = select(Customer).order_by(Customer.name)
    if paging.q:
        stmt = stmt.where(or_(Customer.name.ilike(f"%{paging.q}%"), Customer.code.ilike(f"%{paging.q}%")))
    rows, total = paginate(session, stmt, paging)
    return Page(
        items=[CustomerDto.model_validate(c) for c in rows], total=total, page=paging.page, page_size=paging.page_size
    )


@router.post("/rate-cards", response_model=RateCardDto, status_code=201, operation_id="createRateCard")
def create_rate_card(
    body: RateCardIn, session: DbSession, ctx: Annotated[RequestContext, Depends(CUSTOMER_WRITE)]
) -> RateCardDto:
    return JobService(session, ctx).create_rate_card(body)


@router.post("/contracts", response_model=ContractDto, status_code=201, operation_id="createContract")
def create_contract(
    body: ContractIn, session: DbSession, ctx: Annotated[RequestContext, Depends(CUSTOMER_WRITE)]
) -> ContractDto:
    return JobService(session, ctx).create_contract(body)


@router.get("/contracts", response_model=Page[ContractDto], operation_id="listContracts")
def contracts(
    session: DbSession,
    _: Annotated[RequestContext, Depends(CUSTOMER_READ)],
    paging: Annotated[PageParams, Depends(page_params)],
    customer_id: uuid.UUID | None = None,
) -> Page[ContractDto]:
    stmt = select(RentalContract).order_by(RentalContract.starts_on.desc())
    if customer_id:
        stmt = stmt.where(RentalContract.customer_id == customer_id)
    rows, total = paginate(session, stmt, paging)
    return Page(
        items=[ContractDto.model_validate(c) for c in rows], total=total, page=paging.page, page_size=paging.page_size
    )


@router.post("/jobs", response_model=JobDto, status_code=201, operation_id="createJob")
def create_job(
    body: JobIn,
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(JOB_WRITE)],
    idempotency_key: Annotated[str | None, Header()] = None,
) -> JobDto:
    guard = IdempotencyGuard(session, str(ctx.tenant_id), "createJob", idempotency_key, request_hash(body))
    if (replay := guard.begin()) is not None:
        return JobDto.model_validate(replay)
    dto = JobService(session, ctx).create_job(body)
    guard.complete(dto, 201)
    return dto


@router.get("/jobs", response_model=Page[JobDto], operation_id="listJobs")
def jobs(
    session: DbSession,
    _: Annotated[RequestContext, Depends(JOB_READ)],
    paging: Annotated[PageParams, Depends(page_params)],
    status: JobStatus | None = None,
    machine_id: uuid.UUID | None = None,
) -> Page[JobDto]:
    stmt = select(Job).order_by(Job.planned_start.desc())
    if status:
        stmt = stmt.where(Job.status == status)
    if machine_id:
        stmt = stmt.where(Job.machine_id == machine_id)
    if paging.q:
        stmt = stmt.where(Job.job_number.ilike(f"%{paging.q}%"))
    rows, total = paginate(session, stmt, paging)
    return Page(
        items=[JobDto.model_validate(j) for j in rows], total=total, page=paging.page, page_size=paging.page_size
    )


@router.get("/jobs/{job_id}", response_model=JobSummaryDto, operation_id="getJobSummary")
def job_summary(
    job_id: uuid.UUID, session: DbSession, ctx: Annotated[RequestContext, Depends(JOB_READ)]
) -> JobSummaryDto:
    return JobService(session, ctx).summary(job_id)


@router.post("/jobs/{job_id}/transitions", response_model=JobDto, operation_id="transitionJob")
def transition(
    job_id: uuid.UUID, body: JobTransitionIn, session: DbSession, ctx: Annotated[RequestContext, Depends(JOB_READ)]
) -> JobDto:
    needed = {
        "SUBMIT": "tenant.job.write",
        "APPROVE": "tenant.job.approve",
        "CANCEL": "tenant.job.approve",
        "START": "tenant.job.log",
        "COMPLETE": "tenant.job.log",
    }[body.action]
    if needed not in ctx.permissions:  # per-action authorization (deny by default)
        raise PermissionDenied(f"Missing permission {needed}")
    return JobService(session, ctx).transition(job_id, body.action, body.reason)


@router.post("/jobs/{job_id}/activities", response_model=ActivityDto, status_code=201, operation_id="logJobActivity")
def log_activity(
    job_id: uuid.UUID, body: ActivityIn, session: DbSession, ctx: Annotated[RequestContext, Depends(JOB_LOG)]
) -> ActivityDto:
    return JobService(session, ctx).add_activity(job_id, body)


@router.get("/jobs/{job_id}/activities", response_model=list[ActivityDto], operation_id="listJobActivities")
def activities(
    job_id: uuid.UUID, session: DbSession, ctx: Annotated[RequestContext, Depends(JOB_READ)]
) -> list[ActivityDto]:
    JobService(session, ctx).job(job_id)
    rows = session.execute(
        select(JobActivity).where(JobActivity.job_id == job_id).order_by(JobActivity.started_at)
    ).scalars()
    return [ActivityDto.model_validate(a) for a in rows]


@router.post(
    "/jobs/{job_id}/acknowledgements", response_model=AcknowledgementDto, status_code=201, operation_id="acknowledgeJob"
)
def acknowledge(
    job_id: uuid.UUID, body: AcknowledgementIn, session: DbSession, ctx: Annotated[RequestContext, Depends(JOB_LOG)]
) -> AcknowledgementDto:
    return JobService(session, ctx).acknowledge(job_id, body)
