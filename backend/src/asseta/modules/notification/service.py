"""Inbox, preferences, profile, delivery log and test-send for the signed-in user in the current context (a tenant via
X-Tenant-ID, or the platform console). RLS confines every row to the recipient and context as well."""

import uuid
from datetime import datetime

from sqlalchemy import Select, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from asseta.core.errors import BusinessRuleViolation, NotFound, PermissionDenied
from asseta.core.paging import Page, PageParams, paginate
from asseta.core.search import ilike_any
from asseta.core.sms import InvalidMsisdn, SmsClient, SmsSendError, get_sms_settings, normalize_msisdn
from asseta.modules.identity.principal import RequestContext
from asseta.modules.notification.dto import (
    NotificationDto,
    NotificationMarkReadResultDto,
    NotificationPreferenceDto,
    NotificationPreferencesIn,
    NotificationProfileDto,
    NotificationTestSendIn,
    NotificationTestSendResultDto,
    SmsDeliveryDto,
    to_dto,
)
from asseta.modules.notification.engine import effective_channels, scope_key, unread_count
from asseta.modules.notification.models import (
    DeliveryStatus,
    Notification,
    NotificationPreference,
    NotificationProfile,
    SmsDelivery,
)
from asseta.modules.notification.segments import sms_segments
from asseta.modules.notification.types import TYPES, Channel, Context, Severity

MANAGE = "tenant.notification.manage"


