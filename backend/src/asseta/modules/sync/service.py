"""Device sessions, bootstrap snapshot and cursor-based delta pull.

Delta pull uses the global `sync_revision` sequence. Because a transaction can commit after a later revision is
visible, each pull re-reads a bounded LOOKBACK window below the cursor; clients upsert by (id, sync_revision),
so the overlap is harmless and no committed change is missed.
"""

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, or_, select, text
from sqlalchemy.orm import Session

from asseta.core.errors import AppError, ErrorDetail, NotFound, PermissionDenied
from asseta.modules.expenses.dto import ExpenseCategoryDto
from asseta.modules.expenses.models import ExpenseCategory
from asseta.modules.finance.cash_service import CashCustodyService
from asseta.modules.finance.deposit_accounts import SyncDepositAccountDto
from asseta.modules.finance.deposit_models import CompanyDepositAccount
from asseta.modules.finance.dto import CashCustodyBalanceDto
from asseta.modules.fleet.dto import MachineDto, StaffDto
from asseta.modules.fleet.models import Machine, MachineAssignment, StaffMember
from asseta.modules.geospatial.models import JobSite
from asseta.modules.geospatial.sites_service import SiteService
from asseta.modules.identity.principal import RequestContext
from asseta.modules.jobs.dto import ContractDto, CustomerDto
from asseta.modules.jobs.lifecycle import job_dtos
from asseta.modules.jobs.models import Customer, Job, JobStatus, RentalContract
from asseta.modules.jobs.scope import job_filter, own_staff
from asseta.modules.policy.capabilities import disabled_capabilities
from asseta.modules.policy.schemas import PolicyType
from asseta.modules.policy.service import PolicyService
from asseta.modules.sync.dto import (
    BootstrapDto,
    ChangesDto,
    DeviceRegisterIn,
    DeviceSessionDto,
    PolicySnapshotDto,
    SyncData,
    announced_capabilities,
)
from asseta.modules.sync.inbox import OPEN_JOB_STATES, InboxReader
from asseta.modules.sync.models import (
    TENANT_DATA_RESET_REVOKE_REASON,
    DevicePolicySnapshot,
    DeviceSession,
    DeviceStatus,
)

LOOKBACK = 500
PAGE = 500
CLOSED_JOB_STATES = (JobStatus.COMPLETED, JobStatus.CANCELLED)
CLOSED_JOB_WINDOW = timedelta(days=14)  # bootstrap ships recently closed jobs so the device shows history


class DeviceRevoked(AppError):
    status_code = 403
    code = "DEVICE_REVOKED"


def _reset_revoked(row: DeviceSession) -> bool:
    return row.status is DeviceStatus.REVOKED and row.revoke_reason == TENANT_DATA_RESET_REVOKE_REASON


