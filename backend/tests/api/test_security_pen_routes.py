"""Penetration sweep over EVERY route (prompt.md §10 #11): the route inventory is derived from the app's dependency
metadata (`tests/support/routes.py`), so a new route is covered — or fails as unclassified — automatically.

(i)   no / malformed credentials -> 401 on every non-public route; gateway route needs its own key
(ii)  tenant-A token with tenant-B `X-Tenant-ID` -> 403 on every tenant route (plus missing / malformed header)
(iii) tenant token on every platform route -> 403; platform staff without a mandate on every tenant route -> 403
(iv)  per permission in the catalog: a role holding every permission of its scope EXCEPT that one -> 403 on every
      route guarded by it, and the same role with the permission is not refused (proves the guard is that code)
"""

from collections import Counter
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import Response

from asseta.modules.identity.catalog import CATALOG, PermissionScope
from tests.support.api import Actor, Api
from tests.support.notify import sync_mirror
from tests.support.routes import GATEWAY, PUBLIC, Kind, RouteSpec, concrete, inventory

BODY_METHODS = {"POST", "PUT", "PATCH"}


def _app(api: Api) -> FastAPI:
    app: FastAPI = api.client.app  # type: ignore[assignment]
    return app


def _call(api: Api, spec: RouteSpec, headers: dict[str, str], values: dict[str, str] | None = None) -> Response:
    kw: dict[str, Any] = {"headers": headers}
    if spec.method in BODY_METHODS:
        kw["json"] = {}
    r: Response = api.client.request(spec.method, concrete(spec.path, values), **kw)
    return r


def _routes(api: Api, *kinds: Kind) -> list[RouteSpec]:
    return [r for r in inventory(_app(api)) if r.kind in kinds]


def _code(r: Response) -> str | None:
    try:
        code: str | None = r.json()["error"]["code"]
    except (ValueError, KeyError, TypeError):
        return None
    return code


