"""DEC-031 Phase 2 (asset safety): fuel issued into a machine is compared with its engine hours per machine and
period (S2), a FRAUD_CONTROLS threshold that is off by default: nothing changes until the tenant switches it on.
Engine time is accounted for by machine reports (ADR-008): the engine-activity detectors of the earlier work model
(S1 included) are no longer raised."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from asseta.tools.gps_simulator import Fix
from tests.support.api import Actor, Api
from tests.support.finance import FinCtx, role, setup_finance
from tests.support.intelligence import cases, fraud_policy, signals, sweep
from tests.support.meter import capture
from tests.support.telemetry import DAR, Telemetry, Tracked

T = "/api/v1/tenant"
DAY1 = "2026-11-01"  # the clock starts 2026-11-01 09:00 UTC = 12:00 tenant-local (Africa/Dar_es_Salaam, UTC+3)
DAY1_START = datetime(2026, 10, 31, 21, 0, tzinfo=UTC)  # 00:00 local
DAY1_END = datetime(2026, 11, 1, 21, 0, tzinfo=UTC)
AFTER_DAY1 = datetime(2026, 11, 2, 7, 0, tzinfo=UTC)  # 10:00 local on 2 Nov: 1 Nov has closed
S2_RULE = "MACHINE_FUEL_ABOVE_NORM"


def _ok(r: Any, status: int = 200) -> Any:
    assert r.status_code == status, r.text
    return r.json()


# --- engine activity is not judged against work any more (ADR-008) -----------------------------------------------
def _engine_day(api: Api, name: str, device: str) -> tuple[Tracked, str]:
    """Engine on twice for 20 min with no machine report (12:01 and 14:00 local), then moving at 19:00 local outside
    the approved 06:00-18:00 window for 5 min."""
    tel = Telemetry(api)
    t = tel.tracked_machine(name, device)
    tid, t0 = t.tenant["tenant"]["id"], api.clock.now
    _ok(
        t.owner.post(
            f"{T}/policies/TRACKING/versions",
            {
                "scope": "TENANT",
                "values": {"operating_window_start": "06:00", "operating_window_end": "18:00"},
                "reason": "Site hours",
            },
        ),
        201,
    )
    plan: list[tuple[int, bool, float]] = [(1, True, 0.0), (21, False, 0.0), (120, True, 0.0), (140, False, 0.0)]
    plan += [(420, True, 25.0), (425, False, 0.0)]
    for minutes, ignition, speed in plan:
        at = t0 + timedelta(minutes=minutes)
        api.clock.set_at(at + timedelta(seconds=2))
        assert tel.send(device, Fix(at, DAR[0], DAR[1], speed, 0.0, ignition=ignition))["accepted"] == 1
    tel.drain_timeline()
    api.clock.set_at(t0 + timedelta(hours=8))  # 20:00 local, the day is still open
    return t, tid


def test_engine_activity_raises_no_work_signals_and_s2_is_off_by_default(api: Api) -> None:
    t, tid = _engine_day(api, "Engine Day Off", "EWW-0")
    sweep(api, tid)
    api.clock.set_at(AFTER_DAY1)
    sweep(api, tid)
    for rule in ("UNREPORTED_ENGINE_ACTIVITY", "ENGINE_RUNNING_WITHOUT_WORK", "WORK_WITHOUT_AUTHORIZATION", S2_RULE):
        assert signals(t.owner, rule_code=rule) == [], rule
    eff = _ok(t.owner.get(f"{T}/policies/FRAUD_CONTROLS/effective"))["values"]
    assert (eff["fuel_check_period"], eff["fuel_litres_per_hour_max"]) == (None, None)
    for retired in ("engine_activity_min_minutes", "engine_without_work_case_min_minutes"):
        assert retired not in eff
        r = t.owner.post(
            f"{T}/policies/FRAUD_CONTROLS/versions",
            {"scope": "TENANT", "values": {retired: 10}, "reason": "Retired setting"},
        )
        assert r.status_code == 422 and r.json()["error"]["code"] == "POLICY_UNKNOWN_FIELD", r.text


# --- S2: fuel against the meter's engine hours -------------------------------------------------------------------
def _reading(o: Actor, machine_id: str, reading: str, at: datetime) -> None:
    body = capture(machine_id, reading, at, mode="MANUAL")
    if at > o.api.clock.now:
        o.api.clock.set_at(at)
    _ok(o.post(f"{T}/meter-captures", body), 201)


def _metered_day(api: Api, name: str, device: str) -> FinCtx:
    """Machine with 10 engine hours on 1 Nov from its readings (baseline at 00:00, readings at 12:00 and 24:00 local),
    50 L issued/purchased into it that day (plus 100 L logged as used, never counted twice)."""
    f = setup_finance(api, name, device)
    o, machine = f.owner, f.c.t.machine_id
    _ok(
        o.post(
            f"{T}/policies/METER_CAPTURE/versions",
            {
                "scope": "TENANT",
                "values": {"capture_mode": "MANUAL", "manual_photo_required": False},
                "reason": "Manual capture",
            },
        ),
        201,
    )
    proposed = _ok(
        o.post(
            f"{T}/meter-baselines",
            {"machine_id": machine, "reading": "1000", "captured_at": DAY1_START.isoformat(), "note": "Initial"},
        ),
        201,
    )
    approver = role(api, f.tid, "owner", f"approver-{device}")
    _ok(approver.post(f"{T}/meter-baselines/{proposed['id']}/decision", {"decision": "APPROVE", "note": "Checked"}))
    _reading(o, machine, "1006", DAY1_START + timedelta(hours=12))
    for litres, kind in (("30", "ISSUE"), ("20", "PURCHASE"), ("100", "USAGE")):
        body = {"event_type": kind, "litres": litres, "machine_id": machine, "unit_price": "3000"}
        body["occurred_at"] = (DAY1_START + timedelta(hours=14)).isoformat()
        _ok(f.supervisor.post(f"{T}/fuel-events", body), 201)
    _reading(o, machine, "1010", DAY1_END)
    return f


def test_fuel_per_machine_period_with_category_and_machine_norms(api: Api) -> None:
    f = _metered_day(api, "Fuel Day Co", "MFUEL-1")
    o, machine, category = f.owner, f.c.t.machine_id, f.c.category_id
    api.clock.set_at(AFTER_DAY1)
    fraud_policy(o, fuel_litres_per_hour_max="4")  # no period: the check stays off
    assert sweep(api, f.tid).signals == 0
    fraud_policy(o, fuel_check_period="DAY", fuel_litres_per_hour_max="6")  # 50 L / 10 h = 5 L/h: within the norm
    assert sweep(api, f.tid).signals == 0
    fraud_policy(o, scope="MACHINE_CATEGORY", ref=category, fuel_litres_per_hour_max="4")
    fraud_policy(o, scope="MACHINE", ref=machine, fuel_litres_per_hour_max="5")  # the machine's own norm wins
    assert sweep(api, f.tid).signals == 0  # exactly at the norm
    eff = _ok(o.get(f"{T}/policies/FRAUD_CONTROLS/effective", category_id=category))
    assert eff["values"]["fuel_litres_per_hour_max"] == "4" and ".C" in eff["version_stamp"]
    fraud_policy(o, scope="MACHINE", ref=machine, fuel_litres_per_hour_max="4.5")
    assert sweep(api, f.tid).signals == 1
    [sig] = signals(o, rule_code=S2_RULE)
    ev = sig["evidence"]
    assert (ev["period_kind"], ev["period"], ev["litres_into_machine"]) == ("DAY", DAY1, "50.000")
    assert ev["engine_hours"] == "10.00"
    assert ev["litres_per_engine_hour"] == "5.000" and ev["norm_litres_per_engine_hour"] == "4.5"
    assert ev["norm_source"] == "MACHINE" and len(ev["fuel_event_ids"]) == 2
    assert sig["subject_id"] == machine and ".C" in sig["policy_version"] and ".M" in sig["policy_version"]
    [case] = cases(o)
    assert case["title"] == "Fuel above the norm for the engine hours"
    assert sweep(api, f.tid).signals == 0  # idempotent per machine-period


def test_category_norm_applies_and_category_scope_is_checked(api: Api) -> None:
    f = _metered_day(api, "Fuel Cat Co", "MFUEL-2")
    o = f.owner
    api.clock.set_at(AFTER_DAY1)
    fraud_policy(o, fuel_check_period="DAY")
    fraud_policy(o, scope="MACHINE_CATEGORY", ref=f.c.category_id, fuel_litres_per_hour_max="4.9")
    assert sweep(api, f.tid).signals == 1
    [sig] = signals(o, rule_code=S2_RULE)
    assert sig["evidence"]["norm_source"] == "MACHINE_CATEGORY"
    bad = o.post(
        f"{T}/policies/FRAUD_CONTROLS/versions",
        {"scope": "MACHINE_CATEGORY", "scope_ref_id": f.c.category_id, "values": {"duplicate_receipt_lookback_days": 5},
         "reason": "Not a category field"},
    )  # fmt: skip
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "POLICY_FIELD_NOT_OVERRIDABLE"
    missing = o.post(
        f"{T}/policies/FRAUD_CONTROLS/versions",
        {"scope": "MACHINE_CATEGORY", "scope_ref_id": str(uuid.uuid4()), "values": {"fuel_litres_per_hour_max": "3"},
         "reason": "Unknown category"},
    )  # fmt: skip
    assert missing.status_code == 404
    other = o.post(
        f"{T}/policies/CASH_CUSTODY/versions",
        {"scope": "MACHINE_CATEGORY", "scope_ref_id": f.c.category_id, "values": {"max_holding_days": 3},
         "reason": "No category overrides for this type"},
    )  # fmt: skip
    assert other.status_code == 422 and other.json()["error"]["code"] == "POLICY_FIELD_NOT_OVERRIDABLE"
