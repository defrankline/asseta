"""Supervisor-initiated jobs (R1): a supervisor requests a job from the field (REST or offline sync JOB_REQUEST), the
server numbers and prices it and sends it for approval; the owner approves (setting the price when no rate card
applies) or declines; the named supervisor is notified of approvals, assignments and declines."""

import uuid
from typing import Any

from asseta.modules.sync.push import REQUIRED_PERMISSION
from tests.support.api import Actor, Api
from tests.support.finance import FinCtx, role, setup_finance
from tests.support.notify import drain, member

T = "/api/v1/tenant"
INBOX = f"{T}/notifications"
DEVICE = "android-jobreq-0001"


def _request(api: Api, f: FinCtx, machine_id: str | None = None, **extra: Any) -> dict[str, Any]:
    return {
        "client_id": str(uuid.uuid4()),
        "contract_id": f.c.contract_id,
        "machine_id": machine_id or f.c.t.machine_id,
        "planned_start": api.clock.now.isoformat(),
        "note": "Customer wants the excavator for trenching",
        **extra,
    }


def _machine(f: FinCtx, code: str) -> str:
    r = f.owner.post(f"{T}/machines", {"asset_code": code, "name": f"Grader {code}"})
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


def _types(actor: Actor) -> list[tuple[str, str, str]]:
    r = actor.get(INBOX)
    assert r.status_code == 200, r.text
    return [(n["type"], n["title"], n["body"]) for n in r.json()["items"]]


def test_supervisor_requests_job_over_rest(api: Api) -> None:
    f = setup_finance(api)
    year = api.clock.now.year
    body = _request(api, f)
    key = str(uuid.uuid4())
    r = f.supervisor.post(f"{T}/jobs/requests", body, key=key)
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["id"] == body["client_id"]
    assert job["job_number"] == f"J-{year}-001"
    assert job["status"] == "PENDING_APPROVAL"
    assert (job["supervisor_id"], job["requested_by_staff_id"]) == (f.sup_staff_id, f.sup_staff_id)
    assert job["requested_by_name"] == "Cash Supervisor"
    assert job["request_note"] == body["note"]
    assert job["rate_source"].startswith("RATE_CARD:") and job["hourly_rate"] == "85000.0000"
    # Same Idempotency-Key, and the same client_id without one, both return the one job.
    assert f.supervisor.post(f"{T}/jobs/requests", body, key=key).json()["id"] == job["id"]
    again = f.supervisor.post(f"{T}/jobs/requests", body)
    assert again.status_code == 201 and again.json()["job_number"] == job["job_number"]
    # Next request gets the next number in the series.
    nxt = f.supervisor.post(f"{T}/jobs/requests", _request(api, f)).json()
    assert nxt["job_number"] == f"J-{year}-002"

    mine = f.supervisor.get(f"{T}/jobs", mine="true").json()["items"]
    assert {job["id"], nxt["id"]} <= {j["id"] for j in mine}
    summary = f.owner.get(f"{T}/jobs/{job['id']}").json()["job"]
    assert summary["requested_by_name"] == "Cash Supervisor" and summary["request_note"] == body["note"]

    audit = f.owner.get(f"{T}/audit-events", entity_id=job["id"])
    assert audit.status_code == 200, audit.text
    assert "jobs.job.requested" in {e["action"] for e in audit.json()["items"]}

    # Field lookup of contracts, with names.
    contracts = f.supervisor.get(f"{T}/field/contracts")
    assert contracts.status_code == 200, contracts.text
    [c] = contracts.json()
    assert (c["id"], c["customer_name"], c["contract_number"]) == (f.c.contract_id, "Road Builders Ltd", "CT-001")
    assert f.supervisor.get(f"{T}/field/contracts", q="Road").json()[0]["id"] == f.c.contract_id
    assert f.supervisor.get(f"{T}/field/contracts", q="nothing-like-this").json() == []


def test_request_permission_and_staff_link_required(api: Api) -> None:
    f = setup_finance(api)
    assert f.accountant.post(f"{T}/jobs/requests", _request(api, f)).status_code == 403
    assert f.accountant.get(f"{T}/field/contracts").status_code == 403
    # The owner holds tenant.job.request but has no linked staff record.
    r = f.owner.post(f"{T}/jobs/requests", _request(api, f))
    assert r.status_code == 422 and r.json()["error"]["code"] == "NO_STAFF_RECORD"
    unlinked = role(api, f.tid, "supervisor", "sup-unlinked")
    r = unlinked.post(f"{T}/jobs/requests", _request(api, f))
    assert r.status_code == 422 and r.json()["error"]["code"] == "NO_STAFF_RECORD"
    # A closed contract cannot take requests.
    other = f.owner.post(
        f"{T}/contracts",
        {"customer_id": f.customer_id, "contract_number": "CT-CLOSED", "starts_on": api.clock.now.isoformat()},
    ).json()
    f.owner.post(f"{T}/contracts/{other['id']}/close", {"reason": "Finished", "version": other["version"]})
    r = f.supervisor.post(f"{T}/jobs/requests", _request(api, f, contract_id=other["id"]))
    assert r.status_code == 422 and r.json()["error"]["code"] == "CONTRACT_NOT_ACTIVE"


