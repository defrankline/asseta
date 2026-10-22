"""Mobile push configuration, read only from the environment / `.env`. Key material lives in files outside the
repository (mounted secrets); only their paths are configured.

ASSETA_PUSH_ANDROID_PROVIDER   console (default: logs only) | fcm
ASSETA_PUSH_IOS_PROVIDER       console (default: logs only) | apns
FCM HTTP v1:   ASSETA_PUSH_FCM_SERVICE_ACCOUNT_FILE (Google service-account JSON), ASSETA_PUSH_FCM_PROJECT_ID (optional,
               defaults to the JSON's project_id)
APNs (token):  ASSETA_PUSH_APNS_KEY_FILE (.p8), ASSETA_PUSH_APNS_KEY_ID, ASSETA_PUSH_APNS_TEAM_ID,
               ASSETA_PUSH_APNS_TOPIC (app bundle id), ASSETA_PUSH_APNS_ENVIRONMENT production | sandbox
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class PushSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ASSETA_PUSH_", env_file=".env", extra="ignore")

    android_provider: Literal["console", "fcm"] = "console"
    ios_provider: Literal["console", "apns"] = "console"
    timeout_seconds: float = Field(default=10.0, gt=0, le=60)

    fcm_service_account_file: str = ""
    fcm_project_id: str = ""
    fcm_api_url: str = "https://fcm.googleapis.com"

    apns_key_file: str = ""
    apns_key_id: str = ""
    apns_team_id: str = ""
    apns_topic: str = ""
    apns_environment: Literal["production", "sandbox"] = "production"

    @model_validator(mode="after")
    def _complete(self) -> "PushSettings":
        if self.android_provider == "fcm" and not self.fcm_service_account_file:
            raise ValueError("ASSETA_PUSH_FCM_SERVICE_ACCOUNT_FILE is required when ASSETA_PUSH_ANDROID_PROVIDER=fcm")
        if self.ios_provider == "apns":
            missing = [
                name
                for name, value in (
                    ("ASSETA_PUSH_APNS_KEY_FILE", self.apns_key_file),
                    ("ASSETA_PUSH_APNS_KEY_ID", self.apns_key_id),
                    ("ASSETA_PUSH_APNS_TEAM_ID", self.apns_team_id),
                    ("ASSETA_PUSH_APNS_TOPIC", self.apns_topic),
                )
                if not value
            ]
            if missing:
                raise ValueError(f"{', '.join(missing)} required when ASSETA_PUSH_IOS_PROVIDER=apns")
        return self

    @property
    def apns_url(self) -> str:
        host = "api.sandbox.push.apple.com" if self.apns_environment == "sandbox" else "api.push.apple.com"
        return f"https://{host}"


@lru_cache
def get_push_settings() -> PushSettings:
    return PushSettings()
