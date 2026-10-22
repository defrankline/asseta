"""Record lifecycle for fleet master data: details, optimistic edits, deactivate/reactivate (never deleted),
default-hidden lists, integrity refusals, tenant isolation and permission denial."""

from datetime import timedelta
from typing import Any

from tests.support.api import Actor, Api
from tests.support.jobs import setup_job

T = "/api/v1/tenant"
REASON = {"reason": "No longer used"}


def _accountant(api: Api, tid: str) -> Actor:
    """A tenant role that reads fleet reference data (DEC-023) but may not change it."""
    return Actor(api, "acct-lifecycle", [f"/tenants/{tid}/accountant"], tid, email="acct@lifecycle.example.com")


def _operator(api: Api, tid: str) -> Actor:
    """A tenant role without fleet permissions."""
    return Actor(api, "op-lifecycle", [f"/tenants/{tid}/operator"], tid, email="op@lifecycle.example.com")


def _ids(rows: list[dict[str, Any]]) -> set[str]:
    return {r["id"] for r in rows}


def test_machine_category_and_area_lifecycle(api: Api) -> None:
    t = api.onboard("Ref Co", price="1")
    o, tid = t["owner"], t["tenant"]["id"]
    cat = o.post(f"{T}/machine-categories", {"name": "Excavators"}).json()
    assert (cat["is_active"], cat["version"]) == (True, 1)
    assert o.get(f"{T}/machine-categories/{cat['id']}").json()["name"] == "Excavators"

    upd = o.put(f"{T}/machine-categories/{cat['id']}", {"name": "Crawler excavators", "version": 1})
    assert upd.status_code == 200 and upd.json()["version"] == 2
    stale = o.put(f"{T}/machine-categories/{cat['id']}", {"name": "Lost update", "version": 1})
    assert (stale.status_code, stale.json()["error"]["code"]) == (409, "STALE_VERSION")
    other = o.post(f"{T}/machine-categories", {"name": "Graders"}).json()
    dup = o.put(f"{T}/machine-categories/{other['id']}", {"name": "Crawler excavators", "version": 1})
    assert dup.json()["error"]["code"] == "DUPLICATE_CATEGORY"

    m = o.post(f"{T}/machines", {"asset_code": "EX-1", "name": "CAT 320", "category_id": cat["id"]}).json()
    off = o.post(f"{T}/machine-categories/{cat['id']}/deactivate", REASON)
    assert off.status_code == 200
    body = off.json()
    assert (body["is_active"], body["deactivation_reason"]) == (False, "No longer used") and body["deactivated_at"]
    again = o.post(f"{T}/machine-categories/{cat['id']}/deactivate", REASON)
    assert (again.status_code, again.json()["error"]["code"]) == (409, "ALREADY_INACTIVE")
    assert cat["id"] not in _ids(o.get(f"{T}/machine-categories").json())  # hidden from pickers
    assert cat["id"] in _ids(o.get(f"{T}/machine-categories", include_inactive="true").json())
    assert o.get(f"{T}/machine-categories/{cat['id']}").status_code == 200  # details still resolvable
    refused = o.post(f"{T}/machines", {"asset_code": "EX-2", "name": "New", "category_id": cat["id"]})
    assert refused.json()["error"]["code"] == "CATEGORY_INACTIVE"
    keep = o.get(f"{T}/machines/{m['id']}").json()  # existing machine keeps (and can re-save) its category
    keys = ("name", "category_id", "operating_area_id", "meter_decimal_places", "ownership")
    resave = o.put(f"{T}/machines/{m['id']}", {**{k: keep[k] for k in keys}, "status": "ACTIVE", "version": 1})
    assert resave.status_code == 200, resave.text
    on = o.post(f"{T}/machine-categories/{cat['id']}/reactivate", {"reason": "Back in the fleet"})
    assert on.json()["is_active"] is True and on.json()["deactivated_at"] is None

    area = o.post(f"{T}/operating-areas", {"code": "DSM", "name": "Dar"}).json()
    assert (
        o.put(f"{T}/operating-areas/{area['id']}", {"code": "DSM", "name": "Dar es Salaam", "version": 1}).json()[
            "version"
        ]
        == 2
    )
    assert (
        o.post(f"{T}/operating-areas/{area['id']}/deactivate", {**REASON, "version": 1}).json()["error"]["code"]
        == "STALE_VERSION"
    )
    assert o.post(f"{T}/operating-areas/{area['id']}/deactivate", {**REASON, "version": 2}).status_code == 200
    assert o.get(f"{T}/operating-areas").json() == []
    assert len(o.get(f"{T}/operating-areas", include_inactive="true").json()) == 1
    refused = o.post(f"{T}/machines", {"asset_code": "EX-3", "name": "N", "operating_area_id": area["id"]})
    assert refused.json()["error"]["code"] == "AREA_INACTIVE"
    assert o.post(f"{T}/operating-areas/{area['id']}/reactivate", {"reason": "Reopened depot"}).status_code == 200

    # Tenant isolation and permission denial.
    stranger = api.onboard("Ref Other", price="1")["owner"]
    assert stranger.get(f"{T}/machine-categories/{cat['id']}").status_code == 404
    assert stranger.post(f"{T}/operating-areas/{area['id']}/deactivate", REASON).status_code == 404
    acct = _accountant(api, tid)
    assert acct.get(f"{T}/machine-categories/{cat['id']}").status_code == 200  # read-only reference data
    assert _operator(api, tid).get(f"{T}/machine-categories/{cat['id']}").status_code == 403
    assert acct.put(f"{T}/operating-areas/{area['id']}", {"code": "X", "name": "Y", "version": 3}).status_code == 403


