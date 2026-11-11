"""Petty cash funds API (DEC-033) under /api/v1/tenant/petty-cash. Every route needs the tenant's PETTY_CASH capability
(PETTY_CASH_DISABLED when off). Field users (no oversight permission) only reach the funds they hold."""

import uuid
from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Header, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from asseta.core.clock import get_now
from asseta.core.config import get_settings
from asseta.core.db import get_session
from asseta.core.errors import ERROR_RESPONSES
from asseta.core.idempotency import IdempotencyGuard, request_hash
from asseta.core.lifecycle import IncludeInactive, LifecycleChangeIn
from asseta.core.paging import Page, PageParams, page_params, paginate
from asseta.core.search import ilike_any
from asseta.core.storage import ObjectStore
from asseta.modules.accountability.names import named
from asseta.modules.finance.common import local_date, period_conditions, tenant_settings
from asseta.modules.finance.custody_models import CashDecisionStatus
from asseta.modules.fleet.photos import get_object_store
from asseta.modules.identity.principal import RequestContext
from asseta.modules.meter.dto import AttachmentDto
from asseta.modules.meter.router import save_attachment
from asseta.modules.pettycash.dto import (
    FundFigure,
    PettyCashAcknowledgementIn,
    PettyCashAdjustmentDto,
    PettyCashAdjustmentIn,
    PettyCashAdvanceClearIn,
    PettyCashAdvanceDto,
    PettyCashAdvanceIn,
    PettyCashBalanceDto,
    PettyCashCountDto,
    PettyCashCountIn,
    PettyCashDecisionIn,
    PettyCashFundDto,
    PettyCashFundIn,
    PettyCashFundingIn,
    PettyCashFundUpdateIn,
    PettyCashHolderChangeDecisionIn,
    PettyCashHolderChangeDto,
    PettyCashHolderChangeIn,
    PettyCashIssueIn,
    PettyCashMovementDto,
    PettyCashReturnConfirmIn,
    PettyCashReturnIn,
    PettyCashStatementDto,
    PettyCashTransactionDto,
    TopUpExpenseDto,
    TopUpRequestIn,
    TopUpSuggestionDto,
)
from asseta.modules.pettycash.models import (
    AdvanceStatus,
    HolderChangeStatus,
    MovementKind,
    MovementStatus,
    PettyCashAdjustment,
    PettyCashAdvance,
    PettyCashCount,
    PettyCashFund,
    PettyCashHolderChange,
    PettyCashMovement,
)
from asseta.modules.pettycash.permissions import (
    PETTY_APPROVE,
    PETTY_COUNT,
    PETTY_MANAGE,
    PETTY_PROPOSE,
    PETTY_READ,
)
from asseta.modules.pettycash.service import PettyCashService, sees_all_funds

