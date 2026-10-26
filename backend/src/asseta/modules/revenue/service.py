"""Revenue reconciliation use cases (DEC-031 R2/R3): the daily machine sheet (list, machine-day detail, CSV), the
tenant's revenue reason list (full lifecycle) and revenue differences (list, get, explain, decide).

Explaining and deciding are separate permissions; the person who proposed an explanation can never decide on it
(refusals are recorded as segregation-of-duties signals). Neutral wording throughout: a difference is "to explain"."""

import csv
import io
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound
from asseta.core.lifecycle import check_version, flush_versioned, mark_active, mark_inactive
from asseta.core.outbox import OutboxWriter
from asseta.core.search import ilike_any
from asseta.core.signals import sod_violation
from asseta.modules.fleet.models import Machine
from asseta.modules.identity.principal import RequestContext
from asseta.modules.intelligence.models import AnomalyCase
from asseta.modules.jobs.models import Job, JobActivity
from asseta.modules.policy.service import PolicyService
from asseta.modules.revenue.dto import (
    DailyMachineSheetDetailDto,
    DailyMachineSheetRowDto,
    NonRevenueActivityDto,
    NonRevenueApprovalDto,
    NonRevenueApprovalIn,
    NonRevenueDecisionIn,
    RevenueAdjustmentDto,
    RevenueDecisionIn,
    RevenueDifferenceDto,
    RevenueExplanationIn,
    RevenueReasonDto,
    RevenueReasonIn,
    RevenueReasonUpdateIn,
)
from asseta.modules.revenue.models import (
    NonRevenueApproval,
    NonRevenueApprovalStatus,
    RevenueDifference,
    RevenueDifferenceAdjustment,
    RevenueDifferenceStatus,
    RevenueReason,
)
from asseta.modules.revenue.reconciliation import TOPIC, recompute_after_change
from asseta.modules.revenue.sheet import DailySheet

MAX_SHEET_DAYS = 93
DEFAULT_SHEET_DAYS = 7