def test_pending_price_requires_rate_on_approval(api: Api) -> None:
    f = setup_finance(api)
    machine = _machine(f, "GR-77")  # no category -> no rate card
    job = f.supervisor.post(f"{T}/jobs/requests", _request(api, f, machine)).json()
    assert (job["rate_source"], job["hourly_rate"]) == ("PENDING_PRICE", "0.0000")
    url = f"{T}/jobs/{job['id']}/transitions"
    r = f.owner.post(url, {"action": "APPROVE"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "PRICE_REQUIRED"
    assert f.owner.post(url, {"action": "START", "hourly_rate": "1"}).status_code == 422
    assert f.supervisor.post(url, {"action": "APPROVE", "hourly_rate": "70000"}).status_code == 403
    r = f.owner.post(url, {"action": "APPROVE", "hourly_rate": "70000"})
    assert r.status_code == 200, r.text
    assert (r.json()["status"], r.json()["hourly_rate"], r.json()["rate_source"]) == (
        "APPROVED",
        "70000.0000",
        "OWNER_APPROVED",
    )


def test_offline_job_request_via_sync_is_idempotent(api: Api) -> None:
    f = setup_finance(api)
    h = {**f.supervisor.headers(True, None), "X-Device-Id": DEVICE}
    reg = api.client.post(
        "/api/v1/sync/devices", headers=h, json={"device_id": DEVICE, "platform": "ANDROID", "app_version": "1.3.0"}
    )
    assert reg.status_code == 201, reg.text
    payload = _request(api, f, _machine(f, "GR-88"))

    def push(op_id: str) -> dict[str, Any]:
        op = {
            "id": op_id,
            "op_type": "JOB_REQUEST",
            "payload": payload,
            "created_at_device": api.clock.now.isoformat(),
            "depends_on": [],
        }
        r = api.client.post(
            "/api/v1/sync/push", headers=h, json={"device_now": api.clock.now.isoformat(), "operations": [op]}
        )
        assert r.status_code == 200, r.text
        out: dict[str, Any] = r.json()["results"][0]
        return out

    op_id = str(uuid.uuid4())
    first = push(op_id)
    assert first["status"] == "ACKED", first
    entity = first["result"]["entity"]
    assert entity["id"] == payload["client_id"] and entity["status"] == "PENDING_APPROVAL"
    assert entity["job_number"].startswith("J-")
    replay = push(op_id)
    assert replay["status"] == "DUPLICATE" and replay["result"]["entity"]["id"] == entity["id"]
    resent = push(str(uuid.uuid4()))  # the device lost the ack and queued a new op for the same request
    assert resent["status"] == "ACKED" and resent["result"]["entity"]["job_number"] == entity["job_number"]
    assert len([j for j in f.owner.get(f"{T}/jobs").json()["items"] if j["id"] == entity["id"]]) == 1

    boot = api.client.get("/api/v1/sync/bootstrap", headers=h).json()
    assert entity["id"] in {j["id"] for j in boot["data"]["jobs"]}  # pending request shows on the device
    assert "OP_JOB_REQUEST" in boot["capabilities"]

    # Pushed ops need tenant.job.request like the REST route (checked per op before dispatch).
    assert REQUIRED_PERMISSION["JOB_REQUEST"] == "tenant.job.request"


def test_supervisor_notified_of_approval_decline_and_assignment(api: Api) -> None:
    f = setup_finance(api)
    sup = member(api, f.tid, "supervisor", "sup-notify")
    staff = f.owner.post(
        f"{T}/staff", {"full_name": "Neema Field", "kind": "SUPERVISOR", "keycloak_subject": sup.subject}
    ).json()["id"]
    drain(api)

    # Path B: request -> boss sees who asked; approve -> supervisor told.
    job = sup.post(f"{T}/jobs/requests", _request(api, f, _machine(f, "GR-91"))).json()
    drain(api)
    pending = [n for n in _types(f.owner) if n[0] == "JOB_AWAITING_APPROVAL" and job["job_number"] in n[2]]
    assert pending and "requested from the field by Neema Field" in pending[0][2]
    assert "trenching" in pending[0][2]
    assert f.owner.post(f"{T}/jobs/{job['id']}/transitions", {"action": "APPROVE", "hourly_rate": "60000"}).is_success
    drain(api)
    assert (
        "JOB_REQUEST_APPROVED",
        f"Job {job['job_number']} approved",
        f"Your job request {job['job_number']} was approved; you can start it.",
    ) in _types(sup)

    # Declined request (CANCEL with reason) -> supervisor sees the reason.
    declined = sup.post(f"{T}/jobs/requests", _request(api, f, _machine(f, "GR-92"))).json()
    r = f.owner.post(f"{T}/jobs/{declined['id']}/transitions", {"action": "CANCEL", "reason": "Customer has arrears"})
    assert r.status_code == 200 and r.json()["cancellation_reason"] == "Customer has arrears"
    drain(api)
    num = declined["job_number"]
    assert ("JOB_CANCELLED", f"Job {num} declined", f"Job {num} declined: Customer has arrears") in _types(sup)

    # Path A: the boss creates a job naming the supervisor; approval assigns it.
    machine = _machine(f, "GR-93")
    created = f.owner.post(
        f"{T}/jobs",
        {
            "contract_id": f.c.contract_id,
            "job_number": "J-BOSS-1",
            "machine_id": machine,
            "supervisor_id": staff,
            "planned_start": api.clock.now.isoformat(),
            "hourly_rate": "50000",
        },
    ).json()
    assert created["requested_by_staff_id"] is None
    for action in ("SUBMIT", "APPROVE"):
        assert f.owner.post(f"{T}/jobs/{created['id']}/transitions", {"action": action}).status_code == 200
    drain(api)
    assigned = [n for n in _types(sup) if n[0] == "JOB_ASSIGNED"]
    assert assigned and assigned[0][1] == "New job J-BOSS-1 assigned to you"
    assert assigned[0][2].startswith("New job J-BOSS-1 assigned to you: GR-93")
    # Only the named supervisor is told.
    assert not [n for n in _types(f.owner) if n[0] in ("JOB_ASSIGNED", "JOB_REQUEST_APPROVED", "JOB_CANCELLED")]
