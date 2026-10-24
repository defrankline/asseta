"""Accountability oversight (design D): security events, the controlled review of conflicted/rejected offline
operations, and the dashboard summary assembled from each module's own services (no rule is re-implemented)."""

import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound
from asseta.core.search import ilike_any
from asseta.core.signals import sod_violation
from asseta.modules.accountability.dto import (
    AccountabilitySummaryDto,
    ApprovalsTileDto,
    AttemptsTileDto,
    CashTileDto,
    CountAmountDto,
    CustodianCashDto,
    DiscrepanciesTileDto,
    InvestigationsTileDto,
    PaymentsTileDto,
    SecurityEventDto,
    SyncConflictDto,
    SyncResolutionDto,
    SyncResolutionIn,
)
from asseta.modules.accountability.external_tiles import EXTERNAL_TILES, TileUnavailable
from asseta.modules.accountability.models import (
    SecurityEvent,
    SecurityEventKind,
    SyncOperationResolution,
)
from asseta.modules.expenses.models import ApprovalRequest, ApprovalStatus
from asseta.modules.finance.cash_service import CashCustodyService
from asseta.modules.finance.custody_models import (
    CashDecisionStatus,
    CashFloatAcknowledgement,
    CashRetention,
    CashTransfer,
    CashTransferStatus,
    CashVariance,
    CustodyAdjustment,
    VarianceStatus,
)
from asseta.modules.finance.models import (
    CashHandover,
    CustomerPayment,
    SettlementStatus,
    SupervisorCashCustody,
)
from asseta.modules.identity.models import AppUser
from asseta.modules.identity.principal import RequestContext
from asseta.modules.intelligence.models import AnomalyCase, CaseStatus
from asseta.modules.policy.service import PolicyService
from asseta.modules.sync.models import ClientOperation, DeviceSession, OperationStatus

UNAPPLIED = (OperationStatus.CONFLICT, OperationStatus.REJECTED)
TILES = (
    "customer_hours",
    "hours_awaiting_activation",
    "engine_hours",
    "unexplained_hours",
    "missing_daily_reports",
    "investigations",
    "cash",
    "payments",
    "discrepancies",
    "unauthorized_attempts",
    "outstanding_approvals",
)


