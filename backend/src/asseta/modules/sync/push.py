"""Idempotent, dependency-ordered push of offline operations.

Each operation: (1) replay -> stored result (DUPLICATE), (2) unmet dependency -> DEFERRED (not stored; device
retries), (3) read-only/suspended tenant -> QUARANTINED (stored, never applied, replayed when the device re-sends
after reactivation), (4) dispatched to the same domain service the online API uses, inside a savepoint.
Domain conflicts are returned as structured CONFLICT results with server state — never last-write-wins.
"""

import hashlib
import json
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.errors import AppError, BusinessRuleViolation, DependencyUnavailable, NotFound
from asseta.core.outbox import OutboxWriter
from asseta.modules.accountability.security_events import permission_refused
from asseta.modules.expenses.dto import ExpenseIn, FuelEventIn
from asseta.modules.expenses.service import ExpenseService
from asseta.modules.finance.cash_service import CashCustodyService
from asseta.modules.finance.custody_dto import CashAcknowledgementIn, CashRetentionIn, CashTransferIn
from asseta.modules.finance.custody_service import CashCustodyControls
from asseta.modules.finance.dto import CashCollectionIn, CashHandoverIn
from asseta.modules.hours.approvals import HoursApprovals
from asseta.modules.hours.credit_invoices import CreditInvoiceService
from asseta.modules.hours.dto import CreditInvoicePaymentIn, HoursPurchaseIn, PurchasePaymentIn, TransferIn
from asseta.modules.hours.service import HoursService
from asseta.modules.identity.principal import RequestContext
from asseta.modules.machine_reports.dto import MachineReportIn
from asseta.modules.machine_reports.service import MachineReportService
from asseta.modules.meter.allocation_dto import DailyReportIn
from asseta.modules.meter.daily_report import DailyReportService
from asseta.modules.meter.dto import MeterCaptureIn, ResetIn
from asseta.modules.meter.engine_dto import BaselineIn, CorrectionIn
from asseta.modules.meter.engine_service import EngineHoursService
from asseta.modules.meter.service import MeterService
from asseta.modules.pettycash.dto import (
    PettyCashAcknowledgementIn,
    PettyCashAdvanceClearIn,
    PettyCashAdvanceIn,
    PettyCashCountIn,
    PettyCashHolderChangeDecisionIn,
    PettyCashReturnIn,
    TopUpRequestIn,
)
from asseta.modules.pettycash.service import PettyCashService
from asseta.modules.policy.capabilities import (
    CASH_CUSTODY,
    ENGINE_HOURS,
    FUEL,
    PETTY_CASH,
    require_capability,
)
from asseta.modules.policy.service import PolicyService
from asseta.modules.sync.conflicts import is_conflict
from asseta.modules.sync.dto import (
    OP_TYPES,
    RETIRED_OP_TYPES,
    OperationIn,
    OperationResultDto,
    PushIn,
    PushResultDto,
)
from asseta.modules.sync.models import BlobUploadSession, ClientOperation, DeviceSession, OperationStatus
from asseta.modules.sync.service import SyncService

