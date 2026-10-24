"""Tenant customer hire invoices: draft from COMPLETED, billing-ready jobs (charges come verbatim from the jobs
module's summary — the single pricing source), issue as an immutable numbered snapshot, correct only by voiding
with a reversal adjustment. A job can be claimed by at most one non-voided invoice (DB partial unique index)."""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound
from asseta.core.outbox import OutboxWriter
from asseta.modules.finance.common import ZERO, insert, local_date, tenant_settings
from asseta.modules.finance.dto import HireInvoiceDraftIn, HireInvoiceDto, HireInvoiceIssueIn, HireInvoiceLineDto
from asseta.modules.finance.models import (
    AdjustmentKind,
    CustomerPayment,
    FinancialAdjustment,
    HireInvoiceCounter,
    HireInvoiceJob,
    HireInvoiceLine,
    HireInvoiceStatus,
    HirePaymentAllocation,
    SettlementStatus,
    TenantHireInvoice,
)
from asseta.modules.identity.principal import RequestContext
from asseta.modules.jobs.charges import ChargeKind
from asseta.modules.jobs.dto import JobChargesDto
from asseta.modules.jobs.models import Customer, Job, JobStatus, RentalContract
from asseta.modules.jobs.service import JobService
from asseta.modules.policy.schemas import BillingMode

TOPIC = "asseta.finance"


def verified_paid(session: Session, invoice_id: uuid.UUID) -> Decimal:
    return Decimal(
        session.execute(
            select(func.coalesce(func.sum(HirePaymentAllocation.amount), 0))
            .join(CustomerPayment, CustomerPayment.id == HirePaymentAllocation.payment_id)
            .where(
                HirePaymentAllocation.invoice_id == invoice_id,
                HirePaymentAllocation.released_at.is_(None),
                CustomerPayment.status == SettlementStatus.VERIFIED,
            )
        ).scalar_one()
    )


def invoice_dto(session: Session, inv: TenantHireInvoice) -> HireInvoiceDto:
    lines = list(
        session.execute(
            select(HireInvoiceLine).where(HireInvoiceLine.invoice_id == inv.id).order_by(HireInvoiceLine.line_no)
        ).scalars()
    )
    paid = verified_paid(session, inv.id) if inv.status is HireInvoiceStatus.ISSUED else ZERO
    balance = inv.total - paid if inv.status is HireInvoiceStatus.ISSUED else ZERO
    state = None
    if inv.status is HireInvoiceStatus.ISSUED:
        state = "PAID" if balance <= 0 else ("PARTIALLY_PAID" if paid > 0 else "UNPAID")
    return HireInvoiceDto(
        id=inv.id,
        customer_id=inv.customer_id,
        invoice_number=inv.invoice_number,
        status=inv.status,
        currency=inv.currency,
        subtotal=inv.subtotal,
        discount_total=inv.discount_total,
        tax_total=inv.tax_total,
        total=inv.total,
        amount_paid=paid,
        balance=balance,
        payment_state=state,
        due_date=inv.due_date,
        notes=inv.notes,
        created_at=inv.created_at,
        issued_at=inv.issued_at,
        voided_at=inv.voided_at,
        void_reason=inv.void_reason,
        job_ids=list(dict.fromkeys(line.job_id for line in lines)),
        lines=[HireInvoiceLineDto.model_validate(line) for line in lines],
    )


