"""DEC-031 Phase 5 (is everyone on top of things?): the per-person scorecard with its repeat-pattern signal (M1) and
idle machines (M2: no approved machine-report hours, ADR-008). Every item is an OVERSIGHT policy switch that is off on
the platform default: nothing changes until the tenant switches it on."""

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from tests.support.api import Actor, Api
from tests.support.finance import FinCtx, cash_policy, setup_finance, tenant_sql
from tests.support.intelligence import cases, signals, sweep
from tests.support.machine_reports import idle, later, report_body, setup_reports, submit
from tests.support.meter import capture

T = "/api/v1/tenant"
C = f"{T}/cash"
OFF = ("IDLE_MACHINES", "SCORECARD")


def _ok(r: Any, status: int = 200) -> Any:
    assert r.status_code == status, r.text
    return r.json()


def _refused(r: Any, code: str) -> None:
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == code


def _oversight(f: FinCtx, **values: Any) -> None:
    _ok(
        f.owner.post(
            f"{T}/policies/OVERSIGHT/versions", {"scope": "TENANT", "values": values, "reason": "Owner oversight"}
        ),
        201,
    )


def _nav(actor: Actor) -> dict[str, Any]:
    return dict(_ok(actor.get("/api/v1/me"))["tenants"][0])


def _menus(nav: dict[str, Any]) -> set[str]:
    keys: set[str] = set()

    def walk(items: list[dict[str, Any]]) -> None:
        for m in items:
            keys.add(m["key"])
            walk(m.get("children") or [])

    walk(nav["menus"])
    return keys


# --- defaults --------------------------------------------------------------------------------------------------
def test_defaults_change_nothing(api: Api) -> None:
    f = setup_finance(api)
    eff = _ok(f.owner.get(f"{T}/policies/OVERSIGHT/effective"))["values"]
    assert (eff["scorecard_enabled"], eff["repeat_pattern_count"], eff["idle_after_days"]) == (False, None, None)
    assert eff["near_threshold_percent"] == "90" and eff["repeat_pattern_window_days"] == 30
    assert not {"unbilled_after_days", "site_checkin_required", "site_checkin_times"} & set(eff)
    nav = _nav(f.owner)
    assert set(OFF) <= set(nav["disabled_capabilities"])
    assert not {"tenant.scorecard", "tenant.idle_machines"} & _menus(nav)
    for path, code in (
        ("scorecard", "SCORECARD_DISABLED"),
        (f"scorecard/{f.sup_staff_id}", "SCORECARD_DISABLED"),
        ("idle-machines", "IDLE_MACHINES_DISABLED"),
    ):
        _refused(f.owner.get(f"{T}/{path}"), code)
    summary = _ok(f.owner.get(f"{T}/accountability/summary"))
    assert summary["idle_machines"] is None and "idle_machines" in summary["hidden_tiles"]
    # Unbilled work and site check-ins were removed (ADR-008): their settings are refused.
    for values in (
        {"unbilled_after_days": 2},
        {"site_checkin_required": True},
        {"repeat_pattern_items": ["REVENUE_DIFFERENCE"]},
    ):
        r = f.owner.post(
            f"{T}/policies/OVERSIGHT/versions", {"scope": "TENANT", "values": values, "reason": "Retired settings"}
        )
        assert r.status_code == 422, r.text
    # No pattern signal while the scorecard is off.
    api.clock.set_at(api.clock.now + timedelta(days=30))
    sweep(api, f.tid)
    assert signals(f.owner, rule_code="REPEATED_PATTERN") == []


# --- M1 scorecard ----------------------------------------------------------------------------------------------
def _collect_and_remit(f: FinCtx, at: str, amount: str, received: str) -> str:
    body = {"customer_id": f.customer_id, "amount": amount, "received_at": at, "staff_member_id": f.sup_staff_id}
    _ok(f.manager.post(f"{C}/collections", body), 201)
    h = _ok(
        f.manager.post(f"{C}/handovers", {"staff_member_id": f.sup_staff_id, "amount": amount, "handed_at": at}), 201
    )
    _ok(f.accountant.post(f"{C}/handovers/{h['id']}/decision", {"verified": True, "amount_received": received}))
    variances = _ok(f.accountant.get(f"{C}/variances", staff_member_id=f.sup_staff_id, page_size=50))["items"]
    return str(next(v["id"] for v in variances if v["source_id"] == h["id"]))


