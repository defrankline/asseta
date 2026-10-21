"""Request-level idempotency keyed by (scope, route, Idempotency-Key). A repeated key with the same request
replays the stored response; a reused key with a different request is a 409. Concurrent duplicates serialize
on the unique index (INSERT ... ON CONFLICT waits for the first transaction)."""

import hashlib
import json
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import DateTime, Integer, String, UniqueConstraint, select
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.orm import Mapped, Session, mapped_column

from asseta.core.db import Base, UuidPk, utcnow
from asseta.core.errors import AppError, Conflict


class IdempotencyRecord(UuidPk, Base):
    __tablename__ = "idempotency_record"
    __table_args__ = (UniqueConstraint("scope_key", "route", "idempotency_key", name="uq_idempotency"),)

    scope_key: Mapped[str] = mapped_column(String(64), nullable=False)
    route: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status: Mapped[int | None] = mapped_column(Integer)
    response_body: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class IdempotencyKeyRequired(AppError):
    status_code = 400
    code = "IDEMPOTENCY_KEY_REQUIRED"


def request_hash(payload: BaseModel | dict[str, Any] | None) -> str:
    data = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()


class IdempotencyGuard:
    """Usage: `replay = guard.begin(...)`; if replay is not None return it; else do work and `guard.complete`."""

    def __init__(self, session: Session, scope_key: str, route: str, key: str | None, req_hash: str):
        if not key:
            raise IdempotencyKeyRequired("Idempotency-Key header is required for this operation")
        try:
            uuid.UUID(key)
        except ValueError as exc:
            raise IdempotencyKeyRequired("Idempotency-Key must be a UUID") from exc
        self._s = session
        self._scope_key, self._route, self._key, self._hash = scope_key, route, key, req_hash
        self._record_id: uuid.UUID | None = None

    def begin(self) -> dict[str, Any] | None:
        inserted = self._s.execute(
            insert(IdempotencyRecord)
            .values(
                id=uuid.uuid4(),
                scope_key=self._scope_key,
                route=self._route,
                idempotency_key=self._key,
                request_hash=self._hash,
                created_at=utcnow(),
            )
            .on_conflict_do_nothing(constraint="uq_idempotency")
            .returning(IdempotencyRecord.id)
        ).scalar_one_or_none()
        if inserted is not None:
            self._record_id = inserted
            return None
        existing = self._s.execute(
            select(IdempotencyRecord).where(
                IdempotencyRecord.scope_key == self._scope_key,
                IdempotencyRecord.route == self._route,
                IdempotencyRecord.idempotency_key == self._key,
            )
        ).scalar_one()
        if existing.request_hash != self._hash:
            raise Conflict("Idempotency-Key was already used with a different request", code="IDEMPOTENCY_MISMATCH")
        if existing.response_body is None:
            raise Conflict(
                "Original request with this Idempotency-Key is still in progress", code="IDEMPOTENCY_IN_PROGRESS"
            )
        return existing.response_body

    def complete(self, response: BaseModel, status: int = 200) -> None:
        assert self._record_id is not None
        record = self._s.get(IdempotencyRecord, self._record_id)
        assert record is not None
        record.response_status = status
        record.response_body = response.model_dump(mode="json")
