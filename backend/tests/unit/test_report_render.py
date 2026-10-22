"""Report cell formatting and CSV/PDF safety helpers (pure functions)."""

from datetime import UTC, date, datetime
from decimal import Decimal

from asseta.modules.reports.definitions import format_value
from asseta.modules.reports.render import latin1, safe_csv_cell

TZ = "Africa/Dar_es_Salaam"


def test_machine_and_human_formats() -> None:
    instant = datetime(2026, 11, 1, 21, 30, tzinfo=UTC)
    assert format_value(instant, "instant", TZ) == "2026-11-02T00:30:00+03:00"  # tenant-local date rolls over
    assert format_value(instant, "instant", TZ, human=True) == "2026-11-02 00:30"
    assert format_value(Decimal("1092500"), "money", TZ) == "1092500.0000"  # same text as the JSON API
    assert format_value(Decimal("1092500"), "money", TZ, human=True) == "1,092,500.00"
    assert format_value(date(2026, 11, 30), "date", TZ) == "2026-11-30"
    assert format_value(True, "bool", TZ) == "Yes" and format_value(None, "money", TZ) == ""


def test_formula_injection_is_neutralised_only_in_text_cells() -> None:
    for risky in ("=1+1", "+cmd|' /C calc'!A0", "-2+3", "@SUM(A1)", "\t=x", "\r=x"):
        assert safe_csv_cell(risky, numeric=False) == "'" + risky
    assert safe_csv_cell("-150.0000", numeric=True) == "-150.0000"  # server-rendered Decimal stays numeric
    assert safe_csv_cell("Road Builders", numeric=False) == "Road Builders"


def test_pdf_text_is_latin1_safe() -> None:
    assert latin1("Fuel — 5 L … “ok” ✓ ≥ 3") == 'Fuel - 5 L ... "ok" ? >= 3'
    assert latin1("Dar es Salaam · Ümlaut") == "Dar es Salaam · Ümlaut"