def _missing_report(f: FinCtx, day: str) -> str:
    row = tenant_sql(
        f.tid,
        "INSERT INTO meter_exception (id, tenant_id, machine_id, exception_type, severity, blocking, dedupe_key,"
        " evidence, status, created_at, sync_revision) VALUES (gen_random_uuid(), :t, :m, 'MISSING_DAILY_REPORT',"
        " 'WARNING', false, :k, CAST(:e AS jsonb), 'OPEN', now(), nextval('sync_revision_seq')) RETURNING id",
        t=f.tid,
        m=f.c.t.machine_id,
        k=f"engine:daily:{f.c.t.machine_id}:{day}",
        e=json.dumps({"day": day, "cutoff_hour": 10, "basis": "ENGINE_ACTIVITY"}),
    )
    return str(row[0][0])


def test_scorecard_items_drill_down_and_repeat_pattern_case(api: Api) -> None:
    f = setup_finance(api)  # the supervisor is assigned to the machine from 2026-11-01 09:00 UTC
    cash_policy(f, variance_case_threshold="20000")
    _oversight(f, scorecard_enabled=True, repeat_pattern_count=2, repeat_pattern_items=["CASH_DIFFERENCE"])
    assert "tenant.scorecard" in _menus(_nav(f.owner)) and "SCORECARD" not in _nav(f.owner)["disabled_capabilities"]
    # The scorecard is for the owner/manager: a supervisor is refused (a refused attempt on their scorecard).
    assert f.supervisor.get(f"{T}/scorecard").status_code == 403

    near = _collect_and_remit(f, "2026-11-01T10:00:00+00:00", "100000", "81000")  # 19,000 short: just under
    small = _collect_and_remit(f, "2026-11-01T11:00:00+00:00", "50000", "45000")
    late = _missing_report(f, "2026-11-01")
    missing = _missing_report(f, "2026-11-02")
    api.clock.set_at(datetime(2026, 11, 1, 12, 0, tzinfo=UTC))
    # A reading on the first day, after the cut-off: that day's report was late, not missing.
    _ok(f.owner.post(f"{T}/meter-captures", capture(f.c.t.machine_id, "1000", api.clock.now, mode="MANUAL")), 201)
    api.clock.set_at(datetime(2026, 11, 3, 9, 0, tzinfo=UTC))

    page = _ok(f.manager.get(f"{T}/scorecard", day_from="2026-11-01", day_to="2026-11-03"))
    row = next(r for r in page["items"] if r["staff_member_id"] == f.sup_staff_id)
    assert page["items"][0]["staff_member_id"] == f.sup_staff_id  # most items first
    assert row["staff_member_name"] == "Cash Supervisor" and row["machines"] == 1
    assert (row["cash_differences"], row["cash_differences_near_threshold"]) == (2, 1)
    assert row["cash_difference_totals"] == [{"currency": "TZS", "count": 2, "amount": "24000.0000"}]
    assert (row["daily_reports_late"], row["daily_reports_missing"]) == (1, 1)
    assert row["refused_attempts"] >= 1
    assert not {"revenue_differences", "checkins_missed", "checkins_made"} & set(row)
    assert [c["currency"] for c in row["cash_held"]] == ["TZS"]  # 24,000 counted short is still held

    detail = _ok(f.owner.get(f"{T}/scorecard/{f.sup_staff_id}", day_from="2026-11-01", day_to="2026-11-03"))
    by_item: dict[str, set[str]] = {}
    for rec in detail["records"]:
        by_item.setdefault(rec["item"], set()).add(rec["record_id"])
    assert by_item["CASH_DIFFERENCE"] == {near, small}
    assert by_item["LATE_DAILY_REPORT"] == {late} and by_item["MISSING_DAILY_REPORT"] == {missing}
    assert "REFUSED_ATTEMPT" in by_item
    near_rec = next(r for r in detail["records"] if r["record_id"] == near)
    assert near_rec["near_threshold"] is True and near_rec["record_type"] == "cash_variance"
    only = _ok(f.owner.get(f"{T}/scorecard/{f.sup_staff_id}", day_from="2026-11-01", item="CASH_DIFFERENCE"))
    assert {r["item"] for r in only["records"]} == {"CASH_DIFFERENCE"}
    assert _ok(f.owner.get(f"{T}/scorecard", q="nobody"))["items"] == []

    # Two cash differences within 30 days: one REPEATED_PATTERN signal about the person, joined into a case.
    sweep(api, f.tid)
    sweep(api, f.tid)  # idempotent
    found = signals(f.owner, rule_code="REPEATED_PATTERN")
    assert len(found) == 1 and found[0]["staff_member_id"] == f.sup_staff_id
    assert found[0]["evidence"]["item"] == "CASH_DIFFERENCE" and found[0]["evidence"]["count"] == 2
    titles = {c["title"] for c in cases(f.owner)}
    assert "Repeated items to look at for one person" in titles
    detail = _ok(f.owner.get(f"{T}/scorecard/{f.sup_staff_id}", day_from="2026-11-01"))
    pattern = next(r for r in detail["records"] if r["item"] == "PATTERN_SIGNAL")
    assert pattern["detail"]["case_id"] and detail["row"]["pattern_signals"] == 1


