"""PUSH/EMAIL endpoints: the signed-in user's push devices (`/api/v1/me/push-devices`, tenant context optional),
category x severity routing preferences and the channel delivery log, for the tenant and platform consoles."""

import hashlib
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.core.audit import AuditService
from asseta.core.clock import get_now
from asseta.core.db import DbScope, apply_scope, get_session
from asseta.core.errors import ERROR_RESPONSES, NotFound, PermissionDenied
from asseta.core.idempotency import IdempotencyGuard, request_hash
from asseta.core.paging import Page, PageParams, page_params, paginate
from asseta.core.push import token_hint
from asseta.modules.identity.dependencies import get_claims
from asseta.modules.identity.principal import RequestContext, TokenClaims
from asseta.modules.identity.repository import IdentityRepository
from asseta.modules.notification import permissions as P
from asseta.modules.notification.channel_dto import (
    NotificationChannelDeliveryDto,
    NotificationRoutingDto,
    NotificationRoutingIn,
    PushDeviceDto,
    PushDeviceIn,
)
from asseta.modules.notification.channel_models import (
    ChannelDeliveryStatus,
    DeviceDeactivation,
    NotificationDelivery,
    PushDevice,
)
from asseta.modules.notification.routing import RoutingService
from asseta.modules.notification.types import Channel

DbSession = Annotated[Session, Depends(get_session)]
Now = Annotated[datetime, Depends(get_now)]


def self_context(
    request: Request,
    claims: Annotated[TokenClaims, Depends(get_claims)],
    session: DbSession,
    x_tenant_id: Annotated[str | None, Header()] = None,
) -> RequestContext:
    """Any signed-in user, for their own rows only. With X-Tenant-ID the full tenant gate applies (membership,
    mandate, access state) and the device is bound to that tenant; without it the request runs in USER scope, where
    RLS exposes nothing but the user's own self-service rows."""
    if x_tenant_id:
        return P.TENANT_SELF(request, claims, session, x_tenant_id)
    user = IdentityRepository(session).upsert_user_from_claims(claims)
    if not user.is_active:
        raise PermissionDenied("User is deactivated", code="USER_INACTIVE")
    apply_scope(session, DbScope.USER, None, user.id)
    session.info["mandate_id"] = None
    return RequestContext(user.id, claims.subject, DbScope.USER, None, frozenset(), frozenset())


Self = Annotated[RequestContext, Depends(self_context)]
me_router = APIRouter(prefix="/api/v1/me/push-devices", tags=["push-devices"], responses=ERROR_RESPONSES)


def _device_dto(d: PushDevice) -> PushDeviceDto:
    return PushDeviceDto(
        id=d.id,
        tenant_id=d.tenant_id,
        platform=d.platform,
        app=d.app,
        token_hint=token_hint(d.token),
        app_version=d.app_version,
        device_label=d.device_label,
        active=d.deactivated_at is None,
        created_at=d.created_at,
        last_registered_at=d.last_registered_at,
        deactivated_at=d.deactivated_at,
        deactivation_reason=d.deactivation_reason,
    )


def _audit(session: Session, ctx: RequestContext, action: str, d: PushDevice) -> None:
    AuditService(session).record(
        actor=ctx.audit_actor(),
        action=action,
        entity_type="push_device",
        entity_id=d.id,
        tenant_id=ctx.tenant_id,
        after={"platform": d.platform.value, "app": d.app.value, "token": token_hint(d.token), "active": True}
        if d.deactivated_at is None
        else {"active": False, "reason": d.deactivation_reason.value if d.deactivation_reason else None},
    )


@me_router.post("", response_model=PushDeviceDto, status_code=201, operation_id="registerPushDevice")
def register_device(
    body: PushDeviceIn,
    session: DbSession,
    now: Now,
    ctx: Self,
    idempotency_key: Annotated[str | None, Header()] = None,
) -> PushDeviceDto:
    """Register (or refresh) this app installation's push token. Re-registering the same token reactivates and
    rebinds the existing device instead of duplicating it."""
    guard = IdempotencyGuard(session, f"user:{ctx.user_id}", "registerPushDevice", idempotency_key, request_hash(body))
    if (replay := guard.begin()) is not None:
        return PushDeviceDto.model_validate(replay)
    digest = hashlib.sha256(body.token.encode()).hexdigest()
    device = session.execute(
        select(PushDevice).where(PushDevice.user_id == ctx.user_id, PushDevice.token_sha256 == digest)
    ).scalar_one_or_none()
    if device is None:
        device = PushDevice(id=uuid.uuid4(), user_id=ctx.user_id, token_sha256=digest, created_at=now)
        session.add(device)
    device.tenant_id, device.platform, device.app, device.token = ctx.tenant_id, body.platform, body.app, body.token
    device.app_version, device.device_label = body.app_version, body.device_label
    device.last_registered_at, device.updated_at = now, now
    device.deactivated_at, device.deactivation_reason = None, None
    session.flush()
    _audit(session, ctx, "notification.push_device.registered", device)
    dto = _device_dto(device)
    guard.complete(dto, 201)
    return dto


