"""Shared finance helpers: tenant base currency/timezone, staff resolution, tenant-local day bounds."""

import uuid
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from asseta.core.errors import BusinessRuleViolation, Conflict, NotFound, PermissionDenied
from asseta.modules.fleet.models import StaffMember
from asseta.modules.identity.principal import RequestContext
from asseta.modules.platform_billing.models_commercial import Currency
from asseta.modules.tenancy.models import TenantSettings

ZERO = Decimal(0)


def tenant_settings(session: Session, tenant_id: uuid.UUID) -> TenantSettings:
    settings = session.get(TenantSettings, tenant_id)
    assert settings is not None
    return settings


def currency_or_default(session: Session, tenant_id: uuid.UUID, code: str | None) -> str:
    code = code or tenant_settings(session, tenant_id).currency
    if session.get(Currency, code) is None:
        raise BusinessRuleViolation(f"Currency {code} is not configured", code="CURRENCY_NOT_CONFIGURED")
    return code


def resolve_staff(
    session: Session, ctx: RequestContext, staff_id: uuid.UUID | None, require_active: bool = True
) -> StaffMember:
    """The named staff member (RLS-scoped) or the caller's own linked staff record."""
    if staff_id is not None:
        staff = session.get(StaffMember, staff_id)
        if staff is None:
            raise NotFound("Staff member not found")
    else:
        staff = session.execute(
            select(StaffMember).where(StaffMember.keycloak_subject == ctx.subject)
        ).scalar_one_or_none()
        if staff is None:
            raise BusinessRuleViolation("Your login is not linked to a staff record", code="STAFF_NOT_LINKED")
    if require_active and not staff.is_active:
        raise BusinessRuleViolation("Staff member is inactive", code="STAFF_INACTIVE")
    return staff


OFFICE_CASH_PERMISSION = "tenant.finance.cash"


def resolve_custodian(session: Session, ctx: RequestContext, staff_id: uuid.UUID | None) -> StaffMember:
    """Whose cash custody a movement affects. Field users can only move their own custody; naming another staff
    member requires the office cash permission."""
    if staff_id is None or OFFICE_CASH_PERMISSION in ctx.permissions:
        return resolve_staff(session, ctx, staff_id)
    own = resolve_staff(session, ctx, None)
    if own.id != staff_id:
        raise PermissionDenied("Only office cash staff may record custody for someone else", code="NOT_CUSTODIAN")
    return own


def insert(session: Session, obj: Any, code: str, msg: str) -> None:
    try:
        with session.begin_nested():
            session.add(obj)
            session.flush()
    except IntegrityError as exc:
        raise Conflict(msg, code=code) from exc


def local_bounds(tz_name: str, first: date, last: date) -> tuple[datetime, datetime]:
    """[start of `first`, start of the day after `last`) in tenant local time, as UTC instants."""
    if last < first:
        raise BusinessRuleViolation("Period end is before its start", code="INVALID_PERIOD")
    if (last - first).days > 366:
        raise BusinessRuleViolation("Period is limited to 366 days", code="PERIOD_TOO_LONG")
    tz = ZoneInfo(tz_name)
    start = datetime.combine(first, time.min, tz).astimezone(UTC)
    end = datetime.combine(last + timedelta(days=1), time.min, tz).astimezone(UTC)
    return start, end


def local_date(tz_name: str, instant: datetime) -> date:
    return instant.astimezone(ZoneInfo(tz_name)).date()
