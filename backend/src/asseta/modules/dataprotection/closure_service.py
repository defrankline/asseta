"""Company closure (deletion) requests: an owner asks to close the company and delete all its data. The company turns
read-only at once (the entitlement evaluation keeps it there while a request is active) and the data protection worker
deletes everything after the platform-wide waiting period (`closure_executor.py`). Anyone holding the permission can
cancel before the deletion starts; the platform can run it early only with its own permission and a reason (the owner
asked in writing). Every step is audited (`platform.company_closure.*`, kept after the deletion) and notified."""

import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from asseta.core.audit import AuditActor, AuditService
from asseta.core.db import DbScope, apply_scope
from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound, PermissionDenied
from asseta.core.outbox import OutboxWriter
from asseta.modules.dataprotection.closure_dto import CompanyDeletionRequestDto, CompanyDeletionStatusDto
from asseta.modules.dataprotection.models import ACTIVE_DELETION_STATUSES, CompanyDeletionRequest, DeletionStatus
from asseta.modules.identity.models import AppUser
from asseta.modules.identity.principal import RequestContext
from asseta.modules.policy.service import PolicyService
from asseta.modules.tenancy.models import Tenant, TenantAccessState, TenantStatus

TOPIC = "asseta.dataprotection.closure"
STEP_ORDER = ("snapshot", "subscription", "identity", "objects", "traccar", "database")


def active_closure(session: Session, tenant_id: uuid.UUID) -> CompanyDeletionRequest | None:
    """The company's REQUESTED / IN_PROGRESS closure request (read in any scope that can see the tenant's row)."""
    return session.execute(
        select(CompanyDeletionRequest).where(
            CompanyDeletionRequest.tenant_id == tenant_id,
            CompanyDeletionRequest.status.in_(ACTIVE_DELETION_STATUSES),
        )
    ).scalar_one_or_none()


def closure_access_reason(request: CompanyDeletionRequest) -> str:
    """Why the company is read-only (shown to every user): fits `tenant.access_state_reason` (200)."""
    return f"Company closure requested: all its data will be deleted on {request.scheduled_for.date().isoformat()}"


def _names(session: Session, ids: set[uuid.UUID | None]) -> dict[uuid.UUID, str]:
    wanted = [i for i in ids if i is not None]
    if not wanted:
        return {}
    rows = session.execute(select(AppUser.id, AppUser.display_name).where(AppUser.id.in_(wanted))).all()
    return {row[0]: row[1] for row in rows}


def to_dto(session: Session, row: CompanyDeletionRequest, tenant_name: str | None = None) -> CompanyDeletionRequestDto:
    names = _names(session, {row.requested_by, row.cancelled_by})
    if tenant_name is None:
        tenant_name = session.execute(select(Tenant.display_name).where(Tenant.id == row.tenant_id)).scalar_one()
    return CompanyDeletionRequestDto(
        id=row.id,
        tenant_id=row.tenant_id,
        tenant_name=tenant_name,
        status=row.status,
        reason=row.reason,
        requested_by=row.requested_by,
        requested_by_name=names.get(row.requested_by) if row.requested_by else None,
        requested_at=row.requested_at,
        waiting_days=row.waiting_days,
        scheduled_for=row.scheduled_for,
        policy_version=row.policy_version,
        cancelled_by=row.cancelled_by,
        cancelled_by_name=names.get(row.cancelled_by) if row.cancelled_by else None,
        cancelled_at=row.cancelled_at,
        cancel_reason=row.cancel_reason,
        execute_now_by=row.execute_now_by,
        execute_now_at=row.execute_now_at,
        execute_now_reason=row.execute_now_reason,
        started_at=row.started_at,
        completed_at=row.completed_at,
        attempts=row.attempts,
        last_error=row.last_error,
        steps_done=[s for s in STEP_ORDER if s in (row.steps or {})],
    )


def list_query(status: DeletionStatus | None) -> Select[CompanyDeletionRequest]:
    stmt = select(CompanyDeletionRequest)
    if status is not None:
        stmt = stmt.where(CompanyDeletionRequest.status == status)
    return stmt.order_by(CompanyDeletionRequest.requested_at.desc(), CompanyDeletionRequest.id)


