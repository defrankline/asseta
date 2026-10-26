"""Customer hours endpoints (tenant scope): walk-ins, reason lists, discounts, credit, purchases, payment links and
evidence, the hours ledger, balances, work execution allocations, transfers and cancellations."""

import uuid
from datetime import date, datetime
from typing import Annotated
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, Header, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.clock import get_now
from asseta.core.config import get_settings
from asseta.core.db import get_session
from asseta.core.errors import ERROR_RESPONSES, NotFound
from asseta.core.idempotency import IdempotencyGuard, request_hash
from asseta.core.lifecycle import IncludeInactive, LifecycleChangeIn
from asseta.core.paging import Page, PageParams, page_params, paginate
from asseta.core.search import ilike_any
from asseta.core.storage import ObjectStore
from asseta.modules.accountability.names import named
from asseta.modules.finance import permissions as _finance_permissions  # noqa: F401  (declares finance codes)
from asseta.modules.finance.common import tenant_settings
from asseta.modules.fleet.models import Machine
from asseta.modules.fleet.photos import PhotoUrlDto, get_object_store
from asseta.modules.hours.approvals import HoursApprovals, proposal_query, reason_code_query, request_query
from asseta.modules.hours.dto import (
    CancellationDto,
    CancellationIn,
    CreditActivationIn,
    CreditArrangementDto,
    CreditArrangementIn,
    CreditArrangementUpdateIn,
    CreditExposureDto,
    CustomerRegistrationIn,
    DecisionIn,
    DiscountDto,
    DiscountIn,
    DiscountUpdateIn,
    EvidenceLinkIn,
    HoursBalanceDto,
    HoursPurchaseDto,
    HoursPurchaseIn,
    HoursStatementDto,
    LedgerEntryDto,
    LowBalanceAlertDto,
    PaymentEvidenceDto,
    PurchaseAllocationIn,
    ReasonCodeDto,
    ReasonCodeIn,
    ReasonCodeUpdateIn,
    ReasonIn,
    TransferDto,
    TransferIn,
    WalkInCustomerDto,
    WalkInCustomerIn,
    WorkExecutionAllocationDto,
)
from asseta.modules.hours.models import (
    CreditArrangement,
    CustomerDiscount,
    HoursCancellation,
    HoursLedgerEntry,
    HoursLowBalanceAlert,
    HoursPurchase,
    HoursTransfer,
    LedgerEntryType,
    PaymentEvidence,
    ProposalStatus,
    ReasonKind,
    RequestStatus,
    WorkExecutionAllocation,
)
from asseta.modules.hours.permissions import (
    CANCEL_APPROVE,
    CANCEL_REQUEST,
    CREDIT_ACTIVATE,
    CREDIT_APPROVE,
    CREDIT_PROPOSE,
    DISCOUNT_APPROVE,
    DISCOUNT_PROPOSE,
    HOURS_PURCHASE,
    HOURS_READ,
    REASONS_MANAGE,
    TRANSFER_APPROVE,
    TRANSFER_REQUEST,
)
from asseta.modules.hours.service import (
    HoursService,
    allocation_dto,
    balances,
    ledger_dto,
    purchase_dto,
    purchase_query,
)
from asseta.modules.hours.statement import StatementQuery, build_statement, default_period, statement_pdf
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.dependencies import requires, requires_any
from asseta.modules.identity.models import AppUser
from asseta.modules.identity.principal import RequestContext
from asseta.modules.jobs.dto import CustomerDto
from asseta.modules.jobs.models import Customer
from asseta.modules.meter.dto import AttachmentDto
from asseta.modules.meter.models import CaptureAttachment
from asseta.modules.meter.router import save_attachment
from asseta.modules.reports.definitions import ReportEnv
from asseta.modules.tenancy.models import Tenant

