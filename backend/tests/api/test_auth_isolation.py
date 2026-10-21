"""Gate 0 acceptance: authentication, deny-by-default authorization, tenant boundary (API + DB/RLS)."""

import uuid

from sqlalchemy import create_engine, text

from asseta.core.config import get_settings
from tests.support.api import Actor, Api


def test_health_live_and_unauthenticated_denied(api: Api) -> None:
    assert api.client.get("/api/v1/health/live").json() == {"status": "ok"}
    r = api.client.get("/api/v1/platform/tenants")
    assert r.status_code == 401
    body = r.json()["error"]
    assert body["code"] == "NOT_AUTHENTICATED" and uuid.UUID(body["correlation_id"])


def test_invalid_tokens_rejected(api: Api) -> None:
    from cryptography.hazmat.primitives.asymmetric import rsa

    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    bad = [
        api.tokens.mint("x", ["/platform/platform-owner"], key=other_key),
        api.tokens.mint("x", ["/platform/platform-owner"], ttl=-120),
        api.tokens.mint("x", ["/platform/platform-owner"], audience="other-client"),
        api.tokens.mint("x", ["/platform/platform-owner"], issuer="http://evil/realms/asseta"),
    ]
    for token in bad:
        r = api.client.get("/api/v1/platform/tenants", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401, token


def test_correlation_id_propagates(api: Api) -> None:
    cid = str(uuid.uuid4())
    r = api.client.get("/api/v1/platform/tenants", headers={"X-Correlation-ID": cid})
    assert r.headers["x-correlation-id"] == cid and r.json()["error"]["correlation_id"] == cid


def test_catalog_synced_and_me(api: Api) -> None:
    assert {"platform.tenant.create", "tenant.machine.write"} <= api.idp.permission_roles
    me = api.platform.get("/api/v1/me").json()
    assert "platform.tenant.create" in me["platform_permissions"]
    assert any(m["key"] == "platform.tenants" for m in me["platform_menus"]) and me["tenants"] == []


def test_tenant_isolation_api_and_rls(api: Api) -> None:
    a = api.onboard("Alpha Plant", price="75000")
    b = api.onboard("Bravo Earthmovers", price="50000")
    owner_a, owner_b = a["owner"], b["owner"]
    [machine_a] = api.add_machines(owner_a, 1)

    # B cannot see or reference A's machine, even by guessing the ID.
    assert owner_b.get("/api/v1/tenant/machines").json()["total"] == 0
    r = owner_b.post("/api/v1/tenant/billing/enrollments", {"machine_id": machine_a, "effective_from": "2026-11-01"})
    assert r.status_code == 404
    # B cannot switch into A's tenant by header.
    r = owner_b.get("/api/v1/tenant/machines", tenant=a["tenant"]["id"])
    assert r.status_code == 403 and r.json()["error"]["code"] == "TENANT_ACCESS_DENIED"
    # Token subject alone grants nothing: same subject, no groups.
    bare = Actor(api, owner_a.subject, [], a["tenant"]["id"])
    assert bare.get("/api/v1/tenant/machines").status_code == 403
    # Forged-looking groups for a tenant that has no role mirror grant no permissions.
    forged = Actor(api, "attacker", [f"/tenants/{a['tenant']['id']}/superuser"], a["tenant"]["id"])
    assert forged.get("/api/v1/tenant/machines").status_code == 403
    # Tenant users cannot reach platform endpoints; platform cannot read tenant business data.
    assert owner_a.get("/api/v1/platform/tenants").status_code == 403
    r = api.platform.get("/api/v1/tenant/machines", tenant=a["tenant"]["id"])
    assert r.status_code == 403
    # Missing tenant header on tenant route.
    r = Actor(api, owner_a.subject, owner_a.groups).get("/api/v1/tenant/machines")
    assert r.json()["error"]["code"] == "TENANT_REQUIRED"

    # Database layer: the application role sees nothing without scope, and only its tenant with scope.
    engine = create_engine(get_settings().database_url)
    with engine.begin() as conn:
        assert conn.execute(text("SELECT count(*) FROM machine")).scalar_one() == 0
        conn.execute(
            text("SELECT set_config('app.scope','tenant',true), set_config('app.tenant_id',:t,true)"),
            {"t": b["tenant"]["id"]},
        )
        assert conn.execute(text("SELECT count(*) FROM machine")).scalar_one() == 0
        assert (
            conn.execute(
                text("SELECT count(*) FROM platform_invoice WHERE tenant_id = :a"), {"a": a["tenant"]["id"]}
            ).scalar_one()
            == 0
        )
    with engine.begin() as conn:
        conn.execute(text("SELECT set_config('app.scope','platform',true)"))
        assert conn.execute(text("SELECT count(*) FROM machine")).scalar_one() == 0  # no tenant business data
        assert conn.execute(text("SELECT count(*) FROM tenant_subscription")).scalar_one() == 2
    engine.dispose()


def test_role_permissions_follow_keycloak_mirror(api: Api) -> None:
    a = api.onboard("Charlie Cranes", price="1000")
    tid = a["tenant"]["id"]
    sup = Actor(api, "sup-1", [f"/tenants/{tid}/supervisor"], tid)
    assert sup.get("/api/v1/tenant/machines").status_code == 403  # supervisor template lacks machine.read
    mgr = Actor(api, "mgr-1", [f"/tenants/{tid}/manager"], tid)
    assert mgr.get("/api/v1/tenant/machines").status_code == 200
    assert mgr.get("/api/v1/tenant/billing/subscription").status_code == 403
    me = mgr.get("/api/v1/me").json()
    assert me["tenants"][0]["tenant_id"] == tid and "tenant.billing.read" not in me["tenants"][0]["permissions"]
