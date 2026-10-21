"""Deterministic machine timeline replay (event-time ordered, idempotent).

`replay(machine_id, since)` deletes derived geofence/state events at or after `since` and recomputes them from
stored positions, so late or out-of-order telemetry is attached to the correct time window and past alerts are
re-evaluated (prompt.md §6). Alerts no longer supported by evidence are SUPERSEDED, never deleted.
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from asseta.modules.geospatial.alerts import AlertService
from asseta.modules.geospatial.models import (
    AlertSeverity,
    AlertType,
    Geofence,
    GeofenceEvent,
    GeofenceKind,
    GeofenceTransition,
)
from asseta.modules.policy.service import PolicyService
from asseta.modules.telemetry.models import MachineStateEvent, PositionQuality, StateDimension
from asseta.modules.tenancy.models import TenantSettings

REPLAYED_ALERTS = (
    AlertType.GEOFENCE_EXIT,
    AlertType.RESTRICTED_AREA_ENTRY,
    AlertType.UNAUTHORIZED_MOVEMENT,
    AlertType.GPS_ANOMALY,
)


@dataclass(frozen=True)
class _Pos:
    id: uuid.UUID
    event_time: datetime
    speed_kmh: float | None
    ignition: bool | None
    quality: str
    lat: float
    lon: float


@dataclass
class ReplayResult:
    positions: int = 0
    geofence_events: int = 0
    state_events: int = 0
    alerts_confirmed: int = 0
    alerts_superseded: int = 0


class TimelineProcessor:
    def __init__(self, session: Session, tenant_id: uuid.UUID):
        self._s, self._tenant_id = session, tenant_id
        self._policies = PolicyService(session)
        self._alerts = AlertService(session, tenant_id)

    def replay(self, machine_id: uuid.UUID, since: datetime) -> ReplayResult:
        self._s.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))"), {"k": f"timeline:{machine_id}"})
        result = ReplayResult()
        self._s.execute(
            delete(GeofenceEvent).where(GeofenceEvent.machine_id == machine_id, GeofenceEvent.event_time >= since)
        )
        self._s.execute(
            delete(MachineStateEvent).where(
                MachineStateEvent.machine_id == machine_id,
                MachineStateEvent.event_time >= since,
                MachineStateEvent.dimension.in_([StateDimension.ENGINE, StateDimension.MOTION]),
            )
        )
        positions = self._positions(machine_id, since)
        result.positions = len(positions)
        confirmed: set[str] = set()
        result.state_events = self._states(machine_id, since, positions)
        result.geofence_events = self._geofences(machine_id, since, positions, confirmed)
        self._movement_and_anomalies(machine_id, positions, confirmed)
        result.alerts_confirmed = len(confirmed)
        result.alerts_superseded = self._alerts.supersede_unconfirmed(machine_id, REPLAYED_ALERTS, since, confirmed)
        self._s.flush()
        return result

    def _positions(self, machine_id: uuid.UUID, since: datetime) -> list[_Pos]:
        rows = self._s.execute(
            text("""
            SELECT id, event_time, speed_kmh, ignition, quality, ST_Y(location) AS lat, ST_X(location) AS lon
            FROM machine_position_event WHERE machine_id = :m AND event_time >= :since ORDER BY event_time
        """),
            {"m": machine_id, "since": since},
        ).all()
        return [_Pos(r.id, r.event_time, r.speed_kmh, r.ignition, r.quality, r.lat, r.lon) for r in rows]

    def _last_state(self, machine_id: uuid.UUID, dim: StateDimension, before: datetime) -> str | None:
        return self._s.execute(
            select(MachineStateEvent.value)
            .where(
                MachineStateEvent.machine_id == machine_id,
                MachineStateEvent.dimension == dim,
                MachineStateEvent.event_time < before,
            )
            .order_by(MachineStateEvent.event_time.desc())
            .limit(1)
        ).scalar_one_or_none()

    def _states(self, machine_id: uuid.UUID, since: datetime, positions: list[_Pos]) -> int:
        count = 0
        stamp = None
        engine = self._last_state(machine_id, StateDimension.ENGINE, since)
        motion = self._last_state(machine_id, StateDimension.MOTION, since)
        for p in positions:
            if p.quality == PositionQuality.IMPLAUSIBLE_JUMP:
                continue
            eff = self._policies.tracking(self._tenant_id, machine_id, at=p.event_time)
            stamp = eff.version_stamp
            if p.ignition is not None:
                value = "ON" if p.ignition else "OFF"
                if value != engine:
                    count += self._state(machine_id, StateDimension.ENGINE, value, p, stamp)
                    engine = value
            if p.speed_kmh is not None:
                value = "MOVING" if p.speed_kmh >= eff.policy.moving_speed_kmh else "STOPPED"
                if value != motion:
                    count += self._state(machine_id, StateDimension.MOTION, value, p, stamp)
                    motion = value
        return count

    def _state(self, machine_id: uuid.UUID, dim: StateDimension, value: str, p: _Pos, stamp: str) -> int:
        self._s.add(
            MachineStateEvent(
                id=uuid.uuid4(),
                tenant_id=self._tenant_id,
                machine_id=machine_id,
                dimension=dim,
                value=value,
                event_time=p.event_time,
                position_event_id=p.id,
                policy_version=stamp,
            )
        )
        return 1

    def _applicable_geofences(self, machine_id: uuid.UUID) -> list[uuid.UUID]:
        return list(
            self._s.execute(
                text("""
            SELECT g.id FROM geofence g WHERE g.is_active AND (g.applies_to_all_machines OR EXISTS (
              SELECT 1 FROM geofence_machine gm WHERE gm.geofence_id = g.id AND gm.machine_id = :m))
        """),
                {"m": machine_id},
            ).scalars()
        )

    def _geofences(self, machine_id: uuid.UUID, since: datetime, positions: list[_Pos], confirmed: set[str]) -> int:
        fence_ids = self._applicable_geofences(machine_id)
        good = [p for p in positions if p.quality == PositionQuality.GOOD]
        if not fence_ids or not good:
            return 0
        fences = {f.id: f for f in self._s.execute(select(Geofence).where(Geofence.id.in_(fence_ids))).scalars()}
        distances: dict[uuid.UUID, dict[uuid.UUID, float]] = defaultdict(dict)
        for row in self._s.execute(
            text("""
            SELECT p.id AS pid, g.id AS gid, ST_Distance(g.area, p.location::geography) AS d
            FROM machine_position_event p JOIN geofence g ON g.id = ANY(:fences)
            WHERE p.machine_id = :m AND p.event_time >= :since AND p.quality = 'GOOD'
        """),
            {"fences": list(fences), "m": machine_id, "since": since},
        ):
            distances[row.pid][row.gid] = float(row.d)
        count = 0
        for fence in fences.values():
            prior = self._s.execute(
                select(GeofenceEvent.transition)
                .where(
                    GeofenceEvent.machine_id == machine_id,
                    GeofenceEvent.geofence_id == fence.id,
                    GeofenceEvent.event_time < since,
                )
                .order_by(GeofenceEvent.event_time.desc())
                .limit(1)
            ).scalar_one_or_none()
            state = None if prior is None else ("IN" if prior is GeofenceTransition.ENTER else "OUT")
            for p in good:
                eff = self._policies.tracking(self._tenant_id, machine_id, site_id=fence.job_site_id, at=p.event_time)
                d = distances[p.id].get(fence.id)
                if d is None:
                    continue
                observed = "IN" if d <= 0 else ("OUT" if d > eff.policy.geofence_tolerance_m else None)
                if observed is None or observed == state:
                    continue  # inside tolerance band: hysteresis keeps the previous state
                if state is not None or observed == "IN":
                    transition = GeofenceTransition.ENTER if observed == "IN" else GeofenceTransition.EXIT
                    self._s.add(
                        GeofenceEvent(
                            id=uuid.uuid4(),
                            tenant_id=self._tenant_id,
                            machine_id=machine_id,
                            geofence_id=fence.id,
                            transition=transition,
                            event_time=p.event_time,
                            position_event_id=p.id,
                            distance_m=round(d, 2),
                            policy_version=eff.version_stamp,
                        )
                    )
                    count += 1
                    self._geofence_alert(machine_id, fence, transition, p, d, eff.version_stamp, confirmed)
                state = observed
        return count

    def _geofence_alert(
        self,
        machine_id: uuid.UUID,
        fence: Geofence,
        transition: GeofenceTransition,
        p: _Pos,
        distance: float,
        stamp: str,
        confirmed: set[str],
    ) -> None:
        if fence.kind is GeofenceKind.ALLOWED_AREA and transition is GeofenceTransition.EXIT:
            alert_type, title = AlertType.GEOFENCE_EXIT, f"Left allowed area '{fence.name}'"
        elif fence.kind is GeofenceKind.RESTRICTED_AREA and transition is GeofenceTransition.ENTER:
            alert_type, title = AlertType.RESTRICTED_AREA_ENTRY, f"Entered restricted area '{fence.name}'"
        else:
            return
        key = f"{alert_type.value}:{machine_id}:{fence.id}:{p.event_time.isoformat()}"
        confirmed.add(key)
        self._alerts.raise_alert(
            alert_type=alert_type,
            severity=AlertSeverity.WARNING,
            event_time=p.event_time,
            dedupe_key=key,
            title=title,
            machine_id=machine_id,
            policy_version=stamp,
            evidence={
                "geofence_id": str(fence.id),
                "position_event_id": str(p.id),
                "distance_outside_m": round(distance, 2),
                "lat": p.lat,
                "lon": p.lon,
                "event_time": p.event_time.isoformat(),
            },
        )

    def _movement_and_anomalies(self, machine_id: uuid.UUID, positions: list[_Pos], confirmed: set[str]) -> None:
        settings = self._s.get(TenantSettings, self._tenant_id)
        tz = ZoneInfo(settings.timezone if settings else "UTC")
        flagged_days: set[str] = set()
        for p in positions:
            eff = self._policies.tracking(self._tenant_id, machine_id, at=p.event_time)
            if p.quality == PositionQuality.IMPLAUSIBLE_JUMP:
                key = f"GPS_ANOMALY:{machine_id}:{p.event_time.isoformat()}"
                confirmed.add(key)
                self._alerts.raise_alert(
                    alert_type=AlertType.GPS_ANOMALY,
                    severity=AlertSeverity.WARNING,
                    event_time=p.event_time,
                    dedupe_key=key,
                    title="Implausible GPS jump",
                    machine_id=machine_id,
                    policy_version=eff.version_stamp,
                    evidence={
                        "position_event_id": str(p.id),
                        "lat": p.lat,
                        "lon": p.lon,
                        "max_plausible_speed_kmh": eff.policy.max_plausible_speed_kmh,
                    },
                )
                continue
            moving = p.speed_kmh is not None and p.speed_kmh >= eff.policy.moving_speed_kmh
            local = p.event_time.astimezone(tz)
            if not moving or eff.policy.within_operating_window(local):
                continue
            key = f"UNAUTHORIZED_MOVEMENT:{machine_id}:{local.date().isoformat()}"
            confirmed.add(key)
            if key in flagged_days:
                continue
            flagged_days.add(key)
            self._alerts.raise_alert(
                alert_type=AlertType.UNAUTHORIZED_MOVEMENT,
                severity=AlertSeverity.CRITICAL,
                event_time=p.event_time,
                dedupe_key=key,
                title="Movement outside approved operating window",
                machine_id=machine_id,
                policy_version=eff.version_stamp,
                evidence={
                    "position_event_id": str(p.id),
                    "speed_kmh": p.speed_kmh,
                    "local_time": local.isoformat(),
                    "lat": p.lat,
                    "lon": p.lon,
                },
            )


def replay_window_start(event_time: datetime) -> datetime:
    """Replays start one microsecond before the event so the event itself is included."""
    return event_time - timedelta(microseconds=1)
