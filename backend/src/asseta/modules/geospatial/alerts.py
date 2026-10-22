"""Tracking alerts: idempotent raise (dedupe key), auto-resolve, and supersede-on-replay (never delete)."""

import uuid
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from sqlalchemy import Select, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from asseta.core.db import utcnow
from asseta.core.outbox import OutboxWriter
from asseta.modules.geospatial.models import AlertSeverity, AlertStatus, AlertType, TrackingAlert


def alert_list_query(
    status: AlertStatus | None = None,
    alert_type: AlertType | None = None,
    machine_id: uuid.UUID | None = None,
    severity: AlertSeverity | None = None,
) -> Select[TrackingAlert]:
    """The alert list (newest first) shared by the alerts endpoint and the alerts report."""
    stmt = select(TrackingAlert).order_by(TrackingAlert.event_time.desc(), TrackingAlert.id)
    if status:
        stmt = stmt.where(TrackingAlert.status == status)
    if alert_type:
        stmt = stmt.where(TrackingAlert.alert_type == alert_type)
    if machine_id:
        stmt = stmt.where(TrackingAlert.machine_id == machine_id)
    if severity:
        stmt = stmt.where(TrackingAlert.severity == severity)
    return stmt


class AlertService:
    def __init__(self, session: Session, tenant_id: uuid.UUID):
        self._s, self._tenant_id = session, tenant_id

    def raise_alert(
        self,
        *,
        alert_type: AlertType,
        severity: AlertSeverity,
        event_time: datetime,
        dedupe_key: str,
        title: str,
        evidence: dict[str, Any],
        machine_id: uuid.UUID | None = None,
        tracker_id: uuid.UUID | None = None,
        policy_version: str | None = None,
    ) -> uuid.UUID:
        """Same dedupe key => same alert. A superseded alert re-confirmed by evidence is re-opened."""
        base = insert(TrackingAlert).values(
            id=uuid.uuid4(),
            tenant_id=self._tenant_id,
            machine_id=machine_id,
            tracker_id=tracker_id,
            alert_type=alert_type,
            severity=severity,
            status=AlertStatus.OPEN,
            event_time=event_time,
            dedupe_key=dedupe_key,
            title=title,
            evidence=evidence,
            policy_version=policy_version,
            created_at=utcnow(),
        )
        stmt = base.on_conflict_do_update(
            constraint="uq_tracking_alert_dedupe",
            set_={
                "status": AlertStatus.OPEN,
                "evidence": base.excluded.evidence,
                "policy_version": base.excluded.policy_version,
            },
            where=TrackingAlert.status == AlertStatus.SUPERSEDED,
        ).returning(TrackingAlert.id, TrackingAlert.status)
        row = self._s.execute(stmt).first()
        if row is not None:  # inserted or re-opened -> notify downstream (notification module, later gate)
            OutboxWriter(self._s).emit(
                topic="asseta.tracking.alert",
                event_type="TrackingAlertRaised",
                key=str(machine_id or self._tenant_id),
                payload={
                    "alert_id": str(row[0]),
                    "type": alert_type.value,
                    "severity": severity.value,
                    "machine_id": str(machine_id),
                    "event_time": event_time.isoformat(),
                },
                tenant_id=self._tenant_id,
            )
            return uuid.UUID(str(row[0]))
        existing = self._s.execute(
            select(TrackingAlert.id).where(
                TrackingAlert.tenant_id == self._tenant_id, TrackingAlert.dedupe_key == dedupe_key
            )
        ).scalar_one()
        return existing

    def resolve_open(self, machine_id: uuid.UUID, alert_types: Iterable[AlertType], note: str) -> int:
        result = self._s.execute(
            update(TrackingAlert)
            .where(
                TrackingAlert.machine_id == machine_id,
                TrackingAlert.alert_type.in_(list(alert_types)),
                TrackingAlert.status.in_([AlertStatus.OPEN, AlertStatus.ACKNOWLEDGED]),
            )
            .values(status=AlertStatus.RESOLVED, resolved_at=utcnow(), resolution_note=note)
            .returning(TrackingAlert.id)
        )
        return len(result.scalars().all())

    def supersede_unconfirmed(
        self, machine_id: uuid.UUID, alert_types: Iterable[AlertType], since: datetime, confirmed_keys: set[str]
    ) -> int:
        """After a replay from `since`, OPEN alerts not reproduced by the new evidence become SUPERSEDED."""
        stmt = update(TrackingAlert).where(
            TrackingAlert.machine_id == machine_id,
            TrackingAlert.alert_type.in_(list(alert_types)),
            TrackingAlert.event_time >= since,
            TrackingAlert.status == AlertStatus.OPEN,
        )
        if confirmed_keys:
            stmt = stmt.where(TrackingAlert.dedupe_key.not_in(confirmed_keys))
        result = self._s.execute(
            stmt.values(
                status=AlertStatus.SUPERSEDED, resolution_note="Superseded by late/replayed telemetry"
            ).returning(TrackingAlert.id)
        )
        return len(result.scalars().all())