router = APIRouter(prefix="/api/v1/tenant", tags=["hours"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]
Now = Annotated[datetime, Depends(get_now)]
IdemKey = Annotated[str | None, Header()]
Paging = Annotated[PageParams, Depends(page_params)]
Store = Annotated[ObjectStore, Depends(get_object_store)]
Read = Annotated[RequestContext, Depends(HOURS_READ)]
CUSTOMER_WRITE = requires("tenant.customer.write", S.TENANT, "Manage customers, contracts and rate cards")
EVIDENCE_WRITE = requires_any(("tenant.hours.purchase", "tenant.finance.payment", "tenant.collection.record"), S.TENANT)
EVIDENCE_READ = requires_any(("tenant.hours.read", "tenant.finance.read"), S.TENANT)


# --- walk-in customers ------------------------------------------------------------------------------------------
@router.post(
    "/walk-in-customers", response_model=WalkInCustomerDto, status_code=201, operation_id="createWalkInCustomer"
)
@named
def create_walk_in(
    body: WalkInCustomerIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(HOURS_PURCHASE)],
    idempotency_key: IdemKey = None,
) -> WalkInCustomerDto:
    guard = IdempotencyGuard(session, str(ctx.tenant_id), "createWalkInCustomer", idempotency_key, request_hash(body))
    if (replay := guard.begin()) is not None:
        return WalkInCustomerDto.model_validate(replay)
    svc = HoursService(session, ctx, now)
    dto = svc.walk_in_dto(svc.create_walk_in(body))
    guard.complete(dto, 201)
    return dto


@router.post("/customers/{customer_id}/registration", response_model=CustomerDto, operation_id="registerWalkInCustomer")
@named
def register_walk_in(
    customer_id: uuid.UUID,
    body: CustomerRegistrationIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(CUSTOMER_WRITE)],
) -> CustomerDto:
    return HoursService(session, ctx, now).register_customer(customer_id, body)


# --- reason lists -----------------------------------------------------------------------------------------------
@router.get("/hours-reason-codes", response_model=Page[ReasonCodeDto], operation_id="listHoursReasonCodes")
@named
def list_reason_codes(
    session: DbSession,
    _: Read,
    paging: Paging,
    kind: ReasonKind | None = None,
    include_inactive: IncludeInactive = False,
) -> Page[ReasonCodeDto]:
    rows, total = paginate(session, reason_code_query(paging.q, kind, include_inactive), paging)
    return Page(
        items=[ReasonCodeDto.model_validate(r) for r in rows], total=total, page=paging.page, page_size=paging.page_size
    )


@router.post("/hours-reason-codes", response_model=ReasonCodeDto, status_code=201, operation_id="createHoursReasonCode")
@named
def create_reason_code(
    body: ReasonCodeIn, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(REASONS_MANAGE)]
) -> ReasonCodeDto:
    return HoursApprovals(session, ctx, now).create_reason_code(body)


@router.get("/hours-reason-codes/{code_id}", response_model=ReasonCodeDto, operation_id="getHoursReasonCode")
@named
def get_reason_code(code_id: uuid.UUID, session: DbSession, now: Now, ctx: Read) -> ReasonCodeDto:
    return ReasonCodeDto.model_validate(HoursApprovals(session, ctx, now).reason_code(code_id))


@router.put("/hours-reason-codes/{code_id}", response_model=ReasonCodeDto, operation_id="updateHoursReasonCode")
@named
def update_reason_code(
    code_id: uuid.UUID,
    body: ReasonCodeUpdateIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(REASONS_MANAGE)],
) -> ReasonCodeDto:
    return HoursApprovals(session, ctx, now).update_reason_code(code_id, body)


@router.post(
    "/hours-reason-codes/{code_id}/deactivate", response_model=ReasonCodeDto, operation_id="deactivateHoursReasonCode"
)
@named
def deactivate_reason_code(
    code_id: uuid.UUID,
    body: LifecycleChangeIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(REASONS_MANAGE)],
) -> ReasonCodeDto:
    return HoursApprovals(session, ctx, now).set_reason_code_active(code_id, False, body.reason, body.version)


@router.post(
    "/hours-reason-codes/{code_id}/reactivate", response_model=ReasonCodeDto, operation_id="reactivateHoursReasonCode"
)
@named
def reactivate_reason_code(
    code_id: uuid.UUID,
    body: LifecycleChangeIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(REASONS_MANAGE)],
) -> ReasonCodeDto:
    return HoursApprovals(session, ctx, now).set_reason_code_active(code_id, True, body.reason, body.version)


