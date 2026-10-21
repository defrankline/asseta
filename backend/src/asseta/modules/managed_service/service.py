"""Managed-service use cases (DEC-018).

The platform grants a mandate for a client on the client's written consent (the consent reference, e.g. the signed
agreement number); it takes effect at once and the client's administrators see it on their Managed Service page and
can revoke it at any time with a reason. The platform ends it with a reason. Named platform staff are assigned the
client's own Keycloak role groups; the API honours those groups only while the mandate is in force (gate.py), so a
revoked, ended or expired mandate stops access on the very next request even before Keycloak tokens expire.
Every audit event written under a mandate carries its id.
"""

import uuid
from datetime import date

from sqlalchemy import and_, or_, select, text
from sqlalchemy.orm import Session

from asseta.core.audit import AuditActor, AuditEvent, AuditService
from asseta.core.db import utcnow
from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound
from asseta.core.outbox import OutboxWriter
from asseta.modules.identity.authz_sync import AuthzSyncService
from asseta.modules.identity.idp import IdentityProviderAdmin
from asseta.modules.identity.models import AppUser, Role, RolePermission, TenantMembership
from asseta.modules.identity.repository import IdentityRepository
from asseta.modules.identity.tokens import tenant_group_path
from asseta.modules.managed_service.dto import (
    AssignableRoleDto,
    ClientMandateDto,
    MandateActionDto,
    MandateAssignmentDto,
    MandateAssignmentIn,
    MandateCloseIn,
    MandateDetailDto,
    MandateDto,
    MandateGrantIn,
    PlatformStaffDto,
)
from asseta.modules.managed_service.models import (
    ManagedServiceMandate,
    MandateAssignment,
    MandateScope,
    MandateStatus,
    display_status,
)
from asseta.modules.tenancy.models import Tenant

TOPIC = "asseta.platform.managed_service"
# Under an OPERATIONS mandate staff never administer the client's users, roles or mandates.
ADMIN_PREFIXES = ("tenant.access.", "tenant.managed_service.")


