"""Device sessions, bootstrap snapshot and cursor-based delta pull.

Delta pull uses the global `sync_revision` sequence. Because a transaction can commit after a later revision is
visible, each pull re-reads a bounded LOOKBACK window below the cursor; clients upsert by (id, sync_revision),
so the overlap is harmless and no committed change is missed.
"""

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from asseta.core.errors import AppError, ErrorDetail, NotFound, PermissionDenied
from asseta.modules.expenses.dto import ExpenseCategoryDto
from asseta.modules.expenses.models import ExpenseCategory
from asseta.modules.finance.cash_service import CashCustodyService
from asseta.modules.finance.dto import CashCustodyBalanceDto
from asseta.modules.fleet.dto import MachineDto, StaffDto
from asseta.modules.fleet.models import Machine, MachineAssignment, StaffMember
from asseta.modules.geospatial.models import JobSite
from asseta.modules.geospatial.sites_service import SiteService
from asseta.modules.identity.principal import RequestContext
from asseta.modules.jobs.dto import ContractDto, CustomerDto, JobDto
from asseta.modules.jobs.models import Customer, Job, JobStatus, RentalContract
from asseta.modules.policy.schemas import PolicyType
from asseta.modules.policy.service import PolicyService
from asseta.modules.sync.dto import (
    BootstrapDto,
    ChangesDto,
    DeviceRegisterIn,
    DeviceSessionDto,
    PolicySnapshotDto,
    SyncData,
)
from asseta.modules.sync.models import DevicePolicySnapshot, DeviceSession, DeviceStatus

LOOKBACK = 500
PAGE = 500
OPEN_JOB_STATES = (JobStatus.APPROVED, JobStatus.IN_PROGRESS)


class DeviceRevoked(AppError):
    status_code = 403
    code = "DEVICE_REVOKED"


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
        if existing is not None and existing.status is DeviceStatus.REVOKED:
            raise DeviceRevoked(
                "This device was revoked; contact your administrator",
                details=[ErrorDetail(field=None, issue="WIPE_LOCAL_DATA")],
            )
        grant = self._now + timedelta(
            hours=self._policies.device_sync(self._tid, at=self._now).policy.offline_grant_hours
        )
        if existing is not None:
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

    def active_device(self, device_id: str | None) -> DeviceSession:
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
        if row.status is DeviceStatus.REVOKED:
            raise DeviceRevoked(
                "This device was revoked; local data must be wiped",
                details=[ErrorDetail(field=None, issue="WIPE_LOCAL_DATA")],
            )
        return row

    def touch(self, device: DeviceSession, clock_offset_s: float | None = None) -> None:
        policy = self._policies.device_sync(self._tid, at=self._now).policy
        device.last_sync_at = self._now
        device.offline_grant_until = self._now + timedelta(hours=policy.offline_grant_hours)
        if clock_offset_s is not None:
            device.last_clock_offset_s = clock_offset_s
        self._s.flush()

    # --- scope: what a supervisor device receives -----------------------------------------------------
    def _staff(self) -> StaffMember | None:
        return self._s.execute(
            select(StaffMember).where(
                StaffMember.keycloak_subject == self._ctx.subject, StaffMember.is_active.is_(True)
            )
        ).scalar_one_or_none()

    def _job_filter(self) -> Any:
        staff = self._staff()
        if staff is None:
            return Job.id.is_(None)  # no linked staff record: nothing assigned
        assigned_machines = select(MachineAssignment.machine_id).where(
            MachineAssignment.staff_member_id == staff.id, MachineAssignment.effective_to.is_(None)
        )
        return or_(Job.supervisor_id == staff.id, Job.machine_id.in_(assigned_machines))

    def _data(self, min_revision: int | None) -> tuple[SyncData, int, bool]:
        watermark = self._watermark()
        jobs_stmt = select(Job).where(self._job_filter())
        if min_revision is None:
            jobs_stmt = jobs_stmt.where(Job.status.in_(OPEN_JOB_STATES))
        else:
            jobs_stmt = jobs_stmt.where(Job.sync_revision > min_revision)
        jobs = list(self._s.execute(jobs_stmt.order_by(Job.sync_revision).limit(PAGE + 1)).scalars())
        has_more = len(jobs) > PAGE
        jobs = jobs[:PAGE]
        scope_jobs = list(
            self._s.execute(select(Job).where(self._job_filter(), Job.status.in_(OPEN_JOB_STATES))).scalars()
        )
        machine_ids = {j.machine_id for j in [*jobs, *scope_jobs]}
        site_ids = {j.job_site_id for j in [*jobs, *scope_jobs] if j.job_site_id}
        contract_ids = {j.contract_id for j in [*jobs, *scope_jobs]}

        def changed(model: Any, ids: set[uuid.UUID]) -> list[Any]:
            if not ids:
                return []
            stmt = select(model).where(model.id.in_(ids))
            if min_revision is not None:
                stmt = stmt.where(model.sync_revision > min_revision)
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
        staff = self._staff()
        categories = select(ExpenseCategory).order_by(ExpenseCategory.code)
        if min_revision is None:
            categories = categories.where(ExpenseCategory.is_active.is_(True))
        else:
            categories = categories.where(ExpenseCategory.sync_revision > min_revision)
        sites_svc = SiteService(self._s, self._tid, self._ctx.audit_actor())
        data = SyncData(
            jobs=[JobDto.model_validate(j) for j in jobs],
            machines=[MachineDto.model_validate(m) for m in changed(Machine, machine_ids)],
            sites=[sites_svc.site_dto(s) for s in changed(JobSite, site_ids)],
            customers=[CustomerDto.model_validate(c) for c in customers],
            contracts=[ContractDto.model_validate(c) for c in contracts],
            staff=[StaffDto.model_validate(staff)]
            if staff is not None and (min_revision is None or staff.sync_revision > min_revision)
            else [],
            expense_categories=[ExpenseCategoryDto.model_validate(c) for c in self._s.execute(categories).scalars()],
            cash_custody=self._custody(staff),
        )
        cursor = max(j.sync_revision for j in jobs) if has_more else watermark
        return data, cursor, has_more

    def _custody(self, staff: StaffMember | None) -> list[CashCustodyBalanceDto]:
        """Server-owned custody balance for a cash-collecting supervisor (always current, not a delta)."""
        if staff is None or "tenant.collection.record" not in self._ctx.permissions:
            return []
        return CashCustodyService(self._s, self._ctx, self._now).balances(staff.id)

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

    # --- endpoints ----------------------------------------------------------------------------------
    def bootstrap(self, device_id: str | None) -> BootstrapDto:
        device = self.active_device(device_id)
        data, cursor, _ = self._data(None)
        self.touch(device)
        return BootstrapDto(
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