# --- discounts --------------------------------------------------------------------------------------------------
@router.get("/customer-discounts", response_model=Page[DiscountDto], operation_id="listCustomerDiscounts")
@named
def list_discounts(
    session: DbSession,
    _: Read,
    paging: Paging,
    status: ProposalStatus | None = None,
    customer_id: uuid.UUID | None = None,
) -> Page[DiscountDto]:
    rows, total = paginate(session, proposal_query(CustomerDiscount, paging.q, status, customer_id), paging)
    return Page(
        items=[DiscountDto.model_validate(r) for r in rows], total=total, page=paging.page, page_size=paging.page_size
    )


@router.post("/customer-discounts", response_model=DiscountDto, status_code=201, operation_id="proposeCustomerDiscount")
@named
def propose_discount(
    body: DiscountIn, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(DISCOUNT_PROPOSE)]
) -> DiscountDto:
    return HoursApprovals(session, ctx, now).propose_discount(body)


@router.get("/customer-discounts/{discount_id}", response_model=DiscountDto, operation_id="getCustomerDiscount")
@named
def get_discount(discount_id: uuid.UUID, session: DbSession, _: Read) -> DiscountDto:
    row = session.get(CustomerDiscount, discount_id)
    if row is None:
        raise NotFound("Discount not found")
    return DiscountDto.model_validate(row)


@router.put("/customer-discounts/{discount_id}", response_model=DiscountDto, operation_id="updateCustomerDiscount")
@named
def update_discount(
    discount_id: uuid.UUID,
    body: DiscountUpdateIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(DISCOUNT_PROPOSE)],
) -> DiscountDto:
    return HoursApprovals(session, ctx, now).update_discount(discount_id, body)


@router.post(
    "/customer-discounts/{discount_id}/decision", response_model=DiscountDto, operation_id="decideCustomerDiscount"
)
@named
def decide_discount(
    discount_id: uuid.UUID,
    body: DecisionIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(DISCOUNT_APPROVE)],
) -> DiscountDto:
    return DiscountDto.model_validate(
        HoursApprovals(session, ctx, now).decide_proposal(CustomerDiscount, discount_id, body)
    )


@router.post(
    "/customer-discounts/{discount_id}/withdraw", response_model=DiscountDto, operation_id="withdrawCustomerDiscount"
)
@named
def withdraw_discount(
    discount_id: uuid.UUID,
    body: ReasonIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(DISCOUNT_PROPOSE)],
) -> DiscountDto:
    return DiscountDto.model_validate(
        HoursApprovals(session, ctx, now).withdraw_proposal(CustomerDiscount, discount_id, body.reason)
    )


@router.post(
    "/customer-discounts/{discount_id}/revoke", response_model=DiscountDto, operation_id="revokeCustomerDiscount"
)
@named
def revoke_discount(
    discount_id: uuid.UUID,
    body: ReasonIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(DISCOUNT_APPROVE)],
) -> DiscountDto:
    return DiscountDto.model_validate(
        HoursApprovals(session, ctx, now).revoke_proposal(CustomerDiscount, discount_id, body.reason)
    )


# --- credit arrangements ----------------------------------------------------------------------------------------
@router.get("/credit-arrangements", response_model=Page[CreditArrangementDto], operation_id="listCreditArrangements")
@named
def list_credit(
    session: DbSession,
    _: Read,
    paging: Paging,
    status: ProposalStatus | None = None,
    customer_id: uuid.UUID | None = None,
) -> Page[CreditArrangementDto]:
    rows, total = paginate(session, proposal_query(CreditArrangement, paging.q, status, customer_id), paging)
    return Page(
        items=[CreditArrangementDto.model_validate(r) for r in rows],
        total=total,
        page=paging.page,
        page_size=paging.page_size,
    )


@router.post(
    "/credit-arrangements",
    response_model=CreditArrangementDto,
    status_code=201,
    operation_id="proposeCreditArrangement",
)
@named
def propose_credit(
    body: CreditArrangementIn, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(CREDIT_PROPOSE)]
) -> CreditArrangementDto:
    return HoursApprovals(session, ctx, now).propose_credit(body)


@router.get(
    "/credit-arrangements/{arrangement_id}", response_model=CreditArrangementDto, operation_id="getCreditArrangement"
)
@named
def get_credit(arrangement_id: uuid.UUID, session: DbSession, _: Read) -> CreditArrangementDto:
    row = session.get(CreditArrangement, arrangement_id)
    if row is None:
        raise NotFound("Credit arrangement not found")
    return CreditArrangementDto.model_validate(row)