router = APIRouter(prefix="/api/v1/tenant/petty-cash", tags=["petty-cash"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]
Now = Annotated[datetime, Depends(get_now)]
IdemKey = Annotated[str | None, Header()]
Paging = Annotated[PageParams, Depends(page_params)]
Store = Annotated[ObjectStore, Depends(get_object_store)]
Read = Annotated[RequestContext, Depends(PETTY_READ)]
Manage = Annotated[RequestContext, Depends(PETTY_MANAGE)]
Propose = Annotated[RequestContext, Depends(PETTY_PROPOSE)]
Approve = Annotated[RequestContext, Depends(PETTY_APPROVE)]
Count = Annotated[RequestContext, Depends(PETTY_COUNT)]
DateFrom = Annotated[date | None, Query(alias="from", description="Tenant-local first day (default: 30 days back)")]
DateTo = Annotated[date | None, Query(alias="to", description="Tenant-local last day (default: today)")]
Mine = Annotated[bool, Query(description="Only the funds the caller holds")]


class NoteIn(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


def _page[T](items: list[T], total: int, paging: PageParams) -> Page[T]:
    return Page(items=items, total=total, page=paging.page, page_size=paging.page_size)


def _period(
    session: Session, ctx: RequestContext, now: datetime, first: date | None, last: date | None
) -> tuple[date, date]:
    assert ctx.tenant_id is not None
    today = local_date(tenant_settings(session, ctx.tenant_id).timezone, now)
    last = last or today
    return first or last.replace(day=1), last


def _idempotent[T: BaseModel](
    session: Session, ctx: RequestContext, op: str, key: str | None, body: BaseModel, dto_type: type[T], make: object
) -> T:
    guard = IdempotencyGuard(session, str(ctx.tenant_id), op, key, request_hash(body))
    if (replay := guard.begin()) is not None:
        return dto_type.model_validate(replay)
    assert callable(make)
    dto: T = make()
    guard.complete(dto, 201)
    return dto


# --- funds --------------------------------------------------------------------------------------------------------
@router.get("/funds", response_model=Page[PettyCashFundDto], operation_id="listPettyCashFunds")
@named
def list_funds(
    session: DbSession,
    now: Now,
    ctx: Read,
    paging: Paging,
    include_inactive: IncludeInactive = False,
    holder_staff_id: uuid.UUID | None = None,
    mine: Mine = False,
    with_balance: Annotated[bool, Query(description="Include each fund's ledger figures")] = True,
) -> Page[PettyCashFundDto]:
    """Funds (search by code or name; async-autocomplete friendly). Field users see the funds they hold."""
    svc = PettyCashService(session, ctx, now)
    rows, total = paginate(session, svc.list_funds(paging.q, include_inactive, holder_staff_id, mine), paging)
    return _page([svc.fund_dto(f, with_balance) for f in rows], total, paging)


@router.post("/funds", response_model=PettyCashFundDto, status_code=201, operation_id="createPettyCashFund")
@named
def create_fund(
    body: PettyCashFundIn, session: DbSession, now: Now, ctx: Manage, idempotency_key: IdemKey = None
) -> PettyCashFundDto:
    svc = PettyCashService(session, ctx, now)
    return _idempotent(
        session, ctx, "createPettyCashFund", idempotency_key, body, PettyCashFundDto, lambda: svc.create_fund(body)
    )


@router.get("/funds/mine", response_model=list[PettyCashFundDto], operation_id="listMyPettyCashFunds")
@named
def my_funds(session: DbSession, now: Now, ctx: Read) -> list[PettyCashFundDto]:
    """The active funds the caller holds, with balance and available to spend."""
    return PettyCashService(session, ctx, now).my_funds()


@router.get("/funds/{fund_id}", response_model=PettyCashFundDto, operation_id="getPettyCashFund")
@named
def get_fund(fund_id: uuid.UUID, session: DbSession, now: Now, ctx: Read) -> PettyCashFundDto:
    svc = PettyCashService(session, ctx, now)
    return svc.fund_dto(svc.fund(fund_id))


@router.put("/funds/{fund_id}", response_model=PettyCashFundDto, operation_id="updatePettyCashFund")
@named
def update_fund(
    fund_id: uuid.UUID, body: PettyCashFundUpdateIn, session: DbSession, now: Now, ctx: Manage
) -> PettyCashFundDto:
    """Code, name, site, limit and low-balance level. The holder changes through a holder change."""
    return PettyCashService(session, ctx, now).update_fund(fund_id, body)


@router.post("/funds/{fund_id}/deactivate", response_model=PettyCashFundDto, operation_id="deactivatePettyCashFund")
@named
def deactivate_fund(
    fund_id: uuid.UUID, body: LifecycleChangeIn, session: DbSession, now: Now, ctx: Manage
) -> PettyCashFundDto:
    """Only at zero balance with nothing pending (PETTY_CASH_FUND_NOT_EMPTY / PETTY_CASH_FUND_BUSY)."""
    return PettyCashService(session, ctx, now).set_active(fund_id, False, body.reason, body.version)


@router.post("/funds/{fund_id}/reactivate", response_model=PettyCashFundDto, operation_id="reactivatePettyCashFund")
@named
def reactivate_fund(
    fund_id: uuid.UUID, body: LifecycleChangeIn, session: DbSession, now: Now, ctx: Manage
) -> PettyCashFundDto:
    return PettyCashService(session, ctx, now).set_active(fund_id, True, body.reason, body.version)


@router.get("/funds/{fund_id}/balance", response_model=PettyCashBalanceDto, operation_id="getPettyCashFundBalance")
@named
def fund_balance(fund_id: uuid.UUID, session: DbSession, now: Now, ctx: Read) -> PettyCashBalanceDto:
    svc = PettyCashService(session, ctx, now)
    return svc.ledger.balance(svc.fund(fund_id))


@router.get(
    "/funds/{fund_id}/transactions",
    response_model=list[PettyCashTransactionDto],
    operation_id="listPettyCashFundTransactions",
)
@named
def fund_transactions(
    fund_id: uuid.UUID,
    session: DbSession,
    now: Now,
    ctx: Read,
    date_from: DateFrom = None,
    date_to: DateTo = None,
    figure: Annotated[list[FundFigure] | None, Query(description="Only these figures")] = None,
) -> list[PettyCashTransactionDto]:
    """The records behind each figure of the fund ledger, latest first."""
    svc = PettyCashService(session, ctx, now)
    first, last = _period(session, ctx, now, date_from, date_to)
    return svc.ledger.transactions(svc.fund(fund_id), first, last, figure)


@router.get(
    "/funds/{fund_id}/statement", response_model=PettyCashStatementDto, operation_id="getPettyCashFundStatement"
)
@named
def fund_statement(
    fund_id: uuid.UUID, session: DbSession, now: Now, ctx: Read, date_from: DateFrom = None, date_to: DateTo = None
) -> PettyCashStatementDto:
    """Every movement of the balance with the running balance (opening, lines, closing)."""
    svc = PettyCashService(session, ctx, now)
    first, last = _period(session, ctx, now, date_from, date_to)
    return svc.ledger.statement(svc.fund(fund_id), first, last)


@router.get(
    "/funds/{fund_id}/top-up-suggestion", response_model=TopUpSuggestionDto, operation_id="getPettyCashTopUpSuggestion"
)
def top_up_suggestion(fund_id: uuid.UUID, session: DbSession, now: Now, ctx: Read) -> TopUpSuggestionDto:
    """Approved spending since the last issued funding or top-up, capped at limit - balance - money on its way."""
    svc = PettyCashService(session, ctx, now)
    return svc.ledger.top_up_suggestion(svc.fund(fund_id))


@router.post(
    "/funds/{fund_id}/top-up-requests",
    response_model=PettyCashMovementDto,
    status_code=201,
    operation_id="requestPettyCashTopUp",
)
@named
def request_top_up(
    fund_id: uuid.UUID, body: TopUpRequestIn, session: DbSession, now: Now, ctx: Read, idempotency_key: IdemKey = None
) -> PettyCashMovementDto:
    """The holder asks for a top-up (pre-filled with the suggestion); someone else approves and issues it."""
    svc = PettyCashService(session, ctx, now)
    return _idempotent(
        session,
        ctx,
        "requestPettyCashTopUp",
        idempotency_key,
        body,
        PettyCashMovementDto,
        lambda: svc.request_top_up(fund_id, body),
    )


# --- movements: fundings, top-ups, returns ------------------------------------------------------------------------
@router.post("/fundings", response_model=PettyCashMovementDto, status_code=201, operation_id="proposePettyCashFunding")
@named
def propose_funding(
    body: PettyCashFundingIn, session: DbSession, now: Now, ctx: Propose, idempotency_key: IdemKey = None
) -> PettyCashMovementDto:
    """Propose a FUNDING or TOP_UP. Above the cap (limit - balance - money on its way) needs `above_cap_reason`."""
    svc = PettyCashService(session, ctx, now)
    return _idempotent(
        session,
        ctx,
        "proposePettyCashFunding",
        idempotency_key,
        body,
        PettyCashMovementDto,
        lambda: svc.propose_funding(body),
    )


@router.get("/movements", response_model=Page[PettyCashMovementDto], operation_id="listPettyCashMovements")
@named
def list_movements(
    session: DbSession,
    now: Now,
    ctx: Read,
    paging: Paging,
    fund_id: uuid.UUID | None = None,
    kind: MovementKind | None = None,
    status: MovementStatus | None = None,
    date_from: Annotated[date | None, Query(description="Created on or after this tenant-local day")] = None,
    date_to: Annotated[date | None, Query(description="Created on or before this tenant-local day")] = None,
) -> Page[PettyCashMovementDto]:
    """Fundings, top-ups and returns, latest first; `q` searches the PC- number and reference."""
    svc = PettyCashService(session, ctx, now)
    assert ctx.tenant_id is not None
    stmt: Select[PettyCashMovement] = (
        select(PettyCashMovement)
        .where(PettyCashMovement.fund_id.in_(svc.visible_funds().with_only_columns(PettyCashFund.id)))
        .where(*period_conditions(session, ctx.tenant_id, PettyCashMovement.created_at, date_from, date_to))
        .order_by(PettyCashMovement.created_at.desc(), PettyCashMovement.id)
    )
    for col, val in (
        (PettyCashMovement.fund_id, fund_id),
        (PettyCashMovement.kind, kind),
        (PettyCashMovement.status, status),
    ):
        if val is not None:
            stmt = stmt.where(col == val)
    if (match := ilike_any(paging.q, PettyCashMovement.number, PettyCashMovement.reference)) is not None:
        stmt = stmt.where(match)
    rows, total = paginate(session, stmt, paging)
    return _page([svc.movement_dto(m) for m in rows], total, paging)


@router.get("/movements/{movement_id}", response_model=PettyCashMovementDto, operation_id="getPettyCashMovement")
@named
def get_movement(movement_id: uuid.UUID, session: DbSession, now: Now, ctx: Read) -> PettyCashMovementDto:
    svc = PettyCashService(session, ctx, now)
    return svc.movement_dto(svc.movement(movement_id))


@router.get(
    "/movements/{movement_id}/expenses",
    response_model=list[TopUpExpenseDto],
    operation_id="listPettyCashMovementExpenses",
)
def movement_expenses(movement_id: uuid.UUID, session: DbSession, now: Now, ctx: Read) -> list[TopUpExpenseDto]:
    """The approved spending a top-up proposal was based on (what the approver checks)."""
    rows = PettyCashService(session, ctx, now).movement_expenses(movement_id)
    return [
        TopUpExpenseDto(
            id=e.id,
            description=e.description,
            amount=e.amount,
            incurred_at=e.incurred_at,
            decided_at=e.decided_at,
            category_id=e.category_id,
            machine_id=e.machine_id,
            job_id=e.job_id,
        )
        for e in rows
    ]


@router.post(
    "/movements/{movement_id}/decision", response_model=PettyCashMovementDto, operation_id="decidePettyCashMovement"
)
@named
def decide_movement(
    movement_id: uuid.UUID, body: PettyCashDecisionIn, session: DbSession, now: Now, ctx: Approve
) -> PettyCashMovementDto:
    """Approve or reject a proposed funding or top-up. Never the proposer, never the fund's holder."""
    return PettyCashService(session, ctx, now).decide_movement(movement_id, body)


@router.post(
    "/movements/{movement_id}/issue", response_model=PettyCashMovementDto, operation_id="issuePettyCashMovement"
)
@named
def issue_movement(
    movement_id: uuid.UUID, body: PettyCashIssueIn, session: DbSession, now: Now, ctx: Propose
) -> PettyCashMovementDto:
    """Hand the approved money over (evidence per policy). Never by the holder; the holder then acknowledges."""
    return PettyCashService(session, ctx, now).issue_movement(movement_id, body)


@router.post(
    "/movements/{movement_id}/acknowledgement",
    response_model=PettyCashMovementDto,
    operation_id="acknowledgePettyCashMovement",
)
@named
def acknowledge_movement(
    movement_id: uuid.UUID, body: PettyCashAcknowledgementIn, session: DbSession, now: Now, ctx: Read
) -> PettyCashMovementDto:
    """The holder confirms the amount received (a difference opens a variance) or disputes it."""
    return PettyCashService(session, ctx, now).acknowledge_movement(movement_id, body)


@router.post("/returns", response_model=PettyCashMovementDto, status_code=201, operation_id="claimPettyCashReturn")
@named
def claim_return(
    body: PettyCashReturnIn, session: DbSession, now: Now, ctx: Read, idempotency_key: IdemKey = None
) -> PettyCashMovementDto:
    """The holder hands money back (CLAIMED: it never reduces the balance until the office confirms it)."""
    svc = PettyCashService(session, ctx, now)
    return _idempotent(
        session,
        ctx,
        "claimPettyCashReturn",
        idempotency_key,
        body,
        PettyCashMovementDto,
        lambda: svc.claim_return(body),
    )


@router.post(
    "/movements/{movement_id}/confirmation",
    response_model=PettyCashMovementDto,
    operation_id="confirmPettyCashReturn",
)
@named
def confirm_return(
    movement_id: uuid.UUID, body: PettyCashReturnConfirmIn, session: DbSession, now: Now, ctx: Propose
) -> PettyCashMovementDto:
    """The office confirms the amount it counted (a difference opens a variance). Never the holder or claimer."""
    return PettyCashService(session, ctx, now).confirm_return(movement_id, body)


# --- counts -------------------------------------------------------------------------------------------------------
@router.post("/counts", response_model=PettyCashCountDto, status_code=201, operation_id="recordPettyCashCount")
@named
def record_count(
    body: PettyCashCountIn, session: DbSession, now: Now, ctx: Count, idempotency_key: IdemKey = None
) -> PettyCashCountDto:
    """Counted against the cash expected now (available to spend); a difference opens a variance. The holder alone
    is marked self-count when the tenant asks for a witness."""
    svc = PettyCashService(session, ctx, now)
    return _idempotent(
        session, ctx, "recordPettyCashCount", idempotency_key, body, PettyCashCountDto, lambda: svc.record_count(body)
    )


@router.get("/counts", response_model=Page[PettyCashCountDto], operation_id="listPettyCashCounts")
@named
def list_counts(
    session: DbSession, now: Now, ctx: Read, paging: Paging, fund_id: uuid.UUID | None = None
) -> Page[PettyCashCountDto]:
    svc = PettyCashService(session, ctx, now)
    stmt = (
        select(PettyCashCount)
        .where(PettyCashCount.fund_id.in_(svc.visible_funds().with_only_columns(PettyCashFund.id)))
        .order_by(PettyCashCount.counted_at.desc(), PettyCashCount.id)
    )
    if fund_id is not None:
        stmt = stmt.where(PettyCashCount.fund_id == fund_id)
    if (match := ilike_any(paging.q, PettyCashCount.number)) is not None:
        stmt = stmt.where(match)
    rows, total = paginate(session, stmt, paging)
    return _page([svc.count_dto(c) for c in rows], total, paging)


@router.get("/counts/{count_id}", response_model=PettyCashCountDto, operation_id="getPettyCashCount")
@named
def get_count(count_id: uuid.UUID, session: DbSession, now: Now, ctx: Read) -> PettyCashCountDto:
    svc = PettyCashService(session, ctx, now)
    return svc.count_dto(svc.count(count_id))


# --- holder changes -----------------------------------------------------------------------------------------------
@router.post(
    "/funds/{fund_id}/holder-changes",
    response_model=PettyCashHolderChangeDto,
    status_code=201,
    operation_id="startPettyCashHolderChange",
)
@named
def start_holder_change(
    fund_id: uuid.UUID, body: PettyCashHolderChangeIn, session: DbSession, now: Now, ctx: Manage
) -> PettyCashHolderChangeDto:
    """Count at the change, then the new holder acknowledges; the old holder stays accountable until then."""
    return PettyCashService(session, ctx, now).start_holder_change(fund_id, body)


@router.get("/holder-changes", response_model=Page[PettyCashHolderChangeDto], operation_id="listPettyCashHolderChanges")
@named
def list_holder_changes(
    session: DbSession,
    now: Now,
    ctx: Read,
    paging: Paging,
    fund_id: uuid.UUID | None = None,
    status: HolderChangeStatus | None = None,
) -> Page[PettyCashHolderChangeDto]:
    svc = PettyCashService(session, ctx, now)
    stmt = (
        select(PettyCashHolderChange)
        .where(PettyCashHolderChange.fund_id.in_(svc.visible_funds().with_only_columns(PettyCashFund.id)))
        .order_by(PettyCashHolderChange.requested_at.desc(), PettyCashHolderChange.id)
    )
    if fund_id is not None:
        stmt = stmt.where(PettyCashHolderChange.fund_id == fund_id)
    if status is not None:
        stmt = stmt.where(PettyCashHolderChange.status == status)
    rows, total = paginate(session, stmt, paging)
    return _page([PettyCashHolderChangeDto.model_validate(r) for r in rows], total, paging)


@router.get(
    "/holder-changes/{change_id}", response_model=PettyCashHolderChangeDto, operation_id="getPettyCashHolderChange"
)
@named
def get_holder_change(change_id: uuid.UUID, session: DbSession, now: Now, ctx: Read) -> PettyCashHolderChangeDto:
    return PettyCashHolderChangeDto.model_validate(PettyCashService(session, ctx, now).holder_change(change_id))


@router.post(
    "/holder-changes/{change_id}/acknowledgement",
    response_model=PettyCashHolderChangeDto,
    operation_id="acknowledgePettyCashHolderChange",
)
@named
def acknowledge_holder_change(
    change_id: uuid.UUID, body: PettyCashHolderChangeDecisionIn, session: DbSession, now: Now, ctx: Read
) -> PettyCashHolderChangeDto:
    """The new holder accepts (the fund is theirs from now) or declines (nothing changes)."""
    return PettyCashService(session, ctx, now).decide_holder_change(change_id, body)


@router.post(
    "/holder-changes/{change_id}/cancel",
    response_model=PettyCashHolderChangeDto,
    operation_id="cancelPettyCashHolderChange",
)
@named
def cancel_holder_change(
    change_id: uuid.UUID, body: NoteIn, session: DbSession, now: Now, ctx: Manage
) -> PettyCashHolderChangeDto:
    return PettyCashService(session, ctx, now).cancel_holder_change(change_id, body.note)


# --- adjustments --------------------------------------------------------------------------------------------------
@router.post(
    "/adjustments", response_model=PettyCashAdjustmentDto, status_code=201, operation_id="proposePettyCashAdjustment"
)
@named
def propose_adjustment(
    body: PettyCashAdjustmentIn, session: DbSession, now: Now, ctx: Propose, idempotency_key: IdemKey = None
) -> PettyCashAdjustmentDto:
    """A signed correction with a reason from the tenant's adjustment list (evidence per CASH_CUSTODY policy)."""
    svc = PettyCashService(session, ctx, now)
    return _idempotent(
        session,
        ctx,
        "proposePettyCashAdjustment",
        idempotency_key,
        body,
        PettyCashAdjustmentDto,
        lambda: svc.propose_adjustment(body),
    )


@router.get("/adjustments", response_model=Page[PettyCashAdjustmentDto], operation_id="listPettyCashAdjustments")
@named
def list_adjustments(
    session: DbSession,
    now: Now,
    ctx: Read,
    paging: Paging,
    fund_id: uuid.UUID | None = None,
    status: CashDecisionStatus | None = None,
) -> Page[PettyCashAdjustmentDto]:
    svc = PettyCashService(session, ctx, now)
    stmt = (
        select(PettyCashAdjustment)
        .where(PettyCashAdjustment.fund_id.in_(svc.visible_funds().with_only_columns(PettyCashFund.id)))
        .order_by(PettyCashAdjustment.created_at.desc(), PettyCashAdjustment.id)
    )
    if fund_id is not None:
        stmt = stmt.where(PettyCashAdjustment.fund_id == fund_id)
    if status is not None:
        stmt = stmt.where(PettyCashAdjustment.status == status)
    if (match := ilike_any(paging.q, PettyCashAdjustment.number, PettyCashAdjustment.reason)) is not None:
        stmt = stmt.where(match)
    rows, total = paginate(session, stmt, paging)
    return _page([PettyCashAdjustmentDto.model_validate(r) for r in rows], total, paging)


@router.get(
    "/adjustments/{adjustment_id}", response_model=PettyCashAdjustmentDto, operation_id="getPettyCashAdjustment"
)
@named
def get_adjustment(adjustment_id: uuid.UUID, session: DbSession, now: Now, ctx: Read) -> PettyCashAdjustmentDto:
    return PettyCashAdjustmentDto.model_validate(PettyCashService(session, ctx, now).adjustment(adjustment_id))


@router.post(
    "/adjustments/{adjustment_id}/decision",
    response_model=PettyCashAdjustmentDto,
    operation_id="decidePettyCashAdjustment",
)
@named
def decide_adjustment(
    adjustment_id: uuid.UUID, body: PettyCashDecisionIn, session: DbSession, now: Now, ctx: Approve
) -> PettyCashAdjustmentDto:
    """Never the proposer, never the fund's holder."""
    return PettyCashService(session, ctx, now).decide_adjustment(adjustment_id, body)


# --- advances (phase 3; PETTY_CASH_ADVANCES_DISABLED unless the tenant switches them on) --------------------------
@router.post("/advances", response_model=PettyCashAdvanceDto, status_code=201, operation_id="issuePettyCashAdvance")
@named
def issue_advance(
    body: PettyCashAdvanceIn, session: DbSession, now: Now, ctx: Read, idempotency_key: IdemKey = None
) -> PettyCashAdvanceDto:
    """Cash out of the fund to another person before a purchase; cleared with expenses and change within N days."""
    svc = PettyCashService(session, ctx, now)
    return _idempotent(
        session,
        ctx,
        "issuePettyCashAdvance",
        idempotency_key,
        body,
        PettyCashAdvanceDto,
        lambda: svc.issue_advance(body),
    )


@router.get("/advances", response_model=Page[PettyCashAdvanceDto], operation_id="listPettyCashAdvances")
@named
def list_advances(
    session: DbSession,
    now: Now,
    ctx: Read,
    paging: Paging,
    fund_id: uuid.UUID | None = None,
    status: AdvanceStatus | None = None,
    recipient_staff_id: uuid.UUID | None = None,
) -> Page[PettyCashAdvanceDto]:
    svc = PettyCashService(session, ctx, now)
    stmt = select(PettyCashAdvance).order_by(PettyCashAdvance.issued_at.desc(), PettyCashAdvance.id)
    if not sees_all_funds(ctx):
        own = svc._own()
        stmt = stmt.where(
            or_(
                PettyCashAdvance.fund_id.in_(svc.visible_funds().with_only_columns(PettyCashFund.id)),
                PettyCashAdvance.recipient_staff_id == (own.id if own else None),
            )
        )
    for col, val in (
        (PettyCashAdvance.fund_id, fund_id),
        (PettyCashAdvance.status, status),
        (PettyCashAdvance.recipient_staff_id, recipient_staff_id),
    ):
        if val is not None:
            stmt = stmt.where(col == val)
    if (match := ilike_any(paging.q, PettyCashAdvance.number, PettyCashAdvance.purpose)) is not None:
        stmt = stmt.where(match)
    rows, total = paginate(session, stmt, paging)
    return _page([svc.advance_dto(a) for a in rows], total, paging)


@router.get("/advances/{advance_id}", response_model=PettyCashAdvanceDto, operation_id="getPettyCashAdvance")
@named
def get_advance(advance_id: uuid.UUID, session: DbSession, now: Now, ctx: Read) -> PettyCashAdvanceDto:
    svc = PettyCashService(session, ctx, now)
    return svc.advance_dto(svc.advance(advance_id))


@router.post(
    "/advances/{advance_id}/clearance", response_model=PettyCashAdvanceDto, operation_id="clearPettyCashAdvance"
)
@named
def clear_advance(
    advance_id: uuid.UUID, body: PettyCashAdvanceClearIn, session: DbSession, now: Now, ctx: Read
) -> PettyCashAdvanceDto:
    """The holder takes the change back once the advance's expenses are decided; a difference opens a variance."""
    return PettyCashService(session, ctx, now).clear_advance(advance_id, body)


# --- evidence -----------------------------------------------------------------------------------------------------
@router.post("/evidence", response_model=AttachmentDto, status_code=201, operation_id="uploadPettyCashEvidence")
async def upload_evidence(
    session: DbSession, store: Store, ctx: Read, file: Annotated[UploadFile, File()]
) -> AttachmentDto:
    """A photo of a slip, the cash or a count sheet; reference its id in the request it supports."""
    data = await file.read(get_settings().max_image_bytes + 1)
    return AttachmentDto.model_validate(save_attachment(session, store, ctx, data, "PETTY_CASH_EVIDENCE"))
