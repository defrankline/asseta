"""Petty cash permissions and menus (DEC-033), registered in the catalog at import. Approvals are permissions, never a
role; the proposer is never the approver and the holder never approves or issues money into their own fund."""

from asseta.modules.identity.catalog import CATALOG, MenuDef
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.dependencies import gated, requires
from asseta.modules.policy.capabilities import PETTY_CASH

READ_CODE = "tenant.pettycash.read"
MANAGE_CODE = "tenant.pettycash.manage"
PROPOSE_CODE = "tenant.pettycash.propose"
APPROVE_CODE = "tenant.pettycash.approve"
COUNT_CODE = "tenant.pettycash.count"

_READ = requires(READ_CODE, S.TENANT, "See petty cash funds and their ledgers (field users: only the funds they hold)")
_MANAGE = requires(MANAGE_CODE, S.TENANT, "Create, edit, deactivate and reactivate petty cash funds; change the holder")
_PROPOSE = requires(
    PROPOSE_CODE,
    S.TENANT,
    "Propose petty cash fundings, top-ups and adjustments; issue approved money; confirm returns",
)
_APPROVE = requires(
    APPROVE_CODE, S.TENANT, "Approve or reject petty cash fundings, top-ups and adjustments (never your own)"
)
_COUNT = requires(COUNT_CODE, S.TENANT, "Record a physical count of a petty cash fund or witness one")

# Every petty cash endpoint also needs the tenant's PETTY_CASH capability (PETTY_CASH_DISABLED when off).
PETTY_READ = gated(_READ, PETTY_CASH)
PETTY_MANAGE = gated(_MANAGE, PETTY_CASH)
PETTY_PROPOSE = gated(_PROPOSE, PETTY_CASH)
PETTY_APPROVE = gated(_APPROVE, PETTY_CASH)
PETTY_COUNT = gated(_COUNT, PETTY_CASH)
# Office users who see every fund; anyone else (a holder) sees only the funds they hold.
PETTY_OVERSIGHT = frozenset({MANAGE_CODE, PROPOSE_CODE, APPROVE_CODE})

for menu in (
    MenuDef(
        "tenant.petty_cash",
        S.TENANT,
        "Petty cash",
        "/tenant/finance/petty-cash",
        71,
        READ_CODE,
        group="tenant.finance",
        capability=PETTY_CASH,
    ),
    MenuDef(
        "tenant.field.petty_cash",
        S.TENANT,
        "Petty cash",
        "/tenant/field/petty-cash",
        18,
        READ_CODE,
        group="tenant.field",
        capability=PETTY_CASH,
    ),
):
    CATALOG.register_menu(menu)
