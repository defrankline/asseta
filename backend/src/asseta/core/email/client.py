"""Outbound e-mail: provider-agnostic interface, an SMTP client (stdlib `smtplib`) and a console client for dev/test.

Errors raise `EmailSendError(retryable=...)`: connection problems and SMTP 4xx replies are retryable, 5xx replies
(bad recipient, rejected sender, auth failure) are not. Credentials never appear in logs, exceptions or results.
"""

import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import make_msgid
from typing import Protocol

import structlog

from asseta.core.email.settings import EmailSettings, get_email_settings

log = structlog.get_logger()


@dataclass(frozen=True)
class OutboundEmail:
    to: str
    subject: str
    text: str


@dataclass(frozen=True)
class EmailSendResult:
    provider: str
    message_id: str | None


class EmailSendError(RuntimeError):
    def __init__(self, message: str, retryable: bool = True, smtp_code: int | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.smtp_code = smtp_code


class EmailClient(Protocol):
    def send(self, message: OutboundEmail, reference: str | None = None) -> EmailSendResult: ...


def mask_address(address: str) -> str:
    local, _, domain = address.partition("@")
    return f"{local[:2]}***@{domain}" if domain else "***"


def _validate(message: OutboundEmail) -> None:
    if "@" not in message.to or any(c in message.to for c in "\r\n"):
        raise EmailSendError("Invalid recipient address", retryable=False)
    if any(c in message.subject for c in "\r\n"):
        raise EmailSendError("Subject must be a single line", retryable=False)


class ConsoleEmailClient:
    """Development/test client: logs a masked recipient and the subject length; sends nothing."""

    def send(self, message: OutboundEmail, reference: str | None = None) -> EmailSendResult:
        _validate(message)
        log.info("email_console", to=mask_address(message.to), subject_chars=len(message.subject), reference=reference)
        return EmailSendResult("console", None)


class SmtpEmailClient:
    def __init__(self, settings: EmailSettings | None = None):
        self._s = settings or get_email_settings()

    def _connect(self) -> smtplib.SMTP:
        s = self._s
        if s.smtp_security == "ssl":
            return smtplib.SMTP_SSL(
                s.smtp_host, s.smtp_port, timeout=s.timeout_seconds, context=ssl.create_default_context()
            )
        conn = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=s.timeout_seconds)
        if s.smtp_security == "starttls":
            conn.starttls(context=ssl.create_default_context())
        return conn

    def send(self, message: OutboundEmail, reference: str | None = None) -> EmailSendResult:
        _validate(message)
        s = self._s
        msg = EmailMessage()
        msg["From"] = s.from_address
        msg["To"] = message.to
        msg["Subject"] = message.subject
        msg["Message-ID"] = make_msgid(idstring=reference, domain=s.from_address.rpartition("@")[2].strip(">") or None)
        if reference:
            msg["X-Asseta-Reference"] = reference
        msg.set_content(message.text)
        try:
            with self._connect() as conn:
                if s.smtp_username:
                    conn.login(s.smtp_username, s.smtp_password.get_secret_value())
                conn.send_message(msg)
        except smtplib.SMTPRecipientsRefused as exc:
            codes = [code for code, _ in exc.recipients.values()]
            transient = all(400 <= c < 500 for c in codes)
            raise EmailSendError(
                "Recipient refused by the mail server", transient, codes[0] if codes else None
            ) from None
        except smtplib.SMTPResponseException as exc:
            raise EmailSendError(
                f"Mail server replied {exc.smtp_code}", 400 <= exc.smtp_code < 500, exc.smtp_code
            ) from None
        except (smtplib.SMTPException, OSError) as exc:
            raise EmailSendError(f"Mail server unreachable: {type(exc).__name__}") from None
        log.info("email_sent", provider="smtp", to=mask_address(message.to), reference=reference)
        return EmailSendResult("smtp", str(msg["Message-ID"]))


def build_email_client(settings: EmailSettings | None = None) -> EmailClient:
    s = settings or get_email_settings()
    return SmtpEmailClient(s) if s.provider == "smtp" else ConsoleEmailClient()
