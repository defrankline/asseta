"""Request-time mandate gate. A user is *mandate-governed* in a tenant when they are platform staff or have ever
held a mandate assignment there; such a user's Keycloak tenant groups count only while an in-force mandate assigns
them. Called on every tenant-scoped request, inside the tenant's RLS scope."""

import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.modules.managed_service.models import ManagedServiceMandate, MandateAssignment, MandateScope, in_force


@dataclass(frozen=True)
class MandateGrant:
    mandate_id: uuid.UUID
    reference: str
    scope: MandateScope
    ends_on: date | None
    group_paths: frozenset[str]


def has_assignment_history(session: Session, tenant_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    return (
        session.execute(
            select(MandateAssignment.id)
            .where(MandateAssignment.tenant_id == tenant_id, MandateAssignment.user_id == user_id)
            .limit(1)
        ).first()
        is not None
    )


def active_grant(session: Session, tenant_id: uuid.UUID, user_id: uuid.UUID, today: date) -> MandateGrant | None:
    rows = session.execute(
        select(ManagedServiceMandate, MandateAssignment.group_path)
        .join(MandateAssignment, MandateAssignment.mandate_id == ManagedServiceMandate.id)
        .where(
            ManagedServiceMandate.tenant_id == tenant_id,
            MandateAssignment.user_id == user_id,
            MandateAssignment.is_active.is_(True),
        )
    ).all()
    live = [(m, path) for m, path in rows if in_force(m, today)]
    if not live:
        return None
    mandate = live[0][0]
    return MandateGrant(
        mandate.id, mandate.reference, MandateScope(mandate.scope), mandate.ends_on, frozenset(p for _, p in live)
    )


def grants_for_user(session: Session, user_id: uuid.UUID, today: date) -> dict[uuid.UUID, MandateGrant]:
    """All in-force grants for a user across tenants (platform scope only: mandates are platform records)."""
    rows = session.execute(
        select(ManagedServiceMandate, MandateAssignment.group_path)
        .join(MandateAssignment, MandateAssignment.mandate_id == ManagedServiceMandate.id)
        .where(MandateAssignment.user_id == user_id, MandateAssignment.is_active.is_(True))
    ).all()
    paths: dict[uuid.UUID, set[str]] = {}
    mandates: dict[uuid.UUID, ManagedServiceMandate] = {}
    for m, path in rows:
        if in_force(m, today):
            paths.setdefault(m.tenant_id, set()).add(path)
            mandates[m.tenant_id] = m
    return {
        tid: MandateGrant(m.id, m.reference, MandateScope(m.scope), m.ends_on, frozenset(paths[tid]))
        for tid, m in mandates.items()
    }
