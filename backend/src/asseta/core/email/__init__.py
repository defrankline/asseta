"""Reusable outbound e-mail utility (console by default; SMTP when ASSETA_EMAIL_PROVIDER=smtp)."""

from asseta.core.email.client import (
    ConsoleEmailClient,
    EmailClient,
    EmailSendError,
    EmailSendResult,
    OutboundEmail,
    SmtpEmailClient,
    build_email_client,
    mask_address,
)
from asseta.core.email.settings import EmailSettings, get_email_settings

__all__ = [
    "ConsoleEmailClient",
    "EmailClient",
    "EmailSendError",
    "EmailSendResult",
    "EmailSettings",
    "OutboundEmail",
    "SmtpEmailClient",
    "build_email_client",
    "get_email_settings",
    "mask_address",
]
