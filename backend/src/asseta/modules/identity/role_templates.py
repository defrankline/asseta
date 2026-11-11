"""Seeded role templates (examples, not hard-coded authority). Applied to Keycloak groups when a tenant or
the platform is provisioned; afterwards Keycloak group->role mappings are authoritative and editable."""

from dataclasses import dataclass

from asseta.modules.identity.catalog import CATALOG, PermissionScope


@dataclass(frozen=True)
class RoleTemplate:
    key: str
    name: str
    scope: PermissionScope
    # An entry ending in "." covers everything under it; any other entry is that one permission, exactly.
    include_prefixes: tuple[str, ...]
    read_only: bool = False
    # Taken once from groups of this template (granted by mistake); a later deliberate re-grant is respected.
    retired: tuple[str, ...] = ()
    # Added to this template after the permission already existed: reaches an existing group only if nobody edited it.
    later_additions: frozenset[str] = frozenset()


MANAGER_METER = ("tenant.meter.read", "tenant.meter.review", "tenant.meter.approve", "tenant.meter.classify")

PLATFORM_TEMPLATES = (
    RoleTemplate("platform-owner", "Platform Owner", PermissionScope.PLATFORM, ("platform.",)),
    RoleTemplate("platform-auditor", "Platform Auditor", PermissionScope.PLATFORM, ("platform.",), read_only=True),
)

TENANT_TEMPLATES = (
    RoleTemplate("owner", "Tenant Owner", PermissionScope.TENANT, ("tenant.",)),
    RoleTemplate(
        "manager",
        "Manager / Dispatcher",
        PermissionScope.TENANT,
        (
            "tenant.machine.",
            "tenant.staff.",
            "tenant.tracker.",
            "tenant.fleet.",
            "tenant.geofence.",
            "tenant.job.",
            "tenant.customer.",
            "tenant.approval.",
            "tenant.policy.read",
            "tenant.notification.read",
            "tenant.directory.read",
            "tenant.case.",  # investigation cases (Gate 6)
            "tenant.signal.read",
            "tenant.audit.read",  # tenant audit log (Gate 7)
            # Accountability (DEC-030): managers record cash on custodians' behalf (operators hold cash without a
            # login), oversee the dashboard, refused attempts and offline sync conflicts.
            "tenant.collection.record",
            "tenant.accountability.read",
            "tenant.accountability.employee.read",
            "tenant.lookup.read",
            "tenant.security_event.read",
            "tenant.sync_conflict.",
            # DEC-032 Phase 4: management reviews readings and approves meter exceptions (never their own proposal).
            *MANAGER_METER,
            # Customer hours (DEC-030 / 3.1): managers record purchases and walk-ins for the field, propose and
            # approve discounts/credit/transfers/cancellations (never their own: segregation of duties).
            "tenant.hours.",
            # Revenue reconciliation (DEC-031): see the daily machine sheet, explain revenue differences and decide
            # on someone else's explanation (never their own: segregation of duties).
            "tenant.revenue.",
            # Oversight (DEC-031 Phase 5): the people scorecard, unbilled work, idle machines and site check-ins.
            "tenant.oversight.",
            # Go-live setup checklist: see progress, mark steps not needed, confirm default controls.
            "tenant.setup.",
            # DEC-032 T7: managers read the adjustments ledger and propose corrections/refunds/reversals; they decide
            # only when a role grants `tenant.adjustment.decide` (never their own: segregation of duties).
            "tenant.adjustment.read",
            "tenant.adjustment.propose",
            # DEC-033 petty cash: managers run the funds (create, edit, change holder) and count them; fundings and
            # top-ups are proposed and approved by others.
            "tenant.pettycash.read",
            "tenant.pettycash.manage",
            "tenant.pettycash.count",
        ),
        later_additions=frozenset(MANAGER_METER),
    ),
    RoleTemplate(
        "supervisor",
        "Supervisor",
        PermissionScope.TENANT,
        (
            "tenant.job.read",
            "tenant.job.log",
            "tenant.job.request",  # request jobs from the field; the owner/manager approves them
            "tenant.meter.capture",
            "tenant.meter.read",
            "tenant.customer.read",
            "tenant.customer.details",  # supervisors deal with customers daily: add them, keep their details current
            "tenant.expense.read",
            "tenant.expense.write",
            "tenant.collection.record",
            "tenant.hours.read",  # customer hours: see balances, record walk-in purchases, request transfers
            "tenant.hours.purchase",
            "tenant.hours.transfer",
            "tenant.sync.read",
            "tenant.sync.push",
            "tenant.fleet.read",
            "tenant.notification.read",
            "tenant.directory.read",
            "tenant.site_checkin.record",  # GPS site check-in at the tenant's times (DEC-031 M3; only when switched on)
            "tenant.pettycash.read",  # DEC-033: the funds they hold (never anyone else's), and counting them
            "tenant.pettycash.count",
        ),
        retired=("tenant.hours.transfer_approve",),
    ),
    RoleTemplate(
        "accountant",
        "Accountant / Finance",
        PermissionScope.TENANT,
        (
            "tenant.finance.",
            "tenant.expense.",
            "tenant.collection.",
            "tenant.billing.read",
            "tenant.notification.read",
            "tenant.directory.read",
            # Read-only reference data so invoices, payments and custody show customer, job, machine and
            # supervisor names (DEC-023); no write on operations.
            "tenant.customer.read",
            "tenant.job.read",
            "tenant.machine.read",
            "tenant.staff.read",
            "tenant.case.read",  # read-only view of investigation cases and signals (Gate 6)
            "tenant.signal.read",
            "tenant.accountability.read",  # accountability dashboard (DEC-030)
            "tenant.accountability.employee.read",  # one person's cash and records (the scorecard stays separate)
            "tenant.lookup.read",
            "tenant.hours.read",  # customer hours: link payments to purchases, activate on approved credit
            "tenant.hours.purchase",
            "tenant.hours.credit_activate",
            "tenant.revenue.read",  # revenue reconciliation (DEC-031): daily sheet, explain differences
            "tenant.revenue.explain",
            "tenant.oversight.read",  # unbilled work and idle machines (DEC-031 M2); not the people scorecard
            "tenant.adjustment.",  # adjustments ledger: read, propose, decide (never your own proposal)
            "tenant.pettycash.read",  # DEC-033: propose fundings/top-ups/adjustments, issue money, confirm returns
            "tenant.pettycash.propose",
            "tenant.pettycash.count",
        ),
    ),
    RoleTemplate(
        "operator",
        "Operator",
        PermissionScope.TENANT,
        ("tenant.notification.read", "tenant.directory.read"),
    ),
    # DEC-032 D2: managers record readings for operators by default. A tenant lets an operator submit their own by
    # adding this group to the person; it is not part of the Operator template.
    RoleTemplate(
        "operator-readings",
        "Operator: submits own readings",
        PermissionScope.TENANT,
        (
            "tenant.meter.capture",
            "tenant.meter.read",
            "tenant.job.read",
            "tenant.sync.read",
            "tenant.sync.push",
            "tenant.notification.read",
            "tenant.directory.read",
        ),
    ),
    # Guideline section 6: system configuration and user access, no business approvals.
    RoleTemplate(
        "administrator",
        "Administrator",
        PermissionScope.TENANT,
        (
            "tenant.access.read",
            "tenant.access.manage",
            "tenant.policy.read",
            "tenant.policy.manage",
            "tenant.setup.read",
            "tenant.setup.manage",
            "tenant.notification.read",
            "tenant.notification.manage",
            "tenant.directory.read",
            "tenant.device.manage",
            "tenant.audit.read",
            "tenant.staff.read",
            "tenant.staff.write",
            "tenant.machine.read",
            "tenant.machine.write",
            "tenant.fleet.read",
            "tenant.tracker.read",
            "tenant.tracker.write",
            "tenant.geofence.read",
            "tenant.geofence.write",
            "tenant.billing.read",
            # The tenant's own lists: configuration, not decisions.
            "tenant.hours.reasons",
            "tenant.meter.reasons",
            "tenant.finance.reason_manage",
            "tenant.finance.expense_category",
        ),
    ),
)

