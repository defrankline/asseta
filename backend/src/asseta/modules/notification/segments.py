"""SMS segment counting for wallet metering: GSM-7 (160 single / 153 per concatenated part; extension characters
count twice) or UCS-2 when any character is outside GSM-7 (70 / 67)."""

GSM7_BASIC = frozenset(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿"
    "abcdefghijklmnopqrstuvwxyzäöñüà"
)
GSM7_EXTENSION = frozenset("^{}\\[~]|€\f")


def sms_segments(text: str) -> tuple[int, str]:
    """(segments, encoding) for `text`; an empty text is 0 segments."""
    if all(c in GSM7_BASIC or c in GSM7_EXTENSION for c in text):
        units = sum(2 if c in GSM7_EXTENSION else 1 for c in text)
        single, multi, encoding = 160, 153, "GSM-7"
    else:
        units = sum(2 if ord(c) > 0xFFFF else 1 for c in text)  # UTF-16 code units
        single, multi, encoding = 70, 67, "UCS-2"
    if units == 0:
        return 0, encoding
    return (1 if units <= single else -(-units // multi)), encoding
