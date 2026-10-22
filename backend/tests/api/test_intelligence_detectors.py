"""Gate 6 (R1-H): each deterministic detector fires with fact/threshold evidence, stays silent at the boundary,
and re-running is idempotent (dedupe key; one case link per signal)."""

from datetime import timedelta

from asseta.tools.gps_simulator import Fix
from tests.support.api import Api
from tests.support.finance import category, complete_job, expense_policy, setup_finance
from tests.support.intelligence import cases, expense, feed_events, fraud_policy, receipt, signals, sweep
from tests.support.jobs import capture, unique_jpeg
from tests.support.telemetry import DAR, Telemetry


def test_unreported_engine_activity_from_verified_ignition(api: Api) -> None:
    tel = Telemetry(api)
    t = tel.tracked_machine("Engine Co", "ENG-1")
    tid, t0 = t.tenant["tenant"]["id"], api.clock.now
    for minutes, ignition in ((1, True), (20, True), (40, True), (50, False)):
        api.clock.set_at(t0 + timedelta(minutes=minutes))  # ignition is verified by the first real report
        assert tel.send("ENG-1", Fix(api.clock.now, DAR[0], DAR[1], 0.0, 0.0, ignition=ignition))["accepted"] == 1
    tel.drain_timeline()
    api.clock.set_at(t0 + timedelta(hours=1))

    fraud_policy(t.owner, engine_activity_min_minutes=50)  # engine on for 49 minutes: below the threshold
    assert sweep(api, tid).signals == 0
    fraud_policy(t.owner, engine_activity_min_minutes=49)
    first = sweep(api, tid)
    assert (first.signals, first.cases_opened) == (1, 1)
    [sig] = signals(t.owner, rule_code="UNREPORTED_ENGINE_ACTIVITY")
    ev = sig["evidence"]
    assert sig["subject_type"] == "MACHINE" and sig["subject_id"] == t.machine_id and sig["status"] == "LINKED"
    assert ev["basis"] == "IGNITION" and ev["uncovered_minutes"] == 49.0 and ev["threshold_minutes"] == 49
    assert sig["policy_version"].startswith("FRAUD_CONTROLS@")
    again = sweep(api, tid)
    assert (again.signals, again.linked, again.cases_opened) == (0, 0, 0)  # idempotent re-run
    [case] = cases(t.owner)
    assert case["title"] == "Engine activity without an active job" and case["signal_count"] == 1


def test_duplicate_receipt_event_driven_and_sweep(api: Api) -> None:
    f = setup_finance(api, "Receipt Co", "RCPT-1")
    cat = category(f, "SPARES", "Spares")
    expense_policy(f, receipt_required_above="0", gps_required=False, auto_approve_limit="0")
    image = unique_jpeg()
    first = expense(api, f.supervisor, cat, "50000", receipt_attachment_ids=[receipt(api, f.supervisor, image)])
    api.clock.set_at(api.clock.now + timedelta(hours=2))
    second = expense(api, f.supervisor, cat, "50000", receipt_attachment_ids=[receipt(api, f.supervisor, image)])
    other = expense(api, f.supervisor, cat, "7000", receipt_attachment_ids=[receipt(api, f.supervisor, unique_jpeg())])

    assert feed_events(api, f.tid) == 3  # ExpenseSubmitted x3 -> event-driven receipt check
    [sig] = signals(f.owner, rule_code="DUPLICATE_RECEIPT")
    assert sig["subject_type"] == "EXPENSE" and sig["subject_id"] == second["id"]
    assert [x["expense_id"] for x in sig["evidence"]["same_receipt_on"]] == [first["id"]]
    assert sig["evidence"]["lookback_days"] == 90 and other["id"] not in str(sig["evidence"])
    assert sweep(api, f.tid).signals == 0 and feed_events(api, f.tid) == 3  # both paths idempotent
    assert len(signals(f.owner, rule_code="DUPLICATE_RECEIPT")) == 1

    api.clock.set_at(api.clock.now + timedelta(days=10))
    fraud_policy(f.owner, duplicate_receipt_lookback_days=5)
    late = expense(api, f.supervisor, cat, "50000", receipt_attachment_ids=[receipt(api, f.supervisor, image)])
    feed_events(api, f.tid)
    assert late["id"] not in {s["subject_id"] for s in signals(f.owner, rule_code="DUPLICATE_RECEIPT")}


