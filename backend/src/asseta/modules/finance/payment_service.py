"""Customer payments (cash collections, bank, mobile money): CLAIMED on record, VERIFIED/REJECTED by someone other
than the recorder (segregation of duties). A payment pays orders (hours purchases) and credit invoices through their
own links; verified money not linked is customer credit (deposits/advances). Payment gateways stay out of scope."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.db import utcnow
from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound
from asseta.core.outbox import OutboxWriter
from asseta.core.signals import sod_violation
from asseta.modules.customers.models import Customer
from asseta.modules.finance.common import currency_or_default, insert
from asseta.modules.finance.dto import (
    CustomerPaymentDto,
    CustomerPaymentIn,
    PurchaseLinkDto,
    SettlementDecisionIn,
)
from asseta.modules.finance.models import (
    CashHandover,
    CustomerPayment,
    HirePaymentMethod,
    SettlementStatus,
)
from asseta.modules.finance.references import payment_series, reference
from asseta.modules.fleet.models import StaffMember
from asseta.modules.hours.cash_activation import verified_by_handover
from asseta.modules.hours.engine import HoursEngine
from asseta.modules.hours.models import HoursPaymentAllocation, HoursPurchase, PaymentAutoVerification
from asseta.modules.identity.principal import RequestContext

TOPIC = "asseta.finance"


def payment_dto(session: Session, p: CustomerPayment) -> CustomerPaymentDto:
    dto = CustomerPaymentDto.model_validate(p)
    links = session.execute(
        select(HoursPaymentAllocation, HoursPurchase.purchase_number)
        .join(HoursPurchase, HoursPurchase.id == HoursPaymentAllocation.purchase_id)
        .where(HoursPaymentAllocation.payment_id == p.id, HoursPaymentAllocation.released_at.is_(None))
        .order_by(HoursPaymentAllocation.created_at)
    )
    dto.purchase_links = [
        PurchaseLinkDto(purchase_id=a.purchase_id, purchase_number=number, amount=a.amount) for a, number in links
    ]
    if p.method is HirePaymentMethod.CASH and dto.purchase_links:
        if p.status is SettlementStatus.VERIFIED and p.verified_by is None:
            auto = session.execute(
                select(PaymentAutoVerification, CashHandover.remittance_number)
                .outerjoin(CashHandover, CashHandover.id == PaymentAutoVerification.handover_id)
                .where(PaymentAutoVerification.payment_id == p.id)
            ).first()
            if auto is not None:
                dto.verified_automatically = "ON_HANDOVER" if auto[0].mode == "ON_HANDOVER" else "ON_RECORDING"
                dto.verified_by_handover_id, dto.verified_by_remittance_number = auto[0].handover_id, auto[1]
        elif p.status is SettlementStatus.CLAIMED:
            dto.verifies_on_handover = verified_by_handover(session, p, utcnow())
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
            collection_number=reference(self._s, self._tid, payment_series(body.method), self._now),
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
