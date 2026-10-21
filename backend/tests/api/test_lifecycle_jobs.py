"""Record lifecycle for customers, contracts and jobs: details, optimistic edits, customer deactivation, contract
close/reopen, pre-approval job edits (JOB_LOCKED after approval), isolation and permission denial."""

from decimal import Decimal
from typing import Any

from tests.support.api import Actor, Api
from tests.support.jobs import setup_job

T = "/api/v1/tenant"
REASON = {"reason": "Relationship ended"}


def _supervisor(api: Api, tid: str) -> Actor:
    """Has tenant.customer.read and tenant.job.read only."""
    return Actor(api, "sup-lifecycle", [f"/tenants/{tid}/supervisor"], tid, email="sup@lifecycle.example.com")


def _ids(page: dict[str, Any]) -> set[str]:
    return {r["id"] for r in page["items"]}


def test_customer_lifecycle(api: Api) -> None:
    c = setup_job(api, "Cust Co", "CUST-1")
    o, tid = c.owner, c.t.tenant["tenant"]["id"]
    cust_id = o.get(f"{T}/contracts/{c.contract_id}").json()["customer_id"]
    cust = o.get(f"{T}/customers/{cust_id}").json()
    assert (cust["code"], cust["is_active"], cust["version"]) == ("C1", True, 1)

    body = {**{k: cust[k] for k in ("code", "name", "tax_id", "contact_name", "contact_phone", "contact_email")}}
    r = o.put(f"{T}/customers/{cust_id}", {**body, "contact_email": "ap@roads.example.com", "version": 1})
    assert r.status_code == 200 and (r.json()["version"], r.json()["contact_email"]) == (2, "ap@roads.example.com")
    assert o.put(f"{T}/customers/{cust_id}", {**body, "version": 1}).json()["error"]["code"] == "STALE_VERSION"
    other = o.post(f"{T}/customers", {"code": "C2", "name": "Other"}).json()
    dup = o.put(f"{T}/customers/{other['id']}", {"code": "C1", "name": "Other", "version": 1})
    assert dup.json()["error"]["code"] == "DUPLICATE_CUSTOMER"

    blocked = o.post(f"{T}/customers/{cust_id}/deactivate", REASON)  # the setup job is APPROVED
    assert (blocked.status_code, blocked.json()["error"]["code"]) == (422, "CUSTOMER_HAS_OPEN_JOBS")
    o.post(f"{T}/jobs/{c.job_id}/transitions", {"action": "CANCEL", "reason": "Customer exit"})
    off = o.post(f"{T}/customers/{cust_id}/deactivate", {**REASON, "version": 2})
    assert off.status_code == 200, off.text
    assert (off.json()["is_active"], off.json()["deactivation_reason"]) == (False, "Relationship ended")
    assert cust_id not in _ids(o.get(f"{T}/customers").json())
    assert cust_id in _ids(o.get(f"{T}/customers", include_inactive="true").json())
    assert o.get(f"{T}/customers/{cust_id}/balance").status_code == 200  # history/balance stays reachable
    new_contract = o.post(
        f"{T}/contracts", {"customer_id": cust_id, "contract_number": "CT-9", "starts_on": api.clock.now.isoformat()}
    )
    assert new_contract.json()["error"]["code"] == "CUSTOMER_INACTIVE"
    job = o.post(
        f"{T}/jobs",
        {
            "contract_id": c.contract_id,
            "job_number": "J-X",
            "machine_id": c.t.machine_id,
            "planned_start": api.clock.now.isoformat(),
        },
    )
    assert job.json()["error"]["code"] == "CUSTOMER_INACTIVE"
    assert o.post(f"{T}/customers/{cust_id}/reactivate", {"reason": "Won back"}).json()["is_active"] is True

    stranger = api.onboard("Cust Other", price="1")["owner"]
    assert stranger.get(f"{T}/customers/{cust_id}").status_code == 404
    assert stranger.put(f"{T}/customers/{cust_id}", {**body, "version": 4}).status_code == 404
    sup = _supervisor(api, tid)
    assert sup.get(f"{T}/customers/{cust_id}").status_code == 200
    assert sup.post(f"{T}/customers/{cust_id}/deactivate", REASON).status_code == 403


