"""Credit invoices (ADR-008 §1): the CREDIT line of an order is invoiced automatically when the order is recorded
(CI-<yyyy>-<nnnnn>, due after the customer's payment terms). The customer pays it in full or in parts, each part cash,
bank or mobile money, recorded by the office or by field staff (cash goes into the recorder's custody like any
collection). Every part is an ordinary customer payment, linked to the invoice and to the order, so verified money
activates the order's hours and settles the credit exposure exactly as other payments do.

Nothing about an invoice is stored after it is created except a single rejection stamp (the credit was not approved,
`reject_credit`): what was paid (recorded payments that are not rejected or reversed), the status (UNPAID, PART_PAID,
PAID, CANCELLED with its order or when its credit was rejected) and whether it is overdue are derived."""

import uuid
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import ColumnElement, Select, and_, case, func, or_, select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.errors import BusinessRuleViolation, NotFound, PermissionDenied
from asseta.core.outbox import OutboxWriter
from asseta.core.search import ilike_any
from asseta.modules.customers.models import Customer
from asseta.modules.finance.common import tenant_settings
from asseta.modules.finance.models import CustomerPayment, HirePaymentMethod, SettlementStatus
from asseta.modules.hours.dto import (
    CreditInvoiceDto,
    CreditInvoicePaymentDto,
    CreditInvoicePaymentIn,
    CreditInvoiceStatus,
    CreditInvoiceSummaryDto,
    CreditRejectionDto,
)
from asseta.modules.hours.ledger import ZERO
from asseta.modules.hours.models import CreditInvoice, CreditInvoicePayment, HoursPurchase
from asseta.modules.hours.numbering import next_number
from asseta.modules.identity.principal import RequestContext

TOPIC = "asseta.hours"
SERIES = "CI"
OFFICE_PAYMENT = "tenant.finance.payment"


def local_today(session: Session, tenant_id: uuid.UUID, now: datetime) -> date:
    return now.astimezone(ZoneInfo(tenant_settings(session, tenant_id).timezone)).date()


def invoice_cancelled() -> ColumnElement[bool]:
    """The invoice's order was cancelled or its credit was rejected (needs `HoursPurchase` joined)."""
    return or_(HoursPurchase.cancelled_at.is_not(None), CreditInvoice.rejected_at.is_not(None))


def invoice_open() -> tuple[ColumnElement[bool], ...]:
    """Credit invoices that can still be owed: their order is not cancelled and their credit was not rejected."""
    return (
        HoursPurchase.id == CreditInvoice.purchase_id,
        HoursPurchase.cancelled_at.is_(None),
        CreditInvoice.rejected_at.is_(None),
    )


def rejection_dto(inv: CreditInvoice) -> CreditRejectionDto | None:
    if inv.rejected_at is None:
        return None
    return CreditRejectionDto(
        rejected_at=inv.rejected_at,
        rejected_by=inv.rejected_by,
        reason=inv.rejection_reason or "",
        hours=inv.hours,
        amount=inv.amount,
    )


def _counting() -> ColumnElement[bool]:
    """A linked payment pays the invoice until it is rejected or reversed."""
    return and_(CustomerPayment.status != SettlementStatus.REJECTED, CustomerPayment.reversed_at.is_(None))


def paid_subquery() -> Any:
    """Correlated: money recorded against `CreditInvoice` that still counts."""
    return (
        select(func.coalesce(func.sum(CreditInvoicePayment.amount), 0))
        .join(CustomerPayment, CustomerPayment.id == CreditInvoicePayment.payment_id)
        .where(CreditInvoicePayment.invoice_id == CreditInvoice.id, _counting())
        .scalar_subquery()
    )


