"""Typed policy schemas. Each policy type declares its fields, safe seeded defaults (replaceable, versioned
configuration — prompt.md §5), and which fields may be overridden below tenant level."""

from datetime import datetime, time
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PolicyType(StrEnum):
    TRACKING = "TRACKING"
    METER_CAPTURE = "METER_CAPTURE"
    HIRE_BILLING = "HIRE_BILLING"
    DEVICE_SYNC = "DEVICE_SYNC"


class PolicyScope(StrEnum):
    PLATFORM = "PLATFORM"
    TENANT = "TENANT"
    MACHINE = "MACHINE"
    SITE = "SITE"


class TrackingPolicy(BaseModel):
    """GPS/telematics interpretation rules (R1-C/R1-D). Distances in metres, durations in seconds."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    live_max_age_seconds: int = Field(ge=30, le=3600)
    stale_after_seconds: int = Field(ge=60, le=86400)
    offline_after_seconds: int = Field(ge=300, le=7 * 86400)
    max_position_accuracy_m: float = Field(gt=0, le=5000)
    geofence_tolerance_m: float = Field(ge=0, le=5000)
    moving_speed_kmh: float = Field(gt=0, le=50)
    stop_min_seconds: int = Field(ge=30, le=86400)
    max_plausible_speed_kmh: float = Field(gt=10, le=400)
    future_timestamp_tolerance_seconds: int = Field(ge=0, le=3600)
    max_replay_age_days: int = Field(ge=1, le=365)
    low_power_voltage: float | None = Field(default=None, ge=0, le=100)
    # Approved operating window in tenant local time; movement outside it raises UNAUTHORIZED_MOVEMENT.
    operating_window_start: time | None = None
    operating_window_end: time | None = None
    operating_weekdays: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6])

    @model_validator(mode="after")
    def _ordered(self) -> "TrackingPolicy":
        if not self.live_max_age_seconds <= self.stale_after_seconds <= self.offline_after_seconds:
            raise ValueError("require live_max_age <= stale_after <= offline_after")
        if (self.operating_window_start is None) != (self.operating_window_end is None):
            raise ValueError("operating window needs both start and end")
        if any(d < 0 or d > 6 for d in self.operating_weekdays):
            raise ValueError("operating_weekdays are 0 (Mon) .. 6 (Sun)")
        return self

    def within_operating_window(self, local: datetime) -> bool:
        if self.operating_window_start is None or self.operating_window_end is None:
            return True
        if local.weekday() not in self.operating_weekdays:
            return False
        t = local.time()
        start, end = self.operating_window_start, self.operating_window_end
        return start <= t < end if start <= end else (t >= start or t < end)  # supports overnight windows


class CaptureMode(StrEnum):
    AUTOMATIC = "AUTOMATIC"  # in-app camera photo + on-device OCR
    MANUAL = "MANUAL"  # numeric entry (+ photo when manual_photo_required)


class GpsEnforcement(StrEnum):
    HARD = "HARD"  # reading without valid fix is rejected (field must retry)
    SOFT = "SOFT"  # reading accepted as PROVISIONAL with an auditable exception


class MeterCapturePolicy(BaseModel):
    """Owner-controlled hour-meter capture rules (R1-E, S-007). Opening and closing modes are independent."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    opening_mode: CaptureMode
    closing_mode: CaptureMode
    manual_photo_required: bool
    min_ocr_confidence: float = Field(ge=0, le=1)
    max_recapture_attempts: int = Field(ge=0, le=10)
    manual_correction_requires_review: bool
    gps_enforcement: GpsEnforcement
    gps_max_accuracy_m: float = Field(gt=0, le=5000)
    gps_max_age_seconds: int = Field(ge=5, le=3600)
    tracker_comparison_window_seconds: int = Field(ge=30, le=3600)
    tracker_distance_tolerance_m: float = Field(ge=0, le=10000)
    max_hours_per_elapsed_hour: Decimal = Field(gt=0, le=Decimal(5))  # meter can't run faster than wall clock
    continuity_tolerance_hours: Decimal = Field(ge=0, le=Decimal(100))
    telemetry_engine_hours_tolerance: Decimal = Field(ge=0, le=Decimal(100))


