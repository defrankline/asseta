"""Engine-hour accountability use cases (design B): meter baselines (propose / approve), the tenant's explanation
lists, ledger views (per machine and tenant-wide open items), classification of unallocated hours (propose /
approve per policy) and two-person reading corrections. Approvals are permission-gated; the proposer can never
approve their own proposal (refusals are recorded as segregation-of-duties signals)."""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound
from asseta.core.lifecycle import check_version, flush_versioned, mark_active, mark_inactive
from asseta.core.outbox import OutboxWriter
from asseta.core.search import ilike_any, matches
from asseta.core.signals import sod_violation
from asseta.modules.fleet.models import Machine
from asseta.modules.identity.models import AppUser
from asseta.modules.identity.principal import RequestContext
from asseta.modules.jobs.scope import METER_OVERSIGHT, assigned_machine_ids, own_staff, restricted_to_own
from asseta.modules.meter.dto import MeterCaptureIn
from asseta.modules.meter.engine_dto import (
    BaselineDto,
    BaselineFromReadingIn,
    BaselineIn,
    ClassificationDto,
    ClassificationIn,
    ClassificationRefDto,
    CorrectionDto,
    CorrectionIn,
    EngineHourReasonDto,
    EngineHourReasonIn,
    EngineHourReasonUpdateIn,
    IntervalDto,
    JobOverlapDto,
    LedgerPointDto,
    MachineEngineHoursDto,
    MachineEngineHoursSummaryDto,
    MeterDecisionIn,
    ReconciliationStatus,
    SegmentDto,
    TotalsDto,
    UnallocatedSegmentDto,
)
from asseta.modules.meter.engine_hours import (
    LIVE,
    TOPIC,
    MachineLedger,
    approved_baseline,
    load_machine_ledger,
    pending_baseline,
    unexplained_dedupe,
)
from asseta.modules.meter.engine_models import (
    OUTCOME_REASON_KIND,
    BaselineSource,
    EngineHourClassification,
    EngineHourReason,
    EngineHourReasonKind,
    MachineMeterBaseline,
    MeterCorrection,
    MeterProposalStatus,
)
from asseta.modules.meter.ledger import ClassificationFact, LedgerInterval, LedgerPoint, SegmentClassification
from asseta.modules.meter.models import (
    CaptureAttachment,
    CaptureState,
    ExceptionStatus,
    ExceptionType,
    JobException,
    MeterCapture,
    MeterResetEvent,
)
from asseta.modules.meter.service import FUTURE_SKEW, MeterService
from asseta.modules.policy.service import PolicyService

APPROVE_PERMISSION = "tenant.meter.approve"
CLASSIFY_PERMISSION = "tenant.meter.classify"


