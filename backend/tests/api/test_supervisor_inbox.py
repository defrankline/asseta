"""Supervisor visibility after sync (R1): the sync pull carries the caller's own field records (inbox) by delta,
assigned machines and recently closed jobs; REST lists are least-privilege scoped for field users ("mine"); the
supervisor's own cash views; offline meter reset requests (METER_RESET_REQUEST) are idempotent."""

import hashlib
import uuid
from datetime import timedelta
from typing import Any

from tests.support.api import Actor, Api
from tests.support.finance import FinCtx, category, expense_policy, gps, role, setup_finance, tenant_sql
from tests.support.jobs import capture, photo, unique_jpeg

DEVICE = "android-inbox-0001"


def _h(actor: Actor) -> dict[str, str]:
    return {**actor.headers(True, None), "X-Device-Id": DEVICE}


def _register(api: Api, actor: Actor) -> None:
    r = api.client.post(
        "/api/v1/sync/devices",
        headers=_h(actor),
        json={"device_id": DEVICE, "platform": "ANDROID", "app_version": "1.2.0"},
    )
    assert r.status_code == 201, r.text


def _bootstrap(api: Api, actor: Actor) -> dict[str, Any]:
    r = api.client.get("/api/v1/sync/bootstrap", headers=_h(actor))
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    return body


def _changes(api: Api, actor: Actor, cursor: int) -> dict[str, Any]:
    r = api.client.get("/api/v1/sync/changes", headers=_h(actor), params={"cursor": cursor})
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    return body


def _push(api: Api, actor: Actor, ops: list[dict[str, Any]]) -> list[dict[str, Any]]:
    r = api.client.post(
        "/api/v1/sync/push", headers=_h(actor), json={"device_now": api.clock.now.isoformat(), "operations": ops}
    )
    assert r.status_code == 200, r.text
    out: list[dict[str, Any]] = r.json()["results"]
    return out


def _op(op_type: str, payload: dict[str, Any], depends: list[str] | None = None) -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "op_type": op_type,
        "payload": payload,
        "created_at_device": "2026-11-01T09:00:00+00:00",
        "depends_on": depends or [],
    }


def _second_supervisor(api: Api, f: FinCtx, subject: str = "sup-second") -> tuple[Actor, str]:
    sup = role(api, f.tid, "supervisor", subject)
    staff = f.owner.post(
        "/api/v1/tenant/staff", {"full_name": "Second Supervisor", "kind": "SUPERVISOR", "keycloak_subject": subject}
    )
    assert staff.status_code == 201, staff.text
    return sup, str(staff.json()["id"])


def _other_tenant(api: Api) -> tuple[str, Actor]:
    t = api.onboard("Other Hire", price="1000")
    api.activate(t)
    return str(t["tenant"]["id"]), t["owner"]


def _assign(api: Api, f: FinCtx, machine_id: str, staff_id: str) -> None:
    r = f.owner.post(
        f"/api/v1/tenant/machines/{machine_id}/assignments",
        {"staff_member_id": staff_id, "role": "SUPERVISOR", "effective_from": api.clock.now.isoformat()},
    )
    assert r.status_code == 201, r.text


def _expense(api: Api, actor: Actor, cat: str, amount: str) -> dict[str, Any]:
    r = actor.post(
        "/api/v1/tenant/expenses",
        {
            "category_id": cat,
            "description": f"Spares {amount}",
            "amount": amount,
            "incurred_at": api.clock.now.isoformat(),
            "paid_from": "COMPANY",
            "gps": gps(api.clock.now),
        },
    )
    assert r.status_code == 201, r.text
    out: dict[str, Any] = r.json()
    return out


def _fuel(api: Api, actor: Actor, job_id: str) -> dict[str, Any]:
    r = actor.post(
        "/api/v1/tenant/fuel-events",
        {"event_type": "USAGE", "litres": "10", "job_id": job_id, "occurred_at": api.clock.now.isoformat()},
    )
    assert r.status_code == 201, r.text
    out: dict[str, Any] = r.json()
    return out


