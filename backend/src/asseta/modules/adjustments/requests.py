"""The uniform propose/decide flow (DEC-032 T7, B1-B4): customer-hour corrections, refunds, reversals of posted
transactions and invoice voids. One person proposes, another decides (always; never relaxable); the original stays
visible and the outcome is posted to Ledger 6. Decisions are re-validated against the ledgers at that moment."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound, PermissionDenied
from asseta.core.outbox import OutboxWriter
from asseta.core.search import ilike_any
from asseta.core.signals import sod_violation
from asseta.modules.adjustments.dto import (
    AdjustmentDecisionIn,
    AdjustmentRequestDto,
    AdjustmentRequestIn,
)
from asseta.modules.adjustments.hours_effects import HoursEffects
from asseta.modules.adjustments.models import (
    AdjustmentRequest,
    AdjustmentRequestStatus,
    AdjustmentRequestType,
    RefundSettlement,
)
from asseta.modules.adjustments.permissions import DECIDE_PERMISSION
from asseta.modules.adjustments.request_posting import RequestPosting
from asseta.modules.adjustments.reversals import ReversalEngine, used_hours_of
from asseta.modules.finance.dto import HireInvoiceVoidIn
from asseta.modules.finance.invoice_service import HireInvoiceService
from asseta.modules.finance.models import CustomerPayment, HireInvoiceStatus, HirePaymentMethod, TenantHireInvoice
from asseta.modules.fleet.models import StaffMember
from asseta.modules.hours.engine import TOPIC as HOURS_TOPIC
from asseta.modules.hours.engine import HoursEngine
from asseta.modules.hours.ledger import purchase_totals
from asseta.modules.hours.models import HoursReasonCode, ReasonKind
from asseta.modules.identity.principal import RequestContext
from asseta.modules.meter.models import CaptureAttachment
from asseta.modules.policy.service import PolicyService

ORIGINALS = {
    "payment": "customer_payment",
    "purchase": "hours_purchase",
    "invoice": "tenant_hire_invoice",
}
REASON_KINDS: dict[AdjustmentRequestType, ReasonKind] = {
    AdjustmentRequestType.HOURS_CORRECTION: ReasonKind.CORRECTION,
    AdjustmentRequestType.HOURS_REFUND: ReasonKind.REFUND,
    AdjustmentRequestType.PAYMENT_REVERSAL: ReasonKind.REVERSAL,
    AdjustmentRequestType.COLLECTION_REVERSAL: ReasonKind.REVERSAL,
    AdjustmentRequestType.PURCHASE_REVERSAL: ReasonKind.REVERSAL,
    AdjustmentRequestType.INVOICE_VOID: ReasonKind.REVERSAL,
}


class AdjustmentRequests:
    def __init__(self, session: Session, ctx: RequestContext, now: datetime):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid, self._now = session, ctx, ctx.tenant_id, now
        self._audit = AuditService(session)
        self.engine = HoursEngine(session, ctx.tenant_id, ctx.audit_actor(), now)
        self.hours = HoursEffects(session, ctx, now, self.engine)
        self.reversals = ReversalEngine(session, ctx, now, self.engine)
        self.posting = RequestPosting(session, ctx, now, self.engine, self.hours, self.reversals)

    # --- reading ----------------------------------------------------------------------------------------------
    def query(
        self,
        q: str | None,
        request_type: AdjustmentRequestType | None,
        status: AdjustmentRequestStatus | None,
        customer_id: uuid.UUID | None,
        machine_id: uuid.UUID | None,
        original_id: uuid.UUID | None,
    ) -> Select[AdjustmentRequest]:
        stmt = select(AdjustmentRequest).order_by(AdjustmentRequest.proposed_at.desc(), AdjustmentRequest.id)
        for column, value in (
            (AdjustmentRequest.request_type, request_type),
            (AdjustmentRequest.status, status),
            (AdjustmentRequest.customer_id, customer_id),
            (AdjustmentRequest.machine_id, machine_id),
            (AdjustmentRequest.original_id, original_id),
        ):
            if value is not None:
                stmt = stmt.where(column == value)
        if (match := ilike_any(q, AdjustmentRequest.original_reference, AdjustmentRequest.reason)) is not None:
            stmt = stmt.where(match)
        return stmt

    def row(self, request_id: uuid.UUID, lock: bool = False) -> AdjustmentRequest:
        stmt = select(AdjustmentRequest).where(AdjustmentRequest.id == request_id)
        row = self._s.execute(stmt.with_for_update() if lock else stmt).scalar_one_or_none()
        if row is None:
            raise NotFound("Adjustment request not found", code="ADJUSTMENT_REQUEST_NOT_FOUND")
        return row

    def dto(self, row: AdjustmentRequest) -> AdjustmentRequestDto:
        dto = AdjustmentRequestDto.model_validate(row)
        if row.reason_code_id:
            code = self._s.get(HoursReasonCode, row.reason_code_id)
            dto.reason_label = code.label if code else None
        dto.effects = (
            (row.result or {}) if row.status is not AdjustmentRequestStatus.PROPOSED else self.posting.forecast(row)
        )
        return dto

    # --- proposing --------------------------------------------------------------------------------------------
    def _check_evidence(self, ids: list[uuid.UUID]) -> None:
        for attachment_id in ids:
            if self._s.get(CaptureAttachment, attachment_id) is None:
                raise NotFound("Evidence attachment not found", code="ATTACHMENT_NOT_FOUND")

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

    def propose(self, body: AdjustmentRequestIn) -> AdjustmentRequestDto:
        if body.client_id is not None:
            existing = self._s.execute(
                select(AdjustmentRequest).where(AdjustmentRequest.client_id == body.client_id)
            ).scalar_one_or_none()
            if existing is not None:
                return self.dto(existing)
        if self.engine.policy.adjustment_evidence_required and not body.evidence_attachment_ids:
            raise BusinessRuleViolation("Attach the supporting evidence", code="EVIDENCE_REQUIRED")
        self._check_evidence(body.evidence_attachment_ids)
        reason_code = self._reason_code(REASON_KINDS[body.request_type], body.reason_code_id)
        row = self._build(body, reason_code)
        try:
            with self._s.begin_nested():
                self._s.add(row)
                self._s.flush()
        except IntegrityError as exc:
            raise Conflict("A reversal of this record already exists", code="REVERSAL_EXISTS") from exc
        return self._submitted(row)

    def _submitted(self, row: AdjustmentRequest) -> AdjustmentRequestDto:
        self._audit.record(
            actor=self._ctx.audit_actor(),
            action=f"adjustment.{row.request_type.value.lower()}.proposed",
            entity_type="adjustment_request",
            entity_id=row.id,
            tenant_id=self._tid,
            after={
                "original_type": row.original_type,
                "original_id": str(row.original_id),
                "hours": str(row.hours) if row.hours is not None else None,
                "amount": str(row.amount) if row.amount is not None else None,
            },
            reason=row.reason,
            policy_version=row.policy_version[:64],
        )
        self._notify_requested(row)
        return self.dto(row)

    def _notify_requested(self, row: AdjustmentRequest) -> None:
        label = row.request_type.value.replace("_", " ").lower()
        subject = row.original_reference or str(row.original_id)[:8]
        OutboxWriter(self._s).emit(
            topic=HOURS_TOPIC,
            event_type="AdjustmentApprovalRequested",
            key=str(row.id),
            payload={
                "request_id": str(row.id),
                "request_type": row.request_type.value,
                "audience_permission": DECIDE_PERMISSION,
                "summary": f"{label} of {subject} to approve",
                "requested_by": str(row.proposed_by) if row.proposed_by else None,
            },
            tenant_id=self._tid,
        )

    def _notify_decided(self, row: AdjustmentRequest) -> None:
        if row.proposed_by is None or row.proposed_by == self._ctx.user_id:
            return
        OutboxWriter(self._s).emit(
            topic=HOURS_TOPIC,
            event_type="AdjustmentApprovalDecided",
            key=str(row.id),
            payload={
                "request_id": str(row.id),
                "request_type": row.request_type.value,
                "user_id": str(row.proposed_by),
                "outcome": row.status.value,
            },
            tenant_id=self._tid,
        )

    def _build(self, body: AdjustmentRequestIn, reason_code: uuid.UUID | None) -> AdjustmentRequest:
        t = body.request_type
        fields: dict[str, Any] = {
            "params": {},
            "hours": None,
            "amount": None,
            "currency": None,
            "settlement": None,
            "customer_id": None,
            "machine_id": None,
            "purchase_id": None,
        }
        if t in (AdjustmentRequestType.HOURS_CORRECTION, AdjustmentRequestType.HOURS_REFUND):
            original_type, original_id, reference = self._lot_fields(body, fields, t)
        elif t in (AdjustmentRequestType.PAYMENT_REVERSAL, AdjustmentRequestType.COLLECTION_REVERSAL):
            original_type, original_id, reference = self._payment_fields(body, fields, t)
        elif t is AdjustmentRequestType.PURCHASE_REVERSAL:
            original_type, original_id, reference = self._purchase_fields(body, fields)
        else:
            original_type, original_id, reference = self._invoice_fields(body, fields)
        return AdjustmentRequest(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            client_id=body.client_id,
            request_type=t,
            status=AdjustmentRequestStatus.PROPOSED,
            original_type=original_type,
            original_id=original_id,
            original_reference=reference,
            reason=body.reason,
            reason_code_id=reason_code,
            evidence_attachment_ids=body.evidence_attachment_ids,
            proposed_by=self._ctx.user_id,
            proposed_at=self._now,
            policy_version=self.engine.eff.version_stamp[:80],
            **fields,
        )

    def _lot_fields(
        self, body: AdjustmentRequestIn, fields: dict[str, Any], t: AdjustmentRequestType
    ) -> tuple[str, uuid.UUID, str]:
        if body.purchase_id is None or body.hours is None:
            raise BusinessRuleViolation("Name the hours purchase and the hours", code="ADJUSTMENT_FIELDS_MISSING")
        if not self.engine.policy.enabled:
            raise BusinessRuleViolation("Customer hours are switched off for this tenant", code="HOURS_DISABLED")
        purchase, machine_id = self.hours.resolve_lot(body.purchase_id, body.machine_id)
        totals = purchase_totals(self._s, purchase)
        fields.update(
            customer_id=purchase.customer_id,
            machine_id=machine_id,
            purchase_id=purchase.id,
            hours=body.hours,
            currency=purchase.currency,
        )
        if t is AdjustmentRequestType.HOURS_CORRECTION:
            if body.hours == 0:
                raise BusinessRuleViolation("A correction changes the hours", code="HOURS_CORRECTION_INVALID")
            if body.job_id is not None:
                fields["params"]["job_id"] = str(body.job_id)
            if body.consumed_entry_id is not None:
                fields["params"]["consumed_entry_id"] = str(body.consumed_entry_id)
            self.hours.check_correction(purchase, machine_id, body.hours, totals, body.consumed_entry_id)
        else:
            if not self.engine.policy.refund_allowed:
                raise BusinessRuleViolation("Refunds are switched off by tenant policy", code="REFUND_NOT_ALLOWED")
            if body.settlement is None:
                raise BusinessRuleViolation("Choose how the refund is settled", code="REFUND_SETTLEMENT_REQUIRED")
            if body.settlement is RefundSettlement.PAY_OUT and body.payout is None:
                raise BusinessRuleViolation("Record how the refund is paid out", code="REFUND_PAYOUT_REQUIRED")
            fields["settlement"] = body.settlement
            custodian = body.payout.staff_member_id if body.payout is not None else None
            if custodian is not None and self._s.get(StaffMember, custodian) is None:
                raise NotFound("Staff member not found", code="STAFF_NOT_FOUND")
            if body.payout is not None:
                fields["params"]["payout"] = body.payout.model_dump(mode="json", exclude_none=True)
            fields["amount"] = self.hours.check_refund(purchase, machine_id, body.hours, totals)
        return "hours_purchase", purchase.id, purchase.purchase_number

    def _payment_fields(
        self, body: AdjustmentRequestIn, fields: dict[str, Any], t: AdjustmentRequestType
    ) -> tuple[str, uuid.UUID, str]:
        if body.payment_id is None:
            raise BusinessRuleViolation("Name the payment to reverse", code="ADJUSTMENT_FIELDS_MISSING")
        payment = self._payment(body.payment_id, lock=True)
        is_cash = payment.method is HirePaymentMethod.CASH
        if is_cash != (t is AdjustmentRequestType.COLLECTION_REVERSAL):
            raise BusinessRuleViolation(
                "A cash payment is reversed as a collection; a bank or mobile-money payment as a payment",
                code="REVERSAL_TYPE_MISMATCH",
            )
        self.reversals.check_payment_reversible(payment)
        fields.update(customer_id=payment.customer_id, amount=payment.amount, currency=payment.currency)
        return "customer_payment", payment.id, payment.reference or f"{payment.method.value}-{str(payment.id)[:8]}"

    def _purchase_fields(self, body: AdjustmentRequestIn, fields: dict[str, Any]) -> tuple[str, uuid.UUID, str]:
        if body.purchase_id is None:
            raise BusinessRuleViolation("Name the hours purchase", code="ADJUSTMENT_FIELDS_MISSING")
        purchase = self.engine.lock_purchase(body.purchase_id)
        if purchase.cancelled_at is not None:
            raise BusinessRuleViolation("The purchase is cancelled", code="PURCHASE_CANCELLED")
        totals = purchase_totals(self._s, purchase)
        if totals.remaining <= 0 and used_hours_of(totals) <= 0 and totals.activated <= 0:
            raise BusinessRuleViolation("Nothing of this purchase is posted yet", code="NOTHING_TO_REVERSE")
        fields.update(
            customer_id=purchase.customer_id,
            machine_id=purchase.machine_id,
            purchase_id=purchase.id,
            amount=purchase.amount if purchase.amount > 0 else None,
            currency=purchase.currency,
        )
        return "hours_purchase", purchase.id, purchase.purchase_number

    def _invoice_fields(self, body: AdjustmentRequestIn, fields: dict[str, Any]) -> tuple[str, uuid.UUID, str]:
        if body.invoice_id is None:
            raise BusinessRuleViolation("Name the invoice", code="ADJUSTMENT_FIELDS_MISSING")
        inv = self._invoice(body.invoice_id, lock=True)
        if inv.status is not HireInvoiceStatus.ISSUED or inv.invoice_number is None:
            raise BusinessRuleViolation("Only an issued invoice needs a void request", code="INVOICE_NOT_ISSUED")
        fields.update(customer_id=inv.customer_id, amount=inv.total if inv.total > 0 else None, currency=inv.currency)
        return "tenant_hire_invoice", inv.id, inv.invoice_number

    def propose_void(self, invoice_id: uuid.UUID, body: HireInvoiceVoidIn) -> AdjustmentRequestDto:
        """The void of an issued invoice, when the tenant requires a second person (legacy void endpoint)."""
        inv = self._invoice(invoice_id, lock=True)
        if inv.status is not HireInvoiceStatus.ISSUED or inv.invoice_number is None:
            raise Conflict(f"Invoice is {inv.status.value}", code="INVOICE_NOT_ISSUED")
        self._check_evidence(body.evidence_attachment_ids)
        code = self._reason_code(ReasonKind.REVERSAL, body.reason_code_id)
        fields: dict[str, Any] = {
            "params": {},
            "hours": None,
            "amount": inv.total if inv.total > 0 else None,
            "currency": inv.currency,
            "settlement": None,
            "customer_id": inv.customer_id,
            "machine_id": None,
            "purchase_id": None,
        }
        row = AdjustmentRequest(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            client_id=None,
            request_type=AdjustmentRequestType.INVOICE_VOID,
            status=AdjustmentRequestStatus.PROPOSED,
            original_type="tenant_hire_invoice",
            original_id=inv.id,
            original_reference=inv.invoice_number,
            reason=body.reason,
            reason_code_id=code,
            evidence_attachment_ids=body.evidence_attachment_ids,
            proposed_by=self._ctx.user_id,
            proposed_at=self._now,
            policy_version=self.engine.eff.version_stamp[:80],
            **fields,
        )
        try:
            with self._s.begin_nested():
                self._s.add(row)
                self._s.flush()
        except IntegrityError as exc:
            raise Conflict("A void of this invoice awaits a decision", code="REVERSAL_EXISTS") from exc
        return self._submitted(row)

    def requires_void_approval(self) -> bool:
        return PolicyService(self._s).hire_billing(self._tid, at=self._now).policy.invoice_void_requires_approval

    # --- deciding ---------------------------------------------------------------------------------------------
    def withdraw(self, request_id: uuid.UUID, reason: str) -> AdjustmentRequestDto:
        row = self.row(request_id, lock=True)
        if row.status is not AdjustmentRequestStatus.PROPOSED:
            raise Conflict(f"Already {row.status.value}", code="ALREADY_DECIDED")
        if row.proposed_by != self._ctx.user_id:
            raise PermissionDenied("Only the proposer can withdraw a proposal", code="NOT_PROPOSER")
        row.status, row.decided_at, row.decision_note = AdjustmentRequestStatus.WITHDRAWN, self._now, reason
        self._s.flush()
        self._audit.record(
            actor=self._ctx.audit_actor(),
            action=f"adjustment.{row.request_type.value.lower()}.withdrawn",
            entity_type="adjustment_request",
            entity_id=row.id,
            tenant_id=self._tid,
            before={"status": "PROPOSED"},
            after={"status": "WITHDRAWN"},
            reason=reason,
        )
        return self.dto(row)

    def decide(self, request_id: uuid.UUID, body: AdjustmentDecisionIn) -> AdjustmentRequestDto:
        row = self.row(request_id, lock=True)
        if row.status is not AdjustmentRequestStatus.PROPOSED:
            raise Conflict(f"Already {row.status.value}", code="ALREADY_DECIDED")
        if row.proposed_by is not None and row.proposed_by == self._ctx.user_id:
            sod_violation(self._tid, self._ctx.user_id, "approve", "adjustment_request", row.id)
            raise BusinessRuleViolation("The person who proposed this cannot decide it", code="SEGREGATION_OF_DUTIES")
        approve = body.decision == "APPROVE"
        result: dict[str, Any] = {}
        if approve:
            result = self._apply(row)
        row.status = AdjustmentRequestStatus.APPROVED if approve else AdjustmentRequestStatus.REJECTED
        row.decided_by, row.decided_at, row.decision_note, row.result = (
            self._ctx.user_id,
            self._now,
            body.note,
            result,
        )
        self._s.flush()
        self._audit.record(
            actor=self._ctx.audit_actor(),
            action=f"adjustment.{row.request_type.value.lower()}.{'approved' if approve else 'rejected'}",
            entity_type="adjustment_request",
            entity_id=row.id,
            tenant_id=self._tid,
            before={"status": "PROPOSED"},
            after={"status": row.status.value, "result": result},
            reason=body.note,
        )
        if row.request_type is not AdjustmentRequestType.INVOICE_VOID or not approve:
            self.posting.post(row, body.note, result)  # an approved void posts from the invoice service
        self._notify_decided(row)
        return self.dto(row)

    def _apply(self, row: AdjustmentRequest) -> dict[str, Any]:
        t = row.request_type
        if t is AdjustmentRequestType.HOURS_CORRECTION:
            return self.hours.apply_correction(row)
        if t is AdjustmentRequestType.HOURS_REFUND:
            return self.hours.apply_refund(row)
        if t in (AdjustmentRequestType.PAYMENT_REVERSAL, AdjustmentRequestType.COLLECTION_REVERSAL):
            return self.reversals.apply_payment_reversal(row, self._payment(row.original_id, lock=True))
        if t is AdjustmentRequestType.PURCHASE_REVERSAL:
            return self.reversals.apply_purchase_reversal(row, self.engine.lock_purchase(row.original_id))
        label = self.posting.reason_label(row.reason_code_id)
        HireInvoiceService(self._s, self._ctx, self._now).void(
            row.original_id, row.reason, request=row, reason_label=label
        )
        return {"invoice_id": str(row.original_id)}

    def _payment(self, payment_id: uuid.UUID, lock: bool = False) -> CustomerPayment:
        stmt = select(CustomerPayment).where(CustomerPayment.id == payment_id)
        row = self._s.execute(stmt.with_for_update() if lock else stmt).scalar_one_or_none()
        if row is None:
            raise NotFound("Payment not found", code="PAYMENT_NOT_FOUND")
        return row

    def _invoice(self, invoice_id: uuid.UUID, lock: bool = False) -> TenantHireInvoice:
        stmt = select(TenantHireInvoice).where(TenantHireInvoice.id == invoice_id)
        row = self._s.execute(stmt.with_for_update() if lock else stmt).scalar_one_or_none()
        if row is None:
            raise NotFound("Hire invoice not found")
        return row


def _uuid(value: object) -> uuid.UUID | None:
    return uuid.UUID(str(value)) if value else None
