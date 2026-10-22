"""Route inventory for the security sweep: every HTTP/WebSocket route of the app, classified from its dependency
metadata (`requires(...)` / `requires_any(...)` closures, `get_claims`), never from a hand-maintained list.

Only genuinely public routes are hand-listed (`PUBLIC`, each with a justification); any route that is neither public
nor carries a recognised auth dependency makes `inventory()` raise, so a new unguarded route fails the suite.
"""

import inspect
import re
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from fastapi import FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute, APIWebSocketRoute, iter_route_contexts

from asseta.modules.identity.catalog import PermissionScope


class Kind(StrEnum):
    PUBLIC = "PUBLIC"  # no credential by design (allow-list below)
    GATEWAY = "GATEWAY"  # device gateway shared secret (X-Asseta-Gateway-Key), no end-user token
    WEBSOCKET = "WEBSOCKET"  # token sent in the first frame (tests/api/test_notification_ws.py)
    SELF = "SELF"  # any valid token; acts only on the caller's own records (/me, push devices)
    TENANT = "TENANT"  # requires(...) with TENANT scope: token + X-Tenant-ID membership + permission
    PLATFORM = "PLATFORM"  # requires(...) with PLATFORM scope


# (method, path) -> why it may be reached without credentials.
PUBLIC: dict[tuple[str, str], str] = {
    ("GET", "/api/v1/health/live"): "liveness probe for the orchestrator; returns only {'status': 'ok'}",
    ("GET", "/api/v1/health/ready"): "readiness probe; dependency up/down only, no data",
    ("GET", "/api/v1/openapi.json"): "published API contract (same file as contracts/openapi.json)",
    ("GET", "/api/v1/docs"): "Swagger UI shell for the public contract",
    ("GET", "/docs/oauth2-redirect"): "FastAPI default Swagger OAuth redirect page (static HTML)",
    ("GET", "/redoc"): "FastAPI default ReDoc page (static HTML)",
}
GATEWAY: dict[tuple[str, str], str] = {
    ("POST", "/api/v1/telemetry/traccar"): "Traccar forwarder; authenticated by gateway key hash, not a user token",
}


@dataclass(frozen=True)
class RouteSpec:
    method: str
    path: str
    kind: Kind
    codes: frozenset[str]  # permission codes; for requires_any any one of them suffices
    any_of: bool = False
    query: frozenset[str] = frozenset()  # query parameter names (incl. those of sub-dependencies, e.g. paging)

    @property
    def label(self) -> str:
        return f"{self.method} {self.path}"


def _calls(dep: Dependant) -> Iterator[Callable[..., Any]]:
    for d in dep.dependencies:
        if d.call is not None:
            yield d.call
        yield from _calls(d)


def _query(dep: Dependant) -> Iterator[str]:
    for p in dep.query_params:
        yield p.alias
    for d in dep.dependencies:
        yield from _query(d)


def _classify(method: str, path: str, dep: Dependant | None) -> RouteSpec:
    spec = _classify_auth(method, path, dep)
    if dep is None:
        return spec
    return RouteSpec(spec.method, spec.path, spec.kind, spec.codes, spec.any_of, frozenset(_query(dep)))


def _classify_auth(method: str, path: str, dep: Dependant | None) -> RouteSpec:
    calls = list(_calls(dep)) if dep is not None else []
    guards = [c for c in calls if getattr(c, "__name__", "").startswith(("requires_", "requires_any_"))]
    if guards:
        assert len(guards) == 1, f"{method} {path}: more than one permission guard"
        nl = inspect.getclosurevars(guards[0]).nonlocals
        scope: PermissionScope = nl["scope"]
        codes = frozenset(nl["codes"]) if "codes" in nl else frozenset({nl["code"]})
        kind = Kind.TENANT if scope is PermissionScope.TENANT else Kind.PLATFORM
        return RouteSpec(method, path, kind, codes, any_of="codes" in nl)
    if (method, path) in PUBLIC:
        return RouteSpec(method, path, Kind.PUBLIC, frozenset())
    if (method, path) in GATEWAY:
        return RouteSpec(method, path, Kind.GATEWAY, frozenset())
    if any(getattr(c, "__name__", "") == "get_claims" for c in calls):
        return RouteSpec(method, path, Kind.SELF, frozenset())
    raise AssertionError(f"UNCLASSIFIED route {method} {path}: no auth dependency and not allow-listed")


def inventory(app: FastAPI) -> list[RouteSpec]:
    out: list[RouteSpec] = []
    for rc in iter_route_contexts(app.routes):
        orig = rc.original_route
        path = rc.path
        assert path is not None
        if isinstance(orig, APIWebSocketRoute):
            out.append(RouteSpec("WS", path, Kind.WEBSOCKET, frozenset()))
            continue
        dep = getattr(rc, "dependant", None) if isinstance(orig, APIRoute) else None
        for method in sorted((rc.methods or set()) - {"HEAD"}):
            out.append(_classify(method, path, dep))
    return out


PARAM = re.compile(r"\{([^}:]+)(?::[^}]+)?\}")


def concrete(path: str, values: dict[str, str] | None = None) -> str:
    """Fill path parameters: known values by name, else a random UUID (auth must fail before lookup)."""
    vals = values or {}
    return PARAM.sub(lambda m: vals.get(m.group(1), str(uuid.uuid4())), path)


def params(path: str) -> list[str]:
    return PARAM.findall(path)