# Permissions that decide something another person proposed or recorded. Field and administrator templates hold none.
DECISION_PERMISSIONS = frozenset(
    {
        "tenant.adjustment.decide",
        "tenant.approval.expense",
        "tenant.case.resolve",
        "tenant.finance.adjustment_approve",
        "tenant.finance.retention_approve",
        "tenant.finance.variance_close",
        "tenant.finance.verify",
        "tenant.finance.writeoff",
        "tenant.hours.cancel_approve",
        "tenant.hours.credit_activate",
        "tenant.hours.credit_approve",
        "tenant.hours.discount_approve",
        "tenant.hours.transfer_approve",
        "tenant.job.approve",
        "tenant.meter.approve",
        "tenant.meter.classify",
        "tenant.pettycash.approve",
        "tenant.revenue.decide",
        "tenant.sync_conflict.resolve",
    }
)

# Gives or takes away roles that carry approvals. Only the owner template holds it (through "tenant."); never add
# "tenant.access." as a prefix to another template.
ASSIGN_APPROVERS_PERMISSION = "tenant.access.assign_approvers"
# A role carrying any of these takes the permission above to assign or remove: the permission itself is included so a
# role carrying only it cannot be used to reach the approvals indirectly.
APPROVER_CONTROL_PERMISSIONS = DECISION_PERMISSIONS | {ASSIGN_APPROVERS_PERMISSION}


def template_permissions(template: RoleTemplate) -> set[str]:
    codes = set()
    exact = {e for e in template.include_prefixes if not e.endswith(".")}
    prefixes = tuple(e for e in template.include_prefixes if e.endswith("."))
    for p in CATALOG.permissions():
        if p.scope is not template.scope or not (p.code in exact or p.code.startswith(prefixes)):
            continue
        if template.read_only and not p.code.endswith(".read"):
            continue
        codes.add(p.code)
    return codes
