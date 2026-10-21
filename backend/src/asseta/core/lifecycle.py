"""Soft lifecycle shared by managed records: records with history are never deleted, they are *deactivated*
(audited, reason recorded), hidden from lists/pickers by default and can be reactivated."""

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import Query
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column
from sqlalchemy.orm.exc import StaleDataError

from asseta.core.db import utcnow
from asseta.core.errors import Conflict

IncludeInactive = Annotated[
    bool, Query(description="Also return deactivated/retired/closed records (hidden by default)")
]


class Deactivatable:
    """Who deactivated a record, when and why (cleared again on reactivation; the audit trail keeps history)."""

    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deactivated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    deactivation_reason: Mapped[str | None] = mapped_column(Text)


class LifecycleChangeIn(BaseModel):
    """Body of every deactivate/reactivate (and close/reopen) command."""

    reason: str = Field(min_length=3, max_length=500)
    version: int | None = Field(
        default=None, ge=1, description="Optional optimistic concurrency token from the last read"
    )


def check_version(current: int, expected: int | None, label: str) -> None:
    """Optimistic concurrency: refuse when the caller edited a stale copy."""
    if expected is not None and current != expected:
        raise Conflict(f"{label} was modified by someone else; reload and retry", code="STALE_VERSION")


def mark_inactive(row: Any, actor_id: uuid.UUID | None, reason: str, label: str) -> None:
    if not row.is_active:
        raise Conflict(f"{label} is already inactive", code="ALREADY_INACTIVE")
    row.is_active, row.deactivated_at, row.deactivated_by, row.deactivation_reason = False, utcnow(), actor_id, reason


def mark_active(row: Any, label: str) -> None:
    if row.is_active:
        raise Conflict(f"{label} is already active", code="ALREADY_ACTIVE")
    row.is_active, row.deactivated_at, row.deactivated_by, row.deactivation_reason = True, None, None, None


def flush_versioned(session: Session, label: str, conflict_code: str | None = None, conflict_msg: str = "") -> None:
    """Flush an edit: a concurrent version bump is STALE_VERSION; a unique-key clash is `conflict_code`."""
    try:
        with session.begin_nested():
            session.flush()
    except StaleDataError as exc:
        raise Conflict(f"{label} was modified concurrently", code="STALE_VERSION") from exc
    except IntegrityError as exc:
        if conflict_code is None:
            raise
        raise Conflict(conflict_msg, code=conflict_code) from exc