def test_sync_inbox_bootstrap_and_deltas(api: Api) -> None:
    f = setup_finance(api)
    sup = f.supervisor
    spares = category(f, "SPARES", "Spares")
    expense_policy(f, receipt_required_above="100000000", auto_approve_limit="0")  # every expense needs approval
    spare_machine, later_machine = api.add_machines(f.owner, 2, prefix="SPR")
    _assign(api, f, spare_machine, f.sup_staff_id)  # assigned, but no job on it
    _register(api, sup)
    t0 = api.clock.now

    # Offline day: opening reading without GPS (finding for review), start, work log, expense, fuel, cash.
    cap = _op(
        "METER_CAPTURE",
        capture(f.c.job_id, "OPENING", "800.0", t0, mode="MANUAL", gps={"status": "PERMISSION_DENIED"}),
    )
    start = _op("JOB_TRANSITION", {"job_id": f.c.job_id, "action": "START"}, [cap["id"]])
    work = _op(
        "JOB_ACTIVITY",
        {
            "job_id": f.c.job_id,
            "client_id": str(uuid.uuid4()),
            "activity_type": "DOWNTIME",
            "started_at": (t0 + timedelta(hours=1)).isoformat(),
            "ended_at": (t0 + timedelta(hours=2, minutes=30)).isoformat(),
        },
        [start["id"]],
    )
    expense = _op(
        "EXPENSE",
        {
            "client_id": str(uuid.uuid4()),
            "category_id": spares,
            "description": "Hydraulic hose",
            "amount": "40000",
            "incurred_at": t0.isoformat(),
            "job_id": f.c.job_id,
            "paid_from": "CASH_CUSTODY",
            "gps": gps(t0),
        },
    )
    fuel = _op(
        "FUEL_EVENT",
        {
            "client_id": str(uuid.uuid4()),
            "event_type": "USAGE",
            "litres": "12.5",
            "job_id": f.c.job_id,
            "occurred_at": t0.isoformat(),
        },
    )
    collection = _op(
        "CASH_COLLECTION",
        {
            "client_id": str(uuid.uuid4()),
            "customer_id": f.customer_id,
            "amount": "300000",
            "received_at": t0.isoformat(),
        },
    )
    handover = _op(
        "CASH_HANDOVER",
        {"client_id": str(uuid.uuid4()), "amount": "250000", "handed_at": t0.isoformat()},
        [collection["id"]],
    )
    results = _push(api, sup, [cap, start, work, expense, fuel, collection, handover])
    assert [r["status"] for r in results] == ["ACKED"] * 7, results

    # Other people's records never reach this supervisor's inbox.
    other, _ = _second_supervisor(api, f)
    _expense(api, other, spares, "999")
    _fuel(api, f.owner, f.c.job_id)  # office-recorded fuel is not the supervisor's own record

    boot = _bootstrap(api, sup)
    assert boot["capabilities"] == ["SUPERVISOR_INBOX_V1", "OP_METER_RESET_REQUEST", "OP_JOB_REQUEST"]
    d = boot["data"]
    assert {m["id"] for m in d["machines"]} == {f.c.t.machine_id, spare_machine}
    [c] = d["my_meter_captures"]
    assert (c["id"], c["kind"], c["capture_mode"], c["gps_status"]) == (
        cap["payload"]["id"],
        "OPENING",
        "MANUAL",
        "PERMISSION_DENIED",
    )
    assert c["review_status"] == "PENDING_REVIEW" and c["findings"]
    assert {x["exception_type"] for x in c["findings"]} >= {"GPS_UNAVAILABLE"}
    [a] = d["my_job_activities"]
    assert (a["activity_type"], a["duration_minutes"], a["job_id"]) == ("DOWNTIME", 90, f.c.job_id)
    [e] = d["my_expenses"]
    assert (e["status"], e["paid_from"], e["amount"], e["currency"]) == (
        "PENDING_APPROVAL",
        "CASH_CUSTODY",
        "40000.0000",
        "TZS",
    )
    assert e["approval_request_id"] and e["sync_revision"] > 0
    [fe] = d["my_fuel_events"]
    assert (fe["id"], fe["litres"]) == (results[4]["result"]["entity"]["id"], "12.500")
    [col] = d["my_cash_collections"]
    assert (col["status"], col["amount"]) == ("CLAIMED", "300000.0000")
    [ho] = d["my_cash_handovers"]
    assert (ho["status"], ho["decision_note"]) == ("CLAIMED", None)
    assert d["my_acknowledgements"] == [] and d["my_meter_resets"] == []

    # Nothing changed: an empty delta (the lookback may repeat rows, but nothing is newer than the cursor).
    quiet = _changes(api, sup, boot["cursor"])
    assert quiet["cursor"] >= boot["cursor"] and quiet["has_more"] is False

    # The office decides: expense approved, handover verified with a note, finding reviewed, machine assigned.
    finding = c["findings"][0]["id"]
    r = f.owner.post(f"/api/v1/tenant/exceptions/{finding}/review", {"outcome": "EXPLAINED", "note": "Phone GPS off"})
    assert r.status_code == 200, r.text
    r = f.manager.post(f"/api/v1/tenant/approvals/{e['approval_request_id']}/decision", {"approve": True})
    assert r.status_code == 200, r.text
    r = f.accountant.post(f"/api/v1/tenant/cash/handovers/{ho['id']}/decision", {"verified": True, "note": "Counted"})
    assert r.status_code == 200, r.text
    _assign(api, f, later_machine, f.sup_staff_id)

    delta = _changes(api, sup, boot["cursor"])["data"]
    [e2] = [x for x in delta["my_expenses"] if x["id"] == e["id"]]
    assert e2["status"] == "APPROVED" and e2["sync_revision"] > e["sync_revision"]
    [ho2] = delta["my_cash_handovers"]
    assert (ho2["status"], ho2["decision_note"]) == ("VERIFIED", "Counted")
    [c2] = delta["my_meter_captures"]
    assert c2["sync_revision"] > c["sync_revision"]
    reviewed = {x["id"]: x for x in c2["findings"]}[finding]
    assert (reviewed["status"], reviewed["review_note"]) == ("EXPLAINED", "Phone GPS off")
    assert later_machine in {m["id"] for m in delta["machines"]}
    assert all(x["id"] != fe["id"] or x["sync_revision"] <= boot["cursor"] for x in delta["my_fuel_events"])

    # The other supervisor's inbox holds only their own expense.
    api.client.post(
        "/api/v1/sync/devices",
        headers={**other.headers(True, None), "X-Device-Id": DEVICE},
        json={"device_id": DEVICE, "platform": "IOS", "app_version": "1.2.0"},
    )
    theirs = api.client.get("/api/v1/sync/bootstrap", headers={**other.headers(True, None), "X-Device-Id": DEVICE})
    td = theirs.json()["data"]
    assert [x["amount"] for x in td["my_expenses"]] == ["999.0000"]
    assert td["my_meter_captures"] == td["my_cash_collections"] == td["my_cash_handovers"] == []


