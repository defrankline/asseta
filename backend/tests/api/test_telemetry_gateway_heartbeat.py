"""Regression (Gate 7E telemetry load drill): ingestion must not serialise on the gateway row.

Every message used to `UPDATE telemetry_gateway SET last_seen_at` inside the request transaction, so all ingestion
queued behind one row lock held until commit; at 20 concurrent senders the waiters exhausted the DB pool and the
threadpool and the API stopped answering (docs/evidence/drills/*-telemetry-load.md). The heartbeat is now throttled
and taken with SKIP LOCKED, so a held gateway row never blocks ingestion."""

import threading
from datetime import timedelta

from sqlalchemy import Engine, text

from asseta.tools.gps_simulator import Fix, traccar_payload
from tests.support.api import Api
from tests.support.telemetry import DAR, Telemetry


def _last_seen(owner_engine: Engine) -> object:
    with owner_engine.begin() as c:
        c.execute(text("SELECT set_config('app.scope', 'system', true)"))
        return c.execute(text("SELECT last_seen_at FROM telemetry_gateway")).scalar_one()


def test_gateway_heartbeat_is_throttled(api: Api, owner_engine: Engine) -> None:
    tel = Telemetry(api)
    tel.tracked_machine("Heartbeat Co", "HB-1")
    t0 = api.clock.now
    assert tel.send("HB-1", Fix(t0 + timedelta(seconds=1), DAR[0], DAR[1], 0, 0))["accepted"] == 1
    first = _last_seen(owner_engine)
    assert first == t0
    api.clock.now = t0 + timedelta(seconds=30)
    assert tel.send("HB-1", Fix(t0 + timedelta(seconds=2), DAR[0], DAR[1], 0, 0))["accepted"] == 1
    assert _last_seen(owner_engine) == first  # within the heartbeat interval: no write, no row lock
    api.clock.now = t0 + timedelta(seconds=61)
    assert tel.send("HB-1", Fix(t0 + timedelta(seconds=3), DAR[0], DAR[1], 0, 0))["accepted"] == 1
    assert _last_seen(owner_engine) == t0 + timedelta(seconds=61)


def test_ingestion_does_not_wait_for_a_locked_gateway_row(api: Api, owner_engine: Engine) -> None:
    tel = Telemetry(api)
    tel.tracked_machine("Lock Co", "LOCK-1")
    t0 = api.clock.now
    done = threading.Event()
    result: dict[str, object] = {}

    def ingest() -> None:
        result["body"] = tel.send("LOCK-1", Fix(t0 + timedelta(seconds=1), DAR[0], DAR[1], 0, 0))
        done.set()

    with owner_engine.connect() as holder:  # another request (or anything else) holding the gateway row
        tx = holder.begin()
        holder.execute(text("SELECT set_config('app.scope', 'system', true)"))
        holder.execute(text("SELECT id FROM telemetry_gateway FOR UPDATE"))
        worker = threading.Thread(target=ingest, daemon=True)
        worker.start()
        finished = done.wait(timeout=15)
        tx.rollback()  # always release, so a regression fails instead of hanging the suite
    worker.join(timeout=15)
    assert finished, "ingestion blocked on the telemetry_gateway row lock"
    assert result["body"]["accepted"] == 1  # type: ignore[index]


def test_lock_wait_fails_fast_with_retryable_503(api: Api, owner_engine: Engine) -> None:
    """A request blocked on a row lock no longer pins a pool connection + worker thread indefinitely: after the
    configured lock_timeout it gets 503 DATABASE_BUSY (Traccar and the apps retry), and the next attempt succeeds."""
    tel = Telemetry(api)
    a = tel.tracked_machine("Busy Co", "BUSY-1")
    t0 = api.clock.now
    payload = traccar_payload("BUSY-1", Fix(t0 + timedelta(seconds=1), DAR[0], DAR[1], 0, 0))
    with owner_engine.connect() as holder:
        tx = holder.begin()
        holder.execute(text("SELECT set_config('app.scope', 'system', true)"))
        holder.execute(text("SELECT id FROM tracker WHERE id = :id FOR UPDATE"), {"id": a.tracker_id})
        try:
            r = api.client.post("/api/v1/telemetry/traccar", json=payload, headers={"X-Asseta-Gateway-Key": tel.key})
        finally:
            tx.rollback()
    assert r.status_code == 503, r.text
    assert r.json()["error"]["code"] == "DATABASE_BUSY"
    assert tel.raw(payload)["accepted"] == 1  # retry after the lock is gone: stored exactly once
