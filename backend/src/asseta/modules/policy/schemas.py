"""Typed policy schemas. Each policy type declares its fields, safe seeded defaults (replaceable, versioned
configuration — prompt.md §5), and which fields may be overridden below tenant level."""

from datetime import datetime, time
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from asseta.modules.policy.engine_hours import ENGINE_HOURS_SEED, EngineHoursPolicy


class PolicyType(StrEnum):
    TRACKING = "TRACKING"
    METER_CAPTURE = "METER_CAPTURE"
    HIRE_BILLING = "HIRE_BILLING"
    DEVICE_SYNC = "DEVICE_SYNC"
    EXPENSE_CAPTURE = "EXPENSE_CAPTURE"
    FRAUD_CONTROLS = "FRAUD_CONTROLS"
    ENGINE_HOURS = "ENGINE_HOURS"
    CASH_CUSTODY = "CASH_CUSTODY"
    OVERSIGHT = "OVERSIGHT"
    CUSTOMER_HOURS = "CUSTOMER_HOURS"


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


class ExpenseCapturePolicy(BaseModel):
    """Field expense controls (R1-G). Amount thresholds are in the tenant's base currency; expenses in another
    currency always need a receipt and a human approval (no implicit FX)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    receipt_required_above: Decimal = Field(ge=0)  # 0 => every expense needs a receipt
    gps_required: bool
    gps_max_accuracy_m: float = Field(gt=0, le=5000)
    auto_approve_limit: Decimal = Field(ge=0)  # amount <= limit => APPROVED automatically; 0 => all need approval


class FraudControlsPolicy(BaseModel):
    """Deterministic risk-signal thresholds (R1-H, ADR-007). Signals are evidence for human review, never verdicts.
    A nullable threshold switches its rule off. Amounts are in the tenant's base currency (no implicit FX)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    engine_activity_min_minutes: int = Field(ge=1, le=24 * 60)  # verified engine-on time without a running job
    fuel_max_litres_per_meter_hour: Decimal | None = Field(default=None, gt=0, le=Decimal(1000))
    expense_threshold_per_machine_per_week: Decimal | None = Field(default=None, gt=0)
    cash_outstanding_max_hours: int = Field(ge=1, le=24 * 60)
    cash_outstanding_max_amount: Decimal | None = Field(default=None, gt=0)
    case_grouping_window_hours: int = Field(ge=1, le=24 * 90)  # new signals join an open case on the same subject
    duplicate_receipt_lookback_days: int = Field(ge=1, le=3660)
    authorization_tolerance_minutes: int = Field(ge=0, le=24 * 60)  # clock tolerance around job authorization
    detection_lookback_hours: int = Field(ge=1, le=24 * 90)  # how far back each periodic sweep re-examines facts


class BillingMode(StrEnum):
    PREPAID_HOURS = "PREPAID_HOURS"  # the job consumes the customer's activated purchased hours
    INVOICE = "INVOICE"  # post-paid: the completed job is invoiced (the behaviour before customer hours)


class ActivationBasis(StrEnum):
    VERIFIED_PAYMENT = "VERIFIED_PAYMENT"  # hours activate only from independently verified money
    CREDIT = "CREDIT"  # explicit, permissioned activation within an approved credit arrangement


class OverConsumption(StrEnum):
    BLOCK_START = "BLOCK_START"  # a prepaid job cannot start without remaining activated hours on its machine
    FLAG_EXCESS = "FLAG_EXCESS"  # it may start; any excess on completion is flagged (never silently consumed)


