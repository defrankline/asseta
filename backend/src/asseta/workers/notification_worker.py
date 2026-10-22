"""Notification worker: consumes every `asseta.*` domain topic (relayed from the outbox), applies the notification
rules, and dispatches due SMS deliveries. Offsets are committed only after the notification transaction commits;
redelivery is harmless (notifications are unique per recipient + event). Also dispatches due PUSH/EMAIL deliveries
(providers from ASSETA_PUSH_* / ASSETA_EMAIL_*; console by default)."""

import json
import signal
import time
import uuid
from typing import Any

import structlog
from confluent_kafka import Consumer, KafkaError, Message

from asseta.core.clock import system_clock
from asseta.core.config import get_settings
from asseta.core.correlation import set_correlation_id
from asseta.core.db import get_sessionmaker
from asseta.core.email import build_email_client
from asseta.core.logging import configure_logging
from asseta.core.push import build_push_router
from asseta.core.sms import build_sms_client
from asseta.modules.notification.channel_dispatch import ChannelDispatcher
from asseta.modules.notification.processing import process_event
from asseta.modules.notification.realtime import RedisBroker, SafePublisher
from asseta.modules.notification.rules import DomainEvent
from asseta.modules.notification.sms_channel import SmsDispatcher

log = structlog.get_logger()
TOPICS = "^asseta\\..*"
SMS_EVERY_SECONDS = 5.0


def decode(msg: Message) -> DomainEvent:
    raw = msg.headers() or []
    pairs: Any = raw.items() if isinstance(raw, dict) else raw
    headers = {k: v.decode() if isinstance(v, bytes) else str(v) for k, v in pairs}
    tenant = headers.get("tenant_id")
    return DomainEvent(
        event_id=uuid.UUID(headers["event_id"]),
        event_type=headers.get("event_type", ""),
        tenant_id=uuid.UUID(tenant) if tenant else None,
        payload=json.loads(msg.value() or b"{}"),
        correlation_id=headers.get("correlation_id"),
    )


def run() -> None:
    configure_logging()
    settings = get_settings()
    publisher = SafePublisher(RedisBroker(settings.redis_url))
    dispatcher = SmsDispatcher(get_sessionmaker(), build_sms_client(), system_clock, publisher)
    channels = ChannelDispatcher(get_sessionmaker(), build_push_router(), build_email_client(), system_clock)
    consumer = Consumer(
        {
            "bootstrap.servers": settings.kafka_bootstrap,
            "group.id": "asseta-notification",
            "enable.auto.commit": False,
            "auto.offset.reset": "earliest",
            "topic.metadata.refresh.interval.ms": 30000,  # pick up new asseta.* topics
        }
    )
    consumer.subscribe([TOPICS])
    stopping = False

    def stop(*_: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    next_sms = time.monotonic()
    log.info("notification_worker_started")
    try:
        while not stopping:
            msg = consumer.poll(1.0)
            if msg is not None:
                err = msg.error()
                if err is not None:
                    if err.code() != KafkaError._PARTITION_EOF:
                        log.error("notification_consumer_error", error=str(err))
                else:
                    try:
                        event = decode(msg)
                        set_correlation_id(event.correlation_id or str(uuid.uuid4()))
                        created = process_event(event, get_sessionmaker(), system_clock, publisher)
                        if created:
                            log.info("notifications_created", event_type=event.event_type, count=created)
                        consumer.commit(message=msg, asynchronous=False)
                    except Exception:  # not committed: retried after restart/rebalance
                        log.exception("notification_event_failed")
            if time.monotonic() >= next_sms:
                next_sms = time.monotonic() + SMS_EVERY_SECONDS
                try:
                    summary = dispatcher.dispatch_due()
                    if summary.sent or summary.failed or summary.refused:
                        log.info("sms_dispatched", **summary.__dict__)
                except Exception:
                    log.exception("sms_dispatch_failed")
                try:
                    pushed = channels.dispatch_due()
                    if pushed.sent or pushed.failed or pushed.undeliverable:
                        log.info("channel_deliveries_dispatched", **pushed.__dict__)
                except Exception:
                    log.exception("channel_dispatch_failed")
    finally:
        consumer.close()
