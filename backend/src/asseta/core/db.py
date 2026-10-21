"""Engine/session management and per-transaction tenant scoping for PostgreSQL RLS.

The API connects as the non-owner role `asseta_app`; tenant-owned tables have FORCE ROW LEVEL SECURITY
policies keyed on `app.tenant_id` / `app.scope`, set with transaction-local `set_config` below.
"""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from enum import StrEnum
from functools import lru_cache

from sqlalchemy import BigInteger, DateTime, Engine, create_engine, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from asseta.core.config import get_settings


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class UuidPk:
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class SyncRevisioned:
    """Server-monotonic change revision for offline delta pull (bumped on every update by trigger)."""

    sync_revision: Mapped[int] = mapped_column(
        BigInteger, server_default=text("nextval('sync_revision_seq')"), nullable=False, index=True
    )


class DbScope(StrEnum):
    PLATFORM = "platform"  # platform-owner operations: platform tables only, no tenant business data
    TENANT = "tenant"  # a single tenant, via app.tenant_id
    SYSTEM = "system"  # internal workers with explicit, audited cross-tenant need


@lru_cache
def get_engine() -> Engine:
    # Every session speaks UTC so instants serialize consistently regardless of server timezone.
    return create_engine(
        get_settings().database_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=10,
        connect_args={"options": "-c timezone=UTC"},
    )


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False, autoflush=False)


def apply_scope(session: Session, scope: DbScope, tenant_id: uuid.UUID | None, actor_id: uuid.UUID | None) -> None:
    """Bind the current transaction to a scope. Must be called inside an open transaction."""
    if scope is DbScope.TENANT and tenant_id is None:
        raise ValueError("tenant scope requires tenant_id")
    session.execute(
        text(
            "SELECT set_config('app.scope', :scope, true), set_config('app.tenant_id', :tenant, true),"
            " set_config('app.actor_id', :actor, true)"
        ),
        {"scope": scope.value, "tenant": str(tenant_id) if tenant_id else "", "actor": str(actor_id or "")},
    )


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one transaction per request; commit on success, rollback on error."""
    session = get_sessionmaker()()
    try:
        session.begin()
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()