def _names(session: Session, ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not ids:
        return {}
    return dict(session.execute(select(AppUser.id, AppUser.display_name).where(AppUser.id.in_(ids))).all())


class SecurityEventService:
    def __init__(self, session: Session):
        self._s = session

    def query(
        self,
        kind: SecurityEventKind | None,
        actor_user_id: uuid.UUID | None,
        occurred_from: datetime | None,
        occurred_to: datetime | None,
        q: str | None,
    ) -> Select[SecurityEvent]:
        stmt = select(SecurityEvent).order_by(SecurityEvent.occurred_at.desc(), SecurityEvent.id)
        if kind:
            stmt = stmt.where(SecurityEvent.kind == kind)
        if actor_user_id:
            stmt = stmt.where(SecurityEvent.actor_user_id == actor_user_id)
        if occurred_from:
            stmt = stmt.where(SecurityEvent.occurred_at >= occurred_from)
        if occurred_to:
            stmt = stmt.where(SecurityEvent.occurred_at < occurred_to)
        cond = ilike_any(
            q, SecurityEvent.permission, SecurityEvent.action, SecurityEvent.entity_type, SecurityEvent.request_path
        )
        return stmt.where(cond) if cond is not None else stmt

    def dtos(self, rows: list[SecurityEvent]) -> list[SecurityEventDto]:
        names = _names(self._s, {r.actor_user_id for r in rows if r.actor_user_id})
        subjects = {r.actor_subject for r in rows if r.actor_subject}
        by_subject = (
            dict(
                self._s.execute(
                    select(AppUser.keycloak_subject, AppUser.display_name).where(AppUser.keycloak_subject.in_(subjects))
                ).all()
            )
            if subjects
            else {}
        )
        out = []
        for r in rows:
            dto = SecurityEventDto.model_validate(r)
            dto.actor_display_name = (names.get(r.actor_user_id) if r.actor_user_id else None) or (
                by_subject.get(r.actor_subject) if r.actor_subject else None
            )
            out.append(dto)
        return out


class SyncConflictService:
    def __init__(self, session: Session, ctx: RequestContext, now: datetime):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid, self._now = session, ctx, ctx.tenant_id, now

    def query(
        self, status: OperationStatus | None, op_type: str | None, resolved: bool | None, q: str | None
    ) -> Select[ClientOperation]:
        stmt = select(ClientOperation).where(ClientOperation.status.in_(UNAPPLIED))
        stmt = stmt.order_by(ClientOperation.received_at.desc(), ClientOperation.id)
        if status is not None:
            if status not in UNAPPLIED:
                raise BusinessRuleViolation("Only CONFLICT or REJECTED operations are reviewed", code="INVALID_FILTER")
            stmt = stmt.where(ClientOperation.status == status)
        if op_type:
            stmt = stmt.where(ClientOperation.op_type == op_type)
        if resolved is not None:
            done = ClientOperation.id.in_(select(SyncOperationResolution.operation_id))
            stmt = stmt.where(done if resolved else ~done)
        cond = ilike_any(q, ClientOperation.op_type)
        return stmt.where(cond) if cond is not None else stmt

    def dtos(self, ops: list[ClientOperation]) -> list[SyncConflictDto]:
        devices = {
            d.id: d
            for d in self._s.execute(
                select(DeviceSession).where(DeviceSession.id.in_({o.device_session_id for o in ops}))
            ).scalars()
        }
        names = _names(self._s, {d.user_id for d in devices.values()})
        resolutions = {
            r.operation_id: r
            for r in self._s.execute(
                select(SyncOperationResolution).where(SyncOperationResolution.operation_id.in_([o.id for o in ops]))
            ).scalars()
        }
        out = []
        for o in ops:
            device = devices[o.device_session_id]
            error = o.result.get("error") or {}
            res = resolutions.get(o.id)
            out.append(
                SyncConflictDto(
                    operation_id=o.id,
                    op_type=o.op_type,
                    status=o.status.value,
                    error_code=error.get("code"),
                    error_message=error.get("message"),
                    server_state=o.result.get("server_state") or {},
                    payload=o.payload,
                    created_at_device=o.created_at_device,
                    received_at=o.received_at,
                    attempts=o.attempts,
                    device_id=device.device_id,
                    device_platform=device.platform,
                    submitted_by=device.user_id,
                    submitted_by_name=names.get(device.user_id),
                    resolution=SyncResolutionDto.model_validate(res) if res else None,
                )
            )
        return out

    def get(self, operation_id: uuid.UUID) -> ClientOperation:
        op = self._s.get(ClientOperation, operation_id)
        if op is None or op.status not in UNAPPLIED:
            raise NotFound("No conflicted or rejected operation with this id", code="SYNC_CONFLICT_NOT_FOUND")
        return op

    def resolve(self, operation_id: uuid.UUID, body: SyncResolutionIn) -> SyncConflictDto:
        op = self.get(operation_id)
        if self._s.execute(
            select(SyncOperationResolution.id).where(SyncOperationResolution.operation_id == op.id)
        ).first():
            raise Conflict("This operation was already resolved", code="SYNC_CONFLICT_ALREADY_RESOLVED")
        device = self._s.get(DeviceSession, op.device_session_id)
        assert device is not None
        if device.user_id == self._ctx.user_id:
            sod_violation(self._tid, self._ctx.user_id, "resolve", "client_operation", op.id)
            raise BusinessRuleViolation(
                "The person who submitted the operation cannot resolve it", code="SEGREGATION_OF_DUTIES"
            )
        row = SyncOperationResolution(
            id=uuid.uuid4(),
            tenant_id=self._tid,
            operation_id=op.id,
            outcome=body.outcome,
            reason=body.reason,
            recaptured_entity_type=body.recaptured_entity_type,
            recaptured_entity_id=body.recaptured_entity_id,
            resolved_by=self._ctx.user_id,
            resolved_at=self._now,
        )
        self._s.add(row)
        self._s.flush()
        AuditService(self._s).record(
            actor=self._ctx.audit_actor(),
            action=f"sync.operation.{body.outcome.value.lower()}",
            entity_type="client_operation",
            entity_id=op.id,
            tenant_id=self._tid,
            before={"status": op.status.value, "error": (op.result.get("error") or {}).get("code")},
            after={
                "outcome": body.outcome.value,
                "recaptured": f"{body.recaptured_entity_type}:{body.recaptured_entity_id}"
                if body.recaptured_entity_id
                else None,
            },
            reason=body.reason,
        )
        return self.dtos([op])[0]


class AccountabilityDashboard:
    def __init__(self, session: Session, ctx: RequestContext, now: datetime):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid, self._now = session, ctx, ctx.tenant_id, now

    def _count_amount(self, stmt: Any) -> list[CountAmountDto]:
        return [
            CountAmountDto(currency=c, count=int(n), amount=a or Decimal(0)) for c, n, a in self._s.execute(stmt).all()
        ]

    def summary(self) -> AccountabilitySummaryDto:
        eff = PolicyService(self._s).oversight(self._tid, at=self._now)
        hidden = sorted(set(eff.policy.hidden_dashboard_tiles) & set(TILES))
        out = AccountabilitySummaryDto(
            as_of=self._now, policy_version=eff.version_stamp, hidden_tiles=hidden, unavailable_tiles=[]
        )
        for tile in TILES:
            if tile in hidden:
                continue
            if tile in EXTERNAL_TILES:
                try:
                    setattr(out, tile, EXTERNAL_TILES[tile](self._s, self._ctx, self._now))
                except TileUnavailable:
                    out.unavailable_tiles.append(tile)
                continue
            setattr(out, tile, getattr(self, f"_{tile}")(eff.policy.security_event_window_days))
        return out

    def _investigations(self, _: int) -> InvestigationsTileDto:
        counts = dict(
            self._s.execute(
                select(AnomalyCase.status, func.count())
                .where(AnomalyCase.status.in_((CaseStatus.OPEN, CaseStatus.IN_REVIEW)))
                .group_by(AnomalyCase.status)
            ).all()
        )
        return InvestigationsTileDto(open=counts.get(CaseStatus.OPEN, 0), in_review=counts.get(CaseStatus.IN_REVIEW, 0))

    def _cash(self, window_days: int) -> CashTileDto:
        custody = CashCustodyService(self._s, self._ctx, self._now)
        rows = []
        for staff in custody.custodians():
            for b in custody.balances(staff.id):
                if b.outstanding or b.in_transit_out or b.claimed_unverified_handovers or b.pending_floats:
                    rows.append(
                        CustodianCashDto(
                            staff_member_id=staff.id,
                            staff_name=staff.full_name,
                            currency=b.currency,
                            outstanding=b.outstanding,
                            in_transit_out=b.in_transit_out,
                            claimed_unverified_handovers=b.claimed_unverified_handovers,
                            pending_floats=b.pending_floats,
                        )
                    )
        rows.sort(key=lambda r: (-r.outstanding, r.staff_name))
        pending_floats = (
            select(SupervisorCashCustody.currency, func.count(), func.sum(SupervisorCashCustody.amount))
            .where(
                SupervisorCashCustody.ack_required.is_(True),
                ~SupervisorCashCustody.id.in_(select(CashFloatAcknowledgement.custody_entry_id)),
            )
            .group_by(SupervisorCashCustody.currency)
        )
        return CashTileDto(
            custodians=rows,
            transfers_awaiting_acknowledgement=self._count_amount(
                select(CashTransfer.currency, func.count(), func.sum(CashTransfer.amount_declared))
                .where(CashTransfer.status == CashTransferStatus.PENDING_ACKNOWLEDGEMENT)
                .group_by(CashTransfer.currency)
            ),
            floats_awaiting_acknowledgement=self._count_amount(pending_floats),
            remittances_awaiting_confirmation=self._count_amount(
                select(CashHandover.currency, func.count(), func.sum(CashHandover.amount))
                .where(CashHandover.status == SettlementStatus.CLAIMED)
                .group_by(CashHandover.currency)
            ),
            partial_remittances_in_window=int(
                self._s.execute(
                    select(func.count()).where(
                        CashHandover.partial_shortfall.is_not(None),
                        CashHandover.recorded_at >= self._now - timedelta(days=window_days),
                    )
                ).scalar_one()
            ),
        )

    def _payments(self, _: int) -> PaymentsTileDto:
        return PaymentsTileDto(
            awaiting_confirmation=self._count_amount(
                select(CustomerPayment.currency, func.count(), func.sum(CustomerPayment.amount))
                .where(CustomerPayment.status == SettlementStatus.CLAIMED)
                .group_by(CustomerPayment.currency)
            )
        )

    def _discrepancies(self, _: int) -> DiscrepanciesTileDto:
        open_states = (VarianceStatus.OPEN, VarianceStatus.WRITE_OFF_PROPOSED)
        variances: dict[str, list[Any]] = defaultdict(lambda: [0, Decimal(0)])
        for currency, amount in self._s.execute(
            select(CashVariance.currency, CashVariance.amount).where(CashVariance.status.in_(open_states))
        ).all():
            variances[currency][0] += 1
            variances[currency][1] += abs(amount)
        return DiscrepanciesTileDto(
            open_variances=[CountAmountDto(currency=c, count=n, amount=a) for c, (n, a) in sorted(variances.items())],
            write_offs_proposed=self._count(
                select(func.count()).where(CashVariance.status == VarianceStatus.WRITE_OFF_PROPOSED)
            ),
            sync_conflicts_unresolved=self._count(
                select(func.count()).where(
                    ClientOperation.status.in_(UNAPPLIED),
                    ~ClientOperation.id.in_(select(SyncOperationResolution.operation_id)),
                )
            ),
        )

    def _unauthorized_attempts(self, window_days: int) -> AttemptsTileDto:
        since = self._now - timedelta(days=window_days)
        counts = dict(
            self._s.execute(
                select(SecurityEvent.kind, func.count())
                .where(SecurityEvent.occurred_at >= since)
                .group_by(SecurityEvent.kind)
            ).all()
        )
        return AttemptsTileDto(
            window_days=window_days,
            permission_denied=counts.get(SecurityEventKind.PERMISSION_DENIED, 0),
            segregation_of_duties=counts.get(SecurityEventKind.SEGREGATION_OF_DUTIES, 0),
        )

    def _outstanding_approvals(self, _: int) -> ApprovalsTileDto:
        counts = {
            "approval_requests": self._count(
                select(func.count()).where(ApprovalRequest.status == ApprovalStatus.PENDING)
            ),
            "cash_retentions": self._count(
                select(func.count()).where(CashRetention.status == CashDecisionStatus.PENDING)
            ),
            "custody_adjustments": self._count(
                select(func.count()).where(CustodyAdjustment.status == CashDecisionStatus.PENDING)
            ),
            "write_offs": self._count(
                select(func.count()).where(CashVariance.status == VarianceStatus.WRITE_OFF_PROPOSED)
            ),
            "payments_to_verify": self._count(
                select(func.count()).where(CustomerPayment.status == SettlementStatus.CLAIMED)
            ),
            "remittances_to_verify": self._count(
                select(func.count()).where(CashHandover.status == SettlementStatus.CLAIMED)
            ),
        }
        return ApprovalsTileDto(**counts, total=sum(counts.values()))

    def _count(self, stmt: Any) -> int:
        return int(self._s.execute(stmt).scalar_one())
