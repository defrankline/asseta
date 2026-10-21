"""Central permission & menu catalog. Routes declare permissions via `requires(...)`; the catalog is the
single source pushed to Keycloak (client roles `perm:<code>`) and mirrored to the DB at startup."""

from dataclasses import dataclass
from enum import StrEnum


class PermissionScope(StrEnum):
    PLATFORM = "PLATFORM"
    TENANT = "TENANT"


@dataclass(frozen=True)
class PermissionDef:
    code: str
    scope: PermissionScope
    description: str


@dataclass(frozen=True)
class MenuDef:
    key: str
    scope: PermissionScope
    label: str
    path: str
    order: int
    required_permission: str


class PermissionCatalog:
    def __init__(self) -> None:
        self._permissions: dict[str, PermissionDef] = {}
        self._menus: dict[str, MenuDef] = {}

    def register(self, code: str, scope: PermissionScope, description: str) -> PermissionDef:
        expected_prefix = "platform." if scope is PermissionScope.PLATFORM else "tenant."
        if not code.startswith(expected_prefix):
            raise ValueError(f"permission {code} must start with {expected_prefix}")
        existing = self._permissions.get(code)
        if existing and existing.scope is not scope:
            raise ValueError(f"permission {code} registered with conflicting scope")
        definition = existing or PermissionDef(code, scope, description)
        self._permissions[code] = definition
        return definition

    def register_menu(self, menu: MenuDef) -> None:
        if menu.required_permission not in self._permissions:
            raise ValueError(f"menu {menu.key} references unknown permission {menu.required_permission}")
        self._menus[menu.key] = menu

    def permissions(self) -> list[PermissionDef]:
        return sorted(self._permissions.values(), key=lambda p: p.code)

    def menus(self) -> list[MenuDef]:
        return sorted(self._menus.values(), key=lambda m: (m.scope, m.order))


CATALOG = PermissionCatalog()

KEYCLOAK_PERMISSION_ROLE_PREFIX = "perm:"
PLATFORM_GROUP_ROOT = "platform"
TENANT_GROUP_ROOT = "tenants"
