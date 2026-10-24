"""Customer payments (cash collections, bank, mobile money): CLAIMED on record, VERIFIED/REJECTED by someone other
than the recorder (segregation of duties). Allocations apply payments to issued invoices (partial payments);
verified money not allocated is customer credit (deposits/advances). Payment gateways stay out of scope (BL)."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound
from asseta.core.outbox import OutboxWriter
from asseta.core.signals import sod_violation
from asseta.modules.finance.common import currency_or_default, insert
from asseta.modules.finance.dto import (
    CustomerPaymentDto,
    CustomerPaymentIn,
    HireAllocationDto,
    HireAllocationIn,
    SettlementDecisionIn,
)
from asseta.modules.finance.models import (
    CustomerPayment,
    HireInvoiceStatus,
    HirePaymentAllocation,
    SettlementStatus,
    TenantHireInvoice,
)
from asseta.modules.fleet.models import StaffMember
from asseta.modules.hours.engine import HoursEngine
from asseta.modules.hours.ledger import active_allocated as hours_allocated
from asseta.modules.identity.principal import RequestContext
from asseta.modules.jobs.models import Customer

TOPIC = "asseta.finance"


def payment_dto(session: Session, p: CustomerPayment) -> CustomerPaymentDto:
    allocs = session.execute(
        select(HirePaymentAllocation)
        .where(HirePaymentAllocation.payment_id == p.id)
        .order_by(HirePaymentAllocation.created_at)
    ).scalars()
    dto = CustomerPaymentDto.model_validate(p)
    dto.allocations = [HireAllocationDto.model_validate(a) for a in allocs]
    return dto


class CustomerPaymentService:
    def __init__(self, session: Session, ctx: RequestContext, now: datetime):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid, self._now = session, ctx, ctx.tenant_id, now
        self._audit = AuditService(session)

    def payment(self, payment_id: uuid.UUID, lock: bool = False) -> CustomerPayment:
        stmt = select(CustomerPayment).where(CustomerPayment.id == payment_id)
        row = self._s.execute(stmt.with_for_update() if lock else stmt).scalar_one_or_none()
        if row is None:
            raise NotFound("Payment not found")
        return row

    def record(self, body: CustomerPaymentIn, source: str = "API") -> CustomerPaymentDto:
        if body.client_id is not None:
            existing = self._s.execute(
                select(CustomerPayment).where(CustomerPayment.client_id == body.client_id)
            ).scalar_one_or_none()
            if existing is not None:
                return payment_dto(self._s, existing)  # offline retry of the same capture: exactly one effect
        if self._s.get(Customer, body.customer_id) is None:
            raise NotFound("Customer not found")
        if body.received_by_staff_id is not None and self._s.get(StaffMember, body.received_by_staff_id) is None:
            raise NotFound("Staff member not found")
        payment = CustomerPayment(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            customer_id=body.customer_id,
            client_id=body.client_id,
            amount=body.amount,
            currency=currency_or_default(self._s, self._tid, body.currency),
            method=body.method,
            reference=body.reference,
            received_at=body.received_at,
            received_by_staff_id=body.received_by_staff_id,
            status=SettlementStatus.CLAIMED,
            note=body.note,
            source=source,
            recorded_by=self._ctx.user_id,
            recorded_at=self._now,
        )
        insert(self._s, payment, "DUPLICATE_PAYMENT_REFERENCE", "A payment with this method and reference exists")
        self._audit.record(
            actor=self._ctx.audit_actor(source.lower()),
            action="finance.payment.recorded",
            entity_type="customer_payment",
            entity_id=payment.id,
            tenant_id=self._tid,
            after={
                "amount": str(payment.amount),
                "currency": payment.currency,
                "method": payment.method.value,
                "reference": payment.reference,
                "status": "CLAIMED",
            },
        )
        if body.allocations:
            self._allocate(payment, body.allocations)
        OutboxWriter(self._s).emit(
            topic=TOPIC,
            event_type="CustomerPaymentRecorded",
            key=str(payment.customer_id),
            payload={
                "payment_id": str(payment.id),
                "customer_id": str(payment.customer_id),
                "amount": str(payment.amount),
                "currency": payment.currency,
                "method": payment.method.value,
            },
            tenant_id=self._tid,
        )
        return payment_dto(self._s, payment)

    def _allocate(self, payment: CustomerPayment, items: list[HireAllocationIn]) -> None:
        if payment.status is SettlementStatus.REJECTED:
            raise BusinessRuleViolation("A rejected payment cannot be allocated", code="PAYMENT_REJECTED")
        # Money already linked to hours purchases counts too: a payment is never allocated twice.
        allocated = self._active_allocated(HirePaymentAllocation.payment_id == payment.id) + hours_allocated(
            self._s, payment_id=payment.id
        )
        for item in sorted(items, key=lambda i: i.invoice_id):  # fixed lock order
            inv = self._s.execute(
                select(TenantHireInvoice).where(TenantHireInvoice.id == item.invoice_id).with_for_update()
            ).scalar_one_or_none()
            if inv is None:
                raise NotFound("Hire invoice not found")
            if inv.status is not HireInvoiceStatus.ISSUED:
                raise BusinessRuleViolation(
                    "Payments can only be allocated to issued invoices", code="INVOICE_NOT_OPEN"
                )
            if inv.customer_id != payment.customer_id or inv.currency != payment.currency:
                raise BusinessRuleViolation(
                    "Invoice belongs to another customer or currency", code="ALLOCATION_MISMATCH"
                )
            open_amount = inv.total - self._active_allocated(HirePaymentAllocation.invoice_id == inv.id)
            if item.amount > open_amount:
                raise BusinessRuleViolation(
                    f"Allocation exceeds the invoice's open amount {open_amount}", code="OVER_ALLOCATION"
                )
            if allocated + item.amount > payment.amount:
                raise BusinessRuleViolation("Allocations exceed the payment amount", code="ALLOCATION_EXCEEDS_PAYMENT")
            allocated += item.amount
            alloc = HirePaymentAllocation(
                id=uuid.uuid4(),
                tenant_id=self._tid,
                payment_id=payment.id,
                invoice_id=inv.id,
                amount=item.amount,
                created_by=self._ctx.user_id,
                created_at=self._now,
            )
            self._s.add(alloc)
            self._s.flush()
            self._audit.record(
                actor=self._ctx.audit_actor(),
                action="finance.payment.allocated",
                entity_type="hire_payment_allocation",
                entity_id=alloc.id,
                tenant_id=self._tid,
                after={"payment_id": str(payment.id), "invoice_id": str(inv.id), "amount": str(item.amount)},
            )

    def _active_allocated(self, condition: ColumnElement[bool]) -> Decimal:
        """Allocations of non-rejected payments that are still active (claimed allocations reserve capacity)."""
        return Decimal(
            self._s.execute(
                select(func.coalesce(func.sum(HirePaymentAllocation.amount), 0))
                .join(CustomerPayment, CustomerPayment.id == HirePaymentAllocation.payment_id)
                .where(
                    condition,
                    HirePaymentAllocation.released_at.is_(None),
                    CustomerPayment.status != SettlementStatus.REJECTED,
                )
            ).scalar_one()
        )

    def allocate(self, payment_id: uuid.UUID, items: list[HireAllocationIn]) -> CustomerPaymentDto:
        payment = self.payment(payment_id, lock=True)
        self._allocate(payment, items)
        return payment_dto(self._s, payment)

    def decide(self, payment_id: uuid.UUID, body: SettlementDecisionIn) -> CustomerPaymentDto:
        payment = self.payment(payment_id, lock=True)
        if payment.status is not SettlementStatus.CLAIMED:
            raise Conflict(f"Payment already {payment.status.value}", code="PAYMENT_ALREADY_DECIDED")
        if payment.recorded_by == self._ctx.user_id:
            sod_violation(self._tid, self._ctx.user_id, "verify", "customer_payment", payment.id)
            raise BusinessRuleViolation(
                "The person who recorded a payment cannot verify it", code="SEGREGATION_OF_DUTIES"
            )
        payment.status = SettlementStatus.VERIFIED if body.verified else SettlementStatus.REJECTED
        payment.verified_by, payment.verified_at, payment.decision_note = self._ctx.user_id, self._now, body.note
        if payment.status is SettlementStatus.REJECTED:
            for alloc in self._s.execute(
                select(HirePaymentAllocation).where(
                    HirePaymentAllocation.payment_id == payment.id, HirePaymentAllocation.released_at.is_(None)
                )
            ).scalars():
                alloc.released_at, alloc.release_reason = self._now, "Payment rejected"
        self._s.flush()
        # Linked hours purchases: verified money activates hours, a rejection releases the links.
        HoursEngine(self._s, self._tid, self._ctx.audit_actor(), self._now).on_payment_decided(payment)
        self._audit.record(
            actor=self._ctx.audit_actor(),
            action=f"finance.payment.{payment.status.value.lower()}",
            entity_type="customer_payment",
            entity_id=payment.id,
            tenant_id=self._tid,
            before={"status": "CLAIMED"},
            after={"status": payment.status.value, "amount": str(payment.amount), "currency": payment.currency},
            reason=body.note,
        )
        if payment.status is SettlementStatus.VERIFIED:
            OutboxWriter(self._s).emit(
                topic=TOPIC,
                event_type="CustomerPaymentVerified",
                key=str(payment.customer_id),
                payload={
                    "payment_id": str(payment.id),
                    "customer_id": str(payment.customer_id),
                    "amount": str(payment.amount),
                    "currency": payment.currency,
                    "method": payment.method.value,
                },
                tenant_id=self._tid,
            )
        return payment_dto(self._s, payment)