@router.put(
    "/credit-arrangements/{arrangement_id}",
    response_model=CreditArrangementDto,
    operation_id="updateCreditArrangement",
)
@named
def update_credit(
    arrangement_id: uuid.UUID,
    body: CreditArrangementUpdateIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(CREDIT_PROPOSE)],
) -> CreditArrangementDto:
    return HoursApprovals(session, ctx, now).update_credit(arrangement_id, body)


@router.post(
    "/credit-arrangements/{arrangement_id}/decision",
    response_model=CreditArrangementDto,
    operation_id="decideCreditArrangement",
)
@named
def decide_credit(
    arrangement_id: uuid.UUID,
    body: DecisionIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(CREDIT_APPROVE)],
) -> CreditArrangementDto:
    return CreditArrangementDto.model_validate(
        HoursApprovals(session, ctx, now).decide_proposal(CreditArrangement, arrangement_id, body)
    )


@router.post(
    "/credit-arrangements/{arrangement_id}/withdraw",
    response_model=CreditArrangementDto,
    operation_id="withdrawCreditArrangement",
)
@named
def withdraw_credit(
    arrangement_id: uuid.UUID,
    body: ReasonIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(CREDIT_PROPOSE)],
) -> CreditArrangementDto:
    return CreditArrangementDto.model_validate(
        HoursApprovals(session, ctx, now).withdraw_proposal(CreditArrangement, arrangement_id, body.reason)
    )


@router.post(
    "/credit-arrangements/{arrangement_id}/revoke",
    response_model=CreditArrangementDto,
    operation_id="revokeCreditArrangement",
)
@named
def revoke_credit(
    arrangement_id: uuid.UUID,
    body: ReasonIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(CREDIT_APPROVE)],
) -> CreditArrangementDto:
    return CreditArrangementDto.model_validate(
        HoursApprovals(session, ctx, now).revoke_proposal(CreditArrangement, arrangement_id, body.reason)
    )


@router.get(
    "/customers/{customer_id}/credit-exposure",
    response_model=CreditExposureDto,
    operation_id="getCustomerCreditExposure",
)
@named
def credit_exposure(
    customer_id: uuid.UUID, session: DbSession, now: Now, ctx: Read, currency: str | None = None
) -> CreditExposureDto:
    return HoursApprovals(session, ctx, now).exposure(customer_id, currency)


# --- purchases --------------------------------------------------------------------------------------------------
@router.get("/hours-purchases", response_model=Page[HoursPurchaseDto], operation_id="listHoursPurchases")
@named
def list_purchases(
    session: DbSession,
    _: Read,
    paging: Paging,
    customer_id: uuid.UUID | None = None,
    machine_id: uuid.UUID | None = None,
    cancelled: bool | None = None,
) -> Page[HoursPurchaseDto]:
    rows, total = paginate(session, purchase_query(paging.q, customer_id, machine_id, cancelled), paging)
    return Page(
        items=[purchase_dto(session, p) for p in rows], total=total, page=paging.page, page_size=paging.page_size
    )


@router.post("/hours-purchases", response_model=HoursPurchaseDto, status_code=201, operation_id="recordHoursPurchase")
@named
def record_purchase(
    body: HoursPurchaseIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(HOURS_PURCHASE)],
    idempotency_key: IdemKey = None,
) -> HoursPurchaseDto:
    guard = IdempotencyGuard(session, str(ctx.tenant_id), "recordHoursPurchase", idempotency_key, request_hash(body))
    if (replay := guard.begin()) is not None:
        return HoursPurchaseDto.model_validate(replay)
    dto = HoursService(session, ctx, now).create_purchase(body)
    guard.complete(dto, 201)
    return dto


@router.get("/hours-purchases/{purchase_id}", response_model=HoursPurchaseDto, operation_id="getHoursPurchase")
@named
def get_purchase(purchase_id: uuid.UUID, session: DbSession, now: Now, ctx: Read) -> HoursPurchaseDto:
    return purchase_dto(session, HoursService(session, ctx, now).purchase(purchase_id))


