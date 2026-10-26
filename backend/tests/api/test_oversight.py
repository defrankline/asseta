"""DEC-031 Phase 5 (is everyone on top of things?): the per-person scorecard with its repeat-pattern signal (M1),
unbilled work and idle machines (M2) and optional site check-ins (M3). Every item is an OVERSIGHT policy switch that
is off on the platform default: nothing changes until the tenant switches it on."""

import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from asseta.core.db import get_sessionmaker
from asseta.modules.notification.reminders import run_reminders
from tests.support.api import Actor, Api
from tests.support.finance import FinCtx, cash_policy, complete_job, issue_invoice, setup_finance, tenant_sql
from tests.support.intelligence import cases, signals, sweep
from tests.support.jobs import capture
from tests.support.notify import sql

T = "/api/v1/tenant"
C = f"{T}/cash"
DEVICE = "android-oversight-0001"
OFF = ("IDLE_MACHINES", "SCORECARD", "SITE_CHECKIN", "UNBILLED_WORK")
LON, LAT = 39.28, -6.8


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


def _h(actor: Actor) -> dict[str, str]:
    return {**actor.headers(True, None), "X-Device-Id": DEVICE}


def _device(api: Api, actor: Actor) -> list[str]:
    body = {"device_id": DEVICE, "platform": "ANDROID", "app_version": "1.5.0"}
    r = api.client.post("/api/v1/sync/devices", headers=_h(actor), json=body)
    assert r.status_code in (200, 201), r.text
    return list(_ok(api.client.get("/api/v1/sync/bootstrap", headers=_h(actor)))["capabilities"])


def _push(api: Api, actor: Actor, *ops: dict[str, Any]) -> list[dict[str, Any]]:
    r = api.client.post(
        "/api/v1/sync/push",
        headers=_h(actor),
        json={"device_now": api.clock.now.isoformat(), "operations": list(ops)},
    )
    return list(_ok(r)["results"])


def _checkin_op(at: datetime, site: str | None = None, op_id: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "client_id": str(uuid.uuid4()),
        "captured_at": at.isoformat(),
        "gps": {
            "status": "FIX",
            "latitude": LAT + 0.001,
            "longitude": LON,
            "accuracy_m": 8,
            "captured_at": at.isoformat(),
        },
    }
    if site:
        payload["job_site_id"] = site
    return {
        "id": op_id or str(uuid.uuid4()),
        "op_type": "SITE_CHECKIN",
        "created_at_device": at.isoformat(),
        "payload": payload,
    }


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
    assert (eff["scorecard_enabled"], eff["repeat_pattern_count"], eff["unbilled_after_days"]) == (False, None, None)
    assert (eff["idle_after_days"], eff["site_checkin_required"], eff["site_checkin_times"]) == (None, False, [])
    assert eff["near_threshold_percent"] == "90" and eff["repeat_pattern_window_days"] == 30
    nav = _nav(f.owner)
    assert set(OFF) <= set(nav["disabled_capabilities"])
    assert not {"tenant.scorecard", "tenant.unbilled_work", "tenant.idle_machines", "tenant.site_checkins"} & _menus(
        nav
    )
    for path, code in (
        ("scorecard", "SCORECARD_DISABLED"),
        (f"scorecard/{f.sup_staff_id}", "SCORECARD_DISABLED"),
        ("unbilled-work", "UNBILLED_WORK_DISABLED"),
        ("idle-machines", "IDLE_MACHINES_DISABLED"),
        ("site-checkins", "SITE_CHECKIN_DISABLED"),
    ):
        _refused(f.owner.get(f"{T}/{path}"), code)
    _refused(f.supervisor.get(f"{T}/site-checkins/mine"), "SITE_CHECKIN_DISABLED")
    summary = _ok(f.owner.get(f"{T}/accountability/summary"))
    assert summary["unbilled_work"] is None and summary["idle_machines"] is None
    assert {"unbilled_work", "idle_machines"} <= set(summary["hidden_tiles"])
    caps = _device(api, f.supervisor)
    assert "OP_SITE_CHECKIN" not in caps
    res = _push(api, f.supervisor, _checkin_op(api.clock.now))[0]
    assert (res["status"], res["error"]["code"]) == ("CONFLICT", "SITE_CHECKIN_DISABLED")
    assert sql("SELECT count(*) FROM site_checkin")[0][0] == 0
    # A completed, unbilled job notifies nobody and the sweep raises no pattern signal.
    complete_job(api, f, f.c.job_id, "1000", "1008", 8)
    api.clock.set_at(api.clock.now + timedelta(days=30))
    run_reminders(get_sessionmaker(), api.clock.now)
    assert sql("SELECT count(*) FROM notification WHERE notification_type = 'UNBILLED_WORK'")[0][0] == 0
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
        "INSERT INTO job_exception (id, tenant_id, machine_id, exception_type, severity, blocking, dedupe_key,"
        " evidence, status, created_at, sync_revision) VALUES (gen_random_uuid(), :t, :m, 'MISSING_DAILY_REPORT',"
        " 'WARNING', false, :k, CAST(:e AS jsonb), 'OPEN', now(), nextval('sync_revision_seq')) RETURNING id",
        t=f.tid,
        m=f.c.t.machine_id,
        k=f"engine:daily:{f.c.t.machine_id}:{day}",
        e=json.dumps({"day": day, "cutoff_hour": 10, "basis": "ACTIVE_JOB"}),
    )
    return str(row[0][0])