def test_contract_edit_close_reopen(api: Api) -> None:
    c = setup_job(api, "Contract Co", "CTR-1")
    o, cid = c.owner, c.contract_id
    ct = o.get(f"{T}/contracts/{cid}").json()
    assert (ct["status"], ct["version"]) == ("ACTIVE", 1)
    edit = {"contract_number": "CT-001", "starts_on": ct["starts_on"], "reference": "PO-77", "notes": "Night shifts"}
    r = o.put(f"{T}/contracts/{cid}", {**edit, "version": 1})
    assert r.status_code == 200 and (r.json()["reference"], r.json()["notes"], r.json()["version"]) == (
        "PO-77",
        "Night shifts",
        2,
    )
    assert o.put(f"{T}/contracts/{cid}", {**edit, "version": 1}).json()["error"]["code"] == "STALE_VERSION"
    bad = o.put(f"{T}/contracts/{cid}", {**edit, "ends_on": "2020-01-01T00:00:00+00:00", "version": 2})
    assert bad.json()["error"]["code"] == "CONTRACT_DATES"

    assert o.post(f"{T}/contracts/{cid}/close", REASON).json()["error"]["code"] == "CONTRACT_HAS_OPEN_JOBS"
    o.post(f"{T}/jobs/{c.job_id}/transitions", {"action": "CANCEL", "reason": "Scope cut"})
    closed = o.post(f"{T}/contracts/{cid}/close", {"reason": "Work finished"})
    assert closed.status_code == 200 and closed.json()["status"] == "CLOSED" and closed.json()["closed_at"]
    assert cid not in _ids(o.get(f"{T}/contracts").json())
    assert cid in _ids(o.get(f"{T}/contracts", include_inactive="true").json())
    assert cid in _ids(o.get(f"{T}/contracts", status="CLOSED").json())
    assert o.put(f"{T}/contracts/{cid}", {**edit, "version": 3}).json()["error"]["code"] == "CONTRACT_CLOSED"
    job = o.post(
        f"{T}/jobs",
        {
            "contract_id": cid,
            "job_number": "J-2",
            "machine_id": c.t.machine_id,
            "planned_start": api.clock.now.isoformat(),
        },
    )
    assert job.json()["error"]["code"] == "CONTRACT_NOT_ACTIVE"
    assert o.post(f"{T}/contracts/{cid}/close", REASON).json()["error"]["code"] == "ALREADY_INACTIVE"
    reopened = o.post(f"{T}/contracts/{cid}/reopen", {"reason": "Extension signed"})
    assert reopened.json()["status"] == "ACTIVE" and reopened.json()["close_reason"] is None

    stranger = api.onboard("Contract Other", price="1")["owner"]
    assert stranger.get(f"{T}/contracts/{cid}").status_code == 404
    sup = _supervisor(api, c.t.tenant["tenant"]["id"])
    assert sup.post(f"{T}/contracts/{cid}/close", REASON).status_code == 403


def test_job_edit_before_approval_only(api: Api) -> None:
    c = setup_job(api, "Edit Co", "EDIT-1")
    o = c.owner
    [m2] = api.add_machines(o, 1, prefix="EDT")
    site = o.post(
        f"{T}/job-sites", {"code": "S1", "name": "Bridge", "center": {"type": "Point", "coordinates": [39.28, -6.8]}}
    ).json()
    sup = o.post(f"{T}/staff", {"full_name": "Sam", "kind": "SUPERVISOR"}).json()
    draft = o.post(
        f"{T}/jobs",
        {
            "contract_id": c.contract_id,
            "job_number": "J-EDIT",
            "machine_id": c.t.machine_id,
            "planned_start": api.clock.now.isoformat(),
        },
    ).json()
    assert draft["rate_source"].startswith("RATE_CARD:")
    terms = {
        "machine_id": m2,
        "job_site_id": site["id"],
        "supervisor_id": sup["id"],
        "planned_start": api.clock.now.isoformat(),
        "hourly_rate": "90000",
        "minimum_hours": "6",
        "mobilization_fee": "150000",
    }
    r = o.put(f"{T}/jobs/{draft['id']}", {**terms, "version": 1})
    assert r.status_code == 200, r.text
    job = r.json()
    assert (job["machine_id"], job["job_site_id"], job["supervisor_id"], job["rate_source"], job["version"]) == (
        m2,
        site["id"],
        sup["id"],
        "NEGOTIATED",
        2,
    )
    assert Decimal(job["hourly_rate"]) == Decimal(90000)
    assert o.put(f"{T}/jobs/{draft['id']}", {**terms, "version": 1}).json()["error"]["code"] == "STALE_VERSION"
    no_rate = o.put(f"{T}/jobs/{draft['id']}", {**{**terms, "hourly_rate": None}, "version": 2})
    assert no_rate.json()["error"]["code"] == "NO_RATE"  # m2 has no category -> no rate card

    assert o.post(f"{T}/jobs/{draft['id']}/transitions", {"action": "SUBMIT"}).status_code == 200
    pending = o.get(f"{T}/jobs/{draft['id']}").json()["job"]
    r2 = o.put(f"{T}/jobs/{draft['id']}", {**terms, "mobilization_fee": "0", "version": pending["version"]})
    assert r2.status_code == 200 and r2.json()["status"] == "PENDING_APPROVAL"
    assert o.post(f"{T}/jobs/{draft['id']}/transitions", {"action": "APPROVE"}).status_code == 200
    approved = o.get(f"{T}/jobs/{draft['id']}").json()["job"]
    locked = o.put(f"{T}/jobs/{draft['id']}", {**terms, "version": approved["version"]})
    assert (locked.status_code, locked.json()["error"]["code"]) == (422, "JOB_LOCKED")

    stranger = api.onboard("Edit Other", price="1")["owner"]
    assert stranger.put(f"{T}/jobs/{draft['id']}", {**terms, "version": 1}).status_code == 404
    sup_actor = _supervisor(api, c.t.tenant["tenant"]["id"])
    assert sup_actor.put(f"{T}/jobs/{draft['id']}", {**terms, "version": 1}).status_code == 403
