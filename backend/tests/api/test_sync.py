"""Gate 4 acceptance (prompt.md §10 #7, §6): offline operations pushed after reconnection with duplicates,
rejections, conflicts, dependency ordering, quarantine on suspension, failed/resumed uploads, delta pull,
device revocation — exactly one accepted effect, all evidence preserved."""

import hashlib
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import text

from asseta.core.db import DbScope, apply_scope, get_sessionmaker
from tests.support.api import Actor, Api
from tests.support.jobs import JobCtx, capture, fix, setup_job, unique_jpeg

DEVICE = "android-supervisor-0001"


def _supervisor(api: Api, c: JobCtx) -> Actor:
    tid = c.t.tenant["tenant"]["id"]
    sup = Actor(api, "sup-sync-subject", [f"/tenants/{tid}/supervisor"], tid, email="sup@sync.example.com")
    staff = c.owner.post(
        "/api/v1/tenant/staff", {"full_name": "Sync Supervisor", "kind": "SUPERVISOR", "keycloak_subject": sup.subject}
    ).json()
    r = c.owner.post(
        f"/api/v1/tenant/machines/{c.t.machine_id}/assignments",
        {"staff_member_id": staff["id"], "role": "SUPERVISOR", "effective_from": api.clock.now.isoformat()},
    )
    assert r.status_code == 201, r.text
    return sup


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
    c = setup_job(api)
    sup = _supervisor(api, c)
    assert api.client.get("/api/v1/sync/bootstrap", headers=_h(sup)).json()["error"]["code"] == "DEVICE_NOT_REGISTERED"
    reg = api.client.post(
        "/api/v1/sync/devices",
        headers=_h(sup),
        json={"device_id": DEVICE, "platform": "ANDROID", "app_version": "1.0.0"},
    )
    assert reg.status_code == 201
    boot = api.client.get("/api/v1/sync/bootstrap", headers=_h(sup)).json()
    assert [j["id"] for j in boot["data"]["jobs"]] == [c.job_id]
    snaps = {s["scope_key"]: s for s in boot["policy_snapshots"]}
    assert f"machine:{c.t.machine_id}" in snaps and snaps["tenant"]["version_stamp"].startswith("METER_CAPTURE@")

    # --- phone offline for 9 hours: opening reading, start, work log, closing, acknowledgement -----------------
    t0 = api.clock.now
    photo = _upload(api, sup, unique_jpeg())  # uploaded earlier while briefly online
    snap_ids = snaps[f"machine:{c.t.machine_id}"]["version_ids"]
    open_cap = _op("METER_CAPTURE", capture(c.job_id, "OPENING", "800.0", t0, photo_id=photo, snapshot=snap_ids))
    start = _op("JOB_TRANSITION", {"job_id": c.job_id, "action": "START"}, [open_cap["id"]], at=t0.isoformat())
    work = _op(
        "JOB_ACTIVITY",
        {
            "job_id": c.job_id,
            "client_id": str(uuid.uuid4()),
            "activity_type": "DOWNTIME",
            "started_at": (t0 + timedelta(hours=1)).isoformat(),
            "ended_at": (t0 + timedelta(hours=2)).isoformat(),
        },
        [start["id"]],
        at=t0.isoformat(),
    )
    t1 = t0 + timedelta(hours=9)
    close_cap = _op(
        "METER_CAPTURE",
        capture(
            c.job_id,
            "CLOSING",
            "808.0",
            t1,
            mode="AUTOMATIC",
            photo_id=_upload(api, sup, unique_jpeg()),
            gps=fix(t1),
            snapshot=snap_ids,
        ),
        [start["id"]],
    )
    ack = _op(
        "JOB_ACKNOWLEDGEMENT",
        {
            "job_id": c.job_id,
            "client_id": str(uuid.uuid4()),
            "method": "NAME_CONFIRMATION",
            "signer_name": "Client Engineer",
            "captured_at": t1.isoformat(),
        },
        [close_cap["id"]],
        at=t1.isoformat(),
    )
    complete = _op("JOB_TRANSITION", {"job_id": c.job_id, "action": "COMPLETE"}, [ack["id"]], at=t1.isoformat())
    api.clock.set_at(t1 + timedelta(minutes=10))  # reconnect

    # Network flap: only the last ops arrive first -> dependencies deferred, nothing applied out of order.
    early = _push(api, sup, [ack, complete])
    assert [r["status"] for r in early["results"]] == ["DEFERRED", "DEFERRED"]
    batch = [open_cap, start, work, close_cap, ack, complete]
    first = _push(api, sup, batch)
    assert [r["status"] for r in first["results"]] == ["ACKED"] * 6, first
    again = _push(api, sup, batch)  # client never saw the response and retries everything
    assert [r["status"] for r in again["results"]] == ["DUPLICATE"] * 6
    summary = c.owner.get(f"/api/v1/tenant/jobs/{c.job_id}").json()
    assert summary["job"]["status"] == "COMPLETED" and summary["meter_hours"] == "8.00"
    with get_sessionmaker().begin() as s:
        apply_scope(s, DbScope.TENANT, c.t.tenant["tenant"]["id"], None)
        counts = s.execute(
            text(
                "SELECT (SELECT count(*) FROM meter_capture), (SELECT count(*) FROM job_activity),"
                " (SELECT count(*) FROM customer_acknowledgement), (SELECT count(*) FROM client_operation)"
            )
        ).one()
    assert tuple(counts) == (2, 1, 1, 6)  # exactly one effect per operation
    reused = _push(api, sup, [{**open_cap, "payload": {**open_cap["payload"], "reading": "1.0"}}])
    assert reused["results"][0]["error"]["code"] == "OPERATION_ID_REUSED"


