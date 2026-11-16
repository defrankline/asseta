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

from asseta.core.errors import AppError, Conflict, ErrorDetail, NotFound, PermissionDenied
from asseta.modules.accountability.names import fill_names
from asseta.modules.customers.dto import CustomerDto
from asseta.modules.customers.models import Customer
from asseta.modules.expenses.dto import ExpenseCategoryDto
from asseta.modules.expenses.models import ExpenseCategory
from asseta.modules.finance.cash_service import CashCustodyService
from asseta.modules.finance.deposit_accounts import SyncDepositAccountDto
from asseta.modules.finance.deposit_models import CompanyDepositAccount
from asseta.modules.finance.dto import CashCustodyBalanceDto
from asseta.modules.fleet.dto import StaffDto
from asseta.modules.fleet.machine_view import machine_dtos
from asseta.modules.fleet.models import Machine, MachineAssignment, StaffMember
from asseta.modules.fleet.scope import own_staff
from asseta.modules.geospatial.models import JobSite
from asseta.modules.geospatial.sites_service import SiteService
from asseta.modules.hours.credit_invoices import invoice_dtos, invoice_query, local_today
from asseta.modules.hours.models import CreditInvoice
from asseta.modules.hours.service import HoursService
from asseta.modules.identity.principal import RequestContext
from asseta.modules.machine_reports.service import MachineReportService
from asseta.modules.meter.engine_models import EngineHourReason, EngineHourReasonKind
from asseta.modules.pettycash.dto import (
    PettyCashHolderChangeDto,
)
from asseta.modules.pettycash.models import (
    INBOUND,
    AdvanceStatus,
    HolderChangeStatus,
    MovementStatus,
    PettyCashAdvance,
    PettyCashFund,
    PettyCashHolderChange,
    PettyCashMovement,
)
from asseta.modules.pettycash.service import PettyCashService
from asseta.modules.policy.capabilities import (
    CUSTOMER_HOURS,
    DEPOSIT_ACCOUNTS,
    ENGINE_HOURS,
    PETTY_CASH,
    capability_on,
    disabled_capabilities,
)
from asseta.modules.policy.schemas import PolicyType
from asseta.modules.policy.service import PolicyService
from asseta.modules.sync.dto import (
    BootstrapDto,
    ChangesDto,
    DeviceRegisterIn,
    DeviceSessionDto,
    PolicySnapshotDto,
    SyncData,
    SyncUnbillableReasonDto,
    announced_capabilities,
)
from asseta.modules.sync.inbox import InboxReader
from asseta.modules.sync.models import (
    TENANT_DATA_RESET_REVOKE_REASON,
    DevicePolicySnapshot,
    DeviceSession,
    DeviceStatus,
)
from asseta.modules.tenancy.models import TenantSettings

