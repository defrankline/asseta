"""Tenant customers, the rate card and the field user's own machines."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.clock import get_now
from asseta.core.db import get_session
from asseta.core.errors import ERROR_RESPONSES, PermissionDenied
from asseta.core.lifecycle import IncludeInactive, LifecycleChangeIn
from asseta.core.paging import Page, PageParams, page_params, paginate
from asseta.core.search import ilike_any
from asseta.modules.customers.dto import CustomerDto, CustomerIn, CustomerUpdateIn, RateCardDto, RateCardIn
from asseta.modules.customers.models import Customer, CustomerKind, RentalRatePolicy
from asseta.modules.customers.service import CustomerService, customer_query
from asseta.modules.fleet.dto import MachineDto
from asseta.modules.fleet.machine_view import machine_dtos
from asseta.modules.fleet.models import Machine
from asseta.modules.fleet.scope import assigned_machine_ids, own_staff
from asseta.modules.identity.catalog import CATALOG, MenuDef
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.dependencies import requires, requires_any
from asseta.modules.identity.principal import RequestContext

CUSTOMER_READ = requires("tenant.customer.read", S.TENANT, "View customers and the rate card")
CUSTOMER_WRITE = requires("tenant.customer.write", S.TENANT, "Manage customers, their payment terms and the rate card")
CUSTOMER_DETAILS = requires(
    "tenant.customer.details",
    S.TENANT,
    "Add customers and edit their details (not payment terms or rates)",
)
# Adding a customer or editing its details: either permission. Payment terms stay with tenant.customer.write.
CUSTOMER_EDIT = requires_any(("tenant.customer.write", "tenant.customer.details"), S.TENANT)
# The caller's own machines (field apps, machine pickers of people without the machine register).
FIELD_MACHINES = requires_any(
    ("tenant.machine_report.submit", "tenant.machine_report.read", "tenant.meter.capture"), S.TENANT
)
DEFAULT_PAYMENT_TERMS = CustomerIn.model_fields["payment_terms_days"].default

CATALOG.register_menu(
    MenuDef(
        "tenant.customers",
        S.TENANT,
        "Customers",
        "/tenant/customers",
        25,
        "tenant.customer.read",
        group="tenant.operations",
    )
)

router = APIRouter(prefix="/api/v1/tenant", tags=["customers"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]
CustomerRead = Annotated[RequestContext, Depends(CUSTOMER_READ)]
CustomerWrite = Annotated[RequestContext, Depends(CUSTOMER_WRITE)]
CustomerEdit = Annotated[RequestContext, Depends(CUSTOMER_EDIT)]


def _terms_allowed(ctx: RequestContext, wanted: int, current: int) -> None:
    """Without tenant.customer.write the payment terms are left as they are (the default for a new customer)."""
    if wanted != current and "tenant.customer.write" not in ctx.permissions:
        raise PermissionDenied(
            "Payment terms are set by the office; you can add customers and edit their details",
            code="CUSTOMER_TERMS_NOT_PERMITTED",
        )


@router.post("/customers", response_model=CustomerDto, status_code=201, operation_id="createCustomer")
def create_customer(body: CustomerIn, session: DbSession, ctx: CustomerEdit) -> CustomerDto:
    """`code` is optional: left blank, the server assigns the next free CUST-<nnnnn> of the company."""
    _terms_allowed(ctx, body.payment_terms_days, DEFAULT_PAYMENT_TERMS)
    return CustomerService(session, ctx).create_customer(body)


@router.get("/customers", response_model=Page[CustomerDto], operation_id="listCustomers")
def customers(
    session: DbSession,
    _: CustomerRead,
    paging: Annotated[PageParams, Depends(page_params)],
    include_inactive: IncludeInactive = False,
    kind: CustomerKind | None = None,
) -> Page[CustomerDto]:
    stmt = customer_query(paging.q, include_inactive)
    if kind is not None:
        stmt = stmt.where(Customer.kind == kind)
    rows, total = paginate(session, stmt, paging)
    return Page(
        items=[CustomerDto.model_validate(c) for c in rows], total=total, page=paging.page, page_size=paging.page_size
    )


@router.get("/customers/{customer_id}", response_model=CustomerDto, operation_id="getCustomer")
def get_customer(customer_id: uuid.UUID, session: DbSession, ctx: CustomerRead) -> CustomerDto:
    return CustomerService(session, ctx).customer(customer_id)


@router.put("/customers/{customer_id}", response_model=CustomerDto, operation_id="updateCustomer")
def update_customer(
    customer_id: uuid.UUID, body: CustomerUpdateIn, session: DbSession, ctx: CustomerEdit
) -> CustomerDto:
    """A blank `code` keeps the customer's current code."""
    svc = CustomerService(session, ctx)
    _terms_allowed(ctx, body.payment_terms_days, svc.customer(customer_id).payment_terms_days)
    return svc.update_customer(customer_id, body)


@router.post("/customers/{customer_id}/deactivate", response_model=CustomerDto, operation_id="deactivateCustomer")
def deactivate_customer(
    customer_id: uuid.UUID, body: LifecycleChangeIn, session: DbSession, ctx: CustomerWrite
) -> CustomerDto:
    """History and balances are kept; a deactivated customer leaves the pickers."""
    return CustomerService(session, ctx).set_customer_active(customer_id, False, body.reason, body.version)


@router.post("/customers/{customer_id}/reactivate", response_model=CustomerDto, operation_id="reactivateCustomer")
def reactivate_customer(
    customer_id: uuid.UUID, body: LifecycleChangeIn, session: DbSession, ctx: CustomerWrite
) -> CustomerDto:
    return CustomerService(session, ctx).set_customer_active(customer_id, True, body.reason, body.version)


@router.post("/rate-cards", response_model=RateCardDto, status_code=201, operation_id="createRateCard")
def create_rate_card(body: RateCardIn, session: DbSession, ctx: CustomerWrite) -> RateCardDto:
    return CustomerService(session, ctx).create_rate_card(body)


@router.get("/rate-cards", response_model=list[RateCardDto], operation_id="listRateCards")
def rate_cards(session: DbSession, _: CustomerRead, machine_category_id: uuid.UUID | None = None) -> list[RateCardDto]:
    """All versions, newest first; the effective card for a time is the latest with effective_from <= time."""
    stmt = select(RentalRatePolicy).order_by(
        RentalRatePolicy.machine_category_id, RentalRatePolicy.effective_from.desc()
    )
    if machine_category_id:
        stmt = stmt.where(RentalRatePolicy.machine_category_id == machine_category_id)
    return [RateCardDto.model_validate(r) for r in session.execute(stmt).scalars()]


@router.get("/field/machines", response_model=list[MachineDto], operation_id="listMyFieldMachines")
def field_machines(
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(FIELD_MACHINES)],
    now: Annotated[datetime, Depends(get_now)],
    q: str | None = None,
) -> list[MachineDto]:
    """Machines currently assigned to the caller (by asset code / name, at most 100). Field users have no machine
    register access; this is what the field apps and the machine pickers of such users receive."""
    staff = own_staff(session, ctx)
    if staff is None:
        return []
    stmt = select(Machine).where(Machine.id.in_(assigned_machine_ids(staff.id))).order_by(Machine.asset_code).limit(100)
    if (match := ilike_any(q, Machine.asset_code, Machine.name)) is not None:
        stmt = stmt.where(match)
    return machine_dtos(session, list(session.execute(stmt).scalars()), now)
