"""Safety of the OVERSIGHT.managed_service_enabled switch (DEC-018, DEC-032): the switch hides only the tenant's own
page and must never become a way to hide a mandate from the tenant that granted it. It cannot be turned off while the
tenant has an open mandate, and a platform actor working under a mandate cannot change it at all."""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from asseta.core.errors import BusinessRuleViolation, PermissionDenied
from asseta.modules.identity.principal import RequestContext
from asseta.modules.managed_service.models import ManagedServiceMandate, MandateStatus
from asseta.modules.policy.schemas import OversightPolicy, PolicyType
from asseta.modules.policy.service import PolicyService


def _open_mandate(session: Session, tenant_id: uuid.UUID, today: date) -> bool:
    """A mandate still in force or scheduled to start: ACTIVE and not past its end date (RLS: the tenant's own)."""
    return (
        session.execute(
            select(ManagedServiceMandate.id)
            .where(
                ManagedServiceMandate.tenant_id == tenant_id,
                ManagedServiceMandate.status == MandateStatus.ACTIVE,
                or_(ManagedServiceMandate.ends_on.is_(None), ManagedServiceMandate.ends_on >= today),
            )
            .limit(1)
        ).first()
        is not None
    )


def has_open_mandate(session: Session, tenant_id: uuid.UUID, at: datetime) -> bool:
    return _open_mandate(session, tenant_id, at.date())


def guard_managed_service_switch(session: Session, ctx: RequestContext, values: dict[str, Any], today: date) -> None:
    """Refuse a tenant OVERSIGHT version that would change the switch against the rules above. Omitting the key means
    the platform default, so a version can change the switch without naming it."""
    assert ctx.tenant_id is not None
    svc = PolicyService(session)
    current = svc.oversight(ctx.tenant_id).policy.managed_service_enabled
    platform = svc.resolve(PolicyType.OVERSIGHT, None).policy
    assert isinstance(platform, OversightPolicy)
    desired = bool(values.get("managed_service_enabled", platform.managed_service_enabled))
    if desired == current:
        return
    if ctx.mandate_id is not None:
        raise PermissionDenied(
            "Staff working under a mandate cannot change the managed service switch",
            code="MANAGED_SERVICE_SWITCH_LOCKED",
        )
    if not desired and _open_mandate(session, ctx.tenant_id, today):
        raise BusinessRuleViolation(
            "End the managed-service mandate before switching its page off", code="MANAGED_SERVICE_MANDATE_ACTIVE"
        )