@router.post(
    "/hours-purchases/{purchase_id}/allocations",
    response_model=HoursPurchaseDto,
    operation_id="allocatePaymentToHoursPurchase",
)
@named
def allocate_payment(
    purchase_id: uuid.UUID,
    body: PurchaseAllocationIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(HOURS_PURCHASE)],
    idempotency_key: IdemKey = None,
) -> HoursPurchaseDto:
    guard = IdempotencyGuard(
        session,
        str(ctx.tenant_id),
        f"allocatePaymentToHoursPurchase:{purchase_id}",
        idempotency_key,
        request_hash(body),
    )
    if (replay := guard.begin()) is not None:
        return HoursPurchaseDto.model_validate(replay)
    dto = HoursService(session, ctx, now).allocate(purchase_id, body)
    guard.complete(dto)
    return dto


@router.post(
    "/hours-purchases/{purchase_id}/credit-activations",
    response_model=HoursPurchaseDto,
    operation_id="activateHoursOnCredit",
)
@named
def credit_activate(
    purchase_id: uuid.UUID,
    body: CreditActivationIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(CREDIT_ACTIVATE)],
    idempotency_key: IdemKey = None,
) -> HoursPurchaseDto:
    guard = IdempotencyGuard(
        session, str(ctx.tenant_id), f"activateHoursOnCredit:{purchase_id}", idempotency_key, request_hash(body)
    )
    if (replay := guard.begin()) is not None:
        return HoursPurchaseDto.model_validate(replay)
    dto = HoursService(session, ctx, now).credit_activate(purchase_id, body)
    guard.complete(dto)
    return dto


@router.post(
    "/hours-purchases/{purchase_id}/cancellation",
    response_model=CancellationDto,
    status_code=201,
    operation_id="requestHoursPurchaseCancellation",
)
@named
def request_cancellation(
    purchase_id: uuid.UUID,
    body: CancellationIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(CANCEL_REQUEST)],
) -> CancellationDto:
    return HoursApprovals(session, ctx, now).request_cancellation(purchase_id, body)


# --- ledger, balances, allocations ------------------------------------------------------------------------------
@router.get("/hours-ledger", response_model=Page[LedgerEntryDto], operation_id="listHoursLedger")
@named
def list_ledger(
    session: DbSession,
    _: Read,
    paging: Paging,
    purchase_id: uuid.UUID | None = None,
    customer_id: uuid.UUID | None = None,
    machine_id: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
    entry_type: LedgerEntryType | None = None,
) -> Page[LedgerEntryDto]:
    stmt = select(HoursLedgerEntry).order_by(HoursLedgerEntry.occurred_at.desc(), HoursLedgerEntry.created_at.desc())
    for col, value in (
        (HoursLedgerEntry.purchase_id, purchase_id),
        (HoursLedgerEntry.customer_id, customer_id),
        (HoursLedgerEntry.machine_id, machine_id),
        (HoursLedgerEntry.job_id, job_id),
        (HoursLedgerEntry.entry_type, entry_type),
    ):
        if value is not None:
            stmt = stmt.where(col == value)
    if (match := ilike_any(paging.q, HoursPurchase.purchase_number, HoursLedgerEntry.reason)) is not None:
        stmt = stmt.join(HoursPurchase, HoursPurchase.id == HoursLedgerEntry.purchase_id).where(match)
    rows, total = paginate(session, stmt, paging)
    return Page(items=[ledger_dto(e) for e in rows], total=total, page=paging.page, page_size=paging.page_size)


@router.get(
    "/customers/{customer_id}/hours-balances",
    response_model=list[HoursBalanceDto],
    operation_id="getCustomerHoursBalances",
)
@named
def customer_balances(customer_id: uuid.UUID, session: DbSession, _: Read) -> list[HoursBalanceDto]:
    if session.get(Customer, customer_id) is None:
        raise NotFound("Customer not found")
    return balances(session, customer_id=customer_id)


@router.get(
    "/machines/{machine_id}/hours-balances",
    response_model=list[HoursBalanceDto],
    operation_id="getMachineHoursBalances",
)
@named
def machine_balances(machine_id: uuid.UUID, session: DbSession, _: Read) -> list[HoursBalanceDto]:
    if session.get(Machine, machine_id) is None:
        raise NotFound("Machine not found")
    return balances(session, machine_id=machine_id)


