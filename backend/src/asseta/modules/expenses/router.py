"""Expense categories, field expenses with receipts/GPS, fuel events and expense approvals."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Header, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.clock import get_now
from asseta.core.config import get_settings
from asseta.core.db import get_session
from asseta.core.errors import ERROR_RESPONSES, NotFound
from asseta.core.idempotency import IdempotencyGuard, request_hash
from asseta.core.lifecycle import IncludeInactive, LifecycleChangeIn
from asseta.core.paging import Page, PageParams, page_params, paginate
from asseta.core.search import ilike_any
from asseta.core.storage import ObjectStore
from asseta.modules.expenses.dto import (
    ApprovalDecisionIn,
    ApprovalRequestDto,
    ExpenseCategoryDto,
    ExpenseCategoryIn,
    ExpenseCategoryUpdateIn,
    ExpenseDto,
    ExpenseIn,
    FuelEventDto,
    FuelEventIn,
)
from asseta.modules.expenses.models import (
    ApprovalRequest,
    ApprovalStatus,
    Expense,
    ExpenseAttachment,
    ExpenseCategory,
    ExpenseStatus,
    FuelEvent,
    FuelEventType,
)
from asseta.modules.expenses.service import ExpenseService, expense_dto, expense_list_query
from asseta.modules.fleet.photos import PhotoUrlDto, get_object_store
from asseta.modules.identity.catalog import CATALOG, MenuDef
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.dependencies import requires
from asseta.modules.identity.principal import RequestContext
from asseta.modules.meter.dto import AttachmentDto
from asseta.modules.meter.models import CaptureAttachment
from asseta.modules.meter.router import save_attachment

EXPENSE_READ = requires("tenant.expense.read", S.TENANT, "View expenses, receipts, categories and fuel events")
EXPENSE_WRITE = requires("tenant.expense.write", S.TENANT, "Record expenses (with receipts/GPS) and fuel events")
CATEGORY_MANAGE = requires("tenant.finance.expense_category", S.TENANT, "Manage expense categories")
APPROVAL_READ = requires("tenant.approval.read", S.TENANT, "View approval requests")
APPROVE_EXPENSE = requires("tenant.approval.expense", S.TENANT, "Approve or reject expenses above policy limits")
for menu in (
    MenuDef(
        "tenant.expenses",
        S.TENANT,
        "Expenses & fuel",
        "/tenant/expenses",
        68,
        "tenant.expense.read",
        group="tenant.finance",
    ),
    MenuDef(
        "tenant.approvals",
        S.TENANT,
        "Approvals",
        "/tenant/approvals",
        69,
        "tenant.approval.read",
        group="tenant.finance",
    ),
):
    CATALOG.register_menu(menu)

router = APIRouter(prefix="/api/v1/tenant", tags=["expenses"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]
Now = Annotated[datetime, Depends(get_now)]
IdemKey = Annotated[str | None, Header()]
Store = Annotated[ObjectStore, Depends(get_object_store)]


@router.post(
    "/expense-categories", response_model=ExpenseCategoryDto, status_code=201, operation_id="createExpenseCategory"
)
def create_category(
    body: ExpenseCategoryIn, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(CATEGORY_MANAGE)]
) -> ExpenseCategoryDto:
    return ExpenseService(session, ctx, now).create_category(body)


@router.get("/expense-categories", response_model=list[ExpenseCategoryDto], operation_id="listExpenseCategories")
def categories(
    session: DbSession,
    _: Annotated[RequestContext, Depends(EXPENSE_READ)],
    q: Annotated[str | None, Query(max_length=100)] = None,
    include_inactive: IncludeInactive = False,
) -> list[ExpenseCategoryDto]:
    stmt = select(ExpenseCategory).order_by(ExpenseCategory.code)
    if (match := ilike_any(q, ExpenseCategory.code, ExpenseCategory.name)) is not None:
        stmt = stmt.where(match)
    if not include_inactive:
        stmt = stmt.where(ExpenseCategory.is_active.is_(True))
    return [ExpenseCategoryDto.model_validate(c) for c in session.execute(stmt).scalars()]


@router.get("/expense-categories/{category_id}", response_model=ExpenseCategoryDto, operation_id="getExpenseCategory")
def get_category(
    category_id: uuid.UUID, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(EXPENSE_READ)]
) -> ExpenseCategoryDto:
    return ExpenseCategoryDto.model_validate(ExpenseService(session, ctx, now).category(category_id))


@router.put(
    "/expense-categories/{category_id}", response_model=ExpenseCategoryDto, operation_id="updateExpenseCategory"
)
def update_category(
    category_id: uuid.UUID,
    body: ExpenseCategoryUpdateIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(CATEGORY_MANAGE)],
) -> ExpenseCategoryDto:
    return ExpenseService(session, ctx, now).update_category(category_id, body)


@router.post(
    "/expense-categories/{category_id}/deactivate",
    response_model=ExpenseCategoryDto,
    operation_id="deactivateExpenseCategory",
)
def deactivate_category(
    category_id: uuid.UUID,
    body: LifecycleChangeIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(CATEGORY_MANAGE)],
) -> ExpenseCategoryDto:
    """Refused for new expenses afterwards; recorded expenses keep their category."""
    return ExpenseService(session, ctx, now).set_category_active(category_id, False, body.reason, body.version)


@router.post(
    "/expense-categories/{category_id}/reactivate",
    response_model=ExpenseCategoryDto,
    operation_id="reactivateExpenseCategory",
)
def reactivate_category(
    category_id: uuid.UUID,
    body: LifecycleChangeIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(CATEGORY_MANAGE)],
) -> ExpenseCategoryDto:
    return ExpenseService(session, ctx, now).set_category_active(category_id, True, body.reason, body.version)


@router.post("/expenses", response_model=ExpenseDto, status_code=201, operation_id="submitExpense")
def submit_expense(
    body: ExpenseIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(EXPENSE_WRITE)],
    idempotency_key: IdemKey = None,
) -> ExpenseDto:
    guard = IdempotencyGuard(session, str(ctx.tenant_id), "submitExpense", idempotency_key, request_hash(body))
    if (replay := guard.begin()) is not None:
        return ExpenseDto.model_validate(replay)
    dto = ExpenseService(session, ctx, now).submit(body)
    guard.complete(dto, 201)
    return dto


@router.get("/expenses", response_model=Page[ExpenseDto], operation_id="listExpenses")
def list_expenses(
    session: DbSession,
    _: Annotated[RequestContext, Depends(EXPENSE_READ)],
    paging: Annotated[PageParams, Depends(page_params)],
    status: ExpenseStatus | None = None,
    machine_id: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
    custodian_staff_id: uuid.UUID | None = None,
) -> Page[ExpenseDto]:
    stmt = expense_list_query(status, machine_id, job_id, custodian_staff_id)
    rows, total = paginate(session, stmt, paging)
    return Page(
        items=[expense_dto(session, e) for e in rows], total=total, page=paging.page, page_size=paging.page_size
    )


@router.get("/expenses/{expense_id}", response_model=ExpenseDto, operation_id="getExpense")
def get_expense(
    expense_id: uuid.UUID, session: DbSession, _: Annotated[RequestContext, Depends(EXPENSE_READ)]
) -> ExpenseDto:
    row = session.get(Expense, expense_id)
    if row is None:
        raise NotFound("Expense not found")
    return expense_dto(session, row)


@router.post("/fuel-events", response_model=FuelEventDto, status_code=201, operation_id="recordFuelEvent")
def record_fuel(
    body: FuelEventIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(EXPENSE_WRITE)],
    idempotency_key: IdemKey = None,
) -> FuelEventDto:
    guard = IdempotencyGuard(session, str(ctx.tenant_id), "recordFuelEvent", idempotency_key, request_hash(body))
    if (replay := guard.begin()) is not None:
        return FuelEventDto.model_validate(replay)
    dto = ExpenseService(session, ctx, now).record_fuel(body)
    guard.complete(dto, 201)
    return dto


@router.get("/fuel-events", response_model=Page[FuelEventDto], operation_id="listFuelEvents")
def list_fuel(
    session: DbSession,
    _: Annotated[RequestContext, Depends(EXPENSE_READ)],
    paging: Annotated[PageParams, Depends(page_params)],
    event_type: FuelEventType | None = None,
    machine_id: uuid.UUID | None = None,
) -> Page[FuelEventDto]:
    stmt = select(FuelEvent).order_by(FuelEvent.occurred_at.desc())
    if event_type:
        stmt = stmt.where(FuelEvent.event_type == event_type)
    if machine_id:
        stmt = stmt.where(FuelEvent.machine_id == machine_id)
    rows, total = paginate(session, stmt, paging)
    return Page(
        items=[FuelEventDto.model_validate(f) for f in rows], total=total, page=paging.page, page_size=paging.page_size
    )


@router.get("/approvals", response_model=Page[ApprovalRequestDto], operation_id="listApprovalRequests")
def list_approvals(
    session: DbSession,
    _: Annotated[RequestContext, Depends(APPROVAL_READ)],
    paging: Annotated[PageParams, Depends(page_params)],
    status: ApprovalStatus | None = None,
) -> Page[ApprovalRequestDto]:
    stmt = select(ApprovalRequest).order_by(ApprovalRequest.requested_at.desc())
    if status:
        stmt = stmt.where(ApprovalRequest.status == status)
    rows, total = paginate(session, stmt, paging)
    return Page(
        items=[ApprovalRequestDto.model_validate(a) for a in rows],
        total=total,
        page=paging.page,
        page_size=paging.page_size,
    )


@router.post(
    "/approvals/{approval_id}/decision", response_model=ApprovalRequestDto, operation_id="decideApprovalRequest"
)
def decide_approval(
    approval_id: uuid.UUID,
    body: ApprovalDecisionIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(APPROVE_EXPENSE)],
) -> ApprovalRequestDto:
    return ExpenseService(session, ctx, now).decide(approval_id, body)


@router.post("/expense-receipts", response_model=AttachmentDto, status_code=201, operation_id="uploadExpenseReceipt")
async def upload_receipt(
    session: DbSession,
    store: Store,
    ctx: Annotated[RequestContext, Depends(EXPENSE_WRITE)],
    file: Annotated[UploadFile, File()],
) -> AttachmentDto:
    data = await file.read(get_settings().max_image_bytes + 1)
    return AttachmentDto.model_validate(save_attachment(session, store, ctx, data, "EXPENSE_RECEIPT"))


@router.get(
    "/expenses/{expense_id}/receipts/{attachment_id}/url",
    response_model=PhotoUrlDto,
    operation_id="getExpenseReceiptUrl",
)
def receipt_url(
    expense_id: uuid.UUID,
    attachment_id: uuid.UUID,
    session: DbSession,
    store: Store,
    _: Annotated[RequestContext, Depends(EXPENSE_READ)],
) -> PhotoUrlDto:
    linked = session.execute(
        select(ExpenseAttachment.id).where(
            ExpenseAttachment.expense_id == expense_id, ExpenseAttachment.attachment_id == attachment_id
        )
    ).first()
    row = session.get(CaptureAttachment, attachment_id) if linked else None
    if row is None:
        raise NotFound("Receipt not found")
    ttl = get_settings().presigned_url_ttl_seconds
    return PhotoUrlDto(url=store.presigned_get(row.object_key, ttl), expires_in_seconds=ttl)
