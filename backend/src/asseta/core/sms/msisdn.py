"""Phone number normalisation to the international digits-only form NextSMS expects (e.g. 255712345678)."""

import re

_DIGITS = re.compile(r"\d+")


class InvalidMsisdn(ValueError):
    pass


def normalize_msisdn(raw: str, default_country_code: str = "255") -> str:
    """Accepts "+255 712 345 678", "0712-345-678", "712345678", "255712345678"; returns "255712345678"."""
    text = raw.strip()
    digits = "".join(_DIGITS.findall(text))
    if not digits:
        raise InvalidMsisdn(f"Not a phone number: {raw!r}")
    if text.startswith("+") or text.startswith("00"):
        digits = digits[2:] if text.startswith("00") else digits
    elif digits.startswith("0"):
        digits = default_country_code + digits[1:]
    elif not digits.startswith(default_country_code) and len(digits) == 9:
        digits = default_country_code + digits
    if not 10 <= len(digits) <= 15:
        raise InvalidMsisdn(f"Not a valid international number: {raw!r}")
    if digits.startswith(default_country_code) and default_country_code == "255" and len(digits) != 12:
        raise InvalidMsisdn(f"Tanzanian numbers have 9 digits after 255: {raw!r}")
    return digits