def test_conflict_rejection_quarantine_and_revocation(api: Api) -> None:
    c = setup_job(api)
    sup = _supervisor(api, c)
    api.client.post(
        "/api/v1/sync/devices", headers=_h(sup), json={"device_id": DEVICE, "platform": "IOS", "app_version": "1.0.0"}
    )
    # Subscription suspended -> writes quarantined (kept, not applied), then applied after reactivation.
    sid = api.platform.get(f"/api/v1/platform/tenants/{c.t.tenant['tenant']['id']}/subscription").json()["id"]
    today = api.clock.now.date().isoformat()
    api.platform.post(
        f"/api/v1/platform/subscriptions/{sid}/transitions",
        {"to_status": "SUSPENDED", "effective_date": today, "reason": "Non-payment"},
    )
    note = _op(
        "JOB_ACTIVITY",
        {
            "job_id": c.job_id,
            "client_id": str(uuid.uuid4()),
            "activity_type": "NOTE",
            "started_at": api.clock.now.isoformat(),
            "note": "offline note",
        },
    )
    q = _push(api, sup, [note])
    assert q["results"][0]["status"] == "QUARANTINED"
    assert c.owner.get(f"/api/v1/tenant/jobs/{c.job_id}/activities").json() == []  # not applied while suspended
    api.platform.post(
        f"/api/v1/platform/subscriptions/{sid}/transitions",
        {"to_status": "ACTIVE", "effective_date": today, "reason": "Paid"},
    )
    assert _push(api, sup, [note])["results"][0]["status"] == "ACKED"
    assert len(c.owner.get(f"/api/v1/tenant/jobs/{c.job_id}/activities").json()) == 1
    assert _push(api, sup, [note])["results"][0]["status"] == "DUPLICATE"

    # Server cancelled the job while the phone was offline -> START is a structured conflict, not overwritten.
    c.owner.post(f"/api/v1/tenant/jobs/{c.job_id}/transitions", {"action": "CANCEL", "reason": "customer postponed"})
    res = _push(
        api,
        sup,
        [
            _op("JOB_TRANSITION", {"job_id": c.job_id, "action": "START"}),
            _op("JOB_ACTIVITY", {"job_id": c.job_id, "activity_type": "WORK"}),
        ],
    )
    conflict, bad = res["results"]
    assert conflict["status"] == "CONFLICT" and conflict["result"]["server_state"]["job_status"] == "CANCELLED"
    assert bad["status"] == "REJECTED" and bad["error"]["code"] == "VALIDATION_FAILED"

    # Lost phone: owner revokes; the device is told to wipe and can no longer sync or re-register.
    dev = c.owner.get("/api/v1/tenant/devices").json()[0]
    c.owner.post(f"/api/v1/tenant/devices/{dev['id']}/revoke", {"reason": "Phone reported stolen"})
    r = api.client.get("/api/v1/sync/bootstrap", headers=_h(sup))
    assert r.status_code == 403 and r.json()["error"]["code"] == "DEVICE_REVOKED"
    assert r.json()["error"]["details"][0]["issue"] == "WIPE_LOCAL_DATA"
    rereg = api.client.post(
        "/api/v1/sync/devices", headers=_h(sup), json={"device_id": DEVICE, "platform": "IOS", "app_version": "1.0.1"}
    )
    assert rereg.json()["error"]["code"] == "DEVICE_REVOKED"


def test_resumable_upload_checksum_and_delta_pull(api: Api) -> None:
    c = setup_job(api)
    sup = _supervisor(api, c)
    api.client.post(
        "/api/v1/sync/devices",
        headers=_h(sup),
        json={"device_id": DEVICE, "platform": "ANDROID", "app_version": "1.0.0"},
    )
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
    c.owner.post(f"/api/v1/tenant/jobs/{c.job_id}/transitions", {"action": "CANCEL", "reason": "rescheduled"})
    delta = api.client.get("/api/v1/sync/changes", headers=_h(sup), params={"cursor": boot["cursor"]}).json()
    assert [(j["id"], j["status"]) for j in delta["data"]["jobs"]] == [(c.job_id, "CANCELLED")]
    assert delta["cursor"] > boot["cursor"]