# Operations that belong to a tenant capability (sync capabilities: dto.TENANT_CAPABILITY_OF). DAILY meter captures
# and machine reports never depend on one (ADR-008). Customer-hours operations keep their service refusal.
OP_CAPABILITY = {
    "METER_BASELINE": ENGINE_HOURS,
    "METER_CORRECTION": ENGINE_HOURS,
    "CASH_TRANSFER": CASH_CUSTODY,
    "CASH_TRANSFER_ACKNOWLEDGEMENT": CASH_CUSTODY,
    "CASH_FLOAT_ACKNOWLEDGEMENT": CASH_CUSTODY,
    "CASH_RETENTION_REQUEST": CASH_CUSTODY,
    "DAILY_REPORT": ENGINE_HOURS,
    "PETTY_CASH_ACKNOWLEDGEMENT": PETTY_CASH,
    "PETTY_CASH_TOP_UP_REQUEST": PETTY_CASH,
    "PETTY_CASH_RETURN": PETTY_CASH,
    "PETTY_CASH_COUNT": PETTY_CASH,
    "PETTY_CASH_ADVANCE_CLEARANCE": PETTY_CASH,
    "PETTY_CASH_HOLDER_CHANGE_ACKNOWLEDGEMENT": PETTY_CASH,
    "PETTY_CASH_ADVANCE": PETTY_CASH,
    "FUEL_EVENT": FUEL,
}
REQUIRED_PERMISSION = {
    "METER_CAPTURE": "tenant.meter.capture",
    "EXPENSE": "tenant.expense.write",
    "FUEL_EVENT": "tenant.expense.write",
    "CASH_COLLECTION": "tenant.collection.record",
    "CASH_HANDOVER": "tenant.collection.record",
    "METER_RESET_REQUEST": "tenant.meter.capture",
    "METER_BASELINE": "tenant.meter.capture",
    "METER_CORRECTION": "tenant.meter.capture",
    "CASH_TRANSFER": "tenant.collection.record",
    "CASH_TRANSFER_ACKNOWLEDGEMENT": "tenant.collection.record",
    "CASH_FLOAT_ACKNOWLEDGEMENT": "tenant.collection.record",
    "HOURS_PURCHASE": "tenant.hours.purchase",
    "HOURS_TRANSFER_REQUEST": "tenant.hours.transfer",
    "CASH_RETENTION_REQUEST": "tenant.collection.record",
    "DAILY_REPORT": "tenant.meter.capture",
    "PETTY_CASH_ACKNOWLEDGEMENT": "tenant.pettycash.read",
    "PETTY_CASH_TOP_UP_REQUEST": "tenant.pettycash.read",
    "PETTY_CASH_RETURN": "tenant.pettycash.read",
    "PETTY_CASH_COUNT": "tenant.pettycash.count",
    "PETTY_CASH_ADVANCE_CLEARANCE": "tenant.pettycash.read",
    "PETTY_CASH_HOLDER_CHANGE_ACKNOWLEDGEMENT": "tenant.pettycash.read",
    "PETTY_CASH_ADVANCE": "tenant.pettycash.read",
    "MACHINE_REPORT": "tenant.machine_report.submit",
    "CREDIT_INVOICE_PAYMENT": "tenant.hours.invoice_payment",
}
# Ops whose payload names resumable blob uploads: the op is DEFERRED (not rejected) until they complete.
UPLOAD_FIELDS = {
    "EXPENSE": "receipt_upload_ids",
    "METER_RESET_REQUEST": "evidence_upload_id",
    "HOURS_PURCHASE": "evidence_upload_ids",
    "CASH_HANDOVER": "evidence_upload_ids",
    "DAILY_REPORT": "evidence_upload_ids",
    "HOURS_TRANSFER_REQUEST": "evidence_upload_ids",
    "PETTY_CASH_RETURN": "evidence_upload_ids",
    "PETTY_CASH_COUNT": "evidence_upload_ids",
    "MACHINE_REPORT": "photo_upload_id",
    "CREDIT_INVOICE_PAYMENT": "evidence_upload_ids",
}


class ExpenseOp(ExpenseIn):
    """Offline expense: receipts reference resumable blob uploads (the op waits until they complete)."""

    client_id: uuid.UUID
    receipt_upload_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)


class CashCollectionOp(CashCollectionIn):
    client_id: uuid.UUID


class CashHandoverOp(CashHandoverIn):
    """Offline remittance. Evidence photos reference resumable blob uploads (purpose REMITTANCE_EVIDENCE; the op
    waits until they complete) and/or attachment ids uploaded online."""

    client_id: uuid.UUID
    evidence_upload_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)


class DailyReportOp(DailyReportIn):
    """Offline daily report: the operation id is the report id; evidence by resumable blob uploads (purpose
    DAILY_REPORT_EVIDENCE; the op waits until they complete) or attachment ids uploaded online."""

    evidence_upload_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)


class PurchasePaymentOp(PurchasePaymentIn):
    """One part of an offline hours sale's payment, with its own evidence uploads (e.g. the bank slip)."""

    evidence_upload_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)


