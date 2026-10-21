"""Gate 5 helpers: tenant role actors, completed billing-ready jobs (manual capture), expense categories."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import text

from asseta.core.db import DbScope, apply_scope, get_sessionmaker
from tests.support.api import Actor, Api
from tests.support.jobs import JobCtx, capture, setup_job


@dataclass
class FinCtx:
    c: JobCtx
    tid: str
    owner: Actor
    accountant: Actor
    accountant2: Actor
    manager: Actor
    supervisor: Actor
    sup_staff_id: str
    customer_id: str


def role(api: Api, tid: str, role_key: str, subject: str) -> Actor:
    return Actor(api, subject, [f"/tenants/{tid}/{role_key}"], tid, email=f"{subject}@fin.example.com")


def setup_finance(api: Api, name: str = "Hire Co", device: str = "HIRE-1") -> FinCtx:
    c = setup_job(api, name, device)
    tid = c.t.tenant["tenant"]["id"]
    sup = role(api, tid, "supervisor", f"sup-{device}")
    staff = c.owner.post(
        "/api/v1/tenant/staff", {"full_name": "Cash Supervisor", "kind": "SUPERVISOR", "keycloak_subject": sup.subject}
    )
    assert staff.status_code == 201, staff.text
    r = c.owner.post(
        f"/api/v1/tenant/machines/{c.t.machine_id}/assignments",
        {"staff_member_id": staff.json()["id"], "role": "SUPERVISOR", "effective_from": api.clock.now.isoformat()},
    )
    assert r.status_code == 201, r.text
    policy = c.owner.post(
        "/api/v1/tenant/policies/METER_CAPTURE/versions",
        {
            "scope": "TENANT",
            "values": {"opening_mode": "MANUAL", "closing_mode": "MANUAL", "manual_photo_required": False},
            "reason": "Manual capture for finance tests",
        },
    )
    assert policy.status_code == 201, policy.text
    contract = c.owner.get(f"/api/v1/tenant/jobs/{c.job_id}").json()["job"]["contract_id"]
    customer = next(
        x["customer_id"] for x in c.owner.get("/api/v1/tenant/contracts").json()["items"] if x["id"] == contract
    )
    return FinCtx(
        c,
        tid,
        c.owner,
        role(api, tid, "accountant", f"acct-{device}"),
        role(api, tid, "accountant", f"acct2-{device}"),
        role(api, tid, "manager", f"mgr-{device}"),
        sup,
        staff.json()["id"],
        customer,
    )


def priced_job(api: Api, f: FinCtx, number: str, **terms: Any) -> str:
    body = {
        "contract_id": f.c.contract_id,
        "job_number": number,
        "machine_id": f.c.t.machine_id,
        "planned_start": api.clock.now.isoformat(),
        **terms,
    }
    r = f.owner.post("/api/v1/tenant/jobs", body)
    assert r.status_code == 201, r.text
    job_id = str(r.json()["id"])
    for action in ("SUBMIT", "APPROVE"):
        a = f.owner.post(f"/api/v1/tenant/jobs/{job_id}/transitions", {"action": action})
        assert a.status_code == 200, a.text
    return job_id


def _activity(f: FinCtx, job_id: str, kind: str, start: datetime, hours: float) -> None:
    r = f.owner.post(
        f"/api/v1/tenant/jobs/{job_id}/activities",
        {
            "client_id": str(uuid.uuid4()),
            "activity_type": kind,
            "started_at": start.isoformat(),
            "ended_at": (start + timedelta(hours=hours)).isoformat(),
        },
    )
    assert r.status_code == 201, r.text


def complete_job(
    api: Api,
    f: FinCtx,
    job_id: str,
    opening: str,
    closing: str,
    elapsed_h: float,
    *,
    downtime_h: float = 0,
    standby_h: float = 0,
) -> dict[str, Any]:
    """Opening reading -> start -> work log -> closing reading -> acknowledgement -> COMPLETE. Returns summary."""
    o, t0 = f.owner, api.clock.now
    r = o.post("/api/v1/tenant/meter-captures", capture(job_id, "OPENING", opening, t0, mode="MANUAL"))
    assert r.status_code == 201 and r.json()["capture"]["state"] == "ACCEPTED", r.text
    assert o.post(f"/api/v1/tenant/jobs/{job_id}/transitions", {"action": "START"}).status_code == 200
    if downtime_h:
        _activity(f, job_id, "DOWNTIME", t0 + timedelta(hours=1), downtime_h)
    if standby_h:
        _activity(f, job_id, "STANDBY", t0 + timedelta(hours=1 + downtime_h), standby_h)
    t1 = t0 + timedelta(hours=elapsed_h)
    api.clock.set_at(t1)
    r = o.post("/api/v1/tenant/meter-captures", capture(job_id, "CLOSING", closing, t1, mode="MANUAL"))
    assert r.status_code == 201 and r.json()["capture"]["state"] == "ACCEPTED", r.text
    ack = o.post(
        f"/api/v1/tenant/jobs/{job_id}/acknowledgements",
        {
            "client_id": str(uuid.uuid4()),
            "method": "NAME_CONFIRMATION",
            "signer_name": "Site Engineer",
            "captured_at": t1.isoformat(),
        },
    )
    assert ack.status_code == 201, ack.text
    done = o.post(f"/api/v1/tenant/jobs/{job_id}/transitions", {"action": "COMPLETE"})
    assert done.status_code == 200, done.text
    summary: dict[str, Any] = o.get(f"/api/v1/tenant/jobs/{job_id}").json()
    assert summary["billing_ready"] is True, summary
    return summary


def issue_invoice(f: FinCtx, job_ids: list[str]) -> dict[str, Any]:
    draft = f.accountant.post("/api/v1/tenant/hire-invoices", {"customer_id": f.customer_id, "job_ids": job_ids})
    assert draft.status_code == 201, draft.text
    issued = f.accountant.post(f"/api/v1/tenant/hire-invoices/{draft.json()['id']}/issue", {})
    assert issued.status_code == 200, issued.text
    out: dict[str, Any] = issued.json()
    return out


def category(f: FinCtx, code: str, name: str) -> str:
    r = f.owner.post("/api/v1/tenant/expense-categories", {"code": code, "name": name})
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


def expense_policy(f: FinCtx, **values: Any) -> None:
    r = f.owner.post(
        "/api/v1/tenant/policies/EXPENSE_CAPTURE/versions",
        {"scope": "TENANT", "values": values, "reason": "Owner expense controls"},
    )
    assert r.status_code == 201, r.text


def gps(at: datetime, accuracy: float = 10.0) -> dict[str, Any]:
    return {
        "status": "FIX",
        "latitude": -6.8,
        "longitude": 39.28,
        "accuracy_m": accuracy,
        "captured_at": at.isoformat(),
        "provider": "fused",
    }


def tenant_sql(tid: str, sql: str, **params: Any) -> Any:
    """Run SQL as the application role inside the tenant's RLS scope (returns the result rows)."""
    with get_sessionmaker().begin() as s:
        apply_scope(s, DbScope.TENANT, uuid.UUID(tid), None)
        return s.execute(text(sql), params).all()
