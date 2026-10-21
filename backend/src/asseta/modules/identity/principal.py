"""Authenticated principal and resolved request context."""

import uuid
from dataclasses import dataclass, field

from asseta.core.audit import AuditActor
from asseta.core.db import DbScope


@dataclass(frozen=True)
class TokenClaims:
    subject: str
    email: str
    display_name: str
    groups: frozenset[str]
    session_id: str | None


@dataclass(frozen=True)
class GroupGrants:
    """Role groups parsed from the verified token `groups` claim."""

    platform_roles: frozenset[str] = frozenset()
    tenant_roles: dict[uuid.UUID, frozenset[str]] = field(default_factory=dict)


@dataclass(frozen=True)
class RequestContext:
    user_id: uuid.UUID
    subject: str
    scope: DbScope
    tenant_id: uuid.UUID | None
    roles: frozenset[str]
    permissions: frozenset[str]
    read_only: bool = False

    def audit_actor(self, source: str = "api") -> AuditActor:
        return AuditActor(user_id=self.user_id, roles=sorted(self.roles), source=source)
