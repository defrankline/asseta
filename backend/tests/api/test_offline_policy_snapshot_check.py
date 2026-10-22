"""Security finding F-8: the offline policy snapshot a capture claims must have been issued to that device and valid
at capture time. A mismatch never rejects the capture (field continuity) but holds it for review with a blocking
POLICY_SNAPSHOT_UNVERIFIED exception."""

import uuid
from datetime import timedelta
from typing import Any

from tests.support.api import Actor, Api
from tests.support.jobs import JobCtx, capture, new_job, setup_job

T = "/api/v1/tenant"
DEVICE = "android-snapshot-0001"
UNVERIFIED = "POLICY_SNAPSHOT_UNVERIFIED"


def _h(actor: Actor, device: str = DEVICE) -> dict[str, str]:
    return {**actor.headers(True, None), "X-Device-Id": device}


def _supervisor(api: Api, c: JobCtx) -> Actor:
    tid = c.t.tenant["tenant"]["id"]
    sup = Actor(api, "sup-snapshot", [f"/tenants/{tid}/supervisor"], tid, email="sup@snapshot.example.com")
    staff = c.owner.post(
        f"{T}/staff", {"full_name": "Snapshot Supervisor", "kind": "SUPERVISOR", "keycloak_subject": sup.subject}
    ).json()
    r = c.owner.post(
        f"{T}/machines/{c.t.machine_id}/assignments",
        {"staff_member_id": staff["id"], "role": "SUPERVISOR", "effective_from": api.clock.now.isoformat()},
    )
    assert r.status_code == 201, r.text
    return sup


def _register(api: Api, sup: Actor, device: str) -> None:
    r = api.client.post(
        "/api/v1/sync/devices",
        headers=_h(sup, device),
        json={"device_id": device, "platform": "ANDROID", "app_version": "1"},
    )
    assert r.status_code == 201, r.text


def _push_capture(api: Api, sup: Actor, payload: dict[str, Any], device: str = DEVICE) -> dict[str, Any]:
    op = {
        "id": str(uuid.uuid4()),
        "op_type": "METER_CAPTURE",
        "payload": {**payload, "device_id": device},
        "created_at_device": payload["captured_at"],
        "depends_on": [],
    }
    r = api.client.post(
        "/api/v1/sync/push",
        headers=_h(sup, device),
        json={"device_now": api.clock.now.isoformat(), "operations": [op]},
    )
    assert r.status_code == 200, r.text
    result: dict[str, Any] = r.json()["results"][0]
    assert result["status"] == "ACKED", result  # accepted, never rejected for the snapshot
    entity: dict[str, Any] = result["result"]["entity"]
    return entity


def _next_job(api: Api, c: JobCtx, previous: str, number: str) -> str:
    """One approved job per machine at a time: cancel the previous one (its opening capture is kept)."""
    r = c.owner.post(f"{T}/jobs/{previous}/transitions", {"action": "CANCEL", "reason": "Next test case"})
    assert r.status_code == 200, r.text
    return new_job(api, c, number)


def _unverified(entity: dict[str, Any]) -> list[dict[str, Any]]:
    return [f for f in entity["findings"] if f["type"] == UNVERIFIED]


def test_offline_snapshot_must_be_issued_to_the_device_and_valid_at_capture_time(api: Api) -> None:
    c = setup_job(api, "Snapshot Co", "SNAP-1")
    sup = _supervisor(api, c)
    _register(api, sup, DEVICE)
    boot = api.client.get("/api/v1/sync/bootstrap", headers=_h(sup)).json()
    snap = {s["scope_key"]: s for s in boot["policy_snapshots"]}[f"machine:{c.t.machine_id}"]
    ids = snap["version_ids"]
    t0 = api.clock.now

    # Issued to this device and valid at capture time: no snapshot finding (other findings are not under test).
    ok = _push_capture(api, sup, capture(c.job_id, "OPENING", "100.0", t0 + timedelta(hours=1), snapshot=ids))
    assert _unverified(ok) == []
    assert "|device:" in ok["capture"]["policy_version"]

    # The same version set claimed by another device of the same user that was never handed it.
    _register(api, sup, "android-snapshot-0002")
    job2 = _next_job(api, c, c.job_id, "J-SNAP-2")
    payload = capture(job2, "OPENING", "101.0", t0 + timedelta(hours=1), snapshot=ids)
    other = _push_capture(api, sup, payload, device="android-snapshot-0002")
    [finding] = _unverified(other)
    assert finding["blocking"] is True and finding["evidence"]["reason"] == "NOT_ISSUED_TO_DEVICE"
    assert other["capture"]["state"] == "PROVISIONAL"  # kept, held for review before billing

    # Captured after the snapshot expired (validity 24 h): accepted, flagged with the issuance window as evidence.
    api.clock.set_at(t0 + timedelta(hours=30))
    job3 = _next_job(api, c, job2, "J-SNAP-3")
    late = _push_capture(api, sup, capture(job3, "OPENING", "102.0", api.clock.now, snapshot=ids))
    [finding] = _unverified(late)
    ev = finding["evidence"]
    assert ev["reason"] == "OUTSIDE_VALIDITY" and ev["valid_until"] == snap["valid_until"].replace("Z", "+00:00")
    assert sorted(ev["policy_version_ids"]) == sorted(ids)
    assert late["capture"]["state"] == "PROVISIONAL"

    # The review exception is visible to reviewers like every other capture exception.
    exceptions = c.owner.get(f"{T}/exceptions", exception_type=UNVERIFIED, job_id=job3)
    assert exceptions.status_code == 200, exceptions.text
    assert [e["exception_type"] for e in exceptions.json()["items"]] == [UNVERIFIED]


def test_online_capture_with_a_snapshot_never_issued_to_the_caller_is_held_for_review(api: Api) -> None:
    c = setup_job(api, "Snapshot Online Co", "SNAP-ON-1")
    sup = _supervisor(api, c)
    _register(api, sup, DEVICE)
    boot = api.client.get("/api/v1/sync/bootstrap", headers=_h(sup)).json()
    ids = {s["scope_key"]: s for s in boot["policy_snapshots"]}["tenant"]["version_ids"]
    now = api.clock.now

    # Issued to the supervisor's device: the same capture submitted online from that device id verifies.
    mine = sup.post(
        f"{T}/meter-captures", {**capture(c.job_id, "OPENING", "50.0", now, snapshot=ids), "device_id": DEVICE}
    )
    assert mine.status_code == 201, mine.text
    assert _unverified(mine.json()) == []

    # The owner never received a snapshot on any device: accepted, but held for review.
    job2 = _next_job(api, c, c.job_id, "J-SNAP-ON-2")
    r = c.owner.post(f"{T}/meter-captures", capture(job2, "OPENING", "51.0", now, snapshot=ids))
    assert r.status_code == 201, r.text
    [finding] = _unverified(r.json())
    assert finding["evidence"]["reason"] == "NOT_ISSUED_TO_DEVICE"
    assert r.json()["capture"]["state"] == "PROVISIONAL"
