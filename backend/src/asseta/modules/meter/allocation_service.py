"""Work allocation ledger use cases (DEC-032 A1): list and detail, per-day reconciliation (total engine hours =
customer + authorized + unexplained, the difference displayed) and corrections. A correction never edits an entry: it
adds entries that supersede it, approved by a second person holding `tenant.meter.approve` unless the tenant switched
that off (policy `allocation_correction_requires_approval`); the original stays visible."""

import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound
from asseta.core.outbox import OutboxWriter
from asseta.core.search import ilike_any
from asseta.core.signals import sod_violation
from asseta.modules.adjustments.models import AdjustmentEntryStatus, AdjustmentType, AdjustmentUnit
from asseta.modules.adjustments.posting import AdjustmentPosting, post_adjustment
from asseta.modules.fleet.models import Machine
from asseta.modules.identity.principal import RequestContext
from asseta.modules.jobs.models import Customer, Job
from asseta.modules.jobs.scope import METER_OVERSIGHT, assigned_machine_ids, own_staff, restricted_to_own
from asseta.modules.meter.allocation_dto import (
    AllocationCorrectionDto,
    AllocationCorrectionIn,
    AllocationDayDto,
    AllocationPartIn,
    WorkAllocationDto,
)
from asseta.modules.meter.allocation_models import (
    AllocationKind,
    AllocationSource,
    AllocationStatus,
    WorkAllocation,
)
from asseta.modules.meter.allocation_writer import AllocationWriter
from asseta.modules.meter.engine_dto import MeterDecisionIn
from asseta.modules.meter.engine_hours import LIVE, TOPIC, load_machine_ledger
from asseta.modules.meter.engine_models import EngineHourReason, EngineHourReasonKind
from asseta.modules.meter.models import CaptureAttachment, MeterCapture
from asseta.modules.policy.service import PolicyService

APPROVE_PERMISSION = "tenant.meter.approve"
ZERO = Decimal(0)
REASON_KINDS = (EngineHourReasonKind.NON_CUSTOMER_CATEGORY, EngineHourReasonKind.VARIANCE_REASON)


