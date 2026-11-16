"""Machine report permissions and menus (ADR-008 §2), registered in the catalog at import. Approval is a permission
any role can be granted; the person who submitted a report never decides it (enforced in the service)."""

from asseta.modules.identity.catalog import CATALOG, MenuDef, MenuGroupDef
from asseta.modules.identity.catalog import PermissionScope as S
from asseta.modules.identity.dependencies import requires, requires_any

SUBMIT_PERMISSION = "tenant.machine_report.submit"
READ_PERMISSION = "tenant.machine_report.read"
APPROVE_PERMISSION = "tenant.machine_report.approve"
REASONS_PERMISSION = "tenant.meter.reasons"

SUBMIT = requires(
    SUBMIT_PERMISSION,
    S.TENANT,
    "Submit machine reports (new reading and how its hours split) for machines assigned to you",
)
READ = requires(READ_PERMISSION, S.TENANT, "View machine reports, their tracker cross-check and report status")
APPROVE = requires(
    APPROVE_PERMISSION, S.TENANT, "Approve or reject machine reports (never your own); report on any machine"
)
REASONS = requires(
    REASONS_PERMISSION, S.TENANT, "Manage engine-hour activity categories and variance reasons"
)  # the machine-report reason list is one of the engine-hour reason lists
CONTEXT = requires_any((SUBMIT_PERMISSION, APPROVE_PERMISSION), S.TENANT)
REASONS_READ = requires_any((SUBMIT_PERMISSION, READ_PERMISSION, REASONS_PERMISSION), S.TENANT)

# Approvals: one place for the decisions owners and managers take (ADR-008 §5), right after Field work.
CATALOG.register_group(MenuGroupDef("tenant.approvals", S.TENANT, "Approvals", 17))
for _menu in (
    MenuDef(
        "tenant.approvals.machine_reports",
        S.TENANT,
        "Machine reports",
        "/tenant/machine-reports",
        17,
        READ_PERMISSION,
        group="tenant.approvals",
    ),
    MenuDef(
        "tenant.field.machine_report",
        S.TENANT,
        "Machine report",
        "/tenant/field/machine-report",
        10,
        SUBMIT_PERMISSION,
        group="tenant.field",
    ),
    MenuDef(
        "tenant.machine_report_reasons",
        S.TENANT,
        "Machine report reasons",
        "/tenant/machine-report-reasons",
        91,
        REASONS_PERMISSION,
        group="tenant.admin",
    ),
):
    CATALOG.register_menu(_menu)
