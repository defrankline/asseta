"""Live Kafka integration: outbox -> relay -> broker -> consumer, and broker-down retention.

ASSETA_IT_KAFKA=localhost:29192 uv run pytest -m integration tests/integration/test_kafka_live.py
"""

import json
import os
import uuid
from typing import Any

import pytest
from confluent_kafka import Consumer

from asseta.core.db import DbScope, apply_scope, get_sessionmaker
from asseta.core.events import KafkaEventPublisher
from asseta.core.outbox import OutboxEvent
from asseta.workers.outbox_relay import relay_batch
from tests.support.api import Api

BOOTSTRAP = os.environ.get("ASSETA_IT_KAFKA", "")
pytestmark = [pytest.mark.integration, pytest.mark.skipif(not BOOTSTRAP, reason="ASSETA_IT_KAFKA not set")]


def test_outbox_events_reach_kafka_with_headers(api: Api) -> None:
    t = api.onboard("Kafka Co", price="10")
    with get_sessionmaker().begin() as s:
        published, failed = relay_batch(s, KafkaEventPublisher(BOOTSTRAP), timeout_seconds=30)
    assert published >= 1 and failed == 0

    consumer = Consumer(
        {"bootstrap.servers": BOOTSTRAP, "group.id": f"it-{uuid.uuid4()}", "auto.offset.reset": "earliest"}
    )
    consumer.subscribe(["asseta.platform.tenant"])
    found: tuple[dict[str, Any], dict[str, str]] | None = None
    for _ in range(60):
        msg = consumer.poll(1.0)
        if msg is None or msg.error():
            continue
        payload = json.loads(msg.value() or b"{}")
        if payload["tenant_id"] == t["tenant"]["id"]:
            raw = msg.headers() or []
            pairs = raw.items() if isinstance(raw, dict) else raw
            found = (payload, {k: v.decode() if isinstance(v, bytes) else str(v) for k, v in pairs})
            break
    consumer.close()
    assert found is not None, "TenantOnboarded not consumed"
    payload, headers = found
    assert headers["event_type"] == "TenantOnboarded" and headers["tenant_id"] == t["tenant"]["id"]
    assert uuid.UUID(headers["event_id"]) and uuid.UUID(headers["correlation_id"])


def test_broker_unreachable_keeps_events_for_retry(api: Api) -> None:
    api.onboard("Offline Kafka Co", price="10")
    with get_sessionmaker().begin() as s:
        published, failed = relay_batch(s, KafkaEventPublisher("localhost:1"), timeout_seconds=2)
    assert published == 0 and failed >= 1
    with get_sessionmaker().begin() as s:
        apply_scope(s, DbScope.SYSTEM, None, None)
        rows = s.query(OutboxEvent).all()
        assert rows and all(r.published_at is None and r.attempts == 1 and r.last_error for r in rows)
