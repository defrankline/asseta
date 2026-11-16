"""Gate 6 (R1-H): each deterministic detector fires with fact/threshold evidence, stays silent at the boundary,
and re-running is idempotent (dedupe key; one case link per signal)."""

from datetime import timedelta

from tests.support.api import Api
from tests.support.finance import category, expense_policy, setup_finance
from tests.support.intelligence import cases, expense, feed_events, fraud_policy, receipt, signals, sweep
from tests.support.machine_reports import T, idle, later, ok, report_body, setup_reports, submit
from tests.support.meter import capture, unique_jpeg


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


def test_fuel_allowance_per_approved_machine_report_and_machine_override(api: Api) -> None:
    ctx = setup_reports(api, "Fuel Co", "FUEL-1")
    f, m = ctx.f, ctx.machine_id
    t0 = api.clock.now
    for litres, kind in (("85", "USAGE"), ("40", "ISSUE")):
        body = {"event_type": kind, "litres": litres, "machine_id": m}
        body |= {"occurred_at": (t0 + timedelta(hours=2)).isoformat(), "unit_price": "3000"}
        r = f.supervisor.post("/api/v1/tenant/fuel-events", body)
        assert r.status_code == 201, r.text
    at = later(api, 9)
    rep = submit(f.supervisor, report_body(m, "1008.0", at, [idle(ctx.reasons["IDLE_ON_SITE"], 8)]))  # 8 meter hours
    fraud_policy(f.owner, scope="MACHINE", ref=m, fuel_max_litres_per_meter_hour="10")
    assert sweep(api, f.tid).signals == 0  # the report is not approved yet: nothing to judge
    ok(f.manager.post(f"{T}/machine-reports/{rep['id']}/approve", {}))
    fraud_policy(f.owner, scope="MACHINE", ref=m, fuel_max_litres_per_meter_hour="10.625")  # 85 l / 8 h: not above
    assert sweep(api, f.tid).signals == 0
    fraud_policy(f.owner, scope="MACHINE", ref=m, fuel_max_litres_per_meter_hour="10")
    assert sweep(api, f.tid).signals == 1
    assert sweep(api, f.tid).signals == 0  # idempotent (one signal per report)
    [sig] = signals(f.owner, rule_code="FUEL_ALLOWANCE_EXCEEDED")
    ev = sig["evidence"]
    assert (ev["meter_hours"], ev["litres_used"], ev["litres_into_machine"]) == ("8.00", "85.000", "40.000")
    assert ev["litres_per_meter_hour"] == "10.625" and ev["allowance_litres_per_meter_hour"] == "10"
    assert ev["machine_report_number"] == rep["report_number"] and sig["subject_id"] == m
    assert sig["subject_type"] == "MACHINE" and ".M" in sig["policy_version"]


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


def test_existing_sources_link_confirmed_meter_exceptions_only(api: Api) -> None:
    f = setup_finance(api, "Meter Co", "MTR-1")
    r = f.owner.post(
        "/api/v1/tenant/meter-captures",
        capture(f.c.t.machine_id, "500.0", api.clock.now, mode="MANUAL", gps={"status": "NO_FIX"}),
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