def _revenue_difference(f: FinCtx) -> str:
    row = tenant_sql(
        f.tid,
        "INSERT INTO revenue_difference (id, tenant_id, machine_id, period_kind, period_key, period_start, period_end,"
        " local_from, local_to, currency, expected_amount, in_progress_amount, attributed_amount, difference,"
        " customer_work_hours, non_revenue_hours, unexplained_hours, unexplained_expected_amount, detail, status,"
        " policy_version, opened_at, computed_at) VALUES (gen_random_uuid(), :t, :m, 'DAY', 'DAY:2026-11-01',"
        " '2026-10-31T21:00:00+00', '2026-11-01T21:00:00+00', '2026-11-01', '2026-11-01', 'TZS', 400000, 0,"
        " 300000, 100000, 5, 0, 0, 0, '{}'::jsonb, 'OPEN', 'test', now(), now()) RETURNING id",
        t=f.tid,
        m=f.c.t.machine_id,
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
    _ok(f.owner.post(f"{T}/meter-captures", capture(f.c.job_id, "OPENING", "1000", api.clock.now, mode="MANUAL")), 201)
    revenue = _revenue_difference(f)
    api.clock.set_at(datetime(2026, 11, 3, 9, 0, tzinfo=UTC))

    page = _ok(f.manager.get(f"{T}/scorecard", day_from="2026-11-01", day_to="2026-11-03"))
    row = next(r for r in page["items"] if r["staff_member_id"] == f.sup_staff_id)
    assert page["items"][0]["staff_member_id"] == f.sup_staff_id  # most items first
    assert row["staff_member_name"] == "Cash Supervisor" and row["machines"] == 1
    assert (row["cash_differences"], row["cash_differences_near_threshold"]) == (2, 1)
    assert row["cash_difference_totals"] == [{"currency": "TZS", "count": 2, "amount": "24000.0000"}]
    assert (row["daily_reports_late"], row["daily_reports_missing"]) == (1, 1)
    assert row["revenue_differences"] == 1 and row["refused_attempts"] >= 1
    assert row["checkins_missed"] is None  # site check-ins were never required
    assert [c["currency"] for c in row["cash_held"]] == ["TZS"]  # 24,000 counted short is still held

    detail = _ok(f.owner.get(f"{T}/scorecard/{f.sup_staff_id}", day_from="2026-11-01", day_to="2026-11-03"))
    by_item: dict[str, set[str]] = {}
    for rec in detail["records"]:
        by_item.setdefault(rec["item"], set()).add(rec["record_id"])
    assert by_item["CASH_DIFFERENCE"] == {near, small}
    assert by_item["LATE_DAILY_REPORT"] == {late} and by_item["MISSING_DAILY_REPORT"] == {missing}
    assert by_item["REVENUE_DIFFERENCE"] == {revenue}
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


# --- M2 unbilled work and idle machines -----------------------------------------------------------------------
def test_unbilled_work_and_idle_machines(api: Api) -> None:
    f = setup_finance(api)
    _oversight(f, unbilled_after_days=2, idle_after_days=3)
    nav = _nav(f.owner)
    assert {"tenant.unbilled_work", "tenant.idle_machines"} <= _menus(nav)
    complete_job(api, f, f.c.job_id, "1000", "1008", 8)
    done = api.clock.now
    assert _ok(f.accountant.get(f"{T}/unbilled-work"))["items"] == []  # not two days yet
    api.clock.set_at(done + timedelta(days=2, minutes=1))
    items = _ok(f.accountant.get(f"{T}/unbilled-work"))["items"]
    assert [(i["job_id"], i["days_unbilled"], i["draft_invoice_id"]) for i in items] == [(f.c.job_id, 2, None)]
    assert items[0]["job_number"] == "J-001" and items[0]["customer_name"] == "Road Builders Ltd"
    assert Decimal(items[0]["total"]) > 0
    tile = _ok(f.owner.get(f"{T}/accountability/summary"))["unbilled_work"]
    assert (tile["count"], tile["after_days"]) == (1, 2)

    run_reminders(get_sessionmaker(), api.clock.now)
    run_reminders(get_sessionmaker(), api.clock.now + timedelta(days=1))  # once per job
    rows = sql("SELECT data, link, recipient_user_id FROM notification WHERE notification_type = 'UNBILLED_WORK'")
    assert rows and {r.link for r in rows} == {f"/tenant/jobs/{f.c.job_id}"}
    assert {(r.data["kind"], r.data["record_id"]) for r in rows} == {("JOB", f.c.job_id)}
    assert len(rows) == len({r.recipient_user_id for r in rows})  # once per recipient, not every day

    # Idle: no job and no engine hours since the job ended three days ago.
    assert _ok(f.owner.get(f"{T}/idle-machines"))["items"] == []
    api.clock.set_at(done + timedelta(days=3, minutes=1))
    idle = _ok(f.owner.get(f"{T}/idle-machines"))["items"]
    assert [(i["machine_id"], i["idle_days"], i["last_job_id"]) for i in idle] == [(f.c.t.machine_id, 3, f.c.job_id)]
    assert idle[0]["machine_code"] and idle[0]["last_job_number"] == "J-001"
    assert _ok(f.owner.get(f"{T}/accountability/summary"))["idle_machines"]["count"] == 1

    issue_invoice(f, [f.c.job_id])
    assert _ok(f.accountant.get(f"{T}/unbilled-work"))["items"] == []


# --- M3 site check-ins -----------------------------------------------------------------------------------------
def test_site_checkins_sync_schedule_and_missed(api: Api) -> None:
    f = setup_finance(api)
    o = f.owner
    site = _ok(
        o.post(
            f"{T}/job-sites", {"code": "S1", "name": "Bridge", "center": {"type": "Point", "coordinates": [LON, LAT]}}
        ),
        201,
    )
    _ok(o.post(f"{T}/jobs/{f.c.job_id}/transitions", {"action": "CANCEL", "reason": "Replaced"}))
    body = {
        "contract_id": f.c.contract_id,
        "job_number": "J-SITE",
        "machine_id": f.c.t.machine_id,
        "job_site_id": site["id"],
        "supervisor_id": f.sup_staff_id,
        "planned_start": api.clock.now.isoformat(),
    }
    job = _ok(o.post(f"{T}/jobs", body), 201)["id"]
    for action in ("SUBMIT", "APPROVE"):
        _ok(o.post(f"{T}/jobs/{job}/transitions", {"action": action}))
    t0 = datetime(2026, 11, 1, 4, 0, tzinfo=UTC)  # 07:00 local
    api.clock.set_at(t0)
    _ok(o.post(f"{T}/meter-captures", capture(job, "OPENING", "1000", t0, mode="MANUAL")), 201)
    _ok(o.post(f"{T}/jobs/{job}/transitions", {"action": "START"}))
    _oversight(
        f,
        scorecard_enabled=True,
        site_checkin_required=True,
        site_checkin_times=["09:00", "15:00"],
        site_checkin_window_minutes=60,
        site_checkin_max_distance_m=500,
    )
    caps = _device(api, f.supervisor)
    assert "OP_SITE_CHECKIN" in caps

    at = datetime(2026, 11, 1, 6, 10, tzinfo=UTC)  # 09:10 local
    api.clock.set_at(at + timedelta(minutes=1))
    op = _checkin_op(at)
    res = _push(api, f.supervisor, op)[0]
    assert res["status"] == "ACKED", res
    entity = res["result"]["entity"]
    assert (entity["job_id"], entity["job_site_id"], entity["source"]) == (job, site["id"], "SYNC")
    assert 100 < entity["distance_m"] < 130 and entity["within_distance"] is True
    assert _push(api, f.supervisor, op)[0]["status"] == "DUPLICATE"

    api.clock.set_at(datetime(2026, 11, 1, 13, 5, tzinfo=UTC))  # 16:05 local: the 15:00 window has closed
    mine = _ok(f.supervisor.get(f"{T}/site-checkins/mine", day_from="2026-11-01", day_to="2026-11-01"))
    assert mine["required"] is True and mine["times"] == ["09:00", "15:00"]
    assert [(s["status"], s["checkin_id"] is not None) for s in mine["slots"]] == [("MADE", True), ("MISSED", False)]
    assert [c["id"] for c in mine["checkins"]] == [entity["id"]]

    listed = _ok(o.get(f"{T}/site-checkins", staff_id=f.sup_staff_id))["items"]
    assert [(c["id"], c["staff_member_name"], c["job_site_name"]) for c in listed] == [
        (entity["id"], "Cash Supervisor", "Bridge")
    ]
    assert _ok(o.get(f"{T}/site-checkins/{entity['id']}"))["job_number"] == "J-SITE"
    row = _ok(o.get(f"{T}/scorecard/{f.sup_staff_id}", day_from="2026-11-01", day_to="2026-11-01"))["row"]
    assert (row["checkins_made"], row["checkins_missed"]) == (1, 1)

    # Online check-in (web field work) is the same record; the office list sees it too.
    online = {
        "client_id": str(uuid.uuid4()),
        "captured_at": api.clock.now.isoformat(),
        "gps": {"status": "NO_FIX"},
        "job_site_id": site["id"],
    }
    made = _ok(f.supervisor.post(f"{T}/site-checkins", online), 201)
    assert (made["distance_m"], made["within_distance"], made["source"]) == (None, None, "API")
    assert _ok(f.supervisor.post(f"{T}/site-checkins", online), 201)["id"] == made["id"]  # replay

    # Switched off: no longer announced, queued check-ins are kept for review and not applied.
    _oversight(f, site_checkin_required=False)
    assert "OP_SITE_CHECKIN" not in _device(api, f.supervisor)
    res = _push(api, f.supervisor, _checkin_op(api.clock.now))[0]
    assert (res["status"], res["error"]["code"]) == ("CONFLICT", "SITE_CHECKIN_DISABLED")
