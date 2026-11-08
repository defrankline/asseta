"""Variance investigation (guideline T8, DEC-032): assign to a person holding the variance permission, record the
explanation and evidence, close by a second person, and the append-only history. Used for cash and customer-hour
variances alike; `custody_service` keeps the closing itself and the write-off flow."""

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.errors import BusinessRuleViolation, Conflict
from asseta.core.outbox import OutboxWriter
from asseta.core.search import ilike_any
from asseta.modules.finance.common import resolve_staff
from asseta.modules.finance.custody_dto import (
    CashVarianceDto,
    DecisionIn,
    VarianceAssigneeDto,
    VarianceAssignIn,
    VarianceEventDto,
    VarianceExplanationIn,
)
from asseta.modules.finance.custody_models import (
    CashVariance,
    CashVarianceEvent,
    VarianceEventAction,
    VarianceOutcome,
    VarianceStatus,
)
from asseta.modules.finance.custody_rules import TOPIC, variance_event
from asseta.modules.finance.custody_service import CashCustodyControls
from asseta.modules.identity.models import AppUser, Role, RolePermission, TenantMembership
from asseta.modules.identity.principal import RequestContext

VARIANCE_PERMISSION = "tenant.finance.variance"
# Lower-case key for the outbox/event consumers; the closure decision is notified to whoever proposed it.
CLOSURE_DECIDED = "VarianceClosureDecided"
ASSIGNED = "VarianceAssigned"


