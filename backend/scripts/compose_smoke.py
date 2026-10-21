"""End-to-end smoke test against a running `docker compose` stack (deployed images, real Keycloak/Kafka).

Usage (from backend/): uv run python scripts/compose_smoke.py ../.env
Creates a throwaway test client + platform user in Keycloak, logs in, onboards a tenant through the API,
uses the tenant owner's real token, and verifies the outbox relay published the domain events.
"""

import sys
import time
import uuid
from collections.abc import Callable
from pathlib import Path

import httpx
import psycopg

env = dict(
    line.split("=", 1)
    for line in Path(sys.argv[1]).read_text().splitlines()
    if "=" in line and not line.startswith("#")
)
KC = env.get("ASSETA_PUBLIC_KEYCLOAK_URL", "http://localhost:8080")
API = f"http://localhost:{env.get('ASSETA_API_PORT', '8000')}/api/v1"


def admin_headers() -> dict[str, str]:
    r = httpx.post(
        f"{KC}/realms/master/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": env["KEYCLOAK_ADMIN_USER"],
            "password": env["KEYCLOAK_ADMIN_PASSWORD"],
        },
    )
    r.raise_for_status()
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def telemetry_smoke(ph: dict[str, str], oh: dict[str, str], tenant_id: str, machine_id: str) -> None:
    """Simulated device -> real Traccar (OsmAnd) -> forward -> Asseta ingest -> PostGIS -> Kafka timeline -> map."""
    from datetime import UTC, datetime, timedelta

    from asseta.tools.gps_simulator import route, send_osmand

    def key() -> dict[str, str]:
        return {"Idempotency-Key": str(uuid.uuid4())}

    today = time.strftime("%Y-%m-%d")
    e = httpx.post(
        f"{API}/tenant/billing/enrollments",
        headers={**oh, **key()},
        json={"machine_id": machine_id, "effective_from": today},
    )
    assert e.status_code == 201, e.text
    model = httpx.post(
        f"{API}/platform/tracker-models",
        headers={**ph, **key()},
        json={
            "manufacturer": "Simulated",
            "model": f"OsmAnd-{uuid.uuid4().hex[:4]}",
            "adapter": "TRACCAR",
            "protocol": "osmand",
            "declared_capabilities": ["GNSS", "ACCURACY", "IGNITION"],
        },
    )
    assert model.status_code == 201, model.text
    device = "35" + str(uuid.uuid4().int)[:13]  # IMEI-shaped id, as real trackers report (Traccar regex \w{3,15})
    tr = httpx.post(
        f"{API}/tenant/trackers",
        headers={**oh, **key()},
        json={"tracker_model_id": model.json()["id"], "external_id": device, "label": device},
    )
    assert tr.status_code == 201, tr.text
    start = datetime.now(UTC) - timedelta(seconds=90)
    a = httpx.post(
        f"{API}/tenant/trackers/{tr.json()['id']}/assign",
        headers={**oh, **key()},
        json={"machine_id": machine_id, "effective_from": (start - timedelta(minutes=1)).isoformat()},
    )
    assert a.status_code == 201, a.text
    fixes = route([(-6.8, 39.28), (-6.799, 39.281)], start, 15.0, 15)[:6]
    traccar = f"http://localhost:{env.get('ASSETA_TRACCAR_OSMAND_PORT', '5055')}"
    assert send_osmand(traccar, device, fixes) == len(fixes), "Traccar did not accept OsmAnd messages"
    row: dict[str, object] = {}
    for _ in range(60):
        fleet = httpx.get(f"{API}/tenant/fleet/map", headers=oh).json()
        row = next(r for r in fleet if r["machine_id"] == machine_id)
        if row["position_time"]:
            break
        time.sleep(1)
    assert row.get("position_source") == f"TRACKER:{device}", row
    assert row["connectivity"] in ("LIVE", "RECENT"), row
    print(
        f"TELEMETRY OK device={device} via Traccar -> {row['latitude']},{row['longitude']} "
        f"({row['connectivity']}, engine={row['observed_engine']})"
    )


