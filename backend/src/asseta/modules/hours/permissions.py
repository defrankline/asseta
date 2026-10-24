"""Customer hours permissions (registered in the catalog at import). Approvals are permissions any role can be
granted; segregation of duties (proposer != approver) is enforced in the service, never by role name."""

from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.dependencies import requires

HOURS_READ = requires("tenant.hours.read", S.TENANT, "View hours purchases, balances, the hours ledger and approvals")
HOURS_PURCHASE = requires(
    "tenant.hours.purchase", S.TENANT, "Record walk-in customers and hours purchases, link payments and evidence"
)
DISCOUNT_PROPOSE = requires("tenant.hours.discount", S.TENANT, "Propose, edit and withdraw customer discounts")
DISCOUNT_APPROVE = requires(
    "tenant.hours.discount_approve", S.TENANT, "Approve, reject or revoke customer discounts (not your own)"
)
CREDIT_PROPOSE = requires("tenant.hours.credit", S.TENANT, "Propose, edit and withdraw customer credit arrangements")
CREDIT_APPROVE = requires(
    "tenant.hours.credit_approve", S.TENANT, "Approve, reject or revoke credit arrangements (not your own)"
)
CREDIT_ACTIVATE = requires(
    "tenant.hours.credit_activate", S.TENANT, "Activate purchased hours on credit within an approved arrangement"
)
TRANSFER_REQUEST = requires("tenant.hours.transfer", S.TENANT, "Request an hours transfer to another machine")
TRANSFER_APPROVE = requires("tenant.hours.transfer_approve", S.TENANT, "Approve or reject hours transfers")
CANCEL_REQUEST = requires("tenant.hours.cancel", S.TENANT, "Request cancellation of an hours purchase")
CANCEL_APPROVE = requires("tenant.hours.cancel_approve", S.TENANT, "Approve or reject hours purchase cancellations")
REASONS_MANAGE = requires(
    "tenant.hours.reasons", S.TENANT, "Maintain the tenant's discount/credit/transfer/cancellation reason lists"
)
