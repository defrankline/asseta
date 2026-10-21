"""Connectivity sweep: tracker staleness/offline transitions, alerts and auto-resolution.

Offline hardware never changes billing or enrollment (prompt.md §1.2) — this only records evidence and alerts.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from asseta.modules.geospatial.alerts import AlertService
from asseta.modules.geospatial.fleet_map import Connectivity, connectivity_for
from asseta.modules.geospatial.models import AlertSeverity, AlertType
from asseta.modules.policy.service import PolicyService
from asseta.modules.telemetry.models import MachineStateEvent, StateDimension

_ALERTING = {
    Connectivity.STALE: (AlertType.TRACKER_STALE, AlertSeverity.WARNING),
    Connectivity.OFFLINE: (AlertType.TRACKER_OFFLINE, AlertSeverity.CRITICAL),
}


@dataclass
class SweepResult:
    machines: int = 0
    transitions: int = 0
    alerts_raised: int = 0
    alerts_resolved: int = 0


def sweep_tenant(session: Session, tenant_id: uuid.UUID, now: datetime) -> SweepResult:
    result = SweepResult()
    policies, alerts = PolicyService(session), AlertService(session, tenant_id)
    rows = session.execute(
        text("""
        SELECT ta.machine_id, ta.tracker_id, ta.effective_from, lp.last_message_at
        FROM tracker_assignment ta LEFT JOIN machine_latest_position lp ON lp.machine_id = ta.machine_id
        WHERE ta.is_primary AND ta.effective_to IS NULL""")
    ).all()
    for r in rows:
        result.machines += 1
        eff = policies.tracking(tenant_id, r.machine_id, at=now)
        reference = r.last_message_at or r.effective_from  # never-reported trackers age from installation
        state = connectivity_for(eff.policy, (now - reference).total_seconds(), True)
        if r.last_message_at is None and state in (Connectivity.LIVE, Connectivity.RECENT):
            state = Connectivity.NEVER_REPORTED
        previous = session.execute(
            select(MachineStateEvent.value)
            .where(
                MachineStateEvent.machine_id == r.machine_id, MachineStateEvent.dimension == StateDimension.CONNECTIVITY
            )
            .order_by(MachineStateEvent.event_time.desc())
            .limit(1)
        ).scalar_one_or_none()
        if previous == state.value:
            continue
        session.add(
            MachineStateEvent(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                machine_id=r.machine_id,
                dimension=StateDimension.CONNECTIVITY,
                value=state.value,
                event_time=now,
                policy_version=eff.version_stamp,
            )
        )
        result.transitions += 1
        if state in _ALERTING:
            alert_type, severity = _ALERTING[state]
            alerts.raise_alert(
                alert_type=alert_type,
                severity=severity,
                event_time=now,
                dedupe_key=f"{alert_type.value}:{r.machine_id}:{reference.isoformat()}",
                title=f"Tracker {state.value.lower()} — no data since {reference.isoformat(timespec='minutes')}",
                evidence={
                    "last_message_at": r.last_message_at.isoformat() if r.last_message_at else None,
                    "tracker_id": str(r.tracker_id),
                    "thresholds_s": [eff.policy.stale_after_seconds, eff.policy.offline_after_seconds],
                },
                machine_id=r.machine_id,
                tracker_id=r.tracker_id,
                policy_version=eff.version_stamp,
            )
            result.alerts_raised += 1
        elif state in (Connectivity.LIVE, Connectivity.RECENT):
            result.alerts_resolved += alerts.resolve_open(
                r.machine_id, [AlertType.TRACKER_STALE, AlertType.TRACKER_OFFLINE], "Tracker reporting again"
            )
    session.flush()
    return result
