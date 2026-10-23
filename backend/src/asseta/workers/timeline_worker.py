"""Timeline worker: consumes `asseta.telemetry.position` (keyed by machine -> per-machine ordering) and replays
the machine timeline from the event time. Offsets are committed only after the replay transactions commit;
replays are idempotent, so redelivery after a crash is safe.

Messages are consumed in batches and coalesced to ONE replay per machine from the batch's earliest event time: a
replay rebuilds the machine's derived timeline from that instant over every stored position, and each event is
published only after its position committed, so it subsumes the batch's later events for the same machine. One
replay per message capped the worker at ~7 messages/s in the Gate 7E telemetry load drill (100 machines x 63 fixes
took 14 min to drain)."""

import json
import signal
import uuid
from datetime import datetime
from typing import Any

import structlog
from confluent_kafka import Consumer, KafkaError

from asseta.core.config import get_settings
from asseta.core.correlation import set_correlation_id
from asseta.core.db import DbScope, apply_scope, get_sessionmaker
from asseta.core.logging import configure_logging
from asseta.modules.geospatial.timeline import ReplayResult, TimelineProcessor, replay_window_start
from asseta.modules.telemetry.ingestion import TIMELINE_TOPIC

log = structlog.get_logger()


def handle_position_event(payload: dict[str, Any], correlation_id: str | None = None) -> ReplayResult:
    set_correlation_id(correlation_id or str(uuid.uuid4()))
    tenant_id, machine_id = uuid.UUID(payload["tenant_id"]), uuid.UUID(payload["machine_id"])
    since = replay_window_start(datetime.fromisoformat(payload["event_time"]))
    with get_sessionmaker().begin() as session:
        apply_scope(session, DbScope.TENANT, tenant_id, None)  # replay is confined to the event's tenant
        return TimelineProcessor(session, tenant_id).replay(machine_id, since)


BATCH_SIZE = 500


def coalesce(payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One payload per (tenant, machine): the one with the earliest event time (replays start there)."""
    first: dict[tuple[str, str], dict[str, Any]] = {}
    for p in payloads:
        key = (p["tenant_id"], p["machine_id"])
        cur = first.get(key)
        if cur is None or datetime.fromisoformat(p["event_time"]) < datetime.fromisoformat(cur["event_time"]):
            first[key] = p
    return list(first.values())


def run() -> None:
    configure_logging()
    consumer = Consumer(
        {
            "bootstrap.servers": get_settings().kafka_bootstrap,
            "group.id": "asseta-timeline",
            "enable.auto.commit": False,
            "auto.offset.reset": "earliest",
        }
    )
    consumer.subscribe([TIMELINE_TOPIC])
    stopping = False

    def stop(*_: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        while not stopping:
            msgs = consumer.consume(num_messages=BATCH_SIZE, timeout=1.0)
            if not msgs:
                continue
            payloads: list[dict[str, Any]] = []
            correlation: str | None = None
            for msg in msgs:
                err = msg.error()
                if err is not None:
                    if err.code() != KafkaError._PARTITION_EOF:
                        log.error("timeline_consumer_error", error=str(err))
                    continue
                raw = msg.headers() or []
                pairs = raw.items() if isinstance(raw, dict) else raw
                headers = {k: v.decode() if isinstance(v, bytes) else str(v) for k, v in pairs}
                correlation = correlation or headers.get("correlation_id")
                payloads.append(json.loads(msg.value() or b"{}"))
            failed = False
            for payload in coalesce(payloads):
                try:
                    result = handle_position_event(payload, correlation)
                    log.info("timeline_replayed", positions=result.positions, geofence_events=result.geofence_events)
                except Exception:  # do not commit: the batch is retried after restart/rebalance
                    log.exception("timeline_replay_failed")
                    failed = True
            if payloads:
                log.info("timeline_batch", messages=len(payloads), replays=len(coalesce(payloads)), failed=failed)
            # A batch of only errors/EOFs (e.g. the topic does not exist yet on a fresh broker) stored no offset:
            # committing it raises _NO_OFFSET and crash-looped the worker until the first position arrived.
            if payloads and not failed:
                consumer.commit(asynchronous=False)
    finally:
        consumer.close()
