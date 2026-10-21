"""Telemetry ingestion: authenticate gateway -> parse -> resolve tracker/machine *at event time* -> validate ->
store raw + normalized (tenant RLS scope) -> latest position -> capability verification -> outbox for timeline.

Nothing is silently dropped: unparseable/unresolvable/unauthorized messages are stored QUARANTINED with a reason.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from geoalchemy2.functions import ST_DistanceSphere, ST_MakePoint, ST_SetSRID
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from asseta.core.db import DbScope, apply_scope
from asseta.core.outbox import OutboxWriter
from asseta.modules.geospatial.alerts import AlertService
from asseta.modules.geospatial.models import AlertSeverity, AlertType
from asseta.modules.platform_billing.models_ledger import SubscriptionAssetEnrollment
from asseta.modules.platform_billing.repository import active_on
from asseta.modules.policy.schemas import TrackingPolicy
from asseta.modules.policy.service import PolicyService
from asseta.modules.telemetry.models import (
    IngestionStatus,
    MachineLatestPosition,
    MachinePositionEvent,
    PositionQuality,
    QuarantineReason,
    TrackerIngestionEvent,
)
from asseta.modules.telemetry.observation import InvalidPayload, TelemetryAdapter, TelemetryObservation
from asseta.modules.tracker.models import (
    ProvisioningState,
    Tracker,
    TrackerAssignment,
    TrackerCapability,
)

TIMELINE_TOPIC = "asseta.telemetry.position"


@dataclass(frozen=True)
class Outcome:
    status: IngestionStatus
    reason: QuarantineReason | None = None
    machine_id: uuid.UUID | None = None
    position_event_id: uuid.UUID | None = None


def _point(lat: float, lon: float) -> Any:
    return ST_SetSRID(ST_MakePoint(lon, lat), 4326)


class IngestionService:
    def __init__(self, session: Session, adapter: TelemetryAdapter, gateway_id: uuid.UUID | None, now: datetime):
        self._s, self._adapter, self._gateway_id, self._now = session, adapter, gateway_id, now

    def ingest(self, payload: Any) -> list[Outcome]:
        apply_scope(self._s, DbScope.SYSTEM, None, None)  # device resolution precedes knowing the tenant
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
        try:
            observations = self._adapter.parse(payload)
        except InvalidPayload as exc:
            self._record(
                payload,
                digest,
                None,
                None,
                None,
                IngestionStatus.QUARANTINED,
                QuarantineReason.MALFORMED,
                str(exc),
                self._adapter.device_id_hint(payload),
            )
            return [Outcome(IngestionStatus.QUARANTINED, QuarantineReason.MALFORMED)]
        return [self._one(obs, payload, digest) for obs in observations]

    # --- internals ----------------------------------------------------------------------------------
    def _record(
        self,
        payload: Any,
        digest: str,
        obs: TelemetryObservation | None,
        tracker: Tracker | None,
        machine_id: uuid.UUID | None,
        status: IngestionStatus,
        reason: QuarantineReason | None,
        detail: str | None,
        device_hint: str | None = None,
    ) -> uuid.UUID:
        row = TrackerIngestionEvent(
            id=uuid.uuid4(),
            received_at=self._now,
            gateway_id=self._gateway_id,
            adapter=self._adapter.kind.value,
            external_device_id=obs.external_device_id if obs else device_hint,
            tenant_id=tracker.tenant_id if tracker else None,
            tracker_id=tracker.id if tracker else None,
            machine_id=machine_id,
            event_time=obs.event_time if obs else None,
            payload=payload,
            payload_sha256=digest,
            status=status,
            quarantine_reason=reason,
            detail=detail,
        )
        self._s.add(row)
        self._s.flush()
        return row.id

    def _assignment_at(self, tracker_id: uuid.UUID, at: datetime) -> TrackerAssignment | None:
        return self._s.execute(
            select(TrackerAssignment)
            .where(
                TrackerAssignment.tracker_id == tracker_id,
                TrackerAssignment.effective_from <= at,
                or_(TrackerAssignment.effective_to.is_(None), TrackerAssignment.effective_to > at),
            )
            .order_by(TrackerAssignment.is_primary.desc())
            .limit(1)
        ).scalar_one_or_none()

    def _quarantine(
        self,
        payload: Any,
        digest: str,
        obs: TelemetryObservation,
        tracker: Tracker | None,
        reason: QuarantineReason,
        detail: str,
        machine_id: uuid.UUID | None = None,
    ) -> Outcome:
        self._record(payload, digest, obs, tracker, machine_id, IngestionStatus.QUARANTINED, reason, detail)
        return Outcome(IngestionStatus.QUARANTINED, reason, machine_id)

    def _one(self, obs: TelemetryObservation, payload: Any, digest: str) -> Outcome:
        tracker = self._s.execute(
            select(Tracker).where(Tracker.adapter == obs.adapter, Tracker.external_id == obs.external_device_id)
        ).scalar_one_or_none()
        if tracker is None:
            return self._quarantine(
                payload,
                digest,
                obs,
                None,
                QuarantineReason.UNKNOWN_DEVICE,
                "Device identity not registered to any tenant",
            )
        apply_scope(self._s, DbScope.TENANT, tracker.tenant_id, None)  # all further work is tenant-confined
        if tracker.provisioning_state in (ProvisioningState.SUSPENDED, ProvisioningState.RETIRED):
            return self._quarantine(
                payload,
                digest,
                obs,
                tracker,
                QuarantineReason.TRACKER_INACTIVE,
                f"Tracker {tracker.provisioning_state.value}",
            )
        assignment = self._assignment_at(tracker.id, obs.event_time)  # late data attaches by event time
        if assignment is None:
            return self._quarantine(
                payload, digest, obs, tracker, QuarantineReason.UNASSIGNED, "No machine assignment at event time"
            )
        machine_id = assignment.machine_id
        eff = PolicyService(self._s).tracking(tracker.tenant_id, machine_id, at=obs.event_time)
        policy = eff.policy
        if obs.event_time > self._now + timedelta(seconds=policy.future_timestamp_tolerance_seconds):
            return self._quarantine(
                payload,
                digest,
                obs,
                tracker,
                QuarantineReason.CLOCK_FUTURE,
                "Event time ahead of server clock",
                machine_id,
            )
        if obs.event_time < self._now - timedelta(days=policy.max_replay_age_days):
            return self._quarantine(
                payload, digest, obs, tracker, QuarantineReason.TOO_OLD, "Event older than replay window", machine_id
            )
        enrolled = self._s.execute(
            select(SubscriptionAssetEnrollment.id).where(
                SubscriptionAssetEnrollment.machine_id == machine_id, active_on(obs.event_time.date())
            )
        ).first()
        if enrolled is None:
            return self._quarantine(
                payload,
                digest,
                obs,
                tracker,
                QuarantineReason.NOT_ENROLLED,
                "Machine not an enrolled billable asset at event time (DEC-014)",
                machine_id,
            )

        self._verify_reporting(tracker, obs)
        self._immediate_alerts(tracker, machine_id, obs, policy, eff.version_stamp)
        if not obs.valid_fix or obs.latitude is None or obs.longitude is None:
            self._record(payload, digest, obs, tracker, machine_id, IngestionStatus.ACCEPTED_NO_FIX, None, None)
            self._touch_latest(machine_id)
            return Outcome(IngestionStatus.ACCEPTED_NO_FIX, None, machine_id)

        ingestion_id = self._record(payload, digest, obs, tracker, machine_id, IngestionStatus.ACCEPTED, None, None)
        latest = self._s.get(MachineLatestPosition, machine_id)
        is_late = latest is not None and obs.event_time < latest.event_time
        quality = self._quality(machine_id, obs, policy)
        position_id = self._s.execute(
            insert(MachinePositionEvent)
            .values(
                id=uuid.uuid4(),
                event_time=obs.event_time,
                received_at=self._now,
                tenant_id=tracker.tenant_id,
                machine_id=machine_id,
                tracker_id=tracker.id,
                ingestion_event_id=ingestion_id,
                location=_point(obs.latitude, obs.longitude),
                accuracy_m=obs.accuracy_m,
                altitude_m=obs.altitude_m,
                speed_kmh=obs.speed_kmh,
                heading_deg=obs.heading_deg,
                satellites=obs.satellites,
                ignition=obs.ignition,
                motion=obs.motion,
                engine_hours=obs.engine_hours,
                external_power_v=obs.external_power_v,
                battery_level_pct=obs.battery_level_pct,
                tamper=obs.tamper,
                odometer_km=obs.odometer_km,
                quality=quality,
                is_late=is_late,
                clock_offset_seconds=(self._now - obs.event_time).total_seconds(),
                policy_version=eff.version_stamp,
            )
            .on_conflict_do_nothing(constraint="uq_position_tracker_time")
            .returning(MachinePositionEvent.id)
        ).scalar_one_or_none()
        if position_id is None:
            self._s.execute(
                update(TrackerIngestionEvent)
                .where(
                    TrackerIngestionEvent.id == ingestion_id,
                    TrackerIngestionEvent.received_at == self._now,
                )
                .values(status=IngestionStatus.DUPLICATE, detail="Same tracker and event time already stored")
            )
            self._touch_latest(machine_id)
            return Outcome(IngestionStatus.DUPLICATE, None, machine_id)
        if quality is not PositionQuality.IMPLAUSIBLE_JUMP:
            self._upsert_latest(machine_id, tracker, position_id, obs, quality)
        else:
            self._touch_latest(machine_id)
        OutboxWriter(self._s).emit(
            topic=TIMELINE_TOPIC,
            event_type="PositionStored",
            key=str(machine_id),
            payload={
                "machine_id": str(machine_id),
                "tenant_id": str(tracker.tenant_id),
                "event_time": obs.event_time.isoformat(),
                "late": is_late,
                "position_event_id": str(position_id),
            },
            tenant_id=tracker.tenant_id,
        )
        return Outcome(IngestionStatus.ACCEPTED, None, machine_id, position_id)

    def _quality(self, machine_id: uuid.UUID, obs: TelemetryObservation, policy: TrackingPolicy) -> PositionQuality:
        assert obs.latitude is not None and obs.longitude is not None
        if obs.accuracy_m is not None and obs.accuracy_m > policy.max_position_accuracy_m:
            return PositionQuality.LOW_ACCURACY
        point = _point(obs.latitude, obs.longitude)
        P = MachinePositionEvent  # noqa: N806
        neighbours = [
            select(P.event_time, ST_DistanceSphere(P.location, point).label("d"))
            .where(P.machine_id == machine_id, cond, P.quality != PositionQuality.IMPLAUSIBLE_JUMP)
            .order_by(order)
            .limit(1)
            for cond, order in (
                (P.event_time < obs.event_time, P.event_time.desc()),
                (P.event_time > obs.event_time, P.event_time.asc()),
            )
        ]
        for stmt in neighbours:
            row = self._s.execute(stmt).first()
            if row is None:
                continue
            seconds = abs((obs.event_time - row[0]).total_seconds())
            if seconds > 0 and (row[1] / 1000) / (seconds / 3600) > policy.max_plausible_speed_kmh:
                return PositionQuality.IMPLAUSIBLE_JUMP
        return PositionQuality.GOOD

    def _upsert_latest(
        self,
        machine_id: uuid.UUID,
        tracker: Tracker,
        position_id: uuid.UUID,
        obs: TelemetryObservation,
        quality: PositionQuality,
    ) -> None:
        assert obs.latitude is not None and obs.longitude is not None
        values = {
            "machine_id": machine_id,
            "tenant_id": tracker.tenant_id,
            "tracker_id": tracker.id,
            "position_event_id": position_id,
            "event_time": obs.event_time,
            "received_at": self._now,
            "location": _point(obs.latitude, obs.longitude),
            "accuracy_m": obs.accuracy_m,
            "speed_kmh": obs.speed_kmh,
            "heading_deg": obs.heading_deg,
            "ignition": obs.ignition,
            "quality": quality.value,
            "last_message_at": self._now,
            "external_power_v": obs.external_power_v,
            "updated_at": self._now,
        }
        stmt = insert(MachineLatestPosition).values(**values)
        newer = {k: stmt.excluded[k] for k in values if k not in ("machine_id", "tenant_id")}
        self._s.execute(
            stmt.on_conflict_do_update(
                index_elements=[MachineLatestPosition.machine_id],
                set_=newer,
                where=MachineLatestPosition.event_time < stmt.excluded.event_time,
            )
        )
        self._touch_latest(machine_id)  # late data still proves the tracker is communicating

    def _touch_latest(self, machine_id: uuid.UUID) -> None:
        self._s.execute(
            update(MachineLatestPosition)
            .where(MachineLatestPosition.machine_id == machine_id)
            .values(last_message_at=func.greatest(MachineLatestPosition.last_message_at, self._now))
        )

    def _verify_reporting(self, tracker: Tracker, obs: TelemetryObservation) -> None:
        if tracker.provisioning_state is ProvisioningState.REGISTERED:
            tracker.provisioning_state = ProvisioningState.VERIFIED_REPORTING
        tracker.first_report_at = tracker.first_report_at or self._now
        tracker.last_report_at = max(tracker.last_report_at or self._now, self._now)
        caps = [c.value for c in obs.observed_capabilities()]
        if caps:
            self._s.execute(
                update(TrackerCapability)
                .where(and_(TrackerCapability.tracker_id == tracker.id, TrackerCapability.capability.in_(caps)))
                .values(verified_at=func.coalesce(TrackerCapability.verified_at, self._now), last_observed_at=self._now)
            )

    def _immediate_alerts(
        self, tracker: Tracker, machine_id: uuid.UUID, obs: TelemetryObservation, policy: TrackingPolicy, stamp: str
    ) -> None:
        alerts = AlertService(self._s, tracker.tenant_id)
        ts = obs.event_time.isoformat()
        if obs.tamper:
            alerts.raise_alert(
                alert_type=AlertType.TAMPER,
                severity=AlertSeverity.CRITICAL,
                event_time=obs.event_time,
                dedupe_key=f"TAMPER:{tracker.id}:{ts}",
                title="Tracker tamper alarm",
                evidence={"tracker_id": str(tracker.id), "event_time": ts},
                machine_id=machine_id,
                tracker_id=tracker.id,
                policy_version=stamp,
            )
        if (
            policy.low_power_voltage is not None
            and obs.external_power_v is not None
            and obs.external_power_v < policy.low_power_voltage
        ):
            alerts.raise_alert(
                alert_type=AlertType.LOW_POWER,
                severity=AlertSeverity.WARNING,
                event_time=obs.event_time,
                dedupe_key=f"LOW_POWER:{tracker.id}:{obs.event_time.date()}",
                title="Tracker external power low",
                evidence={"voltage": obs.external_power_v, "threshold": policy.low_power_voltage, "event_time": ts},
                machine_id=machine_id,
                tracker_id=tracker.id,
                policy_version=stamp,
            )
