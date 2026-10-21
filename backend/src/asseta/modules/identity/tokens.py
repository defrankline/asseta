"""OIDC access-token verification against the Keycloak realm JWKS, plus group-claim parsing."""

import uuid
from typing import Any, Protocol

import jwt

from asseta.core.errors import NotAuthenticated
from asseta.modules.identity.catalog import PLATFORM_GROUP_ROOT, TENANT_GROUP_ROOT
from asseta.modules.identity.principal import GroupGrants, TokenClaims

ALLOWED_ALGORITHMS = ["RS256", "ES256", "PS256"]


class TokenVerifier(Protocol):
    def verify(self, token: str) -> TokenClaims: ...


class SigningKeyProvider(Protocol):
    def key_for(self, token: str) -> Any: ...


class JwksSigningKeyProvider:
    """Fetches and caches realm signing keys (rotations handled by kid lookup)."""

    def __init__(self, jwks_url: str, cache_seconds: int, timeout_seconds: float):
        self._client = jwt.PyJWKClient(jwks_url, cache_keys=True, lifespan=cache_seconds, timeout=timeout_seconds)

    def key_for(self, token: str) -> Any:
        try:
            return self._client.get_signing_key_from_jwt(token).key
        except jwt.PyJWKClientError as exc:
            raise NotAuthenticated("Unable to resolve token signing key") from exc


class OidcTokenVerifier:
    def __init__(self, keys: SigningKeyProvider, issuer: str, audience: str):
        self._keys = keys
        self._issuer = issuer
        self._audience = audience

    def verify(self, token: str) -> TokenClaims:
        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                self._keys.key_for(token),
                algorithms=ALLOWED_ALGORITHMS,
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "iat", "iss", "sub", "aud"]},
                leeway=30,
            )
        except jwt.PyJWTError as exc:
            raise NotAuthenticated("Invalid or expired access token") from exc
        groups = claims.get("groups", [])
        if not isinstance(groups, list):
            raise NotAuthenticated("Malformed groups claim")
        return TokenClaims(
            subject=str(claims["sub"]),
            email=str(claims.get("email", "")),
            display_name=str(claims.get("name") or claims.get("preferred_username") or claims["sub"]),
            groups=frozenset(str(g) for g in groups),
            session_id=str(claims["sid"]) if claims.get("sid") else None,
        )


def parse_group_grants(groups: frozenset[str]) -> GroupGrants:
    """`/platform/<role>` and `/tenants/<tenant_uuid>/<role>`; anything else is ignored (deny by default)."""
    platform: set[str] = set()
    tenants: dict[uuid.UUID, set[str]] = {}
    for path in groups:
        parts = [p for p in path.split("/") if p]
        if len(parts) == 2 and parts[0] == PLATFORM_GROUP_ROOT:
            platform.add(parts[1])
        elif len(parts) == 3 and parts[0] == TENANT_GROUP_ROOT:
            try:
                tenant_id = uuid.UUID(parts[1])
            except ValueError:
                continue
            tenants.setdefault(tenant_id, set()).add(parts[2])
    return GroupGrants(platform_roles=frozenset(platform), tenant_roles={t: frozenset(r) for t, r in tenants.items()})


def platform_group_path(role_key: str) -> str:
    return f"/{PLATFORM_GROUP_ROOT}/{role_key}"


def tenant_group_path(tenant_id: uuid.UUID, role_key: str) -> str:
    return f"/{TENANT_GROUP_ROOT}/{tenant_id}/{role_key}"
