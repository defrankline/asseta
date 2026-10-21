"""Idempotent deployment bootstrap (runs after migrations): provisions the Traccar telemetry gateway from the
`ASSETA_TRACCAR_GATEWAY_KEY` secret so the same secret configures both Traccar's forward header and Asseta.
Only the SHA-256 of the key is stored; rotating the env value rotates the gateway key on the next run."""

import hashlib
import os
import uuid

import structlog
from sqlalchemy import select

from asseta.core.db import DbScope, apply_scope, get_sessionmaker
from asseta.core.logging import configure_logging
from asseta.modules.telemetry.models import TelemetryGateway
from asseta.modules.tracker.models import TelemetryAdapterKind

GATEWAY_NAME = "traccar-primary"


def ensure_traccar_gateway(key: str) -> uuid.UUID:
    digest = hashlib.sha256(key.encode()).hexdigest()
    with get_sessionmaker().begin() as s:
        apply_scope(s, DbScope.SYSTEM, None, None)
        gw = s.execute(select(TelemetryGateway).where(TelemetryGateway.name == GATEWAY_NAME)).scalar_one_or_none()
        if gw is None:
            gw = TelemetryGateway(
                id=uuid.uuid4(), name=GATEWAY_NAME, adapter=TelemetryAdapterKind.TRACCAR, key_hash=digest, active=True
            )
            s.add(gw)
        else:
            gw.key_hash, gw.active = digest, True
        s.flush()
        return gw.id


def run() -> None:
    configure_logging()
    key = os.environ.get("ASSETA_TRACCAR_GATEWAY_KEY", "")
    if len(key) < 24:
        structlog.get_logger().warning("bootstrap_skipped_gateway", reason="ASSETA_TRACCAR_GATEWAY_KEY unset/short")
        return
    structlog.get_logger().info("bootstrap_gateway_ready", gateway_id=str(ensure_traccar_gateway(key)))
