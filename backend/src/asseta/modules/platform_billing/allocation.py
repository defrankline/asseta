"""Per-line application of verified platform money (DEC-022). Default: the payment's own invoice, then the tenant's
oldest open invoices (due date, issue time), each filled in line order. Explicit allocations target named lines.
Invoice totals (`amount_paid`, `credits_applied`, `balance`, status) are recomputed from active allocations, and
every line that becomes fully paid is fulfilled exactly once."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditActor
from asseta.core.db import utcnow
from asseta.core.errors import BusinessRuleViolation, NotFound
from asseta.modules.platform_billing.dto import InvoiceDto, LineAllocationIn, PaymentAllocationDto, PaymentDto
from asseta.modules.platform_billing.enums import InvoiceStatus, PaymentStatus
from asseta.modules.platform_billing.fulfilment import FulfilmentService
from asseta.modules.platform_billing.mappers import LineExtras, invoice_dto
from asseta.modules.platform_billing.models_catalog import PlatformLineAllocation, PlatformLineFulfilment
from asseta.modules.platform_billing.models_ledger import (
    CreditAdjustment,
    PlatformInvoice,
    PlatformInvoiceLine,
    PlatformPayment,
)
from asseta.modules.platform_billing.repository import BillingRepository
from asseta.modules.platform_billing.settlement import ZERO, LineInput, LineState, settle

OPEN = (InvoiceStatus.ISSUED, InvoiceStatus.PARTIALLY_PAID)


def _sum(session: Session, *where: ColumnElement[bool]) -> Decimal:
    return Decimal(
        session.execute(
            select(func.coalesce(func.sum(PlatformLineAllocation.amount), 0)).where(
                PlatformLineAllocation.released_at.is_(None), *where
            )
        ).scalar_one()
    )


class AllocationService:
    def __init__(self, session: Session, actor: AuditActor, today: date):
        self._s, self._actor, self._today = session, actor, today
        self._repo = BillingRepository(session)

    # --- reads ------------------------------------------------------------------------------------------------
    def line_states(self, invoice_id: uuid.UUID) -> list[LineState]:
        lines = self._repo.invoice_lines(invoice_id)
        rows = self._s.execute(
            select(PlatformLineAllocation.line_id, PlatformLineAllocation.amount)
            .outerjoin(PlatformPayment, PlatformPayment.id == PlatformLineAllocation.payment_id)
            .where(
                PlatformLineAllocation.invoice_id == invoice_id,
                PlatformLineAllocation.released_at.is_(None),
                (PlatformLineAllocation.credit_id.is_not(None)) | (PlatformPayment.status == PaymentStatus.VERIFIED),
            )
        ).all()
        return settle(
            [LineInput(x.id, x.line_no, x.amount) for x in lines], [(r.line_id, Decimal(r.amount)) for r in rows]
        )

    def invoice_view(self, inv: PlatformInvoice) -> InvoiceDto:
        lines = self._repo.invoice_lines(inv.id)
        states = {st.line_id: st for st in self.line_states(inv.id)}
        fulfilled = {
            r[0]: r[1]
            for r in self._s.execute(
                select(PlatformLineFulfilment.line_id, PlatformLineFulfilment.status).where(
                    PlatformLineFulfilment.invoice_id == inv.id
                )
            ).all()
        }
        extras = {
            line.id: LineExtras(states[line.id].payable, states[line.id].paid, fulfilled.get(line.id)) for line in lines
        }
        return invoice_dto(inv, lines, extras)

    def unallocated(self, payment: PlatformPayment) -> Decimal:
        return payment.amount - _sum(self._s, PlatformLineAllocation.payment_id == payment.id)

    def payment_dto(self, payment: PlatformPayment) -> PaymentDto:
        dto = PaymentDto.model_validate(payment)
        rows = self._s.execute(
            select(PlatformLineAllocation)
            .where(PlatformLineAllocation.payment_id == payment.id)
            .order_by(PlatformLineAllocation.created_at)
        ).scalars()
        dto.allocations = [PaymentAllocationDto.model_validate(a) for a in rows]
        dto.unallocated = self.unallocated(payment) if payment.status is PaymentStatus.VERIFIED else None
        return dto

    def open_invoices(self, tenant_id: uuid.UUID, currency: str) -> list[PlatformInvoice]:
        return list(
            self._s.execute(
                select(PlatformInvoice)
                .where(
                    PlatformInvoice.tenant_id == tenant_id,
                    PlatformInvoice.currency == currency,
                    PlatformInvoice.status.in_(OPEN),
                    PlatformInvoice.balance > 0,
                )
                .order_by(PlatformInvoice.due_date, PlatformInvoice.issued_at, PlatformInvoice.invoice_number)
                .with_for_update()
            ).scalars()
        )

    def open_balance(self, tenant_id: uuid.UUID, currency: str) -> Decimal:
        return sum((i.balance for i in self.open_invoices(tenant_id, currency)), ZERO)

    def line(self, line_id: uuid.UUID) -> tuple[PlatformInvoiceLine, PlatformInvoice]:
        line = self._s.get(PlatformInvoiceLine, line_id)
        if line is None:
            raise NotFound("Invoice line not found")
        return line, self._repo.invoice(line.invoice_id, for_update=True)

    def validate_plan(self, tenant_id: uuid.UUID, currency: str, plan: list[LineAllocationIn]) -> None:
        for item in plan:
            line, inv = self.line(item.line_id)
            if inv.tenant_id != tenant_id or inv.currency != currency:
                raise BusinessRuleViolation(
                    "Allocation line belongs to another tenant or currency", code="ALLOCATION_MISMATCH"
                )
            if inv.status not in OPEN:
                raise BusinessRuleViolation(f"Invoice {inv.invoice_number} is not open", code="INVOICE_NOT_OPEN")
            state = next(st for st in self.line_states(inv.id) if st.line_id == line.id)
            if item.amount > state.remaining:
                raise BusinessRuleViolation(
                    f"Allocation exceeds line {line.line_no}'s open amount {state.remaining}", code="OVER_ALLOCATION"
                )

    # --- writes -----------------------------------------------------------------------------------------------
    def _add(
        self,
        inv: PlatformInvoice,
        amount: Decimal,
        line_id: uuid.UUID | None,
        payment_id: uuid.UUID | None = None,
        credit_id: uuid.UUID | None = None,
    ) -> None:
        self._s.add(
            PlatformLineAllocation(
                id=uuid.uuid4(),
                tenant_id=inv.tenant_id,
                invoice_id=inv.id,
                line_id=line_id,
                payment_id=payment_id,
                credit_id=credit_id,
                amount=amount,
                created_by=self._actor.user_id,
            )
        )
        self._s.flush()

    def allocate_payment(self, payment: PlatformPayment, plan: list[LineAllocationIn] | None) -> list[uuid.UUID]:
        """Apply the payment's unallocated verified money. Returns the touched invoice ids (recomputed+fulfilled)."""
        if payment.status is not PaymentStatus.VERIFIED:
            raise BusinessRuleViolation("Only verified payments can be allocated", code="PAYMENT_NOT_VERIFIED")
        available = self.unallocated(payment)
        touched: list[uuid.UUID] = []
        explicit = sorted(plan or [], key=lambda a: str(a.line_id))  # fixed lock order
        if sum((a.amount for a in explicit), ZERO) > available:
            raise BusinessRuleViolation("Allocations exceed the unallocated amount", code="ALLOCATION_EXCEEDS_PAYMENT")
        self.validate_plan(payment.tenant_id, payment.currency, explicit)
        for item in explicit:
            line, inv = self.line(item.line_id)
            self._add(inv, item.amount, line.id, payment_id=payment.id)
            available -= item.amount
            self._touch(touched, inv)
        candidates = self.open_invoices(payment.tenant_id, payment.currency)
        if payment.invoice_id is not None:  # the invoice the payment was recorded against comes first
            candidates.sort(key=lambda i: i.id != payment.invoice_id)
        for inv in candidates:
            if available <= 0:
                break
            remaining = sum((st.remaining for st in self.line_states(inv.id)), ZERO)
            take = min(available, remaining)
            if take > 0:
                self._add(inv, take, None, payment_id=payment.id)
                available -= take
                self._touch(touched, inv)
        return touched

    def allocate_credit(self, credit: CreditAdjustment, inv: PlatformInvoice) -> None:
        self._add(inv, credit.amount, None, credit_id=credit.id)
        self._touch([], inv)

    def release_invoice(self, inv: PlatformInvoice, reason: str) -> Decimal:
        released = ZERO
        for a in self._s.execute(
            select(PlatformLineAllocation).where(
                PlatformLineAllocation.invoice_id == inv.id, PlatformLineAllocation.released_at.is_(None)
            )
        ).scalars():
            a.released_at, a.release_reason = utcnow(), reason[:500]
            released += a.amount if a.payment_id is not None else ZERO
        self._s.flush()
        return released

    def _touch(self, touched: list[uuid.UUID], inv: PlatformInvoice) -> None:
        self.recompute(inv)
        FulfilmentService(self._s, self._actor, self._today).fulfil_settled(inv, self.line_states(inv.id))
        if inv.id not in touched:
            touched.append(inv.id)

    def recompute(self, inv: PlatformInvoice) -> None:
        if inv.status is InvoiceStatus.VOIDED:
            return
        paid = Decimal(
            self._s.execute(
                select(func.coalesce(func.sum(PlatformLineAllocation.amount), 0))
                .join(PlatformPayment, PlatformPayment.id == PlatformLineAllocation.payment_id)
                .where(
                    PlatformLineAllocation.invoice_id == inv.id,
                    PlatformLineAllocation.released_at.is_(None),
                    PlatformPayment.status == PaymentStatus.VERIFIED,
                )
            ).scalar_one()
        )
        credits = _sum(
            self._s, PlatformLineAllocation.invoice_id == inv.id, PlatformLineAllocation.credit_id.is_not(None)
        )
        inv.amount_paid, inv.credits_applied = paid, credits
        inv.balance = inv.total - paid - credits
        if inv.balance <= 0:
            inv.status = InvoiceStatus.PAID
        elif paid + credits > 0:
            inv.status = InvoiceStatus.PARTIALLY_PAID
        else:
            inv.status = InvoiceStatus.ISSUED
        self._s.flush()
