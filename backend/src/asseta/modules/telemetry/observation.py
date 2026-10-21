"""Vendor-neutral telemetry contract. Adapters turn gateway/vendor payloads into `TelemetryObservation`s;
downstream modules (ingestion, geospatial, fraud) depend only on this type."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol

from asseta.modules.tracker.models import Capability, TelemetryAdapterKind


class InvalidPayload(ValueError):
    """Payload cannot be interpreted; stored raw and quarantined, never silently dropped."""


@dataclass(frozen=True)
class TelemetryObservation:
    adapter: TelemetryAdapterKind
    external_device_id: str
    event_time: datetime  # device fix time (UTC) — the time the observation describes
    valid_fix: bool
    latitude: float | None = None
    longitude: float | None = None
    accuracy_m: float | None = None
    altitude_m: float | None = None
    speed_kmh: float | None = None
    heading_deg: float | None = None
    satellites: int | None = None
    ignition: bool | None = None
    engine_hours: Decimal | None = None
    fuel_level: float | None = None
    external_power_v: float | None = None
    battery_level_pct: float | None = None
    tamper: bool | None = None
    motion: bool | None = None
    odometer_km: Decimal | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def observed_capabilities(self) -> set[Capability]:
        """Capabilities proven by *this* message (used to verify declared capabilities)."""
        checks = {
            Capability.GNSS: self.valid_fix and self.latitude is not None,
            Capability.ACCURACY: self.accuracy_m is not None,
            Capability.IGNITION: self.ignition is not None,
            Capability.ENGINE_HOURS: self.engine_hours is not None,
            Capability.FUEL_LEVEL: self.fuel_level is not None,
            Capability.EXTERNAL_POWER: self.external_power_v is not None,
            Capability.BATTERY: self.battery_level_pct is not None,
            Capability.TAMPER: self.tamper is not None,
            Capability.MOTION: self.motion is not None,
            Capability.ODOMETER: self.odometer_km is not None,
        }
        return {cap for cap, present in checks.items() if present}


class TelemetryAdapter(Protocol):
    kind: TelemetryAdapterKind

    def parse(self, payload: Any) -> list[TelemetryObservation]: ...

    def device_id_hint(self, payload: Any) -> str | None:
        """Best-effort device identity for quarantine records of unparseable payloads."""
        ...
