"""Builds requested tenant data exports (DEC-032 Phase 5), deletes the files whose retention has passed, and runs the
company deletions whose waiting period is over (closure_executor.py; every `company_deletion_sweep_seconds`)."""

import signal
import time

import structlog

from asseta.core.clock import system_clock
from asseta.core.config import get_settings
from asseta.core.db import get_sessionmaker
from asseta.core.logging import configure_logging
from asseta.main import build_keycloak_admin, build_object_store
from asseta.modules.dataprotection.closure_executor import ClosureDeps, TraccarAdmin, psycopg_dsn, run_due_closures
from asseta.modules.dataprotection.export_worker_core import run_pending

log = structlog.get_logger()
IDLE_SLEEP_SECONDS = 15


def run() -> None:
    configure_logging()
    stopping = False

    def stop(*_: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    settings = get_settings()
    store = build_object_store(settings)
    closures = ClosureDeps(
        session_factory=get_sessionmaker(),
        store=store,
        idp=build_keycloak_admin(settings),
        owner_dsn=psycopg_dsn(settings.migration_database_url),
        clock=system_clock,
        traccar=TraccarAdmin(
            settings.traccar_api_url, settings.traccar_admin_email, settings.traccar_admin_password.get_secret_value()
        )
        if settings.traccar_admin_email and settings.traccar_admin_password.get_secret_value()
        else None,
    )
    next_sweep = 0.0
    while not stopping:
        built = 0
        try:
            built = run_pending(get_sessionmaker(), store, system_clock())
        except Exception:
            log.exception("data_export_cycle_failed")
        if time.monotonic() >= next_sweep:
            next_sweep = time.monotonic() + settings.company_deletion_sweep_seconds
            try:
                run_due_closures(closures)
            except Exception:
                log.exception("company_deletion_sweep_failed")
        if built == 0:
            deadline = time.monotonic() + IDLE_SLEEP_SECONDS
            while not stopping and time.monotonic() < deadline:
                time.sleep(1)