class HoursPurchaseOp(HoursPurchaseIn):
    """Offline hours purchase (walk-in allowed). The operation id is the purchase's client id; payment evidence
    references resumable blob uploads (purpose PAYMENT_EVIDENCE) and the op waits until they complete. A split bill's
    parts carry their own evidence_upload_ids; the op-level list goes to the single payment (or the first part)."""

    evidence_upload_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)
    payments: list[PurchasePaymentOp] = Field(default_factory=list, max_length=10)  # type: ignore[assignment]


class CashTransferOp(CashTransferIn):
    client_id: uuid.UUID


class CashRetentionOp(CashRetentionIn):
    client_id: uuid.UUID


class HoursTransferOp(TransferIn):
    """Offline hours transfer request: evidence by resumable blob uploads (purpose ADJUSTMENT_EVIDENCE; the op waits
    until they complete) or attachment ids uploaded online."""

    evidence_upload_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)


class CashTransferAckOp(CashAcknowledgementIn):
    transfer_id: uuid.UUID


class CashFloatAckOp(CashAcknowledgementIn):
    entry_id: uuid.UUID


class PettyCashAckOp(PettyCashAcknowledgementIn):
    movement_id: uuid.UUID


class PettyCashTopUpOp(TopUpRequestIn):
    fund_id: uuid.UUID


class PettyCashReturnOp(PettyCashReturnIn):
    """Offline return: evidence by resumable blob uploads (purpose PETTY_CASH_EVIDENCE) or attachment ids."""

    evidence_upload_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)


class PettyCashCountOp(PettyCashCountIn):
    evidence_upload_ids: list[uuid.UUID] = Field(default_factory=list, max_length=20)


class PettyCashAdvanceClearOp(PettyCashAdvanceClearIn):
    advance_id: uuid.UUID


class PettyCashHolderChangeOp(PettyCashHolderChangeDecisionIn):
    holder_change_id: uuid.UUID


class FuelEventOp(FuelEventIn):
    client_id: uuid.UUID


class MachineReportOp(MachineReportIn):
    """Offline machine report (ADR-008 §2): the operation id is the report id. The reading's photo may reference a
    resumable blob upload (purpose METER_PHOTO; the op waits until it completes) instead of an attachment id."""

    photo_upload_id: uuid.UUID | None = None


class CreditInvoicePaymentOp(CreditInvoicePaymentIn):
    """Offline credit-invoice payment: the operation id is the payment's client id; evidence by resumable blob uploads
    (purpose PAYMENT_EVIDENCE; the op waits until they complete) or attachment ids uploaded online."""

    invoice_id: uuid.UUID
    evidence_upload_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)


class MeterResetOp(ResetIn):
    """Offline meter reset request: evidence photo by resumable blob upload (purpose RESET_EVIDENCE) or by an
    attachment id uploaded online. The device-generated operation id is the idempotency key."""

    evidence_upload_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _one_evidence(self) -> "MeterResetOp":
        if self.evidence_upload_id is not None and self.evidence_attachment_id is not None:
            raise ValueError("give evidence_upload_id or evidence_attachment_id, not both")
        return self


def _hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


