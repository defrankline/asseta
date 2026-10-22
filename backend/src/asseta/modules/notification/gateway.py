"""WebSocket gateway `/api/v1/ws` (protocol `asseta.v1`, documented in docs/api.md).

Auth uses the same Keycloak verifier as REST. The token travels in the first message (`{"type":"auth","token":...,
"tenant_id":...}`) or in `Sec-WebSocket-Protocol: asseta.v1, bearer.<token>` — never in the URL. The connection is
scoped to the user and one context (a tenant, with the same membership/mandate/access-state rules as REST, or the
platform console) and subscribes to that user's channel plus the context's "entity changed" channel (Redis pub/sub,
so any API instance can deliver). Heartbeat, idle timeout, token-expiry and periodic access re-check close the socket
with 4401 (authentication) / 4403 (access) / 4408 (idle)."""

import asyncio
import time
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

import jwt
import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool

from asseta.core.clock import system_clock
from asseta.core.db import DbScope, apply_scope, get_sessionmaker
from asseta.core.errors import AppError, NotAuthenticated, PermissionDenied
from asseta.modules.identity.dependencies import is_platform_staff, mandate_gate_on
from asseta.modules.identity.repository import IdentityRepository
from asseta.modules.identity.tokens import TokenVerifier
from asseta.modules.notification.engine import unread_count
from asseta.modules.notification.realtime import RealtimeBroker, Subscription, entity_channel, user_channel
from asseta.modules.notification.settings import get_notification_settings
from asseta.modules.tenancy.models import TenantAccessState

log = structlog.get_logger()
router = APIRouter()
SUBPROTOCOL = "asseta.v1"
BEARER = "bearer."
TENANT_PERMISSION, PLATFORM_PERMISSION = "tenant.notification.read", "platform.notification.read"


@dataclass(frozen=True)
class WsPrincipal:
    subject: str
    user_id: uuid.UUID
    tenant_id: uuid.UUID | None
    expires_at: float
    unread: int


def authorize(verifier: TokenVerifier, token: str, tenant_id: uuid.UUID | None, today: date) -> WsPrincipal:
    """Sync (DB + JWKS): run in a thread. Raises NotAuthenticated / PermissionDenied."""
    claims = verifier.verify(token)
    exp = float(jwt.decode(token, options={"verify_signature": False}).get("exp", 0))
    with get_sessionmaker()() as session, session.begin():
        repo = IdentityRepository(session)
        user = repo.upsert_user_from_claims(claims)
        if not user.is_active:
            raise PermissionDenied("User is deactivated", code="USER_INACTIVE")
        if tenant_id is None:
            if not is_platform_staff(claims):
                raise PermissionDenied("Platform context requires platform staff", code="PLATFORM_REQUIRED")
            paths = frozenset(g for g in claims.groups if g.startswith("/platform/"))
            needed, scope = PLATFORM_PERMISSION, DbScope.PLATFORM
        else:
            paths = frozenset(g for g in claims.groups if g.startswith(f"/tenants/{tenant_id}/"))
            grant = mandate_gate_on(session, claims, user.id, tenant_id, today)
            if grant is not None:
                paths &= grant.group_paths
            paths -= repo.revoked_role_paths(tenant_id, user.id)  # same rule as REST (identity.dependencies)
            if not paths:
                raise PermissionDenied("No membership in requested tenant", code="TENANT_ACCESS_DENIED")
            access = repo.tenant_access_state(tenant_id)
            if access is None or access is TenantAccessState.BLOCKED:
                raise PermissionDenied("Tenant access is blocked", code="TENANT_ACCESS_BLOCKED")
            needed, scope = TENANT_PERMISSION, DbScope.TENANT
        if needed not in repo.permissions_for_groups(paths):
            raise PermissionDenied(f"Missing permission {needed}")
        apply_scope(session, scope, tenant_id, user.id)
        return WsPrincipal(claims.subject, user.id, tenant_id, exp, unread_count(session, user.id, tenant_id))


def _uuid(raw: object) -> uuid.UUID | None:
    if raw in (None, ""):
        return None
    try:
        return uuid.UUID(str(raw))
    except ValueError as exc:
        raise PermissionDenied("Invalid tenant id", code="TENANT_REQUIRED") from exc


