"""Reference implementation of the hour-meter OCR text parsing rules (spec v2).

The Android and iOS apps implement the same rules natively and must pass the shared cases in
`contracts/fixtures/ocr/parse_cases.json` (prevents business-rule drift between platforms). On-device OCR output
is evidence, not proof: a parse failure or ambiguity returns no value and the app falls back to manual entry
(policy permitting), keeping the original photo and raw text.
"""

import re
from dataclasses import dataclass
from decimal import Decimal

SPEC_VERSION = "2"
# An hours unit written right after a number tags that number (v2); "#" marks it for the tokenizer.
_UNIT_AFTER_NUMBER = re.compile(r"(?<=\d)\s*(?:HOURS?|HRS?|H)(?![A-Z])")
_UNITS = re.compile(r"\b(HRS?|HOURS?|H)\b")
_CLOCK = re.compile(r"\b\d{1,2}:\d{2}(:\d{2})?\b")
_CONFUSABLE = str.maketrans(
    {"O": "0", "D": "0", "Q": "0", "I": "1", "L": "1", "|": "1", "S": "5", "B": "8", "Z": "2", "G": "6"}
)
_TOKEN = re.compile(r"[0-9OQDILSBZG|]+(?:[.,][0-9OQDILSBZG|]+)?|#")


@dataclass(frozen=True)
class ParseResult:
    value: str | None  # decimal string, or None => manual fallback
    reason: str


def parse_reading(text: str, decimal_places: int) -> ParseResult:
    """Extract the hour-meter reading from OCR text.

    Rules: ignore clock times and unit words; map common letter/digit confusions inside numeric tokens; a token with
    an explicit '.'/',' separator is decimal; a long integer token immediately followed by a single digit token is a
    tenths drum (mechanical counters); exactly one candidate must remain, else ambiguous. v2: when several remain, the
    single candidate written with an hours unit and exactly the meter's decimal places wins (dashboards that also show
    trip/idle counters and fuel); two or more such candidates stay ambiguous.
    """
    upper = _CLOCK.sub(" ", text.upper())
    upper = _UNIT_AFTER_NUMBER.sub(" # ", upper)
    upper = _UNITS.sub(" ", upper)
    tokens = [t for t in _TOKEN.findall(upper) if t == "#" or any(c.isdigit() for c in t)]
    tokens = [t.translate(_CONFUSABLE).replace(",", ".") for t in tokens]
    candidates: list[tuple[str, bool]] = []  # (text, written with an hours unit)
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        if tok == "#":
            i += 1
            continue
        if "." not in tok and nxt not in (None, "#") and len(nxt or "") == 1 and len(tok) >= 3 and decimal_places >= 1:
            i += 2
            candidates.append((f"{tok}.{nxt}", i < len(tokens) and tokens[i] == "#"))  # drum: last wheel is tenths
            continue
        i += 1
        if len(tok.replace(".", "")) >= 3:
            candidates.append((tok, i < len(tokens) and tokens[i] == "#"))
    if not candidates:
        return ParseResult(None, "NO_NUMBER")
    if len(candidates) > 1:
        preferred = [c for c in candidates if c[1] and _fraction_digits(c[0]) == decimal_places]
        if len(preferred) != 1:
            return ParseResult(None, "AMBIGUOUS")
        candidates = preferred
    value = Decimal(candidates[0][0])
    exponent = value.as_tuple().exponent
    if not isinstance(exponent, int) or exponent < -decimal_places:
        return ParseResult(None, "PRECISION_EXCEEDS_METER")
    return ParseResult(format(value.quantize(Decimal(1).scaleb(-decimal_places)), "f"), "OK")


def _fraction_digits(candidate: str) -> int:
    return len(candidate.partition(".")[2])
