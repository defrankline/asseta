"""Customer and rate-card use cases (tenant scope): add and edit customers (the code is optional: the server assigns
CUST-<nnnnn> when it is left blank), deactivate/reactivate them, and version the rate card. Nothing is hard-deleted;
every change is audited."""

import uuid
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.db import utcnow
from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound
from asseta.core.lifecycle import check_version, flush_versioned, mark_active, mark_inactive
from asseta.core.search import ilike_any
from asseta.modules.customers.dto import CustomerDto, CustomerIn, CustomerUpdateIn, RateCardDto, RateCardIn
from asseta.modules.customers.models import Customer, RentalRatePolicy
from asseta.modules.hours.numbering import next_number
from asseta.modules.identity.principal import RequestContext
from asseta.modules.tenancy.models import TenantSettings

CODE_SERIES = "CUST"


def check_active_customer(session: Session, customer_id: uuid.UUID) -> Customer:
    customer = session.get(Customer, customer_id)
    if customer is None:
        raise NotFound("Customer not found")
    if not customer.is_active:
        raise BusinessRuleViolation("Customer is deactivated", code="CUSTOMER_INACTIVE")
    return customer


def customer_query(q: str | None, include_inactive: bool) -> Select[Customer]:
    stmt = select(Customer).order_by(Customer.name)
    if (match := ilike_any(q, Customer.name, Customer.code)) is not None:
        stmt = stmt.where(match)
    return stmt if include_inactive else stmt.where(Customer.is_active.is_(True))


def generate_customer_code(session: Session, tenant_id: uuid.UUID) -> str:
    """The next free CUST-<nnnnn> of the tenant (a code typed by a person may already hold a number: skip it)."""
    while True:
        code = f"{CODE_SERIES}-{next_number(session, tenant_id, CODE_SERIES, 0):05d}"
        taken = session.execute(select(Customer.id).where(Customer.code == code).limit(1)).first()
        if taken is None:
            return code


class CustomerService:
    def __init__(self, session: Session, ctx: RequestContext):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid = session, ctx, ctx.tenant_id
        self._audit = AuditService(session)

    def _record(
        self, action: str, entity: str, entity_id: uuid.UUID, before: Any, after: Any, reason: str | None = None
    ) -> None:
        self._audit.record(
            actor=self._ctx.audit_actor(),
            action=action,
            entity_type=entity,
            entity_id=entity_id,
            tenant_id=self._tid,
            before=before,
            after=after,
            reason=reason,
        )

    def _get(self, customer_id: uuid.UUID) -> Customer:
        row = self._s.execute(select(Customer).where(Customer.id == customer_id).with_for_update()).scalar_one_or_none()
        if row is None:  # other tenants' rows are invisible under RLS
            raise NotFound("Customer not found")
        return row

    def _insert(self, obj: Any, code: str, msg: str) -> None:
        try:
            with self._s.begin_nested():
                self._s.add(obj)
                self._s.flush()
        except IntegrityError as exc:
            raise Conflict(msg, code=code) from exc

    # --- customers ----------------------------------------------------------------------------------
    def create_customer(self, body: CustomerIn) -> CustomerDto:
        values = body.model_dump()
        values["code"] = body.code or generate_customer_code(self._s, self._tid)
        c = Customer(id=uuid.uuid4(), tenant_id=self._tid, **values)
        self._insert(c, "DUPLICATE_CUSTOMER", "Customer code already exists")
        dto = CustomerDto.model_validate(c)
        self._record("customers.customer.created", "customer", c.id, None, dto.model_dump(mode="json"))
        return dto

    def customer(self, customer_id: uuid.UUID) -> CustomerDto:
        return CustomerDto.model_validate(self._get(customer_id))

    def update_customer(self, customer_id: uuid.UUID, body: CustomerUpdateIn) -> CustomerDto:
        c = self._get(customer_id)
        check_version(c.version, body.version, "Customer")
        before = CustomerDto.model_validate(c).model_dump(mode="json")
        for key, value in body.model_dump(exclude={"version"}).items():
            if key == "code" and not value:
                continue  # a blank code keeps the current one
            setattr(c, key, value)
        flush_versioned(self._s, "Customer", "DUPLICATE_CUSTOMER", "Customer code already exists")
        dto = CustomerDto.model_validate(c)
        self._record("customers.customer.updated", "customer", c.id, before, dto.model_dump(mode="json"))
        return dto

    def set_customer_active(
        self, customer_id: uuid.UUID, active: bool, reason: str, version: int | None
    ) -> CustomerDto:
        """Orders, machine reports, credit invoices and payments keep their history; the balance stays collectable."""
        c = self._get(customer_id)
        check_version(c.version, version, "Customer")
        if active:
            mark_active(c, "Customer")
        else:
            mark_inactive(c, self._ctx.user_id, reason, "Customer")
        flush_versioned(self._s, "Customer")
        dto = CustomerDto.model_validate(c)
        verb = "reactivated" if active else "deactivated"
        self._record(f"customers.customer.{verb}", "customer", c.id, None, dto.model_dump(mode="json"), reason)
        return dto

    # --- rate card ----------------------------------------------------------------------------------
    def create_rate_card(self, body: RateCardIn) -> RateCardDto:
        effective = body.effective_from or utcnow()
        if effective < utcnow().replace(microsecond=0) and body.effective_from is not None:
            raise BusinessRuleViolation("Rate cards cannot be backdated", code="RATE_BACKDATED")
        settings = self._s.get(TenantSettings, self._tid)
        assert settings is not None
        row = RentalRatePolicy(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            machine_category_id=body.machine_category_id,
            effective_from=effective,
            hourly_rate=body.hourly_rate,
            minimum_hours=body.minimum_hours,
            currency=settings.currency,
            reason=body.reason,
            created_by=self._ctx.user_id,
        )
        self._insert(row, "DUPLICATE_RATE_CARD", "A rate card already starts at this instant")
        self._record(
            "customers.rate_card.versioned",
            "rate_card",
            row.id,
            None,
            {"hourly_rate": str(row.hourly_rate), "category": str(row.machine_category_id)},
            body.reason,
        )
        return RateCardDto.model_validate(row)
