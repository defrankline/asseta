"""FastAPI dependencies enforcing authentication, tenant boundary, entitlement and permissions.

Order: verify Keycloak token -> parse group grants -> resolve scope (platform vs X-Tenant-ID) -> mandate gate for
platform staff -> check tenant access state -> resolve permissions from the Keycloak-synced mirror -> bind DB RLS
scope.
"""

import uuid
from collections.abc import Callable
from datetime import date
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from asseta.core.clock import get_now, get_today
from asseta.core.db import DbScope, apply_scope, get_session
from asseta.core.errors import NotAuthenticated, PermissionDenied
from asseta.modules.accountability.security_events import permission_refused
from asseta.modules.identity.catalog import CATALOG, PermissionScope
from asseta.modules.identity.principal import RequestContext, TokenClaims
from asseta.modules.identity.repository import IdentityRepository
from asseta.modules.identity.tokens import TokenVerifier, parse_group_grants
from asseta.modules.managed_service.gate import MandateGrant, active_grant, has_assignment_history
from asseta.modules.policy.capabilities import require_capability
from asseta.modules.tenancy.models import TenantAccessState

READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def get_token_verifier(request: Request) -> TokenVerifier:
    verifier: TokenVerifier = request.app.state.token_verifier
    return verifier


def get_claims(
    verifier: Annotated[TokenVerifier, Depends(get_token_verifier)],
    authorization: Annotated[str | None, Header()] = None,
) -> TokenClaims:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise NotAuthenticated("Bearer token required")
    return verifier.verify(authorization[7:].strip())


def _resolve_tenant_header(raw: str | None) -> uuid.UUID:
    if not raw:
        raise PermissionDenied("X-Tenant-ID header required for tenant-scoped operations", code="TENANT_REQUIRED")
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise PermissionDenied("Invalid X-Tenant-ID", code="TENANT_REQUIRED") from exc


def is_platform_staff(claims: TokenClaims) -> bool:
    return any(g.startswith("/platform/") for g in claims.groups)


def mandate_gate(
    session: Session, request: Request, claims: TokenClaims, user_id: uuid.UUID, tenant_id: uuid.UUID
) -> MandateGrant | None:
    return mandate_gate_on(session, claims, user_id, tenant_id, get_today(request))


def mandate_gate_on(
    session: Session, claims: TokenClaims, user_id: uuid.UUID, tenant_id: uuid.UUID, today: date
) -> MandateGrant | None:
    """None for an ordinary tenant member. For platform staff (or anyone who ever held a mandate assignment here)
    the in-force mandate grant, else refuse: Keycloak groups alone never carry platform staff into a tenant."""
    apply_scope(session, DbScope.TENANT, tenant_id, user_id)  # mandate rows are readable in the client's scope
    if not is_platform_staff(claims) and not has_assignment_history(session, tenant_id, user_id):
        return None
    grant = active_grant(session, tenant_id, user_id, today)
    if grant is None:
        if has_assignment_history(session, tenant_id, user_id):
            raise PermissionDenied("The managed-service mandate for this tenant is not in force", code="MANDATE_ENDED")
        raise PermissionDenied("Platform staff need a managed-service mandate", code="MANDATE_REQUIRED")
    return grant


def _context(
    request: Request,
    claims: TokenClaims,
    session: Session,
    x_tenant_id: str | None,
    scope: PermissionScope,
    quarantine_when_read_only: bool,
) -> RequestContext:
    repo = IdentityRepository(session)
    user = repo.upsert_user_from_claims(claims)
    if not user.is_active:
        raise PermissionDenied("User is deactivated", code="USER_INACTIVE")
    grants = parse_group_grants(claims.groups)
    if scope is PermissionScope.PLATFORM:
        group_paths = frozenset(g for g in claims.groups if g.startswith("/platform/"))
        permissions = repo.permissions_for_groups(group_paths)
        return RequestContext(user.id, claims.subject, DbScope.PLATFORM, None, grants.platform_roles, permissions)
    tenant_id = _resolve_tenant_header(x_tenant_id)
    group_paths = frozenset(g for g in claims.groups if g.startswith(f"/tenants/{tenant_id}/"))
    mandate = mandate_gate(session, request, claims, user.id, tenant_id)
    if mandate is not None:
        group_paths &= mandate.group_paths  # Keycloak membership AND an in-force assignment
    group_paths -= repo.revoked_role_paths(tenant_id, user.id)  # revoked in Asseta: stale token claims don't count
    roles = frozenset(p.rsplit("/", 1)[-1] for p in group_paths)
    if not roles:
        raise PermissionDenied("No membership in requested tenant", code="TENANT_ACCESS_DENIED")
    access = repo.tenant_access_state(tenant_id)
    if access is None or access is TenantAccessState.BLOCKED:
        raise PermissionDenied("Tenant access is blocked", code="TENANT_ACCESS_BLOCKED")
    read_only = access is TenantAccessState.READ_ONLY
    if read_only and request.method not in READ_METHODS and not quarantine_when_read_only:
        raise PermissionDenied("Subscription allows read-only access", code="SUBSCRIPTION_READ_ONLY")
    permissions = repo.permissions_for_groups(group_paths)
    return RequestContext(
        user.id,
        claims.subject,
        DbScope.TENANT,
        tenant_id,
        roles,
        permissions,
        read_only,
        mandate.mandate_id if mandate else None,
        mandate.reference if mandate else None,
    )