class CustomerHoursPolicy(BaseModel):
    """Customer prepaid hours (accountability 3.1). Every rule a tenant may want differently is here; the platform
    default is only a starting point. Segregation of duties on approvals is always enforced (never relaxable)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool  # off => no new purchases/prepaid jobs; jobs keep the invoice flow
    walk_in_allowed: bool
    billing_modes: list[BillingMode] = Field(min_length=1)
    default_billing_mode: BillingMode
    activation_basis: list[ActivationBasis] = Field(min_length=1)
    partial_activation: bool  # partial verified payments activate hours pro rata
    hours_increment: Decimal = Field(gt=0, le=Decimal(1))  # activation rounds DOWN to this step
    expiry_days: int | None = Field(default=None, ge=1, le=3660)  # None => activated hours never expire
    expiry_warning_days: int = Field(ge=0, le=365)
    over_consumption: OverConsumption
    overrun_exception_blocking: bool  # the HOURS_OVERRUN exception blocks the job until reviewed/covered
    transfer_requires_approval: bool
    cancellation_requires_approval: bool
    cancellation_after_consumption_allowed: bool  # cancel the remaining hours of a partly used purchase
    discount_requires_approval: bool
    max_discount_percent: Decimal = Field(ge=0, le=Decimal(100))
    credit_allowed: bool
    reason_code_required: bool  # approvals/proposals must cite a tenant reason code (tenant list)

    @model_validator(mode="after")
    def _consistent(self) -> "CustomerHoursPolicy":
        if len(set(self.billing_modes)) != len(self.billing_modes):
            raise ValueError("billing_modes must not repeat")
        if self.default_billing_mode not in self.billing_modes:
            raise ValueError("default_billing_mode must be one of billing_modes")
        if len(set(self.activation_basis)) != len(self.activation_basis):
            raise ValueError("activation_basis must not repeat")
        return self


class CashCustodyPolicy(BaseModel):
    """Cash custody chain controls (accountability design C). Every switch is tenant configuration; switching a
    capability off keeps the pre-existing behaviour (own-custody recording, floats counted when issued, no
    acknowledgement step). Segregation of duties (proposer != approver) is always enforced and is not a switch.
    Amounts are in the tenant's base currency."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    # Master switch (capability CASH_CUSTODY). Off: only the cash basics that predate these controls remain
    # (collections, floats, remittances and their confirmation, reconciliation); every switch below reads as off.
    enabled: bool = True
    # Recorders (`tenant.collection.record`) may record collections/transfers/remittances for any active staff
    # member (custodians need no login). Off: only the office cash permission may name another custodian.
    recorders_may_record_for_others: bool
    transfer_ack_required: bool  # off: a field transfer counts as received at the declared amount when recorded
    recorder_receiver_counts_as_ack: bool  # recording a transfer you receive is its acknowledgement
    float_ack_required: bool  # off: a float counts in the receiver's custody when issued
    remit_full_balance: bool  # a remittance below the outstanding balance (less approved retentions) is flagged
    remittance_cutoff_hour: int | None = Field(default=None, ge=0, le=23)  # tenant-local hour; null = no daily cut-off
    variance_case_threshold: Decimal | None = Field(default=None, ge=0)  # |variance| above -> case; null = never
    writeoff_requires_approval: bool  # on: a write-off is proposed then approved by another permission holder
    retention_allowed: bool  # off: no retention may be requested (everything must be remitted)

    def in_force(self) -> "CashCustodyPolicy":
        """The rules actually enforced: as configured when enabled; switched off as a whole otherwise (the cash
        behaviour before these controls: own-custody recording, floats counted when issued, no acknowledgement,
        no variances, retentions, cut-off or partial-remittance flag)."""
        if self.enabled:
            return self
        return self.model_copy(
            update={
                "recorders_may_record_for_others": False,
                "transfer_ack_required": False,
                "recorder_receiver_counts_as_ack": False,
                "float_ack_required": False,
                "remit_full_balance": False,
                "remittance_cutoff_hour": None,
                "variance_case_threshold": None,
                "retention_allowed": False,
            }
        )


