"""Company deposit accounts (DEC-031 D1): list / detail / create / edit / deactivate / reactivate, and the
remittance evidence store (DEC-031 D2). Managing accounts needs `tenant.finance.accounts.manage`; anyone who records
or reads cash may list them (the remittance account picker). Only a masked account number is stored."""

import re
import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import Select, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.clock import get_now
from asseta.core.db import get_session
from asseta.core.errors import ERROR_RESPONSES, BusinessRuleViolation, NotFound
from asseta.core.lifecycle import (
    IncludeInactive,
    LifecycleChangeIn,
    check_version,
    flush_versioned,
    mark_active,
    mark_inactive,
)
from asseta.core.paging import Page, PageParams, page_params, paginate
from asseta.core.search import ilike_any
from asseta.modules.accountability.names import named
from asseta.modules.finance.common import currency_or_default, insert
from asseta.modules.finance.deposit_models import CompanyDepositAccount, DepositAccountType, RemittanceEvidence
from asseta.modules.identity.catalog import CATALOG, MenuDef
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.dependencies import requires, requires_any
from asseta.modules.identity.principal import RequestContext
from asseta.modules.meter.models import CaptureAttachment
from asseta.modules.platform_billing.dto import CurrencyCode

ACCOUNTS_MANAGE = requires(
    "tenant.finance.accounts.manage", S.TENANT, "Manage the company deposit accounts remittances are paid into"
)
ACCOUNTS_READ = requires_any(
    ("tenant.finance.accounts.manage", "tenant.finance.read", "tenant.collection.record", "tenant.finance.cash"),
    S.TENANT,
)
CATALOG.register_menu(
    MenuDef(
        "tenant.deposit_accounts",
        S.TENANT,
        "Deposit accounts",
        "/tenant/finance/deposit-accounts",
        68,
        "tenant.finance.accounts.manage",
        group="tenant.finance",
    )
)

Name = Annotated[str, StringConstraints(min_length=2, max_length=120, strip_whitespace=True)]
Text120 = Annotated[str, StringConstraints(max_length=120, strip_whitespace=True)]
AccountNumber = Annotated[str, StringConstraints(max_length=60, strip_whitespace=True)]
Note = Annotated[str, StringConstraints(max_length=1000, strip_whitespace=True)]


def mask_account_number(raw: str | None) -> str | None:
    """Keep only the last four characters of an account / wallet number ("•••• 4821"); never store the full one."""
    if raw is None:
        return None
    compact = re.sub(r"[\s-]", "", raw)
    if not compact:
        return None
    if set(compact) <= {"•", "*", "x", "X"} or len(compact) <= 4:
        return raw.strip()[:40]
    tail = compact[-4:]
    return f"•••• {tail}"


class DepositAccountIn(BaseModel):
    name: Name
    account_type: DepositAccountType
    institution: Text120 | None = Field(default=None, description="Bank or mobile-money operator")
    account_number: AccountNumber | None = Field(default=None, description="Stored masked (last four characters only)")
    currency: CurrencyCode | None = Field(default=None, description="Defaults to the tenant currency")
    note: Note | None = None


class DepositAccountUpdateIn(BaseModel):
    name: Name | None = None
    account_type: DepositAccountType | None = None
    institution: Text120 | None = None
    account_number: AccountNumber | None = Field(default=None, description="Replaces the masked number")
    currency: CurrencyCode | None = None
    note: Note | None = None
    version: int | None = Field(default=None, ge=1)


class DepositAccountDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    account_type: DepositAccountType
    institution: str | None
    account_number_masked: str | None
    currency: str
    note: str | None
    is_active: bool
    version: int
    created_by: uuid.UUID | None
    created_by_name: str | None = None
    created_at: datetime
    updated_at: datetime
    deactivated_at: datetime | None
    deactivated_by: uuid.UUID | None
    deactivated_by_name: str | None = None
    deactivation_reason: str | None


class SyncDepositAccountDto(DepositAccountDto):
    sync_revision: int


class RemittanceEvidenceDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    handover_id: uuid.UUID
    attachment_id: uuid.UUID
    created_by: uuid.UUID | None
    created_by_name: str | None = None
    created_at: datetime