def test_bootstrap_includes_recently_closed_jobs(api: Api) -> None:
    f = setup_finance(api)
    _register(api, f.supervisor)
    r = f.owner.post(f"/api/v1/tenant/jobs/{f.c.job_id}/transitions", {"action": "CANCEL", "reason": "postponed"})
    assert r.status_code == 200, r.text
    boot = _bootstrap(api, f.supervisor)
    assert [(j["id"], j["status"]) for j in boot["data"]["jobs"]] == [(f.c.job_id, "CANCELLED")]


def test_rest_lists_scoped_to_own_records_for_supervisors(api: Api) -> None:
    f = setup_finance(api)
    spares = category(f, "SPARES", "Spares")
    expense_policy(f, receipt_required_above="100000000", auto_approve_limit="100000000")
    other, _ = _second_supervisor(api, f)
    mine = _expense(api, f.supervisor, spares, "1000")
    theirs = _expense(api, other, spares, "2000")
    office = _expense(api, f.accountant, spares, "3000")
    my_fuel, their_fuel = _fuel(api, f.supervisor, f.c.job_id), _fuel(api, other, f.c.job_id)
    t0 = api.clock.now
    r = f.supervisor.post(
        "/api/v1/tenant/meter-captures",
        capture(f.c.job_id, "OPENING", "500.0", t0, mode="MANUAL", gps={"status": "PERMISSION_DENIED"}),
    )
    assert r.status_code == 201, r.text
    cap = r.json()["capture"]["id"]

    def ids(actor: Actor, path: str, **params: Any) -> set[str]:
        resp = actor.get(path, **params)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        return {x["id"] for x in (body["items"] if isinstance(body, dict) else body)}

    assert ids(f.supervisor, "/api/v1/tenant/expenses") == {mine["id"]}
    assert ids(other, "/api/v1/tenant/expenses") == {theirs["id"]}
    assert ids(f.accountant, "/api/v1/tenant/expenses") == {mine["id"], theirs["id"], office["id"]}
    assert ids(f.owner, "/api/v1/tenant/expenses") == {mine["id"], theirs["id"], office["id"]}
    assert ids(f.accountant, "/api/v1/tenant/expenses", mine="true") == {office["id"]}
    assert f.supervisor.get(f"/api/v1/tenant/expenses/{theirs['id']}").status_code == 404
    assert f.supervisor.get(f"/api/v1/tenant/expenses/{mine['id']}").status_code == 200
    assert f.accountant.get(f"/api/v1/tenant/expenses/{theirs['id']}").status_code == 200

    assert ids(f.supervisor, "/api/v1/tenant/fuel-events") == {my_fuel["id"]}
    assert ids(other, "/api/v1/tenant/fuel-events") == {their_fuel["id"]}
    assert ids(f.accountant, "/api/v1/tenant/fuel-events") == {my_fuel["id"], their_fuel["id"]}

    # Meter: the first supervisor captured on their job; the second supervisor has no jobs and captured nothing.
    assert ids(f.supervisor, "/api/v1/tenant/meter-captures") == {cap}
    assert ids(other, "/api/v1/tenant/meter-captures") == set()
    assert ids(other, f"/api/v1/tenant/jobs/{f.c.job_id}/meter-captures") == set()
    assert ids(f.owner, "/api/v1/tenant/meter-captures") == {cap}
    assert ids(f.owner, "/api/v1/tenant/meter-captures", mine="true") == set()
    exceptions = ids(f.owner, "/api/v1/tenant/exceptions")
    assert exceptions and ids(f.supervisor, "/api/v1/tenant/exceptions") == exceptions
    assert ids(other, "/api/v1/tenant/exceptions") == set()

    # Tenant isolation: another tenant's office sees none of it.
    tid2, _ = _other_tenant(api)
    foreign = role(api, tid2, "accountant", "acct-other")
    assert ids(foreign, "/api/v1/tenant/expenses") == set()
    assert foreign.get(f"/api/v1/tenant/expenses/{mine['id']}").status_code == 404


