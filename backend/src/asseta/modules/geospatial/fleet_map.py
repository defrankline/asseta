"""Fleet command map, proximity and history (R1-D). Status dimensions are independent and evidence-gated:
UNKNOWN whenever evidence is insufficient; stale data is labelled last-known, never live."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from asseta.core.search import matches
from asseta.modules.jobs.work_state import ReportedWorkState, reported_work_states
from asseta.modules.policy.schemas import TrackingPolicy
from asseta.modules.policy.service import PolicyService


class Connectivity(StrEnum):
    LIVE = "LIVE"
    RECENT = "RECENT"
    STALE = "STALE"
    OFFLINE = "OFFLINE"
    NEVER_REPORTED = "NEVER_REPORTED"
    NO_TRACKER = "NO_TRACKER"


class Observed(StrEnum):
    ON = "ON"
    OFF = "OFF"
    MOVING = "MOVING"
    STATIONARY = "STATIONARY"
    UNKNOWN = "UNKNOWN"


class Compliance(StrEnum):
    COMPLIANT = "COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    UNKNOWN = "UNKNOWN"


class MachineMapDto(BaseModel):
    machine_id: uuid.UUID
    asset_code: str
    name: str
    machine_status: str
    longitude: float | None
    latitude: float | None
    accuracy_m: float | None
    position_time: datetime | None
    last_message_at: datetime | None
    last_seen_age_seconds: int | None
    position_source: str | None  # e.g. "TRACKER:<label>"
    position_quality: str | None
    connectivity: Connectivity
    is_live: bool
    reported_work_status: str  # supervisor reports (jobs/work logs, `ReportedWorkState`) — never inferred from GPS
    observed_engine: Observed
    observed_motion: Observed
    location_compliance: Compliance
    tracker_id: uuid.UUID | None
    tracker_state: str | None
    supervisor: str | None
    operator: str | None
    open_alerts: int
    policy_version: str


def connectivity_for(policy: TrackingPolicy, age_seconds: float | None, has_tracker: bool) -> Connectivity:
    if not has_tracker:
        return Connectivity.NO_TRACKER
    if age_seconds is None:
        return Connectivity.NEVER_REPORTED
    if age_seconds <= policy.live_max_age_seconds:
        return Connectivity.LIVE
    if age_seconds <= policy.stale_after_seconds:
        return Connectivity.RECENT
    if age_seconds <= policy.offline_after_seconds:
        return Connectivity.STALE
    return Connectivity.OFFLINE


_FLEET_SQL = text("""
SELECT m.id, m.asset_code, m.name, m.status,
       ST_X(lp.location) AS lon, ST_Y(lp.location) AS lat, lp.accuracy_m, lp.event_time, lp.last_message_at,
       lp.speed_kmh, lp.ignition, lp.quality,
       t.id AS tracker_id, t.label AS tracker_label, t.provisioning_state,
       (SELECT verified_at IS NOT NULL FROM tracker_capability c
         WHERE c.tracker_id = t.id AND c.capability = 'IGNITION') AS ignition_verified,
       (SELECT s.full_name FROM machine_assignment a JOIN staff_member s ON s.id = a.staff_member_id
         WHERE a.machine_id = m.id AND a.role = 'SUPERVISOR' AND a.effective_from <= :now
           AND (a.effective_to IS NULL OR a.effective_to > :now) LIMIT 1) AS supervisor,
       (SELECT s.full_name FROM machine_assignment a JOIN staff_member s ON s.id = a.staff_member_id
         WHERE a.machine_id = m.id AND a.role = 'OPERATOR' AND a.effective_from <= :now
           AND (a.effective_to IS NULL OR a.effective_to > :now) LIMIT 1) AS operator,
       (SELECT count(*) FROM tracking_alert al WHERE al.machine_id = m.id AND al.status = 'OPEN') AS open_alerts,
       (SELECT bool_or(ST_Distance(g.area, lp.location::geography) <= :tol) FROM geofence g
         WHERE g.is_active AND g.kind = 'ALLOWED_AREA' AND (g.applies_to_all_machines OR EXISTS (
           SELECT 1 FROM geofence_machine gm WHERE gm.geofence_id = g.id AND gm.machine_id = m.id))) AS in_allowed,
       (SELECT bool_or(ST_Covers(g.area, lp.location::geography)) FROM geofence g
         WHERE g.is_active AND g.kind = 'RESTRICTED_AREA' AND (g.applies_to_all_machines OR EXISTS (
           SELECT 1 FROM geofence_machine gm WHERE gm.geofence_id = g.id AND gm.machine_id = m.id))) AS in_restricted
