"""Tracker registry use cases (tenant scope, except the platform-owned model catalog)."""

import uuid
from datetime import datetime

from sqlalchemy import Select, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from asseta.core.audit import AuditActor, AuditService
from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound
from asseta.modules.fleet.models import Machine, MachineStatus
from asseta.modules.platform_billing.models_ledger import SubscriptionAssetEnrollment
from asseta.modules.platform_billing.repository import active_on
from asseta.modules.tracker.dto import (
    AssignTrackerIn,
    CapabilityDto,
    TrackerAssignmentDto,
    TrackerDto,
    TrackerIn,
    TrackerModelDto,
    TrackerModelIn,
)
from asseta.modules.tracker.models import (
    Capability,
    ProvisioningState,
    Tracker,
    TrackerAssignment,
    TrackerCapability,
    TrackerModel,
)

_STATE_TRANSITIONS = {
    ProvisioningState.REGISTERED: {ProvisioningState.SUSPENDED, ProvisioningState.RETIRED},
    ProvisioningState.VERIFIED_REPORTING: {ProvisioningState.SUSPENDED, ProvisioningState.RETIRED},
    ProvisioningState.SUSPENDED: {ProvisioningState.REGISTERED, ProvisioningState.RETIRED},
    ProvisioningState.RETIRED: set(),
}


def create_tracker_model(session: Session, body: TrackerModelIn, actor: AuditActor) -> TrackerModelDto:
    row = TrackerModel(
        id=uuid.uuid4(), **{**body.model_dump(), "declared_capabilities": [c.value for c in body.declared_capabilities]}
    )
    try:
        with session.begin_nested():
            session.add(row)
            session.flush()
    except IntegrityError as exc:
        raise Conflict("Tracker model already exists", code="DUPLICATE_TRACKER_MODEL") from exc
    dto = TrackerModelDto.model_validate(row)
    AuditService(session).record(
        actor=actor,
        action="platform.tracker_model.created",
        entity_type="tracker_model",
        entity_id=row.id,
        tenant_id=None,
        after=dto.model_dump(mode="json"),
    )
    return dto


