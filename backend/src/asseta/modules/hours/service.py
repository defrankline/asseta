"""Customer hours use cases: walk-in customers, hours purchases (rate card price less the approved discount, never a
typed price), payment links and evidence, credit activation, derived balances and work execution allocations."""

import uuid
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound, PermissionDenied
from asseta.core.lifecycle import check_version, flush_versioned
from asseta.core.money import quantize
from asseta.core.outbox import OutboxWriter
from asseta.core.search import ilike_any
from asseta.modules.adjustments.models import AdjustmentRequest, AdjustmentRequestStatus, AdjustmentRequestType
from asseta.modules.finance.cash_service import CashCustodyService
from asseta.modules.finance.common import tenant_settings
from asseta.modules.finance.dto import CashCollectionIn, CustomerPaymentDto, CustomerPaymentIn
from asseta.modules.finance.models import (
    CustomerPayment,
    HirePaymentAllocation,
    HirePaymentMethod,
    SettlementStatus,
)
from asseta.modules.finance.payment_service import CustomerPaymentService, payment_dto
from asseta.modules.fleet.models import Machine, MachineStatus
from asseta.modules.geospatial.models import JobSite
from asseta.modules.hours.dto import (
    AllocationLineDto,
    CreditActivationIn,
    CustomerRegistrationIn,
    HoursBalanceDto,
    HoursPurchaseDto,
    HoursPurchaseIn,
    LedgerEntryDto,
    MachineHoursDto,
    PaymentEvidenceDto,
    PurchaseAllocationDto,
    PurchaseAllocationIn,
    PurchaseTotalsDto,
    WalkInCustomerDto,
    WalkInCustomerIn,
    WorkExecutionAllocationDto,
)
from asseta.modules.hours.engine import TOPIC, HoursEngine, minor_units
from asseta.modules.hours.ledger import (
    ZERO,
    PurchaseQueue,
    active_allocated,
    allocated_amounts,
    derived_status,
    purchase_queue_ids,
    purchase_totals,
    purchase_totals_bulk,
)
from asseta.modules.hours.models import (
    SIGN,
    CustomerDiscount,
    HoursLedgerEntry,
    HoursPaymentAllocation,
    HoursPurchase,
    LedgerEntryType,
    PaymentEvidence,
    ProposalStatus,
    WorkExecutionAllocation,
)
from asseta.modules.hours.numbering import next_number
from asseta.modules.identity.principal import RequestContext
from asseta.modules.jobs.dto import CustomerDto
from asseta.modules.jobs.models import Customer, CustomerKind, RentalRatePolicy
from asseta.modules.meter.models import CaptureAttachment, JobException

T = LedgerEntryType
PAYMENT_RECORDERS = {HirePaymentMethod.CASH: "tenant.collection.record"}
OFFICE_PAYMENT = "tenant.finance.payment"


def ledger_dto(e: HoursLedgerEntry) -> LedgerEntryDto:
    dto = LedgerEntryDto.model_validate(e)
    dto.signed_hours = SIGN[e.entry_type] * e.hours
    return dto


