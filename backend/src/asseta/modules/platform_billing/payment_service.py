"""Manual platform payments (record -> verify/reject) and credit adjustments.
Only VERIFIED payments reduce balances. On verification the money is allocated to invoice lines (explicit plan, else
the payment's invoice then the tenant's oldest open invoices, line order) and fully paid lines are fulfilled
(DEC-022). Payment gateways are an adapter seam for later (BL-004)."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from asseta.core.audit import AuditActor, AuditService
from asseta.core.db import utcnow
from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound
from asseta.core.outbox import OutboxWriter
from asseta.core.signals import sod_violation
from asseta.modules.platform_billing.allocation import AllocationService
from asseta.modules.platform_billing.dto import (
    CreditAdjustmentIn,
    InvoiceDto,
    LineAllocationIn,
    PaymentDecisionIn,
    PaymentDto,
    RecordPaymentIn,
)
from asseta.modules.platform_billing.enums import PaymentStatus
from asseta.modules.platform_billing.models_ledger import CreditAdjustment, PlatformPayment
from asseta.modules.platform_billing.repository import BillingRepository
from asseta.modules.tenancy.models import Tenant

TOPIC = "asseta.platform.payment"


class PaymentService:
    def __init__(self, session: Session, actor: AuditActor, today: date | None = None):
        self._s = session
        self._repo = BillingRepository(session)
        self._actor = actor
        self._audit = AuditService(session)
        self._outbox = OutboxWriter(session)
        self._alloc = AllocationService(session, actor, today or utcnow().date())

    def _unverified(self, *where: ColumnElement[bool]) -> Decimal:
        return Decimal(
            self._s.execute(
                select(func.coalesce(func.sum(PlatformPayment.amount), 0)).where(
                    PlatformPayment.status == PaymentStatus.RECORDED, *where
                )
            ).scalar_one()
        )

    def payment(self, payment_id: uuid.UUID, lock: bool = False) -> PlatformPayment:
        stmt = select(PlatformPayment).where(PlatformPayment.id == payment_id)
        payment = self._s.execute(stmt.with_for_update() if lock else stmt).scalar_one_or_none()
        if payment is None:
            raise NotFound("Payment not found")
        return payment

    def record(self, body: RecordPaymentIn) -> PaymentDto:
        if body.invoice_id is not None:
            inv = self._repo.invoice(body.invoice_id, for_update=True)
            if body.tenant_id is not None and body.tenant_id != inv.tenant_id:
                raise BusinessRuleViolation("Invoice belongs to another tenant", code="ALLOCATION_MISMATCH")
            if body.currency != inv.currency:
                raise BusinessRuleViolation("Payment currency must match invoice currency", code="CURRENCY_MISMATCH")
            tenant_id, open_balance = inv.tenant_id, inv.balance
            pending = self._unverified(PlatformPayment.invoice_id == inv.id)
        else:
            assert body.tenant_id is not None  # DTO validator
            if self._s.get(Tenant, body.tenant_id) is None:
                raise NotFound("Tenant not found")
            tenant_id = body.tenant_id
            open_balance = self._alloc.open_balance(tenant_id, body.currency)
            pending = self._unverified(
                PlatformPayment.tenant_id == tenant_id, PlatformPayment.currency == body.currency
            )
        if body.amount + pending > open_balance:
            raise BusinessRuleViolation("Payment exceeds the remaining open balance", code="OVERPAYMENT")
        plan = body.allocations or []
        self._alloc.validate_plan(tenant_id, body.currency, plan)
        payment = PlatformPayment(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            invoice_id=body.invoice_id,
            amount=body.amount,
            currency=body.currency,
            method=body.method,
            reference=body.reference,
            received_on=body.received_on,
            status=PaymentStatus.RECORDED,
            recorded_by=self._actor.user_id,
            allocation_plan=[a.model_dump(mode="json") for a in plan] or None,
        )
        try:
            with self._s.begin_nested():
                self._s.add(payment)
                self._s.flush()
        except IntegrityError as exc:
            raise Conflict(
                "A payment with this method and reference already exists", code="DUPLICATE_PAYMENT_REFERENCE"
            ) from exc
        dto = self._alloc.payment_dto(payment)
        self._audit.record(
            actor=self._actor,
            action="platform.payment.recorded",
            entity_type="platform_payment",
            entity_id=payment.id,
            tenant_id=tenant_id,
            after=dto.model_dump(mode="json"),
        )
        self._outbox.emit(
            topic=TOPIC,
            event_type="PlatformPaymentRecorded",
            key=str(tenant_id),
            payload={
                "payment_id": str(payment.id),
                "invoice_id": str(payment.invoice_id) if payment.invoice_id else None,
                "amount": str(payment.amount),
                "currency": payment.currency,
                "reference": payment.reference,
            },
            tenant_id=tenant_id,
        )
        return dto

    def decide(self, payment_id: uuid.UUID, body: PaymentDecisionIn) -> PaymentDto:
        payment = self.payment(payment_id, lock=True)
        if payment.status is not PaymentStatus.RECORDED:
            raise Conflict(f"Payment already {payment.status.value}", code="PAYMENT_ALREADY_DECIDED")
        if payment.recorded_by is not None and payment.recorded_by == self._actor.user_id:
            # Two-person rule (owner decision, as for tenant finance): whoever recorded a payment cannot decide it.
            sod_violation(payment.tenant_id, self._actor.user_id, "verify", "platform_payment", payment.id)
            raise BusinessRuleViolation(
                "The person who recorded a payment cannot verify or reject it", code="SEGREGATION_OF_DUTIES"
            )
        payment.status = PaymentStatus.VERIFIED if body.verified else PaymentStatus.REJECTED
        payment.decided_by, payment.decided_at, payment.decision_note = self._actor.user_id, utcnow(), body.note
        self._s.flush()
        touched: list[uuid.UUID] = []
        if payment.status is PaymentStatus.VERIFIED:
            plan = body.allocations
            if plan is None and payment.allocation_plan:
                plan = [LineAllocationIn.model_validate(a) for a in payment.allocation_plan]
            touched = self._alloc.allocate_payment(payment, plan)
        dto = self._alloc.payment_dto(payment)
        balances = {str(i): str(self._repo.invoice(i).balance) for i in touched}
        self._audit.record(
            actor=self._actor,
            action=f"platform.payment.{payment.status.value.lower()}",
            entity_type="platform_payment",
            entity_id=payment.id,
            tenant_id=payment.tenant_id,
            before={"status": "RECORDED"},
            after={"status": payment.status.value, "invoice_balances": balances},
            reason=body.note,
        )
        if payment.status is PaymentStatus.VERIFIED:
            self._outbox.emit(
                topic=TOPIC,
                event_type="PlatformPaymentVerified",
                key=str(payment.tenant_id),
                payload={
                    "payment_id": str(payment.id),
                    "invoice_id": str(payment.invoice_id) if payment.invoice_id else None,
                    "invoice_ids": [str(i) for i in touched],
                    "amount": str(payment.amount),
                    "currency": payment.currency,
                },
                tenant_id=payment.tenant_id,
            )
        return dto

    def allocate(self, payment_id: uuid.UUID, plan: list[LineAllocationIn] | None) -> PaymentDto:
        """Apply a verified payment's unallocated money (e.g. released by a void), explicitly or by default order."""
        payment = self.payment(payment_id, lock=True)
        touched = self._alloc.allocate_payment(payment, plan)
        dto = self._alloc.payment_dto(payment)
        self._audit.record(
            actor=self._actor,
            action="platform.payment.allocated",
            entity_type="platform_payment",
            entity_id=payment.id,
            tenant_id=payment.tenant_id,
            after={"invoice_ids": [str(i) for i in touched], "unallocated": str(dto.unallocated)},
        )
        return dto

    def credit(self, body: CreditAdjustmentIn) -> InvoiceDto:
        inv = self._repo.invoice(body.invoice_id, for_update=True)
        if body.amount > inv.balance:
            raise BusinessRuleViolation("Credit exceeds the invoice's remaining balance", code="CREDIT_EXCEEDS_BALANCE")
        credit = CreditAdjustment(
            id=uuid.uuid4(),
            tenant_id=inv.tenant_id,
            invoice_id=inv.id,
            amount=body.amount,
            currency=inv.currency,
            reason=body.reason,
            created_by=self._actor.user_id,
        )
        self._s.add(credit)
        self._s.flush()
        self._alloc.allocate_credit(credit, inv)
        self._audit.record(
            actor=self._actor,
            action="platform.credit.applied",
            entity_type="credit_adjustment",
            entity_id=credit.id,
            tenant_id=inv.tenant_id,
            after={"invoice_id": str(inv.id), "amount": str(body.amount)},
            reason=body.reason,
        )
        return self._alloc.invoice_view(inv)