@router.get(
    "/work-execution-allocations",
    response_model=Page[WorkExecutionAllocationDto],
    operation_id="listWorkExecutionAllocations",
)
@named
def list_allocations(
    session: DbSession,
    _: Read,
    paging: Paging,
    job_id: uuid.UUID | None = None,
    customer_id: uuid.UUID | None = None,
    machine_id: uuid.UUID | None = None,
) -> Page[WorkExecutionAllocationDto]:
    stmt = select(WorkExecutionAllocation).order_by(WorkExecutionAllocation.created_at.desc())
    for col, value in (
        (WorkExecutionAllocation.job_id, job_id),
        (WorkExecutionAllocation.customer_id, customer_id),
        (WorkExecutionAllocation.machine_id, machine_id),
    ):
        if value is not None:
            stmt = stmt.where(col == value)
    rows, total = paginate(session, stmt, paging)
    return Page(
        items=[allocation_dto(session, w) for w in rows], total=total, page=paging.page, page_size=paging.page_size
    )


@router.get(
    "/work-execution-allocations/{allocation_id}",
    response_model=WorkExecutionAllocationDto,
    operation_id="getWorkExecutionAllocation",
)
@named
def get_allocation(allocation_id: uuid.UUID, session: DbSession, _: Read) -> WorkExecutionAllocationDto:
    row = session.get(WorkExecutionAllocation, allocation_id)
    if row is None:
        raise NotFound("Work execution allocation not found")
    return allocation_dto(session, row)


# --- transfers --------------------------------------------------------------------------------------------------
@router.get("/hours-transfers", response_model=Page[TransferDto], operation_id="listHoursTransfers")
@named
def list_transfers(
    session: DbSession,
    _: Read,
    paging: Paging,
    status: RequestStatus | None = None,
    purchase_id: uuid.UUID | None = None,
) -> Page[TransferDto]:
    rows, total = paginate(session, request_query(HoursTransfer, paging.q, status, purchase_id), paging)
    return Page(
        items=[TransferDto.model_validate(r) for r in rows], total=total, page=paging.page, page_size=paging.page_size
    )


@router.post("/hours-transfers", response_model=TransferDto, status_code=201, operation_id="requestHoursTransfer")
@named
def request_transfer(
    body: TransferIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(TRANSFER_REQUEST)],
    idempotency_key: IdemKey = None,
) -> TransferDto:
    guard = IdempotencyGuard(session, str(ctx.tenant_id), "requestHoursTransfer", idempotency_key, request_hash(body))
    if (replay := guard.begin()) is not None:
        return TransferDto.model_validate(replay)
    dto = HoursApprovals(session, ctx, now).request_transfer(body)
    guard.complete(dto, 201)
    return dto


@router.get("/hours-transfers/{transfer_id}", response_model=TransferDto, operation_id="getHoursTransfer")
@named
def get_transfer(transfer_id: uuid.UUID, session: DbSession, now: Now, ctx: Read) -> TransferDto:
    return TransferDto.model_validate(HoursApprovals(session, ctx, now).transfer(transfer_id))


@router.post("/hours-transfers/{transfer_id}/decision", response_model=TransferDto, operation_id="decideHoursTransfer")
@named
def decide_transfer(
    transfer_id: uuid.UUID,
    body: DecisionIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(TRANSFER_APPROVE)],
) -> TransferDto:
    return HoursApprovals(session, ctx, now).decide_transfer(transfer_id, body)


@router.post(
    "/hours-transfers/{transfer_id}/withdraw", response_model=TransferDto, operation_id="withdrawHoursTransfer"
)
@named
def withdraw_transfer(
    transfer_id: uuid.UUID,
    body: ReasonIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(TRANSFER_REQUEST)],
) -> TransferDto:
    return HoursApprovals(session, ctx, now).withdraw_transfer(transfer_id, body.reason)


# --- cancellations ----------------------------------------------------------------------------------------------
@router.get("/hours-cancellations", response_model=Page[CancellationDto], operation_id="listHoursCancellations")
@named
def list_cancellations(
    session: DbSession,
    _: Read,
    paging: Paging,
    status: RequestStatus | None = None,
    purchase_id: uuid.UUID | None = None,
) -> Page[CancellationDto]:
    rows, total = paginate(session, request_query(HoursCancellation, paging.q, status, purchase_id), paging)
    return Page(
        items=[CancellationDto.model_validate(r) for r in rows],
        total=total,
        page=paging.page,
        page_size=paging.page_size,
    )


