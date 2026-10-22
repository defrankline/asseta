"""Reminder scheduler: periodically evaluates the reminder rules for every tenant (idempotent per tenant-local day)
and refreshes the Keycloak membership mirror that notification audiences resolve against."""

import signal
import time

import structlog

from asseta.core.clock import system_clock
from asseta.core.config import get_settings
from asseta.core.db import get_sessionmaker
from asseta.core.logging import configure_logging
from asseta.modules.identity.authz_sync import AuthzSyncService
from asseta.modules.notification.realtime import RedisBroker, SafePublisher
from asseta.modules.notification.reminders import run_reminders
from asseta.modules.notification.settings import get_notification_settings

log = structlog.get_logger()


def refresh_mirror() -> None:
    from asseta.main import build_keycloak_admin

    try:
        with get_sessionmaker().begin() as session:
            AuthzSyncService(build_keycloak_admin(get_settings())).pull_role_mirror(session)
    except Exception:  # Keycloak down: keep notifying with the last mirror
        log.exception("membership_mirror_refresh_failed")


def run() -> None:
    configure_logging()
    cfg = get_notification_settings()
    publisher = SafePublisher(RedisBroker(get_settings().redis_url))
    stopping = False

    def stop(*_: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    next_mirror = 0.0
    while not stopping:
        if time.monotonic() >= next_mirror:
            refresh_mirror()
            next_mirror = time.monotonic() + cfg.mirror_refresh_seconds
        try:
            run_reminders(get_sessionmaker(), system_clock(), publisher, cfg)
        except Exception:
            log.exception("reminders_cycle_failed")
        deadline = time.monotonic() + cfg.scheduler_interval_seconds
        while not stopping and time.monotonic() < deadline:
            time.sleep(1)
