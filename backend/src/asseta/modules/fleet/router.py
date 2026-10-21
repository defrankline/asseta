"""Tenant fleet registry endpoints (thin: permission -> service -> DTO)."""

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from asseta.core.clock import get_now
from asseta.core.db import get_session
from asseta.core.errors import ERROR_RESPONSES
from asseta.core.idempotency import IdempotencyGuard, request_hash
from asseta.core.lifecycle import IncludeInactive, LifecycleChangeIn
from asseta.core.paging import Page, PageParams, page_params, paginate
from asseta.modules.fleet.dto import (
    AreaDto,
    AreaIn,
    AreaUpdateIn,
    AssignIn,
    AssignmentDto,
    CategoryDto,
    CategoryIn,
    CategoryUpdateIn,
    EndAssignmentIn,
    MachineCreateIn,
    MachineDto,
    MachineUpdateIn,
    StaffDto,
    StaffIn,
    StaffUpdateIn,
)
from asseta.modules.fleet.lifecycle import FleetLifecycleService
from asseta.modules.fleet.models import MachineStatus, StaffKind
from asseta.modules.fleet.service import MachineService
from asseta.modules.identity.catalog import CATALOG, MenuDef
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.dependencies import requires
from asseta.modules.identity.principal import RequestContext

MACHINE_READ = requires("tenant.machine.read", S.TENANT, "View machines, categories, areas")
MACHINE_WRITE = requires("tenant.machine.write", S.TENANT, "Register and edit machines, categories, areas")
STAFF_READ = requires("tenant.staff.read", S.TENANT, "View supervisors/operators and assignments")
STAFF_WRITE = requires("tenant.staff.write", S.TENANT, "Manage supervisors/operators and machine assignments")
for menu in (
    MenuDef("tenant.machines", S.TENANT, "Machines", "/tenant/machines", 20, "tenant.machine.read"),
    MenuDef("tenant.staff", S.TENANT, "Staff", "/tenant/staff", 30, "tenant.staff.read"),
):
    CATALOG.register_menu(menu)

router = APIRouter(prefix="/api/v1/tenant", tags=["fleet"], responses=ERROR_RESPONSES)
DbSession = Annotated[Session, Depends(get_session)]
Read = Annotated[RequestContext, Depends(MACHINE_READ)]
Write = Annotated[RequestContext, Depends(MACHINE_WRITE)]
Search = Annotated[str | None, Query(max_length=100)]
Now = Annotated[datetime, Depends(get_now)]
StaffRead = Annotated[RequestContext, Depends(STAFF_READ)]
StaffWrite = Annotated[RequestContext, Depends(STAFF_WRITE)]


@router.post("/machines", response_model=MachineDto, status_code=201, operation_id="createMachine")
def create_machine(
    body: MachineCreateIn, session: DbSession, ctx: Write, idempotency_key: Annotated[str | None, Header()] = None
) -> MachineDto:
    guard = IdempotencyGuard(session, str(ctx.tenant_id), "createMachine", idempotency_key, request_hash(body))
    if (replay := guard.begin()) is not None:
        return MachineDto.model_validate(replay)
    dto = MachineService(session, ctx).create(body)
    guard.complete(dto, 201)
    return dto


@router.get("/machines", response_model=Page[MachineDto], operation_id="listMachines")
def list_machines(
    session: DbSession,
    ctx: Read,
    paging: Annotated[PageParams, Depends(page_params)],
    status: MachineStatus | None = None,
    category_id: uuid.UUID | None = None,
    include_inactive: IncludeInactive = False,
) -> Page[MachineDto]:
    stmt = MachineService(session, ctx).list_query(paging.q, status, category_id, include_inactive)
    rows, total = paginate(session, stmt, paging)
    return Page(
        items=[MachineDto.model_validate(m) for m in rows], total=total, page=paging.page, page_size=paging.page_size
    )


@router.get("/machines/{machine_id}", response_model=MachineDto, operation_id="getMachine")
def get_machine(machine_id: uuid.UUID, session: DbSession, ctx: Read) -> MachineDto:
    return MachineDto.model_validate(MachineService(session, ctx).machine(machine_id))


@router.put("/machines/{machine_id}", response_model=MachineDto, operation_id="updateMachine")
def update_machine(
    machine_id: uuid.UUID, body: MachineUpdateIn, session: DbSession, now: Now, ctx: Write
) -> MachineDto:
    """Setting status DISPOSED applies the same integrity rules as `/deactivate`."""
    return MachineService(session, ctx).update(machine_id, body, now)


