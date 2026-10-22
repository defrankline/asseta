"""DTOs for PUSH/EMAIL routing preferences, push-device registration and the channel delivery log."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from asseta.modules.notification.channel_models import (
    ChannelDeliveryStatus,
    DeviceApp,
    DeviceDeactivation,
    DevicePlatform,
)
from asseta.modules.notification.types import Category, Channel, Severity


class NotificationRoutingDto(BaseModel):
    """Channels for one category x severity. IN_APP is always on (per-type in-app/SMS stay in /preferences)."""

    category: Category
    severity: Severity
    in_app: bool = True
    push: bool
    email: bool
    mandatory_channels: list[Channel] = Field(description="Channels a notification type in this cell forces on")
    source: str = Field(description="USER | TENANT_DEFAULT | BUILT_IN: where the push/email choice comes from")


class NotificationRoutingChangeIn(BaseModel):
    category: Category
    severity: Severity
    push: bool
    email: bool


class NotificationRoutingIn(BaseModel):
    changes: list[NotificationRoutingChangeIn] = Field(min_length=1, max_length=50)
    tenant_default: bool = Field(
        default=False, description="Tenant-wide default for all users (tenant owner, tenant.notification.manage)"
    )


class PushDeviceIn(BaseModel):
    platform: DevicePlatform
    app: DeviceApp
    token: str = Field(min_length=16, max_length=4096, description="FCM registration token or APNs device token")
    app_version: str | None = Field(default=None, max_length=32)
    device_label: str | None = Field(default=None, max_length=100, description="e.g. 'Pixel 8' (shown to the user)")


class PushDeviceDto(BaseModel):
    """The token itself is never returned; `token_hint` is its last characters."""

    id: uuid.UUID
    tenant_id: uuid.UUID | None = Field(description="Pushes only for this tenant; null = every context of the user")
    platform: DevicePlatform
    app: DeviceApp
    token_hint: str
    app_version: str | None
    device_label: str | None
    active: bool
    created_at: datetime
    last_registered_at: datetime
    deactivated_at: datetime | None
    deactivation_reason: DeviceDeactivation | None


class NotificationChannelDeliveryDto(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    notification_id: uuid.UUID
    tenant_id: uuid.UUID | None
    recipient_user_id: uuid.UUID
    channel: Channel
    push_device_id: uuid.UUID | None
    notification_type: str
    severity: Severity
    status: ChannelDeliveryStatus
    attempts: int
    next_attempt_at: datetime
    last_error: str | None
    provider: str | None
    created_at: datetime
    sent_at: datetime | None