LOOKBACK = 500
PAGE = 500


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
            existing.device_model = body.device_model or existing.device_model
            self._s.flush()
            return existing
        session = DeviceSession(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            user_id=self._ctx.user_id,
            device_id=body.device_id,
            platform=body.platform,
            app_version=body.app_version,
            device_model=body.device_model,
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
        assignments: list[tuple[uuid.UUID, int]] = []
        if staff is not None:
            open_assignments = select(MachineAssignment.machine_id, MachineAssignment.sync_revision).where(
                MachineAssignment.staff_member_id == staff.id, MachineAssignment.effective_to.is_(None)
            )
            assignments = [(m, rev) for m, rev in self._s.execute(open_assignments).all()]
        # A machine newly assigned to the supervisor ships even when the machine row itself did not change.
        fresh_assigned = {m for m, rev in assignments if min_revision is None or rev > min_revision}
        machine_ids = {m for m, _ in assignments}

        def changed(model: Any, ids: set[uuid.UUID] | None, force: set[uuid.UUID] | None = None) -> list[Any]:
            """Bootstrap ships only active reference data; deltas also carry deactivations (is_active=false) so
            devices drop them from pickers. `ids` None: every row of the table (company reference data)."""
            if ids is not None and not ids:
                return []
            stmt = select(model) if ids is None else select(model).where(model.id.in_(ids))
            if min_revision is not None:
                stmt = stmt.where(or_(model.sync_revision > min_revision, model.id.in_(force or set())))
            elif hasattr(model, "is_active"):
                stmt = stmt.where(model.is_active.is_(True))
            return list(self._s.execute(stmt.order_by(model.sync_revision).limit(PAGE + 1)).scalars())

        customers = changed(Customer, None) if "tenant.customer.read" in self._ctx.permissions else []
        sites = changed(JobSite, None)
        categories = select(ExpenseCategory).order_by(ExpenseCategory.code)
        if min_revision is None:
            categories = categories.where(ExpenseCategory.is_active.is_(True))
        else:
            categories = categories.where(ExpenseCategory.sync_revision > min_revision)
        sites_svc = SiteService(self._s, self._tid, self._ctx.audit_actor())
        inbox = InboxReader(self._s, self._ctx, self._now, staff, PAGE).read(min_revision)
        data = SyncData(
            machines=machine_dtos(self._s, changed(Machine, machine_ids, fresh_assigned), self._now),
            sites=[sites_svc.site_dto(s) for s in sites[:PAGE]],
            customers=[CustomerDto.model_validate(c) for c in customers[:PAGE]],
            staff=[StaffDto.model_validate(staff)]
            if staff is not None and (min_revision is None or staff.sync_revision > min_revision)
            else [],
            expense_categories=[ExpenseCategoryDto.model_validate(c) for c in self._s.execute(categories).scalars()],
            cash_custody=self._custody(staff),
            deposit_accounts=self._deposit_accounts(min_revision),
            unbillable_reasons=self._unbillable_reasons(min_revision),
            my_meter_captures=inbox.meter_captures.items,
            my_meter_resets=inbox.meter_resets.items,
            my_expenses=inbox.expenses.items,
            my_fuel_events=inbox.fuel_events.items,
            my_cash_collections=inbox.cash_collections.items,
            my_cash_handovers=inbox.cash_handovers.items,
            **self._petty_cash(staff),
            **self._hours_prices(machine_ids),
            **self._machine_reports(),
            **self._credit_invoices(),
        )
        # Every stream is ordered by revision: a truncated stream holds back the cursor to its last delivered row;
        # complete streams were delivered up to the watermark (re-delivery above the cursor is a harmless upsert).
        truncated = [s.last_revision for s in inbox.streams() if s.has_more]
        for rows in (customers, sites):
            if len(rows) > PAGE:
                truncated.append(rows[PAGE - 1].sync_revision)
        cursor = min(truncated) if truncated else watermark
        return data, cursor, bool(truncated)

    def _custody(self, staff: StaffMember | None) -> list[CashCustodyBalanceDto]:
        """Server-owned custody balance for a cash-collecting supervisor (always current, not a delta)."""
        if staff is None or "tenant.collection.record" not in self._ctx.permissions:
            return []
        return CashCustodyService(self._s, self._ctx, self._now).balances(staff.id)

    def _hours_prices(self, machine_ids: set[uuid.UUID]) -> dict[str, Any]:
        """Prices for selling customer hours offline (full snapshot every pull)."""
        if "tenant.hours.purchase" not in self._ctx.permissions or not capability_on(
            self._s, self._tid, CUSTOMER_HOURS, self._now
        ):
            return {}
        svc = HoursService(self._s, self._ctx, self._now)
        return {"hours_prices": svc.current_prices(machine_ids), "customer_discounts": svc.current_discounts()}

    def _machine_reports(self) -> dict[str, Any]:
        """ADR-008 §2: what a phone needs to make machine reports offline (full snapshots every pull)."""
        if "tenant.machine_report.submit" not in self._ctx.permissions:
            return {}
        return MachineReportService(self._s, self._ctx, self._now).sync_snapshot()

    def _credit_invoices(self) -> dict[str, Any]:
        """ADR-008 §1: open credit invoices, so a payment can be recorded offline (full snapshot every pull)."""
        if "tenant.hours.invoice_payment" not in self._ctx.permissions or not capability_on(
            self._s, self._tid, CUSTOMER_HOURS, self._now
        ):
            return {}
        today = local_today(self._s, self._tid, self._now)
        stmt = invoice_query(today, open_only=True).order_by(None)
        invoices = list(
            self._s.execute(stmt.order_by(CreditInvoice.due_date, CreditInvoice.invoice_number).limit(PAGE)).scalars()
        )
        dtos = invoice_dtos(self._s, self._tid, self._now, invoices, with_payments=False)
        fill_names(self._s, dtos)
        return {"open_credit_invoices": dtos}

    def _petty_on(self) -> bool:
        return "tenant.pettycash.read" in self._ctx.permissions and capability_on(
            self._s, self._tid, PETTY_CASH, self._now
        )

    def _petty_cash(self, staff: StaffMember | None) -> dict[str, Any]:
        """The caller's petty cash (DEC-033): server-owned full snapshots, never deltas."""
        if staff is None or not self._petty_on():
            return {}
        svc = PettyCashService(self._s, self._ctx, self._now)
        funds = list(
            self._s.execute(
                select(PettyCashFund)
                .where(PettyCashFund.holder_staff_id == staff.id, PettyCashFund.is_active.is_(True))
                .order_by(PettyCashFund.code)
            ).scalars()
        )
        fund_ids = [f.id for f in funds]
        awaiting = self._s.execute(
            select(PettyCashMovement)
            .where(
                PettyCashMovement.fund_id.in_(fund_ids),
                PettyCashMovement.kind.in_(INBOUND),
                PettyCashMovement.status == MovementStatus.ISSUED,
            )
            .order_by(PettyCashMovement.issued_at)
        ).scalars()
        changes = self._s.execute(
            select(PettyCashHolderChange)
            .where(
                PettyCashHolderChange.to_staff_id == staff.id,
                PettyCashHolderChange.status == HolderChangeStatus.PENDING,
            )
            .order_by(PettyCashHolderChange.requested_at)
        ).scalars()
        advances = self._s.execute(
            select(PettyCashAdvance)
            .where(
                PettyCashAdvance.status == AdvanceStatus.OUTSTANDING,
                or_(PettyCashAdvance.recipient_staff_id == staff.id, PettyCashAdvance.fund_id.in_(fund_ids)),
            )
            .order_by(PettyCashAdvance.issued_at)
        ).scalars()
        return {
            "petty_cash_funds": [svc.fund_dto(f) for f in funds],
            "petty_cash_awaiting": [svc.movement_dto(m) for m in awaiting],
            "petty_cash_holder_changes": [PettyCashHolderChangeDto.model_validate(c) for c in changes],
            "petty_cash_advances": [svc.advance_dto(a) for a in advances],
            "petty_cash_witnesses": svc.witnesses()
            if funds and "tenant.pettycash.count" in self._ctx.permissions
            else [],
        }

    def _deposit_accounts(self, min_revision: int | None) -> list[SyncDepositAccountDto]:
        """The remittance account picker for cash recorders (bootstrap: active; deltas: every change)."""
        if "tenant.collection.record" not in self._ctx.permissions:
            return []
        if not capability_on(self._s, self._tid, DEPOSIT_ACCOUNTS, self._now):
            return []
        stmt = select(CompanyDepositAccount).order_by(CompanyDepositAccount.name, CompanyDepositAccount.id)
        if min_revision is None:
            stmt = stmt.where(CompanyDepositAccount.is_active.is_(True))
        else:
            stmt = stmt.where(CompanyDepositAccount.sync_revision > min_revision)
        return [SyncDepositAccountDto.model_validate(a) for a in self._s.execute(stmt).scalars()]

    def _engine_hours_on(self) -> bool:
        return capability_on(self._s, self._tid, ENGINE_HOURS, self._now)

    def _unbillable_reasons(self, min_revision: int | None) -> list[SyncUnbillableReasonDto]:
        if "tenant.meter.capture" not in self._ctx.permissions or not self._engine_hours_on():
            return []
        stmt = (
            select(EngineHourReason)
            .where(EngineHourReason.kind == EngineHourReasonKind.UNBILLABLE_REASON)
            .order_by(EngineHourReason.code, EngineHourReason.id)
        )
        if min_revision is None:
            stmt = stmt.where(EngineHourReason.is_active.is_(True))
        else:
            stmt = stmt.where(EngineHourReason.sync_revision > min_revision)
        return [SyncUnbillableReasonDto.model_validate(r) for r in self._s.execute(stmt).scalars()]

    def _timezone(self) -> str:
        settings = self._s.get(TenantSettings, self._tid)
        return settings.timezone if settings else "UTC"

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
        if self._petty_on():
            targets.append((PolicyType.PETTY_CASH, "tenant", None))
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
            tenant_timezone=self._timezone(),
            cursor=cursor,
            device_session=DeviceSessionDto.model_validate(device),
            data=data,
            policy_snapshots=self.snapshots(device, {m.id for m in data.machines}),
        )

    def changes(self, device_id: str | None, cursor: int) -> ChangesDto:
        device = self.active_device(device_id)
        data, new_cursor, has_more = self._data(max(cursor - LOOKBACK, 0))
        self.touch(device)
        machine_ids = {m.id for m in data.machines}
        return ChangesDto(
            capabilities=self.capabilities(),
            server_time=self._now,
            tenant_timezone=self._timezone(),
            cursor=max(new_cursor, cursor),
            has_more=has_more,
            data=data,
            policy_snapshots=self.snapshots(device, machine_ids),
        )

    def revoke(self, device_session_id: uuid.UUID, reason: str) -> DeviceSession:
        row = self._s.get(DeviceSession, device_session_id)
        if row is None:
            raise NotFound("Device session not found")
        if row.status is DeviceStatus.REVOKED:
            raise Conflict("This device is already revoked", code="DEVICE_ALREADY_REVOKED")
        row.status, row.revoked_at, row.revoked_by, row.revoke_reason = (
            DeviceStatus.REVOKED,
            self._now,
            self._ctx.user_id,
            reason,
        )
        self._s.flush()
        return row
