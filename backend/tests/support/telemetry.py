"""Gate 2 test helpers: tracked-machine setup via the real APIs, simulator-driven ingestion and timeline drain."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select

from asseta.core.db import DbScope, apply_scope, get_sessionmaker, utcnow
from asseta.core.outbox import OutboxEvent
from asseta.modules.telemetry.ingestion import TIMELINE_TOPIC
from asseta.tools.gps_simulator import Fix, traccar_payload
from asseta.workers.timeline_worker import handle_position_event
from tests.support.api import Actor, Api

DAR = (-6.8000, 39.2800)  # Dar es Salaam area — test coordinates (lat, lon)


@dataclass
class Tracked:
    tenant: dict[str, Any]
    owner: Actor
    machine_id: str
    tracker_id: str
    device_id: str


class Telemetry:
    def __init__(self, api: Api):
        self.api = api
        r = api.platform.post(
            "/api/v1/platform/tracker-models",
            {
                "manufacturer": "Simulated",
                "model": "OsmAnd",
                "adapter": "TRACCAR",
                "protocol": "osmand",
                "declared_capabilities": ["GNSS", "ACCURACY", "IGNITION", "ENGINE_HOURS", "EXTERNAL_POWER"],
            },
        )
        assert r.status_code == 201, r.text
        self.model_id = r.json()["id"]
        g = api.platform.post("/api/v1/platform/telemetry-gateways", {"name": "traccar-test", "adapter": "TRACCAR"})
        assert g.status_code == 201, g.text
        self.key = g.json()["gateway_key"]

    def tracked_machine(
        self, name: str, device_id: str, *, assign_at: datetime | None = None, tenant: dict[str, Any] | None = None
    ) -> Tracked:
        t = tenant or self.api.onboard(name, price="1000")
        if tenant is None:
            self.api.activate(t)
        owner: Actor = t["owner"]
        [machine_id] = self.api.add_machines(
            owner, 1, enroll_on=self.api.clock.now.date(), prefix=device_id.replace("-", "")
        )
        tracker_id = self.register(owner, device_id)
        r = owner.post(
            f"/api/v1/tenant/trackers/{tracker_id}/assign",
            {"machine_id": machine_id, "effective_from": (assign_at or self.api.clock.now).isoformat()},
        )
        assert r.status_code == 201, r.text
        return Tracked(t, owner, machine_id, tracker_id, device_id)

    def register(self, owner: Actor, device_id: str) -> str:
        r = owner.post(
            "/api/v1/tenant/trackers", {"tracker_model_id": self.model_id, "external_id": device_id, "label": device_id}
        )
        assert r.status_code == 201, r.text
        return str(r.json()["id"])

    def send(self, device_id: str, fix: Fix, key: str | None = None, **kw: Any) -> dict[str, Any]:
        return self.raw(traccar_payload(device_id, fix, **kw), key)

    def raw(self, payload: Any, key: str | None = None) -> dict[str, Any]:
        r = self.api.client.post(
            "/api/v1/telemetry/traccar", json=payload, headers={"X-Asseta-Gateway-Key": key or self.key}
        )
        assert r.status_code == 202, r.text
        body: dict[str, Any] = r.json()
        return body

    def drain_timeline(self) -> int:
        """Act as the Kafka timeline consumer for pending PositionStored events (in creation order)."""
        with get_sessionmaker().begin() as s:
            apply_scope(s, DbScope.SYSTEM, None, None)
            rows = list(
                s.execute(
                    select(OutboxEvent)
                    .where(OutboxEvent.topic == TIMELINE_TOPIC, OutboxEvent.published_at.is_(None))
                    .order_by(OutboxEvent.created_at)
                ).scalars()
            )
            payloads = [r.payload for r in rows]
            for r in rows:
                r.published_at = utcnow()
        for p in payloads:
            handle_position_event(p)
        return len(payloads)
