"""SMS configuration, read only from the environment / `.env` (never hard-coded).

ASSETA_SMS_PROVIDER         console (default: logs only, sends nothing) | nextsms
ASSETA_NEXTSMS_URL          NextSMS send endpoint
ASSETA_NEXTSMS_SENDER_ID    approved sender name (e.g. registered with NextSMS)
ASSETA_NEXTSMS_USERNAME / ASSETA_NEXTSMS_PASSWORD   account credentials, or
ASSETA_NEXTSMS_AUTH_TOKEN   the pre-encoded Basic token (base64 of "username:password") instead
ASSETA_SMS_DEFAULT_COUNTRY_CODE   used to normalise local numbers (255 = Tanzania)
"""

import base64
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SmsSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ASSETA_", env_file=".env", extra="ignore")

    sms_provider: Literal["console", "nextsms"] = "console"
    sms_default_country_code: str = Field(default="255", pattern=r"^[1-9]\d{0,2}$")
    sms_timeout_seconds: float = Field(default=15.0, gt=0, le=120)
    sms_max_recipients_per_request: int = Field(default=100, ge=1, le=1000)

    nextsms_url: str = "https://messaging-service.co.tz/api/sms/v1/text/single"
    nextsms_sender_id: str = ""
    nextsms_username: str = ""
    nextsms_password: SecretStr = SecretStr("")
    nextsms_auth_token: SecretStr = SecretStr("")

    @model_validator(mode="after")
    def _nextsms_complete(self) -> "SmsSettings":
        if self.sms_provider == "nextsms":
            if not self.nextsms_sender_id:
                raise ValueError("ASSETA_NEXTSMS_SENDER_ID is required when ASSETA_SMS_PROVIDER=nextsms")
            has_pair = bool(self.nextsms_username and self.nextsms_password.get_secret_value())
            if not has_pair and not self.nextsms_auth_token.get_secret_value():
                raise ValueError(
                    "Set ASSETA_NEXTSMS_USERNAME + ASSETA_NEXTSMS_PASSWORD or ASSETA_NEXTSMS_AUTH_TOKEN "
                    "when ASSETA_SMS_PROVIDER=nextsms"
                )
        return self

    def nextsms_authorization(self) -> str:
        """Value of the `Authorization` header (HTTP Basic)."""
        token = self.nextsms_auth_token.get_secret_value()
        if not token:
            raw = f"{self.nextsms_username}:{self.nextsms_password.get_secret_value()}".encode()
            token = base64.b64encode(raw).decode()
        return f"Basic {token}"


@lru_cache
def get_sms_settings() -> SmsSettings:
    return SmsSettings()
