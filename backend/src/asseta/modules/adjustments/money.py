"""Shared money and balance moves behind corrections, refunds and reversals: partial release of an hours payment
allocation (never edited; released and re-written for the part kept), the customer's and custodian's balances after an
adjustment."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.modules.finance.cash_service import CashCustodyService
from asseta.modules.finance.custody_models import CashDecisionStatus, CustodyAdjustment, CustodyAdjustmentKind
from asseta.modules.finance.models import (
    AdjustmentKind,
    CustomerPayment,
    FinancialAdjustment,
    HirePaymentAllocation,
    SettlementStatus,
)
from asseta.modules.finance.receivables import ReceivablesService
from asseta.modules.hours.models import HoursPaymentAllocation
from asseta.modules.identity.principal import RequestContext

ZERO = Decimal(0)


def customer_balance(session: Session, tenant_id: uuid.UUID, customer_id: uuid.UUID, currency: str) -> Decimal:
    return ReceivablesService(session, tenant_id).balance_of(customer_id, currency).balance


def custody_outstanding(
    session: Session, ctx: RequestContext, now: datetime, staff_id: uuid.UUID, currency: str
) -> Decimal:
    rows = CashCustodyService(session, ctx, now).balances(staff_id)
    return next((b.outstanding for b in rows if b.currency == currency), ZERO)


def custody_offset(
    session: Session,
    ctx: RequestContext,
    now: datetime,
    *,
    staff_id: uuid.UUID,
    amount: Decimal,
    currency: str,
    reason: str,
    entity_type: str,
    entity_id: uuid.UUID,
    approved_by: uuid.UUID | None,
    requested_by: uuid.UUID | None,
    approved: bool = True,
) -> CustodyAdjustment:
    """An approved offsetting entry in the custodian's ledger (the decided adjustment already had two people)."""
    assert ctx.tenant_id is not None
    row = CustodyAdjustment(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        staff_member_id=staff_id,
        kind=CustodyAdjustmentKind.REVERSAL,
        amount=amount,
        currency=currency,
        occurred_at=now,
        reason=reason,
        reverses_entity_type=entity_type,
        reverses_entity_id=entity_id,
        status=CashDecisionStatus.APPROVED if approved else CashDecisionStatus.REJECTED,
        created_by=requested_by,
        created_at=now,
        decided_by=approved_by,
        decided_at=now,
        decision_note="Approved adjustment",
    )
    session.add(row)
    session.flush()
    return row


def money_record(
    session: Session,
    ctx: RequestContext,
    now: datetime,
    *,
    kind: AdjustmentKind,
    customer_id: uuid.UUID,
    amount: Decimal,
    currency: str,
    reason: str,
    request_id: uuid.UUID,
) -> FinancialAdjustment:
    assert ctx.tenant_id is not None
    row = FinancialAdjustment(
        id=uuid.uuid4(),
        tenant_id=ctx.tenant_id,
        customer_id=customer_id,
        kind=kind,
        amount=amount,
        currency=currency,
        reason=reason,
        created_by=ctx.user_id,
        created_at=now,
        adjustment_request_id=request_id,
    )
    session.add(row)
    session.flush()
    return row


def verified_allocations(session: Session, purchase_id: uuid.UUID) -> list[HoursPaymentAllocation]:
    """Active hours allocations backed by verified money, newest first (what a refund gives back first)."""
    return list(
        session.execute(
            select(HoursPaymentAllocation)
            .join(CustomerPayment, CustomerPayment.id == HoursPaymentAllocation.payment_id)
            .where(
                HoursPaymentAllocation.purchase_id == purchase_id,
                HoursPaymentAllocation.released_at.is_(None),
                CustomerPayment.status == SettlementStatus.VERIFIED,
            )
            .order_by(HoursPaymentAllocation.created_at.desc(), HoursPaymentAllocation.id)
            .with_for_update(of=HoursPaymentAllocation)
        ).scalars()
    )


def release_money(
    session: Session, ctx: RequestContext, now: datetime, purchase_id: uuid.UUID, amount: Decimal, reason: str
) -> Decimal:
    """Take `amount` of verified money off the purchase. A partly used allocation is released whole and its remainder
    written as a new allocation row, so no allocation row ever changes amount."""
    assert ctx.tenant_id is not None
    left, released = amount, ZERO
    for alloc in verified_allocations(session, purchase_id):
        if left <= 0:
            break
        take = min(alloc.amount, left)
        alloc.released_at, alloc.release_reason = now, reason
        session.flush()
        if take < alloc.amount:
            session.add(
                HoursPaymentAllocation(
                    id=uuid.uuid4(),
                    tenant_id=ctx.tenant_id,
                    payment_id=alloc.payment_id,
                    purchase_id=alloc.purchase_id,
                    amount=alloc.amount - take,
                    created_by=ctx.user_id,
                    created_at=now,
                )
            )
            session.flush()
        left -= take
        released += take
    return released


def release_hire_allocations(
    session: Session, ctx: RequestContext, now: datetime, payment_id: uuid.UUID, reason: str
) -> Decimal:
    """Every invoice this payment settled opens again: the allocations are released, never edited."""
    released = ZERO
    for alloc in session.execute(
        select(HirePaymentAllocation)
        .where(HirePaymentAllocation.payment_id == payment_id, HirePaymentAllocation.released_at.is_(None))
        .with_for_update()
    ).scalars():
        alloc.released_at, alloc.release_reason = now, reason
        released += alloc.amount
    session.flush()
    if released > 0:
        AuditService(session).record(
            actor=ctx.audit_actor(),
            action="finance.payment.allocations_released",
            entity_type="customer_payment",
            entity_id=payment_id,
            tenant_id=ctx.tenant_id,
            after={"released": str(released)},
            reason=reason,
        )
    return released
