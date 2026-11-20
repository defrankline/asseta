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
class GroupMember:
    subject: str
    email: str
    display_name: str


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

    def remove_user_from_group(self, subject: str, group_id: str) -> None: ...

    def list_group_members(self, group_id: str) -> list[GroupMember]: ...

    def find_user_by_email(self, email: str) -> str | None: ...

    # --- a company's own people (Users & roles) --------------------------------------------------------------------
    def update_user_name(self, subject: str, first_name: str, last_name: str) -> None: ...

    def reset_password(self, subject: str) -> str:
        """Sets a new one-time password (to be changed at the next sign-in) and returns it."""
        ...

    def logout_user(self, subject: str) -> None:
        """Ends all the user's sessions, including the apps' offline sessions."""
        ...

    def enable_user(self, subject: str) -> None: ...

    # --- account and company deletion (idempotent: a user or group already gone is not an error) ----------------
    def user_group_paths(self, subject: str) -> list[str]: ...

    def disable_user(self, subject: str) -> None: ...

    def delete_user(self, subject: str) -> None: ...

    def delete_group(self, path: str) -> None: ...
