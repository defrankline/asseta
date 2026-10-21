"""Live Keycloak integration (DEC-005): real realm import, real Admin REST adapter, real JWKS verification.

Run with a disposable Keycloak started from infra/keycloak/realm-asseta.json:
    ASSETA_IT_KEYCLOAK_URL=http://localhost:8080 uv run pytest -m integration
"""

import os
import uuid
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from asseta.core.config import Settings, get_settings
from asseta.main import create_app

KC = os.environ.get("ASSETA_IT_KEYCLOAK_URL", "")
API_SECRET = os.environ.get("ASSETA_IT_API_SECRET", "dev-asseta-api-secret")
IT_CLIENT, IT_SECRET = "asseta-integration-test", "it-secret-" + uuid.uuid4().hex[:8]
REALM_FILE = __import__("pathlib").Path(__file__).parents[3] / "infra/keycloak/realm-asseta.json"
# Same token mappers as the real public clients, so test tokens have production claim shape.
WEB_MAPPERS = next(
    c for c in __import__("json").loads(REALM_FILE.read_text())["clients"] if c["clientId"] == "asseta-web"
)["protocolMappers"]
pytestmark = [pytest.mark.integration, pytest.mark.skipif(not KC, reason="ASSETA_IT_KEYCLOAK_URL not set")]


class KcAdmin:
    """Master-realm admin used only to arrange fixtures (test client, passwords, membership changes)."""

    def __init__(self) -> None:
        r = httpx.post(
            f"{KC}/realms/master/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": "admin-cli",
                "username": os.environ.get("ASSETA_IT_ADMIN_USER", "admin"),
                "password": os.environ.get("ASSETA_IT_ADMIN_PASSWORD", "admin"),
            },
        )
        r.raise_for_status()
        self.h = {"Authorization": f"Bearer {r.json()['access_token']}"}
        self.base = f"{KC}/admin/realms/asseta"

    def call(self, method: str, path: str, **kw: Any) -> httpx.Response:
        return httpx.request(method, self.base + path, headers=self.h, timeout=10, **kw)

    def ensure_test_client(self) -> None:
        existing = self.call("GET", "/clients", params={"clientId": IT_CLIENT}).json()
        for c in existing:
            self.call("DELETE", f"/clients/{c['id']}")
        r = self.call(
            "POST",
            "/clients",
            json={
                "clientId": IT_CLIENT,
                "publicClient": False,
                "secret": IT_SECRET,
                "directAccessGrantsEnabled": True,
                "standardFlowEnabled": False,
                "defaultClientScopes": ["basic", "profile", "email"],
                "protocolMappers": WEB_MAPPERS,
            },
        )
        assert r.status_code == 201, r.text

    def user_id(self, email: str) -> str:
        return str(self.call("GET", "/users", params={"email": email, "exact": "true"}).json()[0]["id"])

    def create_user(self, email: str) -> str:
        r = self.call(
            "POST",
            "/users",
            json={
                "username": email,
                "email": email,
                "enabled": True,
                "emailVerified": True,
                "firstName": "P",
                "lastName": "O",
            },
        )
        assert r.status_code == 201, r.text
        return self.user_id(email)

    def set_password(self, user_id: str, password: str) -> None:
        self.call(
            "PUT",
            f"/users/{user_id}",
            json={"requiredActions": [], "emailVerified": True, "firstName": "T", "lastName": "U"},
        )
        r = self.call(
            "PUT", f"/users/{user_id}/reset-password", json={"type": "password", "value": password, "temporary": False}
        )
        assert r.status_code == 204, r.text

    def group_id(self, path: str) -> str:
        return str(self.call("GET", f"/group-by-path/{path.strip('/')}").json()["id"])

    def join(self, user_id: str, path: str) -> None:
        assert self.call("PUT", f"/users/{user_id}/groups/{self.group_id(path)}").status_code == 204

    def leave(self, user_id: str, path: str) -> None:
        assert self.call("DELETE", f"/users/{user_id}/groups/{self.group_id(path)}").status_code == 204


def password_token(username: str, password: str) -> str:
    r = httpx.post(
        f"{KC}/realms/asseta/protocol/openid-connect/token",
        data={
            "grant_type": "password",
            "client_id": IT_CLIENT,
            "client_secret": IT_SECRET,
            "username": username,
            "password": password,
            "scope": "openid",
        },
    )
    assert r.status_code == 200, r.text
    return str(r.json()["access_token"])


@pytest.fixture
def kc() -> KcAdmin:
    admin = KcAdmin()
    admin.ensure_test_client()
    return admin


@pytest.fixture
def live_client(kc: KcAdmin) -> Iterator[TestClient]:
    settings = Settings(
        keycloak_url=KC, keycloak_api_client_secret=API_SECRET, database_url=get_settings().database_url
    )
    with TestClient(create_app(settings=settings), raise_server_exceptions=False) as client:
        yield client


def test_live_keycloak_authn_authz_round_trip(kc: KcAdmin, live_client: TestClient) -> None:
    pw = "It-" + uuid.uuid4().hex
    platform_email = f"platform-{uuid.uuid4().hex[:6]}@asseta.local"
    pid = kc.create_user(platform_email)
    kc.set_password(pid, pw)
    kc.join(pid, "/platform/platform-owner")

    def call(method: str, path: str, token: str, tenant: str | None = None, body: Any = None) -> httpx.Response:
        headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": str(uuid.uuid4())}
        if tenant:
            headers["X-Tenant-ID"] = tenant
        resp: httpx.Response = live_client.request(method, path, headers=headers, json=body)
        return resp

    ptoken = password_token(platform_email, pw)
    me = call("GET", "/api/v1/me", ptoken).json()
    assert "platform_permissions" in me, me
    assert "platform.tenant.create" in me["platform_permissions"], me  # catalog pushed + mapped in Keycloak

    owner_email = f"owner-{uuid.uuid4().hex[:6]}@example.com"
    onboard = call(
        "POST",
        "/api/v1/platform/tenants",
        ptoken,
        body={
            "legal_name": "Live KC Ltd",
            "display_name": "Live KC",
            "contact_name": "Live Owner",
            "contact_email": owner_email,
            "timezone": "Africa/Dar_es_Salaam",
            "currency": "TZS",
            "owner": {"email": owner_email, "first_name": "Ow", "last_name": "Ner"},
            "subscription": {
                "start_date": "2026-11-01",
                "rate": {"currency": "TZS", "cadence": "MONTHLY", "unit_price": "75000", "minimum_billable_assets": 1},
            },
        },
    )
    assert onboard.status_code == 201, onboard.text
    tenant_id = onboard.json()["tenant"]["id"]

    owner_id = kc.user_id(owner_email)  # created by the API through the Keycloak Admin REST adapter
    kc.set_password(owner_id, pw)
    otoken = password_token(owner_email, pw)
    assert call("GET", "/api/v1/tenant/machines", otoken, tenant_id).status_code == 200
    created = call("POST", "/api/v1/tenant/machines", otoken, tenant_id, {"asset_code": "KC-1", "name": "Live"})
    assert created.status_code == 201, created.text
    assert call("GET", "/api/v1/tenant/machines", otoken, str(uuid.uuid4())).status_code == 403
    assert call("GET", "/api/v1/platform/tenants", otoken).status_code == 403

    # Revocation in Keycloak is authoritative: next token carries no tenant group -> denied.
    kc.leave(owner_id, f"/tenants/{tenant_id}/owner")
    revoked = password_token(owner_email, pw)
    assert call("GET", "/api/v1/tenant/machines", revoked, tenant_id).status_code == 403
