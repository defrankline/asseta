"""Fleet registry use cases. All queries run under the caller's tenant RLS scope."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from asseta.core.audit import AuditService
from asseta.core.db import utcnow
from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound
from asseta.core.search import ilike_any
from asseta.modules.fleet.dto import (
    AreaDto,
    AreaIn,
    AssignIn,
    AssignmentDto,
    CategoryDto,
    CategoryIn,
    MachineCreateIn,
    MachineDto,
    MachineUpdateIn,
    StaffDto,
    StaffIn,
)
from asseta.modules.fleet.lifecycle import FleetLifecycleService, area_query, category_query
from asseta.modules.fleet.models import (
    Machine,
    MachineAssignment,
    MachineCategory,
    MachineStatus,
    OperatingArea,
    StaffKind,
    StaffMember,
)
from asseta.modules.identity.principal import RequestContext


class MachineService:
    def __init__(self, session: Session, ctx: RequestContext):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tenant_id = session, ctx, ctx.tenant_id
        self._audit = AuditService(session)

    # --- helpers ------------------------------------------------------------------------------------
    def _insert(self, obj: Any, conflict_code: str, message: str) -> None:
        try:
            with self._s.begin_nested():
                self._s.add(obj)
                self._s.flush()
        except IntegrityError as exc:
            raise Conflict(message, code=conflict_code) from exc

    def _record(
        self,
        action: str,
        entity: str,
        entity_id: uuid.UUID,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
    ) -> None:
        self._audit.record(
            actor=self._ctx.audit_actor(),
            action=action,
            entity_type=entity,
            entity_id=entity_id,
            tenant_id=self._tenant_id,
            before=before,
            after=after,
        )

    def _check_refs(
        self, category_id: uuid.UUID | None, area_id: uuid.UUID | None, current: Machine | None = None
    ) -> None:
        """References must exist; newly chosen ones must also be active (an unchanged inactive one is kept)."""
        if category_id:
            cat = self._s.get(MachineCategory, category_id)
            if cat is None:
                raise NotFound("Machine category not found")
            if not cat.is_active and (current is None or current.category_id != category_id):
                raise BusinessRuleViolation("Machine category is deactivated", code="CATEGORY_INACTIVE")
        if area_id:
            area = self._s.get(OperatingArea, area_id)
            if area is None:
                raise NotFound("Operating area not found")
            if not area.is_active and (current is None or current.operating_area_id != area_id):
                raise BusinessRuleViolation("Operating area is deactivated", code="AREA_INACTIVE")

    def machine(self, machine_id: uuid.UUID) -> Machine:
        machine = self._s.execute(select(Machine).where(Machine.id == machine_id)).scalar_one_or_none()
        if machine is None:  # other tenants' machines are invisible under RLS
            raise NotFound("Machine not found")
        return machine

    # --- machines -----------------------------------------------------------------------------------
    def create(self, body: MachineCreateIn) -> MachineDto:
        self._check_refs(body.category_id, body.operating_area_id)
        machine = Machine(id=uuid.uuid4(), tenant_id=self._tenant_id, status=MachineStatus.ACTIVE, **body.model_dump())
        self._insert(machine, "DUPLICATE_ASSET_CODE", "Asset code already used in this tenant")
        dto = MachineDto.model_validate(machine)
        self._record("fleet.machine.created", "machine", machine.id, None, dto.model_dump(mode="json"))
        return dto

    def update(self, machine_id: uuid.UUID, body: MachineUpdateIn) -> MachineDto:
        machine = self.machine(machine_id)
        if machine.version != body.version:
            raise Conflict("Machine was modified by someone else; reload and retry", code="STALE_VERSION")
        if machine.status is MachineStatus.DISPOSED:
            raise BusinessRuleViolation(
                "Disposed machines are read-only; reactivate the machine first", code="MACHINE_DISPOSED"
            )
        self._check_refs(body.category_id, body.operating_area_id, machine)
        before = MachineDto.model_validate(machine).model_dump(mode="json")
        if body.status is MachineStatus.DISPOSED:  # retiring via edit: same integrity rules as /deactivate
            lifecycle = FleetLifecycleService(self._s, self._ctx)
            lifecycle.guard_machine_retirement(machine)
            lifecycle.end_machine_assignments(machine, "Machine disposed")
            machine.deactivated_at, machine.deactivated_by = utcnow(), self._ctx.user_id
            machine.deactivation_reason = "Status set to DISPOSED"
        for key, value in body.model_dump(exclude={"version"}).items():
            setattr(machine, key, value)
        try:
            self._s.flush()
        except StaleDataError as exc:
            raise Conflict("Machine was modified concurrently", code="STALE_VERSION") from exc
        dto = MachineDto.model_validate(machine)
        self._record("fleet.machine.updated", "machine", machine.id, before, dto.model_dump(mode="json"))
        return dto

    def list_query(
        self,
        q: str | None,
        status: MachineStatus | None = None,
        category_id: uuid.UUID | None = None,
        include_inactive: bool = False,
    ) -> Select[Machine]:
        """Retired (DISPOSED) machines are hidden unless asked for explicitly."""
        stmt = select(Machine).order_by(Machine.asset_code)
        if (match := ilike_any(q, Machine.asset_code, Machine.name, Machine.serial_number)) is not None:
            stmt = stmt.where(match)
        if status:
            stmt = stmt.where(Machine.status == status)
        elif not include_inactive:
            stmt = stmt.where(Machine.status != MachineStatus.DISPOSED)
        if category_id:
            stmt = stmt.where(Machine.category_id == category_id)
        return stmt

    # --- reference data -----------------------------------------------------------------------------
    def create_category(self, body: CategoryIn) -> CategoryDto:
        cat = MachineCategory(id=uuid.uuid4(), tenant_id=self._tenant_id, **body.model_dump())
        self._insert(cat, "DUPLICATE_CATEGORY", "Category name already exists")
        return CategoryDto.model_validate(cat)

    def categories(self, q: str | None = None, include_inactive: bool = False) -> list[CategoryDto]:
        rows = self._s.execute(category_query(q, include_inactive)).scalars()
        return [CategoryDto.model_validate(c) for c in rows]

    def create_area(self, body: AreaIn) -> AreaDto:
        area = OperatingArea(id=uuid.uuid4(), tenant_id=self._tenant_id, **body.model_dump())
        self._insert(area, "DUPLICATE_AREA", "Operating area code already exists")
        return AreaDto.model_validate(area)

    def areas(self, q: str | None = None, include_inactive: bool = False) -> list[AreaDto]:
        return [AreaDto.model_validate(a) for a in self._s.execute(area_query(q, include_inactive)).scalars()]

    # --- staff & assignments ------------------------------------------------------------------------
    def create_staff(self, body: StaffIn) -> StaffDto:
        staff = StaffMember(id=uuid.uuid4(), tenant_id=self._tenant_id, **body.model_dump())
        self._insert(staff, "DUPLICATE_STAFF", "Employee code or login already linked to another staff member")
        dto = StaffDto.model_validate(staff)
        self._record("fleet.staff.created", "staff_member", staff.id, None, dto.model_dump(mode="json"))
        return dto

    def staff_query(self, q: str | None, kind: StaffKind | None, include_inactive: bool = False) -> Select[StaffMember]:
        stmt = select(StaffMember).order_by(StaffMember.full_name)
        if (match := ilike_any(q, StaffMember.full_name, StaffMember.employee_code)) is not None:
            stmt = stmt.where(match)
        if not include_inactive:
            stmt = stmt.where(StaffMember.is_active.is_(True))
        if kind:
            stmt = stmt.where(StaffMember.kind == kind)
        return stmt

    def assign(self, machine_id: uuid.UUID, body: AssignIn) -> AssignmentDto:
        """Open a new assignment, closing the current one for the same role at the same instant."""
        self.machine(machine_id)
        staff = self._s.get(StaffMember, body.staff_member_id)
        if staff is None or not staff.is_active:
            raise NotFound("Active staff member not found")
        if staff.kind.value != body.role.value:
            raise BusinessRuleViolation(
                f"{staff.kind.value} cannot be assigned as {body.role.value}", code="ASSIGNMENT_ROLE_MISMATCH"
            )
        current = self._s.execute(
            select(MachineAssignment)
            .where(
                MachineAssignment.machine_id == machine_id,
                MachineAssignment.role == body.role,
                MachineAssignment.effective_to.is_(None),
            )
            .with_for_update()
        ).scalar_one_or_none()
        if current is not None:
            if current.staff_member_id == staff.id:
                return AssignmentDto.model_validate(current)  # idempotent re-assign
            if body.effective_from <= current.effective_from:
                raise BusinessRuleViolation(
                    "New assignment must start after the current one", code="ASSIGNMENT_OVERLAP"
                )
            current.effective_to = body.effective_from
            self._s.flush()
        row = MachineAssignment(
            id=uuid.uuid4(),
            tenant_id=self._tenant_id,
            machine_id=machine_id,
            staff_member_id=staff.id,
            role=body.role,
            effective_from=body.effective_from,
            created_by=self._ctx.user_id,
        )
        self._s.add(row)
        self._s.flush()
        dto = AssignmentDto.model_validate(row)
        self._record("fleet.assignment.created", "machine_assignment", row.id, None, dto.model_dump(mode="json"))
        return dto

    def end_assignment(self, assignment_id: uuid.UUID, effective_to: datetime) -> AssignmentDto:
        row = self._s.execute(
            select(MachineAssignment).where(MachineAssignment.id == assignment_id).with_for_update()
        ).scalar_one_or_none()
        if row is None:
            raise NotFound("Assignment not found")
        if row.effective_to is not None:
            raise Conflict("Assignment already ended", code="ASSIGNMENT_ENDED")
        if effective_to <= row.effective_from:
            raise BusinessRuleViolation("End must be after start", code="ASSIGNMENT_DATES")
        row.effective_to = effective_to
        self._s.flush()
        dto = AssignmentDto.model_validate(row)
        self._record("fleet.assignment.ended", "machine_assignment", row.id, None, dto.model_dump(mode="json"))
        return dto

    def assignments(self, machine_id: uuid.UUID) -> list[AssignmentDto]:
        self.machine(machine_id)
        rows = self._s.execute(
            select(MachineAssignment)
            .where(MachineAssignment.machine_id == machine_id)
            .order_by(MachineAssignment.effective_from.desc())
        ).scalars()
        return [AssignmentDto.model_validate(r) for r in rows]
