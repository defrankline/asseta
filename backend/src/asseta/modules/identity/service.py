"""Identity use cases."""

from sqlalchemy.orm import Session

from asseta.modules.identity.dto import MeDto, MenuDto, TenantAccessDto
from asseta.modules.identity.models import Menu
from asseta.modules.identity.principal import TokenClaims
from asseta.modules.identity.repository import IdentityRepository
from asseta.modules.identity.tokens import parse_group_grants


def _menus_for(menus: list[Menu], scope: str, permissions: frozenset[str]) -> list[MenuDto]:
    return [
        MenuDto(key=m.key, label=m.label, path=m.path, order=m.sort_order)
        for m in menus
        if m.scope == scope and m.required_permission in permissions
    ]


class IdentityService:
    def __init__(self, session: Session):
        self._repo = IdentityRepository(session)

    def me(self, claims: TokenClaims) -> MeDto:
        user = self._repo.upsert_user_from_claims(claims)
        grants = parse_group_grants(claims.groups)
        menus = self._repo.menus()
        platform_perms = self._repo.permissions_for_groups(g for g in claims.groups if g.startswith("/platform/"))
        tenants = []
        for tenant in self._repo.tenants_by_ids(grants.tenant_roles.keys()):
            perms = self._repo.permissions_for_groups(
                g for g in claims.groups if g.startswith(f"/tenants/{tenant.id}/")
            )
            tenants.append(
                TenantAccessDto(
                    tenant_id=tenant.id,
                    name=tenant.display_name,
                    status=tenant.status,
                    access_state=tenant.access_state,
                    permissions=sorted(perms),
                    menus=_menus_for(menus, "TENANT", perms),
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
