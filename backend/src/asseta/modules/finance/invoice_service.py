"""Tenant customer hire invoices: draft from COMPLETED, billing-ready jobs (charges come verbatim from the jobs
module's summary — the single pricing source), issue as an immutable numbered snapshot, correct only by voiding
with a reversal adjustment. A job can be claimed by at most one non-voided invoice (DB partial unique index)."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound
from asseta.core.outbox import OutboxWriter
from asseta.modules.adjustments.models import (
    AdjustmentEntryStatus,
    AdjustmentRequest,
    AdjustmentRequestStatus,
    AdjustmentRequestType,
    AdjustmentType,
    AdjustmentUnit,
)
from asseta.modules.adjustments.posting import AdjustmentPosting, post_adjustment
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
    pending_void = None
    if inv.status is HireInvoiceStatus.ISSUED:
        pending_void = session.execute(
            select(AdjustmentRequest.id).where(
                AdjustmentRequest.request_type == AdjustmentRequestType.INVOICE_VOID,
                AdjustmentRequest.original_id == inv.id,
                AdjustmentRequest.status == AdjustmentRequestStatus.PROPOSED,
            )
        ).scalar_one_or_none()
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
        pending_void_request_id=pending_void,
        job_ids=list(dict.fromkeys(line.job_id for line in lines)),
        lines=[HireInvoiceLineDto.model_validate(line) for line in lines],
    )


@dataclass(frozen=True)
class RecoveryLine:
    job_id: uuid.UUID
    machine_id: uuid.UUID
    description: str
    quantity: Decimal
    unit_price: Decimal
    amount: Decimal


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

    def issue_recovery(
        self, customer_id: uuid.UUID, currency: str, lines: list[RecoveryLine], notes: str
    ) -> TenantHireInvoice:
        """An issued receivable for prepaid hours already used whose payment was reversed (DEC-032 B4): an ordinary
        invoice, so overdue reminders, receivables and payment allocation work unchanged. No job claim: the jobs were
        billed through prepaid hours and are not invoiceable."""
        customer = self._s.get(Customer, customer_id)
        assert customer is not None
        total = sum((line.amount for line in lines), ZERO)
        inv = TenantHireInvoice(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            customer_id=customer_id,
            status=HireInvoiceStatus.DRAFT,
            currency=currency,
            subtotal=total,
            discount_total=ZERO,
            tax_total=ZERO,
            total=total,
            notes=notes,
            created_by=self._ctx.user_id,
            created_at=self._now,
        )
        self._s.add(inv)
        self._s.flush()
        for n, line in enumerate(lines, start=1):
            self._s.add(
                HireInvoiceLine(
                    id=uuid.uuid4(),
                    invoice_id=inv.id,
                    tenant_id=self._tid,
                    line_no=n,
                    kind=ChargeKind.HOURS_RECOVERY,
                    job_id=line.job_id,
                    machine_id=line.machine_id,
                    description=line.description[:300],
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    amount=line.amount,
                )
            )
        self._s.flush()
        issued_on = local_date(tenant_settings(self._s, self._tid).timezone, self._now)
        inv.invoice_number = self._next_number(issued_on.year)
        inv.status, inv.issued_at, inv.issued_by = HireInvoiceStatus.ISSUED, self._now, self._ctx.user_id
        inv.due_date = issued_on + timedelta(days=customer.payment_terms_days)
        self._s.flush()
        self._audit.record(
            actor=self._ctx.audit_actor(),
            action="finance.invoice.recovery_issued",
            entity_type="tenant_hire_invoice",
            entity_id=inv.id,
            tenant_id=self._tid,
            after={"invoice_number": inv.invoice_number, "total": str(total), "currency": currency},
            reason=notes,
        )
        self._outbox.emit(
            topic=TOPIC,
            event_type="HireInvoiceIssued",
            key=str(customer_id),
            payload={
                "invoice_number": inv.invoice_number,
                "total": str(total),
                "currency": currency,
                "invoice_id": str(inv.id),
                "customer_id": str(customer_id),
            },
            tenant_id=self._tid,
        )
        return inv

    def void(
        self,
        invoice_id: uuid.UUID,
        reason: str,
        *,
        request: AdjustmentRequest | None = None,
        reason_label: str | None = None,
    ) -> HireInvoiceDto:
        """Void an invoice. An issued one needs a decided request when the tenant requires a second person (policy
        `HIRE_BILLING.invoice_void_requires_approval`, enforced by the caller); a draft is simply abandoned."""
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
            self._post_void(inv, reason, released, request, reason_label)
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

    def _post_void(
        self,
        inv: TenantHireInvoice,
        reason: str,
        released: Decimal,
        request: AdjustmentRequest | None,
        reason_label: str | None,
    ) -> None:
        from asseta.modules.finance.receivables import ReceivablesService  # lazy: receivables builds on this module

        customer_balance = ReceivablesService(self._s, self._tid).balance_of(inv.customer_id, inv.currency).balance
        post_adjustment(
            self._s,
            self._tid,
            self._now,
            AdjustmentPosting(
                adjustment_type=AdjustmentType.INVOICE_VOID,
                status=AdjustmentEntryStatus.APPROVED,
                original_type="tenant_hire_invoice",
                original_id=inv.id,
                original_reference=inv.invoice_number,
                source_type="adjustment_request" if request else "tenant_hire_invoice",
                source_id=request.id if request else inv.id,
                unit=AdjustmentUnit.MONEY,
                original_value=inv.total,
                new_value=ZERO,
                amount=-inv.total,
                currency=inv.currency,
                resulting_balance=customer_balance,
                reason_id=request.reason_code_id if request else None,
                reason_label=reason_label,
                reason=reason,
                evidence_attachment_ids=list(request.evidence_attachment_ids) if request else [],
                customer_id=inv.customer_id,
                requested_by=request.proposed_by if request else self._ctx.user_id,
                requested_at=request.proposed_at if request else self._now,
                approved_by=self._ctx.user_id if request else None,
                approved_at=self._now if request else None,
                decision_note=None if request else "Approval not required by tenant policy",
                details={"allocations_released": str(released)},
            ),
        )
