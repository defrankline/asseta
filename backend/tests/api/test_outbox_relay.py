"""Outbox relay: only broker-ACKed events are marked published; failures back off; replicas never double-claim."""

import threading
from datetime import timedelta

from sqlalchemy import select

from asseta.core.db import DbScope, apply_scope, get_sessionmaker, utcnow
from asseta.core.events import PublishableEvent
from asseta.core.outbox import OutboxEvent
from asseta.workers.outbox_relay import relay_batch
from tests.support.api import Api


class RecordingPublisher:
    def __init__(self, fail_ids: set[str] | None = None):
        self.sent: list[PublishableEvent] = []
        self.fail_ids = fail_ids or set()
        self.lock = threading.Lock()

    def publish(self, events: list[PublishableEvent], timeout_seconds: float) -> dict[str, str | None]:
        with self.lock:
            self.sent.extend(events)
        return {e.event_id: ("broker unavailable" if e.event_id in self.fail_ids else None) for e in events}


def _events() -> list[OutboxEvent]:
    with get_sessionmaker().begin() as s:
        apply_scope(s, DbScope.SYSTEM, None, None)
        return list(s.execute(select(OutboxEvent).order_by(OutboxEvent.created_at)).scalars())


def test_domain_actions_write_outbox_and_relay_marks_acked(api: Api) -> None:
    t = api.onboard("Events Co", price="10")
    api.activate(t)
    pending = _events()
    assert {e.event_type for e in pending} >= {"TenantOnboarded", "SubscriptionStatusChanged"}
    assert all(e.published_at is None and e.correlation_id for e in pending)

    failing = RecordingPublisher(fail_ids={str(pending[0].id)})
    with get_sessionmaker().begin() as s:
        published, failed = relay_batch(s, failing)
    assert (published, failed) == (len(pending) - 1, 1)
    after = {e.id: e for e in _events()}
    bad = after[pending[0].id]
    assert bad.published_at is None and bad.attempts == 1 and bad.last_error == "broker unavailable"
    assert bad.next_attempt_at is not None and bad.next_attempt_at > utcnow() + timedelta(seconds=1)

    # Not retried before its backoff; nothing else left to send.
    ok = RecordingPublisher()
    with get_sessionmaker().begin() as s:
        assert relay_batch(s, ok) == (0, 0)


def test_concurrent_relays_never_double_publish(api: Api) -> None:
    for i in range(3):
        api.onboard(f"Concurrent {i}", price="10")
    total = len(_events())
    pub = RecordingPublisher()
    barrier = threading.Barrier(3)

    def worker() -> None:
        barrier.wait()
        with get_sessionmaker().begin() as s:
            relay_batch(s, pub, batch_size=2)

    for _ in range(4):
        threads = [threading.Thread(target=worker) for _ in range(3)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
    ids = [e.event_id for e in pub.sent]
    assert len(ids) == len(set(ids)) == total
    assert all(e.published_at is not None for e in _events())