class NotificationService:
    def __init__(self, session: Session, ctx: RequestContext, now: datetime):
        self._s, self._ctx, self._now = session, ctx, now
        self._tid = ctx.tenant_id
        self._context = Context.TENANT if ctx.tenant_id else Context.PLATFORM

    def _mine(self) -> Select[Notification]:
        where = Notification.tenant_id == self._tid if self._tid else Notification.tenant_id.is_(None)
        return select(Notification).where(
            Notification.recipient_user_id == self._ctx.user_id, where, Notification.in_app.is_(True)
        )

    # --- inbox ------------------------------------------------------------------------------------------------
    def inbox(self, paging: PageParams, unread_only: bool, severity: Severity | None) -> Page[NotificationDto]:
        stmt = self._mine().order_by(Notification.created_at.desc(), Notification.id)
        if unread_only:
            stmt = stmt.where(Notification.read_at.is_(None))
        if severity is not None:
            stmt = stmt.where(Notification.severity == severity)
        if (cond := ilike_any(paging.q, Notification.title, Notification.body)) is not None:
            stmt = stmt.where(cond)
        rows, total = paginate(self._s, stmt, paging)
        return Page(items=[to_dto(n) for n in rows], total=total, page=paging.page, page_size=paging.page_size)

    def get(self, notification_id: uuid.UUID) -> NotificationDto:
        row = self._s.execute(self._mine().where(Notification.id == notification_id)).scalar_one_or_none()
        if row is None:
            raise NotFound("Notification not found")
        return to_dto(row)

    def unread(self) -> int:
        return unread_count(self._s, self._ctx.user_id, self._tid)

    def mark_read(self, ids: list[uuid.UUID] | None) -> NotificationMarkReadResultDto:
        where = Notification.tenant_id == self._tid if self._tid else Notification.tenant_id.is_(None)
        stmt = update(Notification).where(
            Notification.recipient_user_id == self._ctx.user_id, where, Notification.read_at.is_(None)
        )
        if ids is not None:
            stmt = stmt.where(Notification.id.in_(ids))
        updated = len(self._s.execute(stmt.values(read_at=self._now).returning(Notification.id)).scalars().all())
        return NotificationMarkReadResultDto(updated=updated, unread=self.unread())

    # --- preferences ------------------------------------------------------------------------------------------
    def preferences(self, tenant_default: bool = False) -> list[NotificationPreferenceDto]:
        if tenant_default:
            self._require_manage()
        out = []
        for t in TYPES.values():
            if self._context not in t.contexts:
                continue
            if tenant_default:
                row = self._default_row(t.code)
                in_app = row.in_app if row else True
                sms = row.sms if row else (t.sms_default and not t.low_priority)
                in_app, sms = in_app or Channel.IN_APP in t.mandatory, sms or Channel.SMS in t.mandatory
            else:
                ch = effective_channels(self._s, self._ctx.user_id, self._tid, t)
                in_app, sms = ch.in_app, ch.sms and (not t.low_priority or ch.sms_opted_in)
            out.append(
                NotificationPreferenceDto(
                    type=t.code,
                    label=t.label,
                    description=f"{t.category.value.title()} · default severity {t.severity.value}",
                    category=t.category.value,
                    in_app=in_app,
                    sms=sms,
                    mandatory=bool(t.mandatory),
                    sms_available=True,
                    mandatory_channels=sorted(c.value for c in t.mandatory),
                    low_priority=t.low_priority,
                )
            )
        return out

    def _require_manage(self) -> None:
        if self._tid is None:
            raise BusinessRuleViolation("Tenant defaults exist only in a tenant", code="TENANT_REQUIRED")
        if MANAGE not in self._ctx.permissions:
            raise PermissionDenied(f"Missing permission {MANAGE}")

    def _default_row(self, code: str) -> NotificationPreference | None:
        return self._s.execute(
            select(NotificationPreference).where(
                NotificationPreference.scope_key == scope_key(self._tid),
                NotificationPreference.user_id.is_(None),
                NotificationPreference.notification_type == code,
            )
        ).scalar_one_or_none()

    def update_preferences(self, body: NotificationPreferencesIn) -> list[NotificationPreferenceDto]:
        if body.tenant_default:
            self._require_manage()
        for change in body.changes:
            t = TYPES.get(change.type)
            if t is None or self._context not in t.contexts:
                raise BusinessRuleViolation(f"Unknown notification type {change.type}", code="UNKNOWN_TYPE")
            if (Channel.IN_APP in t.mandatory and not change.in_app) or (Channel.SMS in t.mandatory and not change.sms):
                raise BusinessRuleViolation(
                    f"{t.label}: mandatory channels cannot be disabled", code="MANDATORY_CHANNEL"
                )
            values = {
                "id": uuid.uuid4(),
                "scope_key": scope_key(self._tid),
                "tenant_id": self._tid,
                "user_id": None if body.tenant_default else self._ctx.user_id,
                "notification_type": t.code,
                "in_app": change.in_app,
                "sms": change.sms,
                "updated_by": self._ctx.user_id,
                "updated_at": self._now,
            }
            index = (
                ["scope_key", "notification_type"]
                if body.tenant_default
                else ["scope_key", "user_id", "notification_type"]
            )
            where = (
                NotificationPreference.user_id.is_(None)
                if body.tenant_default
                else (NotificationPreference.user_id.is_not(None))
            )
            self._s.execute(
                insert(NotificationPreference)
                .values(**values)
                .on_conflict_do_update(
                    index_elements=index,
                    index_where=where,
                    set_={
                        "in_app": change.in_app,
                        "sms": change.sms,
                        "updated_by": self._ctx.user_id,
                        "updated_at": self._now,
                    },
                )
            )
        return self.preferences(body.tenant_default)

    # --- profile ----------------------------------------------------------------------------------------------
    def profile(self) -> NotificationProfileDto:
        row = self._s.get(NotificationProfile, self._ctx.user_id)
        return NotificationProfileDto(user_id=self._ctx.user_id, msisdn=row.msisdn if row else None)

    def update_profile(self, msisdn: str | None) -> NotificationProfileDto:
        normalized = None
        if msisdn:
            try:
                normalized = normalize_msisdn(msisdn, get_sms_settings().sms_default_country_code)
            except InvalidMsisdn as exc:
                raise BusinessRuleViolation(str(exc), code="INVALID_MSISDN") from exc
        self._s.execute(
            insert(NotificationProfile)
            .values(user_id=self._ctx.user_id, msisdn=normalized, updated_at=self._now)
            .on_conflict_do_update(index_elements=["user_id"], set_={"msisdn": normalized, "updated_at": self._now})
        )
        return self.profile()

    # --- delivery log / test --------------------------------------------------------------------------------
    def deliveries(self, paging: PageParams, status: DeliveryStatus | None) -> Page[SmsDeliveryDto]:
        where = SmsDelivery.tenant_id == self._tid if self._tid else SmsDelivery.tenant_id.is_(None)
        stmt = select(SmsDelivery).where(where).order_by(SmsDelivery.created_at.desc(), SmsDelivery.id)
        if status is not None:
            stmt = stmt.where(SmsDelivery.status == status)
        rows, total = paginate(self._s, stmt, paging)
        return Page(
            items=[SmsDeliveryDto.model_validate(d) for d in rows],
            total=total,
            page=paging.page,
            page_size=paging.page_size,
        )

    def test_send(self, body: NotificationTestSendIn, client: SmsClient) -> NotificationTestSendResultDto:
        """Platform console: in-app (+ WebSocket) to the caller, and an immediate SMS (never tenant-billed)."""
        n = Notification(
            id=uuid.uuid4(),
            tenant_id=None,
            recipient_user_id=self._ctx.user_id,
            notification_type="SYSTEM_TEST",
            category=TYPES["SYSTEM_TEST"].category.value,
            severity=Severity.INFO,
            title=body.title,
            body=body.body,
            link="/notifications",
            entity_type=None,
            entity_id=None,
            data={},
            in_app=True,
            dedupe_key=f"test:{uuid.uuid4()}",
            created_at=self._now,
        )
        self._s.add(n)
        self._s.flush()
        delivery = None
        if body.msisdn:
            try:
                msisdn = normalize_msisdn(body.msisdn, get_sms_settings().sms_default_country_code)
            except InvalidMsisdn as exc:
                raise BusinessRuleViolation(str(exc), code="INVALID_MSISDN") from exc
            text = f"Asseta: {body.title}. {body.body}"
            delivery = SmsDelivery(
                id=uuid.uuid4(),
                notification_id=n.id,
                tenant_id=None,
                recipient_user_id=self._ctx.user_id,
                notification_type="SYSTEM_TEST",
                severity=Severity.INFO,
                msisdn=msisdn,
                text=text,
                segments=sms_segments(text)[0],
                billable=False,
                status=DeliveryStatus.PENDING,
                attempts=1,
                next_attempt_at=self._now,
                created_at=self._now,
                updated_at=self._now,
            )
            try:
                result = client.send([msisdn], text, reference=str(delivery.id))
                delivery.status, delivery.provider, delivery.sent_at = DeliveryStatus.SENT, result.provider, self._now
            except SmsSendError as exc:
                delivery.status, delivery.last_error = DeliveryStatus.FAILED, str(exc)[:500]
            self._s.add(delivery)
            self._s.flush()
        return NotificationTestSendResultDto(
            notification=to_dto(n), delivery=SmsDeliveryDto.model_validate(delivery) if delivery else None
        )
