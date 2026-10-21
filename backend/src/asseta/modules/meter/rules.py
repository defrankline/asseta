"""Pure meter-evidence rules. Each rule returns `Finding`s (exception candidates with evidence) — never verdicts.
Inputs are plain values so rules are deterministic, unit-testable, and identical for online and synced captures."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_DOWN, ROUND_HALF_UP, ROUND_UP, Decimal
from typing import Any

from asseta.modules.meter.models import ExceptionType, GpsStatus
from asseta.modules.policy.schemas import CaptureMode, GpsEnforcement, HireBillingPolicy, MeterCapturePolicy

HOUR = Decimal(3600)


@dataclass(frozen=True)
class Finding:
    type: ExceptionType
    severity: str
    blocking: bool
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GpsEvidence:
    status: GpsStatus
    accuracy_m: float | None
    location_captured_at: datetime | None


def gps_findings(policy: MeterCapturePolicy, gps: GpsEvidence, captured_at: datetime) -> tuple[list[Finding], bool]:
    """Returns findings and whether the reading must be rejected (HARD enforcement). Coordinates are never invented:
    a failed fix is recorded as such and becomes an explicit exception."""
    hard = policy.gps_enforcement is GpsEnforcement.HARD
    if gps.status is not GpsStatus.FIX:
        return [
            Finding(
                ExceptionType.GPS_UNAVAILABLE,
                "WARNING",
                True,
                {"gps_status": gps.status.value, "enforcement": policy.gps_enforcement.value},
            )
        ], hard
    findings: list[Finding] = []
    if gps.accuracy_m is None or gps.accuracy_m > policy.gps_max_accuracy_m:
        findings.append(
            Finding(
                ExceptionType.GPS_INACCURATE,
                "WARNING",
                True,
                {"accuracy_m": gps.accuracy_m, "max_accuracy_m": policy.gps_max_accuracy_m},
            )
        )
    if gps.location_captured_at is not None:
        age = (captured_at - gps.location_captured_at).total_seconds()
        if abs(age) > policy.gps_max_age_seconds:
            findings.append(
                Finding(
                    ExceptionType.GPS_STALE,
                    "WARNING",
                    True,
                    {"location_age_s": round(age, 1), "max_age_s": policy.gps_max_age_seconds},
                )
            )
    return findings, hard and bool(findings)


def capture_findings(
    policy: MeterCapturePolicy,
    expected_mode: CaptureMode,
    mode: CaptureMode,
    has_photo: bool,
    reading: Decimal,
    ocr_value: Decimal | None,
    ocr_confidence: float | None,
) -> list[Finding]:
    findings: list[Finding] = []
    if mode is not expected_mode:
        findings.append(
            Finding(
                ExceptionType.MODE_POLICY_VIOLATION,
                "CRITICAL",
                True,
                {"required_mode": expected_mode.value, "used_mode": mode.value},
            )
        )
    needs_photo = mode is CaptureMode.AUTOMATIC or policy.manual_photo_required
    if needs_photo and not has_photo:
        findings.append(Finding(ExceptionType.PHOTO_MISSING, "WARNING", True, {"mode": mode.value}))
    if mode is CaptureMode.AUTOMATIC:
        if ocr_confidence is None or ocr_confidence < policy.min_ocr_confidence:
            findings.append(
                Finding(
                    ExceptionType.LOW_OCR_CONFIDENCE,
                    "INFO",
                    policy.manual_correction_requires_review,
                    {"ocr_confidence": ocr_confidence, "minimum": policy.min_ocr_confidence},
                )
            )
        if ocr_value is not None and ocr_value != reading:
            findings.append(
                Finding(
                    ExceptionType.MANUAL_CORRECTION,
                    "INFO",
                    policy.manual_correction_requires_review,
                    {"ocr_value": str(ocr_value), "entered_value": str(reading)},
                )
            )
    return findings


@dataclass(frozen=True)
class PriorReading:
    reading: Decimal
    captured_at: datetime
    job_id: str
    kind: str


def sequence_findings(
    policy: MeterCapturePolicy,
    reading: Decimal,
    captured_at: datetime,
    prior: PriorReading | None,
    reset_new_reading: Decimal | None,
    is_opening: bool,
) -> list[Finding]:
    """Decrease / impossible increment / cross-job continuity, relative to the machine's last valid reading.
    An approved reset after the prior reading re-bases the comparison (meter replacement/rollover)."""
    if prior is None:
        return []
    base = reset_new_reading if reset_new_reading is not None else prior.reading
    findings: list[Finding] = []
    delta = reading - base
    evidence = {
        "previous_reading": str(base),
        "previous_at": prior.captured_at.isoformat(),
        "previous_job_id": prior.job_id,
        "reading": str(reading),
    }
    if delta < 0:
        findings.append(Finding(ExceptionType.METER_DECREASE, "CRITICAL", True, evidence))
        return findings
    elapsed_h = Decimal(str(max((captured_at - prior.captured_at).total_seconds(), 0))) / HOUR
    if delta > elapsed_h * policy.max_hours_per_elapsed_hour + Decimal("0.05"):
        findings.append(
            Finding(
                ExceptionType.IMPOSSIBLE_INCREMENT,
                "CRITICAL",
                True,
                {**evidence, "delta_hours": str(delta), "elapsed_hours": str(elapsed_h.quantize(Decimal("0.01")))},
            )
        )
    if is_opening and prior.kind == "CLOSING" and delta > policy.continuity_tolerance_hours:
        findings.append(
            Finding(
                ExceptionType.CONTINUITY_GAP,
                "WARNING",
                True,
                {**evidence, "gap_hours": str(delta), "tolerance_hours": str(policy.continuity_tolerance_hours)},
            )
        )
    return findings


def location_findings(
    policy: MeterCapturePolicy,
    distance_m: float | None,
    phone_accuracy_m: float | None,
    tracker_accuracy_m: float | None,
    tracker_time: datetime | None,
    captured_at: datetime,
) -> tuple[list[Finding], dict[str, Any]]:
    """Compare the phone fix with the machine tracker position *at the same observation time* only."""
    if distance_m is None or tracker_time is None:
        return [], {"compared": False, "reason": "no tracker position within comparison window"}
    allowed = policy.tracker_distance_tolerance_m + (phone_accuracy_m or 0) + (tracker_accuracy_m or 0)
    comparison = {
        "compared": True,
        "distance_m": round(distance_m, 1),
        "allowed_m": round(allowed, 1),
        "tracker_time": tracker_time.isoformat(),
        "time_offset_s": round((captured_at - tracker_time).total_seconds(), 1),
    }
    if distance_m > allowed:
        return [Finding(ExceptionType.LOCATION_MISMATCH, "CRITICAL", True, comparison)], comparison
    return [], comparison


def telemetry_findings(
    policy: MeterCapturePolicy, meter_delta: Decimal, engine_hours_delta: Decimal | None
) -> list[Finding]:
    if engine_hours_delta is None:
        return []
    diff = abs(meter_delta - engine_hours_delta)
    if diff > policy.telemetry_engine_hours_tolerance:
        return [
            Finding(
                ExceptionType.TELEMETRY_MISMATCH,
                "WARNING",
                True,
                {
                    "meter_delta": str(meter_delta),
                    "tracker_engine_hours_delta": str(engine_hours_delta),
                    "tolerance": str(policy.telemetry_engine_hours_tolerance),
                },
            )
        ]
    return []


_ROUNDING = {"UP": ROUND_UP, "HALF_UP": ROUND_HALF_UP, "DOWN": ROUND_DOWN}


def billable_hours(
    meter_hours: Decimal, nonbillable_hours: Decimal, minimum_hours: Decimal, policy: HireBillingPolicy
) -> Decimal:
    """Billable hours follow contract rules, not raw engine/meter hours: subtract approved non-billable periods,
    round to the configured increment, then apply the contract minimum."""
    worked = max(meter_hours - nonbillable_hours, Decimal(0))
    steps = (worked / policy.billable_hours_increment).quantize(Decimal(1), rounding=_ROUNDING[policy.rounding])
    return max(steps * policy.billable_hours_increment, minimum_hours)
