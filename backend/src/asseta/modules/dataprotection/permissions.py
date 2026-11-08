"""Data protection permissions and menus (DEC-032 Phase 5). Approvals and access are permissions any role can be
granted; the tenant owner template holds every `tenant.` permission."""

from asseta.modules.identity.catalog import CATALOG, MenuDef
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.dependencies import requires

DATA_EXPORT = requires("tenant.data.export", S.TENANT, "Export all of the company's data and fetch its evidence files")
BALANCE_READ = requires("tenant.balance.read", S.TENANT, "View balance verification results")
BALANCE_VERIFY = requires("tenant.balance.verify", S.TENANT, "Run balance verification on the company's records")
PLATFORM_BALANCE_READ = requires(
    "platform.balance.read", S.PLATFORM, "View balance verification results of every tenant (counts only)"
)
PLATFORM_BALANCE_VERIFY = requires(
    "platform.balance.verify", S.PLATFORM, "Run balance verification on a tenant's records (counts only)"
)
GO_LIVE = requires("platform.tenant.go_live", S.PLATFORM, "Mark a tenant as live (locks the tenant data reset)")

for key, scope, label, path, order, permission, group in (
    (
        "tenant.data_export",
        S.TENANT,
        "Data export",
        "/tenant/data-export",
        80,
        "tenant.data.export",
        "tenant.admin",
    ),
    (
        "tenant.balance_verification",
        S.TENANT,
        "Balance verification",
        "/tenant/balance-verification",
        82,
        "tenant.balance.read",
        "tenant.admin",
    ),
    (
        "platform.balance_verification",
        S.PLATFORM,
        "Balance verification",
        "/platform/balance-verification",
        85,
        "platform.balance.read",
        "platform.admin",
    ),
):
    CATALOG.register_menu(MenuDef(key, scope, label, path, order, permission, group=group))
