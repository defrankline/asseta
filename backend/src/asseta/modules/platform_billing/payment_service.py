"""Manual platform subscription payments (record -> verify/reject) and credit adjustments.
Only VERIFIED payments reduce balances. Payment gateways are an adapter seam for later (BL-004)."""

import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from asseta.core.audit import AuditActor, AuditService
from asseta.core.db import utcnow
from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound
from asseta.core.outbox import OutboxWriter
from asseta.modules.platform_billing.dto import (
    CreditAdjustmentIn,
    InvoiceDto,
    PaymentDecisionIn,
    PaymentDto,
    RecordPaymentIn,
)
from asseta.modules.platform_billing.enums import InvoiceStatus, PaymentStatus
from asseta.modules.platform_billing.mappers import invoice_dto
from asseta.modules.platform_billing.models_ledger import CreditAdjustment, PlatformInvoice, PlatformPayment
from asseta.modules.platform_billing.repository import BillingRepository

TOPIC = "asseta.platform.payment"


class PaymentService:
    def __init__(self, session: Session, actor: AuditActor):
        self._s = session
        self._repo = BillingRepository(session)
        self._actor = actor
        self._audit = AuditService(session)
        self._outbox = OutboxWriter(session)

    def _recompute(self, inv: PlatformInvoice) -> None:
        paid = self._s.execute(
            select(func.coalesce(func.sum(PlatformPayment.amount), 0)).where(
                PlatformPayment.invoice_id == inv.id, PlatformPayment.status == PaymentStatus.VERIFIED
            )
        ).scalar_one()
        credits = self._s.execute(
            select(func.coalesce(func.sum(CreditAdjustment.amount), 0)).where(CreditAdjustment.invoice_id == inv.id)
        ).scalar_one()
        inv.amount_paid, inv.credits_applied = Decimal(paid), Decimal(credits)
        inv.balance = inv.total - inv.amount_paid - inv.credits_applied
        if inv.balance <= 0:
            inv.status = InvoiceStatus.PAID
        elif inv.amount_paid + inv.credits_applied > 0:
            inv.status = InvoiceStatus.PARTIALLY_PAID
        else:
            inv.status = InvoiceStatus.ISSUED

    def _outstanding_unverified(self, invoice_id: uuid.UUID) -> Decimal:
        return Decimal(
            self._s.execute(
                select(func.coalesce(func.sum(PlatformPayment.amount), 0)).where(
                    PlatformPayment.invoice_id == invoice_id, PlatformPayment.status == PaymentStatus.RECORDED
                )
            ).scalar_one()
        )

    def record(self, body: RecordPaymentIn) -> PaymentDto:
        inv = self._repo.invoice(body.invoice_id, for_update=True)
        if body.currency != inv.currency:
            raise BusinessRuleViolation("Payment currency must match invoice currency", code="CURRENCY_MISMATCH")
        if body.amount + self._outstanding_unverified(inv.id) > inv.balance:
            raise BusinessRuleViolation("Payment exceeds the invoice's remaining balance", code="OVERPAYMENT")
        payment = PlatformPayment(
            id=uuid.uuid4(),
            tenant_id=inv.tenant_id,
            status=PaymentStatus.RECORDED,
            recorded_by=self._actor.user_id,
            **body.model_dump(),
        )
        try:
            with self._s.begin_nested():
                self._s.add(payment)
                self._s.flush()
        except IntegrityError as exc:
            raise Conflict(
                "A payment with this method and reference already exists", code="DUPLICATE_PAYMENT_REFERENCE"
            ) from exc
        dto = PaymentDto.model_validate(payment)
        self._audit.record(
            actor=self._actor,
            action="platform.payment.recorded",
            entity_type="platform_payment",
            entity_id=payment.id,
            tenant_id=inv.tenant_id,
            after=dto.model_dump(mode="json"),
        )
        return dto

    def decide(self, payment_id: uuid.UUID, body: PaymentDecisionIn) -> PaymentDto:
        payment = self._s.execute(
            select(PlatformPayment).where(PlatformPayment.id == payment_id).with_for_update()
        ).scalar_one_or_none()
        if payment is None:
            raise NotFound("Payment not found")
        if payment.status is not PaymentStatus.RECORDED:
            raise Conflict(f"Payment already {payment.status.value}", code="PAYMENT_ALREADY_DECIDED")
        inv = self._repo.invoice(payment.invoice_id, for_update=True)
        payment.status = PaymentStatus.VERIFIED if body.verified else PaymentStatus.REJECTED
        payment.decided_by, payment.decided_at, payment.decision_note = self._actor.user_id, utcnow(), body.note
        self._s.flush()
        self._recompute(inv)
        dto = PaymentDto.model_validate(payment)
        self._audit.record(
            actor=self._actor,
            action=f"platform.payment.{payment.status.value.lower()}",
            entity_type="platform_payment",
            entity_id=payment.id,
            tenant_id=inv.tenant_id,
            before={"status": "RECORDED"},
            after={"status": payment.status.value, "invoice_balance": str(inv.balance)},
            reason=body.note,
        )
        if payment.status is PaymentStatus.VERIFIED:
            self._outbox.emit(
                topic=TOPIC,
                event_type="PlatformPaymentVerified",
                key=str(inv.tenant_id),
                payload={
                    "payment_id": str(payment.id),
                    "invoice_id": str(inv.id),
                    "amount": str(payment.amount),
                    "currency": payment.currency,
                },
                tenant_id=inv.tenant_id,
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
        self._recompute(inv)
        self._audit.record(
            actor=self._actor,
            action="platform.credit.applied",
            entity_type="credit_adjustment",
            entity_id=credit.id,
            tenant_id=inv.tenant_id,
            after={"invoice_id": str(inv.id), "amount": str(body.amount)},
            reason=body.reason,
        )
        return invoice_dto(inv, self._repo.invoice_lines(inv.id))