class PushService:
    def __init__(self, session: Session, ctx: RequestContext, now: datetime):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid, self._now = session, ctx, ctx.tenant_id, now

    def push(self, device_id: str | None, body: PushIn) -> PushResultDto:
        sync = SyncService(self._s, self._ctx, self._now)
        device = sync.active_device(device_id)
        policy = PolicyService(self._s).device_sync(self._tid, at=self._now).policy
        if len(body.operations) > policy.max_batch_operations:
            raise BusinessRuleViolation(
                f"Batch exceeds {policy.max_batch_operations} operations", code="BATCH_TOO_LARGE"
            )
        offset = (self._now - body.device_now).total_seconds()
        results = [self._one(device, op) for op in body.operations]
        sync.touch(device, offset)
        skewed = abs(offset) > policy.clock_skew_alert_seconds
        quarantined = sum(1 for r in results if r.status == "QUARANTINED")
        if skewed or quarantined:
            detail = (
                f"Device {device.device_id} clock is {round(offset)} s off server time (possible tampering)."
                if skewed
                else f"Device {device.device_id}: {quarantined} offline operation(s) quarantined."
            )
            OutboxWriter(self._s).emit(
                topic="asseta.sync",
                event_type="SyncAnomalyDetected",
                key=str(device.id),
                payload={
                    "device_session_id": str(device.id),
                    "kind": "CLOCK_SKEW" if skewed else "QUARANTINE",
                    "clock_offset_s": round(offset, 1),
                    "quarantined": quarantined,
                    "detail": detail,
                },
                tenant_id=self._tid,
            )
        return PushResultDto(
            server_time=self._now,
            clock_offset_s=round(offset, 1),
            clock_skew_alert=skewed,
            results=results,
        )

    def _one(self, device: DeviceSession, op: OperationIn) -> OperationResultDto:
        digest = _hash(op.payload)
        existing = self._s.get(ClientOperation, op.id)
        if existing is not None:
            if existing.payload_sha256 != digest or existing.op_type != op.op_type:
                return OperationResultDto(
                    id=op.id,
                    status="REJECTED",
                    error={"code": "OPERATION_ID_REUSED", "message": "Same id, different content"},
                )
            if existing.status is not OperationStatus.QUARANTINED or self._ctx.read_only:
                existing.attempts += 1
                return OperationResultDto(
                    id=op.id, status="DUPLICATE", result=existing.result, error=existing.result.get("error")
                )
        if op.op_type not in OP_TYPES:
            return self._refuse_type(device, op, digest, existing)
        unmet = [
            d
            for d in op.depends_on
            if self._s.execute(select(ClientOperation.status).where(ClientOperation.id == d)).scalar_one_or_none()
            is not OperationStatus.ACKED
        ]
        if unmet:
            return OperationResultDto(
                id=op.id, status="DEFERRED", error={"code": "DEPENDENCY_PENDING", "depends_on": [str(u) for u in unmet]}
            )
        if pending := self._pending_uploads(op):
            return OperationResultDto(
                id=op.id, status="DEFERRED", error={"code": "ATTACHMENT_PENDING", "upload_ids": pending}
            )
        if self._ctx.read_only:
            result = {
                "error": {
                    "code": "SUBSCRIPTION_READ_ONLY",
                    "message": "Tenant is read-only; operation kept and will apply after reactivation",
                }
            }
            self._store(device, op, digest, OperationStatus.QUARANTINED, result, existing)
            return OperationResultDto(id=op.id, status="QUARANTINED", result=result, error=result["error"])
        status, result = self._dispatch(device, op)
        self._store(device, op, digest, status, result, existing)
        return OperationResultDto.model_validate(
            {"id": op.id, "status": status.value, "result": result, "error": result.get("error")}
        )

    def _refuse_type(
        self, device: DeviceSession, op: OperationIn, digest: str, existing: ClientOperation | None
    ) -> OperationResultDto:
        """A retired (pre-ADR-008 app) or unknown operation type: refused on its own and kept for the office's sync
        review, so the rest of the batch still applies and a retry is a DUPLICATE."""
        retired = op.op_type in RETIRED_OP_TYPES
        error = {
            "code": "OPERATION_RETIRED" if retired else "UNKNOWN_OPERATION",
            "message": (
                f"{op.op_type} is no longer supported (jobs and site check-ins were removed); update the app"
                if retired
                else f"Unknown operation type {op.op_type}"
            ),
        }
        self._store(device, op, digest, OperationStatus.REJECTED, {"error": error}, existing)
        return OperationResultDto(id=op.id, status="REJECTED", error=error)

    def _store(
        self,
        device: DeviceSession,
        op: OperationIn,
        digest: str,
        status: OperationStatus,
        result: dict[str, Any],
        existing: ClientOperation | None,
    ) -> None:
        if existing is not None:  # a previously quarantined op being replayed after reactivation
            existing.status, existing.result, existing.attempts = status, result, existing.attempts + 1
        else:
            self._s.add(
                ClientOperation(
                    id=op.id,
                    tenant_id=self._tid,
                    device_session_id=device.id,
                    op_type=op.op_type,
                    payload_sha256=digest,
                    payload=op.payload,
                    status=status,
                    result=result,
                    created_at_device=op.created_at_device,
                    received_at=self._now,
                )
            )
        self._s.flush()

    def _dispatch(self, device: DeviceSession, op: OperationIn) -> tuple[OperationStatus, dict[str, Any]]:
        needed = REQUIRED_PERMISSION[op.op_type]
        if needed not in self._ctx.permissions:
            permission_refused(
                self._tid,
                self._ctx.user_id,
                needed,
                "SYNC",
                op.op_type,
                {"operation_id": str(op.id)},
                occurred_at=self._now,
                actor_subject=self._ctx.subject,
            )
            return OperationStatus.REJECTED, {"error": {"code": "PERMISSION_DENIED", "message": f"Missing {needed}"}}
        handlers: dict[str, Callable[[], BaseModel]] = {
            "METER_CAPTURE": lambda: MeterService(self._s, self._ctx, self._now).submit(
                MeterCaptureIn.model_validate(op.payload), device_session_id=device.id
            ),
            "EXPENSE": lambda: self._expense(ExpenseOp.model_validate(op.payload)),
            "FUEL_EVENT": lambda: ExpenseService(self._s, self._ctx, self._now).record_fuel(
                FuelEventOp.model_validate(op.payload), "SYNC"
            ),
            "CASH_COLLECTION": lambda: CashCustodyService(self._s, self._ctx, self._now).record_collection(
                CashCollectionOp.model_validate(op.payload), "SYNC"
            ),
            "CASH_HANDOVER": lambda: self._handover(CashHandoverOp.model_validate(op.payload)),
            "METER_RESET_REQUEST": lambda: self._meter_reset(MeterResetOp.model_validate(op.payload)),
            "METER_BASELINE": lambda: EngineHoursService(self._s, self._ctx, self._now).propose_baseline(
                BaselineIn.model_validate({"id": op.id, **op.payload})
            ),
            "METER_CORRECTION": lambda: EngineHoursService(self._s, self._ctx, self._now).propose_correction(
                CorrectionIn.model_validate(op.payload), device_session_id=device.id
            ),
            "CASH_TRANSFER": lambda: CashCustodyControls(self._s, self._ctx, self._now).record_transfer(
                CashTransferOp.model_validate(op.payload), "SYNC"
            ),
            "CASH_TRANSFER_ACKNOWLEDGEMENT": lambda: self._transfer_ack(CashTransferAckOp.model_validate(op.payload)),
            "CASH_FLOAT_ACKNOWLEDGEMENT": lambda: self._float_ack(op.id, CashFloatAckOp.model_validate(op.payload)),
            "CASH_RETENTION_REQUEST": lambda: CashCustodyControls(self._s, self._ctx, self._now).request_retention(
                CashRetentionOp.model_validate({**op.payload, "client_created_at": op.created_at_device}), "SYNC"
            ),
            "HOURS_PURCHASE": lambda: self._hours_purchase(
                HoursPurchaseOp.model_validate(
                    {"client_id": op.id, **op.payload, "client_created_at": op.created_at_device}
                )
            ),
            "DAILY_REPORT": lambda: self._daily_report(DailyReportOp.model_validate({"id": op.id, **op.payload})),
            "HOURS_TRANSFER_REQUEST": lambda: self._hours_transfer(
                HoursTransferOp.model_validate({"client_id": op.id, **op.payload})
            ),
            "PETTY_CASH_ACKNOWLEDGEMENT": lambda: self._petty_ack(op.id, PettyCashAckOp.model_validate(op.payload)),
            "PETTY_CASH_TOP_UP_REQUEST": lambda: self._petty_top_up(
                PettyCashTopUpOp.model_validate(
                    {"client_id": op.id, **op.payload, "client_created_at": op.created_at_device}
                )
            ),
            "PETTY_CASH_RETURN": lambda: self._petty_return(
                PettyCashReturnOp.model_validate(
                    {"client_id": op.id, **op.payload, "client_created_at": op.created_at_device}
                )
            ),
            "PETTY_CASH_COUNT": lambda: self._petty_count(
                PettyCashCountOp.model_validate(
                    {"client_id": op.id, **op.payload, "client_created_at": op.created_at_device}
                )
            ),
            "PETTY_CASH_ADVANCE_CLEARANCE": lambda: self._petty_clear(
                op.id, PettyCashAdvanceClearOp.model_validate(op.payload)
            ),
            "PETTY_CASH_HOLDER_CHANGE_ACKNOWLEDGEMENT": lambda: self._petty_holder(
                PettyCashHolderChangeOp.model_validate(op.payload)
            ),
            "MACHINE_REPORT": lambda: self._machine_report(
                MachineReportOp.model_validate({**op.payload, "id": op.id, "client_created_at": op.created_at_device}),
                device,
            ),
            "CREDIT_INVOICE_PAYMENT": lambda: self._invoice_payment(
                CreditInvoicePaymentOp.model_validate({**op.payload, "client_id": op.id})
            ),
            "PETTY_CASH_ADVANCE": lambda: self._petty().issue_advance(
                PettyCashAdvanceIn.model_validate(
                    {"client_id": op.id, **op.payload, "client_created_at": op.created_at_device}
                ),
                "SYNC",
            ),
        }
        try:
            with self._s.begin_nested():
                if capability := OP_CAPABILITY.get(op.op_type):
                    require_capability(self._s, self._tid, capability, self._now)
                dto = handlers[op.op_type]()
                return OperationStatus.ACKED, {"entity": dto.model_dump(mode="json")}
        except DependencyUnavailable:
            raise  # infrastructure failure: whole push fails, device retries everything (idempotent)
        except ValidationError as exc:
            return OperationStatus.REJECTED, {"error": {"code": "VALIDATION_FAILED", "message": str(exc)[:500]}}
        except (KeyError, ValueError) as exc:
            return OperationStatus.REJECTED, {"error": {"code": "BAD_PAYLOAD", "message": str(exc)[:500]}}
        except AppError as exc:
            status = OperationStatus.CONFLICT if is_conflict(op.op_type, exc.code) else OperationStatus.REJECTED
            return status, {"error": {"code": exc.code, "message": exc.message}, "server_state": self._state(op)}

    def _pending_uploads(self, op: OperationIn) -> list[str]:
        """Receipt uploads the op refers to that have not completed yet: defer (device retries), never reject."""
        key = UPLOAD_FIELDS.get(op.op_type)
        raw = op.payload.get(key) if key else None
        if isinstance(raw, str):
            raw = [raw]
        if not isinstance(raw, list):
            return []
        pending = []
        for value in raw:
            try:
                upload = self._s.get(BlobUploadSession, uuid.UUID(str(value)))
            except ValueError:
                continue  # malformed ids are rejected by payload validation
            if upload is not None and upload.status != "COMPLETE":
                pending.append(str(upload.id))
        return pending

    def _expense(self, body: ExpenseOp) -> BaseModel:
        attachments = list(body.receipt_attachment_ids)
        for upload_id in body.receipt_upload_ids:
            upload = self._s.get(BlobUploadSession, upload_id)
            if upload is None or upload.attachment_id is None:
                raise NotFound("Receipt upload not found", code="RECEIPT_NOT_FOUND")
            attachments.append(upload.attachment_id)
        expense = ExpenseIn.model_validate(
            {**body.model_dump(exclude={"receipt_upload_ids"}), "receipt_attachment_ids": attachments}
        )
        return ExpenseService(self._s, self._ctx, self._now).submit(expense, "SYNC")

    def _uploaded(self, upload_ids: list[uuid.UUID]) -> list[uuid.UUID]:
        out = []
        for upload_id in upload_ids:
            upload = self._s.get(BlobUploadSession, upload_id)
            if upload is None or upload.attachment_id is None:
                raise NotFound("Evidence upload not found", code="ATTACHMENT_NOT_FOUND")
            out.append(upload.attachment_id)
        return out

    def _hours_purchase(self, body: HoursPurchaseOp) -> BaseModel:
        evidence = self._uploaded(body.evidence_upload_ids)
        part_evidence = [self._uploaded(p.evidence_upload_ids) for p in body.payments]
        purchase = HoursPurchaseIn.model_validate(
            body.model_dump(exclude={"evidence_upload_ids": True, "payments": {"__all__": {"evidence_upload_ids"}}})
        )
        for part, extra in zip(purchase.payments, part_evidence, strict=True):
            part.evidence_attachment_ids = [*part.evidence_attachment_ids, *extra]
        if evidence:
            target = purchase.payment or (purchase.payments[0] if purchase.payments else None)
            if target is None:
                raise ValueError("evidence_upload_ids need a payment")
            target.evidence_attachment_ids = [*target.evidence_attachment_ids, *evidence]
        return HoursService(self._s, self._ctx, self._now).create_purchase(purchase, "SYNC")

    def _machine_report(self, body: MachineReportOp, device: DeviceSession) -> BaseModel:
        report = MachineReportIn.model_validate(body.model_dump(exclude={"photo_upload_id"}))
        if body.photo_upload_id is not None:
            if report.capture is None:
                raise ValueError("photo_upload_id belongs to a new reading (capture)")
            [photo] = self._uploaded([body.photo_upload_id])
            report.capture = report.capture.model_copy(update={"photo_attachment_id": photo})
        return MachineReportService(self._s, self._ctx, self._now).submit(report, "SYNC", device_session_id=device.id)

    def _invoice_payment(self, body: CreditInvoicePaymentOp) -> BaseModel:
        evidence = [*body.evidence_attachment_ids, *self._uploaded(body.evidence_upload_ids)]
        payment = CreditInvoicePaymentIn.model_validate(
            {**body.model_dump(exclude={"evidence_upload_ids", "invoice_id"}), "evidence_attachment_ids": evidence}
        )
        return CreditInvoiceService(self._s, self._ctx, self._now).record_payment(body.invoice_id, payment, "SYNC")

    def _hours_transfer(self, body: HoursTransferOp) -> BaseModel:
        evidence = list(body.evidence_attachment_ids)
        for upload_id in body.evidence_upload_ids:
            upload = self._s.get(BlobUploadSession, upload_id)
            if upload is None or upload.attachment_id is None:
                raise NotFound("Evidence upload not found", code="ATTACHMENT_NOT_FOUND")
            evidence.append(upload.attachment_id)
        transfer = TransferIn.model_validate(
            {**body.model_dump(exclude={"evidence_upload_ids"}), "evidence_attachment_ids": evidence}
        )
        return HoursApprovals(self._s, self._ctx, self._now).request_transfer(transfer)

    def _handover(self, body: CashHandoverOp) -> BaseModel:
        evidence = list(body.evidence_attachment_ids)
        for upload_id in body.evidence_upload_ids:
            upload = self._s.get(BlobUploadSession, upload_id)
            if upload is None or upload.attachment_id is None:
                raise NotFound("Evidence upload not found", code="ATTACHMENT_NOT_FOUND")
            evidence.append(upload.attachment_id)
        handover = CashHandoverIn.model_validate(
            {**body.model_dump(exclude={"evidence_upload_ids"}), "evidence_attachment_ids": evidence}
        )
        return CashCustodyService(self._s, self._ctx, self._now).record_handover(handover, "SYNC")

    def _daily_report(self, body: DailyReportOp) -> BaseModel:
        evidence = list(body.evidence_attachment_ids)
        for upload_id in body.evidence_upload_ids:
            upload = self._s.get(BlobUploadSession, upload_id)
            if upload is None or upload.attachment_id is None:
                raise NotFound("Evidence upload not found", code="ATTACHMENT_NOT_FOUND")
            evidence.append(upload.attachment_id)
        report = DailyReportIn.model_validate(
            {**body.model_dump(exclude={"evidence_upload_ids"}), "evidence_attachment_ids": evidence}
        )
        return DailyReportService(self._s, self._ctx, self._now).submit(report, "SYNC")

    def _meter_reset(self, body: MeterResetOp) -> BaseModel:
        evidence = body.evidence_attachment_id
        if body.evidence_upload_id is not None:
            upload = self._s.get(BlobUploadSession, body.evidence_upload_id)
            if upload is None or upload.attachment_id is None:
                raise NotFound("Evidence upload not found", code="ATTACHMENT_NOT_FOUND")
            evidence = upload.attachment_id
        reset = ResetIn.model_validate(
            {**body.model_dump(exclude={"evidence_upload_id"}), "evidence_attachment_id": evidence}
        )
        return MeterService(self._s, self._ctx, self._now).request_reset(reset)

    def _uploads(self, upload_ids: list[uuid.UUID]) -> list[uuid.UUID]:
        out = []
        for upload_id in upload_ids:
            upload = self._s.get(BlobUploadSession, upload_id)
            if upload is None or upload.attachment_id is None:
                raise NotFound("Evidence upload not found", code="ATTACHMENT_NOT_FOUND")
            out.append(upload.attachment_id)
        return out

    def _petty(self) -> PettyCashService:
        return PettyCashService(self._s, self._ctx, self._now)

    def _petty_ack(self, op_id: uuid.UUID, body: PettyCashAckOp) -> BaseModel:
        ack = PettyCashAcknowledgementIn.model_validate(body.model_dump(exclude={"movement_id"}))
        return self._petty().acknowledge_movement(body.movement_id, ack, op_id, "SYNC")

    def _petty_top_up(self, body: PettyCashTopUpOp) -> BaseModel:
        req = TopUpRequestIn.model_validate(body.model_dump(exclude={"fund_id"}))
        return self._petty().request_top_up(body.fund_id, req, "SYNC")

    def _petty_return(self, body: PettyCashReturnOp) -> BaseModel:
        evidence = [*body.evidence_attachment_ids, *self._uploads(body.evidence_upload_ids)]
        claim = PettyCashReturnIn.model_validate(
            {**body.model_dump(exclude={"evidence_upload_ids"}), "evidence_attachment_ids": evidence}
        )
        return self._petty().claim_return(claim, "SYNC")

    def _petty_count(self, body: PettyCashCountOp) -> BaseModel:
        evidence = [*body.evidence_attachment_ids, *self._uploads(body.evidence_upload_ids)]
        count = PettyCashCountIn.model_validate(
            {**body.model_dump(exclude={"evidence_upload_ids"}), "evidence_attachment_ids": evidence}
        )
        return self._petty().record_count(count, "SYNC")

    def _petty_clear(self, op_id: uuid.UUID, body: PettyCashAdvanceClearOp) -> BaseModel:
        clear = PettyCashAdvanceClearIn.model_validate(body.model_dump(exclude={"advance_id"}))
        return self._petty().clear_advance(body.advance_id, clear, op_id, "SYNC")

    def _petty_holder(self, body: PettyCashHolderChangeOp) -> BaseModel:
        decision = PettyCashHolderChangeDecisionIn.model_validate(body.model_dump(exclude={"holder_change_id"}))
        return self._petty().decide_holder_change(body.holder_change_id, decision, "SYNC")

    def _transfer_ack(self, body: CashTransferAckOp) -> BaseModel:
        ack = CashAcknowledgementIn.model_validate(body.model_dump(exclude={"transfer_id"}))
        return CashCustodyControls(self._s, self._ctx, self._now).acknowledge_transfer(body.transfer_id, ack, "SYNC")

    def _float_ack(self, op_id: uuid.UUID, body: CashFloatAckOp) -> BaseModel:
        ack = CashAcknowledgementIn.model_validate(body.model_dump(exclude={"entry_id"}))
        return CashCustodyControls(self._s, self._ctx, self._now).acknowledge_float(body.entry_id, ack, op_id, "SYNC")

    def _state(self, op: OperationIn) -> dict[str, Any]:
        """The server state a CONFLICT carries back: for a machine report, the machine's report state now."""
        machine_id = op.payload.get("machine_id") if op.op_type == "MACHINE_REPORT" else None
        if not machine_id:
            return {}
        try:
            states = MachineReportService(self._s, self._ctx, self._now).statuses([uuid.UUID(str(machine_id))])
        except (AppError, ValueError):
            return {}
        return {"machine_report_state": states[0].model_dump(mode="json")} if states else {}
