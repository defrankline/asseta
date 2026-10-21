"""Tenant hire finance permissions (registered in the catalog at import). Template prefixes: `tenant.finance.*`
(accountant/owner), `tenant.collection.*` (supervisor capture + accountant)."""

from asseta.modules.identity.catalog import CATALOG, MenuDef
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.dependencies import requires

FINANCE_READ = requires(
    "tenant.finance.read", S.TENANT, "View hire invoices, customer payments, balances, statements and cash custody"
)
INVOICE_WRITE = requires("tenant.finance.invoice", S.TENANT, "Draft, issue and void customer hire invoices")
PAYMENT_WRITE = requires("tenant.finance.payment", S.TENANT, "Record customer payments and allocate them to invoices")
VERIFY = requires("tenant.finance.verify", S.TENANT, "Verify or reject customer payments and cash handovers")
CASH_OFFICE = requires("tenant.finance.cash", S.TENANT, "Issue cash floats and record custody for any supervisor")
REPORT = requires("tenant.finance.report", S.TENANT, "View machine/job/customer profitability")
COLLECT = requires("tenant.collection.record", S.TENANT, "Record cash collections and cash handovers (own custody)")

for menu in (
    MenuDef("tenant.finance", S.TENANT, "Hire finance", "/tenant/finance", 66, "tenant.finance.read"),
    MenuDef("tenant.profitability", S.TENANT, "Profitability", "/tenant/profitability", 67, "tenant.finance.report"),
):
    CATALOG.register_menu(menu)