def paid_figures(session: Session, invoice_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, tuple[Decimal, Decimal]]:
    """(paid, of which verified) per invoice."""
    out: dict[uuid.UUID, tuple[Decimal, Decimal]] = {}
    if not invoice_ids:
        return out
    verified = case((CustomerPayment.status == SettlementStatus.VERIFIED, CreditInvoicePayment.amount), else_=ZERO)
    for inv_id, paid, ver in session.execute(
        select(CreditInvoicePayment.invoice_id, func.sum(CreditInvoicePayment.amount), func.sum(verified))
        .join(CustomerPayment, CustomerPayment.id == CreditInvoicePayment.payment_id)
        .where(CreditInvoicePayment.invoice_id.in_(invoice_ids), _counting())
        .group_by(CreditInvoicePayment.invoice_id)
    ):
        out[inv_id] = (Decimal(paid), Decimal(ver))
    return out


def derive_status(amount: Decimal, paid: Decimal, cancelled: bool) -> CreditInvoiceStatus:
    if cancelled:
        return "CANCELLED"
    if paid >= amount:
        return "PAID"
    return "PART_PAID" if paid > 0 else "UNPAID"


def invoice_query(
    today: date,
    q: str | None = None,
    customer_id: uuid.UUID | None = None,
    status: CreditInvoiceStatus | None = None,
    overdue: bool | None = None,
    purchase_id: uuid.UUID | None = None,
    period: Sequence[ColumnElement[bool]] = (),
    open_only: bool = False,
) -> Select[CreditInvoice]:
    """Credit invoices, newest first. Status and overdue are derived, so the filters read the payments."""
    paid = paid_subquery()
    cancelled = invoice_cancelled()
    stmt = (
        select(CreditInvoice)
        .join(HoursPurchase, HoursPurchase.id == CreditInvoice.purchase_id)
        .where(*period)
        .order_by(CreditInvoice.issued_at.desc(), CreditInvoice.invoice_number.desc())
    )
    if customer_id is not None:
        stmt = stmt.where(CreditInvoice.customer_id == customer_id)
    if purchase_id is not None:
        stmt = stmt.where(CreditInvoice.purchase_id == purchase_id)
    if open_only:  # UNPAID or PART_PAID
        stmt = stmt.where(~cancelled, paid < CreditInvoice.amount)
    if status == "CANCELLED":
        stmt = stmt.where(cancelled)
    elif status == "PAID":
        stmt = stmt.where(~cancelled, paid >= CreditInvoice.amount)
    elif status == "PART_PAID":
        stmt = stmt.where(~cancelled, paid > 0, paid < CreditInvoice.amount)
    elif status == "UNPAID":
        stmt = stmt.where(~cancelled, paid <= 0)
    open_and_due = and_(~cancelled, paid < CreditInvoice.amount, CreditInvoice.due_date < today)
    if overdue is True:
        stmt = stmt.where(open_and_due)
    elif overdue is False:
        stmt = stmt.where(~open_and_due)
    if (match := ilike_any(q, CreditInvoice.invoice_number, HoursPurchase.purchase_number, Customer.name)) is not None:
        stmt = stmt.join(Customer, Customer.id == CreditInvoice.customer_id).where(match)
    return stmt


def _overdue(inv: CreditInvoice, status: CreditInvoiceStatus, today: date) -> int:
    return (today - inv.due_date).days if status in ("UNPAID", "PART_PAID") and inv.due_date < today else 0


def invoice_summaries(
    session: Session, tenant_id: uuid.UUID, now: datetime, purchase_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, CreditInvoiceSummaryDto]:
    """The credit invoice of each order that has one (keyed by purchase id)."""
    if not purchase_ids:
        return {}
    rows = list(
        session.execute(
            select(CreditInvoice, HoursPurchase.cancelled_at)
            .join(HoursPurchase, HoursPurchase.id == CreditInvoice.purchase_id)
            .where(CreditInvoice.purchase_id.in_(purchase_ids))
        ).all()
    )
    figures = paid_figures(session, [inv.id for inv, _ in rows])
    today = local_today(session, tenant_id, now)
    out = {}
    for inv, cancelled_at in rows:
        paid, _ = figures.get(inv.id, (ZERO, ZERO))
        status = derive_status(inv.amount, paid, cancelled_at is not None or inv.rejected_at is not None)
        out[inv.purchase_id] = CreditInvoiceSummaryDto(
            id=inv.id,
            invoice_number=inv.invoice_number,
            amount=inv.amount,
            paid=paid,
            balance=max(ZERO, inv.amount - paid) if status != "CANCELLED" else ZERO,
            due_date=inv.due_date,
            status=status,
            overdue=_overdue(inv, status, today) > 0,
            rejection=rejection_dto(inv),
        )
    return out


