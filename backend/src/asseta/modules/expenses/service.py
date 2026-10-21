"""Expense capture under the versioned EXPENSE_CAPTURE policy (receipt/GPS requirements, approval limits),
approvals with segregation of duties, and fuel events with cost attribution. The policy version evaluated is
stamped on every expense so later policy changes never rewrite accepted history."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound
from asseta.core.money import quantize
from asseta.core.outbox import OutboxWriter
from asseta.modules.expenses.dto import (
    ApprovalDecisionIn,
    ApprovalRequestDto,
    ExpenseCategoryDto,
    ExpenseCategoryIn,
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
    ExpensePaidFrom,
    ExpenseStatus,
    FuelEvent,
    FuelEventType,
)
from asseta.modules.finance.common import currency_or_default, insert, resolve_custodian, tenant_settings
from asseta.modules.fleet.models import Machine
from asseta.modules.identity.principal import RequestContext
from asseta.modules.jobs.models import Job
from asseta.modules.meter.models import CaptureAttachment, GpsStatus
from asseta.modules.platform_billing.models_commercial import Currency
from asseta.modules.policy.service import PolicyService

TOPIC = "asseta.expenses"
SUBJECT = "EXPENSE"


def expense_dto(session: Session, e: Expense) -> ExpenseDto:
    dto = ExpenseDto.model_validate(e)
    dto.receipt_attachment_ids = list(
        session.execute(
            select(ExpenseAttachment.attachment_id)
            .where(ExpenseAttachment.expense_id == e.id)
            .order_by(ExpenseAttachment.created_at, ExpenseAttachment.attachment_id)
        ).scalars()
    )
    dto.approval_request_id = session.execute(
        select(ApprovalRequest.id).where(ApprovalRequest.subject_type == SUBJECT, ApprovalRequest.subject_id == e.id)
    ).scalar_one_or_none()
    return dto


class ExpenseService:
    def __init__(self, session: Session, ctx: RequestContext, now: datetime):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid, self._now = session, ctx, ctx.tenant_id, now
        self._audit = AuditService(session)

    def create_category(self, body: ExpenseCategoryIn) -> ExpenseCategoryDto:
        row = ExpenseCategory(id=uuid.uuid4(), tenant_id=self._tid, code=body.code, name=body.name, is_active=True)
        insert(self._s, row, "DUPLICATE_EXPENSE_CATEGORY", "Expense category code already exists")
        self._s.refresh(row)  # server-assigned sync_revision
        self._audit.record(
            actor=self._ctx.audit_actor(),
            action="expense.category.created",
            entity_type="expense_category",
            entity_id=row.id,
            tenant_id=self._tid,
            after={"code": row.code, "name": row.name},
        )
        return ExpenseCategoryDto.model_validate(row)

    def _attribution(self, machine_id: uuid.UUID | None, job_id: uuid.UUID | None) -> uuid.UUID | None:
        if job_id is not None:
            job = self._s.get(Job, job_id)
            if job is None:
                raise NotFound("Job not found")
            if machine_id is not None and machine_id != job.machine_id:
                raise BusinessRuleViolation("machine_id does not match the job's machine", code="ATTRIBUTION_MISMATCH")
            return job.machine_id
        if machine_id is not None and self._s.get(Machine, machine_id) is None:
            raise NotFound("Machine not found")
        return machine_id

    def submit(self, body: ExpenseIn, source: str = "API") -> ExpenseDto:
        if body.client_id is not None:
            existing = self._s.execute(select(Expense).where(Expense.client_id == body.client_id)).scalar_one_or_none()
            if existing is not None:
                return expense_dto(self._s, existing)  # offline retry: exactly one expense
        category = self._s.get(ExpenseCategory, body.category_id)
        if category is None or not category.is_active:
            raise NotFound("Expense category not found or inactive")
        currency = currency_or_default(self._s, self._tid, body.currency)
        machine_id = self._attribution(body.machine_id, body.job_id)
        custodian = None
        if body.paid_from is ExpensePaidFrom.CASH_CUSTODY:
            custodian = resolve_custodian(self._s, self._ctx, body.custodian_staff_id).id
        elif body.custodian_staff_id is not None:
            raise BusinessRuleViolation("custodian_staff_id applies to CASH_CUSTODY only", code="CUSTODIAN_NOT_ALLOWED")
        eff = PolicyService(self._s).expense_capture(self._tid, at=body.incurred_at)
        policy, in_base = eff.policy, currency == tenant_settings(self._s, self._tid).currency
        receipt_required = not in_base or body.amount > policy.receipt_required_above
        receipts = list(dict.fromkeys(body.receipt_attachment_ids))
        for att in receipts:
            if self._s.get(CaptureAttachment, att) is None:
                raise NotFound("Receipt attachment not found", code="RECEIPT_NOT_FOUND")
        if receipt_required and not receipts:
            why = f"above {policy.receipt_required_above} {currency}" if in_base else "in a foreign currency"
            raise BusinessRuleViolation(f"A receipt is required for expenses {why}", code="RECEIPT_REQUIRED")
        gps = body.gps
        if policy.gps_required and (
            gps is None
            or gps.status is not GpsStatus.FIX
            or gps.accuracy_m is None
            or gps.accuracy_m > policy.gps_max_accuracy_m
        ):
            raise BusinessRuleViolation(
                f"A GPS fix with accuracy <= {policy.gps_max_accuracy_m} m is required", code="GPS_REQUIRED"
            )
        auto = in_base and body.amount <= policy.auto_approve_limit
        row = Expense(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            client_id=body.client_id,
            category_id=category.id,
            supplier=body.supplier,
            description=body.description,
            amount=body.amount,
            currency=currency,
            incurred_at=body.incurred_at,
            machine_id=machine_id,
            job_id=body.job_id,
            paid_from=body.paid_from,
            custodian_staff_id=custodian,
            status=ExpenseStatus.APPROVED if auto else ExpenseStatus.PENDING_APPROVAL,
            policy_version=eff.version_stamp,
            receipt_required=receipt_required,
            gps_status=gps.status.value if gps else None,
            latitude=gps.latitude if gps else None,
            longitude=gps.longitude if gps else None,
            gps_accuracy_m=gps.accuracy_m if gps else None,
            source=source,
            device_id=body.device_id,
            submitted_by=self._ctx.user_id,
            submitted_at=self._now,
            decided_at=self._now if auto else None,
            decision_note=f"Auto-approved: amount <= {policy.auto_approve_limit} ({eff.version_stamp})"
            if auto
            else None,
        )
        insert(self._s, row, "DUPLICATE_EXPENSE", "Expense already recorded")
        self._s.add_all(
            ExpenseAttachment(id=uuid.uuid4(), tenant_id=self._tid, expense_id=row.id, attachment_id=a)
            for a in receipts
        )
        if not auto:
            limit = policy.auto_approve_limit if in_base else "foreign currency"
            self._s.add(
                ApprovalRequest(
                    id=uuid.uuid4(),
                    tenant_id=self._tid,
                    subject_type=SUBJECT,
                    subject_id=row.id,
                    amount=row.amount,
                    currency=currency,
                    reason=f"Amount {row.amount} {currency} exceeds the auto-approval limit ({limit})",
                    policy_version=eff.version_stamp,
                    status=ApprovalStatus.PENDING,
                    requested_by=self._ctx.user_id,
                    requested_at=self._now,
                )
            )
        self._s.flush()
        self._audit.record(
            actor=self._ctx.audit_actor(source.lower()),
            action="expense.submitted",
            entity_type="expense",
            entity_id=row.id,
            tenant_id=self._tid,
            after={"amount": str(row.amount), "currency": currency, "status": row.status.value},
            policy_version=eff.version_stamp,
        )
        if auto:
            self._approved_event(row)
        return expense_dto(self._s, row)

    def _approved_event(self, e: Expense) -> None:
        OutboxWriter(self._s).emit(
            topic=TOPIC,
            event_type="ExpenseApproved",
            key=str(e.machine_id or e.id),
            payload={
                "expense_id": str(e.id),
                "amount": str(e.amount),
                "currency": e.currency,
                "paid_from": e.paid_from.value,
                "auto": e.decided_by is None,
                "policy_version": e.policy_version,
            },
            tenant_id=self._tid,
        )

    def decide(self, approval_id: uuid.UUID, body: ApprovalDecisionIn) -> ApprovalRequestDto:
        req = self._s.execute(
            select(ApprovalRequest).where(ApprovalRequest.id == approval_id).with_for_update()
        ).scalar_one_or_none()
        if req is None:
            raise NotFound("Approval request not found")
        if req.status is not ApprovalStatus.PENDING:
            raise Conflict(f"Approval already {req.status.value}", code="APPROVAL_ALREADY_DECIDED")
        if req.requested_by == self._ctx.user_id:
            raise BusinessRuleViolation("Submitters cannot approve their own expenses", code="SEGREGATION_OF_DUTIES")
        expense = self._s.execute(select(Expense).where(Expense.id == req.subject_id).with_for_update()).scalar_one()
        req.status = ApprovalStatus.APPROVED if body.approve else ApprovalStatus.REJECTED
        req.decided_by, req.decided_at, req.decision_note = self._ctx.user_id, self._now, body.note
        expense.status = ExpenseStatus.APPROVED if body.approve else ExpenseStatus.REJECTED
        expense.decided_by, expense.decided_at, expense.decision_note = self._ctx.user_id, self._now, body.note
        self._s.flush()
        self._audit.record(
            actor=self._ctx.audit_actor(),
            action=f"expense.{expense.status.value.lower()}",
            entity_type="expense",
            entity_id=expense.id,
            tenant_id=self._tid,
            before={"status": "PENDING_APPROVAL"},
            after={"status": expense.status.value, "amount": str(expense.amount), "approval_id": str(req.id)},
            reason=body.note,
            policy_version=req.policy_version,
        )
        if body.approve:
            self._approved_event(expense)
        return ApprovalRequestDto.model_validate(req)

    def record_fuel(self, body: FuelEventIn, source: str = "API") -> FuelEventDto:
        if body.client_id is not None:
            existing = self._s.execute(
                select(FuelEvent).where(FuelEvent.client_id == body.client_id)
            ).scalar_one_or_none()
            if existing is not None:
                return FuelEventDto.model_validate(existing)
        currency = currency_or_default(self._s, self._tid, body.currency)
        machine_id = self._attribution(body.machine_id, body.job_id)
        if body.expense_id is not None:
            linked = self._s.get(Expense, body.expense_id)
            if linked is None:
                raise NotFound("Expense not found")
            if linked.currency != currency:
                raise BusinessRuleViolation("Fuel purchase currency must match its expense", code="CURRENCY_MISMATCH")
        minor = self._s.get(Currency, currency)
        assert minor is not None
        cost = Decimal(0)
        if body.event_type is not FuelEventType.USAGE and body.unit_price is not None:
            cost = quantize(body.litres * body.unit_price, minor.minor_units)
        row = FuelEvent(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            client_id=body.client_id,
            event_type=body.event_type,
            litres=body.litres,
            unit_price=body.unit_price if body.event_type is not FuelEventType.USAGE else None,
            attributed_cost=cost,
            currency=currency,
            machine_id=machine_id,
            job_id=body.job_id,
            expense_id=body.expense_id,
            meter_reading=body.meter_reading,
            supplier=body.supplier,
            occurred_at=body.occurred_at,
            note=body.note,
            source=source,
            recorded_by=self._ctx.user_id,
            recorded_at=self._now,
        )
        insert(self._s, row, "DUPLICATE_FUEL_EVENT", "Fuel event already recorded")
        self._audit.record(
            actor=self._ctx.audit_actor(source.lower()),
            action="expense.fuel.recorded",
            entity_type="fuel_event",
            entity_id=row.id,
            tenant_id=self._tid,
            after={"type": row.event_type.value, "litres": str(row.litres), "cost": str(cost), "currency": currency},
        )
        return FuelEventDto.model_validate(row)
