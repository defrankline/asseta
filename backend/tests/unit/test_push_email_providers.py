"""Gate 7 provider adapters without any external network: console clients only log; SMTP against an in-process
fake server (real smtplib protocol); FCM HTTP v1 and APNs through mocked httpx transports, including token caching,
signed credentials and "unregistered token" detection."""

import json
import smtplib
import time
from email import message_from_string
from pathlib import Path
from typing import Any

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from pydantic import ValidationError
from structlog.testing import capture_logs

from asseta.core.email import (
    ConsoleEmailClient,
    EmailSendError,
    EmailSettings,
    OutboundEmail,
    SmtpEmailClient,
    build_email_client,
)
from asseta.core.push import (
    ApnsPushClient,
    ConsolePushClient,
    FcmPushClient,
    PushMessage,
    PushSendError,
    PushSettings,
    build_push_router,
)
from tests.support.fake_smtp import FakeSmtpServer

TOKEN = "fcm-registration-token-0123456789abcdef"
MESSAGE = PushMessage(TOKEN, "Machine offline", "EXC-001 stopped reporting", {"type": "TRACKING_ALERT"}, True, "T")


# --- console -----------------------------------------------------------------------------------------------------
def test_console_clients_only_log_masked_targets() -> None:
    with capture_logs() as logs:
        assert ConsoleEmailClient().send(OutboundEmail("owner@hire.example.com", "Hi", "Body"), "ref-1").provider == (
            "console"
        )
        assert ConsolePushClient().send(MESSAGE, "ref-2").provider == "console"
    rendered = json.dumps(logs)
    assert "owner@hire.example.com" not in rendered and TOKEN not in rendered
    assert [entry["event"] for entry in logs] == ["email_console", "push_console"]
    assert isinstance(build_email_client(EmailSettings()), ConsoleEmailClient)  # code default is console
    router = build_push_router(PushSettings())
    assert isinstance(router.for_platform("ANDROID"), ConsolePushClient)
    assert isinstance(router.for_platform("IOS"), ConsolePushClient)


def test_provider_settings_require_explicit_config() -> None:
    with pytest.raises(ValidationError, match="ASSETA_EMAIL_SMTP_HOST"):
        EmailSettings(provider="smtp")
    with pytest.raises(ValidationError, match="ASSETA_PUSH_FCM_SERVICE_ACCOUNT_FILE"):
        PushSettings(android_provider="fcm")
    with pytest.raises(ValidationError, match="ASSETA_PUSH_APNS_KEY_ID"):
        PushSettings(ios_provider="apns", apns_key_file="/x.p8", apns_team_id="T", apns_topic="t")


# --- SMTP --------------------------------------------------------------------------------------------------------
def _smtp(port: int) -> SmtpEmailClient:
    return SmtpEmailClient(
        EmailSettings(
            provider="smtp",
            smtp_host="127.0.0.1",
            smtp_port=port,
            smtp_security="none",
            ASSETA_EMAIL_FROM="Asseta <notify@asseta.test>",
            timeout_seconds=5,
        )
    )


def test_smtp_sends_a_real_protocol_message() -> None:
    with FakeSmtpServer() as server:
        result = _smtp(server.port).send(
            OutboundEmail("owner@hire.example.com", "Asseta: Invoice overdue", "Pay soon.\nThanks"), "delivery-1"
        )
    assert result.provider == "smtp" and result.message_id and "delivery-1" in result.message_id
    [got] = server.state.messages
    assert got.rcpt_to == ["owner@hire.example.com"] and got.mail_from == "notify@asseta.test"
    msg = message_from_string(got.data)
    assert msg["Subject"] == "Asseta: Invoice overdue" and msg["X-Asseta-Reference"] == "delivery-1"
    assert "Pay soon." in msg.get_payload()


