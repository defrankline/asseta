"""Gate 6D: baseline insights (fuel efficiency, utilisation, cash-flow trend) with honest INSUFFICIENT_DATA, and the
audit of manual overrides of OCR readings."""

import json
from datetime import timedelta
from decimal import Decimal
from typing import Any

from tests.support.api import Actor, Api
from tests.support.finance import category, expense_policy, gps, role, setup_finance
from tests.support.intelligence import expense
from tests.support.jobs import capture, new_job, photo, setup_job
from tests.support.ml import fleet_for, last_week_end, shifted_week, store

OVERRIDES = "/api/v1/tenant/insights/manual-overrides"


def get(actor: Actor, path: str, **params: Any) -> dict[str, Any]:
    r = actor.get(path, **params)
    assert r.status_code == 200, r.text
    out: dict[str, Any] = r.json()
    assert "fraud" not in json.dumps(out).lower()
    return out


def test_fresh_tenant_gets_insufficient_data_with_what_is_missing(api: Api) -> None:
    t = api.onboard("Fresh Ins", price="1000")
    owner = t["owner"]
    api.add_machines(owner, 2)
    body = get(owner, "/api/v1/tenant/insights")
    assert len(body["fuel_efficiency"]) == len(body["utilisation"]) == 2 and body["method"]
    for item in body["fuel_efficiency"]:
        assert item["status"] == "INSUFFICIENT_DATA" and item["current_litres_per_hour"] is None
        assert item["min_weeks_required"] == 4 and any("at least 4" in m for m in item["missing"])
    for item in body["utilisation"]:
        assert item["status"] == "INSUFFICIENT_DATA" and item["hours_per_available_day"] is None
        assert item["missing"] == ["0 observed weeks with meter or engine hours; at least 4 needed."]
    flow = body["cash_flow"]
    assert flow["status"] == "INSUFFICIENT_DATA" and flow["min_weeks_required"] == 6 and flow["trend"] is None
    assert flow["missing"] == ["No verified receipts or approved expenses recorded yet."]


def test_machine_insights_from_weekly_snapshots(api: Api) -> None:
    t = api.onboard("Fleet Ins", price="1000")
    owner, tid = t["owner"], t["tenant"]["id"]
    machines = api.add_machines(owner, 5)
    snaps = fleet_for(tid, machines, last_week_end(api.clock.now) - timedelta(weeks=1), anomaly_rate=0.0)
    unusual = shifted_week([s for s in snaps if s.entity_id == machines[0]], litres_per_meter_hour=3.0)
    usual = shifted_week([s for s in snaps if s.entity_id != machines[0]])
    store(tid, snaps + unusual + usual, api.clock.now)

    body = get(owner, "/api/v1/tenant/insights")
    fuel = {f["machine_id"]: f for f in body["fuel_efficiency"]}
    hit = fuel[machines[0]]
    assert hit["status"] == "READY" and hit["outside_usual_range"] is True and hit["missing"] == []
    assert hit["current_litres_per_hour"] > hit["band_high"] > hit["median_litres_per_hour"] > hit["band_low"] >= 0
    assert "outside this machine's usual range" in hit["message"] and hit["weeks_observed"] >= 4
    assert all(f["status"] == "READY" for f in fuel.values())
    for u in body["utilisation"]:
        assert u["status"] == "READY" and u["hours_per_available_day"] > 0 and u["trend"] in ("UP", "DOWN", "FLAT")
        assert u["available_days"] == 7 * u["weeks_observed"] == 7 * len(u["weekly"]) and u["weeks_observed"] == 12
        assert {w["source"] for w in u["weekly"]} <= {"meter", "engine", "none"}

    accountant = role(api, tid, "accountant", "acct-ins")
    assert accountant.get("/api/v1/tenant/insights").status_code == 403  # no tenant.fleet.read
    assert get(accountant, "/api/v1/tenant/insights/cash-flow")["status"] == "INSUFFICIENT_DATA"
    supervisor = role(api, tid, "supervisor", "sup-ins")
    assert get(supervisor, "/api/v1/tenant/insights")["cash_flow"] is None  # no tenant.finance.report
    assert supervisor.get("/api/v1/tenant/insights/cash-flow").status_code == 403
    other = api.onboard("Other Ins", price="1000")["owner"]
    assert get(other, "/api/v1/tenant/insights")["fuel_efficiency"] == []  # tenant-scoped


