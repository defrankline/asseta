"""Shared cash custody rules: whose custody a recorder may move (tenant policy), the caller's own staff record,
reason-list validation, and opening a cash variance (with an investigation case above the policy threshold)."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.errors import BusinessRuleViolation, NotFound, PermissionDenied
from asseta.core.outbox import OutboxWriter
from asseta.core.signals import sod_violation
from asseta.modules.finance.common import OFFICE_CASH_PERMISSION, resolve_staff
from asseta.modules.finance.custody_models import (
    CashReason,
    CashReasonKind,
    CashVariance,
    VarianceSource,
    VarianceStatus,
)
from asseta.modules.fleet.models import StaffMember
from asseta.modules.identity.principal import RequestContext
from asseta.modules.intelligence.linking import CaseItem, CaseLinker
from asseta.modules.intelligence.models import CaseSourceType, SignalSeverity, SubjectType
from asseta.modules.policy.schemas import CashCustodyPolicy
from asseta.modules.policy.service import EffectivePolicy, PolicyService

TOPIC = "asseta.finance"
RECORDER_PERMISSION = "tenant.collection.record"
VARIANCE_TITLE = "Cash received differs from the amount declared"


def cash_policy(session: Session, tenant_id: uuid.UUID, at: datetime) -> EffectivePolicy[CashCustodyPolicy]:
    return PolicyService(session).cash_custody(tenant_id, at=at)


def own_staff(session: Session, ctx: RequestContext) -> StaffMember | None:
    """The caller's linked staff record, if any (office users often have none)."""
    return session.execute(select(StaffMember).where(StaffMember.keycloak_subject == ctx.subject)).scalar_one_or_none()


def may_record_for_others(ctx: RequestContext, policy: CashCustodyPolicy) -> bool:
    return OFFICE_CASH_PERMISSION in ctx.permissions or (
        policy.recorders_may_record_for_others and RECORDER_PERMISSION in ctx.permissions
    )


def resolve_recorded_custodian(
    session: Session,
    ctx: RequestContext,
    staff_id: uuid.UUID | None,
    policy: CashCustodyPolicy,
    require_active: bool = True,
) -> StaffMember:
    """Whose custody a recorded movement affects. Omitted = the caller's own (needs a linked login). Naming another
    staff member (any active staff, login not required) needs the office cash permission, or the recorder
    permission when the tenant lets recorders record on a custodian's behalf."""
    if staff_id is None:
        return resolve_staff(session, ctx, None, require_active=require_active)
    if may_record_for_others(ctx, policy):
        return resolve_staff(session, ctx, staff_id, require_active=require_active)
    own = resolve_staff(session, ctx, None, require_active=require_active)
    if own.id != staff_id:
        raise PermissionDenied("Only office cash staff may record custody for someone else", code="NOT_CUSTODIAN")
    return own


def refuse_sod(ctx: RequestContext, action: str, entity_type: str, entity_id: uuid.UUID, message: str) -> None:
    assert ctx.tenant_id is not None
    sod_violation(ctx.tenant_id, ctx.user_id, action, entity_type, entity_id)
    raise BusinessRuleViolation(message, code="SEGREGATION_OF_DUTIES")


def check_reason(session: Session, kind: CashReasonKind, reason_id: uuid.UUID | None) -> uuid.UUID | None:
    """A reason from the tenant's own list. When the tenant keeps active reasons of this kind, one is required."""
    if reason_id is None:
        has_list = session.execute(
            select(CashReason.id).where(CashReason.kind == kind, CashReason.is_active.is_(True)).limit(1)
        ).first()
        if has_list is not None:
            raise BusinessRuleViolation(f"Choose a {kind.value.lower()} reason from the list", code="REASON_REQUIRED")
        return None
    reason = session.get(CashReason, reason_id)
    if reason is None:
        raise NotFound("Reason not found", code="REASON_NOT_FOUND")
    if reason.kind is not kind or not reason.is_active:
        raise BusinessRuleViolation(f"Reason is not an active {kind.value.lower()} reason", code="REASON_INVALID")
    return reason.id


def open_variance(
    session: Session,
    ctx: RequestContext,
    now: datetime,
    *,
    source_type: VarianceSource,
    source_id: uuid.UUID,
    accountable_staff_id: uuid.UUID | None,
    counterparty_staff_id: uuid.UUID | None,
    currency: str,
    declared: Decimal,
    received: Decimal,
) -> CashVariance | None:
    """Record declared != received (none when equal). Above the tenant's case threshold the variance also opens or
    joins an investigation case about the accountable custodian — for review, never a verdict."""
    amount = declared - received
    if amount == 0:
        return None
    assert ctx.tenant_id is not None
    tid = ctx.tenant_id
    eff = cash_policy(session, tid, now)
    variance_id = uuid.uuid4()
    case_id = None
    threshold = eff.policy.variance_case_threshold
    subject = accountable_staff_id or counterparty_staff_id
    if threshold is not None and abs(amount) > threshold and subject is not None:
        fraud = PolicyService(session).fraud_controls(tid, at=now)
        linker = CaseLinker(session, tid, now, fraud.policy.case_grouping_window_hours)
        case = linker.link(
            CaseItem(
                CaseSourceType.CASH_VARIANCE,
                variance_id,
                "CASH_VARIANCE",
                VARIANCE_TITLE,
                SignalSeverity.WARNING,
                now,
                {
                    "source_type": source_type.value,
                    "source_id": str(source_id),
                    "currency": currency,
                    "declared_amount": str(declared),
                    "received_amount": str(received),
                    "difference": str(amount),
                    "case_threshold": str(threshold),
                },
                SubjectType.STAFF,
                subject,
                eff.version_stamp,
                staff_member_id=subject,
                involved_staff_ids=tuple(s for s in (accountable_staff_id, counterparty_staff_id) if s),
            )
        )
        case_id = case.id if case else None
    row = CashVariance(
        id=variance_id,
        tenant_id=tid,
        source_type=source_type,
        source_id=source_id,
        staff_member_id=accountable_staff_id,
        counterparty_staff_id=counterparty_staff_id,
        currency=currency,
        declared_amount=declared,
        received_amount=received,
        amount=amount,
        case_id=case_id,
        policy_version=eff.version_stamp,
        opened_at=now,
        opened_by=ctx.user_id,
        status=VarianceStatus.OPEN,
    )
    session.add(row)
    session.flush()
    AuditService(session).record(
        actor=ctx.audit_actor(),
        action="finance.cash_variance.opened",
        entity_type="cash_variance",
        entity_id=row.id,
        tenant_id=tid,
        after={
            "source_type": source_type.value,
            "source_id": str(source_id),
            "declared": str(declared),
            "received": str(received),
            "amount": str(amount),
            "case_id": str(case_id) if case_id else None,
        },
        policy_version=eff.version_stamp[:64],
    )
    OutboxWriter(session).emit(
        topic=TOPIC,
        event_type="CashVarianceOpened",
        key=str(subject or tid),
        payload={
            "variance_id": str(row.id),
            "source_type": source_type.value,
            "staff_member_id": str(accountable_staff_id) if accountable_staff_id else None,
            "amount": str(amount),
            "currency": currency,
        },
        tenant_id=tid,
    )
    return row
