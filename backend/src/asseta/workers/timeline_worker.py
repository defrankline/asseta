"""Timeline worker: consumes `asseta.telemetry.position` (keyed by machine -> per-machine ordering) and replays
the machine timeline from the event time. Offsets are committed only after the replay transaction commits;
replays are idempotent, so redelivery after a crash is safe."""

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
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            err = msg.error()
            if err is not None:
                if err.code() != KafkaError._PARTITION_EOF:
                    log.error("timeline_consumer_error", error=str(err))
                continue
            raw = msg.headers() or []
            pairs = raw.items() if isinstance(raw, dict) else raw
            headers = {k: v.decode() if isinstance(v, bytes) else str(v) for k, v in pairs}
            try:
                result = handle_position_event(json.loads(msg.value() or b"{}"), headers.get("correlation_id"))
                log.info("timeline_replayed", positions=result.positions, geofence_events=result.geofence_events)
            except Exception:  # do not commit: the message is retried after restart/rebalance
                log.exception("timeline_replay_failed")
                continue
            consumer.commit(message=msg, asynchronous=False)
    finally:
        consumer.close()