def test_fuel_allowance_uses_meter_hours_and_machine_override(api: Api) -> None:
    f = setup_finance(api, "Fuel Co", "FUEL-1")
    t0 = api.clock.now
    complete_job(api, f, f.c.job_id, "500.0", "508.0", 9)  # 8 meter hours
    for litres, kind in (("85", "USAGE"), ("40", "ISSUE")):
        body = {"event_type": kind, "litres": litres, "machine_id": f.c.t.machine_id}
        body |= {"occurred_at": (t0 + timedelta(hours=2)).isoformat(), "unit_price": "3000"}
        r = f.supervisor.post("/api/v1/tenant/fuel-events", body)
        assert r.status_code == 201, r.text
    assert sweep(api, f.tid).signals == 0  # rule off by default
    fraud_policy(f.owner, fuel_max_litres_per_meter_hour="10.625")  # 85 l / 8 h exactly: not above
    assert sweep(api, f.tid).signals == 0
    fraud_policy(f.owner, scope="MACHINE", ref=f.c.t.machine_id, fuel_max_litres_per_meter_hour="10")
    assert sweep(api, f.tid).signals == 1
    [sig] = signals(f.owner, rule_code="FUEL_ALLOWANCE_EXCEEDED")
    ev = sig["evidence"]
    assert (ev["meter_hours"], ev["litres_used"], ev["litres_into_machine"]) == ("8.00", "85.000", "40.000")
    assert ev["litres_per_meter_hour"] == "10.625" and ev["allowance_litres_per_meter_hour"] == "10"
    assert sig["job_id"] == f.c.job_id and ".M" in sig["policy_version"]


def test_expense_threshold_per_machine_week_boundary(api: Api) -> None:
    f = setup_finance(api, "Spend Co", "SPEND-1")
    cat = category(f, "REPAIRS", "Repairs")
    expense_policy(f, receipt_required_above="100000000", gps_required=False, auto_approve_limit="0")
    fraud_policy(f.owner, expense_threshold_per_machine_per_week="100000")
    m = f.c.t.machine_id
    expense(api, f.supervisor, cat, "60000", machine_id=m)
    expense(api, f.supervisor, cat, "40000", machine_id=m)
    assert sweep(api, f.tid).signals == 0  # exactly at the threshold
    expense(api, f.supervisor, cat, "1", machine_id=m)
    assert sweep(api, f.tid).signals == 1
    [sig] = signals(f.owner, rule_code="EXPENSE_THRESHOLD_EXCEEDED")
    ev = sig["evidence"]
    assert ev["approved_and_pending_total"] == "100001.0000" and ev["threshold_per_week"] == "100000"
    assert len(ev["expense_ids"]) == 3 and ev["iso_week"].startswith("2026-W")


