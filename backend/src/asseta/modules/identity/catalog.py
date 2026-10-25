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
class MenuGroupDef:
    """A side-navigation section ("parent") of one console; menus are its children."""

    key: str
    scope: PermissionScope
    label: str
    order: int
    # A tenant capability (`asseta.modules.policy.capabilities.CAPABILITIES`): when the tenant's effective policy
    # switches it off, the whole group (every child menu) is left out of that tenant's navigation.
    capability: str | None = None


@dataclass(frozen=True)
class MenuDef:
    key: str
    scope: PermissionScope
    label: str
    path: str
    order: int
    required_permission: str
    group: str  # MenuGroupDef.key of the same scope (validated by `PermissionCatalog.register_menu`)
    capability: str | None = None  # as MenuGroupDef.capability, for a single menu outside a gated group


class PermissionCatalog:
    def __init__(self) -> None:
        self._permissions: dict[str, PermissionDef] = {}
        self._menus: dict[str, MenuDef] = {}
        self._groups: dict[str, MenuGroupDef] = {}

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

    def register_group(self, group: MenuGroupDef) -> None:
        if not group.key.startswith(f"{group.scope.value.lower()}."):
            raise ValueError(f"menu group {group.key} must start with {group.scope.value.lower()}.")
        self._groups[group.key] = group

    def register_menu(self, menu: MenuDef) -> None:
        """Every menu belongs to a registered group of its own scope: an ungrouped menu fails at import time."""
        if menu.required_permission not in self._permissions:
            raise ValueError(f"menu {menu.key} references unknown permission {menu.required_permission}")
        group = self._groups.get(menu.group)
        if group is None or group.scope is not menu.scope:
            raise ValueError(f"menu {menu.key} needs a registered {menu.scope.value} menu group (got {menu.group!r})")
        self._menus[menu.key] = menu

    def permissions(self) -> list[PermissionDef]:
        return sorted(self._permissions.values(), key=lambda p: p.code)

    def menus(self) -> list[MenuDef]:
        return sorted(self._menus.values(), key=lambda m: (m.scope, m.order))

    def menu_groups(self) -> list[MenuGroupDef]:
        return sorted(self._groups.values(), key=lambda g: (g.scope, g.order))

    def menu_group(self, key: str) -> MenuGroupDef | None:
        return self._groups.get(key)

    def menu(self, key: str) -> MenuDef | None:
        return self._menus.get(key)

    def menu_capabilities(self, key: str) -> frozenset[str]:
        """Capabilities a menu needs: its own and its group's (empty for ungated menus or unknown keys)."""
        menu = self._menus.get(key)
        if menu is None:
            return frozenset()
        group = self._groups.get(menu.group)
        return frozenset(c for c in (menu.capability, group.capability if group else None) if c)

    def capabilities(self) -> frozenset[str]:
        return frozenset(
            c
            for c in [*(m.capability for m in self._menus.values()), *(g.capability for g in self._groups.values())]
            if c
        )


CATALOG = PermissionCatalog()

# Side-navigation sections in daily-workflow order: each console opens on its Overview (the landing page).
for _group in (
    MenuGroupDef("tenant.overview", PermissionScope.TENANT, "Overview", 10),
    # Supervisor field work from a browser (the same R1 capture flows as the field apps); right after Overview.
    MenuGroupDef("tenant.field", PermissionScope.TENANT, "Field work", 15),
    MenuGroupDef("tenant.operations", PermissionScope.TENANT, "Operations", 20),
    MenuGroupDef("tenant.fleet", PermissionScope.TENANT, "Fleet", 30),
    # Prepaid customer hours (accountability design A): purchases, balances, approvals and reason lists.
    MenuGroupDef("tenant.hours", PermissionScope.TENANT, "Customer hours", 35, capability="CUSTOMER_HOURS"),
    # Engine-hour accountability (design B): reconciliation, explanations, baselines, corrections, reason lists.
    MenuGroupDef("tenant.engine_hours", PermissionScope.TENANT, "Engine hours", 37),
    MenuGroupDef("tenant.finance", PermissionScope.TENANT, "Finance", 40),
    MenuGroupDef("tenant.risk", PermissionScope.TENANT, "Risk & review", 50),
    MenuGroupDef("tenant.admin", PermissionScope.TENANT, "Administration", 90),
    MenuGroupDef("platform.overview", PermissionScope.PLATFORM, "Overview", 10),
    MenuGroupDef("platform.tenants", PermissionScope.PLATFORM, "Tenants", 20),
    MenuGroupDef("platform.billing", PermissionScope.PLATFORM, "Billing", 30),
    MenuGroupDef("platform.intelligence", PermissionScope.PLATFORM, "Intelligence", 40),
    MenuGroupDef("platform.admin", PermissionScope.PLATFORM, "Administration", 90),
):
    CATALOG.register_group(_group)

KEYCLOAK_PERMISSION_ROLE_PREFIX = "perm:"
PLATFORM_GROUP_ROOT = "platform"
TENANT_GROUP_ROOT = "tenants"
