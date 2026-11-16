"""Gate 4 acceptance (prompt.md §10 #7, §6): offline operations pushed after reconnection with duplicates,
rejections, conflicts, dependency ordering, quarantine on suspension, failed/resumed uploads, delta pull,
device revocation — exactly one accepted effect, all evidence preserved. ADR-008: the phones send a machine report
as two operations (a DAILY reading, then the report naming it), an opening report first on a machine without a
starting reading."""

import hashlib
import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from asseta.core.db import DbScope, apply_scope, get_sessionmaker
from tests.support.api import Actor, Api
from tests.support.finance import FinCtx
from tests.support.machine_reports import idle, later, ok, setup_reports
from tests.support.meter import capture, fix, unique_jpeg

DEVICE = "android-supervisor-0001"
T = "/api/v1/tenant"


def _register(api: Api, actor: Actor, platform: str = "ANDROID") -> None:
    reg = api.client.post(
        "/api/v1/sync/devices",
        headers=_h(actor),
        json={"device_id": DEVICE, "platform": platform, "app_version": "1.0.0"},
    )
    assert reg.status_code == 201, reg.text


def _bare_machine(api: Api, f: FinCtx, prefix: str = "BARE") -> str:
    """A machine assigned to the supervisor with no starting reading (no approved report, baseline or reset)."""
    [machine_id] = api.add_machines(f.owner, 1, prefix=prefix)
    ok(
        f.owner.post(
            f"{T}/machines/{machine_id}/assignments",
            {"staff_member_id": f.sup_staff_id, "role": "SUPERVISOR", "effective_from": api.clock.now.isoformat()},
        ),
        201,
    )
    return str(machine_id)


def _daily(machine_id: str, value: str, at: Any) -> dict[str, Any]:
    """METER_CAPTURE: a DAILY reading of the machine."""
    return _op("METER_CAPTURE", capture(machine_id, value, at, mode="MANUAL"))