class Connection:
    def __init__(self, ws: WebSocket, verifier: TokenVerifier, broker: RealtimeBroker, today: date):
        self.ws, self.verifier, self.broker, self.today = ws, verifier, broker, today
        self.cfg = get_notification_settings()
        self.principal: WsPrincipal | None = None
        self.token = ""
        self.sub: Subscription | None = None
        self.last_seen = time.monotonic()
        self.reauth_warned = False

    async def send(self, kind: str, payload: dict[str, Any] | None = None) -> None:
        await self.ws.send_json({"type": kind} if payload is None else {"type": kind, "payload": payload})

    async def fail(self, exc: AppError) -> None:
        await self.send("auth_error", {"code": exc.code, "message": exc.message})
        await self.ws.close(code=4401 if isinstance(exc, NotAuthenticated) else 4403, reason=exc.code)

    async def bind(self, token: str, tenant_id: uuid.UUID | None) -> None:
        principal = await run_in_threadpool(authorize, self.verifier, token, tenant_id, self.today)
        if self.principal is not None and principal.subject != self.principal.subject:
            raise NotAuthenticated("Token belongs to another user", code="SUBJECT_CHANGED")
        if self.sub is not None and (self.principal is None or self.principal.tenant_id != tenant_id):
            await self.sub.close()
            self.sub = None
        if self.sub is None:
            self.sub = await self.broker.subscribe(
                [user_channel(principal.user_id, tenant_id), entity_channel(tenant_id)]
            )
        self.principal, self.token, self.reauth_warned = principal, token, False
        await self.send(
            "auth_ok",
            {
                "user_id": str(principal.user_id),
                "tenant_id": str(tenant_id) if tenant_id else None,
                "scope": {"kind": "tenant", "tenantId": str(tenant_id)} if tenant_id else {"kind": "platform"},
                "expires_at": int(principal.expires_at),
                "unread_count": principal.unread,
                "heartbeat_seconds": self.cfg.ws_heartbeat_seconds,
            },
        )

    async def reader(self) -> None:
        while True:
            msg = await self.ws.receive_json()
            self.last_seen = time.monotonic()
            kind = msg.get("type") if isinstance(msg, dict) else None
            if kind == "ping":
                await self.send("pong")
            elif kind == "auth":  # token refresh on the open socket (same user, same context unless given)
                assert self.principal is not None
                tenant = _uuid(msg["tenant_id"]) if "tenant_id" in msg else self.principal.tenant_id
                await self.bind(str(msg.get("token") or ""), tenant)
            elif kind == "subscribe":  # switch context: re-authorized against the new tenant/platform
                scope = msg.get("scope") or {}
                tenant = _uuid(scope.get("tenantId")) if scope.get("kind") == "tenant" else None
                await self.bind(self.token, tenant)

    async def pump(self) -> None:
        next_ping = time.monotonic() + self.cfg.ws_heartbeat_seconds
        next_check = time.monotonic() + self.cfg.ws_access_recheck_seconds
        while True:
            assert self.sub is not None and self.principal is not None
            message = await self.sub.get(timeout=1.0)
            if message is not None:
                await self.ws.send_json(message)
            now = time.monotonic()
            if now - self.last_seen > self.cfg.ws_idle_timeout_seconds:
                await self.ws.close(code=4408, reason="IDLE_TIMEOUT")
                return
            left = self.principal.expires_at - time.time()
            if left <= 0:
                raise NotAuthenticated("Access token expired", code="TOKEN_EXPIRED")
            if left < 60 and not self.reauth_warned:
                self.reauth_warned = True
                await self.send("reauth_required", {"expires_at": int(self.principal.expires_at)})
            if now >= next_ping:
                next_ping = now + self.cfg.ws_heartbeat_seconds
                await self.send("ping")
            if now >= next_check:  # mandate ended, membership revoked, tenant blocked...
                next_check = now + self.cfg.ws_access_recheck_seconds
                await run_in_threadpool(authorize, self.verifier, self.token, self.principal.tenant_id, self.today)


async def _first_auth(conn: Connection, offered_token: str | None) -> tuple[str, uuid.UUID | None]:
    msg = await asyncio.wait_for(conn.ws.receive_json(), conn.cfg.ws_auth_timeout_seconds)
    if not isinstance(msg, dict) or msg.get("type") not in ("auth", "subscribe"):
        raise NotAuthenticated("First message must be auth", code="AUTH_REQUIRED")
    scope = msg.get("scope") or {}
    raw_tenant = msg.get("tenant_id") or (scope.get("tenantId") if scope.get("kind") == "tenant" else None)
    token = str(msg.get("token") or offered_token or "")
    if not token:
        raise NotAuthenticated("Bearer token required", code="AUTH_REQUIRED")
    return token, _uuid(raw_tenant)


@router.websocket("/api/v1/ws")
async def gateway(ws: WebSocket) -> None:
    offered = [p.strip() for p in ws.headers.get("sec-websocket-protocol", "").split(",") if p.strip()]
    token = next((p[len(BEARER) :] for p in offered if p.startswith(BEARER)), None)
    await ws.accept(subprotocol=SUBPROTOCOL if SUBPROTOCOL in offered else None)
    clock = getattr(ws.app.state, "clock", system_clock)
    conn = Connection(ws, ws.app.state.token_verifier, ws.app.state.realtime, clock().date())
    tasks: list[asyncio.Task[None]] = []
    try:
        first_token, tenant = await _first_auth(conn, token)
        await conn.bind(first_token, tenant)
        tasks = [asyncio.create_task(conn.reader()), asyncio.create_task(conn.pump())]
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in done:
            t.result()  # surface the reason the connection ended
    except AppError as exc:
        await _safe(conn.fail(exc))
    except (WebSocketDisconnect, TimeoutError, KeyError, ValueError, RuntimeError):
        await _safe(ws.close(code=4401, reason="AUTH_TIMEOUT") if conn.principal is None else asyncio.sleep(0))
    finally:
        for t in tasks:
            t.cancel()
        if conn.sub is not None:
            await conn.sub.close()


async def _safe(awaitable: Any) -> None:
    try:
        await awaitable
    except Exception:  # socket already gone
        log.debug("ws_close_ignored")
