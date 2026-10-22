"""E-mail configuration, read only from the environment / `.env` (never hard-coded or committed).

ASSETA_EMAIL_PROVIDER        console (default: logs only, sends nothing) | smtp
ASSETA_EMAIL_FROM            sender address, e.g. "Asseta <notifications@example.com>"
ASSETA_EMAIL_SMTP_HOST / ASSETA_EMAIL_SMTP_PORT
ASSETA_EMAIL_SMTP_USERNAME / ASSETA_EMAIL_SMTP_PASSWORD   optional (no AUTH when the username is empty)
ASSETA_EMAIL_SMTP_SECURITY   starttls (default) | ssl (implicit TLS, usually port 465) | none (local relay/Mailpit)
ASSETA_EMAIL_TIMEOUT_SECONDS
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class EmailSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ASSETA_EMAIL_", env_file=".env", extra="ignore")

    provider: Literal["console", "smtp"] = "console"
    from_address: str = Field(default="Asseta <no-reply@asseta.local>", validation_alias="ASSETA_EMAIL_FROM")
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_security: Literal["starttls", "ssl", "none"] = "starttls"
    timeout_seconds: float = Field(default=15.0, gt=0, le=120)

    @model_validator(mode="after")
    def _smtp_complete(self) -> "EmailSettings":
        if self.provider == "smtp" and not self.smtp_host:
            raise ValueError("ASSETA_EMAIL_SMTP_HOST is required when ASSETA_EMAIL_PROVIDER=smtp")
        return self


@lru_cache
def get_email_settings() -> EmailSettings:
    return EmailSettings()