def _refused(request: Request, ctx: RequestContext, permission: str) -> None:
    """A signed-in tenant member asked for something their roles do not grant: kept as a security event."""
    permission_refused(
        ctx.tenant_id,
        ctx.user_id,
        permission,
        request.method,
        request.url.path,
        occurred_at=get_now(request),
        actor_subject=ctx.subject,
    )


def _bind(session: Session, ctx: RequestContext) -> RequestContext:
    apply_scope(session, ctx.scope, ctx.tenant_id, ctx.user_id)
    session.info["mandate_id"] = ctx.mandate_id  # stamped on every audit event of this request
    return ctx


def requires(
    code: str, scope: PermissionScope, description: str, quarantine_when_read_only: bool = False
) -> Callable[..., RequestContext]:
    """Declare a route permission (registered in the catalog at import time) and enforce it.

    `quarantine_when_read_only` lets a write route (offline sync push) run for READ_ONLY tenants so the handler can
    *quarantine* writes instead of losing them; `RequestContext.read_only` tells it to do so.
    """
    CATALOG.register(code, scope, description)

    def dependency(
        request: Request,
        claims: Annotated[TokenClaims, Depends(get_claims)],
        session: Annotated[Session, Depends(get_session)],
        x_tenant_id: Annotated[str | None, Header()] = None,
    ) -> RequestContext:
        ctx = _context(request, claims, session, x_tenant_id, scope, quarantine_when_read_only)
        if code not in ctx.permissions:
            _refused(request, ctx, code)
            raise PermissionDenied(f"Missing permission {code}")
        return _bind(session, ctx)

    dependency.__name__ = f"requires_{code.replace('.', '_')}"
    return dependency


def requires_any(codes: tuple[str, ...], scope: PermissionScope) -> Callable[..., RequestContext]:
    """Enforce that the caller holds at least one of `codes` (each already declared with `requires`). For views
    assembled from sections that are each gated by their own permission (overview, report menus)."""
    if not codes:
        raise ValueError("requires_any needs at least one permission")

    def dependency(
        request: Request,
        claims: Annotated[TokenClaims, Depends(get_claims)],
        session: Annotated[Session, Depends(get_session)],
        x_tenant_id: Annotated[str | None, Header()] = None,
    ) -> RequestContext:
        unknown = [c for c in codes if c not in {p.code for p in CATALOG.permissions()}]
        if unknown:
            raise ValueError(f"requires_any: undeclared permissions {unknown}")
        ctx = _context(request, claims, session, x_tenant_id, scope, False)
        if not any(c in ctx.permissions for c in codes):
            _refused(request, ctx, " | ".join(codes))
            raise PermissionDenied(f"Missing any of permissions {', '.join(codes)}")
        return _bind(session, ctx)

    dependency.__name__ = "requires_any_" + "_".join(c.replace(".", "_") for c in codes)
    return dependency


def gated(permission: Callable[..., RequestContext], capability: str) -> Callable[..., RequestContext]:
    """A permission dependency that also needs a tenant capability (`asseta.modules.policy.capabilities`) to be on.
    Authentication and the permission are checked first; a switched-off capability is then refused with its
    REFUSALS code (422)."""

    def dependency(
        request: Request,
        ctx: Annotated[RequestContext, Depends(permission)],
        session: Annotated[Session, Depends(get_session)],
    ) -> RequestContext:
        if ctx.tenant_id is not None:
            require_capability(session, ctx.tenant_id, capability, get_now(request))
        return ctx

    dependency.__name__ = f"capability_gate_{capability.lower()}"  # not a permission guard (route inventory)
    return dependency
