"""seed_reason_lists.py: one company's starter reason lists from a file, added once, with audit events."""

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest
from sqlalchemy import Engine, text

from tests.support.api import Api

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "seed_reason_lists.py"
EXAMPLE = ROOT.parent / "deploy" / "reason-lists.example.json"
TABLES = ("hours_reason_code", "engine_hour_reason", "cash_reason", "revenue_reason")
SMALL = {
    "customer_hours": {"DISCOUNT": [{"code": "LOYAL", "label": "Long-standing customer"}]},
    "engine_hours": {"NON_CUSTOMER_CATEGORY": [{"code": "MAINTENANCE", "label": "Maintenance and servicing"}]},
    "cash": {"VARIANCE": [{"label": "Counting error"}], "WRITE_OFF": [{"label": "Counting error"}]},
    "revenue": [{"code": "ON_CREDIT", "label": "On credit, not yet paid", "description": "Paid later"}],
}


@pytest.fixture(scope="module")
def tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("seed_reason_lists", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["seed_reason_lists"] = module
    spec.loader.exec_module(module)
    return module


def _file(tmp_path: Path, data: object, name: str = "reasons.json") -> str:
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


def _scalar(owner_engine: Engine, sql: str, tid: str) -> int:
    with owner_engine.begin() as c:
        c.execute(text("SELECT set_config('app.scope', 'system', true)"))
        return int(c.execute(text(sql), {"t": tid}).scalar_one())


def _counts(owner_engine: Engine, tid: str) -> tuple[int, ...]:
    return tuple(_scalar(owner_engine, f"SELECT count(*) FROM {t} WHERE tenant_id = :t", tid) for t in TABLES)  # noqa: S608


def _audits(owner_engine: Engine, tid: str) -> int:
    sql = (
        "SELECT count(*) FROM audit_event WHERE tenant_id = :t AND action IN ('hours.reason_code.created', "
        "'meter.reason.created', 'finance.cash_reason.created', 'revenue.reason.created')"
    )
    return _scalar(owner_engine, sql, tid)


def test_dry_run_seed_and_second_run(
    api: Api, tool: ModuleType, tmp_path: Path, owner_engine: Engine, capsys: pytest.CaptureFixture[str]
) -> None:
    tid = api.onboard("Reason Co", price="1")["tenant"]["id"]
    f = _file(tmp_path, SMALL)
    assert tool.main(["--tenant-id", tid, "--file", f]) == 0
    assert "DRY RUN: 5 reason(s)" in capsys.readouterr().out
    assert _counts(owner_engine, tid) == (0, 0, 0, 0)

    assert tool.main(["--tenant-id", tid, "--file", f, "--yes", "--operator", "me@host"]) == 0
    assert "ADDED: 5 reason(s)" in capsys.readouterr().out
    assert _counts(owner_engine, tid) == (1, 1, 2, 1)  # the same cash label in two lists is two reasons
    assert _audits(owner_engine, tid) == 5

    assert tool.main(["--tenant-id", tid, "--file", f, "--yes"]) == 0
    assert "Nothing to add." in capsys.readouterr().out
    assert _counts(owner_engine, tid) == (1, 1, 2, 1)


def test_the_seeded_reasons_are_the_companys_usable_lists(api: Api, tool: ModuleType, tmp_path: Path) -> None:
    onboarded = api.onboard("Usable Co", price="1")
    tid = onboarded["tenant"]["id"]
    assert tool.main(["--tenant-id", tid, "--file", _file(tmp_path, SMALL), "--yes"]) == 0
    owner = onboarded["owner"]
    cash = owner.get("/api/v1/tenant/cash/reasons")
    assert cash.status_code == 200, cash.text
    assert sorted((r["kind"], r["label"]) for r in cash.json()["items"]) == [
        ("VARIANCE", "Counting error"),
        ("WRITE_OFF", "Counting error"),
    ]
    engine = owner.get("/api/v1/tenant/engine-hour-reasons")
    assert engine.status_code == 200, engine.text
    assert [r["code"] for r in engine.json()["items"]] == ["MAINTENANCE"]


def test_existing_entries_are_skipped_in_any_capitals(
    api: Api, tool: ModuleType, tmp_path: Path, owner_engine: Engine, capsys: pytest.CaptureFixture[str]
) -> None:
    tid = api.onboard("Skip Reason Co", price="1")["tenant"]["id"]
    assert tool.main(["--tenant-id", tid, "--file", _file(tmp_path, SMALL), "--yes"]) == 0
    capsys.readouterr()
    again = {
        "customer_hours": {"DISCOUNT": [{"code": "loyal", "label": "Renamed"}, {"code": "VOLUME", "label": "Large"}]},
        "cash": {"VARIANCE": [{"label": "COUNTING ERROR"}]},
    }
    assert tool.main(["--tenant-id", tid, "--file", _file(tmp_path, again, "again.json"), "--yes"]) == 0
    out = capsys.readouterr().out
    assert "Already there, skipped: 2" in out and "ADDED: 1 reason(s)" in out
    assert _counts(owner_engine, tid) == (2, 1, 2, 1)


def test_only_the_named_company_changes(api: Api, tool: ModuleType, tmp_path: Path, owner_engine: Engine) -> None:
    tid = api.onboard("One Reason Co", price="1")["tenant"]["id"]
    other = api.onboard("Other Reason Co", price="1")["tenant"]["id"]
    assert tool.main(["--tenant-id", tid, "--file", _file(tmp_path, SMALL), "--yes"]) == 0
    assert _counts(owner_engine, other) == (0, 0, 0, 0)


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({}, "no reasons"),
        ({"stock": []}, "unknown section"),
        ({"cash": {"BONUS": [{"label": "x y"}]}}, "unknown list"),
        ({"revenue": []}, "non-empty"),
        ({"revenue": [{"label": "No code"}]}, '"code"'),
        ({"revenue": [{"code": "X" * 33, "label": "Too long"}]}, '"code"'),
        ({"customer_hours": {"DISCOUNT": [{"code": "A", "label": "x"}]}}, '"label"'),
        ({"revenue": [{"code": "A", "label": "One"}, {"code": "a", "label": "Two"}]}, "twice"),
        ({"cash": {"VARIANCE": [{"label": "Error"}, {"label": "error"}]}}, "twice"),
    ],
)
def test_a_bad_file_is_refused_before_anything_changes(
    api: Api,
    tool: ModuleType,
    tmp_path: Path,
    owner_engine: Engine,
    capsys: pytest.CaptureFixture[str],
    data: object,
    message: str,
) -> None:
    tid = api.onboard("Bad Reason Co", price="1")["tenant"]["id"]
    assert tool.main(["--tenant-id", tid, "--file", _file(tmp_path, data), "--yes"]) == 2
    assert message in capsys.readouterr().err
    assert _counts(owner_engine, tid) == (0, 0, 0, 0)


def test_unknown_company_and_platform_scope_are_refused(
    tool: ModuleType, api: Api, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    f = _file(tmp_path, SMALL)
    assert tool.main(["--registration-number", "no/such/number", "--file", f, "--yes"]) == 2
    assert "no such tenant" in capsys.readouterr().err
    assert tool.main(["--tenant-id", "00000000-0000-0000-0000-000000000000", "--file", f, "--yes"]) == 2


def test_the_example_lists_are_valid(tool: ModuleType) -> None:
    entries = tool.read_file(EXAMPLE)
    assert len(entries) == 70
    assert {e.section for e in entries} == {"customer_hours", "engine_hours", "cash", "revenue"}
