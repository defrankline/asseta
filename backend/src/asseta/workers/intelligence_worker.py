"""Intelligence worker (Gate 6): event-driven risk checks from the `asseta.*` topics (receipt duplicates on expense
submission, linking alerts / meter exceptions / segregation-of-duties attempts to cases) plus a periodic sweep of
every tenant, each in its own RLS scope. Detection is idempotent, so redelivery and re-sweeps are harmless. The
worker never blocks jobs, payments or tracking: it only reads facts and writes signals and cases.

Gate 6D: every `ML_EVERY_SECONDS` the ML cycle refreshes the recent weekly snapshots of tenants with a deployed
model, runs bounded inference (`inference.run_inference_cycle`) and the daily drift check. Every step catches its
own failures (recorded in `inference_audit` / logs), so a dead MinIO, a bad artifact or a slow tenant never stops
the deterministic sweep or event handling."""

import signal
import time
import uuid
from datetime import datetime, timedelta

import structlog
from confluent_kafka import Consumer, KafkaError
from sqlalchemy import select

from asseta.core.clock import system_clock
from asseta.core.config import get_settings
from asseta.core.correlation import set_correlation_id
from asseta.core.db import DbScope, apply_scope, get_sessionmaker
from asseta.core.logging import configure_logging
from asseta.core.storage import ObjectReader
from asseta.modules.intelligence.feature_store import snapshot_tenant, sync_feature_definitions
from asseta.modules.intelligence.inference import InferenceCycleResult, run_inference_cycle
from asseta.modules.intelligence.ml_models import DEPLOYED_STATUSES, ModelVersion
from asseta.modules.intelligence.ml_monitoring import run_drift_cycle
from asseta.modules.intelligence.sweep import IntelligenceSweepResult, handle_event, sweep_tenant
from asseta.modules.notification.rules import DomainEvent
from asseta.modules.tenancy.models import Tenant, TenantStatus
from asseta.workers.notification_worker import TOPICS, decode

log = structlog.get_logger()
SWEEP_EVERY_SECONDS = 300.0
ML_EVERY_SECONDS = 3600.0
SNAPSHOT_LOOKBACK = timedelta(days=15)  # the last two week ends, so a missed run is caught up
EVENT_TYPES = frozenset(
    {"ExpenseSubmitted", "TrackingAlertRaised", "MeterExceptionRaised", "SegregationOfDutiesViolation"}
)


def sweep_all() -> dict[uuid.UUID, IntelligenceSweepResult]:
    now = system_clock()
    with get_sessionmaker().begin() as session:
        apply_scope(session, DbScope.SYSTEM, None, None)
        tenants = list(session.execute(select(Tenant.id).where(Tenant.status != TenantStatus.CLOSED)).scalars())
    results = {}
    for tenant_id in tenants:
        try:
            with get_sessionmaker().begin() as session:
                apply_scope(session, DbScope.TENANT, tenant_id, None)
                results[tenant_id] = sweep_tenant(session, tenant_id, now)
        except Exception:
            log.exception("intelligence_sweep_failed", tenant_id=str(tenant_id))
    return results


def refresh_snapshots(now: datetime) -> list[uuid.UUID]:
    """Recent weekly snapshots for tenants with a deployed model (idempotent: existing points are kept)."""
    with get_sessionmaker().begin() as session:
        apply_scope(session, DbScope.SYSTEM, None, None)
        tenants = list(
            session.execute(
                select(ModelVersion.tenant_id).where(ModelVersion.status.in_(DEPLOYED_STATUSES)).distinct()
            ).scalars()
        )
        sync_feature_definitions(session)
    for tenant_id in tenants:
        try:
            with get_sessionmaker().begin() as session:
                apply_scope(session, DbScope.SYSTEM, None, None)
                snapshot_tenant(session, tenant_id, now - SNAPSHOT_LOOKBACK, now, now)
        except Exception:
            log.exception("ml_snapshot_refresh_failed", tenant_id=str(tenant_id))
    return tenants


def run_ml_cycle(store: ObjectReader | None, now: datetime | None = None) -> InferenceCycleResult | None:
    """Snapshots -> inference -> drift. Never raises (ML must not block the deterministic worker)."""
    now = now or system_clock()
    try:
        refresh_snapshots(now)
    except Exception:
        log.exception("ml_snapshot_refresh_failed")
    result = None
    try:
        if store is None:
            from asseta.main import build_object_store

            store = build_object_store(get_settings())
        result = run_inference_cycle(get_sessionmaker(), now, store)
        log.info(
            "ml_inference",
            switched_off=result.switched_off,
            models=len(result.results),
            outcomes=[r.outcome.value for r in result.results],
        )
    except Exception:
        log.exception("ml_inference_cycle_failed")
    try:
        run_drift_cycle(get_sessionmaker(), now)
    except Exception:
        log.exception("ml_drift_cycle_failed")
    return result


def process(event: DomainEvent) -> IntelligenceSweepResult | None:
    if event.event_type not in EVENT_TYPES or event.tenant_id is None:
        return None
    with get_sessionmaker().begin() as session:
        apply_scope(session, DbScope.TENANT, event.tenant_id, None)
        return handle_event(session, event.tenant_id, system_clock(), event.event_id, event.event_type, event.payload)


def run() -> None:
    configure_logging()
    settings = get_settings()
    consumer = Consumer(
        {
            "bootstrap.servers": settings.kafka_bootstrap,
            "group.id": "asseta-intelligence",
            "enable.auto.commit": False,
            "auto.offset.reset": "earliest",
            "topic.metadata.refresh.interval.ms": 30000,
        }
    )
    consumer.subscribe([TOPICS])
    stopping = False

    def stop(*_: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    next_sweep = time.monotonic()
    next_ml = time.monotonic() + 60.0  # let the first deterministic sweep run first
    ml_store: ObjectReader | None = None
    log.info("intelligence_worker_started")
    try:
        while not stopping:
            msg = consumer.poll(1.0)
            if msg is not None:
                err = msg.error()
                if err is not None:
                    if err.code() != KafkaError._PARTITION_EOF:
                        log.error("intelligence_consumer_error", error=str(err))
                else:
                    try:
                        event = decode(msg)
                        set_correlation_id(event.correlation_id or str(uuid.uuid4()))
                        process(event)
                        consumer.commit(message=msg, asynchronous=False)
                    except Exception:  # not committed: retried after restart/rebalance; the sweep also catches up
                        log.exception("intelligence_event_failed")
            if time.monotonic() >= next_sweep:
                next_sweep = time.monotonic() + SWEEP_EVERY_SECONDS
                results = sweep_all()
                log.info(
                    "intelligence_sweep",
                    tenants=len(results),
                    signals=sum(r.signals for r in results.values()),
                    cases_opened=sum(r.cases_opened for r in results.values()),
                )
            if time.monotonic() >= next_ml:
                next_ml = time.monotonic() + ML_EVERY_SECONDS
                if ml_store is None:
                    try:
                        from asseta.main import build_object_store

                        ml_store = build_object_store(settings)
                    except Exception:
                        log.exception("ml_object_store_unavailable")
                run_ml_cycle(ml_store)
    finally:
        consumer.close()