class TrackerService:
    def __init__(self, session: Session, tenant_id: uuid.UUID, actor: AuditActor):
        self._s, self._tenant_id, self._actor = session, tenant_id, actor
        self._audit = AuditService(session)

    def _audit_change(
        self, action: str, entity_id: uuid.UUID, after: dict[str, object], reason: str | None = None
    ) -> None:
        self._audit.record(
            actor=self._actor,
            action=action,
            entity_type="tracker",
            entity_id=entity_id,
            tenant_id=self._tenant_id,
            after=after,
            reason=reason,
        )

    def tracker(self, tracker_id: uuid.UUID, lock: bool = False) -> Tracker:
        stmt = select(Tracker).where(Tracker.id == tracker_id)
        row = self._s.execute(stmt.with_for_update() if lock else stmt).scalar_one_or_none()
        if row is None:
            raise NotFound("Tracker not found")
        return row

    def to_dto(self, t: Tracker) -> TrackerDto:
        caps = self._s.execute(
            select(TrackerCapability).where(TrackerCapability.tracker_id == t.id).order_by(TrackerCapability.capability)
        ).scalars()
        current = self._s.execute(
            select(TrackerAssignment).where(
                TrackerAssignment.tracker_id == t.id, TrackerAssignment.effective_to.is_(None)
            )
        ).scalar_one_or_none()
        dto = TrackerDto.model_validate(t)
        dto.capabilities = [CapabilityDto.model_validate(c) for c in caps]
        dto.current_assignment = TrackerAssignmentDto.model_validate(current) if current else None
        return dto

    def register(self, body: TrackerIn) -> TrackerDto:
        model = self._s.get(TrackerModel, body.tracker_model_id)
        if model is None or not model.approved:
            raise BusinessRuleViolation("Tracker model is not an approved driver", code="TRACKER_MODEL_NOT_APPROVED")
        tracker = Tracker(
            id=uuid.uuid4(),
            tenant_id=self._tenant_id,
            adapter=model.adapter,
            provisioning_state=ProvisioningState.REGISTERED,
            **body.model_dump(),
        )
        try:
            with self._s.begin_nested():
                self._s.add(tracker)
                self._s.flush()
        except IntegrityError as exc:
            raise Conflict(
                "This device identity is already registered", code="TRACKER_EXTERNAL_ID_UNAVAILABLE"
            ) from exc
        declared = set(model.declared_capabilities)
        for cap in Capability:
            self._s.add(
                TrackerCapability(
                    tracker_id=tracker.id, capability=cap, tenant_id=self._tenant_id, declared=cap.value in declared
                )
            )
        self._s.flush()
        dto = self.to_dto(tracker)
        self._audit_change(
            "tracker.registered",
            tracker.id,
            {"external_id": tracker.external_id, "model": f"{model.manufacturer} {model.model}"},
        )
        return dto

    def list_query(self, q: str | None, state: ProvisioningState | None) -> Select[Tracker]:
        stmt = select(Tracker).order_by(Tracker.label)
        if q:
            stmt = stmt.where(or_(Tracker.label.ilike(f"%{q}%"), Tracker.external_id.ilike(f"%{q}%")))
        if state:
            stmt = stmt.where(Tracker.provisioning_state == state)
        return stmt

    def change_state(self, tracker_id: uuid.UUID, state: ProvisioningState, reason: str, at: datetime) -> TrackerDto:
        tracker = self.tracker(tracker_id, lock=True)
        if state not in _STATE_TRANSITIONS[tracker.provisioning_state]:
            raise BusinessRuleViolation(
                f"{tracker.provisioning_state.value} -> {state.value} not allowed", code="INVALID_TRACKER_STATE"
            )
        if state is ProvisioningState.RETIRED:
            self._end_open_assignment(tracker.id, at, f"Tracker retired: {reason}")
        tracker.provisioning_state = state
        self._s.flush()
        self._audit_change("tracker.state_changed", tracker.id, {"state": state.value}, reason)
        return self.to_dto(tracker)

    def _end_open_assignment(self, tracker_id: uuid.UUID, at: datetime, reason: str) -> None:
        open_row = self._s.execute(
            select(TrackerAssignment)
            .where(TrackerAssignment.tracker_id == tracker_id, TrackerAssignment.effective_to.is_(None))
            .with_for_update()
        ).scalar_one_or_none()
        if open_row is not None:
            if at <= open_row.effective_from:
                raise BusinessRuleViolation("End must be after assignment start", code="ASSIGNMENT_DATES")
            open_row.effective_to, open_row.reason = at, reason
            self._s.flush()

    def assign(self, tracker_id: uuid.UUID, body: AssignTrackerIn) -> TrackerAssignmentDto:
        tracker = self.tracker(tracker_id, lock=True)
        if tracker.provisioning_state in (ProvisioningState.SUSPENDED, ProvisioningState.RETIRED):
            raise BusinessRuleViolation("Tracker is not assignable in its current state", code="TRACKER_NOT_ASSIGNABLE")
        machine = self._s.execute(
            select(Machine).where(Machine.id == body.machine_id).with_for_update()
        ).scalar_one_or_none()
        if machine is None:
            raise NotFound("Machine not found")
        if machine.status is MachineStatus.DISPOSED:
            raise BusinessRuleViolation("Disposed machines cannot be tracked", code="MACHINE_DISPOSED")
        enrolled = self._s.execute(
            select(SubscriptionAssetEnrollment.id).where(
                SubscriptionAssetEnrollment.machine_id == machine.id, active_on(body.effective_from.date())
            )
        ).first()
        if enrolled is None:  # DEC-014: no tracking of machines outside the billable fleet
            raise BusinessRuleViolation(
                "Machine must be an enrolled billable asset before tracking", code="MACHINE_NOT_ENROLLED"
            )
        existing = self._s.execute(
            select(TrackerAssignment).where(
                TrackerAssignment.tracker_id == tracker.id, TrackerAssignment.effective_to.is_(None)
            )
        ).scalar_one_or_none()
        if existing is not None:
            if existing.machine_id == machine.id and existing.is_primary == body.is_primary:
                return TrackerAssignmentDto.model_validate(existing)  # idempotent retry
            raise Conflict("Tracker is assigned to another machine; unassign it first", code="TRACKER_ASSIGNED")
        if body.is_primary:
            primary = self._s.execute(
                select(TrackerAssignment)
                .where(
                    TrackerAssignment.machine_id == machine.id,
                    TrackerAssignment.is_primary.is_(True),
                    TrackerAssignment.effective_to.is_(None),
                )
                .with_for_update()
            ).scalar_one_or_none()
            if primary is not None:
                if not body.replace_existing_primary:
                    raise Conflict("Machine already has a primary tracker", code="PRIMARY_TRACKER_EXISTS")
                if body.effective_from <= primary.effective_from:
                    raise BusinessRuleViolation("Swap must start after the current primary", code="ASSIGNMENT_DATES")
                primary.effective_to, primary.reason = body.effective_from, f"Replaced: {body.reason or 'tracker swap'}"
                self._s.flush()
        row = TrackerAssignment(
            id=uuid.uuid4(),
            tenant_id=self._tenant_id,
            tracker_id=tracker.id,
            machine_id=machine.id,
            is_primary=body.is_primary,
            effective_from=body.effective_from,
            reason=body.reason,
            created_by=self._actor.user_id,
        )
        self._s.add(row)
        self._s.flush()
        dto = TrackerAssignmentDto.model_validate(row)
        self._audit_change("tracker.assigned", tracker.id, dto.model_dump(mode="json"), body.reason)
        return dto

    def unassign(self, tracker_id: uuid.UUID, at: datetime, reason: str) -> TrackerDto:
        tracker = self.tracker(tracker_id, lock=True)
        self._end_open_assignment(tracker.id, at, reason)
        self._audit_change("tracker.unassigned", tracker.id, {"effective_to": at.isoformat()}, reason)
        return self.to_dto(tracker)

    def assignments_for_machine(self, machine_id: uuid.UUID) -> list[TrackerAssignmentDto]:
        rows = self._s.execute(
            select(TrackerAssignment)
            .where(TrackerAssignment.machine_id == machine_id)
            .order_by(TrackerAssignment.effective_from.desc())
        ).scalars()
        return [TrackerAssignmentDto.model_validate(r) for r in rows]
