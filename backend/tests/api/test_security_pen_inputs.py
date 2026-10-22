"""Hostile-input probes (prompt.md §10 #11, check viii/ix) over every route that takes query parameters.

* SQL meta characters / LIKE wildcards / NUL bytes in `q` on every searchable list: never a 5xx, never extra rows;
* junk in every query parameter of every GET route: validation (4xx), never a 5xx;
* oversized JSON fields and bodies, oversized evidence and sync chunks: clean 4xx;
* CSV formula injection: neutralised by `reports.render.safe_csv_cell` (end-to-end in
  tests/api/test_reports.py::test_csv_matches_list_endpoints_for_the_same_filters; every trigger char below).
Path traversal in object keys / file names: tests/api/test_security_pen_sessions.py.
"""

import hashlib
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import Response

from asseta.modules.reports.render import safe_csv_cell
from tests.support.api import Actor, Api
from tests.support.jobs import setup_job, unique_jpeg
from tests.support.routes import Kind, RouteSpec, concrete, inventory

SQLI = [
    "' OR 1=1 --",
    "'; DROP TABLE machine; --",
    '" OR ""="',
    "%",
    "_",
    "\\",
    "%' UNION SELECT keycloak_subject FROM app_user --",
    "\x00",
    "a" * 5000,
]


def _routes(api: Api) -> list[RouteSpec]:
    app: FastAPI = api.client.app  # type: ignore[assignment]
    return inventory(app)


def _actor(spec: RouteSpec, tenant_owner: Actor, platform: Actor) -> Actor:
    return tenant_owner if spec.kind is Kind.TENANT else platform


def _get(api: Api, actor: Actor, spec: RouteSpec, query: dict[str, str]) -> Response:
    r: Response = api.client.get(concrete(spec.path), headers=actor.headers(False, None), params=query)
    return r


def test_sql_meta_characters_in_every_search_box_are_inert(api: Api) -> None:
    c = setup_job(api, "Inject Co", "INJ-1")  # data present, so an injected OR 1=1 would surface rows
    owner = c.owner
    searchable = [r for r in _routes(api) if r.method == "GET" and "q" in r.query and r.kind is not Kind.SELF]
    failures, checked = [], 0
    for spec in searchable:
        for q in SQLI:
            r = _get(api, _actor(spec, owner, api.platform), spec, {"q": q})
            checked += 1
            if r.status_code >= 500:
                failures.append(f"{spec.label} q={q[:30]!r} -> {r.status_code} {r.text[:150]}")
            elif r.status_code == 200 and q.startswith(("'", '"', "%'")):
                body = r.json()
                items = body.get("items", []) if isinstance(body, dict) else body
                if items:
                    failures.append(f"{spec.label} q={q[:30]!r} returned {len(items)} rows")
    assert not failures, "\n".join(failures)
    print(f"\n(viii) search injection: {len(searchable)} searchable routes x {len(SQLI)} payloads, no 5xx/extra rows")


def test_junk_in_every_query_parameter_never_crashes(api: Api) -> None:
    c = setup_job(api, "Fuzz Co", "FUZ-1")
    with_query = [r for r in _routes(api) if r.method == "GET" and r.query and r.kind in (Kind.TENANT, Kind.PLATFORM)]
    junk = ["' OR '1'='1", "-1", "99999999999999999999", "2026-13-45", "../../etc/passwd", "\x00", "NaN"]
    failures, checked = [], 0
    for spec in with_query:
        for value in junk:
            r = _get(api, _actor(spec, c.owner, api.platform), spec, dict.fromkeys(spec.query, value))
            checked += 1
            if r.status_code >= 500:
                failures.append(f"{spec.label} ={value!r} -> {r.status_code} {r.text[:150]}")
    assert not failures, "\n".join(failures)
    print(f"\n(viii) query fuzz: {len(with_query)} routes x {len(junk)} junk values (all params) -> no 5xx")


def test_hostile_path_segments_are_rejected_cleanly(api: Api) -> None:
    c = setup_job(api, "Path Co", "PTH-1")
    for seg in ("..%2F..%2Fetc%2Fpasswd", "%00", "1%20OR%201=1", "%27", "..", "%2e%2e"):
        for path in (f"/api/v1/tenant/machines/{seg}", f"/api/v1/tenant/attachments/{seg}/url"):
            r = api.client.get(path, headers=c.owner.headers(False, None))
            assert r.status_code in (404, 422), (path, r.status_code, r.text)


def test_oversized_inputs_are_refused_without_server_errors(api: Api) -> None:
    c = setup_job(api, "Big Co", "BIG-1")
    owner = c.owner
    big_field = owner.post("/api/v1/tenant/machines", {"asset_code": "BIG", "name": "x" * 1_000_000})
    assert big_field.status_code == 422 and big_field.json()["error"]["code"] == "VALIDATION_FAILED"
    nul = owner.post("/api/v1/tenant/machines", {"asset_code": "NUL", "name": "bad\x00name"})
    assert nul.status_code == 422 and nul.json()["error"]["code"] == "INVALID_INPUT", nul.text
    big_body = owner.post("/api/v1/tenant/customers", {"code": "C9", "name": "ok", "junk": ["y" * 1000] * 2000})
    assert big_body.status_code in (201, 422), big_body.text  # ~2 MB of unknown fields is ignored, not a crash
    too_big = b"\xff\xd8\xff\xe0" + b"\x00" * (10 * 1024 * 1024 + 10)
    r = api.client.post(
        "/api/v1/tenant/attachments",
        headers=owner.headers(True, None),
        files={"file": ("big.jpg", too_big, "image/jpeg")},
        data={"purpose": "METER_PHOTO"},
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "FILE_TOO_LARGE", r.text


def test_sync_chunk_larger_than_declared_is_refused(api: Api) -> None:
    c = setup_job(api, "Chunk Co", "CHK-1")
    tid = c.t.tenant["tenant"]["id"]
    sup = Actor(api, "sup-chunk", [f"/tenants/{tid}/supervisor"], tid, email="chunk@pen.example.com")
    h: dict[str, Any] = {**sup.headers(True, None), "X-Device-Id": "chunk-dev"}
    api.client.post(
        "/api/v1/sync/devices", headers=h, json={"device_id": "chunk-dev", "platform": "IOS", "app_version": "1"}
    )
    data = unique_jpeg()
    s = api.client.post(
        "/api/v1/sync/blobs",
        headers=h,
        json={"sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data), "purpose": "METER_PHOTO"},
    ).json()
    oversized = api.client.put(
        f"/api/v1/sync/blobs/{s['id']}/chunks/0", headers=h, content=b"z" * (2 * s["chunk_size"])
    )
    assert oversized.status_code == 422 and oversized.json()["error"]["code"] == "BAD_CHUNK", oversized.text
    declared = api.client.post(
        "/api/v1/sync/blobs", headers=h, json={"sha256": "c" * 64, "size_bytes": 10**9, "purpose": "METER_PHOTO"}
    )
    assert declared.json()["error"]["code"] == "FILE_TOO_LARGE"


@pytest.mark.parametrize("trigger", ["=", "+", "-", "@", "\t", "\r"])
def test_csv_formula_triggers_are_neutralised(trigger: str) -> None:
    assert safe_csv_cell(f'{trigger}HYPERLINK("http://evil")', numeric=False).startswith("'")
    assert safe_csv_cell("-12.50", numeric=True) == "-12.50"  # real numbers in numeric columns stay numbers