def test_smtp_errors_are_classified() -> None:
    with FakeSmtpServer() as server:
        client = _smtp(server.port)
        server.state.reject_rcpt["gone@hire.example.com"] = "550 5.1.1 no such user"
        with pytest.raises(EmailSendError) as permanent:
            client.send(OutboundEmail("gone@hire.example.com", "s", "b"))
        assert permanent.value.retryable is False and permanent.value.smtp_code == 550
        server.state.fail_data.append("451 4.3.0 try again later")
        with pytest.raises(EmailSendError) as transient:
            client.send(OutboundEmail("owner@hire.example.com", "s", "b"))
        assert transient.value.retryable is True and transient.value.smtp_code == 451
        assert server.state.messages == []
    with pytest.raises(EmailSendError) as down:  # server gone: connection refused
        client.send(OutboundEmail("owner@hire.example.com", "s", "b"))
    assert down.value.retryable is True
    with pytest.raises(EmailSendError, match="Invalid recipient"):
        client.send(OutboundEmail("owner@hire.example.com\r\nBcc: x@y", "s", "b"))
    assert issubclass(smtplib.SMTPRecipientsRefused, smtplib.SMTPException)


# --- FCM ---------------------------------------------------------------------------------------------------------
@pytest.fixture
def service_account(tmp_path: Path) -> tuple[Path, rsa.RSAPrivateKey]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    path = tmp_path / "sa.json"
    path.write_text(
        json.dumps(
            {
                "type": "service_account",
                "project_id": "asseta-test",
                "client_email": "push@asseta-test.iam.gserviceaccount.com",
                "private_key": pem.decode(),
                "token_uri": "https://oauth2.test/token",
            }
        )
    )
    return path, key


class FcmFake:
    def __init__(self, key: rsa.RSAPrivateKey):
        self.key, self.token_requests = key, 0
        self.sends: list[tuple[str, dict[str, Any]]] = []
        self.responses: list[httpx.Response] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.host == "oauth2.test":
            self.token_requests += 1
            form = dict(x.split("=", 1) for x in request.content.decode().split("&"))
            claims = jwt.decode(
                form["assertion"],
                self.key.public_key(),
                algorithms=["RS256"],
                audience="https://oauth2.test/token",
            )
            assert claims["scope"] == "https://www.googleapis.com/auth/firebase.messaging"
            return httpx.Response(200, json={"access_token": f"at-{self.token_requests}", "expires_in": 3600})
        assert request.url.path == "/v1/projects/asseta-test/messages:send"
        self.sends.append((request.headers["authorization"], json.loads(request.content)))
        return self.responses.pop(0) if self.responses else httpx.Response(200, json={"name": "projects/x/m/1"})


def _fcm(path: Path, fake: FcmFake) -> FcmPushClient:
    settings = PushSettings(android_provider="fcm", fcm_service_account_file=str(path), fcm_api_url="https://fcm.test")
    return FcmPushClient(settings, httpx.Client(transport=httpx.MockTransport(fake)), clock=time.time)


def test_fcm_v1_send_with_cached_oauth_token(service_account: tuple[Path, Any]) -> None:
    path, key = service_account
    fake = FcmFake(key)
    client = _fcm(path, fake)
    assert client.send(MESSAGE, "d-1").message_id == "projects/x/m/1"
    client.send(MESSAGE, "d-2")
    assert fake.token_requests == 1  # OAuth token cached until shortly before expiry
    auth, body = fake.sends[0]
    assert auth == "Bearer at-1"
    msg = body["message"]
    assert msg["token"] == TOKEN and msg["notification"] == {
        "title": "Machine offline",
        "body": "EXC-001 stopped reporting",
    }
    assert msg["android"] == {"priority": "HIGH", "collapse_key": "T"} and msg["data"] == {"type": "TRACKING_ALERT"}


def test_fcm_unregistered_retryable_and_auth_refresh(service_account: tuple[Path, Any]) -> None:
    path, key = service_account
    fake = FcmFake(key)
    client = _fcm(path, fake)
    unregistered = {
        "error": {
            "code": 404,
            "status": "NOT_FOUND",
            "details": [{"@type": "type.googleapis.com/google.firebase.fcm.v1.FcmError", "errorCode": "UNREGISTERED"}],
        }
    }
    fake.responses = [
        httpx.Response(404, json=unregistered),
        httpx.Response(503, json={"error": {"status": "UNAVAILABLE"}}),
        httpx.Response(401, json={"error": {"status": "UNAUTHENTICATED"}}),
        httpx.Response(400, json={"error": {"status": "INVALID_ARGUMENT"}}),
    ]
    with pytest.raises(PushSendError) as gone:
        client.send(MESSAGE)
    assert gone.value.unregistered and not gone.value.retryable
    with pytest.raises(PushSendError) as busy:
        client.send(MESSAGE)
    assert busy.value.retryable and not busy.value.unregistered
    with pytest.raises(PushSendError) as stale:
        client.send(MESSAGE)
    assert stale.value.retryable
    with pytest.raises(PushSendError) as bad:
        client.send(MESSAGE)
    assert not bad.value.retryable and not bad.value.unregistered
    assert fake.token_requests == 2  # the 401 dropped the cached OAuth token