def reevaluate_access(
    session: Session, tenant_id: uuid.UUID, actor: AuditActor, today: date, restore: DbScope = DbScope.TENANT
) -> None:
    """Re-derives the tenant's access from its subscription (which keeps it read-only while a closure is active), in
    the platform scope the entitlement evaluation runs in; then binds `restore` again (the caller's scope)."""
    from asseta.modules.platform_billing.models_commercial import TenantSubscription
    from asseta.modules.platform_billing.subscription_service import SubscriptionService

    apply_scope(session, DbScope.PLATFORM, None, actor.user_id)
    try:
        sub = session.execute(
            select(TenantSubscription)
            .where(TenantSubscription.tenant_id == tenant_id)
            .order_by(TenantSubscription.created_at.desc())
            .limit(1)
            .with_for_update()
        ).scalar_one_or_none()
        if sub is not None:
            SubscriptionService(session, actor).evaluate_entitlement(sub, today)
        else:  # no subscription (never seen in practice): the closure alone decides
            tenant = session.get(Tenant, tenant_id, with_for_update=True)
            assert tenant is not None
            pending = active_closure(session, tenant_id)
            if pending is not None and tenant.access_state is TenantAccessState.FULL:
                tenant.access_state, tenant.access_state_reason = (
                    TenantAccessState.READ_ONLY,
                    closure_access_reason(pending),
                )
            elif pending is None and tenant.access_state is TenantAccessState.READ_ONLY:
                tenant.access_state, tenant.access_state_reason = TenantAccessState.FULL, "Company closure cancelled"
        session.flush()
    finally:
        apply_scope(session, restore, tenant_id if restore is DbScope.TENANT else None, actor.user_id)


