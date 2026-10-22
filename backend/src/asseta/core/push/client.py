"""Mobile push clients: Firebase Cloud Messaging HTTP v1 (Android), APNs token-based HTTP/2 (iOS) and a console
client for dev/test. A send raises `PushSendError`; `unregistered=True` means the provider says the token will never
work again (uninstalled app, rotated token) and the caller must deactivate the device. Tokens and keys are never
logged — logs carry only a short token hint."""

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import httpx
import jwt
import structlog

from asseta.core.push.settings import PushSettings, get_push_settings

log = structlog.get_logger()
FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
APNS_TOKEN_TTL = 50 * 60  # Apple accepts provider tokens up to 60 min old; refresh well before
APNS_UNREGISTERED = frozenset({"Unregistered", "BadDeviceToken", "DeviceTokenNotForTopic"})


@dataclass(frozen=True)
class PushMessage:
    token: str
    title: str
    body: str
    data: dict[str, str] = field(default_factory=dict)
    high_priority: bool = False
    collapse_key: str | None = None


@dataclass(frozen=True)
class PushSendResult:
    provider: str
    message_id: str | None


class PushSendError(RuntimeError):
    def __init__(
        self, message: str, retryable: bool = True, unregistered: bool = False, status_code: int | None = None
    ):
        super().__init__(message)
        self.retryable = retryable and not unregistered
        self.unregistered = unregistered
        self.status_code = status_code


class PushClient(Protocol):
    def send(self, message: PushMessage, reference: str | None = None) -> PushSendResult: ...


def token_hint(token: str) -> str:
    return f"...{token[-6:]}" if len(token) > 6 else "..."


class ConsolePushClient:
    def __init__(self, name: str = "console"):
        self._name = name

    def send(self, message: PushMessage, reference: str | None = None) -> PushSendResult:
        log.info("push_console", provider=self._name, token=token_hint(message.token), reference=reference)
        return PushSendResult(self._name, reference)


def _json(resp: httpx.Response) -> dict[str, Any]:
    try:
        data = resp.json()
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