def purchase_dto(session: Session, p: HoursPurchase, payment: CustomerPaymentDto | None = None) -> HoursPurchaseDto:
    totals = purchase_totals(session, p)
    verified, claimed = allocated_amounts(session, p.id)
    units = minor_units(session, p.currency)
    customer = session.get(Customer, p.customer_id)
    allocs = session.execute(
        select(HoursPaymentAllocation, CustomerPayment.status)
        .join(CustomerPayment, CustomerPayment.id == HoursPaymentAllocation.payment_id)
        .where(HoursPaymentAllocation.purchase_id == p.id)
        .order_by(HoursPaymentAllocation.created_at)
    )
    allocations = []
    for a, status in allocs:
        dto = PurchaseAllocationDto.model_validate(a)
        dto.payment_status = status.value
        allocations.append(dto)
    machines = [
        MachineHoursDto(
            machine_id=mid,
            activated=m.by_type[T.ACTIVATED],
            transferred_in=m.by_type[T.TRANSFER_IN],
            consumed=m.by_type[T.CONSUMED],
            transferred_out=m.by_type[T.TRANSFER_OUT],
            expired=m.by_type[T.EXPIRED],
            reversed=m.by_type[T.REVERSAL],
            refunded=m.by_type[T.REFUNDED],
            corrected=m.by_type[T.CORRECTION_ADD] - m.by_type[T.CORRECTION_DEDUCT],
            remaining=m.remaining,
            provisional=m.by_type[T.PROVISIONAL] - m.by_type[T.PROVISIONAL_REVERSED],
        )
        for mid, m in totals.machines.items()
    ]
    return HoursPurchaseDto(
        id=p.id,
        purchase_number=p.purchase_number,
        client_id=p.client_id,
        customer_id=p.customer_id,
        customer_name=customer.name if customer else None,
        customer_kind=customer.kind if customer else None,
        machine_id=p.machine_id,
        job_site_id=p.job_site_id,
        hours=p.hours,
        currency=p.currency,
        rate_card_id=p.rate_card_id,
        hourly_rate=p.hourly_rate,
        discount_id=p.discount_id,
        discount_percent=p.discount_percent,
        effective_rate=p.effective_rate,
        amount=p.amount,
        note=p.note,
        source=p.source,
        policy_version=p.policy_version,
        created_by=p.created_by,
        created_at=p.created_at,
        cancelled_at=p.cancelled_at,
        cancellation_id=p.cancellation_id,
        client_created_at=p.client_created_at,
        pending_zero_amount_request_id=_pending_zero_amount(session, p),
        status=derived_status(p, totals),
        totals=PurchaseTotalsDto(
            purchased=p.hours,
            activated=totals.activated,
            activated_from_payments=totals.activated_payment,
            activated_on_credit=totals.activated_credit,
            awaiting_activation=(
                ZERO
                if p.cancelled_at is not None
                else max(ZERO, p.hours - totals.net_activated - totals.total(T.REFUNDED))
            ),
            consumed=totals.total(T.CONSUMED),
            transferred=totals.total(T.TRANSFER_OUT),
            expired=totals.total(T.EXPIRED),
            reversed=totals.total(T.REVERSAL),
            refunded=totals.total(T.REFUNDED),
            corrected=totals.total(T.CORRECTION_ADD) - totals.total(T.CORRECTION_DEDUCT),
            remaining=totals.remaining,
            provisional=totals.provisional,
            amount_verified=verified,
            amount_claimed_unverified=claimed,
            amount_outstanding=(
                max(ZERO, p.amount - verified - quantize(totals.total(T.REFUNDED) * p.effective_rate, units))
                if p.cancelled_at is None
                else ZERO
            ),
        ),
        machines=machines,
        allocations=allocations,
        payment=payment,
    )


def _pending_zero_amount(session: Session, p: HoursPurchase) -> uuid.UUID | None:
    if p.amount > 0 or p.cancelled_at is not None:
        return None
    return session.execute(
        select(AdjustmentRequest.id)
        .where(
            AdjustmentRequest.purchase_id == p.id,
            AdjustmentRequest.request_type == AdjustmentRequestType.ZERO_AMOUNT_ACTIVATION,
            AdjustmentRequest.status == AdjustmentRequestStatus.PROPOSED,
        )
        .limit(1)
    ).scalar_one_or_none()