def _report_op(capture_op: dict[str, Any], lines: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    """MACHINE_REPORT naming the reading the phone sent just before (op id = report id)."""
    reading = capture_op["payload"]
    payload = {"machine_id": reading["machine_id"], "capture_id": reading["id"], "lines": lines, **extra}
    return _op("MACHINE_REPORT", payload, [capture_op["id"]], at=reading["captured_at"])


def _h(actor: Actor, device: str = DEVICE) -> dict[str, str]:
    return {**actor.headers(True, None), "X-Device-Id": device}


def _push(api: Api, actor: Actor, ops: list[dict[str, Any]], device: str = DEVICE) -> dict[str, Any]:
    r = api.client.post(
        "/api/v1/sync/push",
        headers=_h(actor, device),
        json={"device_now": api.clock.now.isoformat(), "operations": ops},
    )
    assert r.status_code == 200, r.text
    body: dict[str, Any] = r.json()
    return body


def _op(
    op_type: str, payload: dict[str, Any], depends: list[str] | None = None, op_id: str | None = None, at: Any = None
) -> dict[str, Any]:
    return {
        "id": op_id or str(uuid.uuid4()),
        "op_type": op_type,
        "payload": payload,
        "created_at_device": (at or payload.get("captured_at") or "2026-11-01T09:00:00+00:00"),
        "depends_on": depends or [],
    }


def _upload(api: Api, actor: Actor, data: bytes) -> str:
    digest = hashlib.sha256(data).hexdigest()
    s = api.client.post(
        "/api/v1/sync/blobs",
        headers=_h(actor),
        json={"sha256": digest, "size_bytes": len(data), "purpose": "METER_PHOTO"},
    ).json()
    for i in range(s["total_chunks"]):
        chunk = data[i * s["chunk_size"] : (i + 1) * s["chunk_size"]]
        api.client.put(f"/api/v1/sync/blobs/{s['id']}/chunks/{i}", headers=_h(actor), content=chunk)
    done = api.client.post(f"/api/v1/sync/blobs/{s['id']}/complete", headers=_h(actor)).json()
    assert done["status"] == "COMPLETE", done
    return str(done["attachment_id"])


def test_bootstrap_offline_batch_replay_and_exactly_once(api: Api) -> None:
    ctx = setup_reports(api)
    f, sup, machine = ctx.f, ctx.f.supervisor, ctx.machine_id
    assert api.client.get("/api/v1/sync/bootstrap", headers=_h(sup)).json()["error"]["code"] == "DEVICE_NOT_REGISTERED"
    site = ok(
        f.owner.post(f"{T}/job-sites", {"code": "Q-1", "name": "Quarry", "center": {"coordinates": [39.28, -6.8]}}), 201
    )
    _register(api, sup)
    boot = api.client.get("/api/v1/sync/bootstrap", headers=_h(sup)).json()
    data = boot["data"]
    assert [s["id"] for s in data["sites"]] == [site["id"]]  # every active site of the company
    assert [m["id"] for m in data["machines"]] == [machine]  # the machines assigned to the caller
    assert [c["id"] for c in data["customers"]] == [f.customer_id]  # every active customer of the company
    [state] = data["machine_report_states"]
    assert Decimal(state["previous_reading"]) == 1000 and state["opening_required"] is False
    snaps = {s["scope_key"]: s for s in boot["policy_snapshots"]}
    assert f"machine:{machine}" in snaps and snaps["tenant"]["version_stamp"].startswith("METER_CAPTURE@")

    # --- phone offline for 9 hours: the day's reading (photo, GPS, snapshot), then the report naming it ----------
    t0 = api.clock.now
    photo = _upload(api, sup, unique_jpeg())  # uploaded earlier while briefly online
    snap_ids = snaps[f"machine:{machine}"]["version_ids"]
    t1 = t0 + timedelta(hours=9)
    cap = _op(
        "METER_CAPTURE",
        capture(machine, "1008.0", t1, mode="AUTOMATIC", photo_id=photo, gps=fix(t1), snapshot=snap_ids),
    )
    report = _report_op(cap, [idle(ctx.reasons["IDLE_ON_SITE"], 8)])
    api.clock.set_at(t1 + timedelta(minutes=10))  # reconnect

    # Network flap: only the report arrives first -> deferred until its reading is applied, nothing out of order.
    early = _push(api, sup, [report])
    assert [r["status"] for r in early["results"]] == ["DEFERRED"]
    batch = [cap, report]
    first = _push(api, sup, batch)
    assert [r["status"] for r in first["results"]] == ["ACKED"] * 2, first
    again = _push(api, sup, batch)  # client never saw the response and retries everything
    assert [r["status"] for r in again["results"]] == ["DUPLICATE"] * 2
    saved = ok(f.owner.get(f"{T}/machine-reports/{report['id']}"))
    assert saved["capture_id"] == cap["payload"]["id"] and saved["status"] == "SUBMITTED"
    assert Decimal(saved["start_reading"]) == 1000 and Decimal(saved["hours"]) == 8
    with get_sessionmaker().begin() as s:
        apply_scope(s, DbScope.TENANT, uuid.UUID(f.tid), None)
        counts = s.execute(
            text(
                "SELECT (SELECT count(*) FROM meter_capture), (SELECT count(*) FROM machine_report),"
                " (SELECT count(*) FROM client_operation)"
            )
        ).one()
    assert tuple(counts) == (1, 1, 2)  # exactly one effect per operation
    reused = _push(api, sup, [{**cap, "payload": {**cap["payload"], "reading": "1.0"}}])
    assert reused["results"][0]["error"]["code"] == "OPERATION_ID_REUSED"


def test_opening_report_then_normal_report_offline(api: Api) -> None:
    """The phones' contract: a DAILY METER_CAPTURE, then MACHINE_REPORT with its capture_id — `opening: true` and
    no lines on a machine without a starting reading; afterwards `opening` absent and the lines."""
    ctx = setup_reports(api)
    f, sup = ctx.f, ctx.f.supervisor
    bare = _bare_machine(api, f)
    _register(api, sup)
    boot = api.client.get("/api/v1/sync/bootstrap", headers=_h(sup)).json()
    state = next(s for s in boot["data"]["machine_report_states"] if s["machine_id"] == bare)
    assert state["previous_reading"] is None and state["opening_required"] is True

    cap = _daily(bare, "250.0", later(api, 1))
    opening = _report_op(cap, [], opening=True)
    res = _push(api, sup, [cap, opening])["results"]
    assert [r["status"] for r in res] == ["ACKED", "ACKED"], res
    entity = res[1]["result"]["entity"]
    assert entity["id"] == opening["id"] and entity["status"] == "SUBMITTED" and entity["opening"] is True
    assert entity["start_source"] == "OPENING" and Decimal(entity["hours"]) == 0 and entity["lines"] == []
    assert Decimal(entity["start_reading"]) == Decimal(entity["end_reading"]) == 250
    assert entity["submitted_by"] == ok(sup.get("/api/v1/me"))["user_id"]  # the id /me returns
    ok(f.manager.post(f"{T}/machine-reports/{opening['id']}/approve", {}))
    changes = ok(api.client.get("/api/v1/sync/changes", headers=_h(sup), params={"cursor": boot["cursor"]}))
    state = next(s for s in changes["data"]["machine_report_states"] if s["machine_id"] == bare)
    assert Decimal(state["previous_reading"]) == 250 and state["opening_required"] is False

    cap = _daily(bare, "253.0", later(api, 3))
    normal = _report_op(cap, [idle(ctx.reasons["TRANSIT"], 3)])
    res = _push(api, sup, [cap, normal])["results"]
    assert [r["status"] for r in res] == ["ACKED", "ACKED"], res
    entity = res[1]["result"]["entity"]
    assert entity["opening"] is False and entity["start_source"] == "REPORT" and entity["status"] == "SUBMITTED"
    assert Decimal(entity["start_reading"]) == 250 and Decimal(entity["hours"]) == 3


def test_a_report_without_a_starting_reading_is_kept_for_review(api: Api) -> None:
    ctx = setup_reports(api)
    f, sup = ctx.f, ctx.f.supervisor
    bare = _bare_machine(api, f)
    _register(api, sup)
    cap = _daily(bare, "40.0", later(api, 1))
    report = _report_op(cap, [idle(ctx.reasons["TRANSIT"], 1)])
    applied, held = _push(api, sup, [cap, report])["results"]
    assert applied["status"] == "ACKED"  # the reading itself is kept
    assert held["status"] == "CONFLICT" and held["error"]["code"] == "OPENING_REPORT_REQUIRED", held
    assert held["result"]["server_state"]["machine_report_state"]["opening_required"] is True
    # The same reading sent as an opening report goes through; once approved, another opening report is refused.
    opening = _report_op(cap, [], opening=True)
    [done] = _push(api, sup, [opening])["results"]
    assert done["status"] == "ACKED" and done["result"]["entity"]["opening"] is True, done
    ok(f.manager.post(f"{T}/machine-reports/{opening['id']}/approve", {}))
    cap2 = _daily(bare, "41.0", later(api, 1))
    applied, refused = _push(api, sup, [cap2, _report_op(cap2, [], opening=True)])["results"]
    assert applied["status"] == "ACKED"
    assert refused["status"] == "REJECTED" and refused["error"]["code"] == "OPENING_NOT_ALLOWED", refused


def test_conflict_rejection_quarantine_and_revocation(api: Api) -> None:
    ctx = setup_reports(api)
    f, sup, machine = ctx.f, ctx.f.supervisor, ctx.machine_id
    _register(api, sup, "IOS")
    # Subscription suspended -> writes quarantined (kept, not applied), then applied after reactivation.
    sid = api.platform.get(f"/api/v1/platform/tenants/{f.tid}/subscription").json()["id"]
    today = api.clock.now.date().isoformat()
    api.platform.post(
        f"/api/v1/platform/subscriptions/{sid}/transitions",
        {"to_status": "SUSPENDED", "effective_date": today, "reason": "Non-payment"},
    )
    reading = _daily(machine, "1002.0", later(api, 2))
    q = _push(api, sup, [reading])
    assert q["results"][0]["status"] == "QUARANTINED"
    assert ok(f.owner.get(f"{T}/meter-captures", machine_id=machine))["total"] == 0  # not applied while suspended
    api.platform.post(
        f"/api/v1/platform/subscriptions/{sid}/transitions",
        {"to_status": "ACTIVE", "effective_date": today, "reason": "Paid"},
    )
    assert _push(api, sup, [reading])["results"][0]["status"] == "ACKED"
    assert ok(f.owner.get(f"{T}/meter-captures", machine_id=machine))["total"] == 1
    assert _push(api, sup, [reading])["results"][0]["status"] == "DUPLICATE"

    # The office reported on the machine while the phone was offline -> the phone's report is a structured
    # conflict carrying the machine's report state, never overwritten; a malformed report is rejected.
    office_body = {
        "id": str(uuid.uuid4()),
        "machine_id": machine,
        "capture_id": reading["payload"]["id"],
        "lines": [idle(ctx.reasons["IDLE_ON_SITE"], 2)],
    }
    office = ok(f.manager.post(f"{T}/machine-reports", office_body), 201)
    cap = _daily(machine, "1003.0", later(api, 1))
    mine = _report_op(cap, [idle(ctx.reasons["IDLE_ON_SITE"], 3)])
    res = _push(api, sup, [cap, mine, _op("MACHINE_REPORT", {"machine_id": machine, "lines": []})])["results"]
    conflict, bad = res[1], res[2]
    assert conflict["status"] == "CONFLICT" and conflict["error"]["code"] == "REPORT_PENDING", conflict
    assert conflict["result"]["server_state"]["machine_report_state"]["pending_report_id"] == office["id"]
    assert bad["status"] == "REJECTED" and bad["error"]["code"] == "VALIDATION_FAILED", bad

    # Lost phone: owner revokes; the device is told to wipe and can no longer sync or re-register.
    dev = f.owner.get("/api/v1/tenant/devices").json()["items"][0]
    f.owner.post(f"/api/v1/tenant/devices/{dev['id']}/revoke", {"reason": "Phone reported stolen"})
    r = api.client.get("/api/v1/sync/bootstrap", headers=_h(sup))
    assert r.status_code == 403 and r.json()["error"]["code"] == "DEVICE_REVOKED"
    assert r.json()["error"]["details"][0]["issue"] == "WIPE_LOCAL_DATA"
    rereg = api.client.post(
        "/api/v1/sync/devices", headers=_h(sup), json={"device_id": DEVICE, "platform": "IOS", "app_version": "1.0.1"}
    )
    assert rereg.json()["error"]["code"] == "DEVICE_REVOKED"


def test_resumable_upload_checksum_and_delta_pull(api: Api) -> None:
    ctx = setup_reports(api)
    f, sup = ctx.f, ctx.f.supervisor
    _register(api, sup)
    data = unique_jpeg() * 20000  # > 1 chunk
    digest = hashlib.sha256(data).hexdigest()
    s = api.client.post(
        "/api/v1/sync/blobs",
        headers=_h(sup),
        json={"sha256": digest, "size_bytes": len(data), "purpose": "METER_PHOTO"},
    ).json()
    assert s["total_chunks"] >= 2
    api.client.put(f"/api/v1/sync/blobs/{s['id']}/chunks/0", headers=_h(sup), content=data[: s["chunk_size"]])
    partial = api.client.post(f"/api/v1/sync/blobs/{s['id']}/complete", headers=_h(sup)).json()
    assert partial["error"]["code"] == "UPLOAD_INCOMPLETE"  # connection dropped mid-upload
    for i in range(s["total_chunks"]):  # resume: re-sending chunk 0 is harmless
        api.client.put(
            f"/api/v1/sync/blobs/{s['id']}/chunks/{i}",
            headers=_h(sup),
            content=data[i * s["chunk_size"] : (i + 1) * s["chunk_size"]],
        )
    done = api.client.post(f"/api/v1/sync/blobs/{s['id']}/complete", headers=_h(sup)).json()
    assert done["status"] == "COMPLETE" and done["attachment_id"]
    dup = api.client.post(
        "/api/v1/sync/blobs",
        headers=_h(sup),
        json={"sha256": digest, "size_bytes": len(data), "purpose": "METER_PHOTO"},
    ).json()
    assert dup["status"] == "COMPLETE" and dup["attachment_id"] == done["attachment_id"]  # content dedupe

    corrupt = unique_jpeg()
    bad = api.client.post(
        "/api/v1/sync/blobs",
        headers=_h(sup),
        json={"sha256": "0" * 64, "size_bytes": len(corrupt), "purpose": "METER_PHOTO"},
    ).json()
    api.client.put(f"/api/v1/sync/blobs/{bad['id']}/chunks/0", headers=_h(sup), content=corrupt)
    assert (
        api.client.post(f"/api/v1/sync/blobs/{bad['id']}/complete", headers=_h(sup)).json()["error"]["code"]
        == "CHECKSUM_MISMATCH"
    )

    boot = api.client.get("/api/v1/sync/bootstrap", headers=_h(sup)).json()
    empty = api.client.get("/api/v1/sync/changes", headers=_h(sup), params={"cursor": boot["cursor"]}).json()
    assert empty["cursor"] >= boot["cursor"]
    # Company reference data: a deactivated customer and a new one reach the phone as deltas.
    ok(f.owner.post(f"{T}/customers/{f.customer_id}/deactivate", {"reason": "Customer closed"}))
    newcomer = ok(f.owner.post(f"{T}/customers", {"code": "C2", "name": "Bridge Works"}), 201)
    delta = api.client.get("/api/v1/sync/changes", headers=_h(sup), params={"cursor": boot["cursor"]}).json()
    assert {(c["id"], c["is_active"]) for c in delta["data"]["customers"]} == {
        (f.customer_id, False),
        (newcomer["id"], True),
    }
    assert delta["cursor"] > boot["cursor"]
    boot = api.client.get("/api/v1/sync/bootstrap", headers=_h(sup)).json()
    assert [c["id"] for c in boot["data"]["customers"]] == [newcomer["id"]]  # bootstrap: active ones only
