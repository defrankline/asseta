"""Record refused attempts (missing permission, segregation-of-duties) as `security_event` rows.

The refused request rolls back, so the row is written in its own short transaction in the tenant's RLS scope (the
same detached pattern as `core.signals`). Best effort: failing to record never masks the original refusal."""

import uuid
from datetime import datetime
from typing import Any

import structlog

from asseta.core.db import DbScope, apply_scope, get_sessionmaker, utcnow
from asseta.modules.accountability.models import SecurityEvent, SecurityEventKind

log = structlog.get_logger()


def record_security_event(
    tenant_id: uuid.UUID | None,
    kind: SecurityEventKind,
    actor_user_id: uuid.UUID | None,
    *,
    permission: str | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: object = None,
    method: str | None = None,
    path: str | None = None,
    detail: dict[str, Any] | None = None,
    occurred_at: datetime | None = None,
    actor_subject: str | None = None,
) -> None:
    if tenant_id is None:
        return  # platform-scope refusals are outside the tenant's oversight
    try:
        with get_sessionmaker().begin() as session:
            apply_scope(session, DbScope.TENANT, tenant_id, actor_user_id)
            session.add(
                SecurityEvent(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    occurred_at=occurred_at or utcnow(),
                    kind=kind,
                    actor_user_id=actor_user_id,
                    actor_subject=actor_subject[:64] if actor_subject else None,
                    permission=permission[:128] if permission else None,
                    action=action[:64] if action else None,
                    entity_type=entity_type[:64] if entity_type else None,
                    entity_id=str(entity_id)[:64] if entity_id is not None else None,
                    request_method=method[:8] if method else None,
                    request_path=path[:300] if path else None,
                    detail=detail or {},
                )
            )
    except Exception:
        log.exception("security_event_record_failed", kind=kind.value)


def permission_refused(
    tenant_id: uuid.UUID | None,
    actor_user_id: uuid.UUID | None,
    permission: str,
    method: str | None = None,
    path: str | None = None,
    detail: dict[str, Any] | None = None,
    occurred_at: datetime | None = None,
    actor_subject: str | None = None,
) -> None:
    record_security_event(
        tenant_id,
        SecurityEventKind.PERMISSION_DENIED,
        actor_user_id,
        permission=permission,
        method=method,
        path=path,
        detail=detail,
        occurred_at=occurred_at,
        actor_subject=actor_subject,
    )
