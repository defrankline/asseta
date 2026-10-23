"""Supervisor inbox for sync pull: the caller's own field records, so they stay visible on the device after sync.

Each stream is paged by `sync_revision` exactly like jobs (PAGE rows, `has_more` when more remain). Bootstrap ships
a recent window (WINDOW) plus everything still open; deltas ship anything changed above the cursor. Meter captures
are immutable but their findings are reviewed later, so a capture's revision is the highest of the capture and its
findings: a review re-delivers the capture with the new review state.
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import ColumnElement, Select, and_, exists, func, or_, select
from sqlalchemy.orm import Session

from asseta.modules.expenses.models import ApprovalRequest, Expense, ExpenseAttachment, ExpenseStatus, FuelEvent
from asseta.modules.expenses.service import SUBJECT, own_expense_filter, own_fuel_filter
from asseta.modules.finance.dto import HireAllocationDto
from asseta.modules.finance.models import (
    CashHandover,
    CustomerPayment,
    HirePaymentAllocation,
    HirePaymentMethod,
    SettlementStatus,
)
from asseta.modules.fleet.models import StaffMember
from asseta.modules.identity.principal import RequestContext
from asseta.modules.jobs.models import CustomerAcknowledgement, Job, JobActivity, JobStatus
from asseta.modules.jobs.scope import job_filter, scoped_job_ids
from asseta.modules.meter.dto import ExceptionDto
from asseta.modules.meter.models import CaptureState, ExceptionStatus, JobException, MeterCapture, MeterResetEvent
from asseta.modules.meter.service import own_capture_filter, own_reset_filter
from asseta.modules.sync.dto import (
    SyncAcknowledgementDto,
    SyncCashCollectionDto,
    SyncCashHandoverDto,
    SyncExpenseDto,
    SyncFuelEventDto,
    SyncJobActivityDto,
    SyncMeterCaptureDto,
    SyncMeterResetDto,
)

WINDOW = timedelta(days=30)
OPEN_JOB_STATES = (JobStatus.APPROVED, JobStatus.IN_PROGRESS)


@dataclass
class Stream:
    items: list[Any] = field(default_factory=list)
    has_more: bool = False
    last_revision: int = 0


@dataclass
class Inbox:
    meter_captures: Stream
    meter_resets: Stream
    job_activities: Stream
    acknowledgements: Stream
    expenses: Stream
    fuel_events: Stream
    cash_collections: Stream
    cash_handovers: Stream

    def streams(self) -> list[Stream]:
        return list(vars(self).values())


class InboxReader:
    def __init__(self, session: Session, ctx: RequestContext, now: datetime, staff: StaffMember | None, page: int):
        self._s, self._ctx, self._staff, self._page = session, ctx, staff, page
        self._since = now - WINDOW

    def read(self, min_revision: int | None) -> Inbox:
        perms = self._ctx.permissions
        meter = bool({"tenant.meter.capture", "tenant.meter.read"} & perms)
        field_log = bool({"tenant.job.log", "tenant.job.read"} & perms)
        spend = bool({"tenant.expense.read", "tenant.expense.write"} & perms)
        cash = "tenant.collection.record" in perms and self._staff is not None
        return Inbox(
            meter_captures=self._captures(min_revision) if meter else Stream(),
            meter_resets=self._resets(min_revision) if meter else Stream(),
            job_activities=self._activities(min_revision) if field_log else Stream(),
            acknowledgements=self._acknowledgements(min_revision) if field_log else Stream(),
            expenses=self._expenses(min_revision) if spend else Stream(),
            fuel_events=self._fuel(min_revision) if spend else Stream(),
            cash_collections=self._collections(min_revision) if cash else Stream(),
            cash_handovers=self._handovers(min_revision) if cash else Stream(),
        )

    # --- paging -------------------------------------------------------------------------------------------------
    def _paged(
        self,
        model: Any,
        own: ColumnElement[bool],
        min_revision: int | None,
        bootstrap: ColumnElement[bool],
        revision: Any = None,
    ) -> tuple[list[Any], list[int], bool]:
        rev = model.sync_revision if revision is None else revision
        stmt: Select[Any] = select(model, rev.label("rev")).where(own)
        stmt = stmt.where(bootstrap) if min_revision is None else stmt.where(rev > min_revision)
        rows = list(self._s.execute(stmt.order_by(rev, model.id).limit(self._page + 1)).all())
        has_more = len(rows) > self._page
        rows = rows[: self._page]
        return [r[0] for r in rows], [int(r[1]) for r in rows], has_more

    @staticmethod
    def _stream(items: list[Any], revs: list[int], has_more: bool) -> Stream:
        return Stream(items, has_more, revs[-1] if revs else 0)

    def _open_jobs(self) -> Select[uuid.UUID]:
        return select(Job.id).where(job_filter(self._staff), Job.status.in_(OPEN_JOB_STATES))

    # --- streams ------------------------------------------------------------------------------------------------
    def _captures(self, min_revision: int | None) -> Stream:
        finding_rev = (
            select(func.max(JobException.sync_revision))
            .where(JobException.meter_capture_id == MeterCapture.id)
            .correlate(MeterCapture)
            .scalar_subquery()
        )
        revision = func.greatest(MeterCapture.sync_revision, func.coalesce(finding_rev, 0))
        open_finding = exists().where(
            JobException.meter_capture_id == MeterCapture.id, JobException.status == ExceptionStatus.OPEN
        )
        bootstrap = or_(MeterCapture.captured_at >= self._since, MeterCapture.state == CaptureState.PROVISIONAL)
        rows, revs, more = self._paged(
            MeterCapture,
            own_capture_filter(self._ctx, self._staff),
            min_revision,
            or_(bootstrap, open_finding),
            revision,
        )
        findings: dict[uuid.UUID, list[ExceptionDto]] = defaultdict(list)
        if rows:
            stmt = select(JobException).where(JobException.meter_capture_id.in_([r.id for r in rows]))
            for e in self._s.execute(stmt.order_by(JobException.created_at, JobException.id)).scalars():
                assert e.meter_capture_id is not None
                findings[e.meter_capture_id].append(ExceptionDto.model_validate(e))
        out = []
        for row, rev in zip(rows, revs, strict=True):
            dto = SyncMeterCaptureDto.model_validate(row)
            dto.sync_revision, dto.findings = rev, findings[row.id]
            if dto.findings:
                pending = any(f.status is ExceptionStatus.OPEN for f in dto.findings)
                dto.review_status = "PENDING_REVIEW" if pending else "REVIEWED"
            out.append(dto)
        return self._stream(out, revs, more)

    def _resets(self, min_revision: int | None) -> Stream:
        bootstrap = or_(MeterResetEvent.created_at >= self._since, MeterResetEvent.status == "PENDING")
        rows, revs, more = self._paged(
            MeterResetEvent, own_reset_filter(self._ctx, self._staff), min_revision, bootstrap
        )
        return self._stream([SyncMeterResetDto.model_validate(r) for r in rows], revs, more)

    def _activities(self, min_revision: int | None) -> Stream:
        own = or_(JobActivity.recorded_by == self._ctx.user_id, JobActivity.job_id.in_(scoped_job_ids(self._staff)))
        bootstrap = or_(JobActivity.started_at >= self._since, JobActivity.job_id.in_(self._open_jobs()))
        rows, revs, more = self._paged(JobActivity, own, min_revision, bootstrap)
        out = []
        for a in rows:
            dto = SyncJobActivityDto.model_validate(a)
            if a.ended_at is not None:
                dto.duration_minutes = int((a.ended_at - a.started_at).total_seconds() // 60)
            out.append(dto)
        return self._stream(out, revs, more)

    def _acknowledgements(self, min_revision: int | None) -> Stream:
        ack = CustomerAcknowledgement
        own = or_(ack.recorded_by == self._ctx.user_id, ack.job_id.in_(scoped_job_ids(self._staff)))
        bootstrap = or_(ack.captured_at >= self._since, ack.job_id.in_(self._open_jobs()))
        rows, revs, more = self._paged(ack, own, min_revision, bootstrap)
        return self._stream([SyncAcknowledgementDto.model_validate(a) for a in rows], revs, more)

    def _expenses(self, min_revision: int | None) -> Stream:
        bootstrap = or_(Expense.incurred_at >= self._since, Expense.status == ExpenseStatus.PENDING_APPROVAL)
        rows, revs, more = self._paged(Expense, own_expense_filter(self._ctx, self._staff), min_revision, bootstrap)
        ids = [e.id for e in rows]
        receipts: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
        approvals: dict[uuid.UUID, uuid.UUID] = {}
        if ids:
            linked = (
                select(ExpenseAttachment.expense_id, ExpenseAttachment.attachment_id)
                .where(ExpenseAttachment.expense_id.in_(ids))
                .order_by(ExpenseAttachment.created_at, ExpenseAttachment.attachment_id)
            )
            for expense_id, attachment_id in self._s.execute(linked).all():
                receipts[expense_id].append(attachment_id)
            requests = select(ApprovalRequest.subject_id, ApprovalRequest.id).where(
                ApprovalRequest.subject_type == SUBJECT, ApprovalRequest.subject_id.in_(ids)
            )
            approvals = dict(self._s.execute(requests).all())
        out = []
        for e in rows:
            dto = SyncExpenseDto.model_validate(e)
            dto.receipt_attachment_ids, dto.approval_request_id = receipts[e.id], approvals.get(e.id)
            out.append(dto)
        return self._stream(out, revs, more)

    def _fuel(self, min_revision: int | None) -> Stream:
        rows, revs, more = self._paged(
            FuelEvent, own_fuel_filter(self._ctx), min_revision, FuelEvent.occurred_at >= self._since
        )
        return self._stream([SyncFuelEventDto.model_validate(f) for f in rows], revs, more)

    def _collections(self, min_revision: int | None) -> Stream:
        assert self._staff is not None
        own = and_(
            CustomerPayment.received_by_staff_id == self._staff.id, CustomerPayment.method == HirePaymentMethod.CASH
        )
        bootstrap = or_(CustomerPayment.received_at >= self._since, CustomerPayment.status == SettlementStatus.CLAIMED)
        rows, revs, more = self._paged(CustomerPayment, own, min_revision, bootstrap)
        allocations: dict[uuid.UUID, list[HireAllocationDto]] = defaultdict(list)
        if rows:
            stmt = (
                select(HirePaymentAllocation)
                .where(HirePaymentAllocation.payment_id.in_([p.id for p in rows]))
                .order_by(HirePaymentAllocation.created_at)
            )
            for a in self._s.execute(stmt).scalars():
                allocations[a.payment_id].append(HireAllocationDto.model_validate(a))
        out = []
        for p in rows:
            dto = SyncCashCollectionDto.model_validate(p)
            dto.allocations = allocations[p.id]
            out.append(dto)
        return self._stream(out, revs, more)

    def _handovers(self, min_revision: int | None) -> Stream:
        assert self._staff is not None
        own = CashHandover.staff_member_id == self._staff.id
        bootstrap = or_(CashHandover.handed_at >= self._since, CashHandover.status == SettlementStatus.CLAIMED)
        rows, revs, more = self._paged(CashHandover, own, min_revision, bootstrap)
        return self._stream([SyncCashHandoverDto.model_validate(h) for h in rows], revs, more)
