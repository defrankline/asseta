"""Identity use cases."""

import uuid
from datetime import date, datetime

from sqlalchemy.orm import Session

from asseta.core.db import DbScope, apply_scope, utcnow
from asseta.modules.identity.catalog import CATALOG
from asseta.modules.identity.dto import MandateBadgeDto, MeDto, MenuDto, MenuGroupDto, TenantAccessDto
from asseta.modules.identity.models import Menu
from asseta.modules.identity.principal import TokenClaims
from asseta.modules.identity.repository import IdentityRepository
from asseta.modules.identity.tokens import parse_group_grants
from asseta.modules.managed_service.gate import MandateGrant, grants_for_user, has_assignment_history
from asseta.modules.onboarding.checklist import SETUP_READ_PERMISSION
from asseta.modules.onboarding.checklist import compute as compute_setup
from asseta.modules.policy.capabilities import disabled_capabilities


def menus_for(
    menus: list[Menu], scope: str, permissions: frozenset[str], disabled: frozenset[str] = frozenset()
) -> tuple[list[MenuDto], list[MenuGroupDto]]:
    """Visible menus of one console, plus the groups holding at least one of them (both in display order). Menus
    whose capability (own or group's, from the catalog) is switched off by the tenant's policy are left out."""
    visible = sorted(
        (
            m
            for m in menus
            if m.scope == scope
            and m.required_permission in permissions
            and not (CATALOG.menu_capabilities(m.key) & disabled)
        ),
        key=lambda m: (m.sort_order, m.label),
    )
    used = {m.group_key for m in visible}
    return (
        [MenuDto(key=m.key, label=m.label, path=m.path, order=m.sort_order, group=m.group_key) for m in visible],
        [MenuGroupDto(key=g.key, label=g.label, order=g.order) for g in CATALOG.menu_groups() if g.key in used],
    )


class IdentityService:
    def __init__(self, session: Session):
        self._s = session
        self._repo = IdentityRepository(session)

    def me(self, claims: TokenClaims, today: date, now: datetime | None = None) -> MeDto:
        """Tenants the user may enter. Platform staff reach clients only through in-force mandates (DEC-018); the
        Keycloak groups those mandates create are never shown as ordinary tenant membership."""
        user = self._repo.upsert_user_from_claims(claims)
        grants = parse_group_grants(claims.groups)
        menus = self._repo.menus()
        platform_groups = [g for g in claims.groups if g.startswith("/platform/")]
        platform_perms = self._repo.permissions_for_groups(platform_groups)
        access: dict[uuid.UUID, tuple[frozenset[str], MandateGrant | None]] = {}
        if platform_groups:
            apply_scope(self._s, DbScope.PLATFORM, None, user.id)
            for tid, live in grants_for_user(self._s, user.id, today).items():
                access[tid] = (live.group_paths, live)  # permissions from the mandate's roles
        else:
            for tid in grants.tenant_roles:
                apply_scope(self._s, DbScope.TENANT, tid, user.id)
                if has_assignment_history(self._s, tid, user.id):
                    continue  # former mandate staff: never an ordinary member through leftover groups
                access[tid] = (frozenset(g for g in claims.groups if g.startswith(f"/tenants/{tid}/")), None)
        tenants = []
        for tenant in self._repo.tenants_by_ids(access.keys()):
            paths, grant = access[tenant.id]
            perms = self._repo.permissions_for_groups(paths)
            apply_scope(self._s, DbScope.TENANT, tenant.id, user.id)  # the tenant's own effective policy
            disabled = disabled_capabilities(self._s, tenant.id, utcnow())
            tenant_menus, tenant_groups = menus_for(menus, "TENANT", perms, disabled)
            setup = (
                compute_setup(self._s, tenant.id, now or utcnow(), disabled) if SETUP_READ_PERMISSION in perms else None
            )
            tenants.append(
                TenantAccessDto(
                    tenant_id=tenant.id,
                    name=tenant.display_name,
                    status=tenant.status,
                    access_state=tenant.access_state,
                    permissions=sorted(perms),
                    menus=tenant_menus,
                    menu_groups=tenant_groups,
                    disabled_capabilities=sorted(disabled),
                    mandate=MandateBadgeDto(
                        mandate_id=grant.mandate_id,
                        reference=grant.reference,
                        scope=grant.scope.value,
                        ends_on=grant.ends_on,
                    )
                    if grant
                    else None,
                    setup_complete=setup.complete if setup else None,
                    setup_percent=setup.percent if setup else None,
                    setup_steps_done=setup.steps_done if setup else None,
                    setup_steps_total=setup.steps_total if setup else None,
                    setup_dismissed=setup.choices.dismissed if setup else None,
                )
            )
        platform_menus, platform_menu_groups = menus_for(menus, "PLATFORM", platform_perms)
        return MeDto(
            user_id=user.id,
            email=user.email,
            display_name=user.display_name,
            platform_permissions=sorted(platform_perms),
            platform_menus=platform_menus,
            platform_menu_groups=platform_menu_groups,
            tenants=sorted(tenants, key=lambda t: t.name),
        )