class HireInvoiceService:
    def __init__(self, session: Session, ctx: RequestContext, now: datetime):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid, self._now = session, ctx, ctx.tenant_id, now
        self._audit = AuditService(session)
        self._outbox = OutboxWriter(session)

    def invoice(self, invoice_id: uuid.UUID, lock: bool = False) -> TenantHireInvoice:
        stmt = select(TenantHireInvoice).where(TenantHireInvoice.id == invoice_id)
        inv = self._s.execute(stmt.with_for_update() if lock else stmt).scalar_one_or_none()
        if inv is None:
            raise NotFound("Hire invoice not found")
        return inv

    def _charges(self, job_id: uuid.UUID, customer_id: uuid.UUID) -> tuple[Job, JobChargesDto]:
        jobs = JobService(self._s, self._ctx)
        job = jobs.job(job_id, lock=True)  # serializes concurrent drafting of the same job
        contract = self._s.get(RentalContract, job.contract_id)
        if contract is None or contract.customer_id != customer_id:
            raise BusinessRuleViolation(
                f"Job {job.job_number} belongs to another customer", code="JOB_CUSTOMER_MISMATCH"
            )
        if job.billing_mode is BillingMode.PREPAID_HOURS:
            raise BusinessRuleViolation(
                f"Job {job.job_number} consumed prepaid customer hours; it is not invoiced", code="JOB_PREPAID_HOURS"
            )
        summary = jobs.summary(job_id)
        if job.status is not JobStatus.COMPLETED or not summary.billing_ready or summary.charges is None:
            raise BusinessRuleViolation(
                f"Job {job.job_number} is not completed and billing-ready (open blocking exceptions or missing "
                "readings)",
                code="JOB_NOT_BILLABLE",
            )
        return job, summary.charges

    def create_draft(self, body: HireInvoiceDraftIn) -> HireInvoiceDto:
        if self._s.get(Customer, body.customer_id) is None:
            raise NotFound("Customer not found")
        if len(set(body.job_ids)) != len(body.job_ids):
            raise BusinessRuleViolation("A job is listed twice", code="DUPLICATE_JOB")
        priced = [self._charges(j, body.customer_id) for j in sorted(body.job_ids)]  # fixed lock order
        currencies = {c.currency for _, c in priced}
        if len(currencies) != 1:
            raise BusinessRuleViolation("All jobs on an invoice must share one currency", code="CURRENCY_MISMATCH")
        inv = TenantHireInvoice(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            customer_id=body.customer_id,
            status=HireInvoiceStatus.DRAFT,
            currency=currencies.pop(),
            subtotal=sum((c.subtotal for _, c in priced), ZERO),
            discount_total=sum((c.discount_total for _, c in priced), ZERO),
            tax_total=sum((c.tax_total for _, c in priced), ZERO),
            total=sum((c.total for _, c in priced), ZERO),
            notes=body.notes,
            created_by=self._ctx.user_id,
            created_at=self._now,
        )
        self._s.add(inv)
        self._s.flush()
        line_no = 0
        for job, charges in priced:
            insert(
                self._s,
                HireInvoiceJob(id=uuid.uuid4(), tenant_id=self._tid, invoice_id=inv.id, job_id=job.id),
                "JOB_ALREADY_INVOICED",
                f"Job {job.job_number} is already on a non-voided invoice",
            )
            for c in charges.lines:
                line_no += 1
                self._s.add(
                    HireInvoiceLine(
                        id=uuid.uuid4(),
                        invoice_id=inv.id,
                        tenant_id=self._tid,
                        line_no=line_no,
                        kind=ChargeKind(c.kind),
                        job_id=job.id,
                        machine_id=job.machine_id,
                        description=c.description[:300],
                        quantity=c.quantity,
                        unit_price=c.unit_price,
                        amount=c.amount,
                    )
                )
        self._s.flush()
        dto = invoice_dto(self._s, inv)
        self._audit.record(
            actor=self._ctx.audit_actor(),
            action="finance.invoice.drafted",
            entity_type="tenant_hire_invoice",
            entity_id=inv.id,
            tenant_id=self._tid,
            after={"total": str(inv.total), "currency": inv.currency, "jobs": [str(j) for j in body.job_ids]},
        )
        return dto

    def _next_number(self, year: int) -> str:
        n = self._s.execute(
            pg_insert(HireInvoiceCounter)
            .values(tenant_id=self._tid, year=year, last_number=1)
            .on_conflict_do_update(
                index_elements=["tenant_id", "year"], set_={"last_number": HireInvoiceCounter.last_number + 1}
            )
            .returning(HireInvoiceCounter.last_number)
        ).scalar_one()
        return f"HINV-{year}-{n:05d}"

    def issue(self, invoice_id: uuid.UUID, body: HireInvoiceIssueIn) -> HireInvoiceDto:
        inv = self.invoice(invoice_id, lock=True)
        if inv.status is not HireInvoiceStatus.DRAFT:
            raise Conflict(f"Invoice is {inv.status.value}; issued invoices are immutable", code="INVOICE_NOT_DRAFT")
        stored = list(
            self._s.execute(
                select(HireInvoiceLine).where(HireInvoiceLine.invoice_id == inv.id).order_by(HireInvoiceLine.line_no)
            ).scalars()
        )
        fresh: list[tuple[str, Decimal, Decimal, Decimal]] = []
        for job_id in dict.fromkeys(line.job_id for line in stored):
            _, charges = self._charges(job_id, inv.customer_id)
            fresh += [(c.kind, c.quantity, c.unit_price, c.amount) for c in charges.lines]
        if fresh != [(line.kind.value, line.quantity, line.unit_price, line.amount) for line in stored]:
            raise Conflict("Job charges changed since drafting; void this draft and draft again", code="DRAFT_STALE")
        tz = tenant_settings(self._s, self._tid).timezone
        customer = self._s.get(Customer, inv.customer_id)
        assert customer is not None
        issued_on = local_date(tz, self._now)
        inv.invoice_number = self._next_number(issued_on.year)
        inv.status, inv.issued_at, inv.issued_by = HireInvoiceStatus.ISSUED, self._now, self._ctx.user_id
        inv.due_date = body.due_date or issued_on + timedelta(days=customer.payment_terms_days)
        self._s.flush()
        snapshot = {"invoice_number": inv.invoice_number, "total": str(inv.total), "currency": inv.currency}
        self._audit.record(
            actor=self._ctx.audit_actor(),
            action="finance.invoice.issued",
            entity_type="tenant_hire_invoice",
            entity_id=inv.id,
            tenant_id=self._tid,
            before={"status": "DRAFT"},
            after={**snapshot, "status": "ISSUED", "due_date": inv.due_date.isoformat()},
        )
        self._outbox.emit(
            topic=TOPIC,
            event_type="HireInvoiceIssued",
            key=str(inv.customer_id),
            payload={**snapshot, "invoice_id": str(inv.id), "customer_id": str(inv.customer_id)},
            tenant_id=self._tid,
        )
        return invoice_dto(self._s, inv)

    def void(self, invoice_id: uuid.UUID, reason: str) -> HireInvoiceDto:
        inv = self.invoice(invoice_id, lock=True)
        if inv.status is HireInvoiceStatus.VOIDED:
            raise Conflict("Invoice is already voided", code="INVOICE_ALREADY_VOIDED")
        was = inv.status
        for claim in self._s.execute(
            select(HireInvoiceJob).where(HireInvoiceJob.invoice_id == inv.id, HireInvoiceJob.released_at.is_(None))
        ).scalars():
            claim.released_at = self._now  # jobs become invoiceable again
        released = Decimal(0)
        if was is HireInvoiceStatus.ISSUED and inv.total > 0:
            self._s.add(
                FinancialAdjustment(
                    id=uuid.uuid4(),
                    tenant_id=self._tid,
                    customer_id=inv.customer_id,
                    invoice_id=inv.id,
                    kind=AdjustmentKind.INVOICE_REVERSAL,
                    amount=inv.total,
                    currency=inv.currency,
                    reason=reason,
                    created_by=self._ctx.user_id,
                    created_at=self._now,
                )
            )
        if was is HireInvoiceStatus.ISSUED:
            for alloc in self._s.execute(
                select(HirePaymentAllocation).where(
                    HirePaymentAllocation.invoice_id == inv.id, HirePaymentAllocation.released_at.is_(None)
                )
            ).scalars():
                alloc.released_at, alloc.release_reason = self._now, "Invoice voided; amount returned to credit"
                released += alloc.amount
        inv.status, inv.voided_at, inv.voided_by, inv.void_reason = (
            HireInvoiceStatus.VOIDED,
            self._now,
            self._ctx.user_id,
            reason,
        )
        self._s.flush()
        self._audit.record(
            actor=self._ctx.audit_actor(),
            action="finance.invoice.voided",
            entity_type="tenant_hire_invoice",
            entity_id=inv.id,
            tenant_id=self._tid,
            before={"status": was.value},
            after={
                "status": "VOIDED",
                "reversal": str(inv.total) if was is HireInvoiceStatus.ISSUED else "0",
                "allocations_released": str(released),
            },
            reason=reason,
        )
        if was is HireInvoiceStatus.ISSUED:
            self._outbox.emit(
                topic=TOPIC,
                event_type="HireInvoiceVoided",
                key=str(inv.customer_id),
                payload={
                    "invoice_id": str(inv.id),
                    "invoice_number": inv.invoice_number,
                    "reversal": str(inv.total),
                    "currency": inv.currency,
                },
                tenant_id=self._tid,
            )
        return invoice_dto(self._s, inv)
