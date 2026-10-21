"""Identity-provider admin port. Keycloak implementation lives in keycloak_admin.py."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RoleGroup:
    group_id: str
    path: str
    name: str
    permission_codes: frozenset[str]


@dataclass(frozen=True)
class CreatedUser:
    subject: str
    temporary_password: str


class IdentityProviderAdmin(Protocol):
    def ensure_permission_roles(self, codes: list[str], descriptions: dict[str, str]) -> None: ...

    def ensure_group(self, path: str) -> str: ...

    def set_group_permissions(self, group_id: str, codes: set[str]) -> None: ...

    def list_role_groups(self) -> list[RoleGroup]: ...

    def create_user(self, email: str, first_name: str, last_name: str) -> CreatedUser: ...

    def add_user_to_group(self, subject: str, group_id: str) -> None: ...
