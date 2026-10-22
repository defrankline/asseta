"""Notification tuning, from the environment (`ASSETA_NOTIFY_*`). SMS provider settings live in `asseta.core.sms`."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class NotificationSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ASSETA_NOTIFY_", env_file=".env", extra="ignore")

    # SMS channel
    quiet_hours_start: int = Field(default=21, ge=0, le=23, description="Local hour quiet hours begin (no SMS)")
    quiet_hours_end: int = Field(default=7, ge=0, le=23, description="Local hour quiet hours end")
    platform_timezone: str = "Africa/Dar_es_Salaam"  # quiet hours for platform staff
    sms_rate_limit_per_hour: int = Field(default=10, ge=1, description="Max SMS per recipient number per hour")
    sms_max_attempts: int = Field(default=5, ge=1, le=20)
    sms_retry_base_seconds: int = Field(default=60, ge=1)
    sms_max_chars: int = Field(default=459, ge=70, le=1530, description="Longer texts are truncated (3 segments)")
    sms_wallet_low_threshold: int = Field(default=50, ge=0)

    # Reminder thresholds
    invoice_due_soon_days: int = Field(default=3, ge=0)
    approval_pending_hours: int = Field(default=24, ge=1)
    cash_handover_cutoff_hour: int = Field(default=19, ge=0, le=23, description="Tenant-local hour")
    job_missing_reading_hours: int = Field(default=4, ge=1)
    restriction_warning_days: int = Field(default=3, ge=0)
    scheduler_interval_seconds: int = Field(default=900, ge=60)
    mirror_refresh_seconds: int = Field(default=3600, ge=300)

    # WebSocket gateway
    ws_heartbeat_seconds: float = Field(default=25.0, gt=0)
    ws_idle_timeout_seconds: float = Field(default=75.0, gt=0)
    ws_auth_timeout_seconds: float = Field(default=10.0, gt=0)
    ws_access_recheck_seconds: float = Field(default=60.0, gt=0)


@lru_cache
def get_notification_settings() -> NotificationSettings:
    return NotificationSettings()