def test_cash_not_handed_over_age_then_amount_escalates_one_case(api: Api) -> None:
    f = setup_finance(api, "Cash Co", "CASH-1")
    r = f.accountant.post("/api/v1/tenant/cash/floats", {"staff_member_id": f.sup_staff_id, "amount": "500000"})
    assert r.status_code == 201, r.text
    t0 = api.clock.now
    api.clock.set_at(t0 + timedelta(hours=48))
    assert sweep(api, f.tid).signals == 0  # held exactly 48 h (default limit): not older
    api.clock.set_at(t0 + timedelta(hours=49))
    assert sweep(api, f.tid).signals == 1
    [case] = cases(f.owner)
    assert case["severity"] == "WARNING" and case["subject_type"] == "STAFF" and case["subject_id"] == f.sup_staff_id
    fraud_policy(f.owner, cash_outstanding_max_amount="100000")
    result = sweep(api, f.tid)
    assert (result.signals, result.cases_opened, result.cases_escalated) == (1, 0, 1)
    [case] = cases(f.owner)
    assert case["severity"] == "CRITICAL" and case["signal_count"] == 2
    limits = {s["evidence"]["limit"] for s in signals(f.owner, rule_code="CASH_NOT_HANDED_OVER")}
    assert limits == {"HELD_LONGER_THAN_LIMIT", "ABOVE_AMOUNT_LIMIT"}


def test_work_without_authorization_on_unapproved_job_and_unassigned_supervisor(api: Api) -> None:
    f = setup_finance(api, "Auth Co", "AUTH-1")
    cat = category(f, "SITE", "Site costs")
    expense_policy(f, receipt_required_above="100000000", gps_required=False, auto_approve_limit="0")
    draft = f.owner.post(
        "/api/v1/tenant/jobs",
        {"contract_id": f.c.contract_id, "job_number": "J-DRAFT", "machine_id": f.c.t.machine_id,
         "planned_start": api.clock.now.isoformat()},
    )  # fmt: skip
    assert draft.status_code == 201, draft.text
    ok = expense(api, f.supervisor, cat, "1000", job_id=f.c.job_id)  # approved job, assigned supervisor
    on_draft = expense(api, f.supervisor, cat, "2000", job_id=draft.json()["id"])
    before = (api.clock.now - timedelta(days=2)).isoformat()  # before the supervisor's assignment
    unassigned = expense(api, f.supervisor, cat, "3000", job_id=f.c.job_id, incurred_at=before)

    assert sweep(api, f.tid).signals == 2
    found = {s["evidence"]["record_id"]: s for s in signals(f.owner, rule_code="WORK_WITHOUT_AUTHORIZATION")}
    assert ok["id"] not in found
    assert found[on_draft["id"]]["evidence"]["reasons"] == ["BEFORE_JOB_AUTHORIZED"]
    assert found[on_draft["id"]]["evidence"]["job_status_now"] == "DRAFT"
    assert found[unassigned["id"]]["evidence"]["reasons"] == ["SUPERVISOR_NOT_ASSIGNED_TO_MACHINE"]
    assert found[unassigned["id"]]["staff_member_id"] == f.sup_staff_id


def test_existing_sources_link_confirmed_meter_exceptions_only(api: Api) -> None:
    f = setup_finance(api, "Meter Co", "MTR-1")
    r = f.owner.post(
        "/api/v1/tenant/meter-captures",
        capture(f.c.job_id, "OPENING", "500.0", api.clock.now, mode="MANUAL", gps={"status": "NO_FIX"}),
    )
    assert r.status_code == 201, r.text
    [exc] = f.owner.get("/api/v1/tenant/exceptions").json()["items"]
    assert exc["severity"] == "WARNING"
    assert sweep(api, f.tid).linked == 0 and feed_events(api, f.tid) >= 1  # open WARNING: not a case
    assert cases(f.owner) == []
    review = f.owner.post(f"/api/v1/tenant/exceptions/{exc['id']}/review", {"outcome": "CONFIRMED", "note": "No fix"})
    assert review.status_code == 200, review.text
    assert sweep(api, f.tid).linked == 1 and sweep(api, f.tid).linked == 0
    [case] = cases(f.owner)
    assert case["title"] == "Meter reading exception needs review" and case["subject_id"] == f.c.t.machine_id
    detail = f.owner.get(f"/api/v1/tenant/cases/{case['id']}").json()
    assert [(s["source_type"], s["code"]) for s in detail["signals"]] == [("METER_EXCEPTION", "GPS_UNAVAILABLE")]
