"""Managed-service mandates (DEC-018): platform staff reach a client only through an in-force mandate; Keycloak
groups alone never suffice, and closing or expiring a mandate stops access on the next request."""

from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import create_engine, text

from asseta.core.config import get_settings
from tests.support.api import PLATFORM_SUBJECT, Actor, Api

OWNER_PATH = "/platform/platform-owner"


def staff(api: Api, subject: str, email: str) -> Actor:
    """A platform staff member known to the IdP (Keycloak group member) whose token reflects current groups."""
    api.idp.users[subject] = email
    api.idp.memberships.setdefault(subject, set()).add(OWNER_PATH)
    return Actor(api, subject, sorted(api.idp.memberships[subject]), email=email)


def refreshed(api: Api, actor: Actor, tenant_id: str | None = None) -> Actor:
    """The same person after a token refresh: groups as Keycloak now has them."""
    return Actor(api, actor.subject, sorted(api.idp.memberships[actor.subject]), tenant_id, email=actor.email)


def grant(api: Api, tenant_id: str, scope: str = "FULL", **extra: Any) -> dict[str, Any]:
    body = {
        "tenant_id": tenant_id,
        "scope": scope,
        "starts_on": api.clock.now.date().isoformat(),
        "consent_reference": "MSA-2026-014 signed 2026-10-20",
        **extra,
    }
    r = api.platform.post("/api/v1/platform/mandates", body)
    assert r.status_code == 201, r.text
    return dict(r.json())


def staff_id(api: Api, email: str) -> str:
    rows = api.platform.get("/api/v1/platform/mandates/staff").json()
    return str(next(s["user_id"] for s in rows if s["email"] == email))


def assign(api: Api, mandate: dict[str, Any], email: str, role: str) -> Any:
    return api.platform.post(
        f"/api/v1/platform/mandates/{mandate['id']}/assignments", {"user_id": staff_id(api, email), "role_key": role}
    )


@pytest.fixture
def client_tenant(api: Api) -> dict[str, Any]:
    staff(api, PLATFORM_SUBJECT, "platform@asseta.local")
    return api.onboard("Kilimanjaro Earthworks", price="1")


def test_keycloak_group_alone_never_lets_platform_staff_in(api: Api, client_tenant: dict[str, Any]) -> None:
    tid = client_tenant["tenant"]["id"]
    # Someone adds the platform owner straight to the client's Keycloak owner group: still refused.
    sneaky = Actor(api, PLATFORM_SUBJECT, [OWNER_PATH, f"/tenants/{tid}/owner"], tid, email="platform@asseta.local")
    r = sneaky.get("/api/v1/tenant/machines")
    assert r.status_code == 403 and r.json()["error"]["code"] == "MANDATE_REQUIRED"
    assert sneaky.get("/api/v1/me").json()["tenants"] == []


