"""SMS clients. `NextSmsClient` mirrors the NextSMS "text/single" API:

    POST {ASSETA_NEXTSMS_URL}
    Authorization: Basic <base64(username:password)>
    {"from": <sender id>, "to": ["2557...", ...], "text": <message>, "reference": <our id>}

Recipients are normalised and sent in batches; any non-2xx response raises `SmsSendError` (callers decide on retry).
The credential never appears in logs, exceptions or results.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx
import structlog

from asseta.core.sms.msisdn import normalize_msisdn
from asseta.core.sms.settings import SmsSettings, get_sms_settings

log = structlog.get_logger()


@dataclass(frozen=True)
class SmsSendResult:
    provider: str
    recipients: tuple[str, ...]
    reference: str | None
    responses: tuple[dict[str, Any], ...] = field(default_factory=tuple)


class SmsSendError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, retryable: bool = True):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


class SmsClient(Protocol):
    def send(self, recipients: Sequence[str], message: str, reference: str | None = None) -> SmsSendResult: ...


def _prepare(settings: SmsSettings, recipients: Sequence[str], message: str) -> tuple[str, ...]:
    if not message.strip():
        raise ValueError("SMS text is empty")
    normalised = tuple(dict.fromkeys(normalize_msisdn(r, settings.sms_default_country_code) for r in recipients))
    if not normalised:
        raise ValueError("No SMS recipients")
    return normalised


class ConsoleSmsClient:
    """Development/test client: logs the message (masked numbers) and sends nothing."""

    def __init__(self, settings: SmsSettings | None = None):
        self._settings = settings or get_sms_settings()

    def send(self, recipients: Sequence[str], message: str, reference: str | None = None) -> SmsSendResult:
        to = _prepare(self._settings, recipients, message)
        log.info("sms_console", to=[f"{n[:5]}****{n[-2:]}" for n in to], chars=len(message), reference=reference)
        return SmsSendResult("console", to, reference)


class NextSmsClient:
    def __init__(self, settings: SmsSettings | None = None, http: httpx.Client | None = None):
        self._settings = settings or get_sms_settings()
        self._http = http or httpx.Client(timeout=self._settings.sms_timeout_seconds)

    def send(self, recipients: Sequence[str], message: str, reference: str | None = None) -> SmsSendResult:
        s = self._settings
        to = _prepare(s, recipients, message)
        headers = {
            "Authorization": s.nextsms_authorization(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        size = s.sms_max_recipients_per_request
        responses: list[dict[str, Any]] = []
        for start in range(0, len(to), size):
            body: dict[str, Any] = {"from": s.nextsms_sender_id, "to": list(to[start : start + size]), "text": message}
            if reference is not None:
                body["reference"] = reference
            try:
                resp = self._http.post(s.nextsms_url, json=body, headers=headers)
            except httpx.HTTPError as exc:
                raise SmsSendError(f"SMS gateway unreachable: {type(exc).__name__}") from None
            if not resp.is_success:
                # 4xx (bad sender/credentials/number) won't succeed on retry; 429/5xx may.
                retryable = resp.status_code == 429 or resp.status_code >= 500
                raise SmsSendError(
                    f"SMS gateway request failed with status {resp.status_code}", resp.status_code, retryable
                )
            responses.append(_json_or_empty(resp))
        log.info("sms_sent", provider="nextsms", recipients=len(to), reference=reference)
        return SmsSendResult("nextsms", to, reference, tuple(responses))


def _json_or_empty(resp: httpx.Response) -> dict[str, Any]:
    try:
        data = resp.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {"data": data}


def build_sms_client(settings: SmsSettings | None = None) -> SmsClient:
    s = settings or get_sms_settings()
    return NextSmsClient(s) if s.sms_provider == "nextsms" else ConsoleSmsClient(s)
