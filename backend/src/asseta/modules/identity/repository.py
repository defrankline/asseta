"""Identity persistence (mirror tables). No ORM objects leave the service layer."""

import uuid
from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from asseta.core.db import utcnow
from asseta.modules.identity.catalog import MenuDef, PermissionDef
from asseta.modules.identity.idp import GroupMember
from asseta.modules.identity.models import (
    AppUser,
    Menu,
    Permission,
    PlatformMembership,
    Role,
    RolePermission,
    RoleTemplateGrant,
    TenantMembership,
)
from asseta.modules.identity.principal import TokenClaims
from asseta.modules.tenancy.models import Tenant, TenantAccessState


class IdentityRepository:
    def __init__(self, session: Session):
        self._s = session

    def upsert_user_from_claims(self, claims: TokenClaims) -> AppUser:
        now = utcnow()
        stmt = (
            insert(AppUser)
            .values(
                id=uuid.uuid4(),
                keycloak_subject=claims.subject,
                email=claims.email,
                display_name=claims.display_name,
                is_active=True,
                created_at=now,
                updated_at=now,
                last_seen_at=now,
            )
            .on_conflict_do_update(
                index_elements=[AppUser.keycloak_subject],
                set_={
                    "email": claims.email,
                    "display_name": claims.display_name,
                    "last_seen_at": now,
                    "updated_at": now,
                },
            )
            .returning(AppUser)
        )
        return self._s.execute(stmt).scalar_one()

    def permissions_for_groups(self, group_paths: Iterable[str]) -> frozenset[str]:
        paths = list(group_paths)
        if not paths:
            return frozenset()
        rows = self._s.execute(
            select(RolePermission.permission_code)
            .join(Role, Role.id == RolePermission.role_id)
            .join(Permission, Permission.code == RolePermission.permission_code)
            .where(Role.keycloak_group_path.in_(paths), Permission.is_active.is_(True))
        ).scalars()
        return frozenset(rows)

    def tenant_access_state(self, tenant_id: uuid.UUID) -> TenantAccessState | None:
        return self._s.execute(select(Tenant.access_state).where(Tenant.id == tenant_id)).scalar_one_or_none()

    def tenants_by_ids(self, ids: Iterable[uuid.UUID]) -> list[Tenant]:
        id_list = list(ids)
        if not id_list:
            return []
        return list(self._s.execute(select(Tenant).where(Tenant.id.in_(id_list))).scalars())

    def menus(self) -> list[Menu]:
        return list(self._s.execute(select(Menu).order_by(Menu.scope, Menu.sort_order)).scalars())

    def upsert_member(self, member: GroupMember, now: datetime) -> uuid.UUID:
        """Mirror a Keycloak group member as an app user (they may not have signed in yet)."""
        return self._s.execute(
            insert(AppUser)
            .values(
                id=uuid.uuid4(),
                keycloak_subject=member.subject,
                email=member.email,
                display_name=member.display_name or member.email,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=[AppUser.keycloak_subject], set_={"email": member.email, "updated_at": now}
            )
            .returning(AppUser.id)
        ).scalar_one()

    # --- catalog / Keycloak mirror sync -------------------------------------------------------------
    def reconcile_memberships(
        self, tenant_id: uuid.UUID, role_id: uuid.UUID, members: list[GroupMember], now: datetime
    ) -> tuple[int, int]:
        """Mirror Keycloak group membership as effective-dated rows: open new, close removed (never delete)."""
        user_ids = {self.upsert_member(m, now) for m in members}
        current = {
            r.user_id: r
            for r in self._s.execute(
                select(TenantMembership).where(
                    TenantMembership.tenant_id == tenant_id,
                    TenantMembership.role_id == role_id,
                    TenantMembership.effective_to.is_(None),
                )
            ).scalars()
        }
        opened = closed = 0
        for uid in user_ids - current.keys():
            self._s.add(
                TenantMembership(
                    id=uuid.uuid4(),
                    tenant_id=tenant_id,
                    user_id=uid,
                    role_id=role_id,
                    effective_from=now,
                    created_at=now,
                    updated_at=now,
                )
            )
            opened += 1
        for uid in current.keys() - user_ids:
            current[uid].effective_to = now
            closed += 1
        self._s.flush()
        return opened, closed

    def reconcile_platform_memberships(self, role_id: uuid.UUID, members: list[GroupMember], now: datetime) -> None:
        """Mirror a `/platform/<role>` group's members as effective-dated rows (open new, close removed)."""
        user_ids = {self.upsert_member(m, now) for m in members}
        current = {
            r.user_id: r
            for r in self._s.execute(
                select(PlatformMembership).where(
                    PlatformMembership.role_id == role_id, PlatformMembership.effective_to.is_(None)
                )
            ).scalars()
        }
        for uid in user_ids - current.keys():
            self._s.add(
                PlatformMembership(
                    id=uuid.uuid4(), user_id=uid, role_id=role_id, effective_from=now, created_at=now, updated_at=now
                )
            )
        for uid in current.keys() - user_ids:
            current[uid].effective_to = now
        self._s.flush()

    def tenant_ids(self) -> set[uuid.UUID]:
        return set(self._s.execute(select(Tenant.id)).scalars())

    def offered_codes(self, group_path: str) -> set[str]:
        return set(
            self._s.execute(
                select(RoleTemplateGrant.permission_code).where(RoleTemplateGrant.group_path == group_path)
            ).scalars()
        )

    def record_offered(self, group_path: str, codes: set[str]) -> None:
        now = utcnow()
        for code in sorted(codes):
            self._s.execute(
                insert(RoleTemplateGrant)
                .values(group_path=group_path, permission_code=code, offered_at=now)
                .on_conflict_do_nothing()
            )

    def sync_permission_catalog(self, permissions: list[PermissionDef], menus: list[MenuDef]) -> None:
        now = utcnow()
        codes = [p.code for p in permissions]
        for p in permissions:
            self._s.execute(
                insert(Permission)
                .values(
                    id=uuid.uuid4(),
                    code=p.code,
                    scope=p.scope.value,
                    description=p.description,
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
                .on_conflict_do_update(
                    index_elements=[Permission.code],
                    set_={"scope": p.scope.value, "description": p.description, "is_active": True, "updated_at": now},
                )
            )
        # Retired permissions are deactivated (never deleted) so historical audit stays interpretable.
        self._s.execute(update(Permission).where(Permission.code.not_in(codes)).values(is_active=False, updated_at=now))
        for m in menus:
            self._s.execute(
                insert(Menu)
                .values(
                    id=uuid.uuid4(),
                    key=m.key,
                    scope=m.scope.value,
                    label=m.label,
                    path=m.path,
                    sort_order=m.order,
                    required_permission=m.required_permission,
                    group_key=m.group,
                    created_at=now,
                    updated_at=now,
                )
                .on_conflict_do_update(
                    index_elements=[Menu.key],
                    set_={
                        "scope": m.scope.value,
                        "label": m.label,
                        "path": m.path,
                        "sort_order": m.order,
                        "required_permission": m.required_permission,
                        "group_key": m.group,
                        "updated_at": now,
                    },
                )
            )
        self._s.execute(delete(Menu).where(Menu.key.not_in([m.key for m in menus])))

    def replace_role_mirror(
        self,
        *,
        tenant_id: uuid.UUID | None,
        key: str,
        name: str,
        group_id: str,
        group_path: str,
        permission_codes: set[str],
        synced_at: datetime,
    ) -> uuid.UUID:
        role_id = self._s.execute(
            insert(Role)
            .values(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                key=key,
                name=name,
                keycloak_group_id=group_id,
                keycloak_group_path=group_path,
                synced_at=synced_at,
                created_at=synced_at,
                updated_at=synced_at,
            )
            .on_conflict_do_update(
                constraint="uq_role_group_path",
                set_={"name": name, "keycloak_group_id": group_id, "synced_at": synced_at, "updated_at": synced_at},
            )
            .returning(Role.id)
        ).scalar_one()
        known = set(self._s.execute(select(Permission.code)).scalars())
        self._s.execute(delete(RolePermission).where(RolePermission.role_id == role_id))
        for code in sorted(permission_codes & known):
            self._s.add(RolePermission(role_id=role_id, permission_code=code))
        self._s.flush()
        return role_id

    def delete_roles_not_in(self, group_paths: set[str]) -> None:
        """Drop mirror rows for groups deleted in Keycloak (only those never referenced by membership history)."""
        stale = select(Role.id).where(Role.keycloak_group_path.not_in(group_paths))
        self._s.execute(delete(RolePermission).where(RolePermission.role_id.in_(stale)))
        self._s.execute(
            delete(Role).where(
                Role.id.in_(stale),
                ~Role.id.in_(select(TenantMembership.role_id)),
                ~Role.id.in_(select(PlatformMembership.role_id)),
            )
        )
