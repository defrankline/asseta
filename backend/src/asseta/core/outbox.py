"""Transactional outbox: domain events are written in the business transaction and relayed to Kafka."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from asseta.core.correlation import get_correlation_id
from asseta.core.db import Base, UuidPk, utcnow


class OutboxEvent(UuidPk, Base):
    __tablename__ = "outbox_event"
    __table_args__ = (Index("ix_outbox_unpublished", "created_at", postgresql_where=text("published_at IS NULL")),)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    topic: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


class OutboxWriter:
    def __init__(self, session: Session):
        self._session = session

    def emit(
        self, *, topic: str, event_type: str, key: str, payload: dict[str, Any], tenant_id: uuid.UUID | None
    ) -> uuid.UUID:
        event = OutboxEvent(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            topic=topic,
            event_type=event_type,
            key=key,
            payload=payload,
            correlation_id=get_correlation_id(),
        )
        self._session.add(event)
        return event.id