def test_inventory_is_complete_and_every_guard_is_in_the_catalog(api: Api) -> None:
    routes = inventory(_app(api))  # raises on any unclassified route
    counts = Counter(r.kind for r in routes)
    # Cross-check against the OpenAPI document: every documented operation is in the inventory and vice versa.
    documented = {
        (m.upper(), p)
        for p, ops in _app(api).openapi()["paths"].items()
        for m in ops
        if m in {"get", "post", "put", "patch", "delete"}
    }
    http = {(r.method, r.path) for r in routes if r.kind is not Kind.WEBSOCKET}
    undocumented_public = {k for k in PUBLIC if k not in documented}
    assert documented == http - undocumented_public
    assert set(PUBLIC) <= http and set(GATEWAY) <= http
    assert counts[Kind.PUBLIC] == len(PUBLIC) and counts[Kind.GATEWAY] == len(GATEWAY)
    assert counts[Kind.WEBSOCKET] == 1
    assert counts[Kind.TENANT] > 150 and counts[Kind.PLATFORM] > 60  # sanity: the sweep really sees the app
    catalog = {p.code: p.scope for p in CATALOG.permissions()}
    for r in routes:
        for code in r.codes:
            expected = PermissionScope.TENANT if r.kind is Kind.TENANT else PermissionScope.PLATFORM
            assert catalog.get(code) is expected, f"{r.label}: {code} not a {expected} catalog permission"
    print(f"\nROUTE INVENTORY {len(routes)}: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))


def test_unauthenticated_and_forged_credentials_refused_everywhere(api: Api) -> None:
    from cryptography.hazmat.primitives.asymmetric import rsa

    protected = _routes(api, Kind.TENANT, Kind.PLATFORM, Kind.SELF)
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = api.tokens.mint("attacker", ["/platform/platform-owner"], key=other_key)
    expired = api.tokens.mint("attacker", ["/platform/platform-owner"], ttl=-120)
    variants: list[dict[str, str]] = [
        {},
        {"Authorization": "Bearer"},
        {"Authorization": "Basic YWRtaW46YWRtaW4="},
        {"Authorization": "Bearer not.a.jwt"},
        {"Authorization": f"Bearer {forged}"},
        {"Authorization": f"Bearer {expired}"},
    ]
    failures = []
    for spec in protected:
        for i, headers in enumerate(variants):
            r = _call(api, spec, {**headers, "X-Tenant-ID": "00000000-0000-4000-8000-000000000001"})
            if r.status_code != 401 or _code(r) != "NOT_AUTHENTICATED":
                failures.append(f"{spec.label} variant#{i} -> {r.status_code} {r.text[:120]}")
    assert not failures, "\n".join(failures)
    print(f"\n(i) unauthenticated: {len(protected)} routes x {len(variants)} credential variants -> 401")

    # Gateway ingestion: its own credential, never a user token.
    for spec in _routes(api, Kind.GATEWAY):
        for headers in ({}, {"X-Asseta-Gateway-Key": "guess"}, {"Authorization": f"Bearer {forged}"}):
            r = _call(api, spec, headers)
            assert r.status_code == 401, (spec.label, headers, r.text)
    for spec in _routes(api, Kind.PUBLIC):
        assert _call(api, spec, {}).status_code == 200, spec.label


@pytest.fixture
def two_tenants(api: Api) -> tuple[dict[str, Any], dict[str, Any]]:
    a = api.onboard("Pen Alpha", price="1000")
    b = api.onboard("Pen Bravo", price="2000")
    return a, b


def test_wrong_missing_or_malformed_tenant_header_refused_on_every_tenant_route(
    api: Api, two_tenants: tuple[dict[str, Any], dict[str, Any]]
) -> None:
    a, b = two_tenants
    owner_a: Actor = a["owner"]
    token = api.tokens.mint(owner_a.subject, owner_a.groups, email=owner_a.email)
    tenant_routes = _routes(api, Kind.TENANT)
    cases = [
        (b["tenant"]["id"], "TENANT_ACCESS_DENIED"),  # another real tenant
        ("00000000-0000-4000-8000-000000000000", "TENANT_ACCESS_DENIED"),  # unknown tenant
        (None, "TENANT_REQUIRED"),
        ("' OR 1=1 --", "TENANT_REQUIRED"),
    ]
    failures = []
    for spec in tenant_routes:
        for tenant, code in cases:
            headers = {"Authorization": f"Bearer {token}"}
            if tenant is not None:
                headers["X-Tenant-ID"] = tenant
            r = _call(api, spec, headers)
            if r.status_code != 403 or _code(r) != code:
                failures.append(f"{spec.label} tenant={tenant} -> {r.status_code} {r.text[:120]}")
    assert not failures, "\n".join(failures)
    print(f"\n(ii) wrong tenant: {len(tenant_routes)} routes x {len(cases)} header cases -> 403")


def test_platform_and_tenant_boundaries_on_every_route(
    api: Api, two_tenants: tuple[dict[str, Any], dict[str, Any]]
) -> None:
    a, _ = two_tenants
    owner_a: Actor = a["owner"]
    tenant_token = api.tokens.mint(owner_a.subject, owner_a.groups, email=owner_a.email)
    failures = []
    platform_routes = _routes(api, Kind.PLATFORM)
    for spec in platform_routes:  # a tenant owner (with or without its tenant header) has no platform permission
        for headers in (
            {"Authorization": f"Bearer {tenant_token}"},
            {"Authorization": f"Bearer {tenant_token}", "X-Tenant-ID": a["tenant"]["id"]},
        ):
            r = _call(api, spec, headers)
            if r.status_code != 403:
                failures.append(f"{spec.label} as tenant owner -> {r.status_code} {r.text[:120]}")
    # Platform owner, even holding a Keycloak group of the tenant, needs an in-force mandate (ADR-004).
    sneaky = api.tokens.mint(
        "platform-owner-subject", ["/platform/platform-owner", f"/tenants/{a['tenant']['id']}/owner"]
    )
    tenant_routes = _routes(api, Kind.TENANT)
    for spec in tenant_routes:
        r = _call(api, spec, {"Authorization": f"Bearer {sneaky}", "X-Tenant-ID": a["tenant"]["id"]})
        if r.status_code != 403 or _code(r) != "MANDATE_REQUIRED":
            failures.append(f"{spec.label} as platform staff -> {r.status_code} {r.text[:120]}")
    assert not failures, "\n".join(failures)
    print(f"\n(iii) tenant->platform {len(platform_routes)} x 2, platform->tenant {len(tenant_routes)} -> 403")


def _pentest_role(api: Api, scope_path: str, codes: set[str]) -> None:
    """A Keycloak role group with exactly `codes`, mirrored through the production sync path."""
    gid = api.idp.ensure_group(scope_path)
    api.idp.set_group_permissions(gid, codes)
    sync_mirror(api)


def test_every_permission_guard_denies_a_role_lacking_exactly_that_permission(
    api: Api, two_tenants: tuple[dict[str, Any], dict[str, Any]]
) -> None:
    a, _ = two_tenants
    tid = a["tenant"]["id"]
    routes = _routes(api, Kind.TENANT, Kind.PLATFORM)
    all_codes = {s: {p.code for p in CATALOG.permissions() if p.scope is s} for s in PermissionScope}
    tenant_path, platform_path = f"/tenants/{tid}/pentest", "/platform/pentest"
    tenant_actor = Actor(api, "pentest-tenant", [tenant_path], tid, email="pentest-t@pen.example.com")
    platform_actor = Actor(api, "pentest-platform", [platform_path], email="pentest-p@pen.example.com")
    by_guard: dict[tuple[Kind, frozenset[str]], list[RouteSpec]] = {}
    for spec in routes:
        by_guard.setdefault((spec.kind, spec.codes), []).append(spec)

    failures, checked, server_errors = [], 0, []
    for (kind, codes), specs in sorted(by_guard.items(), key=lambda kv: (kv[0][0], sorted(kv[0][1]))):
        scope = PermissionScope.TENANT if kind is Kind.TENANT else PermissionScope.PLATFORM
        path, actor = (tenant_path, tenant_actor) if kind is Kind.TENANT else (platform_path, platform_actor)
        tenant = tid if kind is Kind.TENANT else None
        _pentest_role(api, path, all_codes[scope] - codes)
        for spec in specs:
            r = _call(api, spec, actor.headers(spec.method != "GET", tenant))
            checked += 1
            if r.status_code != 403 or _code(r) != "PERMISSION_DENIED":
                failures.append(f"{spec.label} without {sorted(codes)} -> {r.status_code} {r.text[:120]}")
        _pentest_role(api, path, all_codes[scope])  # positive control: same role, permission restored
        for spec in specs:
            r = _call(api, spec, actor.headers(spec.method != "GET", tenant))
            if r.status_code in (401, 403) and _code(r) in ("NOT_AUTHENTICATED", "PERMISSION_DENIED"):
                failures.append(f"{spec.label} WITH {sorted(codes)} still refused -> {r.text[:120]}")
            if r.status_code >= 500:
                server_errors.append(f"{spec.label} -> {r.status_code} {r.text[:120]}")
    assert not failures, "\n".join(failures)
    assert not server_errors, "random ids / empty bodies must not crash a route:\n" + "\n".join(server_errors)
    print(f"\n(iv) permission guards: {len(by_guard)} distinct guards, {checked} routes denied without their code")
