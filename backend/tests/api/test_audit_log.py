"""Gate 7 audit log views: tenant (`tenant.audit.read`: owner + manager) and platform (`platform.audit.read`) with
filters and paging, actor display names, the managed-service mandate reference on platform-staff actions, and tenant
isolation at the API and RLS layers (the platform console never sees tenant business audit)."""

import uuid
from datetime import timedelta
from typing import Any

from httpx import Response
from sqlalchemy import text

from asseta.core.db import DbScope, apply_scope, get_sessionmaker
from tests.support.api import PLATFORM_SUBJECT, Actor, Api
from tests.support.finance import role
from tests.support.meter import setup_machine

A = "/api/v1/tenant/audit-events"
PA = "/api/v1/platform/audit-events"
OWNER_PATH = "/platform/platform-owner"


def _ok(r: Response, status: int = 200) -> Any:
    assert r.status_code == status, r.text
    return r.json()


def _staff(api: Api, subject: str, email: str, tenant_id: str | None = None) -> Actor:
    api.idp.users[subject] = email
    api.idp.memberships.setdefault(subject, set()).add(OWNER_PATH)
    return Actor(api, subject, sorted(api.idp.memberships[subject]), tenant_id, email=email)


def test_tenant_audit_filters_names_paging_and_permissions(api: Api) -> None:
    c = setup_machine(api)
    owner, tid = c.owner, c.t.tenant["tenant"]["id"]
    _ok(owner.post(f"/api/v1/tenant/customers/{c.customer_id}/deactivate", {"reason": "Moved away"}))
    _ok(owner.post(f"/api/v1/tenant/customers/{c.customer_id}/reactivate", {"reason": "Came back"}))
    page = _ok(owner.get(A, page_size=2))
    assert page["total"] > 2 and len(page["items"]) == 2
    times = [i["occurred_at"] for i in _ok(owner.get(A, page_size=100))["items"]]
    assert times == sorted(times, reverse=True)

    customers = _ok(owner.get(A, action_prefix="customers.customer."))["items"]
    assert {i["action"] for i in customers} == {
        "customers.customer.created",
        "customers.customer.deactivated",
        "customers.customer.reactivated",
    }
    one = _ok(owner.get(A, entity_type="customer", entity_id=c.customer_id))["items"]
    assert {i["entity_id"] for i in one} == {c.customer_id} and len(one) == 3
    created = next(i for i in one if i["action"] == "customers.customer.created")
    me = _ok(owner.get("/api/v1/tenant/people", ids=created["actor_user_id"]))
    assert created["actor_display_name"] == me[0]["display_name"] and created["mandate_reference"] is None
    assert created["tenant_id"] == tid and created["correlation_id"]
    assert _ok(owner.get(A, actor_user_id=str(uuid.uuid4())))["total"] == 0
    future = (api.clock.now + timedelta(days=1)).isoformat()
    assert _ok(owner.get(A, occurred_from=future))["total"] == 0
    assert owner.get(A, occurred_from=future, occurred_to=api.clock.now.isoformat()).status_code == 422
    assert owner.get(A, action_prefix="DROP TABLE;").status_code == 422

    manager = role(api, tid, "manager", "audit-mgr")
    assert _ok(manager.get(A))["total"] == page["total"]
    for denied in ("accountant", "supervisor", "operator"):
        r = role(api, tid, denied, f"audit-{denied}").get(A)
        assert r.status_code == 403 and "tenant.audit.read" in r.json()["error"]["message"]

    menu = _ok(owner.get("/api/v1/me"))["tenants"][0]["menus"]
    assert any(m["key"] == "tenant.audit" and m["group"] == "tenant.admin" for m in menu)


def test_audit_is_tenant_isolated_api_and_rls(api: Api) -> None:
    c = setup_machine(api)
    tid = c.t.tenant["tenant"]["id"]
    other = api.onboard("Other Audit Co", price="1")
    api.activate(other)
    mine = _ok(other["owner"].get(A, page_size=100))["items"]
    assert mine and all(i["tenant_id"] == other["tenant"]["id"] for i in mine)
    assert _ok(other["owner"].get(A, entity_id=c.customer_id))["total"] == 0
    assert other["owner"].get(A, tenant=tid).status_code == 403
    with get_sessionmaker().begin() as s:
        apply_scope(s, DbScope.TENANT, uuid.UUID(other["tenant"]["id"]), None)
        leaked = s.execute(text("SELECT count(*) FROM audit_event WHERE tenant_id = :t"), {"t": tid}).scalar_one()
        assert leaked == 0


def test_mandate_reference_on_platform_staff_actions_and_platform_view(api: Api) -> None:
    _staff(api, PLATFORM_SUBJECT, "platform@asseta.local")
    client = api.onboard("Mandated Co", price="1")
    api.activate(client)
    tid = client["tenant"]["id"]
    mandate = _ok(
        api.platform.post(
            "/api/v1/platform/mandates",
            {
                "tenant_id": tid,
                "scope": "FULL",
                "starts_on": api.clock.now.date().isoformat(),
                "consent_reference": "MSA-2026-099",
            },
        ),
        201,
    )
    asha = _staff(api, "staff-asha", "asha@asseta.local")
    staff_rows = _ok(api.platform.get("/api/v1/platform/mandates/staff"))
    asha_id = next(s["user_id"] for s in staff_rows if s["email"] == "asha@asseta.local")
    _ok(
        api.platform.post(
            f"/api/v1/platform/mandates/{mandate['id']}/assignments", {"user_id": asha_id, "role_key": "manager"}
        )
    )
    asha = Actor(api, asha.subject, sorted(api.idp.memberships[asha.subject]), tid, email=asha.email)
    customer = _ok(asha.post("/api/v1/tenant/customers", {"code": "C9", "name": "Mandate Customer"}), 201)

    rows = _ok(client["owner"].get(A, entity_id=customer["id"]))["items"]
    assert [(r["action"], r["mandate_reference"]) for r in rows] == [
        ("customers.customer.created", mandate["reference"])
    ]
    assert rows[0]["actor_user_id"] == asha_id and rows[0]["mandate_id"] == mandate["id"]
    assert rows[0]["actor_display_name"]
    by_staff = _ok(asha.get(A, actor_user_id=asha_id))["items"]  # mandate manager role includes tenant.audit.read
    assert by_staff and all(r["mandate_reference"] == mandate["reference"] for r in by_staff)

    platform = _ok(api.platform.get(PA, tenant_id=tid, page_size=100))["items"]
    actions = {r["action"] for r in platform}
    assert "platform.tenant.onboarded" in actions and "platform.mandate.granted" in actions
    assert all(r["action"].startswith(("platform.", "billing.")) for r in platform)  # never tenant business audit
    assert _ok(api.platform.get(PA, action_prefix="customers."))["total"] == 0
    assert client["owner"].get(PA).status_code == 403
    menus = _ok(api.platform.get("/api/v1/me"))["platform_menus"]
    assert any(m["key"] == "platform.audit" and m["group"] == "platform.admin" for m in menus)
