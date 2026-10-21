"""Periodic connectivity sweep for every tenant with tracker assignments (each tenant in its own RLS scope)."""

import signal
import time
import uuid

import structlog
from sqlalchemy import text

from asseta.core.clock import system_clock
from asseta.core.db import DbScope, apply_scope, get_sessionmaker
from asseta.core.logging import configure_logging
from asseta.modules.geospatial.connectivity import SweepResult, sweep_tenant

log = structlog.get_logger()
INTERVAL_SECONDS = 60


def sweep_all() -> dict[uuid.UUID, SweepResult]:
    now = system_clock()
    with get_sessionmaker().begin() as session:
        apply_scope(session, DbScope.SYSTEM, None, None)
        session.execute(text("SELECT ensure_telemetry_partitions(3, 0)"))
        tenants = list(
            session.execute(
                text("SELECT DISTINCT tenant_id FROM tracker_assignment WHERE effective_to IS NULL")
            ).scalars()
        )
    results = {}
    for tenant_id in tenants:
        try:
            with get_sessionmaker().begin() as session:
                apply_scope(session, DbScope.TENANT, tenant_id, None)
                results[tenant_id] = sweep_tenant(session, tenant_id, now)
        except Exception:
            log.exception("connectivity_sweep_failed", tenant_id=str(tenant_id))
    return results


def run() -> None:
    configure_logging()
    stopping = False

    def stop(*_: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while not stopping:
        results = sweep_all()
        log.info("connectivity_sweep", tenants=len(results), transitions=sum(r.transitions for r in results.values()))
        deadline = time.monotonic() + INTERVAL_SECONDS
        while not stopping and time.monotonic() < deadline:
            time.sleep(1)