class WorkAllocationService:
    def __init__(self, session: Session, ctx: RequestContext, now: datetime):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid, self._now = session, ctx, ctx.tenant_id, now

    def _visible(self) -> set[uuid.UUID] | None:
        """None = every machine; a field user sees only the machines currently assigned to them."""
        if not restricted_to_own(self._ctx, METER_OVERSIGHT):
            return None
        staff = own_staff(self._s, self._ctx)
        return set() if staff is None else set(self._s.execute(assigned_machine_ids(staff.id)).scalars())

    # --- reads -------------------------------------------------------------------------------------------------
    def query(
        self,
        q: str | None,
        machine_id: uuid.UUID | None,
        day_from: date | None,
        day_to: date | None,
        customer_id: uuid.UUID | None,
        kind: AllocationKind | None,
        status: AllocationStatus | None,
        job_id: uuid.UUID | None = None,
    ) -> Select[WorkAllocation]:
        stmt = (
            select(WorkAllocation)
            .join(Machine, Machine.id == WorkAllocation.machine_id)
            .order_by(
                WorkAllocation.work_date.desc(), Machine.asset_code, WorkAllocation.start_reading, WorkAllocation.id
            )
        )
        stmt = stmt.where(WorkAllocation.status == (status or AllocationStatus.ACTIVE))
        for col, val in (
            (WorkAllocation.machine_id, machine_id),
            (WorkAllocation.customer_id, customer_id),
            (WorkAllocation.kind, kind),
            (WorkAllocation.job_id, job_id),
        ):
            if val is not None:
                stmt = stmt.where(col == val)
        if day_from is not None:
            stmt = stmt.where(WorkAllocation.work_date >= day_from)
        if day_to is not None:
            stmt = stmt.where(WorkAllocation.work_date <= day_to)
        if (match := ilike_any(q, Machine.asset_code, Machine.name)) is not None:
            stmt = stmt.where(match)
        visible = self._visible()
        return stmt.where(WorkAllocation.machine_id.in_(visible)) if visible is not None else stmt

    def dtos(self, rows: list[WorkAllocation]) -> list[WorkAllocationDto]:
        ids = {r.id for r in rows}
        reasons = {r.reason_id for r in rows if r.reason_id}
        names = (
            dict(
                self._s.execute(
                    select(EngineHourReason.id, EngineHourReason.name).where(EngineHourReason.id.in_(reasons))
                ).all()
            )
            if reasons
            else {}
        )
        followers: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
        if ids:
            for follower, target in self._s.execute(
                select(WorkAllocation.id, WorkAllocation.supersedes_id).where(WorkAllocation.supersedes_id.in_(ids))
            ).all():
                if target is not None:
                    followers[target].append(follower)
        return [
            WorkAllocationDto.model_validate(r).model_copy(
                update={
                    "reason_name": names.get(r.reason_id) if r.reason_id else None,
                    "superseded_by_ids": followers.get(r.id, []),
                }
            )
            for r in rows
        ]

    def row(self, allocation_id: uuid.UUID, lock: bool = False) -> WorkAllocation:
        stmt = select(WorkAllocation).where(WorkAllocation.id == allocation_id)
        row = self._s.execute(stmt.with_for_update() if lock else stmt).scalar_one_or_none()
        visible = self._visible()
        if row is None or (visible is not None and row.machine_id not in visible):
            raise NotFound("Work allocation not found", code="ALLOCATION_NOT_FOUND")
        return row

    def reconciliation(self, machine_id: uuid.UUID | None, day_from: date, day_to: date) -> list[AllocationDayDto]:
        if day_to < day_from or day_to - day_from > timedelta(days=92):
            raise BusinessRuleViolation("The range must be 1 to 93 days", code="INVALID_DAY_RANGE")
        visible = self._visible()
        if machine_id is not None:
            machines = {machine_id} if visible is None or machine_id in visible else set()
        else:
            machines = set(
                self._s.execute(
                    select(WorkAllocation.machine_id).where(
                        WorkAllocation.status == AllocationStatus.ACTIVE,
                        WorkAllocation.work_date >= day_from,
                        WorkAllocation.work_date <= day_to,
                    )
                ).scalars()
            ) | set(self._s.execute(select(MeterCapture.machine_id).where(MeterCapture.state.in_(LIVE))).scalars())
            if visible is not None:
                machines &= visible
        out = []
        for row in self._s.execute(
            select(Machine).where(Machine.id.in_(machines)).order_by(Machine.asset_code)
        ).scalars():
            out.extend(self._machine_days(row, day_from, day_to))
        return out

    def _machine_days(self, machine: Machine, day_from: date, day_to: date) -> list[AllocationDayDto]:
        ml = load_machine_ledger(self._s, self._tid, machine, self._now)
        plan = AllocationWriter(self._s, self._tid, self._now, AllocationSource.DERIVED).build_plan(ml)
        totals: dict[date, dict[AllocationKind, Decimal]] = defaultdict(lambda: defaultdict(lambda: ZERO))
        for kind, day, hours in self._s.execute(
            select(WorkAllocation.kind, WorkAllocation.work_date, WorkAllocation.hours).where(
                WorkAllocation.machine_id == machine.id,
                WorkAllocation.status == AllocationStatus.ACTIVE,
                WorkAllocation.work_date >= day_from,
                WorkAllocation.work_date <= day_to,
            )
        ).all():
            totals[day][kind] += hours
        rows = []
        for day in sorted(set(plan.total_by_day) | set(totals)):
            if not day_from <= day <= day_to:
                continue
            total = plan.total_by_day.get(day, ZERO)
            by_kind = totals.get(day, {})
            customer, authorized, unexplained = (
                by_kind.get(AllocationKind.CUSTOMER_WORK, ZERO),
                by_kind.get(AllocationKind.AUTHORIZED_ACTIVITY, ZERO),
                by_kind.get(AllocationKind.UNEXPLAINED, ZERO),
            )
            allocated = customer + authorized + unexplained
            rows.append(
                AllocationDayDto(
                    machine_id=machine.id,
                    machine_code=machine.asset_code,
                    machine_name=machine.name,
                    day=day,
                    total_engine_hours=total,
                    customer_hours=customer,
                    authorized_hours=authorized,
                    unexplained_hours=unexplained,
                    allocated_hours=allocated,
                    difference_hours=total - allocated,
                    reconciled=total == allocated,
                )
            )
        return rows

    # --- corrections -------------------------------------------------------------------------------------------
    def _check_part(self, entry: WorkAllocation, part: AllocationPartIn) -> None:
        if part.kind is AllocationKind.CUSTOMER_WORK:
            if part.customer_id is None or self._s.get(Customer, part.customer_id) is None:
                raise BusinessRuleViolation("Customer work names its customer", code="ALLOCATION_CUSTOMER_REQUIRED")
        elif part.customer_id is not None:
            raise BusinessRuleViolation("Only customer work names a customer", code="ALLOCATION_CUSTOMER_REQUIRED")
        if part.kind is AllocationKind.AUTHORIZED_ACTIVITY:
            reason = self._s.get(EngineHourReason, part.reason_id) if part.reason_id else None
            if reason is None or not reason.is_active or reason.kind not in REASON_KINDS:
                raise BusinessRuleViolation(
                    "An authorized activity needs an active category or variance reason", code="REASON_NOT_ALLOWED"
                )
        elif part.reason_id is not None:
            raise BusinessRuleViolation("Only authorized activity names a reason", code="REASON_NOT_ALLOWED")
        if part.job_id is not None:
            job = self._s.get(Job, part.job_id)
            if job is None or job.machine_id != entry.machine_id:
                raise NotFound("Job not found on this machine", code="JOB_NOT_FOUND")

    def _check_evidence(self, ids: list[uuid.UUID]) -> None:
        for attachment_id in ids:
            if self._s.get(CaptureAttachment, attachment_id) is None:
                raise NotFound("Evidence attachment not found", code="ATTACHMENT_NOT_FOUND")

    def propose_correction(self, allocation_id: uuid.UUID, body: AllocationCorrectionIn) -> AllocationCorrectionDto:
        entry = self.row(allocation_id, lock=True)
        if entry.status is not AllocationStatus.ACTIVE:
            raise Conflict("Only an active allocation can be corrected", code="ALLOCATION_NOT_ACTIVE")
        pending = self._s.execute(
            select(WorkAllocation.id).where(
                WorkAllocation.supersedes_id == entry.id, WorkAllocation.status == AllocationStatus.PROPOSED
            )
        ).first()
        if pending is not None:
            raise Conflict("A correction of this entry awaits a decision", code="ALLOCATION_CORRECTION_PENDING")
        for part in body.parts:
            self._check_part(entry, part)
        if sum((p.hours for p in body.parts), ZERO) != entry.hours:
            raise BusinessRuleViolation("The parts must add up to the entry's hours", code="ALLOCATION_PARTS_MISMATCH")
        self._check_evidence(body.evidence_attachment_ids)
        group = uuid.uuid4()
        eff = PolicyService(self._s).engine_hours(self._tid, entry.machine_id, at=self._now)
        direct = not eff.policy.allocation_correction_requires_approval and APPROVE_PERMISSION in self._ctx.permissions
        cursor, lots = entry.start_reading, list(entry.lots)
        parts = []
        for part in body.parts:
            carries = part.kind is AllocationKind.CUSTOMER_WORK and part.customer_id == entry.customer_id
            row = WorkAllocation(
                id=uuid.uuid4(),
                tenant_id=self._tid,
                machine_id=entry.machine_id,
                work_date=entry.work_date,
                start_ref=entry.start_ref,
                start_reading=cursor,
                start_at=entry.start_at,
                end_ref=entry.end_ref,
                end_reading=cursor + part.hours,
                end_at=entry.end_at,
                meter_epoch=entry.meter_epoch,
                hours=part.hours,
                kind=part.kind,
                customer_id=part.customer_id,
                job_id=part.job_id if part.job_id is not None else entry.job_id,
                activity_type=entry.activity_type if part.kind is entry.kind else None,
                reason_id=part.reason_id,
                classification_id=None,
                changeover_id=entry.changeover_id if part.kind is AllocationKind.CUSTOMER_WORK else None,
                reading_review=entry.reading_review,
                approval_ref_type="work_allocation_correction",
                approval_ref_ids=[group],
                lots=self._carry_lots(lots, part.hours) if carries else [],
                evidence_attachment_ids=list({*entry.evidence_attachment_ids, *body.evidence_attachment_ids}),
                source=AllocationSource.CORRECTION,
                status=AllocationStatus.PROPOSED,
                origin_key=entry.origin_key,
                origin_hours=entry.origin_hours,
                supersedes_id=entry.id,
                correction_group_id=group,
                correction_reason=body.reason,
                recorded_by=self._ctx.user_id,
                policy_version=eff.version_stamp[:80],
                created_at=self._now,
            )
            cursor += part.hours
            parts.append(row)
            self._s.add(row)
        self._s.flush()
        self._audit(
            "meter.work_allocation.correction_proposed",
            entry,
            {"group_id": str(group), "parts": [{"kind": p.kind.value, "hours": str(p.hours)} for p in parts]},
            body.reason,
        )
        if direct:
            self._apply(entry, parts, "Second person not required by tenant policy")
        else:
            OutboxWriter(self._s).emit(
                topic=TOPIC,
                event_type="WorkAllocationCorrectionProposed",
                key=str(entry.machine_id),
                payload={
                    "correction_group_id": str(group),
                    "allocation_id": str(entry.id),
                    "machine_id": str(entry.machine_id),
                    "hours": str(entry.hours),
                },
                tenant_id=self._tid,
            )
        return self._correction_dto(group, parts)

    @staticmethod
    def _carry_lots(lots: list[dict[str, Any]], hours: Decimal) -> list[dict[str, Any]]:
        """Take up to `hours` of the corrected entry's lot hours for this part (first come, first served)."""
        taken, left = [], hours
        for lot in lots:
            amount = min(left, Decimal(str(lot["hours"])))
            if amount <= 0:
                continue
            taken.append({"purchase_id": lot["purchase_id"], "hours": str(amount)})
            lot["hours"] = str(Decimal(str(lot["hours"])) - amount)
            left -= amount
        return taken

    def _group(self, group_id: uuid.UUID) -> list[WorkAllocation]:
        rows = list(
            self._s.execute(
                select(WorkAllocation)
                .where(WorkAllocation.correction_group_id == group_id)
                .order_by(WorkAllocation.start_reading)
                .with_for_update()
            ).scalars()
        )
        visible = self._visible()
        if not rows or (visible is not None and rows[0].machine_id not in visible):
            raise NotFound("Correction not found", code="ALLOCATION_CORRECTION_NOT_FOUND")
        return rows

    def correction(self, group_id: uuid.UUID) -> AllocationCorrectionDto:
        return self._correction_dto(group_id, self._group(group_id))

    def _correction_dto(self, group_id: uuid.UUID, rows: list[WorkAllocation]) -> AllocationCorrectionDto:
        return AllocationCorrectionDto(
            group_id=group_id, status=rows[0].status, supersedes_id=rows[0].supersedes_id, entries=self.dtos(rows)
        )

    def _apply(self, entry: WorkAllocation, parts: list[WorkAllocation], note: str) -> None:
        """Supersede the old entry first, so its meter range leaves the exclusion constraint before the new parts
        enter it; a racing allocation of the same range is refused here, not stored."""
        entry.status, entry.superseded_at = AllocationStatus.SUPERSEDED, self._now
        self._s.flush()
        try:
            with self._s.begin_nested():
                for part in parts:
                    part.status, part.decided_by, part.decided_at, part.decision_note = (
                        AllocationStatus.ACTIVE,
                        self._ctx.user_id,
                        self._now,
                        note,
                    )
                self._s.flush()
        except IntegrityError as exc:
            raise Conflict("These engine hours are already allocated", code="OVERLAPPING_ALLOCATION") from exc
        self._audit(
            "meter.work_allocation.corrected",
            entry,
            {"superseded_by": [str(p.id) for p in parts], "hours": str(entry.hours)},
            note,
        )
        self._post(entry, parts, AdjustmentEntryStatus.APPROVED, note)

    def decide_correction(self, group_id: uuid.UUID, body: MeterDecisionIn) -> AllocationCorrectionDto:
        rows = self._group(group_id)
        if rows[0].status is not AllocationStatus.PROPOSED:
            raise Conflict("This correction was already decided", code="ALREADY_DECIDED")
        proposer = rows[0].recorded_by
        if self._ctx.user_id == proposer:
            sod_violation(self._tid, self._ctx.user_id, "approve", "work_allocation", rows[0].id)
            raise BusinessRuleViolation("The person who proposed this cannot approve it", code="SEGREGATION_OF_DUTIES")
        assert rows[0].supersedes_id is not None
        entry = self.row(rows[0].supersedes_id, lock=True)
        if body.decision == "REJECT":
            for part in rows:
                part.status, part.decided_by, part.decided_at, part.decision_note = (
                    AllocationStatus.REJECTED,
                    self._ctx.user_id,
                    self._now,
                    body.note,
                )
            self._s.flush()
            self._audit("meter.work_allocation.correction_rejected", entry, {"group_id": str(group_id)}, body.note)
            self._post(entry, rows, AdjustmentEntryStatus.REJECTED, body.note)
        else:
            if entry.status is not AllocationStatus.ACTIVE:
                raise Conflict("The entry changed since this was proposed; propose again", code="SEGMENT_CHANGED")
            self._apply(entry, rows, body.note)
        return self._correction_dto(group_id, rows)

    def _post(
        self, entry: WorkAllocation, parts: list[WorkAllocation], status: AdjustmentEntryStatus, note: str | None
    ) -> None:
        group = parts[0].correction_group_id
        assert group is not None
        post_adjustment(
            self._s,
            self._tid,
            self._now,
            AdjustmentPosting(
                adjustment_type=AdjustmentType.ALLOCATION_CORRECTION,
                status=status,
                original_type="work_allocation",
                original_id=entry.id,
                original_reference=None,
                source_type="work_allocation_correction",
                source_id=group,
                unit=AdjustmentUnit.HOURS,
                original_value=entry.hours,
                new_value=sum((p.hours for p in parts), ZERO),
                amount=ZERO,
                reason=parts[0].correction_reason,
                evidence_attachment_ids=list(parts[0].evidence_attachment_ids),
                customer_id=entry.customer_id,
                machine_id=entry.machine_id,
                requested_by=parts[0].recorded_by,
                requested_at=parts[0].created_at,
                approved_by=self._ctx.user_id,
                approved_at=self._now,
                decision_note=note,
                details={"parts": [{"kind": p.kind.value, "hours": str(p.hours)} for p in parts]},
                policy_version=parts[0].policy_version,
            ),
        )

    def _audit(self, action: str, entry: WorkAllocation, after: dict[str, Any], reason: str | None) -> None:
        AuditService(self._s).record(
            actor=self._ctx.audit_actor(),
            action=action,
            entity_type="work_allocation",
            entity_id=entry.id,
            tenant_id=self._tid,
            after=after,
            reason=reason,
        )