class ManagedService:
    def __init__(self, session: Session, actor: AuditActor, idp: IdentityProviderAdmin, today: date):
        self._s, self._actor, self._idp, self._today = session, actor, idp, today

    # --- reads -----------------------------------------------------------------------------------------
    def get(self, mandate_id: uuid.UUID) -> ManagedServiceMandate:
        mandate = self._s.get(ManagedServiceMandate, mandate_id)
        if mandate is None:
            raise NotFound("Mandate not found")
        return mandate

    def list_all(self) -> list[MandateDto]:
        rows = self._s.execute(
            select(ManagedServiceMandate).order_by(ManagedServiceMandate.granted_at.desc())
        ).scalars()
        return [self.to_dto(m) for m in rows]

    def to_dto(self, m: ManagedServiceMandate) -> MandateDto:
        tenant = self._s.get(Tenant, m.tenant_id)
        active = self._assignments(m.id, active_only=True)
        return MandateDto(
            id=m.id,
            reference=m.reference,
            tenant_id=m.tenant_id,
            tenant_name=tenant.display_name if tenant else str(m.tenant_id),
            scope=MandateScope(m.scope),
            starts_on=m.starts_on,
            ends_on=m.ends_on,
            consent_reference=m.consent_reference,
            notes=m.notes,
            status=display_status(m, self._today),
            version=m.version,
            granted_by=self._name(m.granted_by) or "",
            granted_at=m.granted_at,
            closed_by=self._name(m.closed_by),
            closed_at=m.closed_at,
            close_reason=m.close_reason,
            active_staff=len({a.user_id for a in active}),
        )

    def detail(self, m: ManagedServiceMandate) -> MandateDetailDto:
        assignments = []
        for a in self._assignments(m.id, active_only=False):
            user = self._s.get(AppUser, a.user_id)
            assert user is not None
            assignments.append(
                MandateAssignmentDto(
                    id=a.id,
                    user_id=a.user_id,
                    email=user.email,
                    display_name=user.display_name,
                    role_key=a.role_key,
                    is_active=a.is_active,
                    assigned_at=a.created_at,
                    removed_at=a.removed_at,
                )
            )
        return MandateDetailDto(**self.to_dto(m).model_dump(), assignments=assignments)

    def platform_staff(self) -> list[PlatformStaffDto]:
        repo, now, staff = IdentityRepository(self._s), utcnow(), {}
        for group in self._idp.list_role_groups():
            if not group.path.startswith("/platform/"):
                continue
            for member in self._idp.list_group_members(group.group_id):
                uid = repo.upsert_member(member, now)
                staff[uid] = PlatformStaffDto(user_id=uid, email=member.email, display_name=member.display_name)
        return sorted(staff.values(), key=lambda s: s.display_name.lower())

    def assignable_roles(self, m: ManagedServiceMandate) -> list[AssignableRoleDto]:
        roles = []
        for role in self._s.execute(select(Role).where(Role.tenant_id == m.tenant_id).order_by(Role.key)).scalars():
            perms = sorted(
                self._s.execute(
                    select(RolePermission.permission_code).where(RolePermission.role_id == role.id)
                ).scalars()
            )
            if m.scope == MandateScope.OPERATIONS and any(p.startswith(ADMIN_PREFIXES) for p in perms):
                continue
            roles.append(AssignableRoleDto(key=role.key, permissions=perms))
        return roles

    def client_view(self, tenant_id: uuid.UUID) -> ClientMandateDto:
        m = self._s.execute(
            select(ManagedServiceMandate)
            .where(ManagedServiceMandate.tenant_id == tenant_id)
            .order_by(ManagedServiceMandate.granted_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if m is None:
            return ClientMandateDto(mandate=None, recent_actions=[])
        events = self._s.execute(
            select(AuditEvent)
            .where(
                AuditEvent.tenant_id == tenant_id,
                or_(
                    AuditEvent.mandate_id == m.id,  # what staff did under the mandate
                    and_(AuditEvent.entity_type == "managed_service_mandate", AuditEvent.entity_id == str(m.id)),
                ),
            )
            .order_by(AuditEvent.occurred_at.desc())
            .limit(50)
        ).scalars()
        actions = [
            MandateActionDto(
                occurred_at=e.occurred_at,
                actor=self._name(e.actor_user_id) or "system",
                action=e.action,
                entity_type=e.entity_type,
                entity_id=e.entity_id,
            )
            for e in events
        ]
        return ClientMandateDto(mandate=self.detail(m), recent_actions=actions)

    # --- platform: grant / assign / end ----------------------------------------------------------------
    def grant(self, body: MandateGrantIn) -> ManagedServiceMandate:
        if self._s.get(Tenant, body.tenant_id) is None:
            raise NotFound("Client tenant not found")
        open_one = self._s.execute(
            select(ManagedServiceMandate.id).where(
                ManagedServiceMandate.tenant_id == body.tenant_id,
                ManagedServiceMandate.status == MandateStatus.ACTIVE,
            )
        ).first()
        if open_one is not None:
            raise Conflict("This client already has an active mandate", code="MANDATE_ALREADY_ACTIVE")
        number = self._s.execute(text("SELECT nextval('mandate_reference_seq')")).scalar_one()
        assert self._actor.user_id is not None
        m = ManagedServiceMandate(
            id=uuid.uuid4(),
            reference=f"MSM-{self._today.year}-{number:04d}",
            granted_by=self._actor.user_id,
            granted_at=utcnow(),
            status=MandateStatus.ACTIVE,
            version=1,
            **body.model_dump(),
        )
        self._s.add(m)
        self._s.flush()
        self._record(m, "platform.mandate.granted", after=body.model_dump(mode="json"), reason=body.consent_reference)
        self._emit(m, "managed_service.mandate.granted")
        return m

    def assign(self, m: ManagedServiceMandate, body: MandateAssignmentIn) -> MandateAssignment:
        if m.status != MandateStatus.ACTIVE:
            raise BusinessRuleViolation("The mandate is closed", code="MANDATE_CLOSED")
        if body.user_id not in {s.user_id for s in self.platform_staff()}:
            raise BusinessRuleViolation("Only platform staff can be assigned", code="MANDATE_NOT_PLATFORM_STAFF")
        if body.role_key not in {r.key for r in self.assignable_roles(m)}:
            raise BusinessRuleViolation("Role not available under this mandate's scope", code="MANDATE_ROLE_SCOPE")
        path = tenant_group_path(m.tenant_id, body.role_key)
        mine = {a.group_path for a in self._assignments(m.id, active_only=True) if a.user_id == body.user_id}
        if path in mine:
            raise Conflict("Already assigned this role", code="MANDATE_ALREADY_ASSIGNED")
        regular = self._s.execute(
            select(Role.keycloak_group_path)
            .join(TenantMembership, TenantMembership.role_id == Role.id)
            .where(
                TenantMembership.tenant_id == m.tenant_id,
                TenantMembership.user_id == body.user_id,
                TenantMembership.effective_to.is_(None),
            )
        ).scalars()
        if set(regular) - mine:
            # A regular user of the client cannot also act under a mandate: accountability must stay clear.
            raise BusinessRuleViolation("This person is already a user of the client", code="MANDATE_STAFF_IS_MEMBER")
        role = self._role(m.tenant_id, body.role_key)
        user = self._s.get(AppUser, body.user_id)
        assert user is not None and self._actor.user_id is not None
        a = MandateAssignment(
            id=uuid.uuid4(),
            mandate_id=m.id,
            tenant_id=m.tenant_id,
            user_id=body.user_id,
            role_key=body.role_key,
            group_path=path,
            is_active=True,
            assigned_by=self._actor.user_id,
        )
        self._s.add(a)
        self._s.flush()
        self._idp.add_user_to_group(user.keycloak_subject, role.keycloak_group_id)
        AuthzSyncService(self._idp).pull_role_mirror(self._s, only_tenant=m.tenant_id)
        self._record(m, "platform.mandate.assigned", after={"user_id": str(user.id), "role": body.role_key})
        self._emit(m, "managed_service.assignment.added", {"user_id": str(user.id), "role": body.role_key})
        return a

    def unassign(self, m: ManagedServiceMandate, assignment_id: uuid.UUID) -> None:
        a = self._s.get(MandateAssignment, assignment_id)
        if a is None or a.mandate_id != m.id:
            raise NotFound("Assignment not found")
        if not a.is_active:
            raise Conflict("Assignment already removed", code="MANDATE_ASSIGNMENT_REMOVED")
        self._close_assignments(m, [a])
        self._record(m, "platform.mandate.unassigned", after={"user_id": str(a.user_id), "role": a.role_key})
        self._emit(m, "managed_service.assignment.removed", {"user_id": str(a.user_id), "role": a.role_key})

    def end(self, m: ManagedServiceMandate, body: MandateCloseIn) -> None:
        self._close(m, body, MandateStatus.ENDED, "platform.mandate.ended")

    # --- client: revoke --------------------------------------------------------------------------------
    def revoke(self, m: ManagedServiceMandate, body: MandateCloseIn) -> None:
        self._close(m, body, MandateStatus.REVOKED, "platform.mandate.revoked")

    # --- internals -------------------------------------------------------------------------------------
    def _close(self, m: ManagedServiceMandate, body: MandateCloseIn, status: MandateStatus, action: str) -> None:
        if m.version != body.version:
            raise Conflict("The mandate changed; reload and try again", code="STALE_VERSION")
        if m.status != MandateStatus.ACTIVE:
            raise BusinessRuleViolation("The mandate is already closed", code="MANDATE_CLOSED")
        self._close_assignments(m, self._assignments(m.id, active_only=True))
        m.status, m.version = status, m.version + 1
        m.closed_by, m.closed_at, m.close_reason = self._actor.user_id, utcnow(), body.reason
        self._s.flush()
        self._record(m, action, after={"status": status.value}, reason=body.reason)
        self._emit(m, f"managed_service.mandate.{status.value.lower()}", {"reason": body.reason})

    def _close_assignments(self, m: ManagedServiceMandate, rows: list[MandateAssignment]) -> None:
        now = utcnow()
        for a in rows:
            user = self._s.get(AppUser, a.user_id)
            role = self._s.execute(select(Role).where(Role.keycloak_group_path == a.group_path)).scalar_one_or_none()
            if user is not None and role is not None:
                self._idp.remove_user_from_group(user.keycloak_subject, role.keycloak_group_id)
            a.is_active, a.removed_by, a.removed_at = False, self._actor.user_id, now
        self._s.flush()
        if rows:
            AuthzSyncService(self._idp).pull_role_mirror(self._s, only_tenant=m.tenant_id)

    def _assignments(self, mandate_id: uuid.UUID, *, active_only: bool) -> list[MandateAssignment]:
        q = select(MandateAssignment).where(MandateAssignment.mandate_id == mandate_id)
        if active_only:
            q = q.where(MandateAssignment.is_active.is_(True))
        return list(self._s.execute(q.order_by(MandateAssignment.created_at)).scalars())

    def _role(self, tenant_id: uuid.UUID, key: str) -> Role:
        role = self._s.execute(
            select(Role).where(Role.keycloak_group_path == tenant_group_path(tenant_id, key))
        ).scalar_one_or_none()
        if role is None:
            raise NotFound(f"Role '{key}' not found")
        return role

    def _name(self, user_id: uuid.UUID | None) -> str | None:
        user = self._s.get(AppUser, user_id) if user_id else None
        return user.display_name if user else None

    def _record(
        self, m: ManagedServiceMandate, action: str, *, after: dict[str, object], reason: str | None = None
    ) -> None:
        # tenant_id = the client, so both the platform (platform.* actions) and the client can read it.
        AuditService(self._s).record(
            actor=self._actor,
            action=action,
            entity_type="managed_service_mandate",
            entity_id=m.id,
            tenant_id=m.tenant_id,
            after={"reference": m.reference, **after},
            reason=reason,
        )

    def _emit(self, m: ManagedServiceMandate, event_type: str, extra: dict[str, object] | None = None) -> None:
        OutboxWriter(self._s).emit(
            topic=TOPIC,
            event_type=event_type,
            key=str(m.tenant_id),
            payload={"mandate_id": str(m.id), "reference": m.reference, "tenant_id": str(m.tenant_id), **(extra or {})},
            tenant_id=m.tenant_id,
        )