class ClosureService:
    def __init__(self, session: Session, now: datetime):
        self._s, self._now = session, now
        self._audit = AuditService(session)
        self._outbox = OutboxWriter(session)

    def waiting_days(self) -> tuple[int, str]:
        effective = PolicyService(self._s).platform_data_protection(at=self._now)
        return effective.policy.company_deletion_waiting_days, effective.version_stamp

    def status(self, tenant_id: uuid.UUID) -> CompanyDeletionStatusDto:
        tenant = self._s.get(Tenant, tenant_id)
        if tenant is None:
            raise NotFound("Tenant not found")
        row = (
            active_closure(self._s, tenant_id)
            or self._s.execute(
                select(CompanyDeletionRequest)
                .where(CompanyDeletionRequest.tenant_id == tenant_id)
                .order_by(CompanyDeletionRequest.requested_at.desc())
                .limit(1)
            ).scalar_one_or_none()
        )
        return CompanyDeletionStatusDto(
            tenant_id=tenant.id,
            company_name=tenant.display_name,
            waiting_days=self.waiting_days()[0],
            request=to_dto(self._s, row, tenant.display_name) if row is not None else None,
        )

    # --- tenant: request and cancel --------------------------------------------------------------------------------
    def request(self, ctx: RequestContext, confirm_name: str, reason: str) -> CompanyDeletionRequest:
        assert ctx.tenant_id is not None
        if ctx.mandate_id is not None:
            raise PermissionDenied(
                "Only the company's own owners can close it, not platform staff under a mandate",
                code="MANDATE_NOT_ALLOWED",
            )
        tenant = self._s.get(Tenant, ctx.tenant_id, with_for_update=True)
        if tenant is None:
            raise NotFound("Tenant not found")
        if tenant.status is TenantStatus.CLOSED:
            raise BusinessRuleViolation("This company is already closed", code="TENANT_CLOSED")
        if confirm_name.strip().casefold() != tenant.display_name.strip().casefold():
            raise BusinessRuleViolation(
                "The name typed does not match the company's name", code="CONFIRMATION_MISMATCH"
            )
        if active_closure(self._s, tenant.id) is not None:
            raise Conflict("A closure request is already in progress", code="DELETION_ALREADY_REQUESTED")
        days, stamp = self.waiting_days()
        row = CompanyDeletionRequest(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            status=DeletionStatus.REQUESTED,
            reason=reason,
            requested_by=ctx.user_id,
            requested_at=self._now,
            waiting_days=days,
            scheduled_for=self._now + timedelta(days=days),
            policy_version=stamp,
            attempts=0,
            steps={},
            version=1,
        )
        try:
            with self._s.begin_nested():
                self._s.add(row)
                self._s.flush()
        except IntegrityError as exc:  # a concurrent request won the race (one active request per company)
            raise Conflict("A closure request is already in progress", code="DELETION_ALREADY_REQUESTED") from exc
        before = tenant.access_state.value
        actor = ctx.audit_actor()
        reevaluate_access(self._s, tenant.id, actor, self._now.date())
        dto = to_dto(self._s, row, tenant.display_name)
        self._audit.record(
            actor=actor,
            action="platform.company_closure.requested",
            entity_type="company_deletion_request",
            entity_id=row.id,
            tenant_id=tenant.id,
            before={"access_state": before},
            after={**dto.model_dump(mode="json"), "access_state": tenant.access_state.value},
            reason=reason,
            policy_version=stamp,
        )
        self._outbox.emit(
            topic=TOPIC,
            event_type="CompanyDeletionRequested",
            key=str(tenant.id),
            payload={
                "request_id": str(row.id),
                "tenant_name": tenant.display_name,
                "scheduled_for": row.scheduled_for.isoformat(),
                "waiting_days": days,
                "requested_by_name": dto.requested_by_name or "An owner",
                "reason": reason,
            },
            tenant_id=tenant.id,
        )
        return row

    def cancel(self, ctx: RequestContext, reason: str) -> CompanyDeletionRequest:
        assert ctx.tenant_id is not None
        tenant = self._s.get(Tenant, ctx.tenant_id, with_for_update=True)
        if tenant is None:
            raise NotFound("Tenant not found")
        row = active_closure(self._s, tenant.id)
        if row is None:
            raise NotFound("There is no closure request to cancel", code="NO_DELETION_REQUEST")
        self._s.refresh(row, with_for_update=True)
        if row.status is not DeletionStatus.REQUESTED:
            raise Conflict(
                "The deletion has already started and can no longer be cancelled", code="DELETION_IN_PROGRESS"
            )
        row.status, row.cancelled_by, row.cancelled_at, row.cancel_reason = (
            DeletionStatus.CANCELLED,
            ctx.user_id,
            self._now,
            reason,
        )
        row.version += 1
        self._s.flush()
        actor = ctx.audit_actor()
        reevaluate_access(self._s, tenant.id, actor, self._now.date())
        dto = to_dto(self._s, row, tenant.display_name)
        self._audit.record(
            actor=actor,
            action="platform.company_closure.cancelled",
            entity_type="company_deletion_request",
            entity_id=row.id,
            tenant_id=tenant.id,
            before={"status": DeletionStatus.REQUESTED.value},
            after={"status": row.status.value, "access_state": tenant.access_state.value},
            reason=reason,
        )
        self._outbox.emit(
            topic=TOPIC,
            event_type="CompanyDeletionCancelled",
            key=str(tenant.id),
            payload={
                "request_id": str(row.id),
                "tenant_name": tenant.display_name,
                "cancelled_by_name": dto.cancelled_by_name or "An owner",
                "reason": reason,
            },
            tenant_id=tenant.id,
        )
        return row

    # --- platform: run it now -------------------------------------------------------------------------------------
    def execute_now(self, request_id: uuid.UUID, ctx: RequestContext, reason: str) -> CompanyDeletionRequest:
        row = self._s.get(CompanyDeletionRequest, request_id, with_for_update=True)
        if row is None:
            raise NotFound("Deletion request not found")
        if row.status not in ACTIVE_DELETION_STATUSES:
            raise Conflict(f"This request is {row.status.value}", code="DELETION_NOT_ACTIVE")
        before = {"scheduled_for": row.scheduled_for.isoformat(), "status": row.status.value}
        row.scheduled_for = min(row.scheduled_for, self._now)
        row.next_attempt_at = None
        row.execute_now_by, row.execute_now_at, row.execute_now_reason = ctx.user_id, self._now, reason
        row.version += 1
        self._s.flush()
        self._audit.record(
            actor=ctx.audit_actor(),
            action="platform.company_closure.execute_now",
            entity_type="company_deletion_request",
            entity_id=row.id,
            tenant_id=row.tenant_id,
            before=before,
            after={"scheduled_for": row.scheduled_for.isoformat(), "status": row.status.value},
            reason=reason,
        )
        return row
