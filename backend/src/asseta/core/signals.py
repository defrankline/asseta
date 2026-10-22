"""Detached domain signals: an outbox event committed in its *own* transaction, for facts that must survive the
caller's rollback (e.g. a refused segregation-of-duties attempt raises, rolling the request back). Best effort:
failure to record never masks the original refusal."""

import uuid
from typing import Any

import structlog

from asseta.core.db import DbScope, apply_scope, get_sessionmaker
from asseta.core.outbox import OutboxWriter

log = structlog.get_logger()


def emit_detached(topic: str, event_type: str, tenant_id: uuid.UUID, payload: dict[str, Any]) -> None:
    try:
        with get_sessionmaker().begin() as session:
            apply_scope(session, DbScope.TENANT, tenant_id, None)
            OutboxWriter(session).emit(
                topic=topic, event_type=event_type, key=str(tenant_id), payload=payload, tenant_id=tenant_id
            )
    except Exception:
        log.exception("detached_signal_failed", event_type=event_type)


def sod_violation(
    tenant_id: uuid.UUID, actor_id: uuid.UUID | None, action: str, entity_type: str, entity_id: object
) -> None:
    """A user tried to approve/verify their own record (refused). Feeds SOD_VIOLATION_ATTEMPT notifications and,
    later, Gate 6 fraud rules."""
    emit_detached(
        "asseta.security",
        "SegregationOfDutiesViolation",
        tenant_id,
        {
            "actor_user_id": str(actor_id) if actor_id else None,
            "action": action,
            "entity_type": entity_type,
            "entity_id": str(entity_id),
        },
    )