@router.post("/machines/{machine_id}/deactivate", response_model=MachineDto, operation_id="deactivateMachine")
def deactivate_machine(
    machine_id: uuid.UUID, body: LifecycleChangeIn, session: DbSession, now: Now, ctx: Write
) -> MachineDto:
    """Retire (status DISPOSED). Refused while the machine has open jobs, an assigned tracker or an active billing
    enrollment; open staff assignments are ended."""
    return FleetLifecycleService(session, ctx, now).set_machine_active(machine_id, False, body.reason, body.version)


@router.post("/machines/{machine_id}/reactivate", response_model=MachineDto, operation_id="reactivateMachine")
def reactivate_machine(
    machine_id: uuid.UUID, body: LifecycleChangeIn, session: DbSession, now: Now, ctx: Write
) -> MachineDto:
    """Reinstate a retired machine (status ACTIVE)."""
    return FleetLifecycleService(session, ctx, now).set_machine_active(machine_id, True, body.reason, body.version)


@router.get("/machine-categories", response_model=list[CategoryDto], operation_id="listMachineCategories")
def categories(
    session: DbSession, ctx: Read, q: Search = None, include_inactive: IncludeInactive = False
) -> list[CategoryDto]:
    return MachineService(session, ctx).categories(q, include_inactive)


@router.post("/machine-categories", response_model=CategoryDto, status_code=201, operation_id="createMachineCategory")
def create_category(body: CategoryIn, session: DbSession, ctx: Write) -> CategoryDto:
    return MachineService(session, ctx).create_category(body)


@router.get("/machine-categories/{category_id}", response_model=CategoryDto, operation_id="getMachineCategory")
def get_category(category_id: uuid.UUID, session: DbSession, now: Now, ctx: Read) -> CategoryDto:
    return FleetLifecycleService(session, ctx, now).category(category_id)


@router.put("/machine-categories/{category_id}", response_model=CategoryDto, operation_id="updateMachineCategory")
def update_category(
    category_id: uuid.UUID, body: CategoryUpdateIn, session: DbSession, now: Now, ctx: Write
) -> CategoryDto:
    return FleetLifecycleService(session, ctx, now).update_category(category_id, body)


@router.post(
    "/machine-categories/{category_id}/deactivate", response_model=CategoryDto, operation_id="deactivateMachineCategory"
)
def deactivate_category(
    category_id: uuid.UUID, body: LifecycleChangeIn, session: DbSession, now: Now, ctx: Write
) -> CategoryDto:
    """Hide from pickers; machines and rate cards already using the category are unaffected."""
    return FleetLifecycleService(session, ctx, now).set_category_active(category_id, False, body.reason, body.version)


@router.post(
    "/machine-categories/{category_id}/reactivate", response_model=CategoryDto, operation_id="reactivateMachineCategory"
)
def reactivate_category(
    category_id: uuid.UUID, body: LifecycleChangeIn, session: DbSession, now: Now, ctx: Write
) -> CategoryDto:
    return FleetLifecycleService(session, ctx, now).set_category_active(category_id, True, body.reason, body.version)


@router.get("/operating-areas", response_model=list[AreaDto], operation_id="listOperatingAreas")
def areas(session: DbSession, ctx: Read, q: Search = None, include_inactive: IncludeInactive = False) -> list[AreaDto]:
    return MachineService(session, ctx).areas(q, include_inactive)


@router.post("/operating-areas", response_model=AreaDto, status_code=201, operation_id="createOperatingArea")
def create_area(body: AreaIn, session: DbSession, ctx: Write) -> AreaDto:
    return MachineService(session, ctx).create_area(body)


@router.get("/operating-areas/{area_id}", response_model=AreaDto, operation_id="getOperatingArea")
def get_area(area_id: uuid.UUID, session: DbSession, now: Now, ctx: Read) -> AreaDto:
    return FleetLifecycleService(session, ctx, now).area(area_id)


@router.put("/operating-areas/{area_id}", response_model=AreaDto, operation_id="updateOperatingArea")
def update_area(area_id: uuid.UUID, body: AreaUpdateIn, session: DbSession, now: Now, ctx: Write) -> AreaDto:
    return FleetLifecycleService(session, ctx, now).update_area(area_id, body)


