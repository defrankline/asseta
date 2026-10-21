"""Reusable SMS utility: number normalisation, NextSMS request shape/auth from settings, batching and errors.
Uses an in-memory HTTP transport: no real SMS is ever sent from tests."""

import base64
import json
from typing import Any

import httpx
import pytest

from asseta.core.sms import (
    ConsoleSmsClient,
    InvalidMsisdn,
    NextSmsClient,
    SmsSendError,
    SmsSettings,
    build_sms_client,
    normalize_msisdn,
)

FAKE_URL = "https://sms.test/api/sms/v1/text/single"


def settings(**overrides: object) -> SmsSettings:
    values: dict[str, Any] = {
        "sms_provider": "nextsms",
        "nextsms_url": FAKE_URL,
        "nextsms_sender_id": "ASSETA",
        "nextsms_username": "demo-user",
        "nextsms_password": "demo-pass",
        **overrides,
    }
    return SmsSettings(_env_file=None, **values)


def recording_client(s: SmsSettings, status: int = 200) -> tuple[NextSmsClient, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status, json={"messages": [{"status": "PENDING"}]})

    return NextSmsClient(s, httpx.Client(transport=httpx.MockTransport(handler))), seen


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+255 712 345 678", "255712345678"),
        ("0712-345-678", "255712345678"),
        ("712345678", "255712345678"),
        ("255712345678", "255712345678"),
        ("00255712345678", "255712345678"),
        ("+254 712 345678", "254712345678"),
    ],
)
def test_normalize_msisdn(raw: str, expected: str) -> None:
    assert normalize_msisdn(raw) == expected


@pytest.mark.parametrize("raw", ["", "abc", "0712", "2557123456789", "+1"])
def test_normalize_msisdn_rejects(raw: str) -> None:
    with pytest.raises(InvalidMsisdn):
        normalize_msisdn(raw)


def test_nextsms_request_shape_and_basic_auth_from_settings() -> None:
    client, seen = recording_client(settings())
    result = client.send(["0712 345 678", "+255712345678", "0754000111"], "Invoice due", reference="d-1")
    [req] = seen
    assert str(req.url) == FAKE_URL and req.method == "POST"
    assert req.headers["Authorization"] == "Basic " + base64.b64encode(b"demo-user:demo-pass").decode()
    assert req.headers["Accept"] == "application/json"
    body = json.loads(req.content)
    assert body == {"from": "ASSETA", "to": ["255712345678", "255754000111"], "text": "Invoice due", "reference": "d-1"}
    assert result.provider == "nextsms" and result.recipients == ("255712345678", "255754000111")


def test_pre_encoded_token_is_used_verbatim() -> None:
    client, seen = recording_client(settings(nextsms_username="", nextsms_password="", nextsms_auth_token="dG9rZW4="))
    client.send(["0712345678"], "Hi")
    assert seen[0].headers["Authorization"] == "Basic dG9rZW4="


def test_batches_large_recipient_lists() -> None:
    client, seen = recording_client(settings(sms_max_recipients_per_request=2))
    client.send([f"07120000{i:02d}" for i in range(5)], "Bulk")
    assert [len(json.loads(r.content)["to"]) for r in seen] == [2, 2, 1]


@pytest.mark.parametrize(("status", "retryable"), [(401, False), (400, False), (429, True), (503, True)])
def test_failures_raise_without_leaking_credentials(status: int, retryable: bool) -> None:
    client, _ = recording_client(settings(), status=status)
    with pytest.raises(SmsSendError) as err:
        client.send(["0712345678"], "Hi")
    assert err.value.status_code == status and err.value.retryable is retryable
    assert "demo-pass" not in str(err.value) and "Basic" not in str(err.value)


def test_network_error_is_retryable() -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    client = NextSmsClient(settings(), httpx.Client(transport=httpx.MockTransport(boom)))
    with pytest.raises(SmsSendError) as err:
        client.send(["0712345678"], "Hi")
    assert err.value.retryable is True


def test_nextsms_requires_sender_and_credentials() -> None:
    with pytest.raises(ValueError, match="SENDER_ID"):
        settings(nextsms_sender_id="")
    with pytest.raises(ValueError, match="USERNAME"):
        settings(nextsms_username="", nextsms_password="")


def test_console_is_default_and_sends_nothing() -> None:
    s = SmsSettings(_env_file=None)
    client = build_sms_client(s)
    assert isinstance(client, ConsoleSmsClient)
    assert client.send(["0712345678"], "Hello").provider == "console"
    with pytest.raises(ValueError):
        client.send([], "Hello")