@router.get(
    "/hours-cancellations/{cancellation_id}", response_model=CancellationDto, operation_id="getHoursCancellation"
)
@named
def get_cancellation(cancellation_id: uuid.UUID, session: DbSession, now: Now, ctx: Read) -> CancellationDto:
    return CancellationDto.model_validate(HoursApprovals(session, ctx, now).cancellation(cancellation_id))


@router.post(
    "/hours-cancellations/{cancellation_id}/decision",
    response_model=CancellationDto,
    operation_id="decideHoursCancellation",
)
@named
def decide_cancellation(
    cancellation_id: uuid.UUID,
    body: DecisionIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(CANCEL_APPROVE)],
) -> CancellationDto:
    return HoursApprovals(session, ctx, now).decide_cancellation(cancellation_id, body)


@router.post(
    "/hours-cancellations/{cancellation_id}/withdraw",
    response_model=CancellationDto,
    operation_id="withdrawHoursCancellation",
)
@named
def withdraw_cancellation(
    cancellation_id: uuid.UUID,
    body: ReasonIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(CANCEL_REQUEST)],
) -> CancellationDto:
    return HoursApprovals(session, ctx, now).withdraw_cancellation(cancellation_id, body.reason)


# --- payment evidence -------------------------------------------------------------------------------------------
@router.post("/payment-evidence", response_model=AttachmentDto, status_code=201, operation_id="uploadPaymentEvidence")
@named
async def upload_evidence(
    session: DbSession,
    store: Store,
    ctx: Annotated[RequestContext, Depends(EVIDENCE_WRITE)],
    file: Annotated[UploadFile, File()],
) -> AttachmentDto:
    data = await file.read(get_settings().max_image_bytes + 1)
    return AttachmentDto.model_validate(save_attachment(session, store, ctx, data, "PAYMENT_EVIDENCE"))


@router.post(
    "/customer-payments/{payment_id}/evidence",
    response_model=list[PaymentEvidenceDto],
    status_code=201,
    operation_id="attachPaymentEvidence",
)
@named
def attach_evidence(
    payment_id: uuid.UUID,
    body: EvidenceLinkIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(EVIDENCE_WRITE)],
) -> list[PaymentEvidenceDto]:
    return HoursService(session, ctx, now).link_evidence(payment_id, body.attachment_ids)


@router.get(
    "/customer-payments/{payment_id}/evidence",
    response_model=list[PaymentEvidenceDto],
    operation_id="listPaymentEvidence",
)
@named
def list_evidence(
    payment_id: uuid.UUID, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(EVIDENCE_READ)]
) -> list[PaymentEvidenceDto]:
    return HoursService(session, ctx, now).evidence(payment_id)


@router.get(
    "/customer-payments/{payment_id}/evidence/{attachment_id}/url",
    response_model=PhotoUrlDto,
    operation_id="getPaymentEvidenceUrl",
)
@named
def evidence_url(
    payment_id: uuid.UUID,
    attachment_id: uuid.UUID,
    session: DbSession,
    store: Store,
    _: Annotated[RequestContext, Depends(EVIDENCE_READ)],
) -> PhotoUrlDto:
    linked = session.execute(
        select(PaymentEvidence.id).where(
            PaymentEvidence.payment_id == payment_id, PaymentEvidence.attachment_id == attachment_id
        )
    ).first()
    row = session.get(CaptureAttachment, attachment_id) if linked else None
    if row is None:
        raise NotFound("Evidence not found")
    ttl = get_settings().presigned_url_ttl_seconds
    return PhotoUrlDto(url=store.presigned_get(row.object_key, ttl), expires_in_seconds=ttl)