class OversightPolicy(BaseModel):
    """Accountability dashboard (design D): which tiles a tenant shows and the look-back window of its counts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    hidden_dashboard_tiles: list[str] = Field(default_factory=list, max_length=50)
    security_event_window_days: int = Field(ge=1, le=366)


SCHEMAS: dict[PolicyType, type[BaseModel]] = {
    PolicyType.TRACKING: TrackingPolicy,
    PolicyType.METER_CAPTURE: MeterCapturePolicy,
    PolicyType.HIRE_BILLING: HireBillingPolicy,
    PolicyType.DEVICE_SYNC: DeviceSyncPolicy,
    PolicyType.EXPENSE_CAPTURE: ExpenseCapturePolicy,
    PolicyType.FRAUD_CONTROLS: FraudControlsPolicy,
    PolicyType.ENGINE_HOURS: EngineHoursPolicy,
    PolicyType.CASH_CUSTODY: CashCustodyPolicy,
    PolicyType.OVERSIGHT: OversightPolicy,
    PolicyType.CUSTOMER_HOURS: CustomerHoursPolicy,
}

# Fields a lower scope may override (platform/tenant may override any field).
OVERRIDABLE: dict[PolicyType, dict[PolicyScope, frozenset[str]]] = {
    PolicyType.ENGINE_HOURS: {
        PolicyScope.MACHINE: frozenset({"baseline_required_before_start", "daily_report_required"}),
        PolicyScope.SITE: frozenset(),
    },
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
    PolicyType.EXPENSE_CAPTURE: {PolicyScope.MACHINE: frozenset(), PolicyScope.SITE: frozenset()},
    PolicyType.CASH_CUSTODY: {PolicyScope.MACHINE: frozenset(), PolicyScope.SITE: frozenset()},
    PolicyType.OVERSIGHT: {PolicyScope.MACHINE: frozenset(), PolicyScope.SITE: frozenset()},
    PolicyType.FRAUD_CONTROLS: {
        PolicyScope.MACHINE: frozenset(
            {"engine_activity_min_minutes", "fuel_max_litres_per_meter_hour", "expense_threshold_per_machine_per_week"}
        ),
        PolicyScope.SITE: frozenset(),
    },
    PolicyType.CUSTOMER_HOURS: {PolicyScope.MACHINE: frozenset(), PolicyScope.SITE: frozenset()},
}

SEED_DEFAULTS: dict[PolicyType, dict[str, object]] = {
    PolicyType.ENGINE_HOURS: ENGINE_HOURS_SEED,
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
    PolicyType.EXPENSE_CAPTURE: {
        "receipt_required_above": "0",
        "gps_required": True,
        "gps_max_accuracy_m": 100.0,
        "auto_approve_limit": "0",
    },
    PolicyType.FRAUD_CONTROLS: {
        "engine_activity_min_minutes": 30,
        "fuel_max_litres_per_meter_hour": None,
        "expense_threshold_per_machine_per_week": None,
        "cash_outstanding_max_hours": 48,
        "cash_outstanding_max_amount": None,
        "case_grouping_window_hours": 72,
        "duplicate_receipt_lookback_days": 90,
        "authorization_tolerance_minutes": 5,
        "detection_lookback_hours": 168,
    },
    PolicyType.CASH_CUSTODY: {
        "enabled": True,
        "recorders_may_record_for_others": True,
        "transfer_ack_required": True,
        "recorder_receiver_counts_as_ack": True,
        "float_ack_required": False,  # on would leave floats uncounted for field apps without acknowledgement
        "remit_full_balance": False,  # off: no partial-remittance flags until a tenant opts in
        "remittance_cutoff_hour": None,
        "variance_case_threshold": "0",
        "writeoff_requires_approval": True,
        "retention_allowed": True,
    },
    PolicyType.OVERSIGHT: {"hidden_dashboard_tiles": [], "security_event_window_days": 7},
    PolicyType.CUSTOMER_HOURS: {
        "enabled": True,
        "walk_in_allowed": True,
        "billing_modes": ["PREPAID_HOURS", "INVOICE"],
        "default_billing_mode": "INVOICE",
        "activation_basis": ["VERIFIED_PAYMENT", "CREDIT"],
        "partial_activation": True,
        "hours_increment": "0.01",
        "expiry_days": None,
        "expiry_warning_days": 7,
        "over_consumption": "BLOCK_START",
        "overrun_exception_blocking": True,
        "transfer_requires_approval": True,
        "cancellation_requires_approval": True,
        "cancellation_after_consumption_allowed": False,
        "discount_requires_approval": True,
        "max_discount_percent": "100",
        "credit_allowed": True,
        "reason_code_required": False,
    },
}
