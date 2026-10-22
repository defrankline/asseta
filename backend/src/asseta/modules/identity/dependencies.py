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

from asseta.core.clock import get_today
from asseta.core.db import DbScope, apply_scope, get_session
from asseta.core.errors import NotAuthenticated, PermissionDenied
from asseta.modules.identity.catalog import CATALOG, PermissionScope
from asseta.modules.identity.principal import RequestContext, TokenClaims
from asseta.modules.identity.repository import IdentityRepository
from asseta.modules.identity.tokens import TokenVerifier, parse_group_grants
from asseta.modules.managed_service.gate import MandateGrant, active_grant, has_assignment_history
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
            group_paths = frozenset(g for g in claims.groups if g.startswith(f"/tenants/{tenant_id}/"))
            mandate = mandate_gate(session, request, claims, user.id, tenant_id)
            if mandate is not None:
                group_paths &= mandate.group_paths  # Keycloak membership AND an in-force assignment
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
            ctx = RequestContext(
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
        if code not in ctx.permissions:
            raise PermissionDenied(f"Missing permission {code}")
        apply_scope(session, ctx.scope, ctx.tenant_id, ctx.user_id)
        session.info["mandate_id"] = ctx.mandate_id  # stamped on every audit event of this request
        return ctx

    dependency.__name__ = f"requires_{code.replace('.', '_')}"
    return dependency