def invoice_dtos(
    session: Session, tenant_id: uuid.UUID, now: datetime, invoices: Sequence[CreditInvoice], with_payments: bool
) -> list[CreditInvoiceDto]:
    if not invoices:
        return []
    ids = [i.id for i in invoices]
    figures = paid_figures(session, ids)
    purchases = {
        p.id: p
        for p in session.execute(
            select(HoursPurchase).where(HoursPurchase.id.in_({i.purchase_id for i in invoices}))
        ).scalars()
    }
    payments: dict[uuid.UUID, list[CreditInvoicePaymentDto]] = {i: [] for i in ids}
    if with_payments:
        for link, pay in session.execute(
            select(CreditInvoicePayment, CustomerPayment)
            .join(CustomerPayment, CustomerPayment.id == CreditInvoicePayment.payment_id)
            .where(CreditInvoicePayment.invoice_id.in_(ids))
            .order_by(CreditInvoicePayment.created_at, CreditInvoicePayment.id)
        ):
            payments[link.invoice_id].append(
                CreditInvoicePaymentDto(
                    id=link.id,
                    payment_id=pay.id,
                    amount=link.amount,
                    method=pay.method,
                    reference=pay.reference,
                    collection_number=pay.collection_number,
                    payment_status=pay.status.value,
                    received_at=pay.received_at,
                    received_by_staff_id=pay.received_by_staff_id,
                    recorded_by=pay.recorded_by,
                    created_at=link.created_at,
                    counts=pay.status is not SettlementStatus.REJECTED and pay.reversed_at is None,
                )
            )
    today = local_today(session, tenant_id, now)
    out = []
    for inv in invoices:
        purchase = purchases[inv.purchase_id]
        paid, verified = figures.get(inv.id, (ZERO, ZERO))
        status = derive_status(inv.amount, paid, purchase.cancelled_at is not None or inv.rejected_at is not None)
        days = _overdue(inv, status, today)
        out.append(
            CreditInvoiceDto(
                id=inv.id,
                invoice_number=inv.invoice_number,
                purchase_id=inv.purchase_id,
                purchase_number=purchase.purchase_number,
                customer_id=inv.customer_id,
                machine_id=inv.machine_id,
                currency=inv.currency,
                hours=inv.hours,
                unit_price=inv.unit_price,
                amount=inv.amount,
                paid=paid,
                paid_verified=verified,
                balance=max(ZERO, inv.amount - paid) if status != "CANCELLED" else ZERO,
                payment_terms_days=inv.payment_terms_days,
                issued_at=inv.issued_at,
                due_date=inv.due_date,
                status=status,
                overdue=days > 0,
                days_overdue=days,
                created_by=inv.created_by,
                rejection=rejection_dto(inv),
                payments=payments[inv.id],
            )
        )
    return out


