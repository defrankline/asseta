"""Event publishing port and Kafka adapter (idempotent producer, acks=all). Delivery is at-least-once;
consumers deduplicate on the `event_id` header."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from confluent_kafka import KafkaError, Message, Producer

from asseta.core.errors import DependencyUnavailable


@dataclass(frozen=True)
class PublishableEvent:
    event_id: str
    topic: str
    key: str
    event_type: str
    payload: bytes
    correlation_id: str
    tenant_id: str | None


class EventPublisher(Protocol):
    def publish(self, events: list[PublishableEvent], timeout_seconds: float) -> dict[str, str | None]:
        """Returns event_id -> None on broker ACK, or an error string."""
        ...


class KafkaEventPublisher:
    def __init__(self, bootstrap_servers: str, client_id: str = "asseta-outbox-relay"):
        self._producer = Producer(
            {
                "bootstrap.servers": bootstrap_servers,
                "client.id": client_id,
                "enable.idempotence": True,
                "acks": "all",
                "compression.type": "zstd",
                "linger.ms": 5,
                "message.timeout.ms": 30000,
            }
        )

    def publish(self, events: list[PublishableEvent], timeout_seconds: float) -> dict[str, str | None]:
        results: dict[str, str | None] = {e.event_id: "not delivered before timeout" for e in events}

        def on_delivery(event_id: str) -> Callable[[KafkaError | None, Message], None]:
            def callback(err: KafkaError | None, _msg: Message) -> None:
                results[event_id] = None if err is None else str(err)

            return callback

        for e in events:
            headers: list[tuple[str, str | bytes | None]] = [
                ("event_id", e.event_id.encode()),
                ("event_type", e.event_type.encode()),
                ("correlation_id", e.correlation_id.encode()),
            ]
            if e.tenant_id:
                headers.append(("tenant_id", e.tenant_id.encode()))
            try:
                self._producer.produce(
                    e.topic, key=e.key.encode(), value=e.payload, headers=headers, on_delivery=on_delivery(e.event_id)
                )
            except BufferError as exc:
                raise DependencyUnavailable("Kafka producer queue full") from exc
        self._producer.flush(timeout_seconds)
        return results
