"""Customer, contract and job record lifecycle: details, edits with optimistic versions, customer deactivation,
contract close/reopen and pre-approval job edits. Nothing is hard-deleted; every change is audited."""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.db import utcnow
from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound
from asseta.core.lifecycle import check_version, flush_versioned, mark_active, mark_inactive
from asseta.core.outbox import OutboxWriter
from asseta.core.search import ilike_any
from asseta.modules.fleet.models import Machine, MachineStatus, StaffMember
from asseta.modules.geospatial.models import JobSite
from asseta.modules.identity.principal import RequestContext
from asseta.modules.jobs.dto import (
    ContractDto,
    ContractUpdateIn,
    CustomerDto,
    CustomerUpdateIn,
    JobDto,
    JobTermsIn,
    JobUpdateIn,
)
from asseta.modules.jobs.models import (
    ContractStatus,
    Customer,
    Job,
    JobStatus,
    RentalContract,
    RentalRatePolicy,
)

TOPIC = "asseta.jobs"
OPEN_JOB_STATES = (JobStatus.DRAFT, JobStatus.PENDING_APPROVAL, JobStatus.APPROVED, JobStatus.IN_PROGRESS)
EDITABLE_JOB_STATES = (JobStatus.DRAFT, JobStatus.PENDING_APPROVAL)


def check_job_refs(session: Session, body: JobTermsIn, current: Job | None = None) -> Machine:
    """A job may only (newly) reference a machine in service, an active site and an active supervisor."""
    machine = session.get(Machine, body.machine_id)
    if machine is None:
        raise NotFound("Machine not found")
    if machine.status is MachineStatus.DISPOSED:
        raise BusinessRuleViolation("Machine is retired", code="MACHINE_INACTIVE")
    if body.job_site_id and (current is None or current.job_site_id != body.job_site_id):
        site = session.get(JobSite, body.job_site_id)
        if site is None:
            raise NotFound("Job site not found")
        if not site.is_active:
            raise BusinessRuleViolation("Job site is deactivated", code="SITE_INACTIVE")
    if body.supervisor_id and (current is None or current.supervisor_id != body.supervisor_id):
        staff = session.get(StaffMember, body.supervisor_id)
        if staff is None:
            raise NotFound("Supervisor not found")
        if not staff.is_active:
            raise BusinessRuleViolation("Supervisor is deactivated", code="STAFF_INACTIVE")
    return machine


def check_active_customer(session: Session, customer_id: uuid.UUID) -> Customer:
    customer = session.get(Customer, customer_id)
    if customer is None:
        raise NotFound("Customer not found")
    if not customer.is_active:
        raise BusinessRuleViolation("Customer is deactivated", code="CUSTOMER_INACTIVE")
    return customer


def customer_query(q: str | None, include_inactive: bool) -> Select[Customer]:
    stmt = select(Customer).order_by(Customer.name)
    if (match := ilike_any(q, Customer.name, Customer.code)) is not None:
        stmt = stmt.where(match)
    return stmt if include_inactive else stmt.where(Customer.is_active.is_(True))