def create_credit_invoice(
    session: Session,
    ctx: RequestContext,
    now: datetime,
    purchase: HoursPurchase,
    customer: Customer,
    amount: Decimal,
) -> CreditInvoice:
    """The order's credit invoice: the CREDIT line's amount at the order's effective rate, due after the customer's
    payment terms (tenant-local days)."""
    assert ctx.tenant_id is not None
    today = local_today(session, ctx.tenant_id, now)
    hours = (amount / purchase.effective_rate).quantize(Decimal("0.01")) if purchase.effective_rate > 0 else ZERO
    inv = CreditInvoice(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        invoice_number=f"{SERIES}-{today.year}-{next_number(session, ctx.tenant_id, SERIES, today.year):05d}",
        purchase_id=purchase.id,
        customer_id=customer.id,
        machine_id=purchase.machine_id,
        currency=purchase.currency,
        hours=min(hours, purchase.hours),
        unit_price=purchase.effective_rate,
        amount=amount,
        payment_terms_days=customer.payment_terms_days,
        issued_at=now,
        due_date=today + timedelta(days=customer.payment_terms_days),
        created_by=ctx.user_id,
        created_at=now,
    )
    session.add(inv)
    session.flush()
    AuditService(session).record(
        actor=ctx.audit_actor(),
        action="hours.credit_invoice.created",
        entity_type="credit_invoice",
        entity_id=inv.id,
        tenant_id=ctx.tenant_id,
        after={
            "invoice_number": inv.invoice_number,
            "purchase_id": str(purchase.id),
            "customer_id": str(customer.id),
            "amount": str(amount),
            "currency": inv.currency,
            "due_date": inv.due_date.isoformat(),
        },
    )
    OutboxWriter(session).emit(
        topic=TOPIC,
        event_type="HoursCreditSaleRecorded",
        key=str(customer.id),
        payload={
            "invoice_id": str(inv.id),
            "invoice_number": inv.invoice_number,
            "purchase_id": str(purchase.id),
            "purchase_number": purchase.purchase_number,
            "customer_id": str(customer.id),
            "machine_id": str(purchase.machine_id),
            "hours": str(purchase.hours),
            "credit_amount": str(amount),
            "currency": inv.currency,
            "due_date": inv.due_date.isoformat(),
        },
        tenant_id=ctx.tenant_id,
    )
    return inv


