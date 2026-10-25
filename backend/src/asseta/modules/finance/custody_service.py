"""Cash custody chain controls (accountability design C): field-to-field transfers and their acknowledgement, float
acknowledgement, variances (resolution and write-off), approved retentions, custody adjustments, the tenant's reason
lists and the custodian picker. Every rule switch is the tenant's CASH_CUSTODY policy; approvals are permissions;
the proposer/recorder is never the approver (segregation of duties)."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound, PermissionDenied
from asseta.core.lifecycle import LifecycleChangeIn, check_version, flush_versioned, mark_active, mark_inactive
from asseta.core.outbox import OutboxWriter
from asseta.core.search import ilike_any
from asseta.modules.accountability.security_events import permission_refused
from asseta.modules.expenses.models import Expense
from asseta.modules.finance.cash_service import custody_entry_dto
from asseta.modules.finance.common import ZERO, currency_or_default, insert, resolve_staff
from asseta.modules.finance.custody_dto import (
    CashAcknowledgementIn,
    CashReasonDto,
    CashReasonIn,
    CashReasonUpdateIn,
    CashRetentionDto,
    CashRetentionIn,
    CashTransferDto,
    CashTransferIn,
    CashVarianceDto,
    CustodianDto,
    CustodyAdjustmentDto,
    CustodyAdjustmentIn,
    DecisionIn,
    VarianceResolutionIn,
    WriteOffProposalIn,
)
from asseta.modules.finance.custody_models import (
    AcknowledgementMethod,
    CashDecisionStatus,
    CashFloatAcknowledgement,
    CashReason,
    CashReasonKind,
    CashRetention,
    CashTransfer,
    CashTransferStatus,
    CashVariance,
    CustodyAdjustment,
    VarianceOutcome,
    VarianceSource,
    VarianceStatus,
)
from asseta.modules.finance.custody_rules import (
    RECORDER_PERMISSION,
    TOPIC,
    cash_policy,
    check_reason,
    may_record_for_others,
    open_variance,
    own_staff,
    refuse_sod,
    resolve_recorded_custodian,
)
from asseta.modules.finance.dto import CashCustodyEntryDto
from asseta.modules.finance.models import CashHandover, CustodyEntryType, CustomerPayment, SupervisorCashCustody
from asseta.modules.fleet.models import StaffMember
from asseta.modules.identity.principal import RequestContext
from asseta.modules.policy.schemas import CashCustodyPolicy
from asseta.modules.policy.service import EffectivePolicy

WRITEOFF_PERMISSION = "tenant.finance.writeoff"
FINANCE_READ_PERMISSION = "tenant.finance.read"
REVERSIBLE: dict[str, Any] = {
    "customer_payment": CustomerPayment,
    "cash_handover": CashHandover,
    "cash_transfer": CashTransfer,
    "supervisor_cash_custody": SupervisorCashCustody,
    "expense": Expense,
    "custody_adjustment": CustodyAdjustment,
}


def custodian_dto(s: StaffMember) -> CustodianDto:
    return CustodianDto(
        staff_member_id=s.id,
        full_name=s.full_name,
        kind=s.kind,
        employee_code=s.employee_code,
        is_active=s.is_active,
        has_login=s.keycloak_subject is not None,
    )


class CashCustodyControls:
    def __init__(self, session: Session, ctx: RequestContext, now: datetime):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid, self._now = session, ctx, ctx.tenant_id, now
        self._audit = AuditService(session)

    def _policy(self) -> EffectivePolicy[CashCustodyPolicy]:
        return cash_policy(self._s, self._tid, self._now)

    def _emit(self, event_type: str, key: object, payload: dict[str, Any]) -> None:
        OutboxWriter(self._s).emit(
            topic=TOPIC, event_type=event_type, key=str(key), payload=payload, tenant_id=self._tid
        )

    def _record(self, action: str, entity_type: str, entity_id: uuid.UUID, **kw: Any) -> None:
        self._audit.record(
            actor=self._ctx.audit_actor(kw.pop("source", "api")),
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            tenant_id=self._tid,
            **kw,
        )

    # --- custodians -----------------------------------------------------------------------------------------
    def custodians(self, q: str | None, include_inactive: bool) -> Select[StaffMember]:
        stmt = select(StaffMember).order_by(StaffMember.full_name, StaffMember.id)
        if not include_inactive:
            stmt = stmt.where(StaffMember.is_active.is_(True))
        if (cond := ilike_any(q, StaffMember.full_name, StaffMember.employee_code)) is not None:
            stmt = stmt.where(cond)
        return stmt

    # --- exact records (deep links from notifications and dashboards) -------------------------------------
    def _sees_all(self) -> bool:
        return FINANCE_READ_PERMISSION in self._ctx.permissions or may_record_for_others(
            self._ctx, self._policy().policy
        )

    def _party(self, staff_ids: tuple[uuid.UUID | None, ...], recorders: tuple[uuid.UUID | None, ...]) -> bool:
        """Field readers open a record only when they take part in it (custodian or the person who recorded it)."""
        if self._sees_all() or self._ctx.user_id in recorders:
            return True
        own = own_staff(self._s, self._ctx)
        return own is not None and own.id in staff_ids

    def handover(self, handover_id: uuid.UUID) -> CashHandover:
        row = self._s.get(CashHandover, handover_id)
        if row is None or not self._party((row.staff_member_id,), (row.recorded_by,)):
            raise NotFound("Remittance not found", code="HANDOVER_NOT_FOUND")
        return row

    def float_entry(self, entry_id: uuid.UUID) -> SupervisorCashCustody:
        row = self._s.get(SupervisorCashCustody, entry_id)
        if (
            row is None
            or row.entry_type is not CustodyEntryType.FLOAT_ISSUED
            or not self._party((row.staff_member_id,), (row.created_by,))
        ):
            raise NotFound("Float not found", code="FLOAT_NOT_FOUND")
        return row

    def retention(self, retention_id: uuid.UUID) -> CashRetention:
        row = self._s.get(CashRetention, retention_id)
        if row is None or not self._party((row.staff_member_id,), (row.created_by,)):
            raise NotFound("Retention not found", code="RETENTION_NOT_FOUND")
        return row

    def adjustment(self, adjustment_id: uuid.UUID) -> CustodyAdjustment:
        row = self._s.get(CustodyAdjustment, adjustment_id)
        if row is None:
            raise NotFound("Adjustment not found", code="ADJUSTMENT_NOT_FOUND")
        return row

    # --- transfers ------------------------------------------------------------------------------------------
    def transfer_dto(self, t: CashTransfer) -> CashTransferDto:
        dto = CashTransferDto.model_validate(t)
        dto.variance_id = self._s.execute(
            select(CashVariance.id).where(
                CashVariance.source_type == VarianceSource.TRANSFER, CashVariance.source_id == t.id
            )
        ).scalar_one_or_none()
        return dto

    def list_transfers(self, status: CashTransferStatus | None, staff_id: uuid.UUID | None) -> Select[CashTransfer]:
        """Office readers and (when the tenant allows recording for others) recorders see every transfer; other
        recorders see the transfers they recorded or take part in."""
        stmt = select(CashTransfer).order_by(CashTransfer.transferred_at.desc(), CashTransfer.id)
        if FINANCE_READ_PERMISSION not in self._ctx.permissions and not may_record_for_others(
            self._ctx, self._policy().policy
        ):
            own = own_staff(self._s, self._ctx)
            parties = [CashTransfer.recorded_by == self._ctx.user_id]
            if own is not None:
                parties += [CashTransfer.from_staff_id == own.id, CashTransfer.to_staff_id == own.id]
            stmt = stmt.where(or_(*parties))
        if status:
            stmt = stmt.where(CashTransfer.status == status)
        if staff_id:
            stmt = stmt.where(or_(CashTransfer.from_staff_id == staff_id, CashTransfer.to_staff_id == staff_id))
        return stmt

    def get_transfer(self, transfer_id: uuid.UUID, lock: bool = False) -> CashTransfer:
        stmt = select(CashTransfer).where(CashTransfer.id == transfer_id)
        row = self._s.execute(stmt.with_for_update() if lock else stmt).scalar_one_or_none()
        if row is None:
            raise NotFound("Transfer not found", code="TRANSFER_NOT_FOUND")
        return row

    def record_transfer(self, body: CashTransferIn, source: str = "API") -> CashTransferDto:
        """A field-to-field transfer. The caller records it as a party (sender or receiver) or, when the tenant
        allows, on the custodians' behalf. It never counts as company receipt."""
        if body.client_id is not None:
            existing = self._s.execute(
                select(CashTransfer).where(CashTransfer.client_id == body.client_id)
            ).scalar_one_or_none()
            if existing is not None:
                return self.transfer_dto(existing)  # offline retry: exactly one effect
        eff = self._policy()
        policy = eff.policy
        own = own_staff(self._s, self._ctx)
        if body.from_staff_id is None:
            sender = resolve_staff(self._s, self._ctx, None, require_active=False)
        else:
            sender = resolve_staff(self._s, self._ctx, body.from_staff_id, require_active=False)
        receiver = resolve_staff(self._s, self._ctx, body.to_staff_id)
        if sender.id == receiver.id:
            raise BusinessRuleViolation("Sender and receiver must differ", code="TRANSFER_SAME_CUSTODIAN")
        is_party = own is not None and own.id in (sender.id, receiver.id)
        if not is_party and not may_record_for_others(self._ctx, policy):
            raise PermissionDenied("You may only record transfers you take part in", code="NOT_CUSTODIAN")
        recorder_is_receiver = own is not None and own.id == receiver.id
        status, method, received = CashTransferStatus.PENDING_ACKNOWLEDGEMENT, None, None
        if not policy.transfer_ack_required:
            status, method = CashTransferStatus.ACKNOWLEDGED, AcknowledgementMethod.NOT_REQUIRED
        elif recorder_is_receiver and policy.recorder_receiver_counts_as_ack:
            status, method = CashTransferStatus.ACKNOWLEDGED, AcknowledgementMethod.RECORDER_IS_RECEIVER
        if status is CashTransferStatus.ACKNOWLEDGED:
            received = body.amount_received if body.amount_received is not None else body.amount
            if body.amount_received is not None and not recorder_is_receiver:
                raise BusinessRuleViolation(
                    "Only the receiver states the amount received", code="AMOUNT_RECEIVED_NOT_ALLOWED"
                )
        elif body.amount_received is not None:
            raise BusinessRuleViolation(
                "The receiver acknowledges the amount received separately", code="AMOUNT_RECEIVED_NOT_ALLOWED"
            )
        row = CashTransfer(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            client_id=body.client_id,
            from_staff_id=sender.id,
            to_staff_id=receiver.id,
            amount_declared=body.amount,
            currency=currency_or_default(self._s, self._tid, body.currency),
            transferred_at=body.transferred_at,
            note=body.note,
            status=status,
            source=source,
            recorded_by=self._ctx.user_id,
            recorded_at=self._now,
            policy_version=eff.version_stamp[:80],
            amount_received=received,
            ack_method=method,
            acknowledged_by=self._ctx.user_id if method else None,
            acknowledged_at=self._now if method else None,
        )
        insert(self._s, row, "DUPLICATE_TRANSFER", "Transfer already recorded")
        self._record(
            "finance.cash_transfer.recorded",
            "cash_transfer",
            row.id,
            source=source.lower(),
            after={
                "from_staff_id": str(sender.id),
                "to_staff_id": str(receiver.id),
                "amount_declared": str(row.amount_declared),
                "currency": row.currency,
                "status": row.status.value,
                "ack_method": method.value if method else None,
                "amount_received": str(received) if received is not None else None,
            },
            policy_version=eff.version_stamp[:64],
        )
        payload = {
            "transfer_id": str(row.id),
            "from_staff_id": str(sender.id),
            "to_staff_id": str(receiver.id),
            "amount": str(row.amount_declared),
            "currency": row.currency,
            "status": row.status.value,
        }
        self._emit("CashTransferRecorded", receiver.id, payload)
        if received is not None:
            self._variance_for_transfer(row)
        return self.transfer_dto(row)

    def _variance_for_transfer(self, t: CashTransfer) -> None:
        open_variance(
            self._s,
            self._ctx,
            self._now,
            source_type=VarianceSource.TRANSFER,
            source_id=t.id,
            accountable_staff_id=t.from_staff_id,
            counterparty_staff_id=t.to_staff_id,
            currency=t.currency,
            declared=t.amount_declared,
            received=t.amount_received if t.amount_received is not None else Decimal(0),
        )

    def _ack_method(
        self,
        receiver_id: uuid.UUID,
        sender_id: uuid.UUID | None,
        originator: uuid.UUID | None,
        entity: str,
        eid: uuid.UUID,
    ) -> AcknowledgementMethod:
        """Who may acknowledge: the receiving custodian, or (tenant policy / office cash permission) another recorder
        on their behalf — never the sender, and never whoever recorded/issued the movement for someone else."""
        own = own_staff(self._s, self._ctx)
        if own is not None and sender_id is not None and own.id == sender_id:
            refuse_sod(self._ctx, "acknowledge", entity, eid, "The sender cannot acknowledge their own transfer")
        if own is not None and own.id == receiver_id:
            return AcknowledgementMethod.RECEIVER
        if not may_record_for_others(self._ctx, self._policy().policy):
            raise PermissionDenied("Only the receiving custodian may acknowledge", code="NOT_RECEIVER")
        if originator == self._ctx.user_id:
            refuse_sod(
                self._ctx,
                "acknowledge",
                entity,
                eid,
                "Whoever recorded it cannot also confirm receipt for someone else",
            )
        return AcknowledgementMethod.ON_BEHALF

    def acknowledge_transfer(
        self, transfer_id: uuid.UUID, body: CashAcknowledgementIn, source: str = "API"
    ) -> CashTransferDto:
        row = self.get_transfer(transfer_id, lock=True)
        if row.status is not CashTransferStatus.PENDING_ACKNOWLEDGEMENT:
            raise Conflict(f"Transfer already {row.status.value}", code="TRANSFER_ALREADY_DECIDED")
        method = self._ack_method(row.to_staff_id, row.from_staff_id, row.recorded_by, "cash_transfer", row.id)
        row.status = CashTransferStatus.ACKNOWLEDGED if body.acknowledged else CashTransferStatus.DISPUTED
        if body.acknowledged:
            row.amount_received = body.amount_received if body.amount_received is not None else row.amount_declared
        row.ack_method, row.acknowledged_by, row.acknowledged_at = method, self._ctx.user_id, self._now
        row.ack_note = body.note
        self._s.flush()
        self._record(
            f"finance.cash_transfer.{'acknowledged' if body.acknowledged else 'disputed'}",
            "cash_transfer",
            row.id,
            source=source.lower(),
            before={"status": CashTransferStatus.PENDING_ACKNOWLEDGEMENT.value},
            after={
                "status": row.status.value,
                "amount_received": str(row.amount_received) if row.amount_received is not None else None,
                "ack_method": method.value,
            },
            reason=body.note,
        )
        self._emit(
            "CashTransferAcknowledged" if body.acknowledged else "CashTransferDisputed",
            row.from_staff_id,
            {"transfer_id": str(row.id), "status": row.status.value, "currency": row.currency},
        )
        self._variance_for_transfer(row)
        return self.transfer_dto(row)

    # --- floats ---------------------------------------------------------------------------------------------
    def list_floats(self, staff_id: uuid.UUID | None, awaiting: bool | None) -> Select[SupervisorCashCustody]:
        stmt = select(SupervisorCashCustody).order_by(SupervisorCashCustody.occurred_at.desc())
        if FINANCE_READ_PERMISSION not in self._ctx.permissions and not may_record_for_others(
            self._ctx, self._policy().policy
        ):
            own = resolve_staff(self._s, self._ctx, None, require_active=False)
            stmt = stmt.where(SupervisorCashCustody.staff_member_id == own.id)
        if staff_id:
            stmt = stmt.where(SupervisorCashCustody.staff_member_id == staff_id)
        if awaiting is not None:
            pending = SupervisorCashCustody.ack_required.is_(True) & ~SupervisorCashCustody.id.in_(
                select(CashFloatAcknowledgement.custody_entry_id)
            )
            stmt = stmt.where(pending if awaiting else ~pending)
        return stmt

    def float_ack(self, entry_id: uuid.UUID) -> CashFloatAcknowledgement | None:
        return self._s.execute(
            select(CashFloatAcknowledgement).where(CashFloatAcknowledgement.custody_entry_id == entry_id)
        ).scalar_one_or_none()

    def acknowledge_float(
        self, entry_id: uuid.UUID, body: CashAcknowledgementIn, client_id: uuid.UUID | None = None, source: str = "API"
    ) -> CashCustodyEntryDto:
        # The custody ledger is insert-only (no row locks); the unique acknowledgement per float serialises races.
        entry = self._s.get(SupervisorCashCustody, entry_id)
        if entry is None or entry.entry_type is not CustodyEntryType.FLOAT_ISSUED:
            raise NotFound("Float not found", code="FLOAT_NOT_FOUND")
        if not entry.ack_required:
            raise BusinessRuleViolation("This float does not need acknowledgement", code="FLOAT_ACK_NOT_REQUIRED")
        if (existing := self.float_ack(entry.id)) is not None:
            if client_id is not None and existing.client_id == client_id:
                return custody_entry_dto(entry, existing)
            raise Conflict("Float already acknowledged or disputed", code="FLOAT_ALREADY_ACKNOWLEDGED")
        method = self._ack_method(entry.staff_member_id, None, entry.created_by, "supervisor_cash_custody", entry.id)
        received = (
            (body.amount_received if body.amount_received is not None else entry.amount) if body.acknowledged else ZERO
        )
        ack = CashFloatAcknowledgement(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            client_id=client_id,
            custody_entry_id=entry.id,
            staff_member_id=entry.staff_member_id,
            disputed=not body.acknowledged,
            amount_received=received,
            method=method,
            note=body.note,
            source=source,
            acknowledged_by=self._ctx.user_id,
            acknowledged_at=self._now,
        )
        insert(self._s, ack, "FLOAT_ALREADY_ACKNOWLEDGED", "Float already acknowledged or disputed")
        self._record(
            f"finance.cash_float.{'acknowledged' if body.acknowledged else 'disputed'}",
            "supervisor_cash_custody",
            entry.id,
            source=source.lower(),
            after={"amount_received": str(received), "method": method.value, "disputed": not body.acknowledged},
            reason=body.note,
        )
        open_variance(
            self._s,
            self._ctx,
            self._now,
            source_type=VarianceSource.FLOAT,
            source_id=entry.id,
            accountable_staff_id=None,  # a float shortfall sits with the office that issued it
            counterparty_staff_id=entry.staff_member_id,
            currency=entry.currency,
            declared=entry.amount,
            received=received,
        )
        return custody_entry_dto(entry, ack)

    # --- variances ------------------------------------------------------------------------------------------
    def list_variances(
        self, status: VarianceStatus | None, staff_id: uuid.UUID | None, source_type: VarianceSource | None
    ) -> Select[CashVariance]:
        stmt = select(CashVariance).order_by(CashVariance.opened_at.desc(), CashVariance.id)
        if status:
            stmt = stmt.where(CashVariance.status == status)
        if staff_id:
            stmt = stmt.where(
                or_(CashVariance.staff_member_id == staff_id, CashVariance.counterparty_staff_id == staff_id)
            )
        if source_type:
            stmt = stmt.where(CashVariance.source_type == source_type)
        return stmt

    def variance(self, variance_id: uuid.UUID, lock: bool = False) -> CashVariance:
        stmt = select(CashVariance).where(CashVariance.id == variance_id)
        row = self._s.execute(stmt.with_for_update() if lock else stmt).scalar_one_or_none()
        if row is None:
            raise NotFound("Variance not found", code="VARIANCE_NOT_FOUND")
        return row

    def _not_own_variance(self, v: CashVariance, action: str) -> None:
        own = own_staff(self._s, self._ctx)
        if own is not None and own.id == v.staff_member_id:
            refuse_sod(self._ctx, action, "cash_variance", v.id, "You cannot decide a variance you are accountable for")

    def _resolve(self, v: CashVariance, outcome: VarianceOutcome, note: str, reason_id: uuid.UUID | None) -> None:
        before = v.status.value
        v.status, v.outcome = VarianceStatus.RESOLVED, outcome
        v.resolved_by, v.resolved_at, v.resolution_note = self._ctx.user_id, self._now, note
        if reason_id is not None:
            v.reason_id = reason_id
        self._s.flush()
        self._record(
            f"finance.cash_variance.{outcome.value.lower()}",
            "cash_variance",
            v.id,
            before={"status": before},
            after={"status": v.status.value, "outcome": outcome.value, "amount": str(v.amount)},
            reason=note,
        )
        self._emit(
            "CashVarianceResolved", v.staff_member_id or v.id, {"variance_id": str(v.id), "outcome": outcome.value}
        )

    def resolve_variance(self, variance_id: uuid.UUID, body: VarianceResolutionIn) -> CashVarianceDto:
        v = self.variance(variance_id, lock=True)
        if v.status is not VarianceStatus.OPEN:
            raise Conflict(f"Variance is {v.status.value}", code="VARIANCE_NOT_OPEN")
        self._not_own_variance(v, "resolve")
        if body.outcome is VarianceOutcome.WRITTEN_OFF:
            if self._policy().policy.writeoff_requires_approval:
                raise BusinessRuleViolation(
                    "Write-offs are proposed and approved by another person", code="WRITEOFF_APPROVAL_REQUIRED"
                )
            if WRITEOFF_PERMISSION not in self._ctx.permissions:
                permission_refused(
                    self._tid,
                    self._ctx.user_id,
                    WRITEOFF_PERMISSION,
                    detail={"variance": str(v.id)},
                    occurred_at=self._now,
                    actor_subject=self._ctx.subject,
                )
                raise PermissionDenied(f"Missing permission {WRITEOFF_PERMISSION}")
            if v.opened_by == self._ctx.user_id:
                refuse_sod(
                    self._ctx, "write_off", "cash_variance", v.id, "Whoever recorded the difference cannot write it off"
                )
            reason = check_reason(self._s, CashReasonKind.WRITE_OFF, body.reason_id)
        else:
            reason = check_reason(self._s, CashReasonKind.VARIANCE, body.reason_id)
        self._resolve(v, body.outcome, body.note, reason)
        return CashVarianceDto.model_validate(v)

    def propose_writeoff(self, variance_id: uuid.UUID, body: WriteOffProposalIn) -> CashVarianceDto:
        v = self.variance(variance_id, lock=True)
        if v.status is not VarianceStatus.OPEN:
            raise Conflict(f"Variance is {v.status.value}", code="VARIANCE_NOT_OPEN")
        self._not_own_variance(v, "propose_write_off")
        v.reason_id = check_reason(self._s, CashReasonKind.WRITE_OFF, body.reason_id)
        v.status, v.proposed_by, v.proposed_at, v.proposal_note = (
            VarianceStatus.WRITE_OFF_PROPOSED,
            self._ctx.user_id,
            self._now,
            body.note,
        )
        self._s.flush()
        self._record(
            "finance.cash_variance.write_off_proposed",
            "cash_variance",
            v.id,
            before={"status": VarianceStatus.OPEN.value},
            after={"status": v.status.value, "amount": str(v.amount)},
            reason=body.note,
        )
        self._emit(
            "CashApprovalRequested",
            v.id,
            {
                "kind": "WRITE_OFF",
                "permission": WRITEOFF_PERMISSION,
                "entity_type": "cash_variance",
                "entity_id": str(v.id),
                "amount": str(v.amount),
                "currency": v.currency,
            },
        )
        return CashVarianceDto.model_validate(v)

    def decide_writeoff(self, variance_id: uuid.UUID, body: DecisionIn) -> CashVarianceDto:
        v = self.variance(variance_id, lock=True)
        if v.status is not VarianceStatus.WRITE_OFF_PROPOSED:
            raise Conflict("No write-off is proposed for this variance", code="WRITEOFF_NOT_PROPOSED")
        if v.proposed_by == self._ctx.user_id:
            refuse_sod(
                self._ctx, "approve_write_off", "cash_variance", v.id, "The proposer cannot approve the write-off"
            )
        self._not_own_variance(v, "approve_write_off")
        if body.approve:
            self._resolve(v, VarianceOutcome.WRITTEN_OFF, body.note or v.proposal_note or "", None)
        else:
            v.status, v.proposed_by, v.proposed_at, v.proposal_note = VarianceStatus.OPEN, None, None, None
            self._s.flush()
            self._record(
                "finance.cash_variance.write_off_rejected",
                "cash_variance",
                v.id,
                before={"status": VarianceStatus.WRITE_OFF_PROPOSED.value},
                after={"status": v.status.value},
                reason=body.note,
            )
        return CashVarianceDto.model_validate(v)

    # --- retentions -----------------------------------------------------------------------------------------
    def request_retention(self, body: CashRetentionIn, source: str = "API") -> CashRetentionDto:
        if body.client_id is not None:
            existing = self._s.execute(
                select(CashRetention).where(CashRetention.client_id == body.client_id)
            ).scalar_one_or_none()
            if existing is not None:
                return CashRetentionDto.model_validate(existing)  # offline retry: exactly one effect
        eff = self._policy()
        if not eff.policy.retention_allowed:
            raise BusinessRuleViolation("This tenant does not allow cash retention", code="RETENTION_NOT_ALLOWED")
        staff = resolve_recorded_custodian(self._s, self._ctx, body.staff_member_id, eff.policy)
        if body.valid_until is not None and body.valid_until <= self._now:
            raise BusinessRuleViolation("valid_until must be in the future", code="INVALID_PERIOD")
        row = CashRetention(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            client_id=body.client_id,
            staff_member_id=staff.id,
            amount=body.amount,
            currency=currency_or_default(self._s, self._tid, body.currency),
            reason_id=check_reason(self._s, CashReasonKind.RETENTION, body.reason_id),
            reason=body.reason,
            valid_until=body.valid_until,
            status=CashDecisionStatus.PENDING,
            created_by=self._ctx.user_id,
            created_at=self._now,
        )
        insert(self._s, row, "DUPLICATE_RETENTION", "Retention request already recorded")
        self._record(
            "finance.cash_retention.requested",
            "cash_retention",
            row.id,
            source=source.lower(),
            after={"staff_member_id": str(staff.id), "amount": str(row.amount), "currency": row.currency},
            reason=body.reason,
            policy_version=eff.version_stamp[:64],
        )
        self._emit(
            "CashApprovalRequested",
            staff.id,
            {
                "kind": "RETENTION",
                "permission": "tenant.finance.retention_approve",
                "entity_type": "cash_retention",
                "entity_id": str(row.id),
                "amount": str(row.amount),
                "currency": row.currency,
            },
        )
        return CashRetentionDto.model_validate(row)

    def decide_retention(self, retention_id: uuid.UUID, body: DecisionIn) -> CashRetentionDto:
        row = self._s.execute(
            select(CashRetention).where(CashRetention.id == retention_id).with_for_update()
        ).scalar_one_or_none()
        if row is None:
            raise NotFound("Retention not found", code="RETENTION_NOT_FOUND")
        if row.status is not CashDecisionStatus.PENDING:
            raise Conflict(f"Retention already {row.status.value}", code="RETENTION_ALREADY_DECIDED")
        own = own_staff(self._s, self._ctx)
        if row.created_by == self._ctx.user_id or (own is not None and own.id == row.staff_member_id):
            refuse_sod(self._ctx, "approve", "cash_retention", row.id, "A retention is approved by someone else")
        row.status = CashDecisionStatus.APPROVED if body.approve else CashDecisionStatus.REJECTED
        row.decided_by, row.decided_at, row.decision_note = self._ctx.user_id, self._now, body.note
        self._s.flush()
        self._record(
            f"finance.cash_retention.{row.status.value.lower()}",
            "cash_retention",
            row.id,
            before={"status": "PENDING"},
            after={"status": row.status.value},
            reason=body.note,
        )
        return CashRetentionDto.model_validate(row)

    # --- custody adjustments --------------------------------------------------------------------------------
    def propose_adjustment(self, body: CustodyAdjustmentIn) -> CustodyAdjustmentDto:
        staff = resolve_staff(self._s, self._ctx, body.staff_member_id, require_active=False)
        if body.reverses_entity_type is not None:
            model = REVERSIBLE[body.reverses_entity_type]
            if self._s.get(model, body.reverses_entity_id) is None:
                raise NotFound("The record to reverse was not found", code="REVERSED_RECORD_NOT_FOUND")
        row = CustodyAdjustment(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            staff_member_id=staff.id,
            kind=body.kind,
            amount=body.amount,
            currency=currency_or_default(self._s, self._tid, body.currency),
            occurred_at=body.occurred_at or self._now,
            reason_id=check_reason(self._s, CashReasonKind.ADJUSTMENT, body.reason_id),
            reason=body.reason,
            reverses_entity_type=body.reverses_entity_type,
            reverses_entity_id=body.reverses_entity_id,
            status=CashDecisionStatus.PENDING,
            created_by=self._ctx.user_id,
            created_at=self._now,
        )
        self._s.add(row)
        self._s.flush()
        self._record(
            "finance.custody_adjustment.proposed",
            "custody_adjustment",
            row.id,
            after={
                "staff_member_id": str(staff.id),
                "kind": row.kind.value,
                "amount": str(row.amount),
                "currency": row.currency,
                "reverses": f"{row.reverses_entity_type}:{row.reverses_entity_id}" if row.reverses_entity_id else None,
            },
            reason=body.reason,
        )
        self._emit(
            "CashApprovalRequested",
            staff.id,
            {
                "kind": "CUSTODY_ADJUSTMENT",
                "permission": "tenant.finance.adjustment_approve",
                "entity_type": "custody_adjustment",
                "entity_id": str(row.id),
                "amount": str(row.amount),
                "currency": row.currency,
            },
        )
        return CustodyAdjustmentDto.model_validate(row)

    def decide_adjustment(self, adjustment_id: uuid.UUID, body: DecisionIn) -> CustodyAdjustmentDto:
        row = self._s.execute(
            select(CustodyAdjustment).where(CustodyAdjustment.id == adjustment_id).with_for_update()
        ).scalar_one_or_none()
        if row is None:
            raise NotFound("Adjustment not found", code="ADJUSTMENT_NOT_FOUND")
        if row.status is not CashDecisionStatus.PENDING:
            raise Conflict(f"Adjustment already {row.status.value}", code="ADJUSTMENT_ALREADY_DECIDED")
        own = own_staff(self._s, self._ctx)
        if row.created_by == self._ctx.user_id or (own is not None and own.id == row.staff_member_id):
            refuse_sod(self._ctx, "approve", "custody_adjustment", row.id, "An adjustment is approved by someone else")
        row.status = CashDecisionStatus.APPROVED if body.approve else CashDecisionStatus.REJECTED
        row.decided_by, row.decided_at, row.decision_note = self._ctx.user_id, self._now, body.note
        self._s.flush()
        self._record(
            f"finance.custody_adjustment.{row.status.value.lower()}",
            "custody_adjustment",
            row.id,
            before={"status": "PENDING"},
            after={"status": row.status.value, "amount": str(row.amount)},
            reason=body.note,
        )
        return CustodyAdjustmentDto.model_validate(row)

    # --- reason lists (tenant data) -------------------------------------------------------------------------
    def list_reasons(self, kind: CashReasonKind | None, q: str | None, include_inactive: bool) -> Select[CashReason]:
        stmt = select(CashReason).order_by(CashReason.kind, CashReason.label)
        if kind:
            stmt = stmt.where(CashReason.kind == kind)
        if not include_inactive:
            stmt = stmt.where(CashReason.is_active.is_(True))
        if (cond := ilike_any(q, CashReason.label, CashReason.description)) is not None:
            stmt = stmt.where(cond)
        return stmt

    def reason(self, reason_id: uuid.UUID) -> CashReason:
        row = self._s.get(CashReason, reason_id)
        if row is None:
            raise NotFound("Reason not found", code="REASON_NOT_FOUND")
        return row

    def create_reason(self, body: CashReasonIn) -> CashReasonDto:
        row = CashReason(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            kind=body.kind,
            label=body.label,
            description=body.description,
            is_active=True,
            created_by=self._ctx.user_id,
        )
        insert(self._s, row, "DUPLICATE_REASON", "A reason with this label already exists")
        self._record(
            "finance.cash_reason.created", "cash_reason", row.id, after={"kind": row.kind.value, "label": row.label}
        )
        return CashReasonDto.model_validate(row)

    def update_reason(self, reason_id: uuid.UUID, body: CashReasonUpdateIn) -> CashReasonDto:
        row = self.reason(reason_id)
        check_version(row.version, body.version, "Reason")
        before = {"label": row.label, "description": row.description}
        if body.label is not None:
            row.label = body.label
        if body.description is not None:
            row.description = body.description
        flush_versioned(self._s, "Reason", "DUPLICATE_REASON", "A reason with this label already exists")
        self._record(
            "finance.cash_reason.updated",
            "cash_reason",
            row.id,
            before=before,
            after={"label": row.label, "description": row.description},
        )
        return CashReasonDto.model_validate(row)

    def set_reason_active(self, reason_id: uuid.UUID, body: LifecycleChangeIn, active: bool) -> CashReasonDto:
        row = self.reason(reason_id)
        check_version(row.version, body.version, "Reason")
        if active:
            mark_active(row, "Reason")
        else:
            mark_inactive(row, self._ctx.user_id, body.reason, "Reason")
        flush_versioned(self._s, "Reason")
        self._record(
            f"finance.cash_reason.{'reactivated' if active else 'deactivated'}",
            "cash_reason",
            row.id,
            after={"is_active": active},
            reason=body.reason,
        )
        return CashReasonDto.model_validate(row)


__all__ = ["RECORDER_PERMISSION", "CashCustodyControls", "custodian_dto"]
