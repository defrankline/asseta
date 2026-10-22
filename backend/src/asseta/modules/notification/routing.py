"""Priority routing for the optional channels: which of PUSH and EMAIL a notification reaches, chosen per category x
severity ("configurable priority notifications" for owner apps). Resolution: the user's own row > the tenant default
(set with tenant.notification.manage) > the built-in default below. A channel a notification type declares mandatory
is forced on at delivery and cannot be switched off for the cell holding that type (422 MANDATORY_CHANNEL)."""

import uuid
from datetime import datetime

from sqlalchemy import ColumnElement, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.errors import BusinessRuleViolation, PermissionDenied
from asseta.modules.identity.principal import RequestContext
from asseta.modules.notification.channel_dto import NotificationRoutingDto, NotificationRoutingIn
from asseta.modules.notification.channel_models import NotificationRouting
from asseta.modules.notification.types import TYPES, Category, Channel, Context, Severity

MANAGE = "tenant.notification.manage"
OPTIONAL = (Channel.PUSH, Channel.EMAIL)


def scope_key(tenant_id: uuid.UUID | None) -> str:
    return str(tenant_id) if tenant_id else "platform"


def built_in(category: Category | str, severity: Severity) -> tuple[bool, bool]:
    """(push, email): push for anything to act on or above INFO; e-mail only for CRITICAL."""
    push = severity is not Severity.INFO or category == Category.ACTION
    return push, severity is Severity.CRITICAL


def mandatory_in_cell(category: Category | str, severity: Severity, context: Context | None = None) -> set[Channel]:
    return {
        c
        for t in TYPES.values()
        if t.category == category and t.severity is severity and (context is None or context in t.contexts)
        for c in t.mandatory
        if c in OPTIONAL
    }


def resolve(
    session: Session, user_id: uuid.UUID | None, tenant_id: uuid.UUID | None, category: str, severity: Severity
) -> tuple[bool, bool, str]:
    """(push, email, source) before mandatory channels are applied. `user_id` None reads the tenant default."""
    who: ColumnElement[bool] = NotificationRouting.user_id.is_(None)
    if user_id is not None:
        who = or_(NotificationRouting.user_id == user_id, NotificationRouting.user_id.is_(None))
    rows = session.execute(
        select(NotificationRouting).where(
            NotificationRouting.scope_key == scope_key(tenant_id),
            NotificationRouting.category == category,
            NotificationRouting.severity == severity,
            who,
        )
    ).scalars()
    by_user = {r.user_id is not None: r for r in rows}
    if (row := by_user.get(True)) is not None:
        return row.push, row.email, "USER"
    if (row := by_user.get(False)) is not None:
        return row.push, row.email, "TENANT_DEFAULT"
    push, email = built_in(category, severity)
    return push, email, "BUILT_IN"


class RoutingService:
    def __init__(self, session: Session, ctx: RequestContext, now: datetime):
        self._s, self._ctx, self._now, self._tid = session, ctx, now, ctx.tenant_id
        self._context = Context.TENANT if ctx.tenant_id else Context.PLATFORM

    def _require_manage(self) -> None:
        if self._tid is None:
            raise BusinessRuleViolation("Tenant defaults exist only in a tenant", code="TENANT_REQUIRED")
        if MANAGE not in self._ctx.permissions:
            raise PermissionDenied(f"Missing permission {MANAGE}")

    def routing(self, tenant_default: bool = False) -> list[NotificationRoutingDto]:
        if tenant_default:
            self._require_manage()
        user = None if tenant_default else self._ctx.user_id
        out = []
        for category in Category:
            for severity in Severity:
                push, email, source = resolve(self._s, user, self._tid, category.value, severity)
                forced = mandatory_in_cell(category, severity, self._context)
                out.append(
                    NotificationRoutingDto(
                        category=category,
                        severity=severity,
                        push=push or Channel.PUSH in forced,
                        email=email or Channel.EMAIL in forced,
                        mandatory_channels=sorted(forced),
                        source=source,
                    )
                )
        return out

    def update(self, body: NotificationRoutingIn) -> list[NotificationRoutingDto]:
        if body.tenant_default:
            self._require_manage()
        for change in body.changes:
            forced = mandatory_in_cell(change.category, change.severity, self._context)
            if (Channel.PUSH in forced and not change.push) or (Channel.EMAIL in forced and not change.email):
                raise BusinessRuleViolation(
                    f"{change.category.value}/{change.severity.value}: mandatory channels cannot be disabled",
                    code="MANDATORY_CHANNEL",
                )
            user_id = None if body.tenant_default else self._ctx.user_id
            index = ["scope_key", "category", "severity"]
            if user_id is not None:
                index.insert(1, "user_id")
            self._s.execute(
                insert(NotificationRouting)
                .values(
                    id=uuid.uuid4(),
                    scope_key=scope_key(self._tid),
                    tenant_id=self._tid,
                    user_id=user_id,
                    category=change.category.value,
                    severity=change.severity,
                    push=change.push,
                    email=change.email,
                    updated_by=self._ctx.user_id,
                    updated_at=self._now,
                )
                .on_conflict_do_update(
                    index_elements=index,
                    index_where=(
                        NotificationRouting.user_id.is_(None)
                        if user_id is None
                        else NotificationRouting.user_id.is_not(None)
                    ),
                    set_={
                        "push": change.push,
                        "email": change.email,
                        "updated_by": self._ctx.user_id,
                        "updated_at": self._now,
                    },
                )
            )
        AuditService(self._s).record(
            actor=self._ctx.audit_actor(),
            action=f"{'' if self._tid else 'platform.'}notification.routing.updated",
            entity_type="notification_routing",
            entity_id="tenant-default" if body.tenant_default else str(self._ctx.user_id),
            tenant_id=self._tid,
            after={"changes": [c.model_dump(mode="json") for c in body.changes]},
        )
        return self.routing(body.tenant_default)
