"""OCR fixture corpus integrity: every manifest entry exists, is the declared size, and its expected reading is a
valid meter value at the declared precision."""

import json
from decimal import Decimal
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).parents[3] / "contracts/fixtures/ocr"
MANIFEST = json.loads((ROOT / "manifest.json").read_text())


def test_manifest_entries_are_complete_and_valid() -> None:
    images = MANIFEST["images"]
    assert len(images) == 24 and {i["category"] for i in images} == {"must_read", "fallback_ok"}
    for entry in images:
        with Image.open(ROOT / entry["file"]) as img:
            assert img.size == (480, 200)
        reading = Decimal(entry["expected_reading"])
        exponent = reading.as_tuple().exponent
        assert isinstance(exponent, int) and reading == Decimal(entry["displayed"])
        assert -exponent <= entry["decimal_places"]
    assert MANIFEST["acceptance"]["wrong_confident_reads_allowed"] == 0
