"""Outbox relay worker: moves committed domain events from `outbox_event` to Kafka.

* Batches are claimed with FOR UPDATE SKIP LOCKED, so several relay replicas never double-claim.
* A row is marked published only after broker acknowledgement; failures are retried with backoff and
  surface in `attempts`/`last_error` (monitored as backlog). Kafka being down never affects API writes.
"""

import json
import signal
import time
from datetime import timedelta

import structlog
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from asseta.core.config import get_settings
from asseta.core.db import DbScope, apply_scope, get_sessionmaker, utcnow
from asseta.core.events import EventPublisher, KafkaEventPublisher, PublishableEvent
from asseta.core.logging import configure_logging
from asseta.core.outbox import OutboxEvent

log = structlog.get_logger()
MAX_BACKOFF_SECONDS = 300


def _backoff(attempts: int) -> timedelta:
    return timedelta(seconds=min(MAX_BACKOFF_SECONDS, 2 ** min(attempts, 9)))


def relay_batch(
    session: Session, publisher: EventPublisher, batch_size: int = 200, timeout_seconds: float = 10.0
) -> tuple[int, int]:
    """One relay pass inside the caller's transaction. Returns (published, failed)."""
    apply_scope(session, DbScope.SYSTEM, None, None)
    now = utcnow()
    rows = list(
        session.execute(
            select(OutboxEvent)
            .where(
                OutboxEvent.published_at.is_(None),
                or_(OutboxEvent.next_attempt_at.is_(None), OutboxEvent.next_attempt_at <= now),
            )
            .order_by(OutboxEvent.created_at)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        ).scalars()
    )
    if not rows:
        return 0, 0
    events = [
        PublishableEvent(
            str(r.id),
            r.topic,
            r.key,
            r.event_type,
            json.dumps(r.payload, separators=(",", ":"), sort_keys=True).encode(),
            r.correlation_id,
            str(r.tenant_id) if r.tenant_id else None,
        )
        for r in rows
    ]
    results = publisher.publish(events, timeout_seconds)
    published = failed = 0
    for row in rows:
        error = results.get(str(row.id), "no delivery report")
        if error is None:
            row.published_at = utcnow()
            published += 1
        else:
            row.attempts += 1
            row.last_error = error[:1000]
            row.next_attempt_at = utcnow() + _backoff(row.attempts)
            failed += 1
    return published, failed


def run() -> None:
    configure_logging()
    settings = get_settings()
    publisher = KafkaEventPublisher(settings.kafka_bootstrap)
    stopping = False

    def stop(*_: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    log.info("outbox_relay_started")
    while not stopping:
        try:
            with get_sessionmaker().begin() as session:
                published, failed = relay_batch(session, publisher)
            if published or failed:
                log.info("outbox_relay_batch", published=published, failed=failed)
            if not published:
                time.sleep(1.0)
        except Exception:  # keep relaying after transient DB/Kafka failures
            log.exception("outbox_relay_error")
            time.sleep(5.0)
    log.info("outbox_relay_stopped")
