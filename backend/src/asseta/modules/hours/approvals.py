"""Authorised changes around customer hours: tenant reason lists, customer discounts and credit arrangements
(propose -> approve/reject, revoke), hours transfers and purchase cancellations (request -> approve/reject).

Approval is a permission held by any role; the proposer can never approve their own proposal (segregation of
duties, always on). Whether a step needs a second person at all is tenant policy (`*_requires_approval`); credit
arrangements always do."""

import uuid
from datetime import date, datetime
from typing import Any, cast

from sqlalchemy import Select, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound, PermissionDenied
from asseta.core.lifecycle import check_version, flush_versioned, mark_active, mark_inactive
from asseta.core.outbox import OutboxWriter
from asseta.core.search import ilike_any
from asseta.core.signals import sod_violation
from asseta.modules.finance.common import currency_or_default
from asseta.modules.fleet.models import Machine, MachineStatus
from asseta.modules.hours.dto import (
    CancellationDto,
    CancellationIn,
    CreditArrangementDto,
    CreditArrangementIn,
    CreditArrangementUpdateIn,
    CreditExposureDto,
    DecisionIn,
    DiscountDto,
    DiscountIn,
    DiscountUpdateIn,
    ReasonCodeDto,
    ReasonCodeIn,
    ReasonCodeUpdateIn,
    TransferDto,
    TransferIn,
)
from asseta.modules.hours.engine import TOPIC, HoursEngine
from asseta.modules.hours.ledger import ZERO, LedgerWriter, purchase_totals
from asseta.modules.hours.models import (
    CreditArrangement,
    CustomerDiscount,
    HoursCancellation,
    HoursPaymentAllocation,
    HoursPurchase,
    HoursReasonCode,
    HoursTransfer,
    LedgerEntryType,
    ProposalStatus,
    ReasonKind,
    RequestStatus,
)
from asseta.modules.identity.principal import RequestContext
from asseta.modules.jobs.models import Customer

T = LedgerEntryType
Proposal = CustomerDiscount | CreditArrangement


def reason_code_query(q: str | None, kind: ReasonKind | None, include_inactive: bool) -> Select[HoursReasonCode]:
    stmt = select(HoursReasonCode).order_by(HoursReasonCode.kind, HoursReasonCode.code)
    if kind is not None:
        stmt = stmt.where(HoursReasonCode.kind == kind)
    if (match := ilike_any(q, HoursReasonCode.code, HoursReasonCode.label)) is not None:
        stmt = stmt.where(match)
    return stmt if include_inactive else stmt.where(HoursReasonCode.is_active.is_(True))


def proposal_query[P: (CustomerDiscount, CreditArrangement)](
    model: type[P], q: str | None, status: ProposalStatus | None, customer_id: uuid.UUID | None
) -> Select[P]:
    stmt = select(model).order_by(model.proposed_at.desc(), model.id)
    if status is not None:
        stmt = stmt.where(model.status == status)
    if customer_id is not None:
        stmt = stmt.where(model.customer_id == customer_id)
    if (match := ilike_any(q, Customer.name, Customer.code, model.reason)) is not None:
        stmt = stmt.join(Customer, Customer.id == model.customer_id).where(match)
    return stmt


def request_query[R: (HoursTransfer, HoursCancellation)](
    model: type[R], q: str | None, status: RequestStatus | None, purchase_id: uuid.UUID | None
) -> Select[R]:
    stmt = select(model).order_by(model.requested_at.desc(), model.id)
    if status is not None:
        stmt = stmt.where(model.status == status)
    if purchase_id is not None:
        stmt = stmt.where(model.purchase_id == purchase_id)
    if (match := ilike_any(q, HoursPurchase.purchase_number, model.reason)) is not None:
        stmt = stmt.join(HoursPurchase, HoursPurchase.id == model.purchase_id).where(match)
    return stmt