FROM machine m
LEFT JOIN machine_latest_position lp ON lp.machine_id = m.id
LEFT JOIN tracker_assignment ta ON ta.machine_id = m.id AND ta.is_primary AND ta.effective_to IS NULL
LEFT JOIN tracker t ON t.id = ta.tracker_id
WHERE m.status <> 'DISPOSED' AND (CAST(:machine AS uuid) IS NULL OR m.id = CAST(:machine AS uuid))
ORDER BY m.asset_code
""")


class FleetMapService:
    def __init__(self, session: Session, tenant_id: uuid.UUID):
        self._s, self._tenant_id = session, tenant_id
        self._policies = PolicyService(session)

    def fleet(self, now: datetime, machine_id: uuid.UUID | None = None) -> list[MachineMapDto]:
        tenant_policy = self._policies.tracking(self._tenant_id, at=now).policy
        rows = self._s.execute(
            _FLEET_SQL,
            {"now": now, "tol": tenant_policy.geofence_tolerance_m, "machine": str(machine_id) if machine_id else None},
        ).all()
        work = reported_work_states(self._s, now)
        return [self._row(r, now, work.get(r.id, ReportedWorkState.NO_ACTIVE_JOB)) for r in rows]

    def _row(self, r: Any, now: datetime, work: ReportedWorkState) -> MachineMapDto:
        eff = self._policies.tracking(self._tenant_id, r.id, at=now)
        policy = eff.policy
        msg_age = (now - r.last_message_at).total_seconds() if r.last_message_at else None
        conn = connectivity_for(policy, msg_age, r.tracker_id is not None)
        pos_age = (now - r.event_time).total_seconds() if r.event_time else None
        fresh_position = pos_age is not None and pos_age <= policy.stale_after_seconds
        engine = Observed.UNKNOWN
        if r.ignition_verified and r.ignition is not None and fresh_position:
            engine = Observed.ON if r.ignition else Observed.OFF
        motion = Observed.UNKNOWN
        if fresh_position and r.speed_kmh is not None:
            motion = Observed.MOVING if r.speed_kmh >= policy.moving_speed_kmh else Observed.STATIONARY
        compliance = Compliance.UNKNOWN
        if r.event_time is not None and r.quality == "GOOD" and fresh_position:
            if r.in_restricted:
                compliance = Compliance.NON_COMPLIANT
            elif r.in_allowed is not None:
                compliance = Compliance.COMPLIANT if r.in_allowed else Compliance.NON_COMPLIANT
        return MachineMapDto(
            machine_id=r.id,
            asset_code=r.asset_code,
            name=r.name,
            machine_status=r.status,
            longitude=r.lon,
            latitude=r.lat,
            accuracy_m=r.accuracy_m,
            position_time=r.event_time,
            last_message_at=r.last_message_at,
            last_seen_age_seconds=int(msg_age) if msg_age is not None else None,
            position_source=f"TRACKER:{r.tracker_label}" if r.event_time and r.tracker_label else None,
            position_quality=r.quality,
            connectivity=conn,
            is_live=conn is Connectivity.LIVE and pos_age is not None and pos_age <= policy.live_max_age_seconds,
            reported_work_status=work.value,
            observed_engine=engine,
            observed_motion=motion,
            location_compliance=compliance,
            tracker_id=r.tracker_id,
            tracker_state=r.provisioning_state,
            supervisor=r.supervisor,
            operator=r.operator,
            open_alerts=int(r.open_alerts or 0),
            policy_version=eff.version_stamp,
        )


def filter_fleet(
    rows: list[MachineMapDto],
    q: str | None = None,
    connectivity: Connectivity | None = None,
    machine_status: str | None = None,
) -> list[MachineMapDto]:
    """Optional filters shared by the fleet map endpoint and the fleet report (same rows, same order)."""
    return [
        r
        for r in rows
        if matches(q, r.asset_code, r.name)
        and (connectivity is None or r.connectivity is connectivity)
        and (machine_status is None or r.machine_status == machine_status)
    ]
