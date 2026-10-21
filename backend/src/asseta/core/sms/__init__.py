"""Reusable outbound SMS utility: provider-agnostic interface, NextSMS client and a console client for dev/test.

Usage:
    from asseta.core.sms import build_sms_client
    result = build_sms_client().send(["0712 345 678"], "Your invoice is due", reference="delivery-123")
"""

from asseta.core.sms.client import (
    ConsoleSmsClient,
    NextSmsClient,
    SmsClient,
    SmsSendError,
    SmsSendResult,
    build_sms_client,
)
from asseta.core.sms.msisdn import InvalidMsisdn, normalize_msisdn
from asseta.core.sms.settings import SmsSettings, get_sms_settings

__all__ = [
    "ConsoleSmsClient",
    "InvalidMsisdn",
    "NextSmsClient",
    "SmsClient",
    "SmsSendError",
    "SmsSendResult",
    "SmsSettings",
    "build_sms_client",
    "get_sms_settings",
    "normalize_msisdn",
]
