"""Go-live setup checklist: every step is computed live from the tenant's own data (never ticked by hand); the owner
only marks steps not needed, confirms the default controls and dismisses the banner (append-only, audited). Steps for
switched-off capabilities are NOT_APPLICABLE and left out of the total. /me carries the progress for a banner."""

from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy.exc import ProgrammingError

from tests.support.api import Actor, Api
from tests.support.finance import FinCtx, setup_finance, tenant_sql
from tests.support.notify import sql

T = "/api/v1/tenant"
S = f"{T}/setup-checklist"
KEYS = [
    "COMPANY_SETTINGS",
    "PEOPLE",
    "MACHINE_TYPES_AND_RATES",
    "MACHINES",
    "TRACKERS",
    "SITES",
    "CUSTOMERS_AND_CONTRACTS",
    "CONTROLS_CHOSEN",
    "REASON_LISTS",
    "DEPOSIT_ACCOUNTS",
    "METER_BASELINES",
    "FIELD_APP_SIGNED_IN",
    "FIRST_JOB",
]


def _ok(r: Any, status: int = 200) -> Any:
    assert r.status_code == status, r.text
    return r.json()


def _steps(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {s["key"]: s for s in body["steps"]}


def _status(body: dict[str, Any]) -> dict[str, str]:
    return {s["key"]: s["status"] for s in body["steps"]}


def _me(actor: Actor) -> dict[str, Any]:
    return dict(_ok(actor.get("/api/v1/me"))["tenants"][0])


def _menus(nav: dict[str, Any]) -> set[str]:
    return {m["key"] for m in nav["menus"]}


def _invite(api: Api, owner: Actor, tid: str, email: str, role_key: str) -> Actor:
    _ok(
        owner.post(
            f"{T}/access/members", {"email": email, "first_name": "New", "last_name": "Person", "role_key": role_key}
        ),
        201,
    )
    return api.tenant_user(email, tid)


def test_fresh_tenant_all_todo(api: Api) -> None:
    a = api.onboard("Fresh Co", price="1")
    owner, tid = a["owner"], a["tenant"]["id"]
    body = _ok(owner.get(S))
    assert [s["key"] for s in body["steps"]] == KEYS
    assert [s["order"] for s in body["steps"]] == list(range(1, 14))
    # Company settings come from onboarding (time zone + currency); everything else is still to do.
    assert _status(body) == {k: "DONE" if k == "COMPANY_SETTINGS" else "TODO" for k in KEYS}
    assert (body["steps_done"], body["steps_total"], body["percent"], body["complete"]) == (1, 13, 7, False)
    assert body["dismissed"] is False
    steps = _steps(body)
    for s in body["steps"]:
        assert s["title"] and s["description"] and s["link"].startswith("/tenant/") and s["required_permission"]
    assert steps["MACHINES"]["link"] == "/tenant/machines"
    assert steps["METER_BASELINES"]["link"] == "/tenant/meter-baselines?missing=true"
    assert (steps["METER_BASELINES"]["done_count"], steps["METER_BASELINES"]["total_count"]) == (0, 0)
    people = {c["key"]: c for c in steps["PEOPLE"]["checks"]}
    assert people["APPROVERS"]["done_count"] == 1 and people["APPROVERS"]["total_count"] == 2  # the owner only
    assert people["FIELD_USERS"]["done"] is False
    assert {c["key"] for c in steps["REASON_LISTS"]["checks"]} == {
        "HOURS_REASONS",
        "ENGINE_HOUR_REASONS",
        "CASH_REASONS",
    }  # revenue checks are off by default: their list is not asked for
    assert steps["SITES"]["checks"][1]["optional"] is True
    # /me carries the banner figures; the menu sits in Overview.
    nav = _me(owner)
    assert (nav["setup_complete"], nav["setup_percent"]) == (False, 7)
    assert (nav["setup_steps_done"], nav["setup_steps_total"], nav["setup_dismissed"]) == (1, 13, False)
    assert "tenant.setup" in _menus(nav)
    menu = next(m for m in nav["menus"] if m["key"] == "tenant.setup")
    assert (menu["path"], menu["group"], menu["label"]) == ("/tenant/setup", "tenant.overview", "Go-live checklist")
    # A supervisor neither reads it nor gets the banner figures.
    sup = _invite(api, owner, tid, "sup@fresh.example.com", "supervisor")
    assert sup.get(S).status_code == 403
    assert sup.post(f"{S}/dismiss").status_code == 403
    snav = _me(sup)
    assert snav["setup_complete"] is None and snav["setup_steps_total"] is None
    assert "tenant.setup" not in _menus(snav)


def _complete(api: Api, f: FinCtx) -> None:
    """Every remaining step done with real data (setup_finance already has a tracked, enrolled, rated machine, a
    customer with an active contract, a tenant policy version and an approved job)."""
    o, tid = f.owner, f.tid
    approver = _invite(api, o, tid, "partner@hire.example.com", "owner")  # a second person who can approve
    sup = _invite(api, o, tid, "sup@hire.example.com", "supervisor")
    _ok(o.post(f"{T}/staff", {"full_name": "Field Sup", "kind": "SUPERVISOR", "keycloak_subject": sup.subject}), 201)
    point = {"type": "Point", "coordinates": [39.28, -6.8]}
    _ok(o.post(f"{T}/job-sites", {"code": "S1", "name": "Bridge", "center": point}), 201)
    _ok(o.post(f"{T}/hours-reason-codes", {"kind": "DISCOUNT", "code": "VOL", "label": "Volume"}), 201)
    _ok(o.post(f"{T}/engine-hour-reasons", {"kind": "VARIANCE_REASON", "code": "FAULT", "name": "Meter fault"}), 201)
    _ok(o.post(f"{T}/cash/reasons", {"kind": "VARIANCE", "label": "Counting error"}), 201)
    _ok(o.post(f"{T}/deposit-accounts", {"name": "Main bank", "account_type": "BANK"}), 201)
    at = api.clock.now - timedelta(hours=1)
    proposed = _ok(
        o.post(
            f"{T}/meter-baselines",
            {"machine_id": f.c.t.machine_id, "reading": "1000", "captured_at": at.isoformat(), "note": "Initial"},
        ),
        201,
    )
    _ok(approver.post(f"{T}/meter-baselines/{proposed['id']}/decision", {"decision": "APPROVE", "note": "Checked"}))
    device = {"device_id": "android-setup-0001", "platform": "ANDROID", "app_version": "1.5.0"}
    r = api.client.post(
        "/api/v1/sync/devices", headers={**sup.headers(True, None), "X-Device-Id": device["device_id"]}, json=device
    )
    assert r.status_code in (200, 201), r.text


def test_fully_set_up_tenant_is_complete(api: Api) -> None:
    f = setup_finance(api)
    before = _ok(f.owner.get(S))
    assert _status(before)["FIRST_JOB"] == "DONE" and _status(before)["TRACKERS"] == "DONE"
    assert _status(before)["PEOPLE"] == "TODO"
    _complete(api, f)
    body = _ok(f.owner.get(S))
    assert _status(body) == dict.fromkeys(KEYS, "DONE"), _status(body)
    assert (body["steps_done"], body["steps_total"], body["percent"], body["complete"]) == (13, 13, 100, True)
    steps = _steps(body)
    assert (steps["METER_BASELINES"]["done_count"], steps["METER_BASELINES"]["total_count"]) == (1, 1)
    assert (steps["TRACKERS"]["done_count"], steps["TRACKERS"]["total_count"]) == (1, 1)
    people = {c["key"]: c for c in steps["PEOPLE"]["checks"]}
    assert people["APPROVERS"]["done_count"] == 2 and people["FIELD_USERS_LINKED"]["done"] is True
    nav = _me(f.owner)
    assert (nav["setup_complete"], nav["setup_percent"], nav["setup_steps_done"]) == (True, 100, 13)
    # The manager template reads (and manages) the checklist too.
    assert _ok(f.manager.get(S))["complete"] is True
    # Live: a new machine without tracker/baseline reopens those steps with counts and the exact page.
    api.add_machines(f.owner, 1, prefix="NEW")
    again = _steps(_ok(f.owner.get(S)))
    assert again["METER_BASELINES"]["status"] == "TODO"
    assert (again["METER_BASELINES"]["done_count"], again["METER_BASELINES"]["total_count"]) == (1, 2)
    assert again["TRACKERS"]["status"] == "TODO"
    assert again["TRACKERS"]["link"] == "/tenant/machines?missing=tracker"


def test_capability_off_steps_not_applicable(api: Api) -> None:
    f = setup_finance(api)
    for ptype in ("CASH_CUSTODY", "ENGINE_HOURS", "CUSTOMER_HOURS"):
        _ok(
            f.owner.post(
                f"{T}/policies/{ptype}/versions",
                {"scope": "TENANT", "values": {"enabled": False}, "reason": "Not used"},
            ),
            201,
        )
    body = _ok(f.owner.get(S))
    status = _status(body)
    assert status["DEPOSIT_ACCOUNTS"] == status["METER_BASELINES"] == status["REASON_LISTS"] == "NOT_APPLICABLE"
    assert body["steps_total"] == 10
    assert sum(1 for s in status.values() if s in ("DONE", "NOT_NEEDED")) == body["steps_done"]
    # Revenue checks on: the reason-list step applies again, asking only for revenue reasons.
    _ok(
        f.owner.post(
            f"{T}/policies/REVENUE_RECONCILIATION/versions",
            {"scope": "TENANT", "values": {"enabled": True}, "reason": "Revenue checks on"},
        ),
        201,
    )
    reasons = _steps(_ok(f.owner.get(S)))["REASON_LISTS"]
    assert reasons["status"] == "TODO" and [c["key"] for c in reasons["checks"]] == ["REVENUE_REASONS"]
    assert reasons["link"] == "/tenant/revenue-reasons"


def test_not_needed_marks_confirm_controls_and_dismiss(api: Api) -> None:
    a = api.onboard("Marks Co", price="1")
    owner, tid = a["owner"], a["tenant"]["id"]
    body = _ok(owner.post(f"{S}/steps/TRACKERS/not-needed", {"reason": "We do not fit trackers yet"}))
    trackers = _steps(body)["TRACKERS"]
    assert trackers["status"] == "NOT_NEEDED" and trackers["not_needed"]["reason"] == "We do not fit trackers yet"
    assert trackers["not_needed"]["marked_by_name"]
    assert body["steps_done"] == 2 and body["steps_total"] == 13
    # Marking again is a no-op; required steps cannot be skipped; a reason is needed.
    _ok(owner.post(f"{S}/steps/TRACKERS/not-needed", {"reason": "Again please"}))
    refused = owner.post(f"{S}/steps/MACHINES/not-needed", {"reason": "No machines"})
    assert refused.status_code == 422 and refused.json()["error"]["code"] == "SETUP_STEP_REQUIRED"
    assert owner.post(f"{S}/steps/TRACKERS/not-needed", {}).status_code == 422
    assert owner.post(f"{S}/steps/NOPE/not-needed", {"reason": "Unknown"}).status_code == 422
    # Undo.
    r = api.client.delete(f"{S}/steps/TRACKERS/not-needed", headers=owner.headers(True, None))
    assert r.status_code == 200, r.text
    assert _steps(r.json())["TRACKERS"]["status"] == "TODO" and r.json()["steps_done"] == 1
    # "The default controls are fine" completes CONTROLS_CHOSEN without a policy change.
    body = _ok(owner.post(f"{S}/confirm-controls", {"note": "Defaults reviewed"}))
    assert _steps(body)["CONTROLS_CHOSEN"]["status"] == "DONE" and body["controls_confirmed_by_name"]
    # Dismiss / show again, reflected in /me.
    body = _ok(owner.post(f"{S}/dismiss"))
    assert body["dismissed"] is True and body["dismissed_by_name"]
    assert _me(owner)["setup_dismissed"] is True
    r = api.client.delete(f"{S}/dismiss", headers=owner.headers(True, None))
    assert r.status_code == 200 and r.json()["dismissed"] is False
    # Append-only and audited.
    rows = tenant_sql(tid, "SELECT action, step_key FROM tenant_setup_choice ORDER BY seq")
    assert [tuple(x) for x in rows] == [
        ("STEP_NOT_NEEDED", "TRACKERS"),
        ("STEP_NEEDED", "TRACKERS"),
        ("CONTROLS_CONFIRMED", None),
        ("DISMISSED", None),
        ("UNDISMISSED", None),
    ]
    audited = sql("SELECT count(*) FROM audit_event WHERE action LIKE 'tenant.setup.%'")[0][0]
    assert audited == 5
    with pytest.raises(ProgrammingError, match="permission denied"):
        tenant_sql(tid, "UPDATE tenant_setup_choice SET reason = 'changed'")
    with pytest.raises(ProgrammingError, match="appended, never changed"):
        sql("UPDATE tenant_setup_choice SET reason = 'changed'")  # even the owner role: guard trigger


def test_tenant_isolation(api: Api) -> None:
    f = setup_finance(api)
    other = api.onboard("Other Co", price="1")
    o2 = other["owner"]
    _ok(o2.post(f"{S}/steps/TRACKERS/not-needed", {"reason": "Other tenant choice"}))
    _ok(o2.post(f"{S}/confirm-controls", {}))
    # The other tenant's choices and data never show up here, and vice versa.
    mine = _ok(f.owner.get(S))
    assert _status(mine)["TRACKERS"] == "DONE" and _steps(mine)["TRACKERS"]["not_needed"] is None
    assert mine["controls_confirmed_by"] is None
    theirs = _ok(o2.get(S))
    assert _status(theirs)["MACHINES"] == "TODO" and _status(theirs)["FIRST_JOB"] == "TODO"
    assert _status(theirs)["TRACKERS"] == "NOT_NEEDED"
    # A user of one tenant cannot read another tenant's checklist.
    assert f.owner.get(S, tenant=other["tenant"]["id"]).status_code in (403, 404)
    assert tenant_sql(f.tid, "SELECT count(*) FROM tenant_setup_choice")[0][0] == 0


def test_machine_list_carries_setup_state_and_missing_filters(api: Api) -> None:
    """The checklist's 'machines missing a tracker / enrollment' links land on a server-side filter; every machine
    response says whether it is enrolled today and which tracker is its primary one."""
    f = setup_finance(api, "Fleet Setup Co", "FSET-1")
    o, tracked = f.owner, f.c.t.machine_id
    bare = _ok(o.post(f"{T}/machines", {"asset_code": "EX-BARE", "name": "Bare excavator"}), 201)
    assert (bare["billing_enrolled"], bare["primary_tracker_id"], bare["primary_tracker_label"]) == (False, None, None)
    parked = _ok(o.post(f"{T}/machines", {"asset_code": "EX-PARK", "name": "Parked excavator"}), 201)
    _ok(o.put(f"{T}/machines/{parked['id']}", {"name": "Parked excavator", "status": "OUT_OF_SERVICE", "version": 1}))

    items = {m["id"]: m for m in _ok(o.get(f"{T}/machines"))["items"]}
    assert items[tracked]["billing_enrolled"] is True
    assert items[tracked]["primary_tracker_id"] is not None and items[tracked]["primary_tracker_label"]
    assert items[tracked]["primary_tracker_label"] == next(
        t["label"] for t in _ok(o.get(f"{T}/trackers"))["items"] if t["id"] == items[tracked]["primary_tracker_id"]
    )
    assert items[bare["id"]]["billing_enrolled"] is False and items[bare["id"]]["primary_tracker_id"] is None
    single = _ok(o.get(f"{T}/machines/{tracked}"))
    assert (single["billing_enrolled"], single["primary_tracker_id"]) == (True, items[tracked]["primary_tracker_id"])

    # missing=… lists ACTIVE machines only (the checklist counts active ones); an explicit status overrides that.
    for missing in ("tracker", "enrollment"):
        page = _ok(o.get(f"{T}/machines", missing=missing))
        assert [m["id"] for m in page["items"]] == [bare["id"]] and page["total"] == 1
        out = _ok(o.get(f"{T}/machines", missing=missing, status="OUT_OF_SERVICE"))
        assert [m["id"] for m in out["items"]] == [parked["id"]]
    assert o.get(f"{T}/machines", missing="nothing").status_code == 422
    # Search and paging still apply on top of the filter.
    assert _ok(o.get(f"{T}/machines", missing="tracker", q="zzz-none"))["total"] == 0

    # The checklist's links are exactly these filters.
    trackers_step = _steps(_ok(o.get(S)))["TRACKERS"]
    links = {c["link"] for c in trackers_step["checks"]}
    assert {"/tenant/machines?missing=tracker", "/tenant/machines?missing=enrollment"} <= links
