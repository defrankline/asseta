"""The Python reference parser must satisfy the shared cross-platform OCR parsing cases."""

import json
from pathlib import Path

import pytest

from asseta.modules.meter.ocr_parse import SPEC_VERSION, parse_reading

CASES = json.loads((Path(__file__).parents[3] / "contracts/fixtures/ocr/parse_cases.json").read_text())


def test_spec_version_matches() -> None:
    assert CASES["spec_version"] == SPEC_VERSION


@pytest.mark.parametrize("case", CASES["cases"], ids=lambda c: c["text"][:24])
def test_shared_parse_case(case: dict[str, object]) -> None:
    result = parse_reading(str(case["text"]), int(str(case["decimal_places"])))
    assert (result.value, result.reason) == (case["value"], case["reason"])