# --- APNs --------------------------------------------------------------------------------------------------------
@pytest.fixture
def apns_key(tmp_path: Path) -> tuple[Path, ec.EllipticCurvePrivateKey]:
    key = ec.generate_private_key(ec.SECP256R1())
    path = tmp_path / "AuthKey_ABC123.p8"
    path.write_bytes(
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    return path, key


def _apns(path: Path, handler: Any, now: list[float]) -> ApnsPushClient:
    settings = PushSettings(
        ios_provider="apns",
        apns_key_file=str(path),
        apns_key_id="ABC123",
        apns_team_id="TEAM42",
        apns_topic="com.asseta.owner",
        apns_supervisor_topic="com.asseta.supervisor",
        apns_environment="sandbox",
    )
    return ApnsPushClient(settings, httpx.Client(transport=httpx.MockTransport(handler)), clock=lambda: now[0])


def test_apns_token_auth_request_and_errors(apns_key: tuple[Path, Any]) -> None:
    path, key = apns_key
    seen: list[httpx.Request] = []
    replies = [
        httpx.Response(200, headers={"apns-id": "d-1"}),
        httpx.Response(410, json={"reason": "Unregistered", "timestamp": 1}),
        httpx.Response(400, json={"reason": "BadDeviceToken"}),
        httpx.Response(429, json={"reason": "TooManyRequests"}),
        httpx.Response(403, json={"reason": "ExpiredProviderToken"}),
        httpx.Response(200),
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return replies.pop(0)

    now = [time.time()]
    client = _apns(path, handler, now)
    ios = PushMessage("a1b2c3d4" * 8, "Approval waiting", "Expense TZS 120,000", {"link": "/tenant/approvals"})
    assert client.send(ios, "d-1").message_id == "d-1"
    first = seen[0]
    assert str(first.url) == f"https://api.sandbox.push.apple.com/3/device/{'a1b2c3d4' * 8}"
    assert first.headers["apns-topic"] == "com.asseta.owner" and first.headers["apns-id"] == "d-1"
    assert first.headers["apns-push-type"] == "alert" and first.headers["apns-priority"] == "5"
    bearer = first.headers["authorization"].removeprefix("bearer ")
    assert jwt.get_unverified_header(bearer)["kid"] == "ABC123"
    assert jwt.decode(bearer, key.public_key(), algorithms=["ES256"])["iss"] == "TEAM42"
    body = json.loads(first.content)
    assert body["aps"]["alert"] == {"title": "Approval waiting", "body": "Expense TZS 120,000"}
    assert body["link"] == "/tenant/approvals"
    for expected in ("unregistered", "unregistered", "retryable", "retryable"):
        with pytest.raises(PushSendError) as err:
            client.send(ios)
        assert getattr(err.value, expected) is True
    # The provider token is reused within its lifetime and re-minted after an ExpiredProviderToken reply.
    tokens = [r.headers["authorization"] for r in seen]
    assert len(set(tokens[:5])) == 1
    now[0] += 60
    client.send(ios)
    assert seen[-1].headers["authorization"] != tokens[0]


def test_apns_topic_follows_the_receiving_app(apns_key: tuple[Path, Any]) -> None:
    path, _ = apns_key
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200)

    client = _apns(path, handler, [time.time()])
    client.send(PushMessage("a1b2c3d4" * 8, "Expense approved", "TZS 20,000", app="SUPERVISOR"))
    assert seen[0].headers["apns-topic"] == "com.asseta.supervisor"
    settings = PushSettings(
        ios_provider="apns",
        apns_key_file=str(path),
        apns_key_id="ABC123",
        apns_team_id="T",
        apns_topic="com.asseta.owner",
    )
    unset = ApnsPushClient(settings, httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(PushSendError) as err:
        unset.send(PushMessage("a1b2c3d4" * 8, "Expense approved", "TZS 20,000", app="SUPERVISOR"))
    assert not err.value.retryable and not err.value.unregistered and len(seen) == 1
