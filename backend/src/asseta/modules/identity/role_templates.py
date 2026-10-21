"""Seeded role templates (examples, not hard-coded authority). Applied to Keycloak groups when a tenant or
the platform is provisioned; afterwards Keycloak group->role mappings are authoritative and editable."""

from dataclasses import dataclass

from asseta.modules.identity.catalog import CATALOG, PermissionScope


@dataclass(frozen=True)
class RoleTemplate:
    key: str
    name: str
    scope: PermissionScope
    include_prefixes: tuple[str, ...]
    read_only: bool = False


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
        ),
    ),
    RoleTemplate(
        "supervisor",
        "Supervisor",
        PermissionScope.TENANT,
        ("tenant.job.", "tenant.meter.", "tenant.expense.", "tenant.collection.", "tenant.sync."),
    ),
    RoleTemplate(
        "accountant",
        "Accountant / Finance",
        PermissionScope.TENANT,
        ("tenant.finance.", "tenant.expense.", "tenant.collection.", "tenant.billing.read"),
    ),
    RoleTemplate("operator", "Operator", PermissionScope.TENANT, ("tenant.profile.",)),
)


def template_permissions(template: RoleTemplate) -> set[str]:
    codes = set()
    for p in CATALOG.permissions():
        if p.scope is not template.scope or not p.code.startswith(template.include_prefixes):
            continue
        if template.read_only and not p.code.endswith(".read"):
            continue
        codes.add(p.code)
    return codes
