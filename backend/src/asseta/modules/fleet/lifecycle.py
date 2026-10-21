"""Fleet record lifecycle: details/edit/deactivate/reactivate for categories, areas and staff, and machine
retirement (status DISPOSED) / reinstatement. Nothing is hard-deleted; every change is audited with a reason."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.db import utcnow
from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound
from asseta.core.lifecycle import check_version, flush_versioned, mark_active, mark_inactive
from asseta.core.search import ilike_any
from asseta.modules.finance.cash_service import CashCustodyService
from asseta.modules.fleet.dto import (
    AreaDto,
    AreaUpdateIn,
    CategoryDto,
    CategoryUpdateIn,
    MachineDto,
    StaffDto,
    StaffUpdateIn,
)
from asseta.modules.fleet.models import (
    Machine,
    MachineAssignment,
    MachineCategory,
    MachineStatus,
    OperatingArea,
    StaffMember,
)
from asseta.modules.identity.principal import RequestContext
from asseta.modules.jobs.models import Job, JobStatus
from asseta.modules.platform_billing.models_ledger import SubscriptionAssetEnrollment
from asseta.modules.tracker.models import TrackerAssignment

OPEN_JOB_STATES = (JobStatus.DRAFT, JobStatus.PENDING_APPROVAL, JobStatus.APPROVED, JobStatus.IN_PROGRESS)
RUNNING_JOB_STATES = (JobStatus.APPROVED, JobStatus.IN_PROGRESS)


class FleetLifecycleService:
    def __init__(self, session: Session, ctx: RequestContext, now: datetime):
        """`now` is the request clock: assignment ends and cash balances are evaluated at that instant."""
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid, self._now = session, ctx, ctx.tenant_id, now
        self._audit = AuditService(session)

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
        )

    def _get[T](self, model: type[T], row_id: uuid.UUID, label: str) -> T:
        id_col: Any = model.id  # type: ignore[attr-defined]
        row = self._s.execute(select(model).where(id_col == row_id).with_for_update()).scalar_one_or_none()
        if row is None:  # other tenants' rows are invisible under RLS
            raise NotFound(f"{label} not found")
        return row

    # --- machine categories -------------------------------------------------------------------------
    def category(self, category_id: uuid.UUID) -> CategoryDto:
        return CategoryDto.model_validate(self._get(MachineCategory, category_id, "Machine category"))

    def update_category(self, category_id: uuid.UUID, body: CategoryUpdateIn) -> CategoryDto:
        cat = self._get(MachineCategory, category_id, "Machine category")
        check_version(cat.version, body.version, "Machine category")
        before = CategoryDto.model_validate(cat).model_dump(mode="json")
        cat.name, cat.description = body.name, body.description
        flush_versioned(self._s, "Machine category", "DUPLICATE_CATEGORY", "Category name already exists")
        dto = CategoryDto.model_validate(cat)
        self._record("fleet.category.updated", "machine_category", cat.id, before, dto.model_dump(mode="json"))
        return dto

    def set_category_active(
        self, category_id: uuid.UUID, active: bool, reason: str, version: int | None
    ) -> CategoryDto:
        """Deactivated categories leave existing machines/rate cards untouched; they are only not offered anew."""
        cat = self._get(MachineCategory, category_id, "Machine category")
        check_version(cat.version, version, "Machine category")
        self._toggle(cat, active, reason, "Machine category")
        dto = CategoryDto.model_validate(cat)
        verb = "reactivated" if active else "deactivated"
        self._record(f"fleet.category.{verb}", "machine_category", cat.id, None, dto.model_dump(mode="json"), reason)
        return dto

    # --- operating areas ----------------------------------------------------------------------------
    def area(self, area_id: uuid.UUID) -> AreaDto:
        return AreaDto.model_validate(self._get(OperatingArea, area_id, "Operating area"))

    def update_area(self, area_id: uuid.UUID, body: AreaUpdateIn) -> AreaDto:
        area = self._get(OperatingArea, area_id, "Operating area")
        check_version(area.version, body.version, "Operating area")
        before = AreaDto.model_validate(area).model_dump(mode="json")
        area.code, area.name = body.code, body.name
        flush_versioned(self._s, "Operating area", "DUPLICATE_AREA", "Operating area code already exists")
        dto = AreaDto.model_validate(area)
        self._record("fleet.area.updated", "operating_area", area.id, before, dto.model_dump(mode="json"))
        return dto

    def set_area_active(self, area_id: uuid.UUID, active: bool, reason: str, version: int | None) -> AreaDto:
        area = self._get(OperatingArea, area_id, "Operating area")
        check_version(area.version, version, "Operating area")
        self._toggle(area, active, reason, "Operating area")
        dto = AreaDto.model_validate(area)
        verb = "reactivated" if active else "deactivated"
        self._record(f"fleet.area.{verb}", "operating_area", area.id, None, dto.model_dump(mode="json"), reason)
        return dto

    def _toggle(self, row: Any, active: bool, reason: str, label: str) -> None:
        if active:
            mark_active(row, label)
        else:
            mark_inactive(row, self._ctx.user_id, reason, label)
        flush_versioned(self._s, label)

    # --- staff --------------------------------------------------------------------------------------
    def staff(self, staff_id: uuid.UUID) -> StaffDto:
        return StaffDto.model_validate(self._get(StaffMember, staff_id, "Staff member"))

    def _open_assignments(self, staff_id: uuid.UUID) -> Select[MachineAssignment]:
        return select(MachineAssignment).where(
            MachineAssignment.staff_member_id == staff_id, MachineAssignment.effective_to.is_(None)
        )

    def update_staff(self, staff_id: uuid.UUID, body: StaffUpdateIn) -> StaffDto:
        staff = self._get(StaffMember, staff_id, "Staff member")
        check_version(staff.version, body.version, "Staff member")
        if body.kind is not staff.kind and self._s.execute(self._open_assignments(staff.id)).first() is not None:
            raise BusinessRuleViolation(
                "End this person's machine assignments before changing their kind", code="STAFF_ASSIGNED"
            )
        before = StaffDto.model_validate(staff).model_dump(mode="json")
        for key, value in body.model_dump(exclude={"version"}).items():
            setattr(staff, key, value)
        flush_versioned(
            self._s, "Staff member", "DUPLICATE_STAFF", "Employee code or login already linked to another staff member"
        )
        dto = StaffDto.model_validate(staff)
        reason = "Login link changed" if before["keycloak_subject"] != dto.keycloak_subject else None
        self._record("fleet.staff.updated", "staff_member", staff.id, before, dto.model_dump(mode="json"), reason)
        return dto

    def set_staff_active(self, staff_id: uuid.UUID, active: bool, reason: str, version: int | None) -> StaffDto:
        """Deactivation is refused while the person supervises an approved/running job or holds company cash;
        otherwise their open machine assignments are ended now (history kept)."""
        staff = self._get(StaffMember, staff_id, "Staff member")
        check_version(staff.version, version, "Staff member")
        if not active:
            self._guard_staff_deactivation(staff)
            self._end_assignments(self._open_assignments(staff.id), reason)
        self._toggle(staff, active, reason, "Staff member")
        dto = StaffDto.model_validate(staff)
        verb = "reactivated" if active else "deactivated"
        self._record(f"fleet.staff.{verb}", "staff_member", staff.id, None, dto.model_dump(mode="json"), reason)
        return dto

    def _end_assignments(self, stmt: Select[MachineAssignment], reason: str) -> None:
        """Close open assignments now (a future-dated one cannot be closed before it starts: refuse)."""
        now = self._now
        for row in self._s.execute(stmt.with_for_update()).scalars():
            if row.effective_from >= now:
                raise BusinessRuleViolation(
                    "An assignment starts in the future; end it explicitly first", code="ASSIGNMENT_DATES"
                )
            row.effective_to = now
            self._record(
                "fleet.assignment.ended", "machine_assignment", row.id, None, {"effective_to": now.isoformat()}, reason
            )
        self._s.flush()

    def _guard_staff_deactivation(self, staff: StaffMember) -> None:
        running = self._s.execute(
            select(Job.id).where(Job.supervisor_id == staff.id, Job.status.in_(RUNNING_JOB_STATES))
        ).first()
        if running is not None:
            raise BusinessRuleViolation(
                "Staff member supervises an approved or running job; reassign it first", code="STAFF_HAS_ACTIVE_JOBS"
            )
        balances = CashCustodyService(self._s, self._ctx, self._now).balances(staff.id)
        if any(b.outstanding != 0 or b.claimed_unverified_handovers != 0 for b in balances):
            raise BusinessRuleViolation(
                "Staff member still holds company cash; settle the custody first", code="STAFF_HOLDS_CASH"
            )

    # --- machines: retire (DISPOSED) / reinstate ------------------------------------------------------
    def guard_machine_retirement(self, machine: Machine) -> None:
        """A machine can be retired only when nothing operational or billable still depends on it."""
        if self._s.execute(select(Job.id).where(Job.machine_id == machine.id, Job.status.in_(OPEN_JOB_STATES))).first():
            raise BusinessRuleViolation(
                "Machine has open jobs; complete or cancel them first", code="MACHINE_HAS_OPEN_JOBS"
            )
        if self._s.execute(
            select(TrackerAssignment.id).where(
                TrackerAssignment.machine_id == machine.id, TrackerAssignment.effective_to.is_(None)
            )
        ).first():
            raise BusinessRuleViolation("Unassign the machine's tracker first", code="MACHINE_HAS_TRACKER")
        enrollment = SubscriptionAssetEnrollment
        enrolled = self._s.execute(  # current or scheduled (not yet ended) billable enrollment
            select(enrollment.id).where(
                enrollment.machine_id == machine.id,
                or_(enrollment.effective_to.is_(None), enrollment.effective_to > self._now.date()),
            )
        ).first()
        if enrolled is not None:
            raise BusinessRuleViolation(
                "Machine is an enrolled billable asset; unenroll it first", code="MACHINE_ENROLLED"
            )

    def end_machine_assignments(self, machine: Machine, reason: str) -> None:
        self._end_assignments(
            select(MachineAssignment).where(
                MachineAssignment.machine_id == machine.id, MachineAssignment.effective_to.is_(None)
            ),
            reason,
        )

    def set_machine_active(self, machine_id: uuid.UUID, active: bool, reason: str, version: int | None) -> MachineDto:
        machine = self._get(Machine, machine_id, "Machine")
        check_version(machine.version, version, "Machine")
        before = MachineDto.model_validate(machine).model_dump(mode="json")
        if active:
            if machine.status is not MachineStatus.DISPOSED:
                raise Conflict("Machine is not retired", code="ALREADY_ACTIVE")
            machine.status = MachineStatus.ACTIVE
            machine.deactivated_at = machine.deactivated_by = machine.deactivation_reason = None
        else:
            if machine.status is MachineStatus.DISPOSED:
                raise Conflict("Machine is already retired", code="ALREADY_INACTIVE")
            self.guard_machine_retirement(machine)
            self.end_machine_assignments(machine, reason)
            machine.status = MachineStatus.DISPOSED
            machine.deactivated_at, machine.deactivated_by, machine.deactivation_reason = (
                utcnow(),
                self._ctx.user_id,
                reason,
            )
        flush_versioned(self._s, "Machine")
        dto = MachineDto.model_validate(machine)
        verb = "reinstated" if active else "retired"
        self._record(f"fleet.machine.{verb}", "machine", machine.id, before, dto.model_dump(mode="json"), reason)
        return dto


def active_filter(stmt: Select[Any], model: Any, include_inactive: bool) -> Select[Any]:
    return stmt if include_inactive else stmt.where(model.is_active.is_(True))


def category_query(q: str | None, include_inactive: bool) -> Select[MachineCategory]:
    stmt = select(MachineCategory).order_by(MachineCategory.name)
    if (match := ilike_any(q, MachineCategory.name)) is not None:
        stmt = stmt.where(match)
    return active_filter(stmt, MachineCategory, include_inactive)


def area_query(q: str | None, include_inactive: bool) -> Select[OperatingArea]:
    stmt = select(OperatingArea).order_by(OperatingArea.code)
    if (match := ilike_any(q, OperatingArea.code, OperatingArea.name)) is not None:
        stmt = stmt.where(match)
    return active_filter(stmt, OperatingArea, include_inactive)