class HireBillingPolicy(BaseModel):
    """How meter hours become billable hours (engine hours != billable hours)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    billable_hours_increment: Decimal = Field(gt=0, le=Decimal(1))  # e.g. 0.1 h
    rounding: str = Field(pattern="^(UP|HALF_UP|DOWN)$")


class DeviceSyncPolicy(BaseModel):
    """Bounded offline operation for field devices (R1-F)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    offline_grant_hours: int = Field(ge=1, le=24 * 14)  # max time a device may work without contacting the server
    snapshot_validity_hours: int = Field(ge=1, le=24 * 14)  # cached policies expire; device must refresh
    max_batch_operations: int = Field(ge=1, le=500)
    clock_skew_alert_seconds: int = Field(ge=30, le=86400)


SCHEMAS: dict[PolicyType, type[BaseModel]] = {
    PolicyType.TRACKING: TrackingPolicy,
    PolicyType.METER_CAPTURE: MeterCapturePolicy,
    PolicyType.HIRE_BILLING: HireBillingPolicy,
    PolicyType.DEVICE_SYNC: DeviceSyncPolicy,
}

# Fields a lower scope may override (platform/tenant may override any field).
OVERRIDABLE: dict[PolicyType, dict[PolicyScope, frozenset[str]]] = {
    PolicyType.TRACKING: {
        PolicyScope.MACHINE: frozenset(
            {
                "live_max_age_seconds",
                "stale_after_seconds",
                "offline_after_seconds",
                "max_position_accuracy_m",
                "low_power_voltage",
                "max_plausible_speed_kmh",
                "operating_window_start",
                "operating_window_end",
                "operating_weekdays",
            }
        ),
        PolicyScope.SITE: frozenset({"geofence_tolerance_m"}),
    },
    PolicyType.METER_CAPTURE: {
        PolicyScope.MACHINE: frozenset(
            {
                "opening_mode",
                "closing_mode",
                "manual_photo_required",
                "min_ocr_confidence",
                "max_hours_per_elapsed_hour",
                "telemetry_engine_hours_tolerance",
            }
        ),
        PolicyScope.SITE: frozenset({"gps_max_accuracy_m", "tracker_distance_tolerance_m"}),
    },
    PolicyType.HIRE_BILLING: {PolicyScope.MACHINE: frozenset(), PolicyScope.SITE: frozenset()},
    PolicyType.DEVICE_SYNC: {PolicyScope.MACHINE: frozenset(), PolicyScope.SITE: frozenset()},
}

SEED_DEFAULTS: dict[PolicyType, dict[str, object]] = {
    PolicyType.TRACKING: {
        "live_max_age_seconds": 300,
        "stale_after_seconds": 1800,
        "offline_after_seconds": 6 * 3600,
        "max_position_accuracy_m": 100.0,
        "geofence_tolerance_m": 30.0,
        "moving_speed_kmh": 3.0,
        "stop_min_seconds": 300,
        "max_plausible_speed_kmh": 120.0,
        "future_timestamp_tolerance_seconds": 300,
        "max_replay_age_days": 30,
        "low_power_voltage": None,
        "operating_window_start": None,
        "operating_window_end": None,
        "operating_weekdays": [0, 1, 2, 3, 4, 5, 6],
    },
    PolicyType.METER_CAPTURE: {
        "opening_mode": "AUTOMATIC",
        "closing_mode": "AUTOMATIC",
        "manual_photo_required": True,
        "min_ocr_confidence": 0.85,
        "max_recapture_attempts": 3,
        "manual_correction_requires_review": True,
        "gps_enforcement": "SOFT",
        "gps_max_accuracy_m": 50.0,
        "gps_max_age_seconds": 120,
        "tracker_comparison_window_seconds": 300,
        "tracker_distance_tolerance_m": 150.0,
        "max_hours_per_elapsed_hour": "1.05",
        "continuity_tolerance_hours": "0.5",
        "telemetry_engine_hours_tolerance": "0.5",
    },
    PolicyType.HIRE_BILLING: {"billable_hours_increment": "0.1", "rounding": "HALF_UP"},
    PolicyType.DEVICE_SYNC: {
        "offline_grant_hours": 72,
        "snapshot_validity_hours": 24,
        "max_batch_operations": 100,
        "clock_skew_alert_seconds": 300,
    },
}