class VarianceWorkflow:
    def __init__(self, session: Session, ctx: RequestContext, now: datetime):
        assert ctx.tenant_id is not None
        self._s, self._ctx, self._tid, self._now = session, ctx, ctx.tenant_id, now
        self._controls = CashCustodyControls(session, ctx, now)
        self._audit = AuditService(session)

    def _emit(self, event_type: str, key: uuid.UUID, payload: dict[str, object]) -> None:
        OutboxWriter(self._s).emit(
            topic=TOPIC, event_type=event_type, key=str(key), payload=payload, tenant_id=self._tid
        )

    def _record(
        self, action: str, v: CashVariance, before: dict[str, object], after: dict[str, object], reason: str | None
    ) -> None:
        self._audit.record(
            actor=self._ctx.audit_actor(),
            action=f"finance.cash_variance.{action}",
            entity_type="cash_variance",
            entity_id=v.id,
            tenant_id=self._tid,
            before=before,
            after=after,
            reason=reason,
        )

    # --- picking --------------------------------------------------------------------------------------------
    def assignees(self, q: str | None) -> list[VarianceAssigneeDto]:
        """Everyone in this tenant who holds the variance permission (permission-based, never a fixed role)."""
        stmt = (
            select(AppUser.id, AppUser.display_name, AppUser.email)
            .join(TenantMembership, TenantMembership.user_id == AppUser.id)
            .join(Role, Role.id == TenantMembership.role_id)
            .join(RolePermission, RolePermission.role_id == Role.id)
            .where(
                TenantMembership.tenant_id == self._tid,
                TenantMembership.effective_to.is_(None),
                AppUser.is_active.is_(True),
                RolePermission.permission_code == VARIANCE_PERMISSION,
            )
            .distinct()
            .order_by(AppUser.display_name, AppUser.id)
        )
        if (match := ilike_any(q, AppUser.display_name, AppUser.email)) is not None:
            stmt = stmt.where(match)
        return [VarianceAssigneeDto(user_id=i, display_name=n, email=e) for i, n, e in self._s.execute(stmt).all()]

    def _check_assignee(self, v: CashVariance, assignee: uuid.UUID) -> None:
        if assignee not in {a.user_id for a in self.assignees(None)}:
            raise BusinessRuleViolation(
                "Assign the variance to someone who holds the variance permission", code="ASSIGNEE_NOT_ELIGIBLE"
            )
        for staff_id in (v.staff_member_id, v.counterparty_staff_id):
            if staff_id is None:
                continue
            subject = resolve_staff(self._s, self._ctx, staff_id, require_active=False).keycloak_subject
            if (
                subject
                and self._s.execute(select(AppUser.keycloak_subject).where(AppUser.id == assignee)).scalar_one()
                == subject
            ):
                raise BusinessRuleViolation(
                    "This person is a party to the variance; assign someone else", code="SEGREGATION_OF_DUTIES"
                )

    # --- investigation --------------------------------------------------------------------------------------
    def assign(self, variance_id: uuid.UUID, body: VarianceAssignIn) -> CashVarianceDto:
        v = self._controls.variance(variance_id, lock=True)
        if v.status is VarianceStatus.RESOLVED:
            raise Conflict("Variance is already resolved", code="VARIANCE_NOT_OPEN")
        self._check_assignee(v, body.assignee_user_id)
        before = str(v.assignee_user_id) if v.assignee_user_id else None
        v.assignee_user_id, v.assigned_by, v.assigned_at = body.assignee_user_id, self._ctx.user_id, self._now
        self._s.flush()
        self._record(
            "assigned", v, {"assignee_user_id": before}, {"assignee_user_id": str(body.assignee_user_id)}, None
        )
        variance_event(
            self._s,
            v,
            VarianceEventAction.ASSIGNED,
            self._ctx.user_id,
            self._now,
            None,
            {"assignee_user_id": str(body.assignee_user_id)},
        )
        self._emit(
            ASSIGNED,
            v.id,
            {"variance_id": str(v.id), "user_id": str(body.assignee_user_id), "unit": v.unit.value},
        )
        return CashVarianceDto.model_validate(v)

    def explain(self, variance_id: uuid.UUID, body: VarianceExplanationIn) -> CashVarianceDto:
        v = self._controls.variance(variance_id, lock=True)
        if v.status is VarianceStatus.RESOLVED:
            raise Conflict("Variance is already resolved", code="VARIANCE_NOT_OPEN")
        self._controls._add_evidence(v, body.evidence_attachment_ids, required=False)
        v.explanation, v.explained_by, v.explained_at = body.explanation, self._ctx.user_id, self._now
        self._s.flush()
        self._record("explained", v, {}, {"evidence": len(v.evidence_attachment_ids)}, body.explanation)
        variance_event(
            self._s,
            v,
            VarianceEventAction.EXPLAINED,
            self._ctx.user_id,
            self._now,
            body.explanation,
            {"evidence_attachment_ids": [str(a) for a in v.evidence_attachment_ids]},
        )
        return CashVarianceDto.model_validate(v)

    # --- closure by a second person ---------------------------------------------------------------------------
    def decide_closure(self, variance_id: uuid.UUID, body: DecisionIn) -> CashVarianceDto:
        v = self._controls.variance(variance_id, lock=True)
        if v.status is not VarianceStatus.CLOSURE_PROPOSED:
            raise Conflict("No closure is proposed for this variance", code="CLOSURE_NOT_PROPOSED")
        self._controls._not_party(v, "approve_closure", closing=True)
        proposer = v.proposed_by
        if body.approve:
            outcome: VarianceOutcome = v.proposed_outcome or VarianceOutcome.CORRECTED_ERROR
            variance_event(self._s, v, VarianceEventAction.CLOSURE_APPROVED, self._ctx.user_id, self._now, body.note)
            self._controls._resolve(v, outcome, body.note or v.proposal_note or "", v.reason_id)
        else:
            variance_event(self._s, v, VarianceEventAction.CLOSURE_REJECTED, self._ctx.user_id, self._now, body.note)
            v.status, v.proposed_by, v.proposed_at, v.proposal_note, v.proposed_outcome = (
                VarianceStatus.OPEN,
                None,
                None,
                None,
                None,
            )
            self._s.flush()
            self._record(
                "closure_rejected",
                v,
                {"status": VarianceStatus.CLOSURE_PROPOSED.value},
                {"status": v.status.value},
                body.note,
            )
        if proposer is not None and proposer != self._ctx.user_id:
            self._emit(
                CLOSURE_DECIDED,
                v.id,
                {
                    "variance_id": str(v.id),
                    "user_id": str(proposer),
                    "outcome": "APPROVED" if body.approve else "REJECTED",
                },
            )
        return CashVarianceDto.model_validate(v)

    # --- history ----------------------------------------------------------------------------------------------
    def history(self, variance_id: uuid.UUID) -> list[VarianceEventDto]:
        self._controls.variance(variance_id)
        rows = self._s.execute(
            select(CashVarianceEvent)
            .where(CashVarianceEvent.variance_id == variance_id)
            .order_by(CashVarianceEvent.seq)
        ).scalars()
        return [VarianceEventDto.model_validate(r) for r in rows]
