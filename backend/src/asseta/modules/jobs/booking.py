"""Sell hours and book the job in one step. The sale's job is an ordinary field job request (billed from the prepaid
hours, PENDING_APPROVAL, requested by the caller's staff record) linked to the purchase. The contract is the one given,
else the customer's only active contract (for the site when one is given), else - when the tenant's CUSTOMER_HOURS
policy allows it - a standard contract for a walk-in customer who has none. Approval follows the money when the tenant
switches prepaid_job_auto_approval on: once every hour of the sale is active, the system approves the job with the
same checks a person's approval runs (`approve_by_policy`), or leaves it pending and tells the job approvers why."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.errors import BusinessRuleViolation, NotFound, PermissionDenied
from asseta.core.outbox import OutboxWriter
from asseta.modules.finance.common import tenant_settings
from asseta.modules.finance.references import reference
from asseta.modules.geospatial.models import JobSite
from asseta.modules.hours.dto import BookedJobDto, SaleJobIn
from asseta.modules.hours.models import HoursPurchase
from asseta.modules.identity.principal import RequestContext
from asseta.modules.jobs.dto import ContractDto, JobRequestIn
from asseta.modules.jobs.models import ContractStatus, Customer, CustomerKind, Job, JobStatus, RentalContract
from asseta.modules.jobs.service import SYSTEM_POLICY_ACTOR, TOPIC, JobService, approve_by_policy
from asseta.modules.policy.schemas import BillingMode, CustomerHoursPolicy

JOB_REQUEST_PERMISSION = "tenant.job.request"
STANDARD_CONTRACT_SERIES = "CON"
HELD_REASONS = {
    "MACHINE_BUSY": "the machine has another approved or running job in that period",
    "PRICE_REQUIRED": "the job has no price yet",
}


@dataclass(frozen=True)
class ContractPlan:
    contract: RentalContract | None  # None: a standard contract is created with the sale
    site_id: uuid.UUID | None


def job_id_for(client_id: uuid.UUID | None) -> uuid.UUID:
    """The booked job's id: derived from the sale's client id, so an offline retry books exactly one job."""
    return uuid.uuid5(client_id, "job") if client_id is not None else uuid.uuid4()


def booked_job(session: Session, purchase_id: uuid.UUID) -> BookedJobDto | None:
    row = session.execute(
        select(Job, RentalContract.contract_number)
        .join(RentalContract, RentalContract.id == Job.contract_id)
        .where(Job.hours_purchase_id == purchase_id)
        .order_by(Job.created_at)
        .limit(1)
    ).first()
    if row is None:
        return None
    job, number = row
    return BookedJobDto(
        id=job.id,
        job_number=job.job_number,
        status=job.status.value,
        contract_id=job.contract_id,
        contract_number=number,
        planned_start=job.planned_start,
        planned_end=job.planned_end,
        approved_at=job.approved_at,
    )


class SaleBooking:
    def __init__(self, session: Session, ctx: RequestContext, now: datetime, policy: CustomerHoursPolicy):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid, self._now, self._policy = session, ctx, ctx.tenant_id, now, policy

    def check_permission(self) -> None:
        if JOB_REQUEST_PERMISSION not in self._ctx.permissions:
            raise PermissionDenied(
                f"Booking a job with the sale needs {JOB_REQUEST_PERMISSION}", code="JOB_REQUEST_NOT_PERMITTED"
            )

    def plan(self, customer: Customer, body: SaleJobIn, sale_site_id: uuid.UUID | None) -> ContractPlan:
        """Which contract the job goes under; refused before anything is written."""
        site_id = body.job_site_id or sale_site_id
        if body.job_site_id is not None:  # the sale's own site is checked with the sale
            site = self._s.get(JobSite, body.job_site_id)
            if site is None:
                raise NotFound("Job site not found")
            if not site.is_active:
                raise BusinessRuleViolation("Job site is deactivated", code="SITE_INACTIVE")
        if body.contract_id is not None:
            contract = self._s.get(RentalContract, body.contract_id)
            if contract is None or contract.status is not ContractStatus.ACTIVE:
                raise BusinessRuleViolation("Contract not found or not active", code="CONTRACT_NOT_ACTIVE")
            if contract.customer_id != customer.id:
                raise BusinessRuleViolation(
                    "The contract belongs to another customer", code="CONTRACT_CUSTOMER_MISMATCH"
                )
            return ContractPlan(contract, site_id)
        active = list(
            self._s.execute(
                select(RentalContract)
                .where(RentalContract.customer_id == customer.id, RentalContract.status == ContractStatus.ACTIVE)
                .order_by(RentalContract.starts_on, RentalContract.contract_number)
            ).scalars()
        )
        if site_id is not None:
            exact = [c for c in active if c.job_site_id == site_id]
            candidates = exact or [c for c in active if c.job_site_id is None]
        else:
            candidates = active
        if len(candidates) == 1:
            return ContractPlan(candidates[0], site_id)
        if not active and customer.kind is CustomerKind.WALK_IN and self._policy.walk_in_standard_contract:
            return ContractPlan(None, site_id)
        if len(candidates) > 1:
            raise BusinessRuleViolation(
                "This customer has more than one active contract; choose the contract for the job",
                code="CONTRACT_CHOICE_REQUIRED",
            )
        raise BusinessRuleViolation(
            "This customer has no contract yet; the office creates one", code="CONTRACT_REQUIRED"
        )

    def _standard_contract(self, purchase: HoursPurchase, site_id: uuid.UUID | None) -> RentalContract:
        """A standard contract for a walk-in (tenant policy): rate card prices, starting today (tenant-local day)."""
        settings = tenant_settings(self._s, self._tid)
        tz = ZoneInfo(settings.timezone)
        starts = datetime.combine(self._now.astimezone(tz).date(), time.min, tz).astimezone(UTC)
        number = reference(self._s, self._tid, STANDARD_CONTRACT_SERIES, self._now)
        while self._s.execute(
            select(RentalContract.id).where(RentalContract.contract_number == number)
        ).first():  # an office-typed number already took it: the series moves on
            number = reference(self._s, self._tid, STANDARD_CONTRACT_SERIES, self._now)
        contract = RentalContract(
            id=uuid.uuid5(purchase.id, "contract"),
            tenant_id=self._tid,
            customer_id=purchase.customer_id,
            contract_number=number,
            job_site_id=site_id,
            currency=settings.currency,
            status=ContractStatus.ACTIVE,
            starts_on=starts,
            reference=purchase.purchase_number,
            notes=f"Standard contract created with hours sale {purchase.purchase_number} (tenant policy)",
        )
        self._s.add(contract)
        self._s.flush()
        AuditService(self._s).record(
            actor=self._ctx.audit_actor(),
            action="jobs.contract.created",
            entity_type="rental_contract",
            entity_id=contract.id,
            tenant_id=self._tid,
            after={
                **ContractDto.model_validate(contract).model_dump(mode="json"),
                "hours_purchase_id": str(purchase.id),
            },
            reason=f"Standard contract for a walk-in customer, created with hours sale {purchase.purchase_number}",
        )
        return contract

    def book(self, purchase: HoursPurchase, body: SaleJobIn, plan: ContractPlan) -> uuid.UUID:
        contract = plan.contract or self._standard_contract(purchase, plan.site_id)
        request = JobRequestIn(
            client_id=job_id_for(purchase.client_id),
            contract_id=contract.id,
            machine_id=purchase.machine_id,
            job_site_id=plan.site_id,
            planned_start=body.planned_start,
            planned_end=body.planned_end,
            note=body.note,
            billing_mode=BillingMode.PREPAID_HOURS,
        )
        dto = JobService(self._s, self._ctx).request_job(request, hours_purchase_id=purchase.id)
        return dto.id


def auto_approve_booked(session: Session, tenant_id: uuid.UUID, purchase: HoursPurchase, now: datetime) -> None:
    """The sale is fully active and the tenant lets approval follow the money: approve the jobs booked with it. A job
    the checks refuse stays pending and the job approvers are told why, in neutral words."""
    jobs = list(
        session.execute(
            select(Job)
            .where(Job.hours_purchase_id == purchase.id, Job.status == JobStatus.PENDING_APPROVAL)
            .order_by(Job.id)
            .with_for_update()
        ).scalars()
    )
    for job in jobs:
        code = approve_by_policy(session, tenant_id, job, now)
        if code is None:
            continue
        why = HELD_REASONS.get(code, code)
        AuditService(session).record(
            actor=SYSTEM_POLICY_ACTOR,
            action="jobs.job.auto_approval_held",
            entity_type="job",
            entity_id=job.id,
            tenant_id=tenant_id,
            after={"status": job.status.value, "code": code, "hours_purchase_id": str(purchase.id)},
            reason=f"Not approved automatically: {why}",
        )
        OutboxWriter(session).emit(
            topic=TOPIC,
            event_type="JobAutoApprovalHeld",
            key=str(job.machine_id),
            payload={
                "job_id": str(job.id),
                "job_number": job.job_number,
                "purchase_id": str(purchase.id),
                "purchase_number": purchase.purchase_number,
                "code": code,
                "reason": why,
            },
            tenant_id=tenant_id,
        )
