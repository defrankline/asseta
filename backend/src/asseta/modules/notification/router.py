"""Notification REST API, mirrored for the tenant context (`/api/v1/tenant/notifications`, X-Tenant-ID) and the
platform console (`/api/v1/platform/notifications`). The WebSocket gateway lives in `gateway.py`."""

import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlalchemy.orm import Session

from asseta.core.clock import get_now
from asseta.core.db import get_session
from asseta.core.errors import ERROR_RESPONSES
from asseta.core.paging import Page, PageParams, page_params
from asseta.core.sms import SmsClient
from asseta.modules.identity.principal import RequestContext
from asseta.modules.notification import permissions as P
from asseta.modules.notification.dto import (
    NotificationDto,
    NotificationMarkReadIn,
    NotificationMarkReadResultDto,
    NotificationPreferenceDto,
    NotificationPreferencesIn,
    NotificationProfileDto,
    NotificationProfileIn,
    NotificationTestSendIn,
    NotificationTestSendResultDto,
    NotificationUnreadCountDto,
    SmsDeliveryDto,
)
from asseta.modules.notification.models import DeliveryStatus
from asseta.modules.notification.realtime import SafePublisher, user_channel
from asseta.modules.notification.service import NotificationService
from asseta.modules.notification.types import Severity

DbSession = Annotated[Session, Depends(get_session)]
Now = Annotated[datetime, Depends(get_now)]


def _push_unread(request: Request, background: BackgroundTasks, ctx: RequestContext, count: int) -> None:
    """Other tabs/devices of the same user update their badge (after the transaction commits)."""
    publisher = SafePublisher(getattr(request.app.state, "realtime", None))
    message = {"type": "unread_count", "payload": {"count": count}}
    background.add_task(publisher.publish, user_channel(ctx.user_id, ctx.tenant_id), message)


def build_router(
    prefix: str,
    tag: str,
    suffix: str,
    read: Callable[..., RequestContext],
    write: Callable[..., RequestContext],
    manage: Callable[..., RequestContext],
) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=[tag], responses=ERROR_RESPONSES)

    @router.get("", response_model=Page[NotificationDto], operation_id=f"list{suffix}Notifications")
    def list_notifications(
        session: DbSession,
        now: Now,
        ctx: Annotated[RequestContext, Depends(read)],
        paging: Annotated[PageParams, Depends(page_params)],
        unread_only: bool = False,
        severity: Severity | None = None,
    ) -> Page[NotificationDto]:
        return NotificationService(session, ctx, now).inbox(paging, unread_only, severity)

    @router.get("/unread-count", response_model=NotificationUnreadCountDto, operation_id=f"get{suffix}UnreadCount")
    def unread(
        session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(read)]
    ) -> NotificationUnreadCountDto:
        return NotificationUnreadCountDto(count=NotificationService(session, ctx, now).unread())

    @router.get(
        "/preferences",
        response_model=list[NotificationPreferenceDto],
        operation_id=f"get{suffix}NotificationPreferences",
    )
    def preferences(
        session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(read)], tenant_default: bool = False
    ) -> list[NotificationPreferenceDto]:
        return NotificationService(session, ctx, now).preferences(tenant_default)

    @router.put(
        "/preferences",
        response_model=list[NotificationPreferenceDto],
        operation_id=f"update{suffix}NotificationPreferences",
    )
    def update_preferences(
        body: NotificationPreferencesIn, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(write)]
    ) -> list[NotificationPreferenceDto]:
        return NotificationService(session, ctx, now).update_preferences(body)

    @router.get("/profile", response_model=NotificationProfileDto, operation_id=f"get{suffix}NotificationProfile")
    def profile(session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(read)]) -> NotificationProfileDto:
        return NotificationService(session, ctx, now).profile()

    @router.put("/profile", response_model=NotificationProfileDto, operation_id=f"update{suffix}NotificationProfile")
    def update_profile(
        body: NotificationProfileIn, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(write)]
    ) -> NotificationProfileDto:
        return NotificationService(session, ctx, now).update_profile(body.msisdn)

    @router.post("/read", response_model=NotificationMarkReadResultDto, operation_id=f"mark{suffix}NotificationsRead")
    def mark_read(
        body: NotificationMarkReadIn,
        request: Request,
        background: BackgroundTasks,
        session: DbSession,
        now: Now,
        ctx: Annotated[RequestContext, Depends(write)],
    ) -> NotificationMarkReadResultDto:
        result = NotificationService(session, ctx, now).mark_read(body.ids)
        _push_unread(request, background, ctx, result.unread)
        return result

    @router.post(
        "/read-all", response_model=NotificationMarkReadResultDto, operation_id=f"markAll{suffix}NotificationsRead"
    )
    def mark_all_read(
        request: Request,
        background: BackgroundTasks,
        session: DbSession,
        now: Now,
        ctx: Annotated[RequestContext, Depends(write)],
    ) -> NotificationMarkReadResultDto:
        result = NotificationService(session, ctx, now).mark_read(None)
        _push_unread(request, background, ctx, result.unread)
        return result

    @router.get("/deliveries", response_model=Page[SmsDeliveryDto], operation_id=f"list{suffix}SmsDeliveries")
    def deliveries(
        session: DbSession,
        now: Now,
        ctx: Annotated[RequestContext, Depends(manage)],
        paging: Annotated[PageParams, Depends(page_params)],
        status: DeliveryStatus | None = None,
    ) -> Page[SmsDeliveryDto]:
        return NotificationService(session, ctx, now).deliveries(paging, status)

    @router.get("/{notification_id}", response_model=NotificationDto, operation_id=f"get{suffix}Notification")
    def get_notification(
        notification_id: uuid.UUID, session: DbSession, now: Now, ctx: Annotated[RequestContext, Depends(read)]
    ) -> NotificationDto:
        return NotificationService(session, ctx, now).get(notification_id)

    return router


tenant_router = build_router(
    "/api/v1/tenant/notifications", "tenant-notifications", "My", P.TENANT_READ, P.TENANT_SELF, P.TENANT_MANAGE
)
platform_router = build_router(
    "/api/v1/platform/notifications",
    "platform-notifications",
    "Platform",
    P.PLATFORM_READ,
    P.PLATFORM_READ,
    P.PLATFORM_MANAGE,
)


@platform_router.post(
    "/test-send", response_model=NotificationTestSendResultDto, operation_id="testSendPlatformNotification"
)
def test_send(
    body: NotificationTestSendIn,
    request: Request,
    background: BackgroundTasks,
    session: DbSession,
    now: Now,
    ctx: Annotated[RequestContext, Depends(P.PLATFORM_MANAGE)],
) -> NotificationTestSendResultDto:
    client: SmsClient = request.app.state.sms_client
    result = NotificationService(session, ctx, now).test_send(body, client)
    publisher = SafePublisher(getattr(request.app.state, "realtime", None))
    message = {"type": "notification", "payload": result.notification.model_dump(mode="json")}
    background.add_task(publisher.publish, user_channel(ctx.user_id, None), message)
    return result
