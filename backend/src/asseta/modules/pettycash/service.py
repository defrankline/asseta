"""Petty cash funds (DEC-033): fund lifecycle; fundings and imprest top-ups (proposed, approved by someone else,
issued by someone other than the holder, acknowledged by the holder); returns (claimed by the holder, confirmed by the
office with the amount counted); counts (self-count marker, a difference opens a variance); holder changes (count at
the change, the old holder stays accountable until the new one acknowledges); fund adjustments (proposer != approver
!= holder); advances (phase 3). Every rule is the tenant's PETTY_CASH policy (CASH_CUSTODY for recording on someone
else's behalf, cash reasons and adjustment evidence); approvals are permissions; nothing here is a cost."""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound, PermissionDenied
from asseta.core.lifecycle import check_version, flush_versioned, mark_active, mark_inactive
from asseta.core.outbox import OutboxWriter
from asseta.core.search import ilike_any
from asseta.modules.adjustments.models import AdjustmentEntryStatus, AdjustmentType, AdjustmentUnit
from asseta.modules.adjustments.posting import AdjustmentPosting, post_adjustment
from asseta.modules.expenses.models import Expense, ExpenseStatus
from asseta.modules.finance.common import ZERO, currency_or_default, insert, resolve_staff
from asseta.modules.finance.custody_models import (
    AcknowledgementMethod,
    CashDecisionStatus,
    CashReason,
    CashReasonKind,
    CashVariance,
    VarianceSource,
)
from asseta.modules.finance.custody_rules import (
    cash_policy,
    check_reason,
    may_record_for_others,
    open_variance,
    own_staff,
    refuse_sod,
)
from asseta.modules.finance.deposit_accounts import require_active_account
from asseta.modules.finance.deposit_models import ACCOUNT_TYPE_METHOD, RemittanceMethod
from asseta.modules.finance.references import reference
from asseta.modules.fleet.models import StaffMember
from asseta.modules.geospatial.models import JobSite
from asseta.modules.identity.models import AppUser, Role, RolePermission, TenantMembership
from asseta.modules.identity.principal import RequestContext
from asseta.modules.meter.evidence_check import require_evidence
from asseta.modules.pettycash.dto import (
    PettyCashAcknowledgementIn,
    PettyCashAdjustmentDto,
    PettyCashAdjustmentIn,
    PettyCashAdvanceClearIn,
    PettyCashAdvanceDto,
    PettyCashAdvanceIn,
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
    PettyCashWitnessDto,
    TopUpRequestIn,
)
from asseta.modules.pettycash.ledger import FundLedger
from asseta.modules.pettycash.models import (
    INBOUND,
    AdvanceStatus,
    CountReason,
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
from asseta.modules.pettycash.permissions import COUNT_CODE, PETTY_OVERSIGHT
from asseta.modules.policy.petty_cash import PettyCashPolicy
from asseta.modules.policy.service import EffectivePolicy, PolicyService

TOPIC = "asseta.pettycash"
SERIES = "PC"  # one PC-<yyyy>-<nnnnn> series per tenant for movements, counts, adjustments and advances


def sees_all_funds(ctx: RequestContext) -> bool:
    return bool(PETTY_OVERSIGHT & set(ctx.permissions))


class PettyCashService:
    def __init__(self, session: Session, ctx: RequestContext, now: datetime):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid, self._now = session, ctx, ctx.tenant_id, now
        self._audit = AuditService(session)
        self.ledger = FundLedger(session, now)

    # --- shared ----------------------------------------------------------------------------------------------
    def policy(self) -> EffectivePolicy[PettyCashPolicy]:
        return PolicyService(self._s).petty_cash(self._tid, at=self._now)

    def _record(self, action: str, entity_type: str, entity_id: uuid.UUID, source: str = "API", **kw: Any) -> None:
        self._audit.record(
            actor=self._ctx.audit_actor(source.lower()),
            action=f"pettycash.{action}",
            entity_type=entity_type,
            entity_id=entity_id,
            tenant_id=self._tid,
            **kw,
        )

    def _emit(self, event_type: str, key: object, payload: dict[str, Any]) -> None:
        OutboxWriter(self._s).emit(
            topic=TOPIC, event_type=event_type, key=str(key), payload=payload, tenant_id=self._tid
        )

    def _number(self) -> str:
        return reference(self._s, self._tid, SERIES, self._now)

    def _own(self) -> StaffMember | None:
        return own_staff(self._s, self._ctx)

    def _is_holder(self, fund: PettyCashFund) -> bool:
        own = self._own()
        return own is not None and own.id == fund.holder_staff_id

    def _for_others(self) -> bool:
        return may_record_for_others(self._ctx, cash_policy(self._s, self._tid, self._now).policy)

    def visible_funds(self) -> Select[PettyCashFund]:
        """Office users see every fund; anyone else the funds they hold or are being handed."""
        stmt = select(PettyCashFund)
        if sees_all_funds(self._ctx):
            return stmt
        own = self._own()
        if own is None:
            return stmt.where(PettyCashFund.id.is_(None))
        incoming = select(PettyCashHolderChange.fund_id).where(
            PettyCashHolderChange.to_staff_id == own.id, PettyCashHolderChange.status == HolderChangeStatus.PENDING
        )
        return stmt.where(or_(PettyCashFund.holder_staff_id == own.id, PettyCashFund.id.in_(incoming)))

    def fund(self, fund_id: uuid.UUID, lock: bool = False) -> PettyCashFund:
        stmt = self.visible_funds().where(PettyCashFund.id == fund_id)
        row = self._s.execute(stmt.with_for_update() if lock else stmt).scalar_one_or_none()
        if row is None:  # another tenant's fund, or a fund the field user does not hold, is "not found"
            raise NotFound("Petty cash fund not found", code="PETTY_CASH_FUND_NOT_FOUND")
        return row

    def _active_fund(self, fund_id: uuid.UUID, lock: bool = False) -> PettyCashFund:
        fund = self.fund(fund_id, lock)
        if not fund.is_active:
            raise BusinessRuleViolation("This petty cash fund is inactive", code="PETTY_CASH_FUND_INACTIVE")
        return fund

    def _holder_or_recorder(self, fund: PettyCashFund, action: str) -> AcknowledgementMethod:
        """The fund's holder acts for themselves; someone else only when the tenant lets recorders act for others."""
        if self._is_holder(fund):
            return AcknowledgementMethod.RECEIVER
        if self._for_others():
            return AcknowledgementMethod.ON_BEHALF
        raise PermissionDenied(f"Only the fund's holder may {action}", code="NOT_FUND_HOLDER")

    def _account(self, account_id: uuid.UUID | None, fund: PettyCashFund, method: RemittanceMethod | None) -> Any:
        if account_id is None:
            return None, method
        account = require_active_account(self._s, account_id)
        if account.currency != fund.currency:
            raise BusinessRuleViolation(
                f"Deposit account {account.name} holds {account.currency}, not {fund.currency}",
                code="DEPOSIT_ACCOUNT_CURRENCY_MISMATCH",
            )
        return account, method or ACCOUNT_TYPE_METHOD[account.account_type]

    def holds_permission(self, user_id: uuid.UUID, code: str) -> bool:
        return (
            self._s.execute(
                select(AppUser.id)
                .join(TenantMembership, TenantMembership.user_id == AppUser.id)
                .join(RolePermission, RolePermission.role_id == TenantMembership.role_id)
                .join(Role, Role.id == TenantMembership.role_id)
                .where(
                    AppUser.id == user_id,
                    AppUser.is_active.is_(True),
                    TenantMembership.tenant_id == self._tid,
                    TenantMembership.effective_to.is_(None),
                    RolePermission.permission_code == code,
                )
                .limit(1)
            ).first()
            is not None
        )

    def witnesses(self) -> list[PettyCashWitnessDto]:
        """Everyone but the caller who may witness a count (the offline picker in the sync snapshot)."""
        rows = self._s.execute(
            select(AppUser.id, AppUser.display_name)
            .join(TenantMembership, TenantMembership.user_id == AppUser.id)
            .join(RolePermission, RolePermission.role_id == TenantMembership.role_id)
            .where(
                AppUser.is_active.is_(True),
                AppUser.id != self._ctx.user_id,
                TenantMembership.tenant_id == self._tid,
                TenantMembership.effective_to.is_(None),
                RolePermission.permission_code == COUNT_CODE,
            )
            .distinct()
            .order_by(AppUser.display_name, AppUser.id)
        ).all()
        return [PettyCashWitnessDto(user_id=r.id, name=r.display_name) for r in rows]

    # --- funds -----------------------------------------------------------------------------------------------
    def _site(self, site_id: uuid.UUID | None) -> uuid.UUID | None:
        if site_id is not None and self._s.get(JobSite, site_id) is None:
            raise NotFound("Job site not found")
        return site_id

    def fund_dto(self, fund: PettyCashFund, with_balance: bool = True) -> PettyCashFundDto:
        dto = PettyCashFundDto.model_validate(fund)
        dto.pending_holder_change_id = self._s.execute(
            select(PettyCashHolderChange.id).where(
                PettyCashHolderChange.fund_id == fund.id, PettyCashHolderChange.status == HolderChangeStatus.PENDING
            )
        ).scalar_one_or_none()
        if with_balance:
            dto.balance = self.ledger.balance(fund)
        return dto

    def list_funds(
        self, q: str | None, include_inactive: bool, holder_staff_id: uuid.UUID | None, mine: bool
    ) -> Select[PettyCashFund]:
        stmt = self.visible_funds().order_by(PettyCashFund.code, PettyCashFund.id)
        if mine:
            own = self._own()
            stmt = stmt.where(PettyCashFund.holder_staff_id == (own.id if own else None))
        if not include_inactive:
            stmt = stmt.where(PettyCashFund.is_active.is_(True))
        if holder_staff_id is not None:
            stmt = stmt.where(PettyCashFund.holder_staff_id == holder_staff_id)
        if (match := ilike_any(q, PettyCashFund.code, PettyCashFund.name)) is not None:
            stmt = stmt.where(match)
        return stmt

    def create_fund(self, body: PettyCashFundIn) -> PettyCashFundDto:
        holder = resolve_staff(self._s, self._ctx, body.holder_staff_id)
        row = PettyCashFund(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            code=body.code,
            name=body.name,
            holder_staff_id=holder.id,
            job_site_id=self._site(body.job_site_id),
            currency=currency_or_default(self._s, self._tid, body.currency),
            approved_limit=body.approved_limit,
            low_balance_level=body.low_balance_level,
            note=body.note,
            is_active=True,
            created_by=self._ctx.user_id,
        )
        insert(self._s, row, "DUPLICATE_PETTY_CASH_FUND", "A petty cash fund with this code already exists")
        self._record(
            "fund.created",
            "petty_cash_fund",
            row.id,
            after={
                "code": row.code,
                "name": row.name,
                "holder_staff_id": str(holder.id),
                "currency": row.currency,
                "approved_limit": str(row.approved_limit),
            },
        )
        return self.fund_dto(row)

    def update_fund(self, fund_id: uuid.UUID, body: PettyCashFundUpdateIn) -> PettyCashFundDto:
        row = self.fund(fund_id, lock=True)
        check_version(row.version, body.version, "Petty cash fund")
        before = {
            "code": row.code,
            "name": row.name,
            "approved_limit": str(row.approved_limit),
            "low_balance_level": str(row.low_balance_level) if row.low_balance_level is not None else None,
        }
        row.code, row.name, row.job_site_id = body.code, body.name, self._site(body.job_site_id)
        row.approved_limit, row.low_balance_level, row.note = body.approved_limit, body.low_balance_level, body.note
        flush_versioned(
            self._s, "Petty cash fund", "DUPLICATE_PETTY_CASH_FUND", "A petty cash fund with this code already exists"
        )
        self._record(
            "fund.updated",
            "petty_cash_fund",
            row.id,
            before=before,
            after={
                "code": row.code,
                "name": row.name,
                "approved_limit": str(row.approved_limit),
                "low_balance_level": str(row.low_balance_level) if row.low_balance_level is not None else None,
            },
        )
        return self.fund_dto(row)

    def _nothing_pending(self, fund: PettyCashFund) -> None:
        """Deactivation guard: zero balance and nothing waiting on the fund."""
        bal = self.ledger.balance(fund)
        waiting = {
            "PENDING_EXPENSES": bal.pending_spending > 0
            or self._s.execute(
                select(Expense.id)
                .where(Expense.petty_cash_fund_id == fund.id, Expense.status == ExpenseStatus.PENDING_APPROVAL)
                .limit(1)
            ).first()
            is not None,
            "MOVEMENTS_IN_PROGRESS": self._s.execute(
                select(PettyCashMovement.id)
                .where(
                    PettyCashMovement.fund_id == fund.id,
                    PettyCashMovement.status.in_(
                        (
                            MovementStatus.PROPOSED,
                            MovementStatus.APPROVED,
                            MovementStatus.ISSUED,
                            MovementStatus.CLAIMED,
                        )
                    ),
                )
                .limit(1)
            ).first()
            is not None,
            "PENDING_ADJUSTMENTS": bal.pending_adjustments != 0,
            "OUTSTANDING_ADVANCES": bal.advances_outstanding > 0,
            "OPEN_RETURN_DIFFERENCES": bal.open_return_differences != 0,
            "PENDING_HOLDER_CHANGE": self._s.execute(
                select(PettyCashHolderChange.id)
                .where(
                    PettyCashHolderChange.fund_id == fund.id,
                    PettyCashHolderChange.status == HolderChangeStatus.PENDING,
                )
                .limit(1)
            ).first()
            is not None,
        }
        if bal.balance != 0:
            raise BusinessRuleViolation(
                f"The fund still holds {fund.currency} {bal.balance}; return or adjust it to zero first",
                code="PETTY_CASH_FUND_NOT_EMPTY",
            )
        if blocking := sorted(k for k, v in waiting.items() if v):
            raise BusinessRuleViolation(
                f"Finish what is waiting on the fund first: {', '.join(blocking)}", code="PETTY_CASH_FUND_BUSY"
            )

    def set_active(self, fund_id: uuid.UUID, active: bool, reason: str, version: int | None) -> PettyCashFundDto:
        row = self.fund(fund_id, lock=True)
        check_version(row.version, version, "Petty cash fund")
        if active:
            mark_active(row, "Petty cash fund")
        else:
            self._nothing_pending(row)
            mark_inactive(row, self._ctx.user_id, reason, "Petty cash fund")
        flush_versioned(self._s, "Petty cash fund")
        self._record(
            f"fund.{'reactivated' if active else 'deactivated'}",
            "petty_cash_fund",
            row.id,
            after={"is_active": active},
            reason=reason,
        )
        return self.fund_dto(row)

    def my_funds(self) -> list[PettyCashFundDto]:
        own = self._own()
        if own is None:
            return []
        rows = self._s.execute(
            select(PettyCashFund)
            .where(PettyCashFund.holder_staff_id == own.id, PettyCashFund.is_active.is_(True))
            .order_by(PettyCashFund.code)
        ).scalars()
        return [self.fund_dto(f) for f in rows]

    # --- fundings and top-ups --------------------------------------------------------------------------------
    def movement(self, movement_id: uuid.UUID, lock: bool = False) -> PettyCashMovement:
        stmt = select(PettyCashMovement).where(
            PettyCashMovement.id == movement_id,
            PettyCashMovement.fund_id.in_(self.visible_funds().with_only_columns(PettyCashFund.id)),
        )
        row = self._s.execute(stmt.with_for_update() if lock else stmt).scalar_one_or_none()
        if row is None:
            raise NotFound("Petty cash movement not found", code="PETTY_CASH_MOVEMENT_NOT_FOUND")
        return row

    def movement_dto(self, m: PettyCashMovement) -> PettyCashMovementDto:
        dto = PettyCashMovementDto.model_validate(m)
        source = (
            VarianceSource.PETTY_CASH_RETURN if m.kind is MovementKind.RETURN else VarianceSource.PETTY_CASH_FUNDING
        )
        dto.variance_id = self._variance_id(source, m.id)
        return dto

    def _variance_id(self, source: VarianceSource, source_id: uuid.UUID) -> uuid.UUID | None:
        return self._s.execute(
            select(CashVariance.id).where(CashVariance.source_type == source, CashVariance.source_id == source_id)
        ).scalar_one_or_none()

    def _replay(self, model: Any, client_id: uuid.UUID | None) -> Any:
        if client_id is None:
            return None
        return self._s.execute(select(model).where(model.client_id == client_id)).scalar_one_or_none()

    def propose_funding(self, body: PettyCashFundingIn, source: str = "API") -> PettyCashMovementDto:
        if (existing := self._replay(PettyCashMovement, body.client_id)) is not None:
            return self.movement_dto(existing)
        fund = self._active_fund(body.fund_id, lock=True)
        return self._propose(fund, MovementKind(body.kind), body.amount, body, source)

    def request_top_up(self, fund_id: uuid.UUID, body: TopUpRequestIn, source: str = "API") -> PettyCashMovementDto:
        """The holder asks for a top-up; it waits for an approver like any proposal (never approved by the holder)."""
        if (existing := self._replay(PettyCashMovement, body.client_id)) is not None:
            return self.movement_dto(existing)
        fund = self._active_fund(fund_id, lock=True)
        if not self._is_holder(fund) and not sees_all_funds(self._ctx):
            raise PermissionDenied("Only the fund's holder may request a top-up", code="NOT_FUND_HOLDER")
        req = PettyCashFundingIn(
            client_id=body.client_id,
            fund_id=fund.id,
            kind=MovementKind.TOP_UP,
            amount=body.amount,
            note=body.note,
            above_cap_reason=body.above_cap_reason,
            client_created_at=body.client_created_at,
        )
        return self._propose(fund, MovementKind.TOP_UP, body.amount, req, source)

    def _propose(
        self,
        fund: PettyCashFund,
        kind: MovementKind,
        amount: Decimal | None,
        body: PettyCashFundingIn,
        source: str,
    ) -> PettyCashMovementDto:
        suggestion = self.ledger.top_up_suggestion(fund)
        if amount is None:
            amount = suggestion.suggested if kind is MovementKind.TOP_UP else suggestion.cap
        if amount <= 0:
            raise BusinessRuleViolation(
                "Nothing to top up: no approved spending since the last top-up, or the fund is at its limit",
                code="PETTY_CASH_NOTHING_TO_TOP_UP",
            )
        if amount > suggestion.cap and not body.above_cap_reason:
            raise BusinessRuleViolation(
                f"{fund.currency} {amount} is above what brings the fund to its limit ({fund.currency} "
                f"{suggestion.cap}); give the reason",
                code="PETTY_CASH_ABOVE_CAP_REASON_REQUIRED",
            )
        account, method = self._account(body.deposit_account_id, fund, body.method)
        row = PettyCashMovement(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            fund_id=fund.id,
            kind=kind,
            number=self._number(),
            client_id=body.client_id,
            holder_staff_id=fund.holder_staff_id,
            amount=amount,
            currency=fund.currency,
            status=MovementStatus.PROPOSED,
            deposit_account_id=account.id if account is not None else None,
            method=method.value if method is not None else None,
            reference=body.reference,
            note=body.note,
            suggested_amount=suggestion.suggested if kind is MovementKind.TOP_UP else None,
            cap_amount=suggestion.cap,
            above_cap_reason=body.above_cap_reason if amount > suggestion.cap else None,
            basis_from=suggestion.since,
            source=source,
            created_by=self._ctx.user_id,
            created_at=self._now,
            client_created_at=body.client_created_at,
        )
        insert(self._s, row, "DUPLICATE_PETTY_CASH_MOVEMENT", "Petty cash movement already recorded")
        self._record(
            f"{kind.value.lower()}.proposed",
            "petty_cash_movement",
            row.id,
            source,
            after={
                "fund_id": str(fund.id),
                "amount": str(amount),
                "currency": fund.currency,
                "suggested": str(suggestion.suggested),
                "cap": str(suggestion.cap),
            },
            reason=row.above_cap_reason,
        )
        self._emit(
            "PettyCashApprovalRequested",
            fund.id,
            {
                "kind": kind.value,
                "entity_type": "petty_cash_movement",
                "entity_id": str(row.id),
                "number": row.number,
                "fund_name": fund.name,
                "amount": str(amount),
                "currency": fund.currency,
            },
        )
        return self.movement_dto(row)

    def decide_movement(self, movement_id: uuid.UUID, body: PettyCashDecisionIn) -> PettyCashMovementDto:
        row = self.movement(movement_id, lock=True)
        if row.status is not MovementStatus.PROPOSED:
            raise Conflict(f"Already {row.status.value}", code="PETTY_CASH_ALREADY_DECIDED")
        fund = self.fund(row.fund_id)
        if row.created_by == self._ctx.user_id:
            refuse_sod(self._ctx, "approve", "petty_cash_movement", row.id, "A proposal is approved by someone else")
        if self._is_holder(fund):
            refuse_sod(self._ctx, "approve", "petty_cash_movement", row.id, "The holder cannot approve their own fund")
        row.status = MovementStatus.APPROVED if body.approve else MovementStatus.REJECTED
        row.decided_by, row.decided_at, row.decision_note = self._ctx.user_id, self._now, body.note
        self._s.flush()
        self._record(
            f"{row.kind.value.lower()}.{row.status.value.lower()}",
            "petty_cash_movement",
            row.id,
            before={"status": MovementStatus.PROPOSED.value},
            after={"status": row.status.value, "amount": str(row.amount)},
            reason=body.note,
        )
        if body.approve:
            self._emit(
                "PettyCashApproved",
                fund.id,
                {"entity_id": str(row.id), "number": row.number, "amount": str(row.amount), "currency": row.currency},
            )
        return self.movement_dto(row)

    def issue_movement(self, movement_id: uuid.UUID, body: PettyCashIssueIn) -> PettyCashMovementDto:
        row = self.movement(movement_id, lock=True)
        if row.status is not MovementStatus.APPROVED:
            raise Conflict(
                f"Only an approved funding is issued (it is {row.status.value})", code="PETTY_CASH_NOT_APPROVED"
            )
        fund = self._active_fund(row.fund_id)
        if self._is_holder(fund):
            refuse_sod(self._ctx, "issue", "petty_cash_movement", row.id, "The holder cannot issue money to themselves")
        evidence = require_evidence(
            self._s,
            self.policy().policy.funding_evidence_required,
            [*row.evidence_attachment_ids, *body.evidence_attachment_ids],
        )
        account, method = self._account(body.deposit_account_id or row.deposit_account_id, fund, body.method)
        row.status, row.issued_by, row.issued_at = MovementStatus.ISSUED, self._ctx.user_id, self._now
        row.deposit_account_id = account.id if account is not None else None
        row.method = method.value if method is not None else row.method
        row.reference = body.reference or row.reference
        row.evidence_attachment_ids = evidence
        self._s.flush()
        self._record(
            f"{row.kind.value.lower()}.issued",
            "petty_cash_movement",
            row.id,
            before={"status": MovementStatus.APPROVED.value},
            after={"status": row.status.value, "evidence_attachment_ids": [str(e) for e in evidence]},
            reason=body.note,
        )
        self._emit(
            "PettyCashToAcknowledge",
            fund.holder_staff_id,
            {
                "entity_type": "petty_cash_movement",
                "entity_id": str(row.id),
                "number": row.number,
                "staff_member_id": str(fund.holder_staff_id),
                "amount": str(row.amount),
                "currency": row.currency,
            },
        )
        return self.movement_dto(row)

    def acknowledge_movement(
        self,
        movement_id: uuid.UUID,
        body: PettyCashAcknowledgementIn,
        client_id: uuid.UUID | None = None,
        source: str = "API",
    ) -> PettyCashMovementDto:
        row = self.movement(movement_id, lock=True)
        if client_id is not None and row.receipt_client_id == client_id:
            return self.movement_dto(row)  # offline retry: one effect
        if row.kind not in INBOUND or row.status is not MovementStatus.ISSUED:
            raise Conflict(f"Nothing to acknowledge ({row.status.value})", code="PETTY_CASH_ALREADY_ACKNOWLEDGED")
        fund = self.fund(row.fund_id)
        method = self._holder_or_recorder(fund, "acknowledge money received")
        if method is AcknowledgementMethod.ON_BEHALF and self._ctx.user_id in (row.issued_by, row.decided_by):
            refuse_sod(
                self._ctx, "acknowledge", "petty_cash_movement", row.id, "Whoever issued it cannot confirm receipt"
            )
        received = (
            (body.amount_received if body.amount_received is not None else row.amount) if body.acknowledged else ZERO
        )
        row.status = MovementStatus.ACKNOWLEDGED if body.acknowledged else MovementStatus.DISPUTED
        row.received_by, row.received_at, row.amount_received = self._ctx.user_id, self._now, received
        row.receipt_method, row.receipt_note, row.receipt_client_id = method, body.note, client_id
        self._s.flush()
        self._record(
            f"{row.kind.value.lower()}.{row.status.value.lower()}",
            "petty_cash_movement",
            row.id,
            source,
            before={"status": MovementStatus.ISSUED.value},
            after={"status": row.status.value, "amount_received": str(received), "method": method.value},
            reason=body.note,
        )
        open_variance(
            self._s,
            self._ctx,
            self._now,
            source_type=VarianceSource.PETTY_CASH_FUNDING,
            source_id=row.id,
            accountable_staff_id=None,  # a funding difference sits with the office that issued it
            counterparty_staff_id=fund.holder_staff_id,
            currency=row.currency,
            declared=row.amount,
            received=received,
            petty_cash_fund_id=fund.id,
        )
        return self.movement_dto(row)

    def movement_expenses(self, movement_id: uuid.UUID) -> list[Expense]:
        """The approved spending a top-up proposal was based on (what the approver sees)."""
        row = self.movement(movement_id)
        return self.ledger.spending_since(row.fund_id, row.basis_from, row.created_at)

    # --- returns ---------------------------------------------------------------------------------------------
    def claim_return(self, body: PettyCashReturnIn, source: str = "API") -> PettyCashMovementDto:
        if (existing := self._replay(PettyCashMovement, body.client_id)) is not None:
            return self.movement_dto(existing)
        fund = self.fund(body.fund_id, lock=True)  # an inactive fund holds nothing to return
        self._holder_or_recorder(fund, "return the fund")
        evidence = require_evidence(
            self._s, self.policy().policy.return_evidence_required, body.evidence_attachment_ids
        )
        account, method = self._account(body.deposit_account_id, fund, body.method)
        row = PettyCashMovement(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            fund_id=fund.id,
            kind=MovementKind.RETURN,
            number=self._number(),
            client_id=body.client_id,
            holder_staff_id=fund.holder_staff_id,
            amount=body.amount,
            currency=fund.currency,
            status=MovementStatus.CLAIMED,
            deposit_account_id=account.id if account is not None else None,
            method=method.value if method is not None else None,
            reference=body.reference,
            note=body.note,
            evidence_attachment_ids=evidence,
            source=source,
            created_by=self._ctx.user_id,
            created_at=self._now,
            client_created_at=body.client_created_at,
        )
        insert(self._s, row, "DUPLICATE_PETTY_CASH_MOVEMENT", "Petty cash movement already recorded")
        self._record(
            "return.claimed",
            "petty_cash_movement",
            row.id,
            source,
            after={"fund_id": str(fund.id), "amount": str(row.amount), "currency": row.currency},
        )
        self._emit(
            "PettyCashReturnClaimed",
            fund.id,
            {
                "entity_type": "petty_cash_movement",
                "entity_id": str(row.id),
                "number": row.number,
                "fund_name": fund.name,
                "amount": str(row.amount),
                "currency": row.currency,
            },
        )
        return self.movement_dto(row)

    def confirm_return(self, movement_id: uuid.UUID, body: PettyCashReturnConfirmIn) -> PettyCashMovementDto:
        row = self.movement(movement_id, lock=True)
        if row.kind is not MovementKind.RETURN or row.status is not MovementStatus.CLAIMED:
            raise Conflict(f"Nothing to confirm ({row.status.value})", code="PETTY_CASH_ALREADY_CONFIRMED")
        fund = self.fund(row.fund_id)
        if row.created_by == self._ctx.user_id or self._is_holder(fund):
            refuse_sod(self._ctx, "confirm", "petty_cash_movement", row.id, "A return is confirmed by someone else")
        row.status, row.received_by, row.received_at = MovementStatus.CONFIRMED, self._ctx.user_id, self._now
        row.amount_received, row.receipt_note = body.amount_received, body.note
        self._s.flush()
        self._record(
            "return.confirmed",
            "petty_cash_movement",
            row.id,
            before={"status": MovementStatus.CLAIMED.value},
            after={"status": row.status.value, "amount": str(row.amount), "amount_received": str(body.amount_received)},
            reason=body.note,
        )
        open_variance(
            self._s,
            self._ctx,
            self._now,
            source_type=VarianceSource.PETTY_CASH_RETURN,
            source_id=row.id,
            accountable_staff_id=None,
            counterparty_staff_id=fund.holder_staff_id,
            currency=row.currency,
            declared=row.amount,
            received=body.amount_received,
            petty_cash_fund_id=fund.id,
        )
        return self.movement_dto(row)

    # --- counts ----------------------------------------------------------------------------------------------
    def count(self, count_id: uuid.UUID) -> PettyCashCount:
        row = self._s.execute(
            select(PettyCashCount).where(
                PettyCashCount.id == count_id,
                PettyCashCount.fund_id.in_(self.visible_funds().with_only_columns(PettyCashFund.id)),
            )
        ).scalar_one_or_none()
        if row is None:
            raise NotFound("Petty cash count not found", code="PETTY_CASH_COUNT_NOT_FOUND")
        return row

    def count_dto(self, c: PettyCashCount) -> PettyCashCountDto:
        dto = PettyCashCountDto.model_validate(c)
        dto.variance_id = self._variance_id(VarianceSource.PETTY_CASH_COUNT, c.id)
        return dto

    def record_count(
        self,
        body: PettyCashCountIn,
        source: str = "API",
        reason: CountReason = CountReason.ROUTINE,
    ) -> PettyCashCountDto:
        if (existing := self._replay(PettyCashCount, body.client_id)) is not None:
            return self.count_dto(existing)
        fund = self._active_fund(body.fund_id, lock=True)
        return self.count_dto(self._count(fund, body, source, reason))

    def _count(self, fund: PettyCashFund, body: PettyCashCountIn, source: str, reason: CountReason) -> PettyCashCount:
        if COUNT_CODE not in self._ctx.permissions:
            raise PermissionDenied(f"Missing permission {COUNT_CODE}")
        eff = self.policy()
        if body.witness_user_id is not None:
            if body.witness_user_id == self._ctx.user_id:
                raise BusinessRuleViolation("The witness is someone else", code="PETTY_CASH_WITNESS_INVALID")
            if not self.holds_permission(body.witness_user_id, COUNT_CODE):
                if source != "SYNC":
                    raise BusinessRuleViolation(
                        "The witness must hold the petty cash count permission", code="PETTY_CASH_WITNESS_INVALID"
                    )
                # Picked offline from the downloaded list, the witness lost the permission before the phone synced:
                # the count is a fact and is kept, recorded without a witness (a self-count when the holder counted).
                body = body.model_copy(update={"witness_user_id": None})
        evidence = require_evidence(self._s, False, body.evidence_attachment_ids)
        expected = self.ledger.figures(fund).available
        row = PettyCashCount(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            fund_id=fund.id,
            number=self._number(),
            client_id=body.client_id,
            reason=reason,
            holder_staff_id=fund.holder_staff_id,
            currency=fund.currency,
            counted_amount=body.counted_amount,
            expected_amount=expected,
            difference=body.counted_amount - expected,
            counted_by=self._ctx.user_id,
            counted_at=self._now,
            witness_user_id=body.witness_user_id,
            self_count=eff.policy.count_witness_required and body.witness_user_id is None and self._is_holder(fund),
            evidence_attachment_ids=evidence,
            note=body.note,
            source=source,
            policy_version=eff.version_stamp[:80],
            client_created_at=body.client_created_at,
        )
        insert(self._s, row, "DUPLICATE_PETTY_CASH_COUNT", "Count already recorded")
        self._record(
            "count.recorded",
            "petty_cash_count",
            row.id,
            source,
            after={
                "fund_id": str(fund.id),
                "counted": str(row.counted_amount),
                "expected": str(expected),
                "difference": str(row.difference),
                "self_count": row.self_count,
                "reason": reason.value,
            },
            policy_version=eff.version_stamp[:64],
        )
        open_variance(
            self._s,
            self._ctx,
            self._now,
            source_type=VarianceSource.PETTY_CASH_COUNT,
            source_id=row.id,
            accountable_staff_id=None,  # the holder is the counterparty; nobody's collections custody moves
            counterparty_staff_id=fund.holder_staff_id,
            currency=fund.currency,
            declared=expected,
            received=row.counted_amount,
            petty_cash_fund_id=fund.id,
        )
        return row

    # --- holder changes --------------------------------------------------------------------------------------
    def holder_change(self, change_id: uuid.UUID, lock: bool = False) -> PettyCashHolderChange:
        stmt = select(PettyCashHolderChange).where(
            PettyCashHolderChange.id == change_id,
            PettyCashHolderChange.fund_id.in_(self.visible_funds().with_only_columns(PettyCashFund.id)),
        )
        row = self._s.execute(stmt.with_for_update() if lock else stmt).scalar_one_or_none()
        if row is None:
            raise NotFound("Holder change not found", code="PETTY_CASH_HOLDER_CHANGE_NOT_FOUND")
        return row

    def start_holder_change(self, fund_id: uuid.UUID, body: PettyCashHolderChangeIn) -> PettyCashHolderChangeDto:
        fund = self._active_fund(fund_id, lock=True)
        to = resolve_staff(self._s, self._ctx, body.to_staff_id)
        if to.id == fund.holder_staff_id:
            raise BusinessRuleViolation("This person already holds the fund", code="PETTY_CASH_SAME_HOLDER")
        pending = self._s.execute(
            select(PettyCashHolderChange.id).where(
                PettyCashHolderChange.fund_id == fund.id, PettyCashHolderChange.status == HolderChangeStatus.PENDING
            )
        ).first()
        if pending is not None:
            raise Conflict("A holder change is already waiting", code="PETTY_CASH_HOLDER_CHANGE_PENDING")
        count = self._count(
            fund,
            PettyCashCountIn(
                fund_id=fund.id,
                counted_amount=body.counted_amount,
                witness_user_id=body.witness_user_id,
                evidence_attachment_ids=body.evidence_attachment_ids,
                note=body.note,
            ),
            "API",
            CountReason.HOLDER_CHANGE,
        )
        row = PettyCashHolderChange(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            fund_id=fund.id,
            from_staff_id=fund.holder_staff_id,
            to_staff_id=to.id,
            count_id=count.id,
            status=HolderChangeStatus.PENDING,
            note=body.note,
            requested_by=self._ctx.user_id,
            requested_at=self._now,
        )
        self._s.add(row)
        self._s.flush()
        self._record(
            "holder_change.requested",
            "petty_cash_holder_change",
            row.id,
            after={"fund_id": str(fund.id), "from": str(row.from_staff_id), "to": str(to.id), "count": str(count.id)},
            reason=body.note,
        )
        self._emit(
            "PettyCashToAcknowledge",
            to.id,
            {
                "entity_type": "petty_cash_holder_change",
                "entity_id": str(row.id),
                "number": fund.code,
                "staff_member_id": str(to.id),
                "amount": str(count.counted_amount),
                "currency": fund.currency,
            },
        )
        return PettyCashHolderChangeDto.model_validate(row)

    def decide_holder_change(
        self, change_id: uuid.UUID, body: PettyCashHolderChangeDecisionIn, source: str = "API"
    ) -> PettyCashHolderChangeDto:
        row = self.holder_change(change_id, lock=True)
        if row.status is not HolderChangeStatus.PENDING:
            raise Conflict(f"Holder change already {row.status.value}", code="PETTY_CASH_ALREADY_DECIDED")
        own = self._own()
        if own is not None and own.id == row.from_staff_id:
            refuse_sod(
                self._ctx,
                "acknowledge",
                "petty_cash_holder_change",
                row.id,
                "The outgoing holder cannot accept the fund for the new holder",
            )
        if own is None or own.id != row.to_staff_id:
            if not self._for_others():
                raise PermissionDenied("Only the new holder may take over the fund", code="NOT_FUND_HOLDER")
            if row.requested_by == self._ctx.user_id:
                refuse_sod(
                    self._ctx,
                    "acknowledge",
                    "petty_cash_holder_change",
                    row.id,
                    "Whoever started the change cannot accept it for the new holder",
                )
        fund = self._s.execute(
            select(PettyCashFund).where(PettyCashFund.id == row.fund_id).with_for_update()
        ).scalar_one()
        row.status = HolderChangeStatus.ACKNOWLEDGED if body.accept else HolderChangeStatus.DECLINED
        row.decided_by, row.decided_at, row.decision_note = self._ctx.user_id, self._now, body.note
        if body.accept:
            fund.holder_staff_id = row.to_staff_id
        flush_versioned(self._s, "Petty cash fund")
        self._record(
            f"holder_change.{row.status.value.lower()}",
            "petty_cash_holder_change",
            row.id,
            source,
            before={"status": HolderChangeStatus.PENDING.value, "holder_staff_id": str(row.from_staff_id)},
            after={"status": row.status.value, "holder_staff_id": str(fund.holder_staff_id)},
            reason=body.note,
        )
        return PettyCashHolderChangeDto.model_validate(row)

    def cancel_holder_change(self, change_id: uuid.UUID, note: str | None) -> PettyCashHolderChangeDto:
        row = self.holder_change(change_id, lock=True)
        if row.status is not HolderChangeStatus.PENDING:
            raise Conflict(f"Holder change already {row.status.value}", code="PETTY_CASH_ALREADY_DECIDED")
        row.status = HolderChangeStatus.CANCELLED
        row.decided_by, row.decided_at, row.decision_note = self._ctx.user_id, self._now, note
        self._s.flush()
        self._record(
            "holder_change.cancelled",
            "petty_cash_holder_change",
            row.id,
            before={"status": HolderChangeStatus.PENDING.value},
            after={"status": row.status.value},
            reason=note,
        )
        return PettyCashHolderChangeDto.model_validate(row)

    # --- adjustments -----------------------------------------------------------------------------------------
    def adjustment(self, adjustment_id: uuid.UUID, lock: bool = False) -> PettyCashAdjustment:
        stmt = select(PettyCashAdjustment).where(
            PettyCashAdjustment.id == adjustment_id,
            PettyCashAdjustment.fund_id.in_(self.visible_funds().with_only_columns(PettyCashFund.id)),
        )
        row = self._s.execute(stmt.with_for_update() if lock else stmt).scalar_one_or_none()
        if row is None:
            raise NotFound("Adjustment not found", code="PETTY_CASH_ADJUSTMENT_NOT_FOUND")
        return row

    def propose_adjustment(self, body: PettyCashAdjustmentIn) -> PettyCashAdjustmentDto:
        fund = self.fund(body.fund_id, lock=True)
        evidence = require_evidence(
            self._s,
            cash_policy(self._s, self._tid, self._now).policy.custody_adjustment_evidence_required,
            body.evidence_attachment_ids,
        )
        row = PettyCashAdjustment(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            fund_id=fund.id,
            number=self._number(),
            amount=body.amount,
            currency=fund.currency,
            reason_id=check_reason(self._s, CashReasonKind.ADJUSTMENT, body.reason_id),
            reason=body.reason,
            evidence_attachment_ids=evidence,
            status=CashDecisionStatus.PENDING,
            created_by=self._ctx.user_id,
            created_at=self._now,
        )
        self._s.add(row)
        self._s.flush()
        self._record(
            "adjustment.proposed",
            "petty_cash_adjustment",
            row.id,
            after={"fund_id": str(fund.id), "amount": str(row.amount), "currency": row.currency},
            reason=body.reason,
        )
        self._emit(
            "PettyCashApprovalRequested",
            fund.id,
            {
                "kind": "ADJUSTMENT",
                "entity_type": "petty_cash_adjustment",
                "entity_id": str(row.id),
                "number": row.number,
                "fund_name": fund.name,
                "amount": str(row.amount),
                "currency": row.currency,
            },
        )
        return PettyCashAdjustmentDto.model_validate(row)

    def decide_adjustment(self, adjustment_id: uuid.UUID, body: PettyCashDecisionIn) -> PettyCashAdjustmentDto:
        row = self.adjustment(adjustment_id, lock=True)
        if row.status is not CashDecisionStatus.PENDING:
            raise Conflict(f"Adjustment already {row.status.value}", code="PETTY_CASH_ALREADY_DECIDED")
        fund = self.fund(row.fund_id)
        if row.created_by == self._ctx.user_id or self._is_holder(fund):
            refuse_sod(
                self._ctx, "approve", "petty_cash_adjustment", row.id, "An adjustment is approved by someone else"
            )
        row.status = CashDecisionStatus.APPROVED if body.approve else CashDecisionStatus.REJECTED
        row.decided_by, row.decided_at, row.decision_note = self._ctx.user_id, self._now, body.note
        self._s.flush()
        self._record(
            f"adjustment.{row.status.value.lower()}",
            "petty_cash_adjustment",
            row.id,
            before={"status": "PENDING"},
            after={"status": row.status.value, "amount": str(row.amount)},
            reason=body.note,
        )
        reason = self._s.get(CashReason, row.reason_id) if row.reason_id else None
        post_adjustment(
            self._s,
            self._tid,
            self._now,
            AdjustmentPosting(
                adjustment_type=AdjustmentType.PETTY_CASH_ADJUSTMENT,
                status=AdjustmentEntryStatus(row.status.value),
                original_type="petty_cash_fund",
                original_id=fund.id,
                original_reference=fund.code,
                source_type="petty_cash_adjustment",
                source_id=row.id,
                unit=AdjustmentUnit.MONEY,
                amount=row.amount,
                currency=row.currency,
                resulting_balance=self.ledger.figures(fund).balance if body.approve else None,
                reason_id=row.reason_id,
                reason_label=reason.label if reason else None,
                reason=row.reason,
                evidence_attachment_ids=list(row.evidence_attachment_ids),
                requested_by=row.created_by,
                requested_at=row.created_at,
                approved_by=row.decided_by,
                approved_at=row.decided_at,
                decision_note=body.note,
                details={"fund_id": str(fund.id), "number": row.number},
            ),
        )
        return PettyCashAdjustmentDto.model_validate(row)

    # --- advances (phase 3) ----------------------------------------------------------------------------------
    def _advances_on(self) -> PettyCashPolicy:
        policy = self.policy().policy
        if not policy.advances_enabled:
            raise BusinessRuleViolation(
                "Cash advances are switched off for this tenant", code="PETTY_CASH_ADVANCES_DISABLED"
            )
        return policy

    def advance(self, advance_id: uuid.UUID, lock: bool = False) -> PettyCashAdvance:
        stmt = select(PettyCashAdvance).where(PettyCashAdvance.id == advance_id)
        if not sees_all_funds(self._ctx):
            own = self._own()
            stmt = stmt.where(
                or_(
                    PettyCashAdvance.fund_id.in_(self.visible_funds().with_only_columns(PettyCashFund.id)),
                    PettyCashAdvance.recipient_staff_id == (own.id if own else None),
                )
            )
        row = self._s.execute(stmt.with_for_update() if lock else stmt).scalar_one_or_none()
        if row is None:
            raise NotFound("Advance not found", code="PETTY_CASH_ADVANCE_NOT_FOUND")
        return row

    def advance_dto(self, a: PettyCashAdvance) -> PettyCashAdvanceDto:
        dto = PettyCashAdvanceDto.model_validate(a)
        approved, pending = self.ledger.advance_spending(a.id)
        dto.approved_spending, dto.pending_spending = approved, pending
        dto.remaining = a.amount - approved - pending if a.status is AdvanceStatus.OUTSTANDING else ZERO
        dto.overdue = a.status is AdvanceStatus.OUTSTANDING and a.due_at < self._now
        dto.variance_id = self._variance_id(VarianceSource.PETTY_CASH_ADVANCE, a.id)
        return dto

    def issue_advance(self, body: PettyCashAdvanceIn, source: str = "API") -> PettyCashAdvanceDto:
        if (existing := self._replay(PettyCashAdvance, body.client_id)) is not None:
            return self.advance_dto(existing)
        policy = self._advances_on()
        fund = self._active_fund(body.fund_id, lock=True)
        self._holder_or_recorder(fund, "hand out an advance")
        recipient = resolve_staff(self._s, self._ctx, body.recipient_staff_id)
        if recipient.id == fund.holder_staff_id:
            raise BusinessRuleViolation(
                "The holder spends from the fund directly; an advance goes to someone else",
                code="PETTY_CASH_ADVANCE_TO_HOLDER",
            )
        available = self.ledger.figures(fund).available
        if body.amount > available:
            raise BusinessRuleViolation(
                f"The fund has {fund.currency} {available} available", code="PETTY_CASH_INSUFFICIENT"
            )
        row = PettyCashAdvance(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            fund_id=fund.id,
            number=self._number(),
            client_id=body.client_id,
            recipient_staff_id=recipient.id,
            amount=body.amount,
            currency=fund.currency,
            purpose=body.purpose,
            status=AdvanceStatus.OUTSTANDING,
            issued_by=self._ctx.user_id,
            issued_at=self._now,
            due_at=self._now + timedelta(days=policy.advance_clear_within_days),
            source=source,
            client_created_at=body.client_created_at,
        )
        insert(self._s, row, "DUPLICATE_PETTY_CASH_ADVANCE", "Advance already recorded")
        self._record(
            "advance.issued",
            "petty_cash_advance",
            row.id,
            source,
            after={
                "fund_id": str(fund.id),
                "recipient_staff_id": str(recipient.id),
                "amount": str(row.amount),
                "due_at": row.due_at.isoformat(),
            },
            reason=body.purpose,
        )
        return self.advance_dto(row)

    def clear_advance(
        self,
        advance_id: uuid.UUID,
        body: PettyCashAdvanceClearIn,
        client_id: uuid.UUID | None = None,
        source: str = "API",
    ) -> PettyCashAdvanceDto:
        row = self.advance(advance_id, lock=True)
        if client_id is not None and row.clear_client_id == client_id:
            return self.advance_dto(row)
        if row.status is not AdvanceStatus.OUTSTANDING:
            raise Conflict("The advance is already cleared", code="PETTY_CASH_ADVANCE_CLEARED")
        own = self._own()
        if own is not None and own.id == row.recipient_staff_id:
            refuse_sod(
                self._ctx,
                "clear",
                "petty_cash_advance",
                row.id,
                "The fund's holder takes the change back, not the recipient",
            )
        fund = self._s.execute(select(PettyCashFund).where(PettyCashFund.id == row.fund_id)).scalar_one()
        self._holder_or_recorder(fund, "take the change back")
        approved, pending = self.ledger.advance_spending(row.id)
        if pending > 0:
            raise BusinessRuleViolation(
                "Expenses of this advance still wait for approval", code="PETTY_CASH_ADVANCE_EXPENSES_PENDING"
            )
        row.status, row.cleared_by, row.cleared_at = AdvanceStatus.CLEARED, self._ctx.user_id, self._now
        row.spent_amount, row.change_returned, row.clear_note = approved, body.change_returned, body.note
        row.clear_client_id = client_id
        self._s.flush()
        expected = row.amount - approved
        self._record(
            "advance.cleared",
            "petty_cash_advance",
            row.id,
            source,
            before={"status": AdvanceStatus.OUTSTANDING.value},
            after={
                "status": row.status.value,
                "spent": str(approved),
                "expected_change": str(expected),
                "change_returned": str(body.change_returned),
            },
            reason=body.note,
        )
        open_variance(
            self._s,
            self._ctx,
            self._now,
            source_type=VarianceSource.PETTY_CASH_ADVANCE,
            source_id=row.id,
            accountable_staff_id=None,
            counterparty_staff_id=row.recipient_staff_id,
            currency=row.currency,
            declared=expected,
            received=body.change_returned,
            petty_cash_fund_id=fund.id,
        )
        return self.advance_dto(row)