def test_cash_flow_trend_from_verified_receipts_and_approved_expenses(api: Api) -> None:
    f = setup_finance(api, "Flow Co", "FLOW-1")
    expense_policy(f, receipt_required_above="100000000", auto_approve_limit="100000000")
    ops = category(f, "OPS", "Operations")
    start = api.clock.now
    for week in range(7):
        api.clock.set_at(start + timedelta(weeks=week))
        body = {"customer_id": f.customer_id, "amount": str(100000 * (week + 1)), "method": "BANK"}
        body |= {"reference": f"REF-{week}", "received_at": api.clock.now.isoformat()}
        paid = f.accountant.post("/api/v1/tenant/customer-payments", body).json()
        decided = f.owner.post(f"/api/v1/tenant/customer-payments/{paid['id']}/decision", {"verified": True})
        assert decided.json()["status"] == "VERIFIED", decided.text
        assert expense(api, f.owner, ops, "20000", gps=gps(api.clock.now))["status"] == "APPROVED"
    claimed = {"customer_id": f.customer_id, "amount": "999999", "method": "BANK", "reference": "UNVERIFIED"}
    f.accountant.post("/api/v1/tenant/customer-payments", claimed | {"received_at": api.clock.now.isoformat()})
    api.clock.set_at(start + timedelta(weeks=7, days=1))

    flow = get(f.accountant, "/api/v1/tenant/insights/cash-flow")
    assert flow["status"] == "READY" and flow["trend"] == "UP" and flow["currency"] == "TZS"
    assert flow["weeks_observed"] >= 6 and Decimal(flow["trend_per_week"]) > 0 and flow["missing"] == []
    receipts = sum(Decimal(w["receipts"]) for w in flow["weeks"])
    assert receipts == Decimal(100000 * sum(range(1, 8)))  # verified only: the claimed payment is excluded
    assert sum(Decimal(w["expenses"]) for w in flow["weeks"]) == Decimal(7 * 20000)
    assert all(Decimal(w["net"]) == Decimal(w["receipts"]) - Decimal(w["expenses"]) for w in flow["weeks"])
    assert get(f.owner, "/api/v1/tenant/insights")["cash_flow"]["status"] == "READY"


def test_manual_override_audit_lists_ocr_vs_entered_and_is_tenant_isolated(api: Api) -> None:
    c = setup_job(api, "Ocr Co", "OCR-1")
    o, now, tid = c.owner, api.clock.now, c.t.tenant["tenant"]["id"]
    sup = Actor(api, "sup-ocr", [f"/tenants/{tid}/supervisor"], tid, email="sup-ocr@example.com")
    corrected = capture(c.job_id, "OPENING", "70.0", now, photo_id=photo(api, sup), confidence=0.4, ocr="78.0")
    assert sup.post("/api/v1/tenant/meter-captures", corrected).status_code == 201
    policy = {"opening_mode": "MANUAL", "closing_mode": "MANUAL", "manual_photo_required": False}
    r = o.post(
        "/api/v1/tenant/policies/METER_CAPTURE/versions",
        {"scope": "TENANT", "values": policy, "reason": "Manual entry"},
    )
    assert r.status_code == 201, r.text
    other_machine = o.post("/api/v1/tenant/machines", {"asset_code": "OCR-2", "name": "Loader"}).json()["id"]
    job2 = new_job(api, c, "J-002", machine_id=other_machine, rate="90000")
    later = now + timedelta(hours=1)
    manual = capture(job2, "OPENING", "120.5", later, mode="MANUAL", ocr="120.5")
    assert sup.post("/api/v1/tenant/meter-captures", manual).status_code == 201

    report = get(o, OVERRIDES)
    assert report["summary"] == {
        "total": 2,
        "manual_corrections": 1,
        "manual_mode_with_ocr": 1,
        "value_differs": 1,
        "exceptions_open": 1,
    }
    first, second = report["items"]  # newest first
    assert (second["capture_id"], second["kind"], second["capture_mode"]) == (corrected["id"], "OPENING", "AUTOMATIC")
    assert Decimal(second["ocr_value"]) == 78 and Decimal(second["entered_value"]) == 70
    assert Decimal(second["difference"]) == -8 and second["ocr_confidence"] == 0.4 and second["manually_corrected"]
    assert second["exception_id"] and second["exception_status"] == "OPEN" and second["captured_by_user_id"]
    assert second["machine_id"] == c.t.machine_id and second["job_number"] == "J-001" and second["asset_code"]
    assert (first["capture_mode"], first["manually_corrected"], first["machine_id"]) == ("MANUAL", False, other_machine)
    assert Decimal(first["difference"]) == 0 and first["exception_id"] is None

    assert get(o, OVERRIDES, machine_id=other_machine)["total"] == 1
    assert get(o, OVERRIDES, user_id=second["captured_by_user_id"])["total"] == 2
    window = {"captured_from": (now + timedelta(minutes=30)).isoformat(), "captured_to": later.isoformat()}
    assert get(o, OVERRIDES, **window)["total"] == 0  # captured_to is exclusive
    assert get(o, OVERRIDES, page_size=1)["items"][0]["capture_id"] == manual["id"]
    assert get(sup, OVERRIDES)["total"] == 2  # supervisors hold tenant.meter.read
    assert role(api, tid, "accountant", "acct-ocr").get(OVERRIDES).status_code == 403
    other = api.onboard("Other Ocr", price="1000")["owner"]
    assert get(other, OVERRIDES)["summary"]["total"] == 0  # tenant-isolated
