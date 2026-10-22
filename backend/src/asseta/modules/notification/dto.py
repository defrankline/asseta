"""Notification API DTOs (shared by REST and the WebSocket `notification` message)."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from asseta.modules.notification.models import DeliveryStatus, Notification
from asseta.modules.notification.types import Severity

NotificationPriority = Literal["NORMAL", "HIGH"]


class NotificationTarget(BaseModel):
    """The screen to act on: `path` is a console route; `entity`/`id` identify the record."""

    entity: str
    id: str | None
    path: str | None


class NotificationDto(BaseModel):
    id: uuid.UUID
    type: str
    category: str
    severity: Severity
    priority: NotificationPriority
    title: str
    body: str
    created_at: datetime
    read_at: datetime | None
    target: NotificationTarget | None
    tenant_id: uuid.UUID | None
    data: dict[str, Any]


def to_dto(n: Notification) -> NotificationDto:
    target = None
    if n.link or n.entity_type:
        target = NotificationTarget(entity=n.entity_type or "screen", id=n.entity_id, path=n.link)
    return NotificationDto(
        id=n.id,
        type=n.notification_type,
        category=n.category,
        severity=n.severity,
        priority="HIGH" if n.severity is not Severity.INFO else "NORMAL",
        title=n.title,
        body=n.body,
        created_at=n.created_at,
        read_at=n.read_at,
        target=target,
        tenant_id=n.tenant_id,
        data=n.data or {},
    )


def notification_dto(n: Notification) -> dict[str, Any]:
    """JSON-ready form for real-time messages."""
    return to_dto(n).model_dump(mode="json")


class NotificationUnreadCountDto(BaseModel):
    count: int


class NotificationMarkReadIn(BaseModel):
    ids: list[uuid.UUID] = Field(min_length=1, max_length=200)


class NotificationMarkReadResultDto(BaseModel):
    updated: int
    unread: int


class NotificationPreferenceDto(BaseModel):
    type: str
    label: str
    description: str
    category: str
    in_app: bool
    sms: bool
    mandatory: bool
    sms_available: bool
    mandatory_channels: list[str]
    low_priority: bool


class NotificationPreferenceChangeIn(BaseModel):
    type: str = Field(max_length=48)
    in_app: bool
    sms: bool


class NotificationPreferencesIn(BaseModel):
    changes: list[NotificationPreferenceChangeIn] = Field(min_length=1, max_length=100)
    tenant_default: bool = Field(
        default=False, description="Tenant-wide default for all users (tenant owner, tenant.notification.manage)"
    )


class NotificationProfileDto(BaseModel):
    user_id: uuid.UUID
    msisdn: str | None


class NotificationProfileIn(BaseModel):
    msisdn: str | None = Field(default=None, max_length=32, description="Phone for SMS; any common TZ/E.164 form")


class SmsDeliveryDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    notification_id: uuid.UUID | None
    tenant_id: uuid.UUID | None
    notification_type: str
    msisdn: str
    segments: int
    billable: bool
    status: DeliveryStatus
    attempts: int
    next_attempt_at: datetime
    last_error: str | None
    provider: str | None
    created_at: datetime
    sent_at: datetime | None


class NotificationTestSendIn(BaseModel):
    msisdn: str | None = Field(default=None, max_length=32, description="Also send an SMS to this number")
    title: str = Field(default="Asseta test notification", min_length=1, max_length=120)
    body: str = Field(default="If you can read this, notifications reach you.", min_length=1, max_length=300)


class NotificationTestSendResultDto(BaseModel):
    notification: NotificationDto
    delivery: SmsDeliveryDto | None