def _names(s: Session, ids: set[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    wanted = {i for i in ids if i is not None}
    if not wanted:
        return {}
    return dict(s.execute(select(AppUser.id, AppUser.display_name).where(AppUser.id.in_(wanted))).all())


def _point(p: LedgerPoint) -> LedgerPointDto:
    return LedgerPointDto(ref=p.ref, source=p.source, at=p.at, reading=p.reading, job_id=p.job_id)


def _ref(c: ClassificationFact | None) -> ClassificationRefDto | None:
    if c is None:
        return None
    return ClassificationRefDto.model_validate(
        {"id": c.id, "status": c.status, "outcome": c.outcome, "reason_id": c.reason_id}
    )


def _totals(ml: MachineLedger, intervals: list[LedgerInterval] | None = None) -> TotalsDto:
    return TotalsDto.model_validate(ml.ledger.totals(intervals).__dict__)


def _status(ml: MachineLedger) -> ReconciliationStatus:
    if not ml.reconciling:
        return ReconciliationStatus.NO_BASELINE
    if ml.open_items():
        return ReconciliationStatus.UNEXPLAINED
    t = ml.ledger.totals()
    if t.unexplained_hours > 0 or t.pending_review_hours > 0:
        return ReconciliationStatus.PENDING_REVIEW
    return ReconciliationStatus.RECONCILED


class EngineHoursService:
    def __init__(self, session: Session, ctx: RequestContext, now: datetime):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid, self._now = session, ctx, ctx.tenant_id, now
        self._audit = AuditService(session)

    # --- shared ------------------------------------------------------------------------------------------------
    def _record(
        self,
        action: str,
        entity: str,
        entity_id: uuid.UUID,
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

    def _emit(self, event_type: str, key: uuid.UUID, payload: dict[str, Any]) -> None:
        OutboxWriter(self._s).emit(
            topic=TOPIC, event_type=event_type, key=str(key), payload=payload, tenant_id=self._tid
        )

    def _own_only(self) -> bool:
        return restricted_to_own(self._ctx, METER_OVERSIGHT)

    def _visible_machine_ids(self) -> set[uuid.UUID] | None:
        """None = every machine; a field user sees only the machines currently assigned to them."""
        if not self._own_only():
            return None
        staff = own_staff(self._s, self._ctx)
        return set() if staff is None else set(self._s.execute(assigned_machine_ids(staff.id)).scalars())

    def machine(self, machine_id: uuid.UUID) -> Machine:
        row = self._s.get(Machine, machine_id)
        visible = self._visible_machine_ids()
        if row is None or (visible is not None and machine_id not in visible):
            raise NotFound("Machine not found", code="MACHINE_NOT_FOUND")
        return row

    def _sod(self, proposer: uuid.UUID | None, entity: str, entity_id: uuid.UUID, *others: uuid.UUID | None) -> None:
        if self._ctx.user_id in {proposer, *others} - {None}:
            sod_violation(self._tid, self._ctx.user_id, "approve", entity, entity_id)
            raise BusinessRuleViolation(
                "The person who proposed or recorded this cannot approve it", code="SEGREGATION_OF_DUTIES"
            )

    # --- baselines ---------------------------------------------------------------------------------------------
    def baseline_dtos(self, rows: list[MachineMeterBaseline]) -> list[BaselineDto]:
        names = _names(self._s, {r.proposed_by for r in rows} | {r.decided_by for r in rows})
        machines = {
            m.id: m
            for m in self._s.execute(select(Machine).where(Machine.id.in_({r.machine_id for r in rows}))).scalars()
        }
        out = []
        for r in rows:
            m = machines.get(r.machine_id)
            out.append(
                BaselineDto.model_validate(r).model_copy(
                    update={
                        "machine_code": m.asset_code if m else None,
                        "machine_name": m.name if m else None,
                        "proposed_by_name": names.get(r.proposed_by) if r.proposed_by else None,
                        "decided_by_name": names.get(r.decided_by) if r.decided_by else None,
                    }
                )
            )
        return out

    def baseline_dto(self, row: MachineMeterBaseline) -> BaselineDto:
        return self.baseline_dtos([row])[0]

    def baseline_query(
        self, q: str | None, machine_id: uuid.UUID | None, status: MeterProposalStatus | None
    ) -> Select[MachineMeterBaseline]:
        stmt = (
            select(MachineMeterBaseline)
            .join(Machine, Machine.id == MachineMeterBaseline.machine_id)
            .order_by(MachineMeterBaseline.proposed_at.desc(), MachineMeterBaseline.id)
        )
        if (match := ilike_any(q, Machine.asset_code, Machine.name)) is not None:
            stmt = stmt.where(match)
        if machine_id is not None:
            stmt = stmt.where(MachineMeterBaseline.machine_id == machine_id)
        if status is not None:
            stmt = stmt.where(MachineMeterBaseline.status == status)
        visible = self._visible_machine_ids()
        if visible is not None:
            stmt = stmt.where(MachineMeterBaseline.machine_id.in_(visible))
        return stmt

    def baseline(self, baseline_id: uuid.UUID, lock: bool = False) -> MachineMeterBaseline:
        stmt = select(MachineMeterBaseline).where(MachineMeterBaseline.id == baseline_id)
        row = self._s.execute(stmt.with_for_update() if lock else stmt).scalar_one_or_none()
        visible = self._visible_machine_ids()
        if row is None or (visible is not None and row.machine_id not in visible):
            raise NotFound("Baseline not found")
        return row

    def _check_can_propose(self, machine_id: uuid.UUID) -> None:
        if approved_baseline(self._s, machine_id) is not None:
            raise Conflict(
                "This machine already has an approved baseline; re-baseline through a meter reset",
                code="BASELINE_EXISTS",
            )
        if pending_baseline(self._s, machine_id) is not None:
            raise Conflict("A baseline proposal for this machine awaits a decision", code="BASELINE_PENDING")

    def _check_consistent(self, machine_id: uuid.UUID, at: datetime, reading: Decimal) -> None:
        """A baseline may not exceed a later live reading unless an approved reset re-based the meter between."""
        later = self._s.execute(
            select(MeterCapture)
            .where(
                MeterCapture.machine_id == machine_id,
                MeterCapture.state.in_(LIVE),
                MeterCapture.captured_at > at,
                MeterCapture.reading < reading,
            )
            .order_by(MeterCapture.captured_at)
            .limit(1)
        ).scalar_one_or_none()
        if later is None:
            return
        reset = self._s.execute(
            select(MeterResetEvent.id).where(
                MeterResetEvent.machine_id == machine_id,
                MeterResetEvent.status == "APPROVED",
                MeterResetEvent.effective_at > at,
                MeterResetEvent.effective_at <= later.captured_at,
            )
        ).first()
        if reset is None:
            raise BusinessRuleViolation(
                f"Baseline {reading} is above the later reading {later.reading} of {later.captured_at.isoformat()}",
                code="BASELINE_INCONSISTENT",
            )

    def _insert_baseline(self, row: MachineMeterBaseline) -> BaselineDto:
        try:
            with self._s.begin_nested():
                self._s.add(row)
                self._s.flush()
        except IntegrityError as exc:
            raise Conflict("A baseline proposal for this machine awaits a decision", code="BASELINE_PENDING") from exc
        self._record(
            "meter.baseline.proposed",
            "machine_meter_baseline",
            row.id,
            None,
            {
                "machine_id": str(row.machine_id),
                "reading": str(row.reading),
                "captured_at": row.captured_at.isoformat(),
                "source": row.source.value,
                "source_capture_id": str(row.source_capture_id) if row.source_capture_id else None,
            },
            row.note,
        )
        self._emit(
            "MeterBaselineProposed",
            row.machine_id,
            {"baseline_id": str(row.id), "machine_id": str(row.machine_id), "reading": str(row.reading)},
        )
        return self.baseline_dto(row)

    def propose_baseline(self, body: BaselineIn) -> BaselineDto:
        if body.id is not None and (existing := self._s.get(MachineMeterBaseline, body.id)) is not None:
            if existing.machine_id != body.machine_id or existing.reading != body.reading:
                raise Conflict("Baseline id reused with different content", code="BASELINE_ID_CONFLICT")
            return self.baseline_dto(existing)  # idempotent replay (offline retry)
        self.machine(body.machine_id)
        if body.captured_at > self._now + FUTURE_SKEW:
            raise BusinessRuleViolation("A baseline cannot be taken in the future", code="BASELINE_IN_FUTURE")
        if body.photo_attachment_id is not None and self._s.get(CaptureAttachment, body.photo_attachment_id) is None:
            raise NotFound("Photo attachment not found", code="ATTACHMENT_NOT_FOUND")
        self._check_can_propose(body.machine_id)
        self._check_consistent(body.machine_id, body.captured_at, body.reading)
        gps = body.gps
        return self._insert_baseline(
            MachineMeterBaseline(
                id=body.id or uuid.uuid4(),
                tenant_id=self._tid,
                machine_id=body.machine_id,
                reading=body.reading,
                captured_at=body.captured_at,
                source=BaselineSource.CAPTURE,
                photo_attachment_id=body.photo_attachment_id,
                latitude=gps.latitude if gps else None,
                longitude=gps.longitude if gps else None,
                accuracy_m=gps.accuracy_m if gps else None,
                device_id=body.device_id,
                note=body.note,
                status=MeterProposalStatus.PROPOSED,
                proposed_by=self._ctx.user_id,
                proposed_at=self._now,
            )
        )

    def propose_baseline_from_reading(self, body: BaselineFromReadingIn) -> BaselineDto:
        """For machines that already have readings: propose an existing live reading (default the earliest) as the
        baseline. Reconciliation starts there once a second person approves."""
        self.machine(body.machine_id)
        stmt = select(MeterCapture).where(MeterCapture.machine_id == body.machine_id, MeterCapture.state.in_(LIVE))
        if body.capture_id is not None:
            stmt = stmt.where(MeterCapture.id == body.capture_id)
        capture = self._s.execute(
            stmt.order_by(MeterCapture.captured_at, MeterCapture.id).limit(1)
        ).scalar_one_or_none()
        if capture is None:
            raise NotFound("No live reading of this machine to propose", code="READING_NOT_FOUND")
        self._check_can_propose(body.machine_id)
        self._check_consistent(body.machine_id, capture.captured_at, capture.reading)
        return self._insert_baseline(
            MachineMeterBaseline(
                id=uuid.uuid4(),
                tenant_id=self._tid,
                machine_id=body.machine_id,
                reading=capture.reading,
                captured_at=capture.captured_at,
                source=BaselineSource.READING,
                source_capture_id=capture.id,
                photo_attachment_id=capture.photo_attachment_id,
                latitude=capture.latitude,
                longitude=capture.longitude,
                accuracy_m=capture.accuracy_m,
                device_id=capture.device_id,
                note=body.note,
                status=MeterProposalStatus.PROPOSED,
                proposed_by=self._ctx.user_id,
                proposed_at=self._now,
            )
        )

    def decide_baseline(self, baseline_id: uuid.UUID, body: MeterDecisionIn) -> BaselineDto:
        row = self.baseline(baseline_id, lock=True)
        if row.status is not MeterProposalStatus.PROPOSED:
            raise Conflict("Baseline already decided", code="ALREADY_DECIDED")
        recorder = None
        if row.source_capture_id is not None:
            recorder = self._s.execute(
                select(MeterCapture.supervisor_user_id).where(MeterCapture.id == row.source_capture_id)
            ).scalar_one_or_none()
        self._sod(row.proposed_by, "meter_baseline", row.id, recorder)
        approve = body.decision == "APPROVE"
        if approve:
            if approved_baseline(self._s, row.machine_id) is not None:
                raise Conflict("This machine already has an approved baseline", code="BASELINE_EXISTS")
            self._check_consistent(row.machine_id, row.captured_at, row.reading)
        row.status = MeterProposalStatus.APPROVED if approve else MeterProposalStatus.REJECTED
        row.decided_by, row.decided_at, row.decision_note = self._ctx.user_id, self._now, body.note
        self._s.flush()
        self._record(
            f"meter.baseline.{'approved' if approve else 'rejected'}",
            "machine_meter_baseline",
            row.id,
            {"status": MeterProposalStatus.PROPOSED.value},
            {"status": row.status.value, "reading": str(row.reading)},
            body.note,
        )
        self._emit(
            "MeterBaselineDecided",
            row.machine_id,
            {"baseline_id": str(row.id), "machine_id": str(row.machine_id), "status": row.status.value},
        )
        return self.baseline_dto(row)

    # --- tenant lists ------------------------------------------------------------------------------------------
    def reason(self, reason_id: uuid.UUID, lock: bool = False) -> EngineHourReason:
        stmt = select(EngineHourReason).where(EngineHourReason.id == reason_id)
        row = self._s.execute(stmt.with_for_update() if lock else stmt).scalar_one_or_none()
        if row is None:
            raise NotFound("Reason not found")
        return row

    @staticmethod
    def reason_query(
        q: str | None, kind: EngineHourReasonKind | None, include_inactive: bool
    ) -> Select[EngineHourReason]:
        stmt = select(EngineHourReason).order_by(EngineHourReason.kind, EngineHourReason.code)
        if (match := ilike_any(q, EngineHourReason.code, EngineHourReason.name)) is not None:
            stmt = stmt.where(match)
        if kind is not None:
            stmt = stmt.where(EngineHourReason.kind == kind)
        return stmt if include_inactive else stmt.where(EngineHourReason.is_active.is_(True))

    def create_reason(self, body: EngineHourReasonIn) -> EngineHourReasonDto:
        row = EngineHourReason(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            kind=body.kind,
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
        dto = EngineHourReasonDto.model_validate(row)
        self._record("meter.reason.created", "engine_hour_reason", row.id, None, dto.model_dump(mode="json"))
        return dto

    def update_reason(self, reason_id: uuid.UUID, body: EngineHourReasonUpdateIn) -> EngineHourReasonDto:
        row = self.reason(reason_id, lock=True)
        check_version(row.version, body.version, "Reason")
        before = EngineHourReasonDto.model_validate(row).model_dump(mode="json")
        row.code, row.name, row.description = body.code, body.name, body.description
        flush_versioned(self._s, "Reason", "DUPLICATE_REASON", "A reason with this code already exists")
        dto = EngineHourReasonDto.model_validate(row)
        self._record("meter.reason.updated", "engine_hour_reason", row.id, before, dto.model_dump(mode="json"))
        return dto

    def set_reason_active(
        self, reason_id: uuid.UUID, active: bool, reason: str, version: int | None
    ) -> EngineHourReasonDto:
        """Deactivated entries are refused for new classifications; past classifications keep them."""
        row = self.reason(reason_id, lock=True)
        check_version(row.version, version, "Reason")
        if active:
            mark_active(row, "Reason")
        else:
            mark_inactive(row, self._ctx.user_id, reason, "Reason")
        flush_versioned(self._s, "Reason")
        dto = EngineHourReasonDto.model_validate(row)
        verb = "reactivated" if active else "deactivated"
        self._record(f"meter.reason.{verb}", "engine_hour_reason", row.id, None, {"is_active": active}, reason)
        return dto

    # --- ledger views ------------------------------------------------------------------------------------------
    def _interval_dto(self, ml: MachineLedger, i: LedgerInterval) -> IntervalDto:
        return IntervalDto(
            machine_id=ml.machine.id,
            start=_point(i.start),
            end=_point(i.end),
            hours=i.hours,
            raw_hours=i.raw_hours,
            reset_applied=i.reset_applied,
            inconsistent=i.inconsistent,
            review=i.review,
            opened_at=i.opened_at,
            age_days=max((self._now - i.opened_at).days, 0),
            overlapping_job_ids=i.overlapping_job_ids,
            segments=[
                SegmentDto(
                    kind=i.kind,
                    hours=i.hours,
                    classification=i.classification,
                    job_id=i.job_id,
                    job_number=i.job_number,
                    approved=_ref(i.approved),
                    proposal=_ref(i.proposal),
                )
            ],
        )

    def machine_ledger(self, machine_id: uuid.UUID) -> MachineLedger:
        return load_machine_ledger(self._s, self._tid, self.machine(machine_id), self._now)

    def reconciliation(
        self, machine_id: uuid.UUID, at_from: datetime | None, at_to: datetime | None
    ) -> MachineEngineHoursDto:
        ml = self.machine_ledger(machine_id)
        intervals = [
            i
            for i in ml.ledger.intervals
            if (at_from is None or i.end.at >= at_from) and (at_to is None or i.start.at < at_to)
        ]
        return MachineEngineHoursDto(
            machine_id=ml.machine.id,
            machine_code=ml.machine.asset_code,
            machine_name=ml.machine.name,
            status=_status(ml),
            baseline=self.baseline_dto(ml.baseline) if ml.baseline else None,
            baseline_proposal=self.baseline_dto(ml.proposal) if ml.proposal else None,
            policy_version=ml.policy.version_stamp,
            totals=_totals(ml, intervals),
            intervals=[self._interval_dto(ml, i) for i in intervals],
            overlaps=[JobOverlapDto(**o.__dict__) for o in ml.ledger.overlaps],
        )

    def _machines(self, q: str | None) -> list[Machine]:
        stmt = select(Machine).order_by(Machine.asset_code)
        if (match := ilike_any(q, Machine.asset_code, Machine.name)) is not None:
            stmt = stmt.where(match)
        visible = self._visible_machine_ids()
        if visible is not None:
            stmt = stmt.where(Machine.id.in_(visible))
        return list(self._s.execute(stmt).scalars())

    def summaries(self, q: str | None, status: ReconciliationStatus | None) -> list[MachineEngineHoursSummaryDto]:
        out = []
        for m in self._machines(q):
            ml = load_machine_ledger(self._s, self._tid, m, self._now)
            st = _status(ml)
            if status is not None and st is not status:
                continue
            items = ml.open_items()
            last = ml.ledger.intervals[-1].end if ml.ledger.intervals else None
            out.append(
                MachineEngineHoursSummaryDto(
                    machine_id=m.id,
                    machine_code=m.asset_code,
                    machine_name=m.name,
                    status=st,
                    baseline_reading=ml.baseline.reading if ml.baseline else None,
                    baseline_pending=ml.proposal is not None,
                    last_reading=last.reading if last else None,
                    last_reading_at=last.at if last else None,
                    open_items=len(items),
                    oldest_open_item_days=max(((self._now - i.opened_at).days for i in items), default=None),
                    totals=_totals(ml),
                )
            )
        return out

    def unallocated(
        self,
        q: str | None,
        machine_id: uuid.UUID | None,
        classification: SegmentClassification | None,
        min_age_days: int | None,
    ) -> list[UnallocatedSegmentDto]:
        """Tenant-wide unallocated segments of reconciling machines, oldest first. Default: the unexplained ones
        (verified readings), i.e. the open items management must look at [3.6.4]."""
        machines = [self.machine(machine_id)] if machine_id else self._machines(None)
        out = []
        for m in machines:
            if not matches(q, m.asset_code, m.name):
                continue
            ml = load_machine_ledger(self._s, self._tid, m, self._now)
            if not ml.reconciling:
                continue
            days = ml.policy.policy.unexplained_investigation_after_days
            for i in ml.ledger.intervals:
                if i.classification is SegmentClassification.NOT_APPLICABLE:
                    continue
                if classification is None and not i.open_item:
                    continue
                if classification is not None and i.classification is not classification:
                    continue
                age = max((self._now - i.opened_at).days, 0)
                if min_age_days is not None and age < min_age_days:
                    continue
                out.append(
                    UnallocatedSegmentDto(
                        machine_id=m.id,
                        machine_code=m.asset_code,
                        machine_name=m.name,
                        start=_point(i.start),
                        end=_point(i.end),
                        hours=i.hours,
                        review=i.review,
                        classification=i.classification,
                        opened_at=i.opened_at,
                        age_days=age,
                        investigation_due=bool(
                            i.open_item and days is not None and self._now - i.opened_at >= timedelta(days=days)
                        ),
                        approved=_ref(i.approved),
                        proposal=_ref(i.proposal),
                    )
                )
        return sorted(out, key=lambda x: (x.opened_at, x.machine_code))

    # --- classifications ---------------------------------------------------------------------------------------
    def _classification_dtos(self, rows: list[EngineHourClassification]) -> list[ClassificationDto]:
        names = _names(self._s, {r.proposed_by for r in rows} | {r.decided_by for r in rows})
        machines = dict(
            self._s.execute(
                select(Machine.id, Machine.asset_code).where(Machine.id.in_({r.machine_id for r in rows}))
            ).all()
        )
        reasons = dict(
            self._s.execute(
                select(EngineHourReason.id, EngineHourReason.name).where(
                    EngineHourReason.id.in_({r.reason_id for r in rows})
                )
            ).all()
        )
        return [
            ClassificationDto.model_validate(r).model_copy(
                update={
                    "machine_code": machines.get(r.machine_id),
                    "reason_name": reasons.get(r.reason_id),
                    "proposed_by_name": names.get(r.proposed_by) if r.proposed_by else None,
                    "decided_by_name": names.get(r.decided_by) if r.decided_by else None,
                }
            )
            for r in rows
        ]

    def classification_query(
        self, q: str | None, machine_id: uuid.UUID | None, status: MeterProposalStatus | None
    ) -> Select[EngineHourClassification]:
        stmt = (
            select(EngineHourClassification)
            .join(Machine, Machine.id == EngineHourClassification.machine_id)
            .order_by(EngineHourClassification.proposed_at.desc(), EngineHourClassification.id)
        )
        if (match := ilike_any(q, Machine.asset_code, Machine.name, EngineHourClassification.note)) is not None:
            stmt = stmt.where(match)
        if machine_id is not None:
            stmt = stmt.where(EngineHourClassification.machine_id == machine_id)
        if status is not None:
            stmt = stmt.where(EngineHourClassification.status == status)
        visible = self._visible_machine_ids()
        if visible is not None:
            stmt = stmt.where(EngineHourClassification.machine_id.in_(visible))
        return stmt

    def classification_dtos(self, rows: list[EngineHourClassification]) -> list[ClassificationDto]:
        return self._classification_dtos(rows)

    def classification(self, classification_id: uuid.UUID, lock: bool = False) -> EngineHourClassification:
        stmt = select(EngineHourClassification).where(EngineHourClassification.id == classification_id)
        row = self._s.execute(stmt.with_for_update() if lock else stmt).scalar_one_or_none()
        visible = self._visible_machine_ids()
        if row is None or (visible is not None and row.machine_id not in visible):
            raise NotFound("Classification not found")
        return row

    def _segment(self, ml: MachineLedger, start_ref: uuid.UUID, end_ref: uuid.UUID) -> LedgerInterval:
        if not ml.reconciling:
            raise BusinessRuleViolation(
                "Reconciliation starts at an approved baseline; approve one first", code="BASELINE_REQUIRED"
            )
        found = next((i for i in ml.ledger.intervals if i.key == (start_ref, end_ref)), None)
        if found is None:
            raise NotFound("Segment not found in the machine's current ledger", code="SEGMENT_NOT_FOUND")
        return found

    def propose_classification(self, body: ClassificationIn) -> ClassificationDto:
        ml = self.machine_ledger(body.machine_id)
        seg = self._segment(ml, body.start_ref, body.end_ref)
        if not seg.open_item:
            raise BusinessRuleViolation(
                f"Only verified, unexplained engine hours can be classified (this segment is "
                f"{seg.kind.value}/{seg.classification.value}/{seg.review.value})",
                code="SEGMENT_NOT_UNEXPLAINED",
            )
        if seg.proposal is not None:
            raise Conflict("A classification of this segment awaits a decision", code="CLASSIFICATION_PENDING")
        reason = self.reason(body.reason_id)
        if reason.kind is not OUTCOME_REASON_KIND[body.outcome] or not reason.is_active:
            raise BusinessRuleViolation(
                f"{body.outcome.value} needs an active {OUTCOME_REASON_KIND[body.outcome].value} entry",
                code="REASON_NOT_ALLOWED",
            )
        policy = ml.policy.policy
        direct = not policy.classification_requires_approval and CLASSIFY_PERMISSION in self._ctx.permissions
        row = EngineHourClassification(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            machine_id=ml.machine.id,
            start_ref=seg.start.ref,
            end_ref=seg.end.ref,
            start_at=seg.start.at,
            end_at=seg.end.at,
            hours=seg.hours,
            outcome=body.outcome,
            reason_id=reason.id,
            note=body.note,
            status=MeterProposalStatus.APPROVED if direct else MeterProposalStatus.PROPOSED,
            proposed_by=self._ctx.user_id,
            proposed_at=self._now,
            decided_by=self._ctx.user_id if direct else None,
            decided_at=self._now if direct else None,
            decision_note="Approval not required by tenant policy" if direct else None,
            policy_version=ml.policy.version_stamp,
        )
        try:
            with self._s.begin_nested():
                self._s.add(row)
                self._s.flush()
        except IntegrityError as exc:
            raise Conflict("This segment is already classified", code="CLASSIFICATION_PENDING") from exc
        after = {
            "machine_id": str(row.machine_id),
            "start_ref": str(row.start_ref),
            "end_ref": str(row.end_ref),
            "hours": str(row.hours),
            "outcome": row.outcome.value,
            "reason_id": str(row.reason_id),
            "status": row.status.value,
        }
        self._record("meter.classification.proposed", "engine_hour_classification", row.id, None, after, body.note)
        if direct:
            self._close_flag(row)
        else:
            self._emit(
                "EngineHoursClassificationProposed",
                row.machine_id,
                {"classification_id": str(row.id), "machine_id": str(row.machine_id), "hours": str(row.hours)},
            )
        return self._classification_dtos([row])[0]

    def _close_flag(self, row: EngineHourClassification) -> None:
        """The segment's UNEXPLAINED_HOURS flag is reviewed by the classification decision (a person's decision)."""
        flag = self._s.execute(
            select(JobException)
            .where(
                JobException.dedupe_key == unexplained_dedupe(row.machine_id, row.start_ref, row.end_ref),
                JobException.exception_type == ExceptionType.UNEXPLAINED_HOURS,
                JobException.status == ExceptionStatus.OPEN,
            )
            .with_for_update()
        ).scalar_one_or_none()
        if flag is not None:
            flag.status, flag.reviewed_by, flag.reviewed_at = ExceptionStatus.EXPLAINED, row.decided_by, self._now
            flag.review_note = f"Classified {row.outcome.value} ({row.id})"
            self._s.flush()

    def decide_classification(self, classification_id: uuid.UUID, body: MeterDecisionIn) -> ClassificationDto:
        row = self.classification(classification_id, lock=True)
        if row.status is not MeterProposalStatus.PROPOSED:
            raise Conflict("Classification already decided", code="ALREADY_DECIDED")
        self._sod(row.proposed_by, "engine_hour_classification", row.id)
        approve = body.decision == "APPROVE"
        if approve:  # the segment must still be exactly the one that was explained
            ml = self.machine_ledger(row.machine_id)
            seg = next((i for i in ml.ledger.intervals if i.key == (row.start_ref, row.end_ref)), None)
            if seg is None or seg.hours != row.hours:
                raise Conflict(
                    "The segment changed since this was proposed (a correction or late reading); propose again",
                    code="SEGMENT_CHANGED",
                )
        row.status = MeterProposalStatus.APPROVED if approve else MeterProposalStatus.REJECTED
        row.decided_by, row.decided_at, row.decision_note = self._ctx.user_id, self._now, body.note
        self._s.flush()
        self._record(
            f"meter.classification.{'approved' if approve else 'rejected'}",
            "engine_hour_classification",
            row.id,
            {"status": MeterProposalStatus.PROPOSED.value},
            {"status": row.status.value, "outcome": row.outcome.value, "hours": str(row.hours)},
            body.note,
        )
        if approve:
            self._close_flag(row)
        return self._classification_dtos([row])[0]

    # --- corrections -------------------------------------------------------------------------------------------
    def _correction_dtos(self, rows: list[MeterCorrection]) -> list[CorrectionDto]:
        names = _names(self._s, {r.proposed_by for r in rows} | {r.decided_by for r in rows})
        machines = dict(
            self._s.execute(
                select(Machine.id, Machine.asset_code).where(Machine.id.in_({r.machine_id for r in rows}))
            ).all()
        )
        return [
            CorrectionDto.model_validate(r).model_copy(
                update={
                    "machine_code": machines.get(r.machine_id),
                    "proposed_by_name": names.get(r.proposed_by) if r.proposed_by else None,
                    "decided_by_name": names.get(r.decided_by) if r.decided_by else None,
                }
            )
            for r in rows
        ]

    def correction_dtos(self, rows: list[MeterCorrection]) -> list[CorrectionDto]:
        return self._correction_dtos(rows)

    def correction_query(
        self, q: str | None, machine_id: uuid.UUID | None, status: MeterProposalStatus | None
    ) -> Select[MeterCorrection]:
        stmt = (
            select(MeterCorrection)
            .join(Machine, Machine.id == MeterCorrection.machine_id)
            .order_by(MeterCorrection.proposed_at.desc(), MeterCorrection.id)
        )
        if (match := ilike_any(q, Machine.asset_code, Machine.name, MeterCorrection.reason)) is not None:
            stmt = stmt.where(match)
        if machine_id is not None:
            stmt = stmt.where(MeterCorrection.machine_id == machine_id)
        if status is not None:
            stmt = stmt.where(MeterCorrection.status == status)
        if self._own_only():
            stmt = stmt.where(MeterCorrection.proposed_by == self._ctx.user_id)
        return stmt

    def correction(self, correction_id: uuid.UUID, lock: bool = False) -> MeterCorrection:
        stmt = select(MeterCorrection).where(MeterCorrection.id == correction_id)
        row = self._s.execute(stmt.with_for_update() if lock else stmt).scalar_one_or_none()
        if row is None or (self._own_only() and row.proposed_by != self._ctx.user_id):
            raise NotFound("Correction not found")
        return row

    def propose_correction(self, body: CorrectionIn, device_session_id: uuid.UUID | None = None) -> CorrectionDto:
        replay = self._s.execute(
            select(MeterCorrection).where(MeterCorrection.replacement_capture_id == body.replacement.id)
        ).scalar_one_or_none()
        if replay is not None:  # idempotent replay (offline retry)
            if replay.superseded_capture_id != body.superseded_capture_id:
                raise Conflict("Replacement id reused with different content", code="CAPTURE_ID_CONFLICT")
            return self._correction_dtos([replay])[0]
        old = self._s.execute(
            select(MeterCapture).where(MeterCapture.id == body.superseded_capture_id).with_for_update()
        ).scalar_one_or_none()
        if old is None or (
            self._own_only()
            and old.supervisor_user_id != self._ctx.user_id
            and old.machine_id not in (self._visible_machine_ids() or set())
        ):
            raise NotFound("Reading not found", code="CAPTURE_NOT_FOUND")
        if old.state not in LIVE:
            raise Conflict("Only a live reading can be corrected", code="CAPTURE_NOT_ACTIVE")
        rep = body.replacement
        if rep.kind is not old.kind or rep.job_id != old.job_id or (rep.machine_id or old.machine_id) != old.machine_id:
            raise BusinessRuleViolation(
                "The replacement must be the same kind of reading for the same job and machine",
                code="CORRECTION_MISMATCH",
            )
        if self._s.get(MeterCapture, rep.id) is not None:
            raise Conflict("Replacement id already used by a reading", code="CAPTURE_ID_CONFLICT")
        eff = PolicyService(self._s).engine_hours(self._tid, old.machine_id, at=self._now)
        payload = rep.model_copy(update={"supersedes_id": old.id, "machine_id": old.machine_id})
        row = MeterCorrection(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            machine_id=old.machine_id,
            job_id=old.job_id,
            superseded_capture_id=old.id,
            replacement_capture_id=rep.id,
            replacement=payload.model_dump(mode="json"),
            old_reading=old.reading,
            new_reading=rep.reading,
            reason=body.reason,
            status=MeterProposalStatus.PROPOSED,
            proposed_by=self._ctx.user_id,
            proposed_at=self._now,
            policy_version=eff.version_stamp,
        )
        try:
            with self._s.begin_nested():
                self._s.add(row)
                self._s.flush()
        except IntegrityError as exc:
            raise Conflict("A correction of this reading awaits a decision", code="CORRECTION_PENDING") from exc
        self._record(
            "meter.correction.proposed",
            "meter_correction",
            row.id,
            {"capture_id": str(old.id), "reading": str(old.reading)},
            {"replacement_capture_id": str(rep.id), "reading": str(rep.reading)},
            body.reason,
        )
        if not eff.policy.correction_requires_second_person and APPROVE_PERMISSION in self._ctx.permissions:
            self._apply_correction(row, old, "Second person not required by tenant policy", device_session_id)
        else:
            self._emit(
                "MeterCorrectionProposed",
                row.machine_id,
                {"correction_id": str(row.id), "machine_id": str(row.machine_id), "capture_id": str(old.id)},
            )
        return self._correction_dtos([row])[0]

    def decide_correction(self, correction_id: uuid.UUID, body: MeterDecisionIn) -> CorrectionDto:
        row = self.correction(correction_id, lock=True)
        if row.status is not MeterProposalStatus.PROPOSED:
            raise Conflict("Correction already decided", code="ALREADY_DECIDED")
        self._sod(row.proposed_by, "meter_correction", row.id)
        if body.decision == "REJECT":
            row.status = MeterProposalStatus.REJECTED
            row.decided_by, row.decided_at, row.decision_note = self._ctx.user_id, self._now, body.note
            self._s.flush()
            self._record(
                "meter.correction.rejected",
                "meter_correction",
                row.id,
                {"status": MeterProposalStatus.PROPOSED.value},
                {"status": row.status.value},
                body.note,
            )
            return self._correction_dtos([row])[0]
        old = self._s.execute(
            select(MeterCapture).where(MeterCapture.id == row.superseded_capture_id).with_for_update()
        ).scalar_one()
        if old.state not in LIVE:
            raise Conflict("The reading was already superseded or rejected", code="CAPTURE_NOT_ACTIVE")
        self._apply_correction(row, old, body.note, None)
        return self._correction_dtos([row])[0]

    def _apply_correction(
        self, row: MeterCorrection, old: MeterCapture, note: str, device_session_id: uuid.UUID | None
    ) -> None:
        """Record the replacement through the normal capture pipeline (same evidence rules and findings), as the
        proposer's reading, and supersede the old one. Audited with before/after and the superseded id."""
        before_state = old.state.value
        result = MeterService(self._s, self._ctx, self._now).submit(
            MeterCaptureIn.model_validate(row.replacement),
            device_session_id,
            correction_of=old,
            recorded_by=row.proposed_by,
        )
        row.status = MeterProposalStatus.APPROVED
        row.decided_by, row.decided_at, row.decision_note = self._ctx.user_id, self._now, note
        self._s.flush()
        self._record(
            "meter.correction.approved",
            "meter_correction",
            row.id,
            {"capture_id": str(old.id), "reading": str(old.reading), "state": before_state},
            {
                "superseded_capture_id": str(old.id),
                "superseded_state": CaptureState.SUPERSEDED.value,
                "replacement_capture_id": str(result.capture.id),
                "reading": str(result.capture.reading),
                "replacement_state": result.capture.state.value,
            },
            f"{row.reason} | decision: {note}",
        )
        self._emit(
            "MeterCorrectionApplied",
            row.machine_id,
            {
                "correction_id": str(row.id),
                "superseded_capture_id": str(old.id),
                "replacement_capture_id": str(result.capture.id),
            },
        )