def purchase_query(
    q: str | None,
    customer_id: uuid.UUID | None,
    machine_id: uuid.UUID | None,
    cancelled: bool | None,
    queue: PurchaseQueue | None = None,
    period: Sequence[ColumnElement[bool]] = (),
) -> Select[HoursPurchase]:
    stmt = select(HoursPurchase).where(*period).order_by(HoursPurchase.created_at.desc(), HoursPurchase.id)
    if queue is not None:
        stmt = stmt.where(HoursPurchase.id.in_(purchase_queue_ids(queue)))
    if customer_id:
        stmt = stmt.where(HoursPurchase.customer_id == customer_id)
    if machine_id:
        stmt = stmt.where(HoursPurchase.machine_id == machine_id)
    if cancelled is not None:
        stmt = stmt.where(
            HoursPurchase.cancelled_at.is_not(None) if cancelled else HoursPurchase.cancelled_at.is_(None)
        )
    if (match := ilike_any(q, HoursPurchase.purchase_number, Customer.name, Customer.code)) is not None:
        stmt = stmt.join(Customer, Customer.id == HoursPurchase.customer_id).where(match)
    return stmt


def allocation_dto(session: Session, wea: WorkExecutionAllocation) -> WorkExecutionAllocationDto:
    rows = session.execute(
        select(HoursLedgerEntry, HoursPurchase.purchase_number)
        .join(HoursPurchase, HoursPurchase.id == HoursLedgerEntry.purchase_id)
        .where(HoursLedgerEntry.allocation_id == wea.id, HoursLedgerEntry.entry_type == T.CONSUMED)
        .order_by(HoursLedgerEntry.created_at, HoursPurchase.purchase_number)
    )
    lines = [
        AllocationLineDto(
            purchase_id=e.purchase_id, purchase_number=n, hours=e.hours, entry_id=e.id, occurred_at=e.occurred_at
        )
        for e, n in rows
    ]
    consumed = sum((line.hours for line in lines), ZERO)
    exc = session.get(JobException, wea.exception_id) if wea.exception_id else None
    return WorkExecutionAllocationDto(
        id=wea.id,
        job_id=wea.job_id,
        customer_id=wea.customer_id,
        machine_id=wea.machine_id,
        billable_hours=wea.billable_hours,
        consumed_hours=consumed,
        overrun_hours=max(ZERO, wea.billable_hours - consumed),
        exception_id=wea.exception_id,
        exception_status=exc.status.value if exc else None,
        policy_version=wea.policy_version,
        created_at=wea.created_at,
        lines=lines,
    )


def balances(
    session: Session, customer_id: uuid.UUID | None = None, machine_id: uuid.UUID | None = None
) -> list[HoursBalanceDto]:
    """Remaining hours per (customer, machine) from the ledger, plus purchased hours still awaiting activation."""
    acc: dict[tuple[uuid.UUID, uuid.UUID], dict[str, Any]] = {}

    def row(cid: uuid.UUID, mid: uuid.UUID) -> dict[str, Any]:
        return acc.setdefault(
            (cid, mid), {"by": dict.fromkeys(LedgerEntryType, ZERO), "awaiting": ZERO, "purchases": set()}
        )

    ledger_conds: list[ColumnElement[bool]] = []
    purchase_conds: list[ColumnElement[bool]] = [HoursPurchase.cancelled_at.is_(None)]
    if customer_id is not None:
        ledger_conds.append(HoursLedgerEntry.customer_id == customer_id)
        purchase_conds.append(HoursPurchase.customer_id == customer_id)
    if machine_id is not None:
        ledger_conds.append(HoursLedgerEntry.machine_id == machine_id)
        purchase_conds.append(HoursPurchase.machine_id == machine_id)
    for cid, mid, pid, t, h in session.execute(
        select(
            HoursLedgerEntry.customer_id,
            HoursLedgerEntry.machine_id,
            HoursLedgerEntry.purchase_id,
            HoursLedgerEntry.entry_type,
            func.sum(HoursLedgerEntry.hours),
        )
        .where(*ledger_conds)
        .group_by(
            HoursLedgerEntry.customer_id,
            HoursLedgerEntry.machine_id,
            HoursLedgerEntry.purchase_id,
            HoursLedgerEntry.entry_type,
        )
    ):
        r = row(cid, mid)
        r["by"][t] += Decimal(h)
        r["purchases"].add(pid)
    purchases = list(session.execute(select(HoursPurchase).where(*purchase_conds)).scalars())
    totals_of = purchase_totals_bulk(session, purchases)
    for p in purchases:
        awaiting = max(ZERO, p.hours - totals_of[p.id].net_activated)
        if awaiting > 0:
            r = row(p.customer_id, p.machine_id)
            r["awaiting"] += awaiting
            r["purchases"].add(p.id)
    out = []
    for (cid, mid), r in sorted(acc.items(), key=lambda kv: (str(kv[0][0]), str(kv[0][1]))):
        by = r["by"]
        out.append(
            HoursBalanceDto(
                customer_id=cid,
                machine_id=mid,
                purchases=len(r["purchases"]),
                activated=by[T.ACTIVATED],
                transferred_in=by[T.TRANSFER_IN],
                consumed=by[T.CONSUMED],
                transferred_out=by[T.TRANSFER_OUT],
                expired=by[T.EXPIRED],
                reversed=by[T.REVERSAL],
                refunded=by[T.REFUNDED],
                corrected=by[T.CORRECTION_ADD] - by[T.CORRECTION_DEDUCT],
                remaining=sum((SIGN[t] * v for t, v in by.items()), ZERO),
                awaiting_activation=r["awaiting"],
                provisional=by[T.PROVISIONAL] - by[T.PROVISIONAL_REVERSED],
            )
        )
    return out


