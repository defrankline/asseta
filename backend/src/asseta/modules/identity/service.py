"""Identity use cases."""

import uuid
from datetime import date

from sqlalchemy.orm import Session

from asseta.core.db import DbScope, apply_scope
from asseta.modules.identity.dto import MandateBadgeDto, MeDto, MenuDto, TenantAccessDto
from asseta.modules.identity.models import Menu
from asseta.modules.identity.principal import TokenClaims
from asseta.modules.identity.repository import IdentityRepository
from asseta.modules.identity.tokens import parse_group_grants
from asseta.modules.managed_service.gate import MandateGrant, grants_for_user, has_assignment_history


def _menus_for(menus: list[Menu], scope: str, permissions: frozenset[str]) -> list[MenuDto]:
    return [
        MenuDto(key=m.key, label=m.label, path=m.path, order=m.sort_order)
        for m in menus
        if m.scope == scope and m.required_permission in permissions
    ]


class IdentityService:
    def __init__(self, session: Session):
        self._s = session
        self._repo = IdentityRepository(session)

    def me(self, claims: TokenClaims, today: date) -> MeDto:
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
            tenants.append(
                TenantAccessDto(
                    tenant_id=tenant.id,
                    name=tenant.display_name,
                    status=tenant.status,
                    access_state=tenant.access_state,
                    permissions=sorted(perms),
                    menus=_menus_for(menus, "TENANT", perms),
                    mandate=MandateBadgeDto(
                        mandate_id=grant.mandate_id,
                        reference=grant.reference,
                        scope=grant.scope.value,
                        ends_on=grant.ends_on,
                    )
                    if grant
                    else None,
                )
            )
        return MeDto(
            user_id=user.id,
            email=user.email,
            display_name=user.display_name,
            platform_permissions=sorted(platform_perms),
            platform_menus=_menus_for(menus, "PLATFORM", platform_perms),
            tenants=sorted(tenants, key=lambda t: t.name),
        )