class RevenueService:
    def __init__(self, session: Session, ctx: RequestContext, now: datetime):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid, self._now = session, ctx, ctx.tenant_id, now
        self._audit = AuditService(session)

    def _record(
        self,
        action: str,
        entity: str,
        entity_id: uuid.UUID | str,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
        reason: str | None = None,
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
        )

    # --- daily machine sheet ----------------------------------------------------------------------------------
    def _range(self, day_from: date | None, day_to: date | None) -> tuple[date, date]:
        sheet = DailySheet(self._s, self._tid, self._now)
        today = self._now.astimezone(sheet.tz).date()
        day_to = day_to or today
        day_from = day_from or day_to - timedelta(days=DEFAULT_SHEET_DAYS - 1)
        if day_from > day_to:
            raise BusinessRuleViolation("day_from must not be after day_to", code="INVALID_RANGE")
        if (day_to - day_from).days + 1 > MAX_SHEET_DAYS:
            raise BusinessRuleViolation(f"At most {MAX_SHEET_DAYS} days per request", code="RANGE_TOO_LONG")
        return day_from, day_to

    def machine(self, machine_id: uuid.UUID) -> Machine:
        row = self._s.get(Machine, machine_id)
        if row is None:
            raise NotFound("Machine not found", code="MACHINE_NOT_FOUND")
        return row

    def sheet_rows(
        self,
        q: str | None,
        machine_id: uuid.UUID | None,
        site_id: uuid.UUID | None,
        day_from: date | None,
        day_to: date | None,
    ) -> list[DailyMachineSheetRowDto]:
        first, last = self._range(day_from, day_to)
        stmt = select(Machine).order_by(Machine.asset_code)
        if machine_id is not None:
            stmt = stmt.where(Machine.id == machine_id)
        if (match := ilike_any(q, Machine.asset_code, Machine.name)) is not None:
            stmt = stmt.where(match)
        machines = list(self._s.execute(stmt).scalars())
        rows = DailySheet(self._s, self._tid, self._now).rows(machines, first, last, site_id)
        return sorted(rows, key=lambda r: (r.day, r.machine_code or ""), reverse=True)

    def sheet_detail(self, machine_id: uuid.UUID, day: date) -> DailyMachineSheetDetailDto:
        return DailySheet(self._s, self._tid, self._now).detail(self.machine(machine_id), day)

    def sheet_csv(self, rows: list[DailyMachineSheetRowDto]) -> str:
        currencies = sorted({m.currency for r in rows for m in r.money})
        types = sorted({t for r in rows for t in r.non_revenue_by_type})
        header = [
            "day",
            "machine_code",
            "machine_name",
            "first_reading",
            "last_reading",
            "reading_count",
            "engine_hours",
            "customer_work_hours",
            "non_revenue_hours",
            *(f"non_revenue_{t.lower()}_hours" for t in types),
            "revenue_hours",
            "approved_non_customer_hours",
            "identified_variance_hours",
            "unexplained_hours",
            "pending_review_hours",
            "fuel_litres",
            "fuel_litres_per_engine_hour",
            "jobs",
            "customers",
            *(f"{c}_{k}" for c in currencies for k in ("expected", "in_progress", "attributed", "difference")),
            "flags",
        ]
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(header)
        for r in rows:
            money = {m.currency: m for m in r.money}
            writer.writerow(
                [
                    r.day.isoformat(),
                    r.machine_code,
                    r.machine_name,
                    r.first_reading,
                    r.last_reading,
                    r.reading_count,
                    r.engine_hours,
                    r.customer_work_hours,
                    r.non_revenue_hours,
                    *(r.non_revenue_by_type.get(t, "") for t in types),
                    r.revenue_hours,
                    r.approved_non_customer_hours,
                    r.identified_variance_hours,
                    r.unexplained_hours,
                    r.pending_review_hours,
                    r.fuel_litres,
                    r.fuel_litres_per_engine_hour if r.fuel_litres_per_engine_hour is not None else "",
                    "; ".join(j.job_number or str(j.job_id) for j in r.jobs),
                    "; ".join(sorted({j.customer_name or "" for j in r.jobs} - {""})),
                    *(
                        getattr(money[c], k) if c in money else ""
                        for c in currencies
                        for k in ("expected", "in_progress", "attributed", "difference")
                    ),
                    " ".join(f.value for f in r.flags),
                ]
            )
        self._audit.record(
            actor=self._ctx.audit_actor(),
            action="report.exported",
            entity_type="report",
            entity_id="daily-machine-sheet",
            tenant_id=self._tid,
            after={"format": "csv", "rows": len(rows)},
        )
        return buf.getvalue()

    # --- reasons ----------------------------------------------------------------------------------------------
    def reason(self, reason_id: uuid.UUID, lock: bool = False) -> RevenueReason:
        stmt = select(RevenueReason).where(RevenueReason.id == reason_id)
        row = self._s.execute(stmt.with_for_update() if lock else stmt).scalar_one_or_none()
        if row is None:
            raise NotFound("Reason not found", code="REVENUE_REASON_NOT_FOUND")
        return row

    @staticmethod
    def reason_query(q: str | None, include_inactive: bool) -> Select[RevenueReason]:
        stmt = select(RevenueReason).order_by(RevenueReason.code)
        if (match := ilike_any(q, RevenueReason.code, RevenueReason.name)) is not None:
            stmt = stmt.where(match)
        return stmt if include_inactive else stmt.where(RevenueReason.is_active.is_(True))

    def create_reason(self, body: RevenueReasonIn) -> RevenueReasonDto:
        row = RevenueReason(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            code=body.code,
            name=body.name,
            description=body.description,
            is_active=True,
        )
        try:
            with self._s.begin_nested():
                self._s.add(row)
                self._s.flush()
        except IntegrityError as exc:
            raise Conflict("A reason with this code already exists", code="DUPLICATE_REASON") from exc
        dto = RevenueReasonDto.model_validate(row)
        self._record("revenue.reason.created", "revenue_reason", row.id, None, dto.model_dump(mode="json"))
        return dto

    def update_reason(self, reason_id: uuid.UUID, body: RevenueReasonUpdateIn) -> RevenueReasonDto:
        row = self.reason(reason_id, lock=True)
        check_version(row.version, body.version, "Reason")
        before = RevenueReasonDto.model_validate(row).model_dump(mode="json")
        row.code, row.name, row.description = body.code, body.name, body.description
        flush_versioned(self._s, "Reason", "DUPLICATE_REASON", "A reason with this code already exists")
        dto = RevenueReasonDto.model_validate(row)
        self._record("revenue.reason.updated", "revenue_reason", row.id, before, dto.model_dump(mode="json"))
        return dto

    def set_reason_active(
        self, reason_id: uuid.UUID, active: bool, reason: str, version: int | None
    ) -> RevenueReasonDto:
        """Deactivated entries are refused for new explanations; past explanations keep them."""
        row = self.reason(reason_id, lock=True)
        check_version(row.version, version, "Reason")
        if active:
            mark_active(row, "Reason")
        else:
            mark_inactive(row, self._ctx.user_id, reason, "Reason")
        flush_versioned(self._s, "Reason")
        dto = RevenueReasonDto.model_validate(row)
        verb = "reactivated" if active else "deactivated"
        self._record(f"revenue.reason.{verb}", "revenue_reason", row.id, None, {"is_active": active}, reason)
        return dto

    # --- differences ------------------------------------------------------------------------------------------
    def difference(self, difference_id: uuid.UUID, lock: bool = False) -> RevenueDifference:
        stmt = select(RevenueDifference).where(RevenueDifference.id == difference_id)
        row = self._s.execute(stmt.with_for_update() if lock else stmt).scalar_one_or_none()
        if row is None:
            raise NotFound("Revenue difference not found", code="REVENUE_DIFFERENCE_NOT_FOUND")
        return row

    @staticmethod
    def difference_query(
        q: str | None,
        status: RevenueDifferenceStatus | None,
        machine_id: uuid.UUID | None,
        day_from: date | None,
        day_to: date | None,
    ) -> Select[RevenueDifference]:
        stmt = select(RevenueDifference).order_by(
            RevenueDifference.local_from.desc(), RevenueDifference.opened_at.desc(), RevenueDifference.id
        )
        if status is not None:
            stmt = stmt.where(RevenueDifference.status == status)
        if machine_id is not None:
            stmt = stmt.where(RevenueDifference.machine_id == machine_id)
        if day_from is not None:
            stmt = stmt.where(RevenueDifference.local_to >= day_from)
        if day_to is not None:
            stmt = stmt.where(RevenueDifference.local_from <= day_to)
        if (match := ilike_any(q, Machine.asset_code, Machine.name, RevenueDifference.period_key)) is not None:
            stmt = stmt.join(Machine, Machine.id == RevenueDifference.machine_id).where(match)
        return stmt

    def difference_dtos(self, rows: list[RevenueDifference]) -> list[RevenueDifferenceDto]:
        reasons = (
            dict(
                self._s.execute(
                    select(RevenueReason.id, RevenueReason.name).where(
                        RevenueReason.id.in_({r.reason_id for r in rows if r.reason_id})
                    )
                ).all()
            )
            if any(r.reason_id for r in rows)
            else {}
        )
        cases = (
            dict(
                self._s.execute(
                    select(AnomalyCase.id, AnomalyCase.case_number).where(
                        AnomalyCase.id.in_({r.case_id for r in rows if r.case_id})
                    )
                ).all()
            )
            if any(r.case_id for r in rows)
            else {}
        )
        adjustments: dict[uuid.UUID, list[RevenueAdjustmentDto]] = {}
        for a in self._s.execute(
            select(RevenueDifferenceAdjustment)
            .where(RevenueDifferenceAdjustment.difference_id.in_([r.id for r in rows]))
            .order_by(RevenueDifferenceAdjustment.created_at, RevenueDifferenceAdjustment.id)
        ).scalars():
            adjustments.setdefault(a.difference_id, []).append(RevenueAdjustmentDto.model_validate(a))
        out = []
        for r in rows:
            dto = RevenueDifferenceDto.model_validate(r)
            dto.reason_name = reasons.get(r.reason_id) if r.reason_id else None
            dto.case_number = cases.get(r.case_id) if r.case_id else None
            dto.adjustments = adjustments.get(r.id, [])
            if dto.adjustments:
                dto.adjusted_difference = r.difference + sum((a.amount for a in dto.adjustments), Decimal(0))
            out.append(dto)
        return out

    def explain(self, difference_id: uuid.UUID, body: RevenueExplanationIn) -> RevenueDifferenceDto:
        row = self.difference(difference_id, lock=True)
        if row.status is not RevenueDifferenceStatus.OPEN:
            raise Conflict(
                f"Only an open revenue difference can be explained (it is {row.status.value})",
                code="REVENUE_DIFFERENCE_NOT_OPEN",
            )
        reason = self.reason(body.reason_id)
        if not reason.is_active:
            raise BusinessRuleViolation("This reason is deactivated", code="REASON_INACTIVE")
        before = {"status": row.status.value}
        row.status = RevenueDifferenceStatus.EXPLANATION_PROPOSED
        row.reason_id, row.explanation_note = reason.id, body.note
        row.explained_by, row.explained_at = self._ctx.user_id, self._now
        self._s.flush()
        self._record(
            "revenue.difference.explained",
            "revenue_difference",
            row.id,
            before,
            {"status": row.status.value, "reason_id": str(reason.id)},
            body.note,
        )
        OutboxWriter(self._s).emit(
            topic=TOPIC,
            event_type="RevenueExplanationProposed",
            key=str(row.machine_id),
            payload={
                "difference_id": str(row.id),
                "machine_id": str(row.machine_id),
                "period_key": row.period_key,
                "currency": row.currency,
                "difference": str(row.difference),
                "reason": reason.name,
                "proposed_by": str(self._ctx.user_id),
            },
            tenant_id=self._tid,
        )
        return self.difference_dtos([row])[0]

    def decide(self, difference_id: uuid.UUID, body: RevenueDecisionIn) -> RevenueDifferenceDto:
        row = self.difference(difference_id, lock=True)
        allowed = {
            "APPROVE": (RevenueDifferenceStatus.EXPLANATION_PROPOSED,),
            "REJECT": (RevenueDifferenceStatus.EXPLANATION_PROPOSED,),
            "CONFIRM": (RevenueDifferenceStatus.OPEN, RevenueDifferenceStatus.EXPLANATION_PROPOSED),
        }[body.decision]
        if row.status not in allowed:
            raise Conflict(
                f"A {row.status.value} revenue difference cannot take the decision {body.decision}",
                code="REVENUE_DIFFERENCE_STATE",
            )
        if row.explained_by is not None and row.explained_by == self._ctx.user_id:
            sod_violation(self._tid, self._ctx.user_id, "decide", "revenue_difference", row.id)
            raise BusinessRuleViolation(
                "The person who explained this difference cannot decide on it", code="SEGREGATION_OF_DUTIES"
            )
        before = {"status": row.status.value}
        if body.decision == "REJECT":  # back to open; the rejected explanation stays in the audit trail
            row.status = RevenueDifferenceStatus.OPEN
            row.reason_id = row.explanation_note = row.explained_by = row.explained_at = None
        else:
            row.status = (
                RevenueDifferenceStatus.EXPLAINED if body.decision == "APPROVE" else RevenueDifferenceStatus.CONFIRMED
            )
            row.decided_by, row.decided_at, row.decision_note = self._ctx.user_id, self._now, body.note
        self._s.flush()
        self._record(
            {"APPROVE": "revenue.difference.approved", "REJECT": "revenue.difference.rejected"}.get(
                body.decision, "revenue.difference.confirmed"
            ),
            "revenue_difference",
            row.id,
            before,
            {"status": row.status.value},
            body.note,
        )
        return self.difference_dtos([row])[0]

    # --- non-revenue approvals (owner rule 2026-10-26) --------------------------------------------------------
    def non_revenue_activities(
        self, machine_id: uuid.UUID | None, job_id: uuid.UUID | None, status: str | None
    ) -> list[NonRevenueActivityDto]:
        """Non-billable, ended work-log entries of the declared non-revenue types, newest first, with the status of
        their explanation (NONE: not explained — counted as revenue)."""
        policy = PolicyService(self._s).revenue_reconciliation(self._tid, at=self._now).policy
        stmt = (
            select(JobActivity, Job.machine_id)
            .join(Job, Job.id == JobActivity.job_id)
            .where(
                JobActivity.activity_type.in_(policy.non_revenue_activity_types),
                JobActivity.billable.is_(False),
                JobActivity.ended_at.is_not(None),
            )
            .order_by(JobActivity.started_at.desc(), JobActivity.id)
        )
        if machine_id is not None:
            stmt = stmt.where(Job.machine_id == machine_id)
        if job_id is not None:
            stmt = stmt.where(JobActivity.job_id == job_id)
        rows = self._s.execute(stmt).all()
        latest: dict[uuid.UUID, NonRevenueApproval] = {}
        if rows:
            for a in self._s.execute(
                select(NonRevenueApproval)
                .where(NonRevenueApproval.activity_id.in_([r[0].id for r in rows]))
                .order_by(NonRevenueApproval.proposed_at)
            ).scalars():
                latest[a.activity_id] = a  # the latest explanation decides the status
        out = []
        for activity, machine in rows:
            approval = latest.get(activity.id)
            st = approval.status.value if approval else "NONE"
            if status is not None and st != status:
                continue
            assert activity.ended_at is not None
            out.append(
                NonRevenueActivityDto(
                    activity_id=activity.id,
                    job_id=activity.job_id,
                    machine_id=machine,
                    activity_type=activity.activity_type.value,
                    started_at=activity.started_at,
                    ended_at=activity.ended_at,
                    hours=_hours(activity.started_at, activity.ended_at),
                    note=activity.note,
                    approval_id=approval.id if approval else None,
                    approval_status=st,
                )
            )
        return out

    def approval(self, approval_id: uuid.UUID, lock: bool = False) -> NonRevenueApproval:
        stmt = select(NonRevenueApproval).where(NonRevenueApproval.id == approval_id)
        row = self._s.execute(stmt.with_for_update() if lock else stmt).scalar_one_or_none()
        if row is None:
            raise NotFound("Non-revenue approval not found", code="NON_REVENUE_APPROVAL_NOT_FOUND")
        return row

    @staticmethod
    def approval_query(
        status: NonRevenueApprovalStatus | None, machine_id: uuid.UUID | None, job_id: uuid.UUID | None
    ) -> Select[NonRevenueApproval]:
        stmt = select(NonRevenueApproval).order_by(NonRevenueApproval.proposed_at.desc(), NonRevenueApproval.id)
        if status is not None:
            stmt = stmt.where(NonRevenueApproval.status == status)
        if machine_id is not None:
            stmt = stmt.where(NonRevenueApproval.machine_id == machine_id)
        if job_id is not None:
            stmt = stmt.where(NonRevenueApproval.job_id == job_id)
        return stmt

    def approval_dtos(self, rows: list[NonRevenueApproval]) -> list[NonRevenueApprovalDto]:
        reasons = (
            dict(
                self._s.execute(
                    select(RevenueReason.id, RevenueReason.name).where(
                        RevenueReason.id.in_({r.reason_id for r in rows})
                    )
                ).all()
            )
            if rows
            else {}
        )
        out = []
        for r in rows:
            dto = NonRevenueApprovalDto.model_validate(r)
            dto.status = r.status.value
            dto.reason_name = reasons.get(r.reason_id)
            out.append(dto)
        return out

    def propose_non_revenue(self, body: NonRevenueApprovalIn) -> NonRevenueApprovalDto:
        eff = PolicyService(self._s).revenue_reconciliation(self._tid, at=self._now)
        policy = eff.policy
        if not policy.non_revenue_requires_approval:
            raise BusinessRuleViolation(
                "Non-revenue time needs no approval under the tenant policy", code="NON_REVENUE_APPROVAL_NOT_REQUIRED"
            )
        activity = self._s.get(JobActivity, body.activity_id)
        if activity is None:
            raise NotFound("Work-log entry not found", code="ACTIVITY_NOT_FOUND")
        if (
            activity.activity_type.value not in policy.non_revenue_activity_types
            or activity.billable
            or activity.ended_at is None
        ):
            raise BusinessRuleViolation(
                "Only an ended, non-billable entry of a declared non-revenue type can be explained",
                code="NOT_NON_REVENUE_ACTIVITY",
            )
        reason = self.reason(body.reason_id)
        if not reason.is_active:
            raise BusinessRuleViolation("This reason is deactivated", code="REASON_INACTIVE")
        job = self._s.get(Job, activity.job_id)
        assert job is not None
        row = NonRevenueApproval(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            activity_id=activity.id,
            job_id=job.id,
            machine_id=job.machine_id,
            activity_type=activity.activity_type.value,
            started_at=activity.started_at,
            ended_at=activity.ended_at,
            hours=_hours(activity.started_at, activity.ended_at),
            reason_id=reason.id,
            note=body.note,
            status=NonRevenueApprovalStatus.PROPOSED,
            proposed_by=self._ctx.user_id,
            proposed_at=self._now,
            policy_version=eff.version_stamp[:80],
        )
        try:
            with self._s.begin_nested():
                self._s.add(row)
                self._s.flush()
        except IntegrityError as exc:
            raise Conflict(
                "This entry already has an explanation awaiting a decision or approved", code="NON_REVENUE_PENDING"
            ) from exc
        self._record(
            "revenue.non_revenue.proposed",
            "non_revenue_approval",
            row.id,
            None,
            {"activity_id": str(activity.id), "hours": str(row.hours), "reason_id": str(reason.id)},
            body.note,
        )
        OutboxWriter(self._s).emit(
            topic=TOPIC,
            event_type="NonRevenueApprovalProposed",
            key=str(row.machine_id),
            payload={
                "approval_id": str(row.id),
                "machine_id": str(row.machine_id),
                "activity_type": row.activity_type,
                "hours": str(row.hours),
                "reason": reason.name,
            },
            tenant_id=self._tid,
        )
        return self.approval_dtos([row])[0]

    def decide_non_revenue(self, approval_id: uuid.UUID, body: NonRevenueDecisionIn) -> NonRevenueApprovalDto:
        row = self.approval(approval_id, lock=True)
        if row.status is not NonRevenueApprovalStatus.PROPOSED:
            raise Conflict("Already decided", code="ALREADY_DECIDED")
        if row.proposed_by is not None and row.proposed_by == self._ctx.user_id:
            sod_violation(self._tid, self._ctx.user_id, "approve", "non_revenue_approval", row.id)
            raise BusinessRuleViolation(
                "The person who explained this time cannot approve it", code="SEGREGATION_OF_DUTIES"
            )
        approve = body.decision == "APPROVE"
        row.status = NonRevenueApprovalStatus.APPROVED if approve else NonRevenueApprovalStatus.REJECTED
        row.decided_by, row.decided_at, row.decision_note = self._ctx.user_id, self._now, body.note
        self._s.flush()
        self._record(
            f"revenue.non_revenue.{'approved' if approve else 'rejected'}",
            "non_revenue_approval",
            row.id,
            {"status": NonRevenueApprovalStatus.PROPOSED.value},
            {"status": row.status.value, "hours": str(row.hours)},
            body.note,
        )
        if approve:
            recompute_after_change(
                self._s,
                self._tid,
                row.machine_id,
                row.started_at,
                row.ended_at,
                "non_revenue_approval",
                row.id,
                self._ctx.user_id,
                self._now,
            )
        return self.approval_dtos([row])[0]


def _hours(start: datetime, end: datetime) -> Decimal:
    return (Decimal(str((end - start).total_seconds())) / Decimal(3600)).quantize(Decimal("0.01"))
