"""Audience resolution from the Keycloak-synced mirrors (DEC-005): open tenant/platform memberships -> role groups
-> permissions. Mandate-aware (DEC-018): a user governed by managed-service mandates in a tenant counts only through
role groups an in-force mandate assigns them, exactly like the request-time gate. Always confined to one tenant."""

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.modules.fleet.models import StaffMember
from asseta.modules.identity.models import AppUser, PlatformMembership, Role, RolePermission, TenantMembership
from asseta.modules.managed_service.gate import active_grant, has_assignment_history


@dataclass(frozen=True)
class Recipient:
    user_id: uuid.UUID
    via_mandate: bool = False  # platform staff acting for the tenant: their SMS is never tenant-billed


class Directory:
    """Run in SYSTEM scope (mirror + mandate tables); every query is filtered by the event's tenant."""

    def __init__(self, session: Session, today: date):
        self._s, self._today = session, today
        self._cache: dict[uuid.UUID, dict[uuid.UUID, tuple[frozenset[str], bool]]] = {}

    def _members(self, tenant_id: uuid.UUID) -> dict[uuid.UUID, tuple[frozenset[str], bool]]:
        """user -> (effective role-group paths, via mandate)."""
        if tenant_id in self._cache:
            return self._cache[tenant_id]
        rows = self._s.execute(
            select(TenantMembership.user_id, Role.keycloak_group_path)
            .join(Role, Role.id == TenantMembership.role_id)
            .join(AppUser, AppUser.id == TenantMembership.user_id)
            .where(
                TenantMembership.tenant_id == tenant_id,
                TenantMembership.effective_to.is_(None),
                AppUser.is_active.is_(True),
            )
        ).all()
        paths: dict[uuid.UUID, set[str]] = defaultdict(set)
        for user_id, path in rows:
            paths[user_id].add(path)
        out: dict[uuid.UUID, tuple[frozenset[str], bool]] = {}
        for user_id, groups in paths.items():
            if has_assignment_history(self._s, tenant_id, user_id):
                grant = active_grant(self._s, tenant_id, user_id, self._today)
                kept = frozenset(groups & grant.group_paths) if grant else frozenset()
                if kept:
                    out[user_id] = (kept, True)
            else:
                out[user_id] = (frozenset(groups), False)
        self._cache[tenant_id] = out
        return out

    def _granting_paths(self, permission: str) -> set[str]:
        return set(
            self._s.execute(
                select(Role.keycloak_group_path)
                .join(RolePermission, RolePermission.role_id == Role.id)
                .where(RolePermission.permission_code == permission)
            ).scalars()
        )

    def tenant_permission(self, tenant_id: uuid.UUID, permission: str) -> list[Recipient]:
        granting = self._granting_paths(permission)
        return [
            Recipient(uid, mandate)
            for uid, (paths, mandate) in sorted(self._members(tenant_id).items())
            if paths & granting
        ]

    def tenant_role(self, tenant_id: uuid.UUID, role_key: str) -> list[Recipient]:
        suffix = f"/tenants/{tenant_id}/{role_key}"
        return [Recipient(uid, m) for uid, (paths, m) in sorted(self._members(tenant_id).items()) if suffix in paths]

    def tenant_user(self, tenant_id: uuid.UUID, user_id: uuid.UUID | None) -> list[Recipient]:
        member = self._members(tenant_id).get(user_id) if user_id else None
        return [Recipient(user_id, member[1])] if user_id and member else []

    def tenant_staff(self, tenant_id: uuid.UUID, staff_member_id: uuid.UUID | None) -> list[Recipient]:
        """The person behind a supervisor/operator record (linked login), if still a member of this tenant."""
        if staff_member_id is None:
            return []
        subject = self._s.execute(
            select(StaffMember.keycloak_subject).where(
                StaffMember.id == staff_member_id, StaffMember.tenant_id == tenant_id
            )
        ).scalar_one_or_none()
        if not subject:
            return []
        user_id = self._s.execute(select(AppUser.id).where(AppUser.keycloak_subject == subject)).scalar_one_or_none()
        return self.tenant_user(tenant_id, user_id)

    def platform_permission(self, permission: str) -> list[Recipient]:
        granting = self._granting_paths(permission)
        rows = self._s.execute(
            select(PlatformMembership.user_id)
            .join(Role, Role.id == PlatformMembership.role_id)
            .join(AppUser, AppUser.id == PlatformMembership.user_id)
            .where(
                PlatformMembership.effective_to.is_(None),
                AppUser.is_active.is_(True),
                Role.tenant_id.is_(None),
                Role.keycloak_group_path.in_(granting),
            )
            .distinct()
        ).scalars()
        return [Recipient(uid) for uid in sorted(rows)]