class HoursApprovals:
    def __init__(self, session: Session, ctx: RequestContext, now: datetime):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid, self._now = session, ctx, ctx.tenant_id, now
        self._audit = AuditService(session)
        self.engine = HoursEngine(session, ctx.tenant_id, ctx.audit_actor(), now)

    # --- shared -----------------------------------------------------------------------------------------------
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
            policy_version=self.engine.eff.version_stamp[:64],
        )

    def _notify_requested(self, kind: str, entity_id: uuid.UUID, permission: str, summary: str) -> None:
        OutboxWriter(self._s).emit(
            topic=TOPIC,
            event_type="HoursApprovalRequested",
            key=str(entity_id),
            payload={
                "kind": kind,
                "entity_id": str(entity_id),
                "audience_permission": permission,
                "summary": summary,
                "requested_by": str(self._ctx.user_id) if self._ctx.user_id else None,
            },
            tenant_id=self._tid,
        )

    def _notify_decided(self, kind: str, entity_id: uuid.UUID, proposer: uuid.UUID | None, outcome: str) -> None:
        if proposer is None or proposer == self._ctx.user_id:
            return
        OutboxWriter(self._s).emit(
            topic=TOPIC,
            event_type="HoursApprovalDecided",
            key=str(entity_id),
            payload={"kind": kind, "entity_id": str(entity_id), "user_id": str(proposer), "outcome": outcome},
            tenant_id=self._tid,
        )

    def _second_person(self, proposer: uuid.UUID | None, action: str, entity: str, entity_id: uuid.UUID) -> None:
        if proposer is not None and proposer == self._ctx.user_id:
            sod_violation(self._tid, self._ctx.user_id, action, entity, entity_id)
            raise BusinessRuleViolation(
                "The person who proposed or requested this cannot approve it", code="SEGREGATION_OF_DUTIES"
            )

    def _reason_code(self, kind: ReasonKind, code_id: uuid.UUID | None) -> uuid.UUID | None:
        if code_id is None:
            if self.engine.policy.reason_code_required:
                raise BusinessRuleViolation("Choose a reason from the tenant's list", code="REASON_CODE_REQUIRED")
            return None
        row = self._s.get(HoursReasonCode, code_id)
        if row is None or row.kind is not kind:
            raise NotFound("Reason code not found", code="REASON_CODE_NOT_FOUND")
        if not row.is_active:
            raise BusinessRuleViolation("Reason code is deactivated", code="REASON_CODE_INACTIVE")
        return row.id

    def _customer(self, customer_id: uuid.UUID) -> Customer:
        c = self._s.get(Customer, customer_id)
        if c is None:
            raise NotFound("Customer not found")
        if not c.is_active:
            raise BusinessRuleViolation("Customer is deactivated", code="CUSTOMER_INACTIVE")
        return c

    def _require_enabled(self) -> None:
        if not self.engine.policy.enabled:
            raise BusinessRuleViolation("Customer hours are switched off for this tenant", code="HOURS_DISABLED")

    # --- reason lists -----------------------------------------------------------------------------------------
    def reason_code(self, code_id: uuid.UUID, lock: bool = False) -> HoursReasonCode:
        stmt = select(HoursReasonCode).where(HoursReasonCode.id == code_id)
        row = self._s.execute(stmt.with_for_update() if lock else stmt).scalar_one_or_none()
        if row is None:
            raise NotFound("Reason code not found")
        return row

    def create_reason_code(self, body: ReasonCodeIn) -> ReasonCodeDto:
        row = HoursReasonCode(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            kind=body.kind,
            code=body.code,
            label=body.label,
            created_by=self._ctx.user_id,
            created_at=self._now,
        )
        try:
            with self._s.begin_nested():
                self._s.add(row)
                self._s.flush()
        except IntegrityError as exc:
            raise Conflict("This reason code already exists", code="DUPLICATE_REASON_CODE") from exc
        dto = ReasonCodeDto.model_validate(row)
        self._record("hours.reason_code.created", "hours_reason_code", row.id, None, dto.model_dump(mode="json"))
        return dto

    def update_reason_code(self, code_id: uuid.UUID, body: ReasonCodeUpdateIn) -> ReasonCodeDto:
        row = self.reason_code(code_id, lock=True)
        check_version(row.version, body.version, "Reason code")
        before = ReasonCodeDto.model_validate(row).model_dump(mode="json")
        row.code, row.label = body.code, body.label
        flush_versioned(self._s, "Reason code", "DUPLICATE_REASON_CODE", "This reason code already exists")
        dto = ReasonCodeDto.model_validate(row)
        self._record("hours.reason_code.updated", "hours_reason_code", row.id, before, dto.model_dump(mode="json"))
        return dto

    def set_reason_code_active(
        self, code_id: uuid.UUID, active: bool, reason: str, version: int | None
    ) -> ReasonCodeDto:
        row = self.reason_code(code_id, lock=True)
        check_version(row.version, version, "Reason code")
        if active:
            mark_active(row, "Reason code")
        else:
            mark_inactive(row, self._ctx.user_id, reason, "Reason code")
        flush_versioned(self._s, "Reason code")
        dto = ReasonCodeDto.model_validate(row)
        verb = "reactivated" if active else "deactivated"
        self._record(
            f"hours.reason_code.{verb}", "hours_reason_code", row.id, None, dto.model_dump(mode="json"), reason
        )
        return dto

    # --- discounts & credit arrangements (proposals) ----------------------------------------------------------
    def _proposal[P: (CustomerDiscount, CreditArrangement)](self, model: type[P], row_id: uuid.UUID) -> P:
        return cast(P, self._lock_proposal(model, row_id))

    def _lock_proposal(self, model: type[Proposal], row_id: uuid.UUID) -> Proposal:
        row = self._s.execute(select(model).where(model.id == row_id).with_for_update()).scalar_one_or_none()
        if row is None:
            raise NotFound("Discount not found" if model is CustomerDiscount else "Credit arrangement not found")
        return cast(Proposal, row)

    def _overlaps(self, row: Proposal, start: date, end: date | None) -> bool:
        model = type(row)
        conds = [
            model.customer_id == row.customer_id,
            model.status == ProposalStatus.APPROVED,
            model.id != row.id,
            or_(model.effective_to.is_(None), model.effective_to >= start),
        ]
        if end is not None:
            conds.append(model.effective_from <= end)
        if isinstance(row, CreditArrangement):
            conds.append(CreditArrangement.currency == row.currency)
        return self._s.execute(select(model.id).where(*conds)).first() is not None

    def _approve(self, row: Proposal, entity: str, note: str | None) -> None:
        if self._overlaps(row, row.effective_from, row.effective_to):
            raise Conflict(
                f"Another approved {entity.replace('_', ' ')} for this customer overlaps these dates; revoke it first",
                code="OVERLAPPING_ARRANGEMENT",
            )
        row.status, row.decided_by, row.decided_at, row.decision_note = (
            ProposalStatus.APPROVED,
            self._ctx.user_id,
            self._now,
            note,
        )

    def propose_discount(self, body: DiscountIn) -> DiscountDto:
        self._require_enabled()
        self._customer(body.customer_id)
        if body.percent > self.engine.policy.max_discount_percent:
            raise BusinessRuleViolation(
                f"Discounts above {self.engine.policy.max_discount_percent}% are not allowed by tenant policy",
                code="DISCOUNT_ABOVE_MAXIMUM",
            )
        row = CustomerDiscount(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            customer_id=body.customer_id,
            percent=body.percent,
            effective_from=body.effective_from,
            effective_to=body.effective_to,
            reason=body.reason,
            reason_code_id=self._reason_code(ReasonKind.DISCOUNT, body.reason_code_id),
            status=ProposalStatus.PROPOSED,
            proposed_by=self._ctx.user_id,
            proposed_at=self._now,
        )
        self._s.add(row)
        self._s.flush()
        if not self.engine.policy.discount_requires_approval:
            self._approve(row, "discount", "Approval not required by tenant policy")
            self._s.flush()
        dto = DiscountDto.model_validate(row)
        self._record("hours.discount.proposed", "customer_discount", row.id, None, dto.model_dump(mode="json"))
        if row.status is ProposalStatus.PROPOSED:
            self._notify_requested(
                "DISCOUNT", row.id, "tenant.hours.discount_approve", f"Customer discount of {row.percent}% to approve"
            )
        return dto

    def update_discount(self, row_id: uuid.UUID, body: DiscountUpdateIn) -> DiscountDto:
        row = self._proposal(CustomerDiscount, row_id)
        self._editable(row, body.version)
        if body.percent > self.engine.policy.max_discount_percent:
            raise BusinessRuleViolation(
                f"Discounts above {self.engine.policy.max_discount_percent}% are not allowed by tenant policy",
                code="DISCOUNT_ABOVE_MAXIMUM",
            )
        before = DiscountDto.model_validate(row).model_dump(mode="json")
        row.percent, row.effective_from, row.effective_to, row.reason = (
            body.percent,
            body.effective_from,
            body.effective_to,
            body.reason,
        )
        row.reason_code_id = self._reason_code(ReasonKind.DISCOUNT, body.reason_code_id)
        flush_versioned(self._s, "Discount")
        dto = DiscountDto.model_validate(row)
        self._record("hours.discount.updated", "customer_discount", row.id, before, dto.model_dump(mode="json"))
        return dto

    def _editable(self, row: Proposal, version: int | None) -> None:
        check_version(row.version, version, "Proposal")
        if row.status is not ProposalStatus.PROPOSED:
            raise Conflict(f"Only a proposal can be changed (this one is {row.status.value})", code="NOT_PROPOSED")
        if row.proposed_by != self._ctx.user_id:
            raise PermissionDenied("Only the proposer can change or withdraw a proposal", code="NOT_PROPOSER")

    def decide_proposal(self, model: type[Proposal], row_id: uuid.UUID, body: DecisionIn) -> Proposal:
        row = self._lock_proposal(model, row_id)
        entity = "customer_discount" if model is CustomerDiscount else "credit_arrangement"
        if row.status is not ProposalStatus.PROPOSED:
            raise Conflict(f"Already {row.status.value}", code="ALREADY_DECIDED")
        self._second_person(row.proposed_by, "approve", entity, row.id)
        if body.approve:
            self._approve(row, entity, body.note)
        else:
            row.status, row.decided_by, row.decided_at, row.decision_note = (
                ProposalStatus.REJECTED,
                self._ctx.user_id,
                self._now,
                body.note,
            )
        flush_versioned(self._s, "Proposal")
        self._record(
            f"hours.{entity.split('_')[-1]}.{row.status.value.lower()}",
            entity,
            row.id,
            {"status": "PROPOSED"},
            {"status": row.status.value},
            body.note,
        )
        self._notify_decided(entity.upper(), row.id, row.proposed_by, row.status.value)
        return row

    def withdraw_proposal(self, model: type[Proposal], row_id: uuid.UUID, reason: str) -> Proposal:
        row = self._lock_proposal(model, row_id)
        self._editable(row, None)
        row.status, row.decided_at, row.decision_note = ProposalStatus.WITHDRAWN, self._now, reason
        flush_versioned(self._s, "Proposal")
        entity = "customer_discount" if model is CustomerDiscount else "credit_arrangement"
        self._record(
            f"hours.{entity.split('_')[-1]}.withdrawn",
            entity,
            row.id,
            {"status": "PROPOSED"},
            {"status": "WITHDRAWN"},
            reason,
        )
        return row

    def revoke_proposal(self, model: type[Proposal], row_id: uuid.UUID, reason: str) -> Proposal:
        row = self._lock_proposal(model, row_id)
        if row.status is not ProposalStatus.APPROVED:
            raise Conflict("Only an approved arrangement can be revoked", code="NOT_APPROVED")
        row.status, row.revoked_by, row.revoked_at, row.revoke_reason = (
            ProposalStatus.REVOKED,
            self._ctx.user_id,
            self._now,
            reason,
        )
        flush_versioned(self._s, "Proposal")
        entity = "customer_discount" if model is CustomerDiscount else "credit_arrangement"
        self._record(
            f"hours.{entity.split('_')[-1]}.revoked",
            entity,
            row.id,
            {"status": "APPROVED"},
            {"status": "REVOKED"},
            reason,
        )
        return row

    def propose_credit(self, body: CreditArrangementIn) -> CreditArrangementDto:
        self._require_enabled()
        if not self.engine.policy.credit_allowed:
            raise BusinessRuleViolation("Credit is not allowed by tenant policy", code="CREDIT_NOT_ALLOWED")
        self._customer(body.customer_id)
        row = CreditArrangement(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            customer_id=body.customer_id,
            limit_amount=body.limit_amount,
            currency=currency_or_default(self._s, self._tid, body.currency),
            effective_from=body.effective_from,
            effective_to=body.effective_to,
            terms=body.terms,
            reason=body.reason,
            reason_code_id=self._reason_code(ReasonKind.CREDIT, body.reason_code_id),
            status=ProposalStatus.PROPOSED,
            proposed_by=self._ctx.user_id,
            proposed_at=self._now,
        )
        self._s.add(row)
        self._s.flush()
        dto = CreditArrangementDto.model_validate(row)
        self._record("hours.arrangement.proposed", "credit_arrangement", row.id, None, dto.model_dump(mode="json"))
        self._notify_requested(
            "CREDIT",
            row.id,
            "tenant.hours.credit_approve",
            f"Credit arrangement of {row.currency} {row.limit_amount} to approve",
        )
        return dto

    def update_credit(self, row_id: uuid.UUID, body: CreditArrangementUpdateIn) -> CreditArrangementDto:
        row = self._proposal(CreditArrangement, row_id)
        self._editable(row, body.version)
        before = CreditArrangementDto.model_validate(row).model_dump(mode="json")
        row.limit_amount, row.effective_from, row.effective_to = (
            body.limit_amount,
            body.effective_from,
            body.effective_to,
        )
        row.terms, row.reason = body.terms, body.reason
        row.reason_code_id = self._reason_code(ReasonKind.CREDIT, body.reason_code_id)
        flush_versioned(self._s, "Credit arrangement")
        dto = CreditArrangementDto.model_validate(row)
        self._record("hours.arrangement.updated", "credit_arrangement", row.id, before, dto.model_dump(mode="json"))
        return dto

    def exposure(self, customer_id: uuid.UUID, currency: str | None) -> CreditExposureDto:
        if self._s.get(Customer, customer_id) is None:
            raise NotFound("Customer not found")
        currency = currency_or_default(self._s, self._tid, currency)
        arrangement = self.engine.arrangement(customer_id, currency)
        exposure = self.engine.credit_exposure(customer_id, currency)
        return CreditExposureDto(
            customer_id=customer_id,
            currency=currency,
            arrangement_id=arrangement.id if arrangement else None,
            limit_amount=arrangement.limit_amount if arrangement else None,
            exposure=exposure,
            available=max(ZERO, arrangement.limit_amount - exposure) if arrangement else None,
        )

    # --- transfers --------------------------------------------------------------------------------------------
    def transfer(self, row_id: uuid.UUID, lock: bool = False) -> HoursTransfer:
        stmt = select(HoursTransfer).where(HoursTransfer.id == row_id)
        row = self._s.execute(stmt.with_for_update() if lock else stmt).scalar_one_or_none()
        if row is None:
            raise NotFound("Hours transfer not found")
        return row

    def request_transfer(self, body: TransferIn) -> TransferDto:
        if body.client_id is not None:
            existing = self._s.execute(
                select(HoursTransfer).where(HoursTransfer.client_id == body.client_id)
            ).scalar_one_or_none()
            if existing is not None:
                return TransferDto.model_validate(existing)
        self._require_enabled()
        purchase = self.engine.lock_purchase(body.purchase_id)
        if purchase.cancelled_at is not None:
            raise BusinessRuleViolation("The purchase is cancelled", code="PURCHASE_CANCELLED")
        source = body.from_machine_id or purchase.machine_id
        target = self._s.get(Machine, body.to_machine_id)
        if target is None:
            raise NotFound("Machine not found")
        if target.status is not MachineStatus.ACTIVE:
            raise BusinessRuleViolation("The receiving machine is not in service", code="MACHINE_INACTIVE")
        if source == target.id:
            raise BusinessRuleViolation("Choose a different machine", code="SAME_MACHINE")
        self._check_remaining(purchase, source, body.hours)
        row = HoursTransfer(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            client_id=body.client_id,
            purchase_id=purchase.id,
            from_machine_id=source,
            to_machine_id=target.id,
            hours=body.hours,
            reason=body.reason,
            reason_code_id=self._reason_code(ReasonKind.TRANSFER, body.reason_code_id),
            status=RequestStatus.PENDING,
            requested_by=self._ctx.user_id,
            requested_at=self._now,
        )
        self._s.add(row)
        self._s.flush()
        self._record(
            "hours.transfer.requested",
            "hours_transfer",
            row.id,
            None,
            TransferDto.model_validate(row).model_dump(mode="json"),
            body.reason,
        )
        if self.engine.policy.transfer_requires_approval:
            self._notify_requested(
                "TRANSFER",
                row.id,
                "tenant.hours.transfer_approve",
                f"{row.hours} h of {purchase.purchase_number} to move to another machine",
            )
        else:
            self._apply_transfer(row, purchase, "Approval not required by tenant policy")
        return TransferDto.model_validate(row)

    def _check_remaining(self, purchase: HoursPurchase, machine_id: uuid.UUID, hours: Any) -> None:
        left = purchase_totals(self._s, purchase).remaining_on(machine_id)
        if hours > left:
            raise BusinessRuleViolation(
                f"Only {left} activated hours of {purchase.purchase_number} remain on that machine",
                code="EXCEEDS_REMAINING_HOURS",
            )

    def _apply_transfer(self, row: HoursTransfer, purchase: HoursPurchase, note: str | None) -> None:
        self._check_remaining(purchase, row.from_machine_id, row.hours)
        row.status, row.decided_by, row.decided_at, row.decision_note = (
            RequestStatus.APPROVED,
            self._ctx.user_id,
            self._now,
            note,
        )
        self._s.flush()
        ledger = LedgerWriter(self._s, self._tid, self._ctx.user_id, self._now)
        stamp = self.engine.eff.version_stamp
        ledger.add(
            purchase,
            row.from_machine_id,
            T.TRANSFER_OUT,
            row.hours,
            transfer_id=row.id,
            reason=row.reason,
            policy_version=stamp,
        )
        ledger.add(
            purchase,
            row.to_machine_id,
            T.TRANSFER_IN,
            row.hours,
            transfer_id=row.id,
            reason=row.reason,
            policy_version=stamp,
        )
        self._record(
            "hours.transfer.applied",
            "hours_transfer",
            row.id,
            {"status": "PENDING"},
            {
                "status": "APPROVED",
                "purchase_number": purchase.purchase_number,
                "from_machine_id": str(row.from_machine_id),
                "to_machine_id": str(row.to_machine_id),
                "hours": str(row.hours),
            },
            note,
        )
        self.engine.cover_overruns(purchase.customer_id, row.to_machine_id)

    def decide_transfer(self, row_id: uuid.UUID, body: DecisionIn) -> TransferDto:
        row = self.transfer(row_id, lock=True)
        if row.status is not RequestStatus.PENDING:
            raise Conflict(f"Transfer already {row.status.value}", code="ALREADY_DECIDED")
        self._second_person(row.requested_by, "approve", "hours_transfer", row.id)
        purchase = self.engine.lock_purchase(row.purchase_id)
        if body.approve:
            if purchase.cancelled_at is not None:
                raise BusinessRuleViolation("The purchase is cancelled", code="PURCHASE_CANCELLED")
            self._apply_transfer(row, purchase, body.note)
        else:
            row.status, row.decided_by, row.decided_at, row.decision_note = (
                RequestStatus.REJECTED,
                self._ctx.user_id,
                self._now,
                body.note,
            )
            self._s.flush()
            self._record(
                "hours.transfer.rejected",
                "hours_transfer",
                row.id,
                {"status": "PENDING"},
                {"status": "REJECTED"},
                body.note,
            )
        self._notify_decided("TRANSFER", row.id, row.requested_by, row.status.value)
        return TransferDto.model_validate(row)

    def withdraw_transfer(self, row_id: uuid.UUID, reason: str) -> TransferDto:
        row = self.transfer(row_id, lock=True)
        if row.status is not RequestStatus.PENDING:
            raise Conflict(f"Transfer already {row.status.value}", code="ALREADY_DECIDED")
        if row.requested_by != self._ctx.user_id:
            raise PermissionDenied("Only the requester can withdraw a request", code="NOT_REQUESTER")
        row.status, row.decided_at, row.decision_note = RequestStatus.WITHDRAWN, self._now, reason
        self._s.flush()
        self._record(
            "hours.transfer.withdrawn", "hours_transfer", row.id, {"status": "PENDING"}, {"status": "WITHDRAWN"}, reason
        )
        return TransferDto.model_validate(row)

    # --- cancellations ----------------------------------------------------------------------------------------
    def cancellation(self, row_id: uuid.UUID, lock: bool = False) -> HoursCancellation:
        stmt = select(HoursCancellation).where(HoursCancellation.id == row_id)
        row = self._s.execute(stmt.with_for_update() if lock else stmt).scalar_one_or_none()
        if row is None:
            raise NotFound("Cancellation not found")
        return row

    def _check_cancellable(self, purchase: HoursPurchase) -> None:
        if purchase.cancelled_at is not None:
            raise Conflict("The purchase is already cancelled", code="PURCHASE_CANCELLED")
        consumed = purchase_totals(self._s, purchase).total(T.CONSUMED)
        if consumed > 0 and not self.engine.policy.cancellation_after_consumption_allowed:
            raise BusinessRuleViolation(
                "Hours of this purchase were already used; tenant policy allows cancelling only unused purchases",
                code="PURCHASE_HAS_CONSUMPTION",
            )

    def request_cancellation(self, purchase_id: uuid.UUID, body: CancellationIn) -> CancellationDto:
        purchase = self.engine.lock_purchase(purchase_id)
        self._check_cancellable(purchase)
        row = HoursCancellation(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            purchase_id=purchase.id,
            reason=body.reason,
            reason_code_id=self._reason_code(ReasonKind.CANCELLATION, body.reason_code_id),
            status=RequestStatus.PENDING,
            requested_by=self._ctx.user_id,
            requested_at=self._now,
        )
        try:
            with self._s.begin_nested():
                self._s.add(row)
                self._s.flush()
        except IntegrityError as exc:
            raise Conflict("A cancellation is already pending for this purchase", code="CANCELLATION_PENDING") from exc
        self._record(
            "hours.cancellation.requested",
            "hours_cancellation",
            row.id,
            None,
            {"purchase_number": purchase.purchase_number},
            body.reason,
        )
        if self.engine.policy.cancellation_requires_approval:
            self._notify_requested(
                "CANCELLATION",
                row.id,
                "tenant.hours.cancel_approve",
                f"Cancellation of {purchase.purchase_number} to approve",
            )
        else:
            self._apply_cancellation(row, purchase, "Approval not required by tenant policy")
        return CancellationDto.model_validate(row)

    def _apply_cancellation(self, row: HoursCancellation, purchase: HoursPurchase, note: str | None) -> None:
        self._check_cancellable(purchase)
        totals = purchase_totals(self._s, purchase)
        row.status, row.decided_by, row.decided_at, row.decision_note = (
            RequestStatus.APPROVED,
            self._ctx.user_id,
            self._now,
            note,
        )
        self._s.flush()
        ledger = LedgerWriter(self._s, self._tid, self._ctx.user_id, self._now)
        reversed_total = ZERO
        for machine_id, m in sorted(totals.machines.items(), key=lambda kv: str(kv[0])):
            if m.remaining > 0:
                ledger.add(
                    purchase,
                    machine_id,
                    T.REVERSAL,
                    m.remaining,
                    cancellation_id=row.id,
                    reason=row.reason,
                    policy_version=self.engine.eff.version_stamp,
                )
                reversed_total += m.remaining
        released = ZERO
        if totals.total(T.CONSUMED) <= 0:  # nothing used: the money goes back to the customer's credit
            for alloc in self._s.execute(
                select(HoursPaymentAllocation).where(
                    HoursPaymentAllocation.purchase_id == purchase.id, HoursPaymentAllocation.released_at.is_(None)
                )
            ).scalars():
                alloc.released_at, alloc.release_reason = self._now, "Purchase cancelled; amount returned to credit"
                released += alloc.amount
        for pending in self._s.execute(
            select(HoursTransfer)
            .where(HoursTransfer.purchase_id == purchase.id, HoursTransfer.status == RequestStatus.PENDING)
            .with_for_update()
        ).scalars():
            pending.status, pending.decided_by, pending.decided_at, pending.decision_note = (
                RequestStatus.REJECTED,
                self._ctx.user_id,
                self._now,
                "Purchase cancelled",
            )
        purchase.cancelled_at, purchase.cancelled_by, purchase.cancellation_id = self._now, self._ctx.user_id, row.id
        self._s.flush()
        self._record(
            "hours.purchase.cancelled",
            "hours_purchase",
            purchase.id,
            None,
            {
                "purchase_number": purchase.purchase_number,
                "reversed_hours": str(reversed_total),
                "allocations_released": str(released),
                "cancellation_id": str(row.id),
            },
            row.reason,
        )

    def decide_cancellation(self, row_id: uuid.UUID, body: DecisionIn) -> CancellationDto:
        row = self.cancellation(row_id, lock=True)
        if row.status is not RequestStatus.PENDING:
            raise Conflict(f"Cancellation already {row.status.value}", code="ALREADY_DECIDED")
        self._second_person(row.requested_by, "approve", "hours_cancellation", row.id)
        purchase = self.engine.lock_purchase(row.purchase_id)
        if body.approve:
            self._apply_cancellation(row, purchase, body.note)
        else:
            row.status, row.decided_by, row.decided_at, row.decision_note = (
                RequestStatus.REJECTED,
                self._ctx.user_id,
                self._now,
                body.note,
            )
            self._s.flush()
            self._record(
                "hours.cancellation.rejected",
                "hours_cancellation",
                row.id,
                {"status": "PENDING"},
                {"status": "REJECTED"},
                body.note,
            )
        self._notify_decided("CANCELLATION", row.id, row.requested_by, row.status.value)
        return CancellationDto.model_validate(row)

    def withdraw_cancellation(self, row_id: uuid.UUID, reason: str) -> CancellationDto:
        row = self.cancellation(row_id, lock=True)
        if row.status is not RequestStatus.PENDING:
            raise Conflict(f"Cancellation already {row.status.value}", code="ALREADY_DECIDED")
        if row.requested_by != self._ctx.user_id:
            raise PermissionDenied("Only the requester can withdraw a request", code="NOT_REQUESTER")
        row.status, row.decided_at, row.decision_note = RequestStatus.WITHDRAWN, self._now, reason
        self._s.flush()
        self._record(
            "hours.cancellation.withdrawn",
            "hours_cancellation",
            row.id,
            {"status": "PENDING"},
            {"status": "WITHDRAWN"},
            reason,
        )
        return CancellationDto.model_validate(row)