class RecordLifecycleService:
    def __init__(self, session: Session, ctx: RequestContext):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid = session, ctx, ctx.tenant_id
        self._audit = AuditService(session)

    def _record(
        self, action: str, entity: str, entity_id: uuid.UUID, before: Any, after: Any, reason: str | None = None
    ) -> None:
        self._audit.record(
            actor=self._ctx.audit_actor(),
            action=action,
            entity_type=entity,
            entity_id=entity_id,
            tenant_id=self._tid,
            before=before,
            after=after,
            reason=reason,
        )

    def _get[T](self, model: type[T], row_id: uuid.UUID, label: str) -> T:
        id_col: Any = model.id  # type: ignore[attr-defined]
        row = self._s.execute(select(model).where(id_col == row_id).with_for_update()).scalar_one_or_none()
        if row is None:  # other tenants' rows are invisible under RLS
            raise NotFound(f"{label} not found")
        return row

    # --- customers ----------------------------------------------------------------------------------
    def customer(self, customer_id: uuid.UUID) -> CustomerDto:
        return CustomerDto.model_validate(self._get(Customer, customer_id, "Customer"))

    def update_customer(self, customer_id: uuid.UUID, body: CustomerUpdateIn) -> CustomerDto:
        c = self._get(Customer, customer_id, "Customer")
        check_version(c.version, body.version, "Customer")
        before = CustomerDto.model_validate(c).model_dump(mode="json")
        for key, value in body.model_dump(exclude={"version"}).items():
            setattr(c, key, value)
        flush_versioned(self._s, "Customer", "DUPLICATE_CUSTOMER", "Customer code already exists")
        dto = CustomerDto.model_validate(c)
        self._record("jobs.customer.updated", "customer", c.id, before, dto.model_dump(mode="json"))
        return dto

    def set_customer_active(
        self, customer_id: uuid.UUID, active: bool, reason: str, version: int | None
    ) -> CustomerDto:
        """Deactivation is refused while any job for the customer is open (draft through in progress); contracts,
        invoices and payments keep their history and the balance stays collectable."""
        c = self._get(Customer, customer_id, "Customer")
        check_version(c.version, version, "Customer")
        if active:
            mark_active(c, "Customer")
        else:
            open_job = self._s.execute(
                select(Job.id)
                .join(RentalContract, RentalContract.id == Job.contract_id)
                .where(RentalContract.customer_id == c.id, Job.status.in_(OPEN_JOB_STATES))
            ).first()
            if open_job is not None:
                raise BusinessRuleViolation(
                    "Customer has open jobs; complete or cancel them first", code="CUSTOMER_HAS_OPEN_JOBS"
                )
            mark_inactive(c, self._ctx.user_id, reason, "Customer")
        flush_versioned(self._s, "Customer")
        dto = CustomerDto.model_validate(c)
        verb = "reactivated" if active else "deactivated"
        self._record(f"jobs.customer.{verb}", "customer", c.id, None, dto.model_dump(mode="json"), reason)
        return dto

    # --- contracts ----------------------------------------------------------------------------------
    def contract(self, contract_id: uuid.UUID) -> ContractDto:
        return ContractDto.model_validate(self._get(RentalContract, contract_id, "Contract"))

    def update_contract(self, contract_id: uuid.UUID, body: ContractUpdateIn) -> ContractDto:
        c = self._get(RentalContract, contract_id, "Contract")
        check_version(c.version, body.version, "Contract")
        if c.status is ContractStatus.CLOSED:
            raise BusinessRuleViolation("Closed contracts are read-only; reopen it first", code="CONTRACT_CLOSED")
        if body.ends_on is not None and body.ends_on < body.starts_on:
            raise BusinessRuleViolation("Contract cannot end before it starts", code="CONTRACT_DATES")
        if body.job_site_id and body.job_site_id != c.job_site_id:
            site = self._s.get(JobSite, body.job_site_id)
            if site is None:
                raise NotFound("Job site not found")
            if not site.is_active:
                raise BusinessRuleViolation("Job site is deactivated", code="SITE_INACTIVE")
        before = ContractDto.model_validate(c).model_dump(mode="json")
        for key, value in body.model_dump(exclude={"version"}).items():
            setattr(c, key, value)
        flush_versioned(self._s, "Contract", "DUPLICATE_CONTRACT", "Contract number already exists")
        dto = ContractDto.model_validate(c)
        self._record("jobs.contract.updated", "rental_contract", c.id, before, dto.model_dump(mode="json"))
        return dto

    def set_contract_open(self, contract_id: uuid.UUID, open_: bool, reason: str, version: int | None) -> ContractDto:
        """Close (status CLOSED) is refused while the contract has open jobs; reopen needs an active customer."""
        c = self._get(RentalContract, contract_id, "Contract")
        check_version(c.version, version, "Contract")
        before = {"status": c.status.value}
        if open_:
            if c.status is not ContractStatus.CLOSED:
                raise Conflict("Contract is not closed", code="ALREADY_ACTIVE")
            check_active_customer(self._s, c.customer_id)
            c.status, c.closed_at, c.closed_by, c.close_reason = ContractStatus.ACTIVE, None, None, None
        else:
            if c.status is ContractStatus.CLOSED:
                raise Conflict("Contract is already closed", code="ALREADY_INACTIVE")
            if self._s.execute(select(Job.id).where(Job.contract_id == c.id, Job.status.in_(OPEN_JOB_STATES))).first():
                raise BusinessRuleViolation(
                    "Contract has open jobs; complete or cancel them first", code="CONTRACT_HAS_OPEN_JOBS"
                )
            c.status, c.closed_at, c.closed_by, c.close_reason = (
                ContractStatus.CLOSED,
                utcnow(),
                self._ctx.user_id,
                reason,
            )
        flush_versioned(self._s, "Contract")
        dto = ContractDto.model_validate(c)
        verb = "reopened" if open_ else "closed"
        self._record(f"jobs.contract.{verb}", "rental_contract", c.id, before, {"status": c.status.value}, reason)
        return dto

    # --- jobs ---------------------------------------------------------------------------------------
    def update_job(self, job_id: uuid.UUID, body: JobUpdateIn) -> JobDto:
        """Pre-approval edit of terms/machine/site/supervisor/dates; the price is re-derived like at creation."""
        job = self._get(Job, job_id, "Job")
        check_version(job.version, body.version, "Job")
        if job.status not in EDITABLE_JOB_STATES:
            raise BusinessRuleViolation(f"A job in {job.status.value} can no longer be edited", code="JOB_LOCKED")
        machine = check_job_refs(self._s, body, job)
        contract = self._s.get(RentalContract, job.contract_id)
        assert contract is not None
        if body.hourly_rate is not None:
            rate, source = body.hourly_rate, "NEGOTIATED"
            card = None
        else:
            card = self._rate_card(machine.category_id, body)
            if card is None:
                raise BusinessRuleViolation(
                    "No rate card for this machine category; provide a negotiated hourly_rate", code="NO_RATE"
                )
            rate, source = card.hourly_rate, f"RATE_CARD:{card.id}"
        minimum = body.minimum_hours if body.minimum_hours is not None else (card.minimum_hours if card else Decimal(0))
        before = JobDto.model_validate(job).model_dump(mode="json")
        for key, value in body.model_dump(exclude={"version", "hourly_rate", "minimum_hours"}).items():
            setattr(job, key, value)
        job.job_site_id = body.job_site_id or contract.job_site_id
        job.hourly_rate, job.minimum_hours, job.rate_source = rate, minimum, source
        flush_versioned(self._s, "Job")
        dto = JobDto.model_validate(job)
        self._record("jobs.job.updated", "job", job.id, before, dto.model_dump(mode="json"))
        OutboxWriter(self._s).emit(
            topic=TOPIC,
            event_type="JobUpdated",
            key=str(job.machine_id),
            payload={"job_id": str(job.id), "status": job.status.value, "version": job.version},
            tenant_id=self._tid,
        )
        return dto

    def _rate_card(self, category_id: uuid.UUID | None, body: JobTermsIn) -> RentalRatePolicy | None:
        if category_id is None:
            return None
        return self._s.execute(
            select(RentalRatePolicy)
            .where(
                RentalRatePolicy.machine_category_id == category_id,
                RentalRatePolicy.effective_from <= body.planned_start,
            )
            .order_by(RentalRatePolicy.effective_from.desc())
            .limit(1)
        ).scalar_one_or_none()
