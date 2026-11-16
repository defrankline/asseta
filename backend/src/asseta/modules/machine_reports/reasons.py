"""The starting machine-report reason list (ADR-008 §2). Every tenant's list is its own data, edited in the app: these
entries are added once, for a new tenant at onboarding and for an existing tenant by the one-off script
backend/scripts/seed_machine_report_reasons.py. An entry already there (same code, any capitals, active or not) is
never added again or changed."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditActor, AuditService
from asseta.modules.meter.engine_models import EngineHourReason, EngineHourReasonKind

DEFAULT_REASONS: tuple[tuple[str, str], ...] = (
    ("TRANSIT", "Transit between sites"),
    ("BREAKDOWN", "Breakdown / repair"),
    ("SERVICING", "Servicing"),
    ("IDLE_ON_SITE", "Idle on site"),
    ("WAITING_CUSTOMER", "Waiting for customer"),
    ("WEATHER", "Weather"),
)


def missing_default_reasons(session: Session) -> list[tuple[str, str]]:
    """Default entries the tenant (the session's RLS scope) does not have yet."""
    have = {
        str(code).casefold()
        for code in session.execute(
            select(EngineHourReason.code).where(EngineHourReason.kind == EngineHourReasonKind.NON_PRODUCTIVE)
        ).scalars()
    }
    return [(code, name) for code, name in DEFAULT_REASONS if code.casefold() not in have]


def seed_default_reasons(session: Session, tenant_id: uuid.UUID, actor: AuditActor, reason: str) -> int:
    """Add the missing default entries (in the session's tenant scope), each with an audit event; returns how many."""
    added = 0
    for code, name in missing_default_reasons(session):
        row = EngineHourReason(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            kind=EngineHourReasonKind.NON_PRODUCTIVE,
            code=code,
            name=name,
            is_active=True,
        )
        session.add(row)
        session.flush()
        AuditService(session).record(
            actor=actor,
            action="meter.reason.created",
            entity_type="engine_hour_reason",
            entity_id=row.id,
            tenant_id=tenant_id,
            after={"list": EngineHourReasonKind.NON_PRODUCTIVE.value, "code": code, "label": name},
            reason=reason,
        )
        added += 1
    return added