class DepositAccountService:
    def __init__(self, session: Session, ctx: RequestContext, now: datetime):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid, self._now = session, ctx, ctx.tenant_id, now

    def _record(self, action: str, entity_id: uuid.UUID, **kw: Any) -> None:
        AuditService(self._s).record(
            actor=self._ctx.audit_actor(),
            action=action,
            entity_type="company_deposit_account",
            entity_id=entity_id,
            tenant_id=self._tid,
            **kw,
        )

    def query(
        self, q: str | None, include_inactive: bool, account_type: DepositAccountType | None
    ) -> Select[CompanyDepositAccount]:
        stmt = select(CompanyDepositAccount).order_by(CompanyDepositAccount.name, CompanyDepositAccount.id)
        if not include_inactive:
            stmt = stmt.where(CompanyDepositAccount.is_active.is_(True))
        if account_type is not None:
            stmt = stmt.where(CompanyDepositAccount.account_type == account_type)
        a = CompanyDepositAccount
        cond = ilike_any(q, a.name, a.institution, a.account_number_masked)
        return stmt.where(cond) if cond is not None else stmt

    def get(self, account_id: uuid.UUID) -> CompanyDepositAccount:
        row = self._s.get(CompanyDepositAccount, account_id)
        if row is None:
            raise NotFound("Deposit account not found", code="DEPOSIT_ACCOUNT_NOT_FOUND")
        return row

    def create(self, body: DepositAccountIn) -> CompanyDepositAccount:
        row = CompanyDepositAccount(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            name=body.name,
            account_type=body.account_type,
            institution=body.institution or None,
            account_number_masked=mask_account_number(body.account_number),
            currency=currency_or_default(self._s, self._tid, body.currency),
            note=body.note or None,
            is_active=True,
            created_by=self._ctx.user_id,
        )
        insert(self._s, row, "DUPLICATE_DEPOSIT_ACCOUNT", "A deposit account with this name already exists")
        self._record("finance.deposit_account.created", row.id, after=self._snapshot(row))
        return row

    def update(self, account_id: uuid.UUID, body: DepositAccountUpdateIn) -> CompanyDepositAccount:
        row = self.get(account_id)
        check_version(row.version, body.version, "Deposit account")
        before = self._snapshot(row)
        if body.name is not None:
            row.name = body.name
        if body.account_type is not None:
            row.account_type = body.account_type
        if body.institution is not None:
            row.institution = body.institution or None
        if body.account_number is not None:
            row.account_number_masked = mask_account_number(body.account_number)
        if body.currency is not None:
            row.currency = currency_or_default(self._s, self._tid, body.currency)
        if body.note is not None:
            row.note = body.note or None
        flush_versioned(
            self._s, "Deposit account", "DUPLICATE_DEPOSIT_ACCOUNT", "A deposit account with this name already exists"
        )
        self._record("finance.deposit_account.updated", row.id, before=before, after=self._snapshot(row))
        return row

    def set_active(self, account_id: uuid.UUID, body: LifecycleChangeIn, active: bool) -> CompanyDepositAccount:
        row = self.get(account_id)
        check_version(row.version, body.version, "Deposit account")
        if active:
            mark_active(row, "Deposit account")
        else:
            mark_inactive(row, self._ctx.user_id, body.reason, "Deposit account")
        flush_versioned(self._s, "Deposit account")
        self._record(
            f"finance.deposit_account.{'reactivated' if active else 'deactivated'}",
            row.id,
            after={"is_active": active},
            reason=body.reason,
        )
        return row

    @staticmethod
    def _snapshot(row: CompanyDepositAccount) -> dict[str, Any]:
        return {
            "name": row.name,
            "account_type": row.account_type.value,
            "institution": row.institution,
            "account_number_masked": row.account_number_masked,
            "currency": row.currency,
        }

    # --- remittance evidence ------------------------------------------------------------------------------------
    def link_evidence(self, handover_id: uuid.UUID, attachment_ids: list[uuid.UUID]) -> None:
        """Attach uploaded photos to a remittance (idempotent per attachment). Evidence only."""
        for att in dict.fromkeys(attachment_ids):
            if self._s.get(CaptureAttachment, att) is None:
                raise NotFound("Evidence attachment not found", code="ATTACHMENT_NOT_FOUND")
            self._s.execute(
                pg_insert(RemittanceEvidence)
                .values(
                    id=uuid.uuid4(),
                    tenant_id=self._tid,
                    handover_id=handover_id,
                    attachment_id=att,
                    created_by=self._ctx.user_id,
                    created_at=self._now,
                )
                .on_conflict_do_nothing(constraint="uq_remittance_evidence")
            )

    def evidence(self, handover_id: uuid.UUID) -> list[RemittanceEvidence]:
        return list(
            self._s.execute(
                select(RemittanceEvidence)
                .where(RemittanceEvidence.handover_id == handover_id)
                .order_by(RemittanceEvidence.created_at, RemittanceEvidence.id)
            ).scalars()
        )