class CreditInvoiceService:
    def __init__(self, session: Session, ctx: RequestContext, now: datetime):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid, self._now = session, ctx, ctx.tenant_id, now

    def invoice(self, invoice_id: uuid.UUID, lock: bool = False) -> CreditInvoice:
        stmt = select(CreditInvoice).where(CreditInvoice.id == invoice_id)
        row = self._s.execute(stmt.with_for_update() if lock else stmt).scalar_one_or_none()
        if row is None:
            raise NotFound("Credit invoice not found", code="INVOICE_NOT_FOUND")
        return row

    def dto(self, inv: CreditInvoice) -> CreditInvoiceDto:
        return invoice_dtos(self._s, self._tid, self._now, [inv], with_payments=True)[0]

    def _replayed(self, client_id: uuid.UUID | None) -> CreditInvoice | None:
        if client_id is None:
            return None
        return self._s.execute(
            select(CreditInvoice)
            .join(CreditInvoicePayment, CreditInvoicePayment.invoice_id == CreditInvoice.id)
            .join(CustomerPayment, CustomerPayment.id == CreditInvoicePayment.payment_id)
            .where(CustomerPayment.client_id == client_id)
        ).scalar_one_or_none()

    def record_payment(
        self, invoice_id: uuid.UUID, body: CreditInvoicePaymentIn, source: str = "API"
    ) -> CreditInvoiceDto:
        """A payment in full or in part. Refused above the balance (INVOICE_OVERPAYMENT), on a paid invoice
        (INVOICE_PAID) and on the invoice of a cancelled order or of rejected credit (INVOICE_CANCELLED)."""
        # Lazy: the hours service builds on this module (it creates the invoice with the order).
        from asseta.modules.finance.cash_service import CashCustodyService
        from asseta.modules.finance.dto import CashCollectionIn, CustomerPaymentIn
        from asseta.modules.finance.payment_service import CustomerPaymentService
        from asseta.modules.hours.cash_activation import CashActivation
        from asseta.modules.hours.dto import PurchaseAllocationIn
        from asseta.modules.hours.engine import hours_policy
        from asseta.modules.hours.ledger import active_allocated
        from asseta.modules.hours.service import HoursService

        if (replay := self._replayed(body.client_id)) is not None:
            return self.dto(replay)  # offline retry: exactly one payment
        inv = self.invoice(invoice_id, lock=True)
        purchase = self._s.get(HoursPurchase, inv.purchase_id)
        assert purchase is not None
        if purchase.cancelled_at is not None:
            raise BusinessRuleViolation("The order of this invoice was cancelled", code="INVOICE_CANCELLED")
        if inv.rejected_at is not None:
            raise BusinessRuleViolation(
                "The credit of this invoice was not approved: the invoice is cancelled", code="INVOICE_CANCELLED"
            )
        paid, _ = paid_figures(self._s, [inv.id]).get(inv.id, (ZERO, ZERO))
        balance = inv.amount - paid
        if balance <= 0:
            raise BusinessRuleViolation("This invoice is already paid", code="INVOICE_PAID")
        if body.amount > balance:
            raise BusinessRuleViolation(
                f"The payment {body.amount} is more than the invoice balance {balance}", code="INVOICE_OVERPAYMENT"
            )
        method = HirePaymentMethod(body.method)
        policy = hours_policy(self._s, self._tid, self._now).policy
        if method is not HirePaymentMethod.CASH and not (
            OFFICE_PAYMENT in self._ctx.permissions or policy.field_noncash_payments
        ):
            raise PermissionDenied(
                f"Recording a {method.value} payment needs {OFFICE_PAYMENT} (or the company setting that lets field "
                "staff record bank and mobile-money payments)",
                code="PAYMENT_NOT_PERMITTED",
            )
        note = body.note or f"Credit invoice {inv.invoice_number}"
        if method is HirePaymentMethod.CASH:
            recorded = CashCustodyService(self._s, self._ctx, self._now).record_collection(
                CashCollectionIn(
                    client_id=body.client_id,
                    customer_id=inv.customer_id,
                    amount=body.amount,
                    currency=inv.currency,
                    received_at=body.received_at,
                    staff_member_id=body.staff_member_id,
                    reference=body.reference,
                    note=note,
                ),
                source,
                link_satisfied=True,  # linked to the invoice and its order just below
            )
        else:
            recorded = CustomerPaymentService(self._s, self._ctx, self._now).record(
                CustomerPaymentIn(
                    customer_id=inv.customer_id,
                    amount=body.amount,
                    currency=inv.currency,
                    method=method,
                    reference=body.reference,
                    received_at=body.received_at,
                    received_by_staff_id=body.staff_member_id,
                    note=note,
                    client_id=body.client_id,
                ),
                source,
            )
        hours = HoursService(self._s, self._ctx, self._now)
        if body.evidence_attachment_ids:
            hours.link_evidence(recorded.id, body.evidence_attachment_ids)
        link = CreditInvoicePayment(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            invoice_id=inv.id,
            payment_id=recorded.id,
            amount=body.amount,
            created_by=self._ctx.user_id,
            created_at=self._now,
        )
        self._s.add(link)
        self._s.flush()
        # The money also pays the order (up to what is still open), so once verified it activates the order's hours
        # and settles the credit exposure like any payment of the order.
        open_amount = purchase.amount - active_allocated(self._s, purchase_id=purchase.id)
        if open_amount > 0:
            hours.allocate(
                purchase.id, PurchaseAllocationIn(payment_id=recorded.id, amount=min(body.amount, open_amount))
            )
        if method is HirePaymentMethod.CASH:
            CashActivation(self._s, self._tid, self._ctx.user_id, self._now).on_recorded(recorded.id)
        AuditService(self._s).record(
            actor=self._ctx.audit_actor(source.lower()),
            action="hours.credit_invoice.payment_recorded",
            entity_type="credit_invoice",
            entity_id=inv.id,
            tenant_id=self._tid,
            after={
                "invoice_number": inv.invoice_number,
                "payment_id": str(recorded.id),
                "amount": str(body.amount),
                "method": method.value,
                "balance_after": str(balance - body.amount),
            },
        )
        OutboxWriter(self._s).emit(
            topic=TOPIC,
            event_type="CreditInvoicePaymentRecorded",
            key=str(inv.customer_id),
            payload={
                "invoice_id": str(inv.id),
                "invoice_number": inv.invoice_number,
                "payment_id": str(recorded.id),
                "customer_id": str(inv.customer_id),
                "amount": str(body.amount),
                "currency": inv.currency,
                "method": method.value,
                "balance_after": str(balance - body.amount),
            },
            tenant_id=self._tid,
        )
        return self.dto(inv)
