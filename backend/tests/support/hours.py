"""Customer hours helpers: tenant policy, purchases with payments, verification, prepaid jobs."""

import uuid
from typing import Any

from tests.support.api import Actor, Api
from tests.support.finance import FinCtx

RATE = 85000  # the finance fixture's rate card (per hour), tenant currency TZS (0 minor units)


def hours_policy(f: FinCtx, **values: Any) -> None:
    r = f.owner.post(
        "/api/v1/tenant/policies/CUSTOMER_HOURS/versions",
        {"scope": "TENANT", "values": values, "reason": "Tenant customer hours configuration"},
    )
    assert r.status_code == 201, r.text


def purchase(
    api: Api,
    actor: Actor,
    f: FinCtx,
    hours: str,
    *,
    customer_id: str | None = None,
    walk_in: dict[str, Any] | None = None,
    machine_id: str | None = None,
    pay: str | None = None,
    method: str = "BANK",
    reference: str | None = None,
    staff_id: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"machine_id": machine_id or f.c.t.machine_id, "hours": hours}
    if walk_in is not None:
        body["walk_in"] = walk_in
    else:
        body["customer_id"] = customer_id or f.customer_id
    if pay is not None:
        body["payment"] = {
            "amount": pay,
            "method": method,
            "reference": reference or (None if method == "CASH" else f"REF-{uuid.uuid4().hex[:10]}"),
            "received_at": api.clock.now.isoformat(),
            "staff_member_id": staff_id,
        }
    r = actor.post("/api/v1/tenant/hours-purchases", body)
    assert r.status_code == 201, r.text
    out: dict[str, Any] = r.json()
    return out


def verify(actor: Actor, payment_id: str, ok: bool = True) -> None:
    r = actor.post(f"/api/v1/tenant/customer-payments/{payment_id}/decision", {"verified": ok, "note": "Counted"})
    assert r.status_code == 200, r.text


def get_purchase(actor: Actor, purchase_id: str) -> dict[str, Any]:
    r = actor.get(f"/api/v1/tenant/hours-purchases/{purchase_id}")
    assert r.status_code == 200, r.text
    out: dict[str, Any] = r.json()
    return out


def balance(actor: Actor, customer_id: str, machine_id: str) -> dict[str, Any] | None:
    r = actor.get(f"/api/v1/tenant/customers/{customer_id}/hours-balances")
    assert r.status_code == 200, r.text
    return next((b for b in r.json() if b["machine_id"] == machine_id), None)


def prepaid_job(api: Api, f: FinCtx, number: str, machine_id: str | None = None) -> str:
    r = f.owner.post(
        "/api/v1/tenant/jobs",
        {
            "contract_id": f.c.contract_id,
            "job_number": number,
            "machine_id": machine_id or f.c.t.machine_id,
            "planned_start": api.clock.now.isoformat(),
            "billing_mode": "PREPAID_HOURS",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["billing_mode"] == "PREPAID_HOURS"
    job_id = str(r.json()["id"])
    for action in ("SUBMIT", "APPROVE"):
        a = f.owner.post(f"/api/v1/tenant/jobs/{job_id}/transitions", {"action": action})
        assert a.status_code == 200, a.text
    return job_id


def new_id() -> str:
    return str(uuid.uuid4())