class SyncService:
    def __init__(self, session: Session, ctx: RequestContext, now: datetime):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid, self._now = session, ctx, ctx.tenant_id, now
        self._policies = PolicyService(session)

    # --- device sessions ----------------------------------------------------------------------------
    def register(self, body: DeviceRegisterIn) -> DeviceSession:
        existing = self._s.execute(
            select(DeviceSession)
            .where(DeviceSession.device_id == body.device_id, DeviceSession.user_id == self._ctx.user_id)
            .order_by(DeviceSession.registered_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if existing is not None and existing.status is DeviceStatus.REVOKED and not _reset_revoked(existing):
            raise DeviceRevoked(
                "This device was revoked; contact your administrator",
                details=[ErrorDetail(field=None, issue="WIPE_LOCAL_DATA")],
            )
        grant = self._now + timedelta(
            hours=self._policies.device_sync(self._tid, at=self._now).policy.offline_grant_hours
        )
        if existing is not None and existing.status is DeviceStatus.ACTIVE:
            existing.app_version, existing.platform, existing.offline_grant_until = (
                body.app_version,
                body.platform,
                grant,
            )
            self._s.flush()
            return existing
        session = DeviceSession(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            user_id=self._ctx.user_id,
            device_id=body.device_id,
            platform=body.platform,
            app_version=body.app_version,
            status=DeviceStatus.ACTIVE,
            offline_grant_until=grant,
        )
        self._s.add(session)
        self._s.flush()
        return session

    def active_device(self, device_id: str | None, *, bootstrap: bool = False) -> DeviceSession:
        """The caller's current session for `device_id`. Answers the wipe instruction for a revoked session, and for
        a session registered after a tenant data reset that has not bootstrapped yet unless this is the bootstrap:
        such a phone still holds the erased records (and their cursor), so it must drop them first."""
        if not device_id:
            raise PermissionDenied("X-Device-Id header required for sync", code="DEVICE_NOT_REGISTERED")
        row = self._s.execute(
            select(DeviceSession)
            .where(DeviceSession.device_id == device_id, DeviceSession.user_id == self._ctx.user_id)
            .order_by(DeviceSession.registered_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if row is None:
            raise PermissionDenied("Device not registered for this user", code="DEVICE_NOT_REGISTERED")
        if row.status is DeviceStatus.REVOKED or (
            not bootstrap and row.last_sync_at is None and self._reset_before(row)
        ):
            raise DeviceRevoked(
                "This device was revoked; local data must be wiped",
                details=[ErrorDetail(field=None, issue="WIPE_LOCAL_DATA")],
            )
        return row

    def _reset_before(self, row: DeviceSession) -> bool:
        """True when this device + user had a session revoked by a tenant data reset (it may hold erased data)."""
        return (
            self._s.execute(
                select(DeviceSession.id)
                .where(
                    DeviceSession.device_id == row.device_id,
                    DeviceSession.user_id == row.user_id,
                    DeviceSession.status == DeviceStatus.REVOKED,
                    DeviceSession.revoke_reason == TENANT_DATA_RESET_REVOKE_REASON,
                )
                .limit(1)
            ).first()
            is not None
        )

    def touch(self, device: DeviceSession, clock_offset_s: float | None = None) -> None:
        policy = self._policies.device_sync(self._tid, at=self._now).policy
        device.last_sync_at = self._now
        device.offline_grant_until = self._now + timedelta(hours=policy.offline_grant_hours)
        if clock_offset_s is not None:
            device.last_clock_offset_s = clock_offset_s
        self._s.flush()

    # --- scope: what a supervisor device receives -----------------------------------------------------
    def _data(self, min_revision: int | None) -> tuple[SyncData, int, bool]:
        watermark = self._watermark()
        staff = own_staff(self._s, self._ctx)
        scope = job_filter(staff)
        jobs_stmt = select(Job).where(scope)
        if min_revision is None:  # open jobs plus recently closed ones (history on the device)
            recent = and_(Job.status.in_(CLOSED_JOB_STATES), Job.updated_at >= self._now - CLOSED_JOB_WINDOW)
            # the caller's own field requests still waiting for approval ("Waiting for approval" on the device)
            conds = [Job.status.in_(OPEN_JOB_STATES), recent]
            if staff is not None:
                conds.append(and_(Job.status == JobStatus.PENDING_APPROVAL, Job.requested_by_staff_id == staff.id))
            jobs_stmt = jobs_stmt.where(or_(*conds))
        else:
            jobs_stmt = jobs_stmt.where(Job.sync_revision > min_revision)
        jobs = list(self._s.execute(jobs_stmt.order_by(Job.sync_revision).limit(PAGE + 1)).scalars())
        jobs_more = len(jobs) > PAGE
        jobs = jobs[:PAGE]
        scope_jobs = list(self._s.execute(select(Job).where(scope, Job.status.in_(OPEN_JOB_STATES))).scalars())
        assignments: list[tuple[uuid.UUID, int]] = []
        if staff is not None:
            open_assignments = select(MachineAssignment.machine_id, MachineAssignment.sync_revision).where(
                MachineAssignment.staff_member_id == staff.id, MachineAssignment.effective_to.is_(None)
            )
            assignments = [(m, rev) for m, rev in self._s.execute(open_assignments).all()]
        # A machine newly assigned to the supervisor ships even when the machine row itself did not change.
        fresh_assigned = {m for m, rev in assignments if min_revision is None or rev > min_revision}
        machine_ids = {j.machine_id for j in [*jobs, *scope_jobs]} | {m for m, _ in assignments}
        site_ids = {j.job_site_id for j in [*jobs, *scope_jobs] if j.job_site_id}
        contract_ids = {j.contract_id for j in [*jobs, *scope_jobs]}

        def changed(model: Any, ids: set[uuid.UUID], force: set[uuid.UUID] | None = None) -> list[Any]:
            """Bootstrap ships only active reference data; deltas also carry deactivations (is_active=false) so
            devices drop them from pickers."""
            if not ids:
                return []
            stmt = select(model).where(model.id.in_(ids))
            if min_revision is not None:
                stmt = stmt.where(or_(model.sync_revision > min_revision, model.id.in_(force or set())))
            elif hasattr(model, "is_active"):
                stmt = stmt.where(model.is_active.is_(True))
            return list(self._s.execute(stmt).scalars())

        contracts = changed(RentalContract, contract_ids)
        customers = changed(
            Customer,
            {
                c.customer_id
                for c in self._s.execute(select(RentalContract).where(RentalContract.id.in_(contract_ids))).scalars()
            }
            if contract_ids
            else set(),
        )
        categories = select(ExpenseCategory).order_by(ExpenseCategory.code)
        if min_revision is None:
            categories = categories.where(ExpenseCategory.is_active.is_(True))
        else:
            categories = categories.where(ExpenseCategory.sync_revision > min_revision)
        sites_svc = SiteService(self._s, self._tid, self._ctx.audit_actor())
        inbox = InboxReader(self._s, self._ctx, self._now, staff, PAGE).read(min_revision)
        data = SyncData(
            jobs=job_dtos(self._s, jobs),
            machines=[MachineDto.model_validate(m) for m in changed(Machine, machine_ids, fresh_assigned)],
            sites=[sites_svc.site_dto(s) for s in changed(JobSite, site_ids)],
            customers=[CustomerDto.model_validate(c) for c in customers],
            contracts=[ContractDto.model_validate(c) for c in contracts],
            staff=[StaffDto.model_validate(staff)]
            if staff is not None and (min_revision is None or staff.sync_revision > min_revision)
            else [],
            expense_categories=[ExpenseCategoryDto.model_validate(c) for c in self._s.execute(categories).scalars()],
            cash_custody=self._custody(staff),
            deposit_accounts=self._deposit_accounts(min_revision),
            my_meter_captures=inbox.meter_captures.items,
            my_meter_resets=inbox.meter_resets.items,
            my_job_activities=inbox.job_activities.items,
            my_acknowledgements=inbox.acknowledgements.items,
            my_expenses=inbox.expenses.items,
            my_fuel_events=inbox.fuel_events.items,
            my_cash_collections=inbox.cash_collections.items,
            my_cash_handovers=inbox.cash_handovers.items,
        )
        # Every stream is ordered by revision: a truncated stream holds back the cursor to its last delivered row;
        # complete streams were delivered up to the watermark (re-delivery above the cursor is a harmless upsert).
        truncated = [s.last_revision for s in inbox.streams() if s.has_more]
        if jobs_more:
            truncated.append(max(j.sync_revision for j in jobs))
        cursor = min(truncated) if truncated else watermark
        return data, cursor, bool(truncated)

    def _custody(self, staff: StaffMember | None) -> list[CashCustodyBalanceDto]:
        """Server-owned custody balance for a cash-collecting supervisor (always current, not a delta)."""
        if staff is None or "tenant.collection.record" not in self._ctx.permissions:
            return []
        return CashCustodyService(self._s, self._ctx, self._now).balances(staff.id)

    def _deposit_accounts(self, min_revision: int | None) -> list[SyncDepositAccountDto]:
        """The remittance account picker for cash recorders (bootstrap: active; deltas: every change)."""
        if "tenant.collection.record" not in self._ctx.permissions:
            return []
        stmt = select(CompanyDepositAccount).order_by(CompanyDepositAccount.name, CompanyDepositAccount.id)
        if min_revision is None:
            stmt = stmt.where(CompanyDepositAccount.is_active.is_(True))
        else:
            stmt = stmt.where(CompanyDepositAccount.sync_revision > min_revision)
        return [SyncDepositAccountDto.model_validate(a) for a in self._s.execute(stmt).scalars()]

    def _watermark(self) -> int:
        """Highest revision handed out so far (read *before* querying; LOOKBACK covers late commits)."""
        return int(self._s.execute(text("SELECT last_value FROM sync_revision_seq")).scalar_one())

    # --- policy snapshots -----------------------------------------------------------------------------
    def snapshots(self, device: DeviceSession, machine_ids: set[uuid.UUID]) -> list[PolicySnapshotDto]:
        validity = timedelta(hours=self._policies.device_sync(self._tid, at=self._now).policy.snapshot_validity_hours)
        out: list[PolicySnapshotDto] = []
        targets: list[tuple[PolicyType, str, uuid.UUID | None]] = [
            (PolicyType.EXPENSE_CAPTURE, "tenant", None),
            (PolicyType.METER_CAPTURE, "tenant", None),
            *[(PolicyType.METER_CAPTURE, f"machine:{m}", m) for m in machine_ids],
        ]
        for ptype, scope_key, machine_id in targets:
            eff = self._policies.resolve(ptype, self._tid, machine_id=machine_id, at=self._now)
            values = eff.policy.model_dump(mode="json")
            snap = PolicySnapshotDto(
                policy_type=ptype.value,
                scope_key=scope_key,
                version_ids=list(eff.version_ids),
                version_stamp=eff.version_stamp,
                values=values,
                valid_until=self._now + validity,
            )
            self._s.add(
                DevicePolicySnapshot(
                    id=uuid.uuid4(),
                    tenant_id=self._tid,
                    device_session_id=device.id,
                    policy_type=snap.policy_type,
                    scope_key=scope_key,
                    version_ids=[str(v) for v in snap.version_ids],
                    version_stamp=snap.version_stamp,
                    values=values,
                    issued_at=self._now,
                    valid_until=snap.valid_until,
                )
            )
            out.append(snap)
        self._s.flush()
        return out

    def capabilities(self) -> list[str]:
        """Protocol capabilities, less those of tenant capabilities the tenant switched off."""
        return announced_capabilities(disabled_capabilities(self._s, self._tid, self._now))

    # --- endpoints ----------------------------------------------------------------------------------
    def bootstrap(self, device_id: str | None) -> BootstrapDto:
        device = self.active_device(device_id, bootstrap=True)
        data, cursor, _ = self._data(None)
        self.touch(device)
        return BootstrapDto(
            capabilities=self.capabilities(),
            server_time=self._now,
            cursor=cursor,
            device_session=DeviceSessionDto.model_validate(device),
            data=data,
            policy_snapshots=self.snapshots(device, {m.id for m in data.machines}),
        )

    def changes(self, device_id: str | None, cursor: int) -> ChangesDto:
        device = self.active_device(device_id)
        data, new_cursor, has_more = self._data(max(cursor - LOOKBACK, 0))
        self.touch(device)
        machine_ids = {m.id for m in data.machines} | {j.machine_id for j in data.jobs}
        return ChangesDto(
            capabilities=self.capabilities(),
            server_time=self._now,
            cursor=max(new_cursor, cursor),
            has_more=has_more,
            data=data,
            policy_snapshots=self.snapshots(device, machine_ids),
        )

    def revoke(self, device_session_id: uuid.UUID, reason: str) -> DeviceSession:
        row = self._s.get(DeviceSession, device_session_id)
        if row is None:
            raise NotFound("Device session not found")
        row.status, row.revoked_at, row.revoked_by, row.revoke_reason = (
            DeviceStatus.REVOKED,
            self._now,
            self._ctx.user_id,
            reason,
        )
        self._s.flush()
        return row