# --- M2 idle machines -----------------------------------------------------------------------------------------
def test_idle_machines_count_approved_machine_report_hours(api: Api) -> None:
    ctx = setup_reports(api, "Idle Co", "IDLE-1")
    f, m = ctx.f, ctx.machine_id
    _oversight(f, idle_after_days=7)
    assert "tenant.idle_machines" in _menus(_nav(f.owner))
    assert _ok(f.owner.get(f"{T}/idle-machines"))["items"] == []  # registered four days ago
    pending = submit(f.supervisor, report_body(m, "1005.0", later(api, 5), [idle(ctx.reasons["TRANSIT"], 5)]))
    worked = api.clock.now

    # A report waiting for a decision does not count: idle since the machine was registered (11 days).
    api.clock.set_at(worked + timedelta(days=7, minutes=1))
    rows = _ok(f.owner.get(f"{T}/idle-machines"))["items"]
    assert [(r["machine_id"], r["idle_days"], r["last_machine_report_id"]) for r in rows] == [(m, 11, None)]

    # Approved: its hours count from the end of the report.
    _ok(f.manager.post(f"{T}/machine-reports/{pending['id']}/approve", {"note": "Checked"}))
    rows = _ok(f.owner.get(f"{T}/idle-machines"))["items"]
    assert [(r["machine_id"], r["idle_days"], r["last_machine_report_id"]) for r in rows] == [(m, 7, pending["id"])]
    assert rows[0]["machine_code"] and rows[0]["last_machine_report_number"] == pending["report_number"]
    assert rows[0]["idle_since"].startswith(worked.date().isoformat())
    tile = _ok(f.owner.get(f"{T}/accountability/summary"))["idle_machines"]
    assert tile["count"] == 1 and tile["after_days"] == 7
    item = tile["items"][0]
    assert (item["machine_code"], item["machine_name"]) == (rows[0]["machine_code"], rows[0]["machine_name"])
    assert item["last_machine_report_number"] == pending["report_number"]

    # New approved hours: no longer idle.
    fresh = submit(f.supervisor, report_body(m, "1007.0", later(api, 2), [idle(ctx.reasons["TRANSIT"], 2)]))
    _ok(f.manager.post(f"{T}/machine-reports/{fresh['id']}/approve", {"note": "Checked"}))
    assert _ok(f.owner.get(f"{T}/idle-machines"))["items"] == []
