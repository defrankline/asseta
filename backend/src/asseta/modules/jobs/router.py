"""Tenant customers, rate cards, contracts, jobs, work logs and acknowledgements."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.db import get_session
from asseta.core.errors import ERROR_RESPONSES, PermissionDenied
from asseta.core.idempotency import IdempotencyGuard, request_hash
from asseta.core.lifecycle import IncludeInactive, LifecycleChangeIn
from asseta.core.paging import Page, PageParams, page_params, paginate
from asseta.core.search import ilike_any
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
    ContractUpdateIn,
    CustomerDto,
    CustomerIn,
    CustomerUpdateIn,
    JobDto,
    JobIn,
    JobSummaryDto,
    JobTransitionIn,
    JobUpdateIn,
    RateCardDto,
    RateCardIn,
)
from asseta.modules.jobs.lifecycle import RecordLifecycleService, customer_query, job_list_query
from asseta.modules.jobs.models import (
    ContractStatus,
    CustomerAcknowledgement,
    JobActivity,
    JobStatus,
    RentalContract,
    RentalRatePolicy,
)
from asseta.modules.jobs.service import JobService

CUSTOMER_READ = requires("tenant.customer.read", S.TENANT, "View customers and contracts")
CUSTOMER_WRITE = requires("tenant.customer.write", S.TENANT, "Manage customers, contracts and rate cards")
JOB_READ = requires("tenant.job.read", S.TENANT, "View jobs, work logs and job summaries")
JOB_WRITE = requires("tenant.job.write", S.TENANT, "Create jobs and submit them for approval")
JOB_APPROVE = requires("tenant.job.approve", S.TENANT, "Approve job prices and authorize start/completion")
JOB_LOG = requires("tenant.job.log", S.TENANT, "Record work logs, start/stop and customer acknowledgements")
for menu in (
    MenuDef(
        "tenant.customers",
        S.TENANT,
        "Customers",
        "/tenant/customers",
        25,
        "tenant.customer.read",
        group="tenant.operations",
    ),
    MenuDef("tenant.jobs", S.TENANT, "Jobs", "/tenant/jobs", 15, "tenant.job.read", group="tenant.operations"),
):
    CATALOG.register_menu(menu)

router = APIRouter(prefix="/api/v1/tenant", tags=["jobs"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]
CustomerRead = Annotated[RequestContext, Depends(CUSTOMER_READ)]
CustomerWrite = Annotated[RequestContext, Depends(CUSTOMER_WRITE)]


@router.post("/customers", response_model=CustomerDto, status_code=201, operation_id="createCustomer")
def create_customer(
    body: CustomerIn, session: DbSession, ctx: Annotated[RequestContext, Depends(CUSTOMER_WRITE)]
) -> CustomerDto:
    return JobService(session, ctx).create_customer(body)


@router.get("/customers", response_model=Page[CustomerDto], operation_id="listCustomers")
def customers(
    session: DbSession,
    _: CustomerRead,
    paging: Annotated[PageParams, Depends(page_params)],
    include_inactive: IncludeInactive = False,
) -> Page[CustomerDto]:
    rows, total = paginate(session, customer_query(paging.q, include_inactive), paging)
    return Page(
        items=[CustomerDto.model_validate(c) for c in rows], total=total, page=paging.page, page_size=paging.page_size
    )


@router.get("/customers/{customer_id}", response_model=CustomerDto, operation_id="getCustomer")
def get_customer(customer_id: uuid.UUID, session: DbSession, ctx: CustomerRead) -> CustomerDto:
    return RecordLifecycleService(session, ctx).customer(customer_id)


@router.put("/customers/{customer_id}", response_model=CustomerDto, operation_id="updateCustomer")
def update_customer(
    customer_id: uuid.UUID, body: CustomerUpdateIn, session: DbSession, ctx: CustomerWrite
) -> CustomerDto:
    return RecordLifecycleService(session, ctx).update_customer(customer_id, body)


@router.post("/customers/{customer_id}/deactivate", response_model=CustomerDto, operation_id="deactivateCustomer")
def deactivate_customer(
    customer_id: uuid.UUID, body: LifecycleChangeIn, session: DbSession, ctx: CustomerWrite
) -> CustomerDto:
    """Refused while the customer has open jobs (DRAFT..IN_PROGRESS); history and balances are kept."""
    return RecordLifecycleService(session, ctx).set_customer_active(customer_id, False, body.reason, body.version)


@router.post("/customers/{customer_id}/reactivate", response_model=CustomerDto, operation_id="reactivateCustomer")
def reactivate_customer(
    customer_id: uuid.UUID, body: LifecycleChangeIn, session: DbSession, ctx: CustomerWrite
) -> CustomerDto:
    return RecordLifecycleService(session, ctx).set_customer_active(customer_id, True, body.reason, body.version)


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
    _: CustomerRead,
    paging: Annotated[PageParams, Depends(page_params)],
    customer_id: uuid.UUID | None = None,
    status: ContractStatus | None = None,
    include_inactive: IncludeInactive = False,
) -> Page[ContractDto]:
    """CLOSED contracts are hidden unless `include_inactive` or `status=CLOSED` is given."""
    stmt = select(RentalContract).order_by(RentalContract.starts_on.desc())
    if customer_id:
        stmt = stmt.where(RentalContract.customer_id == customer_id)
    if status:
        stmt = stmt.where(RentalContract.status == status)
    elif not include_inactive:
        stmt = stmt.where(RentalContract.status != ContractStatus.CLOSED)
    if (match := ilike_any(paging.q, RentalContract.contract_number, RentalContract.reference)) is not None:
        stmt = stmt.where(match)
    rows, total = paginate(session, stmt, paging)
    return Page(
        items=[ContractDto.model_validate(c) for c in rows], total=total, page=paging.page, page_size=paging.page_size
    )


@router.get("/contracts/{contract_id}", response_model=ContractDto, operation_id="getContract")
def get_contract(contract_id: uuid.UUID, session: DbSession, ctx: CustomerRead) -> ContractDto:
    return RecordLifecycleService(session, ctx).contract(contract_id)


@router.put("/contracts/{contract_id}", response_model=ContractDto, operation_id="updateContract")
def update_contract(
    contract_id: uuid.UUID, body: ContractUpdateIn, session: DbSession, ctx: CustomerWrite
) -> ContractDto:
    """Editable while DRAFT/ACTIVE; CLOSED contracts must be reopened first (CONTRACT_CLOSED)."""
    return RecordLifecycleService(session, ctx).update_contract(contract_id, body)


@router.post("/contracts/{contract_id}/close", response_model=ContractDto, operation_id="closeContract")
def close_contract(
    contract_id: uuid.UUID, body: LifecycleChangeIn, session: DbSession, ctx: CustomerWrite
) -> ContractDto:
    """Status CLOSED; refused while the contract has open jobs (DRAFT..IN_PROGRESS)."""
    return RecordLifecycleService(session, ctx).set_contract_open(contract_id, False, body.reason, body.version)


@router.post("/contracts/{contract_id}/reopen", response_model=ContractDto, operation_id="reopenContract")
def reopen_contract(
    contract_id: uuid.UUID, body: LifecycleChangeIn, session: DbSession, ctx: CustomerWrite
) -> ContractDto:
    """Back to ACTIVE; the customer must be active."""
    return RecordLifecycleService(session, ctx).set_contract_open(contract_id, True, body.reason, body.version)


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
    rows, total = paginate(session, job_list_query(paging.q, status, machine_id), paging)
    return Page(
        items=[JobDto.model_validate(j) for j in rows], total=total, page=paging.page, page_size=paging.page_size
    )


@router.get("/jobs/{job_id}", response_model=JobSummaryDto, operation_id="getJobSummary")
def job_summary(
    job_id: uuid.UUID, session: DbSession, ctx: Annotated[RequestContext, Depends(JOB_READ)]
) -> JobSummaryDto:
    return JobService(session, ctx).summary(job_id)


@router.put("/jobs/{job_id}", response_model=JobDto, operation_id="updateJob")
def update_job(
    job_id: uuid.UUID, body: JobUpdateIn, session: DbSession, ctx: Annotated[RequestContext, Depends(JOB_WRITE)]
) -> JobDto:
    """Edit a DRAFT/PENDING_APPROVAL job (optimistic `version`); approved and later jobs are locked (JOB_LOCKED).
    Cancel through the CANCEL transition."""
    return RecordLifecycleService(session, ctx).update_job(job_id, body)


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


@router.get("/rate-cards", response_model=list[RateCardDto], operation_id="listRateCards")
def rate_cards(
    session: DbSession,
    _: Annotated[RequestContext, Depends(CUSTOMER_READ)],
    machine_category_id: uuid.UUID | None = None,
) -> list[RateCardDto]:
    """All versions, newest first; the effective card for a time is the latest with effective_from <= time."""
    stmt = select(RentalRatePolicy).order_by(
        RentalRatePolicy.machine_category_id, RentalRatePolicy.effective_from.desc()
    )
    if machine_category_id:
        stmt = stmt.where(RentalRatePolicy.machine_category_id == machine_category_id)
    return [RateCardDto.model_validate(r) for r in session.execute(stmt).scalars()]


@router.get(
    "/jobs/{job_id}/acknowledgements", response_model=list[AcknowledgementDto], operation_id="listJobAcknowledgements"
)
def acknowledgements(
    job_id: uuid.UUID, session: DbSession, ctx: Annotated[RequestContext, Depends(JOB_READ)]
) -> list[AcknowledgementDto]:
    JobService(session, ctx).job(job_id)
    rows = session.execute(
        select(CustomerAcknowledgement)
        .where(CustomerAcknowledgement.job_id == job_id)
        .order_by(CustomerAcknowledgement.captured_at)
    ).scalars()
    return [AcknowledgementDto.model_validate(a) for a in rows]