@me_router.get("", response_model=Page[PushDeviceDto], operation_id="listMyPushDevices")
def list_devices(
    session: DbSession,
    ctx: Self,
    paging: Annotated[PageParams, Depends(page_params)],
    include_inactive: bool = False,
) -> Page[PushDeviceDto]:
    stmt = (
        select(PushDevice)
        .where(PushDevice.user_id == ctx.user_id)
        .order_by(PushDevice.last_registered_at.desc(), PushDevice.id)
    )
    if not include_inactive:
        stmt = stmt.where(PushDevice.deactivated_at.is_(None))
    rows, total = paginate(session, stmt, paging)
    return Page(items=[_device_dto(d) for d in rows], total=total, page=paging.page, page_size=paging.page_size)


@me_router.delete("/{device_id}", response_model=PushDeviceDto, operation_id="deactivatePushDevice")
def deactivate_device(device_id: uuid.UUID, session: DbSession, now: Now, ctx: Self) -> PushDeviceDto:
    """Stop pushes to this device (sign-out / device removed). The row is kept (deactivated), never deleted."""
    device = session.execute(
        select(PushDevice).where(PushDevice.id == device_id, PushDevice.user_id == ctx.user_id).with_for_update()
    ).scalar_one_or_none()
    if device is None:
        raise NotFound("Push device not found")
    if device.deactivated_at is None:
        device.deactivated_at, device.deactivation_reason, device.updated_at = now, DeviceDeactivation.USER, now
        session.flush()
        _audit(session, ctx, "notification.push_device.deactivated", device)
    return _device_dto(device)


def build_routing_router(
    prefix: str,
    tag: str,
    suffix: str,
    read: Callable[..., RequestContext],
    write: Callable[..., RequestContext],
    manage: Callable[..., RequestContext],
) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=[tag], responses=ERROR_RESPONSES)

    @router.get(
        "/notification-routing",
        response_model=list[NotificationRoutingDto],
        operation_id=f"get{suffix}NotificationRouting",
    )
    def get_routing(
        session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(read)], tenant_default: bool = False
    ) -> list[NotificationRoutingDto]:
        """PUSH/EMAIL per category x severity for the caller (or the tenant default)."""
        return RoutingService(session, ctx, now).routing(tenant_default)

    @router.put(
        "/notification-routing",
        response_model=list[NotificationRoutingDto],
        operation_id=f"update{suffix}NotificationRouting",
    )
    def update_routing(
        body: NotificationRoutingIn, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(write)]
    ) -> list[NotificationRoutingDto]:
        return RoutingService(session, ctx, now).update(body)

    @router.get(
        "/notification-deliveries",
        response_model=Page[NotificationChannelDeliveryDto],
        operation_id=f"list{suffix}NotificationChannelDeliveries",
    )
    def deliveries(
        session: DbSession,
        ctx: Annotated[RequestContext, Depends(manage)],
        paging: Annotated[PageParams, Depends(page_params)],
        channel: Channel | None = None,
        status: ChannelDeliveryStatus | None = None,
    ) -> Page[NotificationChannelDeliveryDto]:
        """PUSH and EMAIL delivery log of this context (SMS has its own log)."""
        own = (
            NotificationDelivery.tenant_id == ctx.tenant_id
            if ctx.tenant_id
            else NotificationDelivery.tenant_id.is_(None)
        )
        stmt = select(NotificationDelivery).where(own)
        if channel is not None:
            stmt = stmt.where(NotificationDelivery.channel == channel.value)
        if status is not None:
            stmt = stmt.where(NotificationDelivery.status == status)
        stmt = stmt.order_by(NotificationDelivery.created_at.desc(), NotificationDelivery.id)
        rows, total = paginate(session, stmt, paging)
        return Page(
            items=[NotificationChannelDeliveryDto.model_validate(d) for d in rows],
            total=total,
            page=paging.page,
            page_size=paging.page_size,
        )

    return router


tenant_router = build_routing_router(
    "/api/v1/tenant", "tenant-notifications", "My", P.TENANT_READ, P.TENANT_SELF, P.TENANT_MANAGE
)
platform_router = build_routing_router(
    "/api/v1/platform", "platform-notifications", "Platform", P.PLATFORM_READ, P.PLATFORM_READ, P.PLATFORM_MANAGE
)
