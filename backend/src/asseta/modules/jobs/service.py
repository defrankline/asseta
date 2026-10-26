"""Rental contract/job use cases (tenant scope). Job prices are owner-approved; jobs start only with an opening
reading and complete only with a closing reading and customer acknowledgement (readings at every job boundary)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import ColumnElement, Integer, cast, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.db import utcnow
from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound
from asseta.core.outbox import OutboxWriter
from asseta.modules.geospatial.models import JobSite
from asseta.modules.hours.engine import HoursEngine, resolve_billing_mode
from asseta.modules.identity.principal import RequestContext
from asseta.modules.jobs.charges import JobCharges, job_charges
from asseta.modules.jobs.dto import (
    AcknowledgementDto,
    AcknowledgementIn,
    ActivityDto,
    ActivityIn,
    ContractDto,
    ContractIn,
    CustomerDto,
    CustomerIn,
    JobChargeLineDto,
    JobChargesDto,
    JobDto,
    JobIn,
    JobRequestIn,
    JobSummaryDto,
    JobTermsIn,
    RateCardDto,
    RateCardIn,
)
from asseta.modules.jobs.lifecycle import check_active_customer, check_job_refs, job_dto
from asseta.modules.jobs.models import (
    ActivityType,
    ContractStatus,
    Customer,
    CustomerAcknowledgement,
    Job,
    JobActivity,
    JobStatus,
    RentalContract,
    RentalRatePolicy,
    StandbyTreatment,
)
from asseta.modules.jobs.scope import own_staff
from asseta.modules.meter.engine_hours import (
    billing_deduction_filter,
    ensure_job_can_complete,
    ensure_job_can_start,
    ensure_no_activity_overlap,
)
from asseta.modules.meter.models import CaptureState, ExceptionStatus, JobException, MeterCapture, ReadingKind
from asseta.modules.meter.rules import billable_hours
from asseta.modules.platform_billing.models_commercial import Currency
from asseta.modules.policy.schemas import BillingMode
from asseta.modules.policy.service import PolicyService
from asseta.modules.tenancy.models import TenantSettings

TOPIC = "asseta.jobs"
PENDING_PRICE = "PENDING_PRICE"  # field request with no applicable rate card: the approver sets the price
OWNER_APPROVED = "OWNER_APPROVED"  # price set by the approver at APPROVE
_TRANSITIONS: dict[str, tuple[set[JobStatus], JobStatus]] = {
    "SUBMIT": ({JobStatus.DRAFT}, JobStatus.PENDING_APPROVAL),
    "APPROVE": ({JobStatus.PENDING_APPROVAL}, JobStatus.APPROVED),
    "START": ({JobStatus.APPROVED}, JobStatus.IN_PROGRESS),
    "COMPLETE": ({JobStatus.IN_PROGRESS}, JobStatus.COMPLETED),
    "CANCEL": ({JobStatus.DRAFT, JobStatus.PENDING_APPROVAL, JobStatus.APPROVED}, JobStatus.CANCELLED),
}


def charges_dto(c: JobCharges) -> JobChargesDto:
    return JobChargesDto(
        currency=c.currency,
        lines=[
            JobChargeLineDto(
                kind=line.kind.value,
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                amount=line.amount,
            )
            for line in c.lines
        ],
        subtotal=c.subtotal,
        discount_total=c.discount_total,
        tax_total=c.tax_total,
        total=c.total,
    )


class JobService:
    def __init__(self, session: Session, ctx: RequestContext):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid = session, ctx, ctx.tenant_id
        self._audit = AuditService(session)

    def _insert(self, obj: Any, code: str, msg: str) -> None:
        try:
            with self._s.begin_nested():
                self._s.add(obj)
                self._s.flush()
        except IntegrityError as exc:
            raise Conflict(msg, code=code) from exc

    def _currency(self) -> str:
        settings = self._s.get(TenantSettings, self._tid)
        assert settings is not None
        return settings.currency

    # --- customers & rate cards ---------------------------------------------------------------------
    def create_customer(self, body: CustomerIn) -> CustomerDto:
        c = Customer(id=uuid.uuid4(), tenant_id=self._tid, **body.model_dump())
        self._insert(c, "DUPLICATE_CUSTOMER", "Customer code already exists")
        dto = CustomerDto.model_validate(c)
        self._audit.record(
            actor=self._ctx.audit_actor(),
            action="jobs.customer.created",
            entity_type="customer",
            entity_id=c.id,
            tenant_id=self._tid,
            after=dto.model_dump(mode="json"),
        )
        return dto

    def create_rate_card(self, body: RateCardIn) -> RateCardDto:
        effective = body.effective_from or utcnow()
        if effective < utcnow().replace(microsecond=0) and body.effective_from is not None:
            raise BusinessRuleViolation("Rate cards cannot be backdated", code="RATE_BACKDATED")
        row = RentalRatePolicy(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            machine_category_id=body.machine_category_id,
            effective_from=effective,
            hourly_rate=body.hourly_rate,
            minimum_hours=body.minimum_hours,
            currency=self._currency(),
            reason=body.reason,
            created_by=self._ctx.user_id,
        )
        self._insert(row, "DUPLICATE_RATE_CARD", "A rate card already starts at this instant")
        self._audit.record(
            actor=self._ctx.audit_actor(),
            action="jobs.rate_card.versioned",
            entity_type="rate_card",
            entity_id=row.id,
            tenant_id=self._tid,
            after={"hourly_rate": str(row.hourly_rate), "category": str(row.machine_category_id)},
            reason=body.reason,
        )
        return RateCardDto.model_validate(row)

    def _rate_card(self, category_id: uuid.UUID | None, at: datetime) -> RentalRatePolicy | None:
        if category_id is None:
            return None
        return self._s.execute(
            select(RentalRatePolicy)
            .where(RentalRatePolicy.machine_category_id == category_id, RentalRatePolicy.effective_from <= at)
            .order_by(RentalRatePolicy.effective_from.desc())
            .limit(1)
        ).scalar_one_or_none()

    # --- contracts & jobs ---------------------------------------------------------------------------
    def create_contract(self, body: ContractIn) -> ContractDto:
        check_active_customer(self._s, body.customer_id)
        if body.job_site_id:
            site = self._s.get(JobSite, body.job_site_id)
            if site is None:
                raise NotFound("Job site not found")
            if not site.is_active:
                raise BusinessRuleViolation("Job site is deactivated", code="SITE_INACTIVE")
        c = RentalContract(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            currency=self._currency(),
            status=ContractStatus.ACTIVE,
            **body.model_dump(),
        )
        self._insert(c, "DUPLICATE_CONTRACT", "Contract number already exists")
        dto = ContractDto.model_validate(c)
        self._audit.record(
            actor=self._ctx.audit_actor(),
            action="jobs.contract.created",
            entity_type="rental_contract",
            entity_id=c.id,
            tenant_id=self._tid,
            after=dto.model_dump(mode="json"),
        )
        return dto

    def job(self, job_id: uuid.UUID, lock: bool = False) -> Job:
        stmt = select(Job).where(Job.id == job_id)
        job = self._s.execute(stmt.with_for_update() if lock else stmt).scalar_one_or_none()
        if job is None:
            raise NotFound("Job not found")
        return job

    def create_job(self, body: JobIn) -> JobDto:
        contract = self._s.get(RentalContract, body.contract_id)
        if contract is None or contract.status is not ContractStatus.ACTIVE:
            raise BusinessRuleViolation("Contract not found or not active", code="CONTRACT_NOT_ACTIVE")
        check_active_customer(self._s, contract.customer_id)
        machine = check_job_refs(self._s, body)
        card = self._rate_card(machine.category_id, body.planned_start)
        if body.hourly_rate is not None:
            rate, source = body.hourly_rate, "NEGOTIATED"
        elif card is not None:
            rate, source = card.hourly_rate, f"RATE_CARD:{card.id}"
        else:
            raise BusinessRuleViolation(
                "No rate card for this machine category; provide a negotiated hourly_rate", code="NO_RATE"
            )
        minimum = body.minimum_hours if body.minimum_hours is not None else (card.minimum_hours if card else Decimal(0))
        data = body.model_dump(exclude={"hourly_rate", "minimum_hours", "billing_mode"})
        data["job_site_id"] = body.job_site_id or contract.job_site_id
        data["billing_mode"] = resolve_billing_mode(self._s, self._tid, body.billing_mode, utcnow())
        job = Job(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            status=JobStatus.DRAFT,
            currency=contract.currency,
            hourly_rate=rate,
            minimum_hours=minimum,
            rate_source=source,
            **data,
        )
        self._insert(job, "DUPLICATE_JOB", "Job number already exists")
        self._audit.record(
            actor=self._ctx.audit_actor(),
            action="jobs.job.created",
            entity_type="job",
            entity_id=job.id,
            tenant_id=self._tid,
            after=JobDto.model_validate(job).model_dump(mode="json"),
        )
        return JobDto.model_validate(job)

    def _next_job_number(self, year: int) -> str:
        """Next J-<year>-<nnn> for the tenant: one past the highest number in that series (office-entered numbers in
        the same format count too). A per-tenant transaction advisory lock serializes concurrent requests, and the
        unique (tenant, job_number) constraint stays the backstop."""
        self._s.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": f"job_number:{self._tid}"})
        prefix = f"J-{year}-"
        top = self._s.execute(
            select(func.max(cast(func.substring(Job.job_number, rf"^J-{year}-(\d{{1,9}})$"), Integer))).where(
                Job.job_number.like(f"{prefix}%")
            )
        ).scalar_one_or_none()
        return f"{prefix}{(top or 0) + 1:03d}"

    def request_job(self, body: JobRequestIn) -> JobDto:
        """A supervisor's field request: numbered and priced by the server, straight to PENDING_APPROVAL with the
        caller as supervisor. Replaying the same client_id returns the job already created (offline retries)."""
        existing = self._s.get(Job, body.client_id)
        if existing is not None:
            staff = own_staff(self._s, self._ctx)
            if existing.requested_by_staff_id is None or staff is None or existing.requested_by_staff_id != staff.id:
                raise Conflict("This id is already used by another job", code="DUPLICATE_JOB")
            return job_dto(self._s, existing)
        staff = own_staff(self._s, self._ctx)
        if staff is None:
            raise BusinessRuleViolation(
                "Your login is not linked to an active staff record; ask the owner to link it", code="NO_STAFF_RECORD"
            )
        contract = self._s.get(RentalContract, body.contract_id)
        if contract is None or contract.status is not ContractStatus.ACTIVE:
            raise BusinessRuleViolation("Contract not found or not active", code="CONTRACT_NOT_ACTIVE")
        check_active_customer(self._s, contract.customer_id)
        terms = JobTermsIn(
            machine_id=body.machine_id,
            job_site_id=body.job_site_id,
            supervisor_id=staff.id,
            planned_start=body.planned_start,
            planned_end=body.planned_end,
        )
        machine = check_job_refs(self._s, terms)
        card = self._rate_card(machine.category_id, body.planned_start)
        rate, source = (card.hourly_rate, f"RATE_CARD:{card.id}") if card else (Decimal(0), PENDING_PRICE)
        job = Job(
            id=body.client_id,
            tenant_id=self._tid,
            contract_id=contract.id,
            job_number=self._next_job_number(body.planned_start.year),
            machine_id=machine.id,
            job_site_id=body.job_site_id or contract.job_site_id,
            supervisor_id=staff.id,
            requested_by_staff_id=staff.id,
            request_note=body.note,
            status=JobStatus.PENDING_APPROVAL,
            planned_start=body.planned_start,
            planned_end=body.planned_end,
            currency=contract.currency,
            hourly_rate=rate,
            minimum_hours=card.minimum_hours if card else Decimal(0),
            standby_treatment=StandbyTreatment.EXCLUDED,
            standby_rate=None,
            mobilization_fee=Decimal(0),
            discount_percent=Decimal(0),
            tax_rate_percent=Decimal(0),
            rate_source=source,
            billing_mode=resolve_billing_mode(self._s, self._tid, body.billing_mode, utcnow()),
        )
        self._insert(job, "DUPLICATE_JOB", "Job number already exists")
        dto = job_dto(self._s, job)
        self._audit.record(
            actor=self._ctx.audit_actor(),
            action="jobs.job.requested",
            entity_type="job",
            entity_id=job.id,
            tenant_id=self._tid,
            after=dto.model_dump(mode="json"),
            reason=body.note,
        )
        self._emit(job, JobStatus.PENDING_APPROVAL, None)
        return dto

    def _emit(self, job: Job, status: JobStatus, reason: str | None) -> None:
        OutboxWriter(self._s).emit(
            topic=TOPIC,
            event_type=f"Job{status.value.title().replace('_', '')}",
            key=str(job.machine_id),
            payload={
                "job_id": str(job.id),
                "job_number": job.job_number,
                "status": status.value,
                "machine_id": str(job.machine_id),
                "job_site_id": str(job.job_site_id) if job.job_site_id else None,
                "supervisor_id": str(job.supervisor_id) if job.supervisor_id else None,
                "requested_by_staff_id": str(job.requested_by_staff_id) if job.requested_by_staff_id else None,
                "request_note": job.request_note,
                "reason": reason,
            },
            tenant_id=self._tid,
        )

    def transition(
        self, job_id: uuid.UUID, action: str, reason: str | None, hourly_rate: Decimal | None = None
    ) -> JobDto:
        job = self.job(job_id, lock=True)
        allowed, target = _TRANSITIONS[action]
        if job.status not in allowed:
            raise BusinessRuleViolation(f"Cannot {action} a job in {job.status.value}", code="INVALID_JOB_TRANSITION")
        if hourly_rate is not None and action != "APPROVE":
            raise BusinessRuleViolation("A price can only be set when approving", code="PRICE_NOT_ALLOWED")
        now = utcnow()
        price_before = None
        if action == "APPROVE":
            if hourly_rate is not None:
                price_before = {"hourly_rate": str(job.hourly_rate), "rate_source": job.rate_source}
                job.hourly_rate, job.rate_source = hourly_rate, OWNER_APPROVED
            elif job.rate_source == PENDING_PRICE:
                raise BusinessRuleViolation(
                    "This job has no price yet; give the hourly rate to approve it", code="PRICE_REQUIRED"
                )
            job.approved_by, job.approved_at = self._ctx.user_id, now
        elif action == "START":
            opening = self._reading(job.id, ReadingKind.OPENING)
            if opening is None:
                raise BusinessRuleViolation("An opening meter reading is required to start", code="OPENING_REQUIRED")
            ensure_job_can_start(self._s, self._tid, job, opening, now)
            HoursEngine(self._s, self._tid, self._ctx.audit_actor(), now).check_start(job)
            job.started_at = opening.captured_at
        elif action == "COMPLETE":
            closing = self._reading(job.id, ReadingKind.CLOSING)
            if closing is None:
                raise BusinessRuleViolation("A closing meter reading is required to complete", code="CLOSING_REQUIRED")
            if (
                self._s.execute(
                    select(CustomerAcknowledgement.id).where(CustomerAcknowledgement.job_id == job.id)
                ).first()
                is None
            ):
                raise BusinessRuleViolation("Customer acknowledgement is required to complete", code="ACK_REQUIRED")
            ensure_job_can_complete(self._s, self._tid, job, closing, now)
            job.completed_at = closing.captured_at
        elif action == "CANCEL":
            if not reason:
                raise BusinessRuleViolation("Cancellation reason required", code="REASON_REQUIRED")
            job.cancellation_reason = reason
        before = job.status.value
        job.status = target
        try:
            self._s.flush()
        except IntegrityError as exc:
            raise Conflict("Machine already has an approved or running job", code="MACHINE_BUSY") from exc
        if action == "COMPLETE":
            self._allocate_prepaid_hours(job, now)
        after: dict[str, Any] = {"status": target.value}
        if price_before is not None:
            after |= {"hourly_rate": str(job.hourly_rate), "rate_source": job.rate_source}
        self._audit.record(
            actor=self._ctx.audit_actor(),
            action=f"jobs.job.{action.lower()}",
            entity_type="job",
            entity_id=job.id,
            tenant_id=self._tid,
            before={"status": before, **(price_before or {})},
            after=after,
            reason=reason,
        )
        self._emit(job, target, reason)
        return job_dto(self._s, job)

    def _allocate_prepaid_hours(self, job: Job, now: datetime) -> None:
        """Work Execution Allocation of a completed PREPAID_HOURS job (no effect on INVOICE jobs)."""
        if job.billing_mode is not BillingMode.PREPAID_HOURS:
            return
        billable = self.summary(job.id).billable_hours or Decimal(0)
        HoursEngine(self._s, self._tid, self._ctx.audit_actor(), now).allocate_job(job, billable)

    def _reading(self, job_id: uuid.UUID, kind: ReadingKind) -> MeterCapture | None:
        return self._s.execute(
            select(MeterCapture).where(
                MeterCapture.job_id == job_id,
                MeterCapture.kind == kind,
                MeterCapture.state.in_([CaptureState.ACCEPTED, CaptureState.PROVISIONAL]),
            )
        ).scalar_one_or_none()

    # --- work log & acknowledgement -----------------------------------------------------------------
    def add_activity(self, job_id: uuid.UUID, body: ActivityIn) -> ActivityDto:
        existing = self._s.execute(
            select(JobActivity).where(JobActivity.client_id == body.client_id)
        ).scalar_one_or_none()
        if existing is not None:
            return ActivityDto.model_validate(existing)  # offline retry of the same operation
        job = self.job(job_id)
        if job.status not in (JobStatus.APPROVED, JobStatus.IN_PROGRESS, JobStatus.COMPLETED):
            raise BusinessRuleViolation("Work can only be logged on approved/running jobs", code="JOB_NOT_ACTIVE")
        ensure_no_activity_overlap(self._s, self._tid, job, body.activity_type.value, body.started_at, body.ended_at)
        billable = body.billable
        if billable is None:
            billable = body.activity_type is ActivityType.WORK or (
                body.activity_type is ActivityType.STANDBY and job.standby_treatment is StandbyTreatment.INCLUDED
            )
        row = JobActivity(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            job_id=job.id,
            billable=billable,
            recorded_by=self._ctx.user_id,
            **body.model_dump(exclude={"billable"}),
        )
        self._insert(row, "DUPLICATE_ACTIVITY", "Activity already recorded")
        return ActivityDto.model_validate(row)

    def acknowledge(self, job_id: uuid.UUID, body: AcknowledgementIn) -> AcknowledgementDto:
        existing = self._s.execute(
            select(CustomerAcknowledgement).where(CustomerAcknowledgement.client_id == body.client_id)
        ).scalar_one_or_none()
        if existing is not None:
            return AcknowledgementDto.model_validate(existing)
        self.job(job_id)
        row = CustomerAcknowledgement(
            id=uuid.uuid4(), tenant_id=self._tid, job_id=job_id, recorded_by=self._ctx.user_id, **body.model_dump()
        )
        self._insert(row, "DUPLICATE_ACK", "Acknowledgement already recorded")
        return AcknowledgementDto.model_validate(row)

    # --- summary ------------------------------------------------------------------------------------
    def _nonbillable_filter(self, job: Job) -> ColumnElement[bool]:
        return billing_deduction_filter(self._s, self._tid, job)

    def summary(self, job_id: uuid.UUID) -> JobSummaryDto:
        job = self.job(job_id)
        opening, closing = self._reading(job.id, ReadingKind.OPENING), self._reading(job.id, ReadingKind.CLOSING)
        nonbillable_seconds = self._s.execute(
            select(
                func.coalesce(func.sum(func.extract("epoch", JobActivity.ended_at - JobActivity.started_at)), 0)
            ).where(
                JobActivity.job_id == job.id,
                JobActivity.billable.is_(False),
                JobActivity.ended_at.is_not(None),
                self._nonbillable_filter(job),
            )
        ).scalar_one()
        nonbillable = (Decimal(str(nonbillable_seconds)) / Decimal(3600)).quantize(Decimal("0.01"))
        eff = PolicyService(self._s).hire_billing(self._tid, at=job.started_at or utcnow())
        meter = (closing.reading - opening.reading) if opening and closing else None
        billable = billable_hours(meter, nonbillable, job.minimum_hours, eff.policy) if meter is not None else None
        standby = Decimal(0)
        if job.standby_treatment is StandbyTreatment.STANDBY_RATE:
            raw = self._s.execute(
                select(
                    func.coalesce(func.sum(func.extract("epoch", JobActivity.ended_at - JobActivity.started_at)), 0)
                ).where(
                    JobActivity.job_id == job.id,
                    JobActivity.billable.is_(False),
                    JobActivity.ended_at.is_not(None),
                    JobActivity.activity_type == ActivityType.STANDBY,
                )
            ).scalar_one()
            hours = Decimal(str(raw)) / Decimal(3600)
            standby = billable_hours(hours, Decimal(0), Decimal(0), eff.policy) if hours > 0 else Decimal(0)
        charges = None
        if billable is not None:
            currency = self._s.get(Currency, job.currency)
            assert currency is not None
            charges = charges_dto(job_charges(job, billable, standby, currency.minor_units))
        counts = dict(
            self._s.execute(
                select(JobException.blocking, func.count())
                .where(JobException.job_id == job.id, JobException.status == ExceptionStatus.OPEN)
                .group_by(JobException.blocking)
            ).all()
        )
        blocking = int(counts.get(True, 0))
        return JobSummaryDto(
            job=job_dto(self._s, job),
            opening_reading=opening.reading if opening else None,
            closing_reading=closing.reading if closing else None,
            meter_hours=meter,
            nonbillable_hours=nonbillable,
            billable_hours=billable,
            open_exceptions=blocking + int(counts.get(False, 0)),
            blocking_exceptions=blocking,
            billing_ready=job.status is JobStatus.COMPLETED and billable is not None and blocking == 0,
            policy_version=eff.version_stamp,
            standby_hours=standby,
            charges=charges,
        )
