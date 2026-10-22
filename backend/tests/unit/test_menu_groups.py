"""Side navigation is grouped (parent -> children): every menu has a group, groups list only when visible."""

import pytest

import asseta.main  # noqa: F401  (registers every module's permissions and menus)
from asseta.modules.identity.catalog import CATALOG, MenuDef, MenuGroupDef, PermissionCatalog, PermissionScope
from asseta.modules.identity.models import Menu
from asseta.modules.identity.service import menus_for


def _rows() -> list[Menu]:
    return [
        Menu(
            key=m.key,
            scope=m.scope.value,
            label=m.label,
            path=m.path,
            sort_order=m.order,
            required_permission=m.required_permission,
            group_key=m.group,
        )
        for m in CATALOG.menus()
    ]


def test_every_registered_menu_has_a_group_of_its_own_scope() -> None:
    menus = CATALOG.menus()
    assert menus
    for m in menus:
        group = CATALOG.menu_group(m.group)
        assert group is not None and group.scope is m.scope, m.key
    used = {m.group for m in menus}
    assert {g.key for g in CATALOG.menu_groups()} == used  # no group is defined without a menu


def test_groups_follow_the_daily_workflow_and_start_on_the_landing_page() -> None:
    def labels(scope: PermissionScope) -> list[str]:
        return [g.label for g in CATALOG.menu_groups() if g.scope is scope]

    assert labels(PermissionScope.TENANT) == [
        "Overview",
        "Operations",
        "Fleet",
        "Finance",
        "Risk & review",
        "Administration",
    ]
    assert labels(PermissionScope.PLATFORM) == ["Overview", "Tenants", "Billing", "Intelligence", "Administration"]
    everything = frozenset(p.code for p in CATALOG.permissions())
    tenant_menus, _ = menus_for(_rows(), "TENANT", everything)
    platform_menus, _ = menus_for(_rows(), "PLATFORM", everything)
    assert (tenant_menus[0].group, tenant_menus[0].path) == ("tenant.overview", "/tenant/fleet")
    assert (platform_menus[0].group, platform_menus[0].path) == ("platform.overview", "/platform")


def test_finance_only_role_sees_only_finance_and_its_administration_items() -> None:
    perms = frozenset(
        {
            "tenant.finance.read",
            "tenant.finance.report",
            "tenant.expense.read",
            "tenant.approval.read",
            "tenant.notification.read",
        }
    )
    menus, groups = menus_for(_rows(), "TENANT", perms)
    assert [g.key for g in groups] == ["tenant.finance", "tenant.admin"]
    assert [(m.group, m.label) for m in menus] == [
        ("tenant.finance", "Hire finance"),
        ("tenant.finance", "Expenses & fuel"),
        ("tenant.finance", "Approvals"),
        ("tenant.finance", "Profitability"),
        ("tenant.admin", "Notifications"),
    ]
    assert menus_for(_rows(), "TENANT", frozenset()) == ([], [])


def test_registration_rejects_ungrouped_or_cross_scope_menus() -> None:
    catalog = PermissionCatalog()
    catalog.register("tenant.x.read", PermissionScope.TENANT, "x")
    catalog.register_group(MenuGroupDef("tenant.g", PermissionScope.TENANT, "G", 1))
    catalog.register_group(MenuGroupDef("platform.g", PermissionScope.PLATFORM, "P", 1))
    with pytest.raises(ValueError, match="menu group"):
        catalog.register_menu(MenuDef("tenant.new", PermissionScope.TENANT, "New", "/n", 1, "tenant.x.read", ""))
    with pytest.raises(ValueError, match="menu group"):
        catalog.register_menu(MenuDef("tenant.new", PermissionScope.TENANT, "New", "/n", 1, "tenant.x.read", "nope"))
    with pytest.raises(ValueError, match="menu group"):
        catalog.register_menu(
            MenuDef("tenant.new", PermissionScope.TENANT, "New", "/n", 1, "tenant.x.read", "platform.g")
        )
    with pytest.raises(ValueError, match="must start with"):
        catalog.register_group(MenuGroupDef("tenant.bad", PermissionScope.PLATFORM, "Bad", 1))
    catalog.register_menu(MenuDef("tenant.new", PermissionScope.TENANT, "New", "/n", 1, "tenant.x.read", "tenant.g"))
    assert [m.group for m in catalog.menus()] == ["tenant.g"]
