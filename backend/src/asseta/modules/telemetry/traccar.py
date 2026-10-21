"""Traccar gateway adapter (first supported gateway, DEC-003).

Consumes Traccar's position forwarding JSON (`forward.enable=true`, `forward.json=true`):
`{"position": {...}, "device": {"uniqueId": ...}}`. Units: speed in knots, `hours` attribute in milliseconds.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from asseta.modules.telemetry.observation import InvalidPayload, TelemetryObservation
from asseta.modules.tracker.models import TelemetryAdapterKind

KNOTS_TO_KMH = 1.852
_KNOWN = {"ignition", "hours", "fuel", "power", "batteryLevel", "alarm", "motion", "totalDistance", "odometer", "sat"}


def _float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _time(value: Any) -> datetime:
    if not isinstance(value, str):
        raise InvalidPayload("fixTime missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvalidPayload("fixTime not ISO-8601") from exc
    if parsed.tzinfo is None:
        raise InvalidPayload("fixTime without timezone")
    return parsed.astimezone(UTC)


class TraccarAdapter:
    kind = TelemetryAdapterKind.TRACCAR

    def device_id_hint(self, payload: Any) -> str | None:
        if isinstance(payload, dict) and isinstance(payload.get("device"), dict):
            unique = payload["device"].get("uniqueId")
            return str(unique)[:100] if unique else None
        return None

    def parse(self, payload: Any) -> list[TelemetryObservation]:
        if not isinstance(payload, dict) or not isinstance(payload.get("position"), dict):
            raise InvalidPayload("expected object with 'position'")
        device_id = self.device_id_hint(payload)
        if not device_id:
            raise InvalidPayload("device.uniqueId missing")
        pos: dict[str, Any] = payload["position"]
        attrs: dict[str, Any] = pos.get("attributes") or {}
        if not isinstance(attrs, dict):
            raise InvalidPayload("attributes must be an object")
        lat, lon = _float(pos.get("latitude")), _float(pos.get("longitude"))
        valid = bool(pos.get("valid")) and lat is not None and lon is not None
        if valid and lat is not None and lon is not None and not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise InvalidPayload("coordinates out of range")
        if valid and lat == 0 and lon == 0:
            valid = False  # "null island" is a receiver default, not a fix
        speed = _float(pos.get("speed"))
        accuracy = _float(pos.get("accuracy"))
        hours_ms = _float(attrs.get("hours"))
        odometer = _float(attrs.get("totalDistance") if "totalDistance" in attrs else attrs.get("odometer"))
        alarm = attrs.get("alarm")
        tamper = True if alarm in ("tampering", "tamper", "removing") else None
        return [
            TelemetryObservation(
                adapter=self.kind,
                external_device_id=device_id,
                event_time=_time(pos.get("fixTime")),
                valid_fix=valid,
                latitude=lat if valid else None,
                longitude=lon if valid else None,
                accuracy_m=accuracy if accuracy and accuracy > 0 else None,
                altitude_m=_float(pos.get("altitude")),
                speed_kmh=round(speed * KNOTS_TO_KMH, 3) if speed is not None else None,
                heading_deg=_float(pos.get("course")),
                satellites=int(attrs["sat"]) if isinstance(attrs.get("sat"), int) else None,
                ignition=_bool(attrs.get("ignition")),
                engine_hours=(Decimal(str(hours_ms)) / Decimal(3_600_000)).quantize(Decimal("0.001"))
                if hours_ms is not None
                else None,
                fuel_level=_float(attrs.get("fuel")),
                external_power_v=_float(attrs.get("power")),
                battery_level_pct=_float(attrs.get("batteryLevel")),
                tamper=tamper,
                motion=_bool(attrs.get("motion")),
                odometer_km=(Decimal(str(odometer)) / Decimal(1000)).quantize(Decimal("0.001"))
                if odometer is not None
                else None,
                extra={k: v for k, v in attrs.items() if k not in _KNOWN},
            )
        ]
