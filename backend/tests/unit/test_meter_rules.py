from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from asseta.modules.meter.models import ExceptionType as X
from asseta.modules.meter.models import GpsStatus
from asseta.modules.meter.rules import (
    GpsEvidence,
    PriorReading,
    capture_findings,
    gps_findings,
    location_findings,
    sequence_findings,
    telemetry_findings,
)
from asseta.modules.policy.schemas import (
    SEED_DEFAULTS,
    CaptureMode,
    MeterCapturePolicy,
    PolicyType,
)

NOW = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)


def policy(**kw: object) -> MeterCapturePolicy:
    return MeterCapturePolicy.model_validate({**SEED_DEFAULTS[PolicyType.METER_CAPTURE], **kw})


def types(findings: list) -> set[X]:  # type: ignore[type-arg]
    return {f.type for f in findings}


@pytest.mark.parametrize(
    ("expected", "used", "violation"),
    [
        (CaptureMode.AUTOMATIC, CaptureMode.AUTOMATIC, False),
        (CaptureMode.MANUAL, CaptureMode.MANUAL, False),
        (CaptureMode.AUTOMATIC, CaptureMode.MANUAL, True),
        (CaptureMode.MANUAL, CaptureMode.AUTOMATIC, True),
    ],
)
def test_mode_enforcement_all_combinations(expected: CaptureMode, used: CaptureMode, violation: bool) -> None:
    f = capture_findings(policy(), expected, used, True, Decimal("100.0"), Decimal("100.0"), 0.99)
    assert (X.MODE_POLICY_VIOLATION in types(f)) is violation


def test_photo_and_ocr_rules() -> None:
    assert X.PHOTO_MISSING in types(
        capture_findings(policy(), CaptureMode.AUTOMATIC, CaptureMode.AUTOMATIC, False, Decimal(1), Decimal(1), 0.99)
    )
    assert X.PHOTO_MISSING not in types(
        capture_findings(
            policy(manual_photo_required=False), CaptureMode.MANUAL, CaptureMode.MANUAL, False, Decimal(1), None, None
        )
    )
    f = capture_findings(
        policy(), CaptureMode.AUTOMATIC, CaptureMode.AUTOMATIC, True, Decimal("1234.6"), Decimal("1284.6"), 0.62
    )
    assert types(f) == {X.LOW_OCR_CONFIDENCE, X.MANUAL_CORRECTION}


def test_gps_no_fix_soft_vs_hard_and_accuracy_age() -> None:
    no_fix = GpsEvidence(GpsStatus.PERMISSION_DENIED, None, None)
    f, reject = gps_findings(policy(), no_fix, NOW)
    assert types(f) == {X.GPS_UNAVAILABLE} and not reject
    f, reject = gps_findings(policy(gps_enforcement="HARD"), no_fix, NOW)
    assert reject
    f, _ = gps_findings(policy(), GpsEvidence(GpsStatus.FIX, 180.0, NOW - timedelta(minutes=10)), NOW)
    assert types(f) == {X.GPS_INACCURATE, X.GPS_STALE}
    assert gps_findings(policy(), GpsEvidence(GpsStatus.FIX, 8.0, NOW - timedelta(seconds=5)), NOW) == ([], False)


def test_sequence_decrease_impossible_increment_and_reset() -> None:
    prior = PriorReading(Decimal("1000.0"), NOW - timedelta(hours=10))
    assert types(sequence_findings(policy(), Decimal("990.0"), NOW, prior, None)) == {X.METER_DECREASE}
    assert sequence_findings(policy(), Decimal("12.0"), NOW, prior, Decimal("10.0")) == []  # reset: 10 -> 12 in 10h
    assert types(sequence_findings(policy(), Decimal("1020.0"), NOW, prior, None)) == {X.IMPOSSIBLE_INCREMENT}
    assert sequence_findings(policy(), Decimal("1003.0"), NOW, prior, None) == []  # no continuity rule any more
    assert sequence_findings(policy(), Decimal("1000.3"), NOW, prior, None) == []
    assert sequence_findings(policy(), Decimal("5.0"), NOW, None, None) == []  # first reading: nothing to compare


def test_location_compares_only_same_time_positions() -> None:
    f, c = location_findings(policy(), None, 10, None, None, NOW)
    assert f == [] and c["compared"] is False
    f, c = location_findings(policy(), 900.0, 10, 5, NOW - timedelta(seconds=40), NOW)
    assert types(f) == {X.LOCATION_MISMATCH} and c["allowed_m"] == 165.0
    assert location_findings(policy(), 120.0, 10, 5, NOW, NOW)[0] == []


def test_telemetry_mismatch() -> None:
    assert types(telemetry_findings(policy(), Decimal("8.0"), Decimal("6.9"))) == {X.TELEMETRY_MISMATCH}
    assert telemetry_findings(policy(), Decimal("8.0"), Decimal("7.9")) == []
    assert telemetry_findings(policy(), Decimal("8.0"), None) == []
