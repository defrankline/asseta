"""Tenant hire finance permissions (registered in the catalog at import). Template prefixes: `tenant.finance.*`
(accountant/owner), `tenant.collection.*` (supervisor capture + accountant)."""

from asseta.modules.identity.catalog import CATALOG, MenuDef
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.dependencies import requires, requires_any

FINANCE_READ = requires(
    "tenant.finance.read", S.TENANT, "View hire invoices, customer payments, balances, statements and cash custody"
)
INVOICE_WRITE = requires("tenant.finance.invoice", S.TENANT, "Draft, issue and void customer hire invoices")
PAYMENT_WRITE = requires("tenant.finance.payment", S.TENANT, "Record customer payments and allocate them to invoices")
VERIFY = requires("tenant.finance.verify", S.TENANT, "Verify or reject customer payments and cash handovers")
CASH_OFFICE = requires("tenant.finance.cash", S.TENANT, "Issue cash floats and record custody for any supervisor")
REPORT = requires("tenant.finance.report", S.TENANT, "View machine/job/customer profitability")
COLLECT = requires(
    "tenant.collection.record",
    S.TENANT,
    "Record cash collections, transfers and remittances (own custody; for any custodian when the tenant allows)",
)
# Cash custody chain controls (accountability design C). Approvals are permissions; never tied to a role.
VARIANCE = requires("tenant.finance.variance", S.TENANT, "Resolve cash variances and propose write-offs")
WRITEOFF = requires("tenant.finance.writeoff", S.TENANT, "Write off cash variances (approve proposed write-offs)")
RETENTION_APPROVE = requires(
    "tenant.finance.retention_approve", S.TENANT, "Approve or reject requests to retain field cash"
)
ADJUSTMENT_APPROVE = requires(
    "tenant.finance.adjustment_approve", S.TENANT, "Approve or reject custody reversals and adjustments"
)
REASON_MANAGE = requires(
    "tenant.finance.reason_manage", S.TENANT, "Manage the tenant's cash reason lists (variance, write-off, ...)"
)
CUSTODY_READ = requires_any(("tenant.collection.record", "tenant.finance.read"), S.TENANT)
CUSTODY_RECORD = requires_any(("tenant.collection.record", "tenant.finance.cash"), S.TENANT)

for menu in (
    MenuDef(
        "tenant.finance", S.TENANT, "Hire finance", "/tenant/finance", 66, "tenant.finance.read", group="tenant.finance"
    ),
    MenuDef(
        "tenant.cash_custody",
        S.TENANT,
        "Cash custody",
        "/tenant/finance/cash",
        67,
        "tenant.finance.read",
        group="tenant.finance",
    ),
    MenuDef(
        "tenant.profitability",
        S.TENANT,
        "Profitability",
        "/tenant/profitability",
        70,
        "tenant.finance.report",
        group="tenant.finance",
    ),
    MenuDef(
        "tenant.field.cash",
        S.TENANT,
        "Cash",
        "/tenant/field/cash",
        15,
        "tenant.collection.record",
        group="tenant.field",
    ),
):
    CATALOG.register_menu(menu)
