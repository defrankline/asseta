"""Builds requested tenant data exports (DEC-032 Phase 5) and deletes the files whose retention has passed."""

import signal
import time

import structlog

from asseta.core.clock import system_clock
from asseta.core.config import get_settings
from asseta.core.db import get_sessionmaker
from asseta.core.logging import configure_logging
from asseta.main import build_object_store
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
    store = build_object_store(get_settings())
    while not stopping:
        built = 0
        try:
            built = run_pending(get_sessionmaker(), store, system_clock())
        except Exception:
            log.exception("data_export_cycle_failed")
        if built == 0:
            deadline = time.monotonic() + IDLE_SLEEP_SECONDS
            while not stopping and time.monotonic() < deadline:
                time.sleep(1)