def require_active_account(session: Session, account_id: uuid.UUID) -> CompanyDepositAccount:
    row = session.get(CompanyDepositAccount, account_id)
    if row is None:
        raise NotFound("Deposit account not found", code="DEPOSIT_ACCOUNT_NOT_FOUND")
    if not row.is_active:
        raise BusinessRuleViolation("Deposit account is inactive", code="DEPOSIT_ACCOUNT_INACTIVE")
    return row


# --- endpoints ----------------------------------------------------------------------------------------------------
router = APIRouter(prefix="/api/v1/tenant/deposit-accounts", tags=["finance"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]
Now = Annotated[datetime, Depends(get_now)]
Paging = Annotated[PageParams, Depends(page_params)]


@router.get("", response_model=Page[DepositAccountDto], operation_id="listDepositAccounts")
@named
def list_accounts(
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(ACCOUNTS_READ)],
    paging: Paging,
    account_type: DepositAccountType | None = None,
    include_inactive: IncludeInactive = False,
) -> Page[DepositAccountDto]:
    """Company deposit accounts (search by name, institution or masked number). Active only unless asked."""
    stmt = DepositAccountService(session, ctx, now).query(paging.q, include_inactive, account_type)
    rows, total = paginate(session, stmt, paging)
    return Page(
        items=[DepositAccountDto.model_validate(r) for r in rows],
        total=total,
        page=paging.page,
        page_size=paging.page_size,
    )


@router.post("", response_model=DepositAccountDto, status_code=201, operation_id="createDepositAccount")
@named
def create_account(
    body: DepositAccountIn, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(ACCOUNTS_MANAGE)]
) -> DepositAccountDto:
    return DepositAccountDto.model_validate(DepositAccountService(session, ctx, now).create(body))


@router.get("/{account_id}", response_model=DepositAccountDto, operation_id="getDepositAccount")
@named
def get_account(
    account_id: uuid.UUID, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(ACCOUNTS_READ)]
) -> DepositAccountDto:
    return DepositAccountDto.model_validate(DepositAccountService(session, ctx, now).get(account_id))


@router.patch("/{account_id}", response_model=DepositAccountDto, operation_id="updateDepositAccount")
@named
def update_account(
    account_id: uuid.UUID,
    body: DepositAccountUpdateIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(ACCOUNTS_MANAGE)],
) -> DepositAccountDto:
    return DepositAccountDto.model_validate(DepositAccountService(session, ctx, now).update(account_id, body))


@router.post("/{account_id}/deactivate", response_model=DepositAccountDto, operation_id="deactivateDepositAccount")
@named
def deactivate_account(
    account_id: uuid.UUID,
    body: LifecycleChangeIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(ACCOUNTS_MANAGE)],
) -> DepositAccountDto:
    """Deactivated accounts stay on past remittances but can no longer be chosen for new ones."""
    return DepositAccountDto.model_validate(
        DepositAccountService(session, ctx, now).set_active(account_id, body, active=False)
    )


@router.post("/{account_id}/reactivate", response_model=DepositAccountDto, operation_id="reactivateDepositAccount")
@named
def reactivate_account(
    account_id: uuid.UUID,
    body: LifecycleChangeIn,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(ACCOUNTS_MANAGE)],
) -> DepositAccountDto:
    return DepositAccountDto.model_validate(
        DepositAccountService(session, ctx, now).set_active(account_id, body, active=True)
    )
