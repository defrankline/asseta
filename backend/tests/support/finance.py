"""Gate 5 helpers: tenant role actors (owner, accountants, manager, a supervisor assigned to the machine), expense
categories, tenant policies."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import text

from asseta.core.db import DbScope, apply_scope, get_sessionmaker
from tests.support.api import Actor, Api
from tests.support.meter import MachineCtx, setup_machine


@dataclass
class FinCtx:
    c: MachineCtx
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
    c = setup_machine(api, name, device)
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
            "values": {"capture_mode": "MANUAL", "manual_photo_required": False},
            "reason": "Manual capture for finance tests",
        },
    )
    assert policy.status_code == 201, policy.text
    return FinCtx(
        c,
        tid,
        c.owner,
        role(api, tid, "accountant", f"acct-{device}"),
        role(api, tid, "accountant", f"acct2-{device}"),
        role(api, tid, "manager", f"mgr-{device}"),
        sup,
        staff.json()["id"],
        c.customer_id,
    )


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


def cash_policy(f: FinCtx, **values: Any) -> None:
    """Version the tenant's CASH_CUSTODY policy (cash custody chain switches)."""
    r = f.owner.post(
        "/api/v1/tenant/policies/CASH_CUSTODY/versions",
        {"scope": "TENANT", "values": values, "reason": "Owner cash custody controls"},
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