def test_supervisor_own_cash_views(api: Api) -> None:
    f = setup_finance(api)
    sup = f.supervisor
    other, _ = _second_supervisor(api, f)
    t0 = api.clock.now
    r = sup.post(
        "/api/v1/tenant/cash/collections",
        {"customer_id": f.customer_id, "amount": "300000", "received_at": t0.isoformat()},
    )
    assert r.status_code == 201, r.text
    first = sup.post("/api/v1/tenant/cash/handovers", {"amount": "200000", "handed_at": t0.isoformat()}).json()
    second = sup.post("/api/v1/tenant/cash/handovers", {"amount": "50000", "handed_at": t0.isoformat()}).json()
    r = f.accountant.post(f"/api/v1/tenant/cash/handovers/{first['id']}/decision", {"verified": True, "note": "OK"})
    assert r.status_code == 200, r.text
    r = f.accountant.post(
        f"/api/v1/tenant/cash/handovers/{second['id']}/decision", {"verified": False, "note": "Envelope short"}
    )
    assert r.status_code == 200, r.text

    assert sup.get("/api/v1/tenant/cash/handovers").status_code == 403  # office list stays finance-only
    cols = sup.get("/api/v1/tenant/cash/custody/me/collections").json()
    assert [(c["amount"], c["status"]) for c in cols["items"]] == [("300000.0000", "CLAIMED")]
    hos = sup.get("/api/v1/tenant/cash/custody/me/handovers").json()
    assert {(h["amount"], h["status"], h["decision_note"]) for h in hos["items"]} == {
        ("200000.0000", "VERIFIED", "OK"),
        ("50000.0000", "REJECTED", "Envelope short"),
    }
    rejected = sup.get("/api/v1/tenant/cash/custody/me/handovers", status="REJECTED").json()
    assert [h["id"] for h in rejected["items"]] == [second["id"]]
    rec = sup.get("/api/v1/tenant/cash/custody/me/reconciliation", date=t0.date().isoformat())
    assert rec.status_code == 200, rec.text
    [tzs] = rec.json()
    [day] = tzs["days"]
    assert (tzs["currency"], day["opening"], day["collections"], day["verified_handovers"], day["outstanding"]) == (
        "TZS",
        "0.0000",
        "300000.0000",
        "200000.0000",
        "100000.0000",
    )
    assert sup.get("/api/v1/tenant/cash/custody/me/reconciliation").status_code == 200  # defaults to today
    assert other.get("/api/v1/tenant/cash/custody/me/collections").json()["items"] == []
    assert other.get("/api/v1/tenant/cash/custody/me/handovers").json()["total"] == 0
    assert f.manager.get("/api/v1/tenant/cash/custody/me/handovers").status_code == 403  # no COLLECT permission