def test_staff_lifecycle_and_integrity(api: Api) -> None:
    c = setup_job(api, "Staff Co", "STAFF-1")
    o, tid = c.owner, c.t.tenant["tenant"]["id"]
    sup = o.post(f"{T}/staff", {"full_name": "Asha", "kind": "SUPERVISOR", "employee_code": "E-1"}).json()
    assert o.get(f"{T}/staff/{sup['id']}").json()["employee_code"] == "E-1"
    edit = {"full_name": "Asha M.", "kind": "SUPERVISOR", "employee_code": "E-1", "phone": "+255700000001"}
    r = o.put(f"{T}/staff/{sup['id']}", {**edit, "keycloak_subject": "asha-login", "version": 1})
    assert r.status_code == 200 and (r.json()["version"], r.json()["keycloak_subject"]) == (2, "asha-login")
    assert o.put(f"{T}/staff/{sup['id']}", {**edit, "version": 1}).json()["error"]["code"] == "STALE_VERSION"
    twin = o.post(f"{T}/staff", {"full_name": "Twin", "kind": "OPERATOR"}).json()
    clash = o.put(
        f"{T}/staff/{twin['id']}", {"full_name": "Twin", "kind": "OPERATOR", "employee_code": "E-1", "version": 1}
    )
    assert clash.json()["error"]["code"] == "DUPLICATE_STAFF"

    # Assigned to a machine: the kind cannot change; supervising an approved job blocks deactivation.
    [m2] = api.add_machines(o, 1, prefix="STF")
    a = o.post(
        f"{T}/machines/{m2}/assignments",
        {"staff_member_id": sup["id"], "role": "SUPERVISOR", "effective_from": api.clock.now.isoformat()},
    )
    assert a.status_code == 201, a.text
    kind = o.put(f"{T}/staff/{sup['id']}", {**edit, "kind": "OPERATOR", "keycloak_subject": "asha-login", "version": 2})
    assert kind.json()["error"]["code"] == "STAFF_ASSIGNED"
    job = o.post(
        f"{T}/jobs",
        {
            "contract_id": c.contract_id,
            "job_number": "J-STAFF",
            "machine_id": m2,
            "supervisor_id": sup["id"],
            "planned_start": api.clock.now.isoformat(),
            "hourly_rate": "50000",
        },
    ).json()
    for action in ("SUBMIT", "APPROVE"):
        assert o.post(f"{T}/jobs/{job['id']}/transitions", {"action": action}).status_code == 200
    busy = o.post(f"{T}/staff/{sup['id']}/deactivate", REASON)
    assert (busy.status_code, busy.json()["error"]["code"]) == (422, "STAFF_HAS_ACTIVE_JOBS")
    o.post(f"{T}/jobs/{job['id']}/transitions", {"action": "CANCEL", "reason": "Customer postponed"})

    # Holding company cash blocks deactivation until the custody is settled.
    f = o.post(f"{T}/cash/floats", {"staff_member_id": sup["id"], "amount": "5000"})
    assert f.status_code == 201, f.text
    cash = o.post(f"{T}/staff/{sup['id']}/deactivate", REASON)
    assert cash.json()["error"]["code"] == "STAFF_HOLDS_CASH"
    h = o.post(
        f"{T}/cash/handovers",
        {"staff_member_id": sup["id"], "amount": "5000", "handed_at": api.clock.now.isoformat()},
    )
    assert h.status_code == 201, h.text
    claimed = o.post(f"{T}/staff/{sup['id']}/deactivate", REASON)
    assert claimed.json()["error"]["code"] == "STAFF_HOLDS_CASH"  # a claimed handover is not settled yet
    v = _accountant(api, tid).post(f"{T}/cash/handovers/{h.json()['id']}/decision", {"verified": True, "note": "ok"})
    assert v.status_code == 200, v.text

    api.clock.set_at(api.clock.now + timedelta(hours=2))
    off = o.post(f"{T}/staff/{sup['id']}/deactivate", REASON)
    assert off.status_code == 200, off.text
    assert off.json()["is_active"] is False
    hist = o.get(f"{T}/machines/{m2}/assignments").json()
    assert [(h["staff_member_id"], h["effective_to"] is not None) for h in hist] == [(sup["id"], True)]
    assert sup["id"] not in _ids(o.get(f"{T}/staff").json()["items"])
    assert sup["id"] in _ids(o.get(f"{T}/staff", include_inactive="true").json()["items"])
    reassign = o.post(
        f"{T}/machines/{m2}/assignments",
        {"staff_member_id": sup["id"], "role": "SUPERVISOR", "effective_from": api.clock.now.isoformat()},
    )
    assert reassign.status_code == 404  # inactive staff are not assignable
    assert o.post(f"{T}/staff/{sup['id']}/reactivate", {"reason": "Rehired"}).json()["is_active"] is True

    stranger = api.onboard("Staff Other", price="1")["owner"]
    assert stranger.get(f"{T}/staff/{sup['id']}").status_code == 404
    assert _accountant(api, tid).post(f"{T}/staff/{sup['id']}/deactivate", REASON).status_code == 403