@router.post("/operating-areas/{area_id}/deactivate", response_model=AreaDto, operation_id="deactivateOperatingArea")
def deactivate_area(area_id: uuid.UUID, body: LifecycleChangeIn, session: DbSession, now: Now, ctx: Write) -> AreaDto:
    return FleetLifecycleService(session, ctx, now).set_area_active(area_id, False, body.reason, body.version)


@router.post("/operating-areas/{area_id}/reactivate", response_model=AreaDto, operation_id="reactivateOperatingArea")
def reactivate_area(area_id: uuid.UUID, body: LifecycleChangeIn, session: DbSession, now: Now, ctx: Write) -> AreaDto:
    return FleetLifecycleService(session, ctx, now).set_area_active(area_id, True, body.reason, body.version)


@router.get("/staff", response_model=Page[StaffDto], operation_id="listStaff")
def list_staff(
    session: DbSession,
    ctx: StaffRead,
    paging: Annotated[PageParams, Depends(page_params)],
    kind: StaffKind | None = None,
    include_inactive: IncludeInactive = False,
) -> Page[StaffDto]:
    stmt = MachineService(session, ctx).staff_query(paging.q, kind, include_inactive)
    rows, total = paginate(session, stmt, paging)
    return Page(
        items=[StaffDto.model_validate(s) for s in rows], total=total, page=paging.page, page_size=paging.page_size
    )


@router.post("/staff", response_model=StaffDto, status_code=201, operation_id="createStaff")
def create_staff(body: StaffIn, session: DbSession, ctx: StaffWrite) -> StaffDto:
    return MachineService(session, ctx).create_staff(body)


@router.get("/staff/{staff_id}", response_model=StaffDto, operation_id="getStaff")
def get_staff(staff_id: uuid.UUID, session: DbSession, now: Now, ctx: StaffRead) -> StaffDto:
    return FleetLifecycleService(session, ctx, now).staff(staff_id)


@router.put("/staff/{staff_id}", response_model=StaffDto, operation_id="updateStaff")
def update_staff(staff_id: uuid.UUID, body: StaffUpdateIn, session: DbSession, now: Now, ctx: StaffWrite) -> StaffDto:
    """Kind cannot change while the person has open machine assignments. Changing `keycloak_subject` moves
    field-app access (sync scope, cash custody) to another login and is audited."""
    return FleetLifecycleService(session, ctx, now).update_staff(staff_id, body)


@router.post("/staff/{staff_id}/deactivate", response_model=StaffDto, operation_id="deactivateStaff")
def deactivate_staff(
    staff_id: uuid.UUID, body: LifecycleChangeIn, session: DbSession, now: Now, ctx: StaffWrite
) -> StaffDto:
    """Refused while supervising an approved/running job or holding company cash; open machine assignments end."""
    return FleetLifecycleService(session, ctx, now).set_staff_active(staff_id, False, body.reason, body.version)


@router.post("/staff/{staff_id}/reactivate", response_model=StaffDto, operation_id="reactivateStaff")
def reactivate_staff(
    staff_id: uuid.UUID, body: LifecycleChangeIn, session: DbSession, now: Now, ctx: StaffWrite
) -> StaffDto:
    return FleetLifecycleService(session, ctx, now).set_staff_active(staff_id, True, body.reason, body.version)


@router.get("/machines/{machine_id}/assignments", response_model=list[AssignmentDto], operation_id="listAssignments")
def assignments(
    machine_id: uuid.UUID, session: DbSession, ctx: Annotated[RequestContext, Depends(STAFF_READ)]
) -> list[AssignmentDto]:
    return MachineService(session, ctx).assignments(machine_id)


@router.post(
    "/machines/{machine_id}/assignments", response_model=AssignmentDto, status_code=201, operation_id="assignStaff"
)
def assign(
    machine_id: uuid.UUID, body: AssignIn, session: DbSession, ctx: Annotated[RequestContext, Depends(STAFF_WRITE)]
) -> AssignmentDto:
    return MachineService(session, ctx).assign(machine_id, body)


@router.post("/assignments/{assignment_id}/end", response_model=AssignmentDto, operation_id="endAssignment")
def end_assignment(
    assignment_id: uuid.UUID,
    body: EndAssignmentIn,
    session: DbSession,
    ctx: Annotated[RequestContext, Depends(STAFF_WRITE)],
) -> AssignmentDto:
    return MachineService(session, ctx).end_assignment(assignment_id, body.effective_to)
