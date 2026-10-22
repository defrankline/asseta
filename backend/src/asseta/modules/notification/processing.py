"""Event -> notifications pipeline used by the notification worker (and tests, which feed outbox rows directly).
Idempotent: notifications are unique per (recipient, event-derived dedupe key), so Kafka redelivery is harmless."""

from collections.abc import Callable
from datetime import datetime

from sqlalchemy.orm import Session

from asseta.core.db import DbScope, apply_scope
from asseta.modules.notification.engine import NotificationEngine
from asseta.modules.notification.realtime import RealtimePublisher
from asseta.modules.notification.rules import PLATFORM_ENTITY_EVENTS, RULES, DomainEvent, Intent, entity_change


def process_event(
    event: DomainEvent,
    session_factory: Callable[[], Session],
    clock: Callable[[], datetime],
    publisher: RealtimePublisher | None = None,
) -> int:
    """Returns the number of notifications created."""
    rule_fn, change = RULES.get(event.event_type), entity_change(event)
    if rule_fn is None and change is None:
        return 0
    now = clock()
    with session_factory() as s, s.begin():
        intents: list[Intent] = []
        if rule_fn is not None:
            # Rule lookups see only the event's tenant (RLS); platform events read in platform scope.
            if event.tenant_id is not None:
                apply_scope(s, DbScope.TENANT, event.tenant_id, None)
            else:
                apply_scope(s, DbScope.PLATFORM, None, None)
            intents = rule_fn(s, event)
        apply_scope(s, DbScope.SYSTEM, None, None)
        engine = NotificationEngine(s, now.date(), now)
        engine.deliver(event.tenant_id, intents, event.event_id)
        if change is not None:
            if event.tenant_id is not None:
                engine.entity_changed(event.tenant_id, change)
            if event.event_type in PLATFORM_ENTITY_EVENTS:
                engine.entity_changed(None, change)
        created = len(engine.created)
    if publisher is not None:
        engine.publish(publisher)
    return created