def test_machine_retire_and_reinstate(api: Api) -> None:
    c = setup_job(api, "Retire Co", "RET-1")
    o, mid = c.owner, c.t.machine_id
    blocked = o.post(f"{T}/machines/{mid}/deactivate", REASON)
    assert (blocked.status_code, blocked.json()["error"]["code"]) == (422, "MACHINE_HAS_OPEN_JOBS")
    m = o.get(f"{T}/machines/{mid}").json()
    keys = ("name", "category_id", "operating_area_id", "meter_decimal_places", "ownership")
    via_put = o.put(f"{T}/machines/{mid}", {**{k: m[k] for k in keys}, "status": "DISPOSED", "version": m["version"]})
    assert via_put.json()["error"]["code"] == "MACHINE_HAS_OPEN_JOBS"  # same rules when disposing via edit
    o.post(f"{T}/jobs/{c.job_id}/transitions", {"action": "CANCEL", "reason": "Machine sold"})
    assert o.post(f"{T}/machines/{mid}/deactivate", REASON).json()["error"]["code"] == "MACHINE_HAS_TRACKER"
    end = (api.clock.now + timedelta(hours=1)).isoformat()
    u = o.post(f"{T}/trackers/{c.t.tracker_id}/unassign", {"effective_to": end, "reason": "Machine sold"})
    assert u.status_code == 200, u.text
    assert o.post(f"{T}/machines/{mid}/deactivate", REASON).json()["error"]["code"] == "MACHINE_ENROLLED"

    # A plain machine (no jobs/tracker/enrollment) retires; its staff assignment ends; it can be reinstated.
    [plain] = api.add_machines(o, 1, prefix="PLN")
    op = o.post(f"{T}/staff", {"full_name": "Peter", "kind": "OPERATOR"}).json()
    o.post(
        f"{T}/machines/{plain}/assignments",
        {"staff_member_id": op["id"], "role": "OPERATOR", "effective_from": api.clock.now.isoformat()},
    )
    api.clock.set_at(api.clock.now + timedelta(hours=1))
    stale = o.post(f"{T}/machines/{plain}/deactivate", {**REASON, "version": 9})
    assert stale.json()["error"]["code"] == "STALE_VERSION"
    off = o.post(f"{T}/machines/{plain}/deactivate", {"reason": "Sold at auction", "version": 1})
    assert off.status_code == 200, off.text
    assert (off.json()["status"], off.json()["deactivation_reason"]) == ("DISPOSED", "Sold at auction")
    assert o.get(f"{T}/machines/{plain}/assignments").json()[0]["effective_to"] is not None
    listed = _ids(o.get(f"{T}/machines").json()["items"])
    assert plain not in listed and mid in listed
    assert plain in _ids(o.get(f"{T}/machines", include_inactive="true").json()["items"])
    assert plain in _ids(o.get(f"{T}/machines", status="DISPOSED").json()["items"])
    d = o.get(f"{T}/machines/{plain}").json()
    locked = o.put(f"{T}/machines/{plain}", {**{k: d[k] for k in keys}, "status": "ACTIVE", "version": d["version"]})
    assert locked.json()["error"]["code"] == "MACHINE_DISPOSED"
    job = o.post(
        f"{T}/jobs",
        {
            "contract_id": c.contract_id,
            "job_number": "J-RET",
            "machine_id": plain,
            "planned_start": api.clock.now.isoformat(),
            "hourly_rate": "1",
        },
    )
    assert job.json()["error"]["code"] == "MACHINE_INACTIVE"
    on = o.post(f"{T}/machines/{plain}/reactivate", {"reason": "Bought back"})
    assert on.status_code == 200 and on.json()["status"] == "ACTIVE" and on.json()["deactivated_at"] is None
    assert o.post(f"{T}/machines/{plain}/reactivate", {"reason": "Twice"}).json()["error"]["code"] == "ALREADY_ACTIVE"
    stranger = api.onboard("Retire Other", price="1")["owner"]
    assert stranger.post(f"{T}/machines/{plain}/deactivate", REASON).status_code == 404
