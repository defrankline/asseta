"""In-memory IdentityProviderAdmin test double that mirrors Keycloak group/role semantics (path-addressed
groups, client permission roles mapped to groups, users in groups). Used only in tests; the real adapter is
exercised against a live Keycloak in tests/integration."""

import secrets
import uuid

from asseta.modules.identity.idp import CreatedUser, RoleGroup


class InMemoryIdp:
    def __init__(self) -> None:
        self.permission_roles: set[str] = set()
        self.groups: dict[str, str] = {}  # path -> id
        self.group_perms: dict[str, set[str]] = {}  # id -> codes
        self.users: dict[str, str] = {}  # subject -> email
        self.memberships: dict[str, set[str]] = {}  # subject -> group paths

    def ensure_permission_roles(self, codes: list[str], descriptions: dict[str, str]) -> None:
        self.permission_roles |= set(codes)

    def ensure_group(self, path: str) -> str:
        return self.groups.setdefault(path, str(uuid.uuid4()))

    def set_group_permissions(self, group_id: str, codes: set[str]) -> None:
        unknown = codes - self.permission_roles
        assert not unknown, f"unknown permission roles {unknown}"
        self.group_perms[group_id] = set(codes)

    def list_role_groups(self) -> list[RoleGroup]:
        result = []
        for path, gid in self.groups.items():
            depth = len([p for p in path.split("/") if p])
            if (path.startswith("/platform/") and depth == 2) or (path.startswith("/tenants/") and depth == 3):
                result.append(
                    RoleGroup(gid, path, path.rsplit("/", 1)[-1], frozenset(self.group_perms.get(gid, set())))
                )
        return result

    def create_user(self, email: str, first_name: str, last_name: str) -> CreatedUser:
        subject = str(uuid.uuid4())
        self.users[subject] = email
        return CreatedUser(subject, secrets.token_urlsafe(12))

    def add_user_to_group(self, subject: str, group_id: str) -> None:
        path = next(p for p, g in self.groups.items() if g == group_id)
        self.memberships.setdefault(subject, set()).add(path)

    def subject_for(self, email: str) -> str:
        return next(s for s, e in self.users.items() if e == email)