def test_mandate_lifecycle_access_audit_and_client_revocation(api: Api, client_tenant: dict[str, Any]) -> None:
    tid = client_tenant["tenant"]["id"]
    client_owner = client_tenant["owner"]
    m = grant(api, tid)
    assert m["reference"].startswith(f"MSM-{api.clock.now.year}-") and m["status"] == "IN_FORCE"
    again = api.platform.post(
        "/api/v1/platform/mandates",
        {"tenant_id": tid, "scope": "FULL", "starts_on": m["starts_on"], "consent_reference": "dup"},
    )
    assert again.json()["error"]["code"] == "MANDATE_ALREADY_ACTIVE"

    asha = staff(api, "staff-asha", "asha@asseta.local")
    assert assign(api, m, "asha@asseta.local", "manager").status_code == 200
    assert assign(api, m, "asha@asseta.local", "manager").json()["error"]["code"] == "MANDATE_ALREADY_ASSIGNED"
    asha = refreshed(api, asha, tid)
    me = asha.get("/api/v1/me").json()
    assert [(t["tenant_id"], t["mandate"]["reference"]) for t in me["tenants"]] == [(tid, m["reference"])]

    created = asha.post("/api/v1/tenant/machines", {"asset_code": "EX-77", "name": "CAT 336"})
    assert created.status_code == 201, created.text
    view = client_owner.get("/api/v1/tenant/managed-service").json()
    assert view["mandate"]["reference"] == m["reference"]
    assert [(a["email"], a["role_key"], a["is_active"]) for a in view["mandate"]["assignments"]] == [
        ("asha@asseta.local", "manager", True)
    ]
    actions = {a["action"] for a in view["recent_actions"]}
    assert "platform.mandate.granted" in actions and "platform.mandate.assigned" in actions
    assert any(a["actor"] and a["entity_id"] == created.json()["id"] for a in view["recent_actions"])

    # The client cannot strip a mandate role piecemeal, and mandate staff never count as the client's owners.
    members = client_owner.get("/api/v1/tenant/access/members").json()
    asha_row = next(x for x in members if x["email"] == "asha@asseta.local")
    assert asha_row["roles"][0]["mandate_reference"] == m["reference"]
    piecemeal = client_owner.post(f"/api/v1/tenant/access/members/{asha_row['user_id']}/roles/manager/revoke")
    assert piecemeal.json()["error"]["code"] == "MANDATE_MANAGED"

    no_reason = client_owner.post(f"/api/v1/tenant/managed-service/{m['id']}/revoke", {"version": 1, "reason": ""})
    assert no_reason.status_code == 422
    stale = client_owner.post(f"/api/v1/tenant/managed-service/{m['id']}/revoke", {"version": 9, "reason": "x" * 5})
    assert stale.json()["error"]["code"] == "STALE_VERSION"
    revoked = client_owner.post(
        f"/api/v1/tenant/managed-service/{m['id']}/revoke", {"version": 1, "reason": "We hired our own dispatcher"}
    )
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["mandate"]["status"] == "REVOKED"
    # Asha's old token still carries the Keycloak group: refused on the very next request.
    r = asha.get("/api/v1/tenant/machines")
    assert r.status_code == 403 and r.json()["error"]["code"] == "MANDATE_ENDED"
    assert f"/tenants/{tid}/manager" not in api.idp.memberships["staff-asha"]  # removed from Keycloak too
    assert refreshed(api, asha).get("/api/v1/me").json()["tenants"] == []


def test_staff_under_mandate_cannot_revoke_it_and_platform_end_needs_reason(
    api: Api, client_tenant: dict[str, Any]
) -> None:
    tid = client_tenant["tenant"]["id"]
    m = grant(api, tid)
    juma = staff(api, "staff-juma", "juma@asseta.local")
    assign(api, m, "juma@asseta.local", "owner")
    juma = refreshed(api, juma, tid)
    self_revoke = juma.post(f"/api/v1/tenant/managed-service/{m['id']}/revoke", {"version": 1, "reason": "testing"})
    assert self_revoke.json()["error"]["code"] == "MANDATE_SELF_REVOKE"
    assert api.platform.post(f"/api/v1/platform/mandates/{m['id']}/end", {"version": 1}).status_code == 422
    ended = api.platform.post(f"/api/v1/platform/mandates/{m['id']}/end", {"version": 1, "reason": "Contract ended"})
    assert ended.json()["status"] == "ENDED" and ended.json()["active_staff"] == 0
    assert juma.get("/api/v1/tenant/machines").json()["error"]["code"] == "MANDATE_ENDED"
    closed = assign(api, m, "juma@asseta.local", "manager")
    assert closed.json()["error"]["code"] == "MANDATE_CLOSED"


