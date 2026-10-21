"""Keycloak Admin REST adapter (client-credentials service account of `asseta-api`).

Bounded timeouts + retries on transient failures. Permission roles are client roles `perm:<code>` on the
API client; role groups live under `/platform/<role>` and `/tenants/<tenant_id>/<role>`.
"""

import secrets
import time
from typing import Any
from urllib.parse import quote

import httpx

from asseta.core.errors import DependencyUnavailable
from asseta.modules.identity.catalog import KEYCLOAK_PERMISSION_ROLE_PREFIX, PLATFORM_GROUP_ROOT, TENANT_GROUP_ROOT
from asseta.modules.identity.idp import CreatedUser, GroupMember, RoleGroup

_RETRYABLE = {502, 503, 504}


class KeycloakAdminClient:
    def __init__(
        self, base_url: str, realm: str, client_id: str, client_secret: str, timeout: float, max_attempts: int = 3
    ):
        self._base = base_url.rstrip("/")
        self._realm = realm
        self._client_id = client_id
        self._client_secret = client_secret
        self._http = httpx.Client(timeout=timeout)
        self._max_attempts = max_attempts
        self._token: str | None = None
        self._token_expiry = 0.0
        self._client_uuid: str | None = None

    # --- transport ----------------------------------------------------------------------------------
    def _access_token(self) -> str:
        if self._token and time.monotonic() < self._token_expiry - 15:
            return self._token
        resp = self._http.post(
            f"{self._base}/realms/{self._realm}/protocol/openid-connect/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
            },
        )
        if resp.status_code != 200:
            raise DependencyUnavailable(f"Keycloak service-account login failed ({resp.status_code})")
        body = resp.json()
        self._token = str(body["access_token"])
        self._token_expiry = time.monotonic() + float(body.get("expires_in", 60))
        return self._token

    def _request(
        self, method: str, path: str, json: Any = None, params: dict[str, str] | None = None
    ) -> httpx.Response:
        url = f"{self._base}/admin/realms/{self._realm}{path}"
        last_error = ""
        for attempt in range(self._max_attempts):
            try:
                resp = self._http.request(
                    method, url, json=json, params=params, headers={"Authorization": f"Bearer {self._access_token()}"}
                )
            except httpx.TransportError as exc:
                last_error = type(exc).__name__
            else:
                if resp.status_code not in _RETRYABLE:
                    return resp
                last_error = f"HTTP {resp.status_code}"
            time.sleep(0.2 * 2**attempt)
        raise DependencyUnavailable(f"Keycloak admin API unavailable: {last_error}")

    def _ok(self, resp: httpx.Response, *allowed: int) -> httpx.Response:
        if resp.status_code not in (allowed or (200, 201, 204)):
            raise DependencyUnavailable(f"Keycloak admin call failed: {resp.status_code} {resp.text[:200]}")
        return resp

    def _api_client_uuid(self) -> str:
        if self._client_uuid is None:
            found = self._ok(self._request("GET", "/clients", params={"clientId": self._client_id})).json()
            if not found:
                raise DependencyUnavailable(f"Keycloak client {self._client_id} not found")
            self._client_uuid = str(found[0]["id"])
        return self._client_uuid

    # --- permission roles ---------------------------------------------------------------------------
    def ensure_permission_roles(self, codes: list[str], descriptions: dict[str, str]) -> None:
        cid = self._api_client_uuid()
        existing = {
            r["name"] for r in self._ok(self._request("GET", f"/clients/{cid}/roles", params={"max": "10000"})).json()
        }
        for code in codes:
            name = KEYCLOAK_PERMISSION_ROLE_PREFIX + code
            if name not in existing:
                self._ok(
                    self._request(
                        "POST", f"/clients/{cid}/roles", json={"name": name, "description": descriptions.get(code, "")}
                    ),
                    201,
                    409,
                )

    # --- groups -------------------------------------------------------------------------------------
    def _group_by_path(self, path: str) -> dict[str, Any] | None:
        resp = self._request("GET", f"/group-by-path/{quote(path.strip('/'), safe='/')}")
        if resp.status_code == 404:
            return None
        group: dict[str, Any] = self._ok(resp).json()
        return group

    def ensure_group(self, path: str) -> str:
        parts = [p for p in path.split("/") if p]
        parent_id: str | None = None
        current = ""
        for part in parts:
            current += "/" + part
            found = self._group_by_path(current)
            if found is None:
                endpoint = f"/groups/{parent_id}/children" if parent_id else "/groups"
                self._ok(self._request("POST", endpoint, json={"name": part}), 201, 409)
                found = self._group_by_path(current)
                if found is None:
                    raise DependencyUnavailable(f"Keycloak group {current} could not be created")
            parent_id = str(found["id"])
        assert parent_id is not None
        return parent_id

    def set_group_permissions(self, group_id: str, codes: set[str]) -> None:
        cid = self._api_client_uuid()
        mapping_path = f"/groups/{group_id}/role-mappings/clients/{cid}"
        current = {r["name"]: r for r in self._ok(self._request("GET", mapping_path)).json()}
        wanted = {KEYCLOAK_PERMISSION_ROLE_PREFIX + c for c in codes}
        all_roles = {
            r["name"]: r
            for r in self._ok(self._request("GET", f"/clients/{cid}/roles", params={"max": "10000"})).json()
        }
        to_add = [all_roles[n] for n in sorted(wanted - current.keys()) if n in all_roles]
        to_remove = [
            current[n] for n in sorted(current.keys() - wanted) if n.startswith(KEYCLOAK_PERMISSION_ROLE_PREFIX)
        ]
        if to_add:
            self._ok(self._request("POST", mapping_path, json=to_add))
        if to_remove:
            self._ok(self._request("DELETE", mapping_path, json=to_remove))

    def _children(self, group_id: str) -> list[dict[str, Any]]:
        children: list[dict[str, Any]] = self._ok(
            self._request("GET", f"/groups/{group_id}/children", params={"max": "10000"})
        ).json()
        return children

    def _group_permissions(self, group_id: str) -> frozenset[str]:
        cid = self._api_client_uuid()
        roles = self._ok(self._request("GET", f"/groups/{group_id}/role-mappings/clients/{cid}/composite")).json()
        prefix = KEYCLOAK_PERMISSION_ROLE_PREFIX
        return frozenset(r["name"][len(prefix) :] for r in roles if str(r["name"]).startswith(prefix))

    def list_role_groups(self) -> list[RoleGroup]:
        result: list[RoleGroup] = []
        platform = self._group_by_path(f"/{PLATFORM_GROUP_ROOT}")
        if platform:
            for role in self._children(str(platform["id"])):
                result.append(
                    RoleGroup(
                        str(role["id"]),
                        f"/{PLATFORM_GROUP_ROOT}/{role['name']}",
                        str(role["name"]),
                        self._group_permissions(str(role["id"])),
                    )
                )
        tenants = self._group_by_path(f"/{TENANT_GROUP_ROOT}")
        if tenants:
            for tenant in self._children(str(tenants["id"])):
                for role in self._children(str(tenant["id"])):
                    path = f"/{TENANT_GROUP_ROOT}/{tenant['name']}/{role['name']}"
                    result.append(
                        RoleGroup(str(role["id"]), path, str(role["name"]), self._group_permissions(str(role["id"])))
                    )
        return result

    # --- users --------------------------------------------------------------------------------------
    def create_user(self, email: str, first_name: str, last_name: str) -> CreatedUser:
        temporary = secrets.token_urlsafe(18)
        resp = self._request(
            "POST",
            "/users",
            json={
                "username": email,
                "email": email,
                "firstName": first_name,
                "lastName": last_name,
                "enabled": True,
                "emailVerified": False,
                "requiredActions": ["UPDATE_PASSWORD"],
                "credentials": [{"type": "password", "value": temporary, "temporary": True}],
            },
        )
        if resp.status_code == 409:
            from asseta.core.errors import Conflict

            raise Conflict("A user with this email already exists in the identity provider", code="USER_EXISTS")
        self._ok(resp, 201)
        subject = resp.headers["Location"].rstrip("/").rsplit("/", 1)[-1]
        return CreatedUser(subject=subject, temporary_password=temporary)

    def add_user_to_group(self, subject: str, group_id: str) -> None:
        self._ok(self._request("PUT", f"/users/{subject}/groups/{group_id}"))

    def remove_user_from_group(self, subject: str, group_id: str) -> None:
        self._ok(self._request("DELETE", f"/users/{subject}/groups/{group_id}"), 204, 404)

    def list_group_members(self, group_id: str) -> list[GroupMember]:
        rows = self._ok(
            self._request("GET", f"/groups/{group_id}/members", params={"max": "10000", "briefRepresentation": "true"})
        ).json()
        return [
            GroupMember(
                subject=str(r["id"]),
                email=str(r.get("email") or r.get("username", "")),
                display_name=" ".join(x for x in (r.get("firstName"), r.get("lastName")) if x)
                or str(r.get("username", "")),
            )
            for r in rows
        ]

    def find_user_by_email(self, email: str) -> str | None:
        rows = self._ok(self._request("GET", "/users", params={"email": email, "exact": "true"})).json()
        return str(rows[0]["id"]) if rows else None
