"""Synchronizes the code-declared permission catalog to Keycloak and mirrors Keycloak role groups to the DB.

Idempotent; safe to run on every startup and after any role change made through the API.
"""

import uuid

import structlog
from sqlalchemy.orm import Session

from asseta.core.db import utcnow
from asseta.modules.identity.catalog import CATALOG, PLATFORM_GROUP_ROOT, TENANT_GROUP_ROOT
from asseta.modules.identity.idp import IdentityProviderAdmin
from asseta.modules.identity.repository import IdentityRepository
from asseta.modules.identity.role_templates import (
    PLATFORM_TEMPLATES,
    TENANT_TEMPLATES,
    template_permissions,
)
from asseta.modules.identity.tokens import platform_group_path, tenant_group_path

log = structlog.get_logger()


class AuthzSyncService:
    def __init__(self, idp: IdentityProviderAdmin):
        self._idp = idp

    def push_catalog(self, session: Session) -> None:
        perms = CATALOG.permissions()
        self._idp.ensure_permission_roles([p.code for p in perms], {p.code: p.description for p in perms})
        IdentityRepository(session).sync_permission_catalog(perms, CATALOG.menus())

    def ensure_platform_roles(self) -> None:
        for template in PLATFORM_TEMPLATES:
            self._idp.ensure_group(platform_group_path(template.key))

    def provision_tenant_roles(self, tenant_id: uuid.UUID, session: Session) -> dict[str, str]:
        """Create the seeded role groups for a new tenant and offer their template permissions."""
        result = {t.key: self._idp.ensure_group(tenant_group_path(tenant_id, t.key)) for t in TENANT_TEMPLATES}
        self.apply_templates(session, only_paths={tenant_group_path(tenant_id, k) for k in result})
        return result

    def apply_templates(self, session: Session, only_paths: set[str] | None = None) -> int:
        """Offer each template permission to each matching role group exactly once. New permissions from a
        release reach existing groups; permissions an owner removed after being offered are never re-added."""
        repo = IdentityRepository(session)
        templates = {t.key: t for t in (*PLATFORM_TEMPLATES, *TENANT_TEMPLATES)}
        changed = 0
        for group in self._idp.list_role_groups():
            template = templates.get(group.name)
            if template is None or (only_paths is not None and group.path not in only_paths):
                continue
            wanted = template_permissions(template)
            to_offer = wanted - repo.offered_codes(group.path)
            if not to_offer:
                continue
            if to_offer - group.permission_codes:
                self._idp.set_group_permissions(group.group_id, set(group.permission_codes) | to_offer)
                changed += 1
            repo.record_offered(group.path, to_offer)
        if changed:
            log.info("authz_template_permissions_offered", groups=changed)
        return changed

    def pull_role_mirror(self, session: Session, only_tenant: uuid.UUID | None = None) -> int:
        repo = IdentityRepository(session)
        groups = self._idp.list_role_groups()
        now = utcnow()
        known_tenants = repo.tenant_ids()
        orphans: set[str] = set()
        for g in groups:
            parts = [p for p in g.path.split("/") if p]
            tenant_id = uuid.UUID(parts[1]) if parts[0] == TENANT_GROUP_ROOT else None
            if parts[0] not in (PLATFORM_GROUP_ROOT, TENANT_GROUP_ROOT):
                continue
            role_id = repo.replace_role_mirror(
                tenant_id=tenant_id,
                key=g.name,
                name=g.name,
                group_id=g.group_id,
                group_path=g.path,
                permission_codes=set(g.permission_codes),
                synced_at=now,
            )
            if tenant_id is None and only_tenant is None:
                repo.reconcile_platform_memberships(role_id, self._idp.list_group_members(g.group_id), now)
            if tenant_id is not None and (only_tenant is None or tenant_id == only_tenant):
                if tenant_id not in known_tenants:  # orphan group (e.g. onboarding rolled back after Keycloak)
                    orphans.add(str(tenant_id))
                    continue
                repo.reconcile_memberships(tenant_id, role_id, self._idp.list_group_members(g.group_id), now)
        repo.delete_roles_not_in({g.path for g in groups})
        if orphans:
            log.warning("authz_orphan_tenant_groups", tenants=sorted(orphans))
        log.info("authz_mirror_synced", role_groups=len(groups))
        return len(groups)

    def full_sync(self, session: Session) -> int:
        self.push_catalog(session)
        self.ensure_platform_roles()
        self.apply_templates(session)
        return self.pull_role_mirror(session)