class FcmPushClient:
    """FCM HTTP v1 with a service-account OAuth2 token (JWT bearer grant), cached until shortly before expiry."""

    def __init__(
        self,
        settings: PushSettings | None = None,
        http: httpx.Client | None = None,
        clock: Callable[[], float] = time.time,
    ):
        s = settings or get_push_settings()
        account = json.loads(Path(s.fcm_service_account_file).read_text(encoding="utf-8"))
        self._email: str = account["client_email"]
        self._key: str = account["private_key"]
        self._token_uri: str = account.get("token_uri", "https://oauth2.googleapis.com/token")
        self._project = s.fcm_project_id or account["project_id"]
        self._url = f"{s.fcm_api_url}/v1/projects/{self._project}/messages:send"
        self._http = http or httpx.Client(timeout=s.timeout_seconds)
        self._clock = clock
        self._access: tuple[str, float] | None = None

    def _access_token(self) -> str:
        now = self._clock()
        if self._access and self._access[1] - 60 > now:
            return self._access[0]
        claims = {
            "iss": self._email,
            "scope": FCM_SCOPE,
            "aud": self._token_uri,
            "iat": int(now),
            "exp": int(now) + 3600,
        }
        assertion = jwt.encode(claims, self._key, algorithm="RS256")
        try:
            resp = self._http.post(
                self._token_uri,
                data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion},
            )
        except httpx.HTTPError as exc:
            raise PushSendError(f"FCM auth unreachable: {type(exc).__name__}") from None
        if not resp.is_success:
            raise PushSendError(f"FCM auth failed with status {resp.status_code}", resp.status_code >= 500)
        body = _json(resp)
        self._access = (str(body["access_token"]), now + float(body.get("expires_in", 3600)))
        return self._access[0]

    def send(self, message: PushMessage, reference: str | None = None) -> PushSendResult:
        android: dict[str, Any] = {"priority": "HIGH" if message.high_priority else "NORMAL"}
        if message.collapse_key:
            android["collapse_key"] = message.collapse_key
        payload = {
            "message": {
                "token": message.token,
                "notification": {"title": message.title, "body": message.body},
                "data": message.data,
                "android": android,
            }
        }
        headers = {"Authorization": f"Bearer {self._access_token()}"}
        try:
            resp = self._http.post(self._url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise PushSendError(f"FCM unreachable: {type(exc).__name__}") from None
        if resp.is_success:
            log.info("push_sent", provider="fcm", token=token_hint(message.token), reference=reference)
            return PushSendResult("fcm", str(_json(resp).get("name") or "") or None)
        error = _json(resp).get("error") or {}
        codes = {d.get("errorCode") for d in error.get("details") or [] if isinstance(d, dict)}
        status = str(error.get("status") or "")
        if resp.status_code == 401:
            self._access = None  # stale OAuth token: refreshed on the retry
        unregistered = "UNREGISTERED" in codes or resp.status_code == 404 or status == "NOT_FOUND"
        retryable = resp.status_code in (401, 429) or resp.status_code >= 500
        raise PushSendError(
            f"FCM rejected the message: {status or resp.status_code}", retryable, unregistered, resp.status_code
        )


class ApnsPushClient:
    """APNs provider-token (ES256 .p8) over HTTP/2; the delivery id is sent as `apns-id`."""

    def __init__(
        self,
        settings: PushSettings | None = None,
        http: httpx.Client | None = None,
        clock: Callable[[], float] = time.time,
    ):
        s = settings or get_push_settings()
        self._s = s
        self._key = Path(s.apns_key_file).read_text(encoding="utf-8")
        self._http = http or httpx.Client(http2=True, timeout=s.timeout_seconds)
        self._clock = clock
        self._jwt: tuple[str, float] | None = None

    def _provider_token(self) -> str:
        now = self._clock()
        if self._jwt and now - self._jwt[1] < APNS_TOKEN_TTL:
            return self._jwt[0]
        token = jwt.encode(
            {"iss": self._s.apns_team_id, "iat": int(now)},
            self._key,
            algorithm="ES256",
            headers={"kid": self._s.apns_key_id},
        )
        self._jwt = (token, now)
        return token

    def send(self, message: PushMessage, reference: str | None = None) -> PushSendResult:
        headers = {
            "authorization": f"bearer {self._provider_token()}",
            "apns-topic": self._s.apns_topic,
            "apns-push-type": "alert",
            "apns-priority": "10" if message.high_priority else "5",
        }
        if reference:
            headers["apns-id"] = reference
        if message.collapse_key:
            headers["apns-collapse-id"] = message.collapse_key[:64]
        payload: dict[str, Any] = {
            "aps": {"alert": {"title": message.title, "body": message.body}, "sound": "default"},
            **message.data,
        }
        try:
            resp = self._http.post(f"{self._s.apns_url}/3/device/{message.token}", json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise PushSendError(f"APNs unreachable: {type(exc).__name__}") from None
        if resp.is_success:
            log.info("push_sent", provider="apns", token=token_hint(message.token), reference=reference)
            return PushSendResult("apns", resp.headers.get("apns-id", reference))
        reason = str(_json(resp).get("reason") or resp.status_code)
        if reason in ("ExpiredProviderToken", "InvalidProviderToken"):
            self._jwt = None
        unregistered = resp.status_code == 410 or reason in APNS_UNREGISTERED
        retryable = resp.status_code in (429, 500, 503) or reason == "ExpiredProviderToken"
        raise PushSendError(f"APNs rejected the message: {reason}", retryable, unregistered, resp.status_code)


class PushRouter:
    """Picks the client for a device platform (ANDROID -> FCM/console, IOS -> APNs/console)."""

    def __init__(self, android: PushClient, ios: PushClient):
        self._clients = {"ANDROID": android, "IOS": ios}

    def for_platform(self, platform: str) -> PushClient:
        return self._clients[platform]


def build_push_router(settings: PushSettings | None = None) -> PushRouter:
    s = settings or get_push_settings()
    android: PushClient = FcmPushClient(s) if s.android_provider == "fcm" else ConsolePushClient("console-android")
    ios: PushClient = ApnsPushClient(s) if s.ios_provider == "apns" else ConsolePushClient("console-ios")
    return PushRouter(android, ios)
