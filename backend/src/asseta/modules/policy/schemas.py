"""Typed policy schemas. Each policy type declares its fields, safe seeded defaults (replaceable, versioned
configuration — prompt.md §5), and which fields may be overridden below tenant level."""

from datetime import datetime, time
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PolicyType(StrEnum):
    TRACKING = "TRACKING"


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


SCHEMAS: dict[PolicyType, type[BaseModel]] = {PolicyType.TRACKING: TrackingPolicy}

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
}
