"""FastAPI dependencies enforcing authentication, tenant boundary, entitlement and permissions.

Order: verify Keycloak token -> parse group grants -> resolve scope (platform vs X-Tenant-ID) -> check
tenant access state -> resolve permissions from the Keycloak-synced mirror -> bind DB RLS scope.
"""

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.orm import Session

from asseta.core.db import DbScope, apply_scope, get_session
from asseta.core.errors import NotAuthenticated, PermissionDenied
from asseta.modules.identity.catalog import CATALOG, PermissionScope
from asseta.modules.identity.principal import RequestContext, TokenClaims
from asseta.modules.identity.repository import IdentityRepository
from asseta.modules.identity.tokens import TokenVerifier, parse_group_grants
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


def requires(code: str, scope: PermissionScope, description: str) -> Callable[..., RequestContext]:
    """Declare a route permission (registered in the catalog at import time) and enforce it."""
    CATALOG.register(code, scope, description)

    def dependency(
        request: Request,
        claims: Annotated[TokenClaims, Depends(get_claims)],
        session: Annotated[Session, Depends(get_session)],
        x_tenant_id: Annotated[str | None, Header()] = None,
    ) -> RequestContext:
        repo = IdentityRepository(session)
        user = repo.upsert_user_from_claims(claims)
        if not user.is_active:
            raise PermissionDenied("User is deactivated", code="USER_INACTIVE")
        grants = parse_group_grants(claims.groups)
        if scope is PermissionScope.PLATFORM:
            group_paths = frozenset(g for g in claims.groups if g.startswith("/platform/"))
            permissions = repo.permissions_for_groups(group_paths)
            ctx = RequestContext(user.id, claims.subject, DbScope.PLATFORM, None, grants.platform_roles, permissions)
        else:
            tenant_id = _resolve_tenant_header(x_tenant_id)
            roles = grants.tenant_roles.get(tenant_id)
            if not roles:
                raise PermissionDenied("No membership in requested tenant", code="TENANT_ACCESS_DENIED")
            access = repo.tenant_access_state(tenant_id)
            if access is None or access is TenantAccessState.BLOCKED:
                raise PermissionDenied("Tenant access is blocked", code="TENANT_ACCESS_BLOCKED")
            read_only = access is TenantAccessState.READ_ONLY
            if read_only and request.method not in READ_METHODS:
                raise PermissionDenied("Subscription allows read-only access", code="SUBSCRIPTION_READ_ONLY")
            group_paths = frozenset(g for g in claims.groups if g.startswith(f"/tenants/{tenant_id}/"))
            permissions = repo.permissions_for_groups(group_paths)
            ctx = RequestContext(user.id, claims.subject, DbScope.TENANT, tenant_id, roles, permissions, read_only)
        if code not in ctx.permissions:
            raise PermissionDenied(f"Missing permission {code}")
        apply_scope(session, ctx.scope, ctx.tenant_id, ctx.user_id)
        return ctx

    dependency.__name__ = f"requires_{code.replace('.', '_')}"
    return dependency
