"""Data protection permissions and menus (DEC-032 Phase 5). Approvals and access are permissions any role can be
granted; the tenant owner template holds every `tenant.` permission."""

from asseta.modules.identity.catalog import CATALOG, MenuDef
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.dependencies import requires

_DATA_EXPORT_TEXT = "Export all of the company's data and fetch its evidence files"
DATA_EXPORT = requires("tenant.data.export", S.TENANT, _DATA_EXPORT_TEXT)
# Guideline 9: a company on a read-only subscription keeps access to its data. Exactly two writes use this guard:
# requesting an export and requesting its download link. Every other write stays refused.
DATA_EXPORT_READ_ONLY_EXEMPT = requires("tenant.data.export", S.TENANT, _DATA_EXPORT_TEXT, read_only_exempt=True)
BALANCE_READ = requires("tenant.balance.read", S.TENANT, "View balance verification results")
BALANCE_VERIFY = requires("tenant.balance.verify", S.TENANT, "Run balance verification on the company's records")
PLATFORM_BALANCE_READ = requires(
    "platform.balance.read", S.PLATFORM, "View balance verification results of every tenant (counts only)"
)
PLATFORM_BALANCE_VERIFY = requires(
    "platform.balance.verify", S.PLATFORM, "Run balance verification on a tenant's records (counts only)"
)
# Company closure: deletes ALL of the company's data after the platform-wide waiting period. In the owner template only
# (it is an approver-control permission: only an owner can give it to anyone). Requesting and cancelling stay open on
# a read-only subscription (the request itself makes the company read-only, and leaving is the company's right).
_COMPANY_CLOSE_TEXT = "Close the company and delete all its data"
COMPANY_CLOSE_PERMISSION = "tenant.company.close"
COMPANY_CLOSE = requires(COMPANY_CLOSE_PERMISSION, S.TENANT, _COMPANY_CLOSE_TEXT, read_only_exempt=True)
COMPANY_CLOSE_VIEW = requires(COMPANY_CLOSE_PERMISSION, S.TENANT, _COMPANY_CLOSE_TEXT)
PLATFORM_DELETION_READ = requires("platform.tenant.deletion.read", S.PLATFORM, "View company deletion requests")
PLATFORM_DELETION_EXECUTE = requires(
    "platform.tenant.deletion.execute",
    S.PLATFORM,
    "Run a company deletion before its waiting period ends (when the owner asks in writing)",
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
        "tenant.company_close",
        S.TENANT,
        "Close company",
        "/tenant/company/close",
        95,
        COMPANY_CLOSE_PERMISSION,
        "tenant.admin",
    ),
    (
        "platform.deletion_requests",
        S.PLATFORM,
        "Deletion requests",
        "/platform/deletion-requests",
        28,
        "platform.tenant.deletion.read",
        "platform.tenants",
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