# --- low-balance alerts (DEC-031 P2) ----------------------------------------------------------------------------
@router.get(
    "/hours-low-balance-alerts", response_model=Page[LowBalanceAlertDto], operation_id="listHoursLowBalanceAlerts"
)
@named
def list_low_balance_alerts(
    session: DbSession,
    _: Read,
    paging: Paging,
    purchase_id: uuid.UUID | None = None,
    customer_id: uuid.UUID | None = None,
    machine_id: uuid.UUID | None = None,
    armed: bool | None = None,
) -> Page[LowBalanceAlertDto]:
    stmt = select(HoursLowBalanceAlert).order_by(HoursLowBalanceAlert.crossed_at.desc(), HoursLowBalanceAlert.id)
    for col, value in (
        (HoursLowBalanceAlert.purchase_id, purchase_id),
        (HoursLowBalanceAlert.customer_id, customer_id),
        (HoursLowBalanceAlert.machine_id, machine_id),
    ):
        if value is not None:
            stmt = stmt.where(col == value)
    if armed is not None:
        stmt = stmt.where(
            HoursLowBalanceAlert.rearmed_at.is_(None) if armed else HoursLowBalanceAlert.rearmed_at.is_not(None)
        )
    rows, total = paginate(session, stmt, paging)
    return Page(
        items=[LowBalanceAlertDto.model_validate(a) for a in rows],
        total=total,
        page=paging.page,
        page_size=paging.page_size,
    )


@router.get(
    "/hours-low-balance-alerts/{alert_id}", response_model=LowBalanceAlertDto, operation_id="getHoursLowBalanceAlert"
)
@named
def get_low_balance_alert(alert_id: uuid.UUID, session: DbSession, _: Read) -> LowBalanceAlertDto:
    row = session.get(HoursLowBalanceAlert, alert_id)
    if row is None:
        raise NotFound("Low-balance alert not found")
    return LowBalanceAlertDto.model_validate(row)


# --- customer hours statement (DEC-031 P3) ----------------------------------------------------------------------
def _statement(
    session: Session,
    ctx: RequestContext,
    now: datetime,
    customer_id: uuid.UUID,
    machine_id: uuid.UUID | None,
    date_from: date | None,
    date_to: date | None,
) -> tuple[HoursStatementDto, ZoneInfo]:
    assert ctx.tenant_id is not None
    tz = ZoneInfo(tenant_settings(session, ctx.tenant_id).timezone)
    start, end = default_period(now.astimezone(tz).date())
    query = StatementQuery(customer_id, machine_id, date_from or start, date_to or end)
    params = {"date_from": query.date_from.isoformat(), "date_to": query.date_to.isoformat()}
    if machine_id is not None:
        params["machine_id"] = str(machine_id)
    pdf_path = f"/api/v1/tenant/customers/{customer_id}/hours-statement.pdf?{urlencode(params)}"
    return build_statement(session, tz, query, now, pdf_path), tz


@router.get(
    "/customers/{customer_id}/hours-statement",
    response_model=HoursStatementDto,
    operation_id="getCustomerHoursStatement",
)
def customer_statement(
    customer_id: uuid.UUID,
    session: DbSession,
    now: Now,
    ctx: Read,
    machine_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> HoursStatementDto:
    """Bought, activated, used per day and job, transferred, expired, cancelled and remaining hours of one customer
    (optionally one machine) for a tenant-local period (default: this month to date)."""
    return _statement(session, ctx, now, customer_id, machine_id, date_from, date_to)[0]


@router.get(
    "/customers/{customer_id}/hours-statement.pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}, "description": "The statement as a PDF"}},
    operation_id="downloadCustomerHoursStatementPdf",
)
def customer_statement_pdf(
    customer_id: uuid.UUID,
    session: DbSession,
    now: Now,
    ctx: Read,
    machine_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> Response:
    dto, tz = _statement(session, ctx, now, customer_id, machine_id, date_from, date_to)
    assert ctx.tenant_id is not None
    tenant = session.get(Tenant, ctx.tenant_id)
    user = session.get(AppUser, ctx.user_id)
    env = ReportEnv(
        str(tz),
        tenant.display_name if tenant else str(ctx.tenant_id),
        now,
        user.display_name if user else str(ctx.user_id),
    )
    content = statement_pdf(dto, env)
    AuditService(session).record(
        actor=ctx.audit_actor(),
        action="hours.statement_exported",
        entity_type="customer",
        entity_id=customer_id,
        tenant_id=ctx.tenant_id,
        after={
            "format": "pdf",
            "machine_id": str(machine_id) if machine_id else None,
            "date_from": dto.date_from.isoformat(),
            "date_to": dto.date_to.isoformat(),
        },
    )
    session.flush()
    name = f"asseta-hours-statement-{dto.date_from.isoformat()}-{dto.date_to.isoformat()}.pdf"
    return Response(
        content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{name}"', "Cache-Control": "no-store"},
    )