def test_offline_meter_reset_request_idempotent(api: Api) -> None:
    f = setup_finance(api)
    sup = f.supervisor
    _register(api, sup)
    boot = _bootstrap(api, sup)
    data = unique_jpeg()
    upload = api.client.post(
        "/api/v1/sync/blobs",
        headers=_h(sup),
        json={"sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data), "purpose": "RESET_EVIDENCE"},
    ).json()
    reset = _op(
        "METER_RESET_REQUEST",
        {
            "machine_id": f.c.t.machine_id,
            "old_reading": "9999.9",
            "new_reading": "0.0",
            "effective_at": api.clock.now.isoformat(),
            "reason": "Hour meter replaced after cluster failure",
            "evidence_upload_id": upload["id"],
        },
    )
    bad = _op("METER_RESET_REQUEST", {**reset["payload"], "evidence_upload_id": None, "machine_id": str(uuid.uuid4())})
    short = _op("METER_RESET_REQUEST", {**reset["payload"], "evidence_upload_id": None, "reason": "short"})
    first = _push(api, sup, [reset, bad, short])
    assert first[0]["status"] == "DEFERRED" and first[0]["error"]["code"] == "ATTACHMENT_PENDING"
    assert (first[1]["status"], first[1]["error"]["code"]) == ("REJECTED", "MACHINE_NOT_FOUND")
    assert (first[2]["status"], first[2]["error"]["code"]) == ("REJECTED", "VALIDATION_FAILED")

    api.client.put(f"/api/v1/sync/blobs/{upload['id']}/chunks/0", headers=_h(sup), content=data)
    done = api.client.post(f"/api/v1/sync/blobs/{upload['id']}/complete", headers=_h(sup)).json()
    assert done["status"] == "COMPLETE"
    second = _push(api, sup, [reset])
    assert second[0]["status"] == "ACKED", second
    entity = second[0]["result"]["entity"]
    assert (entity["status"], entity["evidence_attachment_id"]) == ("PENDING", done["attachment_id"])
    assert _push(api, sup, [reset])[0]["status"] == "DUPLICATE"
    assert tenant_sql(f.tid, "SELECT count(*) FROM meter_reset_event")[0][0] == 1  # exactly one effect

    delta = _changes(api, sup, boot["cursor"])["data"]
    assert [(r["id"], r["status"]) for r in delta["my_meter_resets"]] == [(entity["id"], "PENDING")]
    assert [r["id"] for r in sup.get("/api/v1/tenant/meter-resets").json()] == [entity["id"]]
    decided = f.owner.post(
        f"/api/v1/tenant/meter-resets/{entity['id']}/decision", {"outcome": "EXPLAINED", "note": "Workshop report"}
    )
    assert decided.status_code == 200, decided.text
    later = _changes(api, sup, boot["cursor"])["data"]
    assert [(r["id"], r["status"]) for r in later["my_meter_resets"]] == [(entity["id"], "APPROVED")]

    # Another tenant's device never sees it.
    tid2, owner2 = _other_tenant(api)
    foreign = role(api, tid2, "supervisor", "sup-other")
    staff = owner2.post(
        "/api/v1/tenant/staff", {"full_name": "Other Sup", "kind": "SUPERVISOR", "keycloak_subject": foreign.subject}
    )
    assert staff.status_code == 201, staff.text
    _register(api, foreign)
    assert _bootstrap(api, foreign)["data"]["my_meter_resets"] == []
    assert foreign.get("/api/v1/tenant/meter-resets").json() == []


def test_inbox_streams_are_paged_by_revision(api: Api, monkeypatch: Any) -> None:
    from asseta.modules.sync import service

    monkeypatch.setattr(service, "PAGE", 2)
    monkeypatch.setattr(service, "LOOKBACK", 0)
    f = setup_finance(api)
    sup = f.supervisor
    _register(api, sup)
    fuel = {_fuel(api, sup, f.c.job_id)["id"] for _ in range(5)}
    boot = _bootstrap(api, sup)
    seen = [x["id"] for x in boot["data"]["my_fuel_events"]]
    assert len(seen) == 2
    cursor, pulls = boot["cursor"], 0
    while True:
        page = _changes(api, sup, cursor)
        assert len(page["data"]["my_fuel_events"]) <= 2
        seen += [x["id"] for x in page["data"]["my_fuel_events"]]
        cursor, pulls = page["cursor"], pulls + 1
        if not page["has_more"]:
            break
        assert pulls < 10
    assert set(seen) == fuel and len(seen) == 5  # every record exactly once, in revision order


def test_attachment_urls_scoped_to_own_records_for_supervisors(api: Api) -> None:
    f = setup_finance(api)
    other, _ = _second_supervisor(api, f)
    pic = photo(api, f.supervisor)
    r = f.supervisor.post(
        "/api/v1/tenant/meter-captures",
        capture(f.c.job_id, "OPENING", "500.0", api.clock.now, photo_id=pic, gps={"status": "PERMISSION_DENIED"}),
    )
    assert r.status_code == 201, r.text
    stray = photo(api, other)  # uploaded by the second supervisor, attached to nothing

    def url(actor: Actor, att: str) -> int:
        return int(actor.get(f"/api/v1/tenant/attachments/{att}/url").status_code)

    assert url(f.supervisor, pic) == 200  # own upload on own job
    assert url(other, pic) == 404  # another supervisor's reading photo: hidden, not forbidden
    assert url(other, stray) == 200 and url(f.supervisor, stray) == 404
    assert url(f.owner, pic) == 200 and url(f.owner, stray) == 200  # office roles see the tenant