def mandate_smoke(
    ph: dict[str, str], oh: dict[str, str], tenant_id: str, platform_email: str, login: Callable[[str], str]
) -> None:
    """Managed service against real Keycloak: no access without a mandate; assignment materializes the client's
    Keycloak group; ending the mandate refuses the still-valid token on the next request (DEC-018)."""
    acting = {"Authorization": f"Bearer {login(platform_email)}", "X-Tenant-ID": tenant_id}
    assert httpx.get(f"{API}/tenant/machines", headers=acting).json()["error"]["code"] == "MANDATE_REQUIRED"
    grant = httpx.post(
        f"{API}/platform/mandates",
        headers={**ph, "Idempotency-Key": str(uuid.uuid4())},
        json={
            "tenant_id": tenant_id,
            "scope": "FULL",
            "starts_on": time.strftime("%Y-%m-%d"),
            "consent_reference": "SMOKE-MSA-1",
        },
    )
    assert grant.status_code == 201, grant.text
    mandate = grant.json()
    me_id = httpx.get(f"{API}/me", headers=ph).json()["user_id"]
    staff = httpx.get(f"{API}/platform/mandates/staff", headers=ph).json()
    assert me_id in {s["user_id"] for s in staff}, staff  # listed from the real Keycloak platform groups
    r = httpx.post(
        f"{API}/platform/mandates/{mandate['id']}/assignments",
        headers=ph,
        json={"user_id": me_id, "role_key": "manager"},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    acting = {"Authorization": f"Bearer {login(platform_email)}", "X-Tenant-ID": tenant_id}  # refreshed groups
    assert httpx.get(f"{API}/tenant/machines", headers=acting).status_code == 200
    view = httpx.get(f"{API}/tenant/managed-service", headers=oh).json()
    assert view["mandate"]["reference"] == mandate["reference"], view
    end = httpx.post(
        f"{API}/platform/mandates/{mandate['id']}/end",
        headers=ph,
        json={"version": mandate["version"], "reason": "Smoke test complete"},
        timeout=30,
    )
    assert end.status_code == 200, end.text
    assert httpx.get(f"{API}/tenant/machines", headers=acting).json()["error"]["code"] == "MANDATE_ENDED"
    fresh = {"Authorization": f"Bearer {login(platform_email)}", "X-Tenant-ID": tenant_id}
    assert httpx.get(f"{API}/tenant/machines", headers=fresh).json()["error"]["code"] == "MANDATE_ENDED"
    print(f"MANDATE OK {mandate['reference']}")


def main() -> None:
    h, base = admin_headers(), f"{KC}/admin/realms/asseta"
    secret = uuid.uuid4().hex
    web = next(c for c in httpx.get(f"{base}/clients", params={"clientId": "asseta-web"}, headers=h).json())
    client_id = f"smoke-{uuid.uuid4().hex[:6]}"
    httpx.post(
        f"{base}/clients",
        headers=h,
        json={
            "clientId": client_id,
            "secret": secret,
            "publicClient": False,
            "directAccessGrantsEnabled": True,
            "standardFlowEnabled": False,
            "protocolMappers": [{k: v for k, v in m.items() if k != "id"} for m in web["protocolMappers"]],
        },
    ).raise_for_status()

    passwords: dict[str, str] = {}

    def login(email: str) -> str:
        tok = httpx.post(
            f"{KC}/realms/asseta/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": client_id,
                "client_secret": secret,
                "username": email,
                "password": passwords[email],
            },
        )
        tok.raise_for_status()
        return str(tok.json()["access_token"])

    def user(email: str, group: str | None) -> str:
        if group:
            httpx.post(
                f"{base}/users",
                headers=h,
                json={
                    "username": email,
                    "email": email,
                    "enabled": True,
                    "emailVerified": True,
                    "firstName": "S",
                    "lastName": "T",
                },
            )
        uid = httpx.get(f"{base}/users", params={"email": email, "exact": "true"}, headers=h).json()[0]["id"]
        httpx.put(
            f"{base}/users/{uid}",
            headers=h,
            json={"requiredActions": [], "emailVerified": True, "firstName": "S", "lastName": "T"},
        )
        pw = "Smoke-" + uuid.uuid4().hex
        httpx.put(
            f"{base}/users/{uid}/reset-password", headers=h, json={"type": "password", "value": pw, "temporary": False}
        ).raise_for_status()
        if group:
            gid = httpx.get(f"{base}/group-by-path/{group.strip('/')}", headers=h).json()["id"]
            httpx.put(f"{base}/users/{uid}/groups/{gid}", headers=h).raise_for_status()
        passwords[email] = pw
        return login(email)

    try:
        platform_email = f"smoke-platform-{uuid.uuid4().hex[:6]}@asseta.local"
        ptoken = user(platform_email, "/platform/platform-owner")
        ph = {"Authorization": f"Bearer {ptoken}"}
        me = httpx.get(f"{API}/me", headers=ph).json()
        assert "platform.tenant.create" in me["platform_permissions"], me
        owner_email = f"smoke-owner-{uuid.uuid4().hex[:6]}@example.com"
        r = httpx.post(
            f"{API}/platform/tenants",
            headers={**ph, "Idempotency-Key": str(uuid.uuid4())},
            json={
                "legal_name": "Smoke Test Ltd",
                "display_name": "Smoke Test",
                "contact_name": "Smoke Owner",
                "contact_email": owner_email,
                "timezone": "Africa/Dar_es_Salaam",
                "currency": "TZS",
                "owner": {"email": owner_email, "first_name": "Smoke", "last_name": "Owner"},
                "subscription": {
                    "start_date": time.strftime("%Y-%m-%d"),
                    "rate": {
                        "currency": "TZS",
                        "cadence": "MONTHLY",
                        "unit_price": "75000",
                        "minimum_billable_assets": 1,
                    },
                },
            },
            timeout=30,
        )
        assert r.status_code == 201, r.text
        tenant_id = r.json()["tenant"]["id"]
        otoken = user(owner_email, None)
        oh = {"Authorization": f"Bearer {otoken}", "X-Tenant-ID": tenant_id, "Idempotency-Key": str(uuid.uuid4())}
        m = httpx.post(f"{API}/tenant/machines", headers=oh, json={"asset_code": "SMK-1", "name": "Smoke excavator"})
        assert m.status_code == 201, m.text
        assert httpx.get(f"{API}/platform/tenants", headers={"Authorization": f"Bearer {otoken}"}).status_code == 403
        telemetry_smoke(ph, oh, tenant_id, m.json()["id"])
        mandate_smoke(ph, oh, tenant_id, platform_email, login)
        dsn = (
            f"postgresql://asseta_owner:{env['ASSETA_OWNER_DB_PASSWORD']}@localhost:"
            f"{env.get('ASSETA_PG_PORT', '5433')}/asseta"
        )
        unpublished, total = -1, 0
        for _ in range(30):
            with psycopg.connect(dsn) as conn:
                conn.execute("SELECT set_config('app.scope','system',false)")
                row = conn.execute(
                    "SELECT count(*) FILTER (WHERE published_at IS NULL), count(*) FROM outbox_event "
                    "WHERE tenant_id = %s",
                    (tenant_id,),
                ).fetchone()
            assert row is not None
            unpublished, total = int(row[0]), int(row[1])
            if total and unpublished == 0:
                break
            time.sleep(1)
        assert total > 0 and unpublished == 0, f"outbox not relayed: {unpublished}/{total} pending"
        print(f"SMOKE OK tenant={tenant_id} outbox_events_published={total}")
    finally:
        cid = httpx.get(f"{base}/clients", params={"clientId": client_id}, headers=h).json()[0]["id"]
        httpx.delete(f"{base}/clients/{cid}", headers=h)
        # Throwaway users (incl. a platform owner!) must not outlive the run.
        for email in passwords:
            for u in httpx.get(f"{base}/users", params={"email": email, "exact": "true"}, headers=h).json():
                httpx.delete(f"{base}/users/{u['id']}", headers=h)


if __name__ == "__main__":
    main()
