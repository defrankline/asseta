"""Adjustments ledger permissions (registered in the catalog at import). Approvals are permissions any role can be
granted; the proposer can never approve their own proposal (enforced in the service, never by role name)."""

from asseta.modules.identity.catalog import CATALOG, MenuDef
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.dependencies import requires

ADJUSTMENT_READ = requires(
    "tenant.adjustment.read", S.TENANT, "View the adjustments ledger and pending adjustment requests"
)
ADJUSTMENT_PROPOSE = requires(
    "tenant.adjustment.propose",
    S.TENANT,
    "Propose customer-hour corrections, refunds and reversals of posted transactions (never decide your own)",
)
ADJUSTMENT_DECIDE = requires(
    "tenant.adjustment.decide", S.TENANT, "Approve or reject proposed corrections, refunds, reversals and invoice voids"
)
READ_PERMISSION = "tenant.adjustment.read"
DECIDE_PERMISSION = "tenant.adjustment.decide"

CATALOG.register_menu(
    MenuDef(
        "tenant.finance.adjustments",
        S.TENANT,
        "Adjustments ledger",
        "/tenant/finance/adjustments",
        68,
        READ_PERMISSION,
        group="tenant.finance",
    )
)