class HoursService:
    def __init__(self, session: Session, ctx: RequestContext, now: datetime):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid, self._now = session, ctx, ctx.tenant_id, now
        self._audit = AuditService(session)
        self.engine = HoursEngine(session, ctx.tenant_id, ctx.audit_actor(), now)

    def _require_enabled(self) -> None:
        if not self.engine.policy.enabled:
            raise BusinessRuleViolation("Customer hours are switched off for this tenant", code="HOURS_DISABLED")

    def _local_year(self) -> int:
        return self._now.astimezone(ZoneInfo(tenant_settings(self._s, self._tid).timezone)).year

    def _record(self, action: str, entity: str, entity_id: uuid.UUID, after: Any, reason: str | None = None) -> None:
        self._audit.record(
            actor=self._ctx.audit_actor(),
            action=action,
            entity_type=entity,
            entity_id=entity_id,
            tenant_id=self._tid,
            after=after,
            reason=reason,
        )

    # --- walk-in customers ----------------------------------------------------------------------------------
    def create_walk_in(self, body: WalkInCustomerIn) -> Customer:
        if body.client_id is not None and (existing := self._s.get(Customer, body.client_id)) is not None:
            if existing.kind is not CustomerKind.WALK_IN:
                raise Conflict("This id is already used by another customer", code="DUPLICATE_CUSTOMER")
            return existing  # offline replay
        self._require_enabled()
        if not self.engine.policy.walk_in_allowed:
            raise BusinessRuleViolation(
                "Walk-in customers are not allowed by tenant policy", code="WALK_IN_NOT_ALLOWED"
            )
        customer = Customer(
            id=body.client_id or uuid.uuid4(),
            tenant_id=self._tid,
            code=f"WALK-{next_number(self._s, self._tid, 'WALK', 0):05d}",
            name=body.name,
            contact_phone=body.phone,
            payment_terms_days=0,
            kind=CustomerKind.WALK_IN,
        )
        self._s.add(customer)
        try:
            with self._s.begin_nested():
                self._s.flush()
        except IntegrityError as exc:
            raise Conflict("Customer already exists", code="DUPLICATE_CUSTOMER") from exc
        self._record(
            "hours.walk_in.created",
            "customer",
            customer.id,
            {"code": customer.code, "name": customer.name, "kind": "WALK_IN"},
        )
        return customer

    def walk_in_dto(self, customer: Customer) -> WalkInCustomerDto:
        return WalkInCustomerDto.model_validate(customer)

    def register_customer(self, customer_id: uuid.UUID, body: CustomerRegistrationIn) -> CustomerDto:
        c = self._s.execute(select(Customer).where(Customer.id == customer_id).with_for_update()).scalar_one_or_none()
        if c is None:
            raise NotFound("Customer not found")
        check_version(c.version, body.version, "Customer")
        if c.kind is not CustomerKind.WALK_IN:
            raise Conflict("Customer is already registered", code="ALREADY_REGISTERED")
        before = CustomerDto.model_validate(c).model_dump(mode="json")
        c.kind, c.code = CustomerKind.REGISTERED, body.code
        for key in ("name", "tax_id", "contact_name", "contact_email", "payment_terms_days"):
            value = getattr(body, key)
            if value is not None:
                setattr(c, key, value)
        flush_versioned(self._s, "Customer", "DUPLICATE_CUSTOMER", "Customer code already exists")
        dto = CustomerDto.model_validate(c)
        self._audit.record(
            actor=self._ctx.audit_actor(),
            action="jobs.customer.registered",
            entity_type="customer",
            entity_id=c.id,
            tenant_id=self._tid,
            before=before,
            after=dto.model_dump(mode="json"),
        )
        return dto

    # --- purchases ------------------------------------------------------------------------------------------
    def purchase(self, purchase_id: uuid.UUID) -> HoursPurchase:
        row = self._s.get(HoursPurchase, purchase_id)
        if row is None:
            raise NotFound("Hours purchase not found")
        return row

    def _discount(self, customer_id: uuid.UUID) -> CustomerDiscount | None:
        today = self._now.astimezone(ZoneInfo(tenant_settings(self._s, self._tid).timezone)).date()
        return self._s.execute(
            select(CustomerDiscount)
            .where(
                CustomerDiscount.customer_id == customer_id,
                CustomerDiscount.status == ProposalStatus.APPROVED,
                CustomerDiscount.effective_from <= today,
                (CustomerDiscount.effective_to.is_(None)) | (CustomerDiscount.effective_to >= today),
            )
            .order_by(CustomerDiscount.effective_from.desc(), CustomerDiscount.decided_at.desc())
            .limit(1)
        ).scalar_one_or_none()

    def _rate_card(self, machine: Machine) -> RentalRatePolicy:
        card = (
            self._s.execute(
                select(RentalRatePolicy)
                .where(
                    RentalRatePolicy.machine_category_id == machine.category_id,
                    RentalRatePolicy.effective_from <= self._now,
                )
                .order_by(RentalRatePolicy.effective_from.desc())
                .limit(1)
            ).scalar_one_or_none()
            if machine.category_id is not None
            else None
        )
        if card is None:
            raise BusinessRuleViolation(
                "No rate card applies to this machine's category; the standard rate is the only price source",
                code="NO_RATE",
            )
        return card

    def _check_payment_permission(self, method: HirePaymentMethod) -> None:
        needed = {PAYMENT_RECORDERS.get(method, OFFICE_PAYMENT), OFFICE_PAYMENT}
        if not needed & self._ctx.permissions:
            raise PermissionDenied(
                f"Recording a {method.value} payment needs {' or '.join(sorted(needed))}", code="PAYMENT_NOT_PERMITTED"
            )

    def create_purchase(self, body: HoursPurchaseIn, source: str = "API") -> HoursPurchaseDto:
        if body.client_id is not None:
            existing = self._s.execute(
                select(HoursPurchase).where(HoursPurchase.client_id == body.client_id)
            ).scalar_one_or_none()
            if existing is not None:
                return purchase_dto(self._s, existing)  # offline retry: exactly one purchase
        self._require_enabled()
        if body.payment is not None:
            self._check_payment_permission(body.payment.method)
        if body.walk_in is not None:
            walk_in = body.walk_in
            if walk_in.client_id is None and body.client_id is not None:
                walk_in = walk_in.model_copy(update={"client_id": uuid.uuid5(body.client_id, "walk-in")})
            customer = self.create_walk_in(walk_in)
        else:
            assert body.customer_id is not None
            found = self._s.get(Customer, body.customer_id)
            if found is None:
                raise NotFound("Customer not found")
            customer = found
        if not customer.is_active:
            raise BusinessRuleViolation("Customer is deactivated", code="CUSTOMER_INACTIVE")
        machine = self._s.get(Machine, body.machine_id)
        if machine is None:
            raise NotFound("Machine not found")
        if machine.status is MachineStatus.DISPOSED:
            raise BusinessRuleViolation("Machine is retired", code="MACHINE_INACTIVE")
        if body.job_site_id is not None:
            site = self._s.get(JobSite, body.job_site_id)
            if site is None:
                raise NotFound("Job site not found")
            if not site.is_active:
                raise BusinessRuleViolation("Job site is deactivated", code="SITE_INACTIVE")
        card = self._rate_card(machine)
        discount = self._discount(customer.id)
        pct = discount.percent if discount else Decimal(0)
        if pct > self.engine.policy.max_discount_percent:
            raise BusinessRuleViolation(
                f"The customer's discount exceeds the tenant maximum of {self.engine.policy.max_discount_percent}%",
                code="DISCOUNT_ABOVE_MAXIMUM",
            )
        effective_rate = (card.hourly_rate * (Decimal(100) - pct) / Decimal(100)).quantize(Decimal("0.0001"))
        amount = quantize(body.hours * effective_rate, minor_units(self._s, card.currency))
        year = self._local_year()
        purchase = HoursPurchase(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            purchase_number=f"HP-{year}-{next_number(self._s, self._tid, 'HP', year):05d}",
            client_id=body.client_id,
            customer_id=customer.id,
            machine_id=machine.id,
            job_site_id=body.job_site_id,
            hours=body.hours,
            currency=card.currency,
            rate_card_id=card.id,
            hourly_rate=card.hourly_rate,
            discount_id=discount.id if discount else None,
            discount_percent=pct,
            effective_rate=effective_rate,
            amount=amount,
            note=body.note,
            source=source,
            policy_version=self.engine.eff.version_stamp,
            created_by=self._ctx.user_id,
            created_at=self._now,
            client_created_at=body.client_created_at,
        )
        self._s.add(purchase)
        self._s.flush()
        self._record(
            "hours.purchase.recorded",
            "hours_purchase",
            purchase.id,
            {
                "purchase_number": purchase.purchase_number,
                "customer_id": str(customer.id),
                "machine_id": str(machine.id),
                "hours": str(purchase.hours),
                "rate_card_id": str(card.id),
                "hourly_rate": str(card.hourly_rate),
                "discount_percent": str(pct),
                "amount": str(amount),
                "currency": purchase.currency,
            },
        )
        OutboxWriter(self._s).emit(
            topic=TOPIC,
            event_type="HoursPurchaseRecorded",
            key=str(customer.id),
            payload={
                "purchase_id": str(purchase.id),
                "purchase_number": purchase.purchase_number,
                "customer_id": str(customer.id),
                "machine_id": str(machine.id),
                "hours": str(purchase.hours),
                "amount": str(amount),
                "currency": purchase.currency,
            },
            tenant_id=self._tid,
        )
        if amount <= 0:  # nothing to pay: a second person approves, unless the tenant lets it activate on recording
            if self.engine.policy.zero_amount_requires_approval:
                from asseta.modules.adjustments.requests import AdjustmentRequests  # lazy: builds on the hours modules

                AdjustmentRequests(self._s, self._ctx, self._now).propose_zero_amount(purchase)
            else:
                self.engine.activate_from_payments(purchase)
        payment_out = None
        if body.payment is not None:
            payment_out = self._take_payment(purchase, body, source)
        return purchase_dto(self._s, purchase, payment_out)

    def _take_payment(self, purchase: HoursPurchase, body: HoursPurchaseIn, source: str) -> CustomerPaymentDto:
        pay = body.payment
        assert pay is not None
        client_id = uuid.uuid5(body.client_id, "payment") if body.client_id else None
        amount = pay.amount or purchase.amount
        if amount <= 0:
            raise BusinessRuleViolation("Nothing to pay on this purchase", code="NOTHING_TO_PAY")
        if pay.method is HirePaymentMethod.CASH:
            recorded = CashCustodyService(self._s, self._ctx, self._now).record_collection(
                CashCollectionIn(
                    client_id=client_id,
                    customer_id=purchase.customer_id,
                    amount=amount,
                    currency=purchase.currency,
                    received_at=pay.received_at,
                    staff_member_id=pay.staff_member_id,
                    reference=pay.reference,
                    note=pay.note or f"Hours purchase {purchase.purchase_number}",
                ),
                source,
                link_satisfied=True,  # the allocation to this purchase follows just below
            )
        else:
            recorded = CustomerPaymentService(self._s, self._ctx, self._now).record(
                CustomerPaymentIn(
                    customer_id=purchase.customer_id,
                    amount=amount,
                    currency=purchase.currency,
                    method=pay.method,
                    reference=pay.reference,
                    received_at=pay.received_at,
                    received_by_staff_id=pay.staff_member_id,
                    note=pay.note or f"Hours purchase {purchase.purchase_number}",
                    client_id=client_id,
                ),
                source,
            )
        if pay.evidence_attachment_ids:
            self.link_evidence(recorded.id, pay.evidence_attachment_ids)
        if purchase.amount > 0:
            self.allocate(
                purchase.id, PurchaseAllocationIn(payment_id=recorded.id, amount=min(amount, purchase.amount))
            )
        return payment_dto(self._s, self._payment(recorded.id))

    def _payment(self, payment_id: uuid.UUID, lock: bool = False) -> CustomerPayment:
        stmt = select(CustomerPayment).where(CustomerPayment.id == payment_id)
        row = self._s.execute(stmt.with_for_update() if lock else stmt).scalar_one_or_none()
        if row is None:
            raise NotFound("Payment not found")
        return row

    def allocate(self, purchase_id: uuid.UUID, body: PurchaseAllocationIn) -> HoursPurchaseDto:
        """Link a payment to the purchase (same rules as invoice allocations: row locks, no over-allocation)."""
        payment = self._payment(body.payment_id, lock=True)
        purchase = self.engine.lock_purchase(purchase_id)
        if payment.status is SettlementStatus.REJECTED:
            raise BusinessRuleViolation("A rejected payment cannot be allocated", code="PAYMENT_REJECTED")
        if payment.reversed_at is not None:
            raise BusinessRuleViolation("A reversed payment cannot be allocated", code="PAYMENT_REVERSED")
        if purchase.cancelled_at is not None:
            raise BusinessRuleViolation("The purchase is cancelled", code="PURCHASE_CANCELLED")
        if payment.customer_id != purchase.customer_id or payment.currency != purchase.currency:
            raise BusinessRuleViolation("Payment belongs to another customer or currency", code="ALLOCATION_MISMATCH")
        open_amount = purchase.amount - active_allocated(self._s, purchase_id=purchase.id)
        if body.amount > open_amount:
            raise BusinessRuleViolation(
                f"Allocation exceeds the purchase's open amount {open_amount}", code="OVER_ALLOCATION"
            )
        hire = Decimal(
            self._s.execute(
                select(func.coalesce(func.sum(HirePaymentAllocation.amount), 0)).where(
                    HirePaymentAllocation.payment_id == payment.id, HirePaymentAllocation.released_at.is_(None)
                )
            ).scalar_one()
        )
        if hire + active_allocated(self._s, payment_id=payment.id) + body.amount > payment.amount:
            raise BusinessRuleViolation("Allocations exceed the payment amount", code="ALLOCATION_EXCEEDS_PAYMENT")
        alloc = HoursPaymentAllocation(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            payment_id=payment.id,
            purchase_id=purchase.id,
            amount=body.amount,
            created_by=self._ctx.user_id,
            created_at=self._now,
        )
        self._s.add(alloc)
        self._s.flush()
        self._record(
            "hours.payment.allocated",
            "hours_payment_allocation",
            alloc.id,
            {"payment_id": str(payment.id), "purchase_id": str(purchase.id), "amount": str(body.amount)},
        )
        if payment.status is SettlementStatus.VERIFIED:
            self.engine.activate_from_payments(purchase, payment.id)
        return purchase_dto(self._s, purchase)

    def link_collection(self, payment_id: uuid.UUID, purchase_ref: uuid.UUID, amount: Decimal) -> None:
        """Link a cash collection to the purchase it pays for: the purchase's id or its offline client id; up to the
        open amount (anything above stays as customer credit)."""
        purchase_id = self._s.execute(
            select(HoursPurchase.id).where(
                (HoursPurchase.id == purchase_ref) | (HoursPurchase.client_id == purchase_ref)
            )
        ).scalar_one_or_none()
        if purchase_id is None:
            raise NotFound("Hours purchase not found", code="PURCHASE_NOT_FOUND")
        purchase = self.engine.lock_purchase(purchase_id)
        open_amount = purchase.amount - active_allocated(self._s, purchase_id=purchase.id)
        if open_amount <= 0:
            raise BusinessRuleViolation("This purchase is already fully paid for", code="OVER_ALLOCATION")
        self.allocate(purchase.id, PurchaseAllocationIn(payment_id=payment_id, amount=min(amount, open_amount)))

    def credit_activate(self, purchase_id: uuid.UUID, body: CreditActivationIn) -> HoursPurchaseDto:
        self._require_enabled()
        purchase = self.engine.lock_purchase(purchase_id)
        self.engine.activate_on_credit(purchase, body.hours, body.reason)
        return purchase_dto(self._s, purchase)

    # --- evidence -------------------------------------------------------------------------------------------
    def link_evidence(self, payment_id: uuid.UUID, attachment_ids: list[uuid.UUID]) -> list[PaymentEvidenceDto]:
        """Evidence only: attaching a receipt never changes the payment's CLAIMED/VERIFIED status."""
        payment = self._payment(payment_id)
        for att in dict.fromkeys(attachment_ids):
            if self._s.get(CaptureAttachment, att) is None:
                raise NotFound("Evidence attachment not found", code="ATTACHMENT_NOT_FOUND")
            self._s.execute(
                pg_insert(PaymentEvidence)
                .values(
                    id=uuid.uuid4(),
                    tenant_id=self._tid,
                    payment_id=payment.id,
                    attachment_id=att,
                    created_by=self._ctx.user_id,
                    created_at=self._now,
                )
                .on_conflict_do_nothing(constraint="uq_payment_evidence")
            )
        self._record(
            "finance.payment.evidence_attached",
            "customer_payment",
            payment.id,
            {"attachment_ids": [str(a) for a in attachment_ids], "status": payment.status.value},
        )
        return self.evidence(payment.id)

    def evidence(self, payment_id: uuid.UUID) -> list[PaymentEvidenceDto]:
        self._payment(payment_id)
        rows = self._s.execute(
            select(PaymentEvidence)
            .where(PaymentEvidence.payment_id == payment_id)
            .order_by(PaymentEvidence.created_at, PaymentEvidence.id)
        ).scalars()
        return [PaymentEvidenceDto.model_validate(r) for r in rows]