def test_scope_membership_and_staff_rules(api: Api, client_tenant: dict[str, Any]) -> None:
    tid = client_tenant["tenant"]["id"]
    m = grant(api, tid, scope="OPERATIONS")
    roles = {r["key"] for r in api.platform.get(f"/api/v1/platform/mandates/{m['id']}/roles").json()}
    assert "owner" not in roles and "manager" in roles  # owner administers users and mandates
    staff(api, "staff-neema", "neema@asseta.example.com")
    assert assign(api, m, "neema@asseta.example.com", "owner").json()["error"]["code"] == "MANDATE_ROLE_SCOPE"
    owner_uid = client_tenant["owner"].get("/api/v1/tenant/access/members").json()[0]["user_id"]
    not_staff = api.platform.post(
        f"/api/v1/platform/mandates/{m['id']}/assignments", {"user_id": owner_uid, "role_key": "manager"}
    )
    assert not_staff.json()["error"]["code"] == "MANDATE_NOT_PLATFORM_STAFF"
    # A platform staff member the client invited as an ordinary user: gated, and cannot also be mandate staff.
    invited = client_tenant["owner"].post(
        "/api/v1/tenant/access/members",
        {"email": "neema@asseta.example.com", "first_name": "Neema", "last_name": "S", "role_key": "manager"},
    )
    assert invited.status_code == 201, invited.text
    assert assign(api, m, "neema@asseta.example.com", "manager").json()["error"]["code"] == "MANDATE_STAFF_IS_MEMBER"
    neema = Actor(api, "staff-neema", sorted(api.idp.memberships["staff-neema"]), tid, email="neema@asseta.example.com")
    assert neema.get("/api/v1/tenant/machines").json()["error"]["code"] == "MANDATE_REQUIRED"


def test_scheduled_and_expired_mandates_give_no_access(api: Api, client_tenant: dict[str, Any]) -> None:
    tid = client_tenant["tenant"]["id"]
    today = api.clock.now.date()
    m = grant(
        api, tid, starts_on=(today + timedelta(days=1)).isoformat(), ends_on=(today + timedelta(days=2)).isoformat()
    )
    assert m["status"] == "SCHEDULED"
    staff(api, "staff-peter", "peter@asseta.local")
    assign(api, m, "peter@asseta.local", "manager")
    peter = refreshed(api, Actor(api, "staff-peter", [], email="peter@asseta.local"), tid)
    assert peter.get("/api/v1/tenant/machines").json()["error"]["code"] == "MANDATE_ENDED"
    api.clock.set(today + timedelta(days=1))
    assert peter.get("/api/v1/tenant/machines").status_code == 200
    api.clock.set(today + timedelta(days=3))
    assert peter.get("/api/v1/tenant/machines").json()["error"]["code"] == "MANDATE_ENDED"
    assert api.platform.get(f"/api/v1/platform/mandates/{m['id']}").json()["status"] == "EXPIRED"


def test_two_different_staff_needed_for_approvals_under_mandate(api: Api, client_tenant: dict[str, Any]) -> None:
    tid = client_tenant["tenant"]["id"]
    m = grant(api, tid)
    a = staff(api, "staff-a", "a@asseta.local")
    b = staff(api, "staff-b", "b@asseta.local")
    assign(api, m, "a@asseta.local", "owner")
    assign(api, m, "b@asseta.local", "owner")
    a, b = refreshed(api, a, tid), refreshed(api, b, tid)
    machine = a.post("/api/v1/tenant/machines", {"asset_code": "EX-1", "name": "Dozer"}).json()
    reset = a.post(
        "/api/v1/tenant/meter-resets",
        {
            "machine_id": machine["id"],
            "old_reading": "100.0",
            "new_reading": "0.0",
            "effective_at": api.clock.now.isoformat(),
            "reason": "Hour meter replaced",
        },
    )
    assert reset.status_code == 201, reset.text
    rid = reset.json()["id"]
    own = a.post(f"/api/v1/tenant/meter-resets/{rid}/decision", {"outcome": "EXPLAINED", "note": "approve own"})
    assert own.json()["error"]["code"] == "SEGREGATION_OF_DUTIES"
    ok = b.post(f"/api/v1/tenant/meter-resets/{rid}/decision", {"outcome": "EXPLAINED", "note": "Workshop WS-9"})
    assert ok.json()["status"] == "APPROVED"


def test_database_guards_on_mandates(api: Api, client_tenant: dict[str, Any]) -> None:
    m = grant(api, client_tenant["tenant"]["id"])
    api.platform.post(f"/api/v1/platform/mandates/{m['id']}/end", {"version": 1, "reason": "Contract ended"})
    engine = create_engine(get_settings().database_url)
    with engine.connect() as conn, pytest.raises(Exception, match="closed mandate is immutable"):
        conn.execute(text("SELECT set_config('app.scope', 'platform', false)"))
        conn.execute(text("UPDATE managed_service_mandate SET status = 'ACTIVE' WHERE id = :i"), {"i": m["id"]})
    engine.dispose()
