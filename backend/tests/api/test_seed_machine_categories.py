"""seed_machine_categories.py: one company's machine types from a file, added once, with audit events."""

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest
from sqlalchemy import Engine, text

from tests.support.api import Api

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "seed_machine_categories.py"
EXAMPLE = ROOT.parent / "deploy" / "machine-categories.example.json"


@pytest.fixture(scope="module")
def tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("seed_machine_categories", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["seed_machine_categories"] = module
    spec.loader.exec_module(module)
    return module


def _file(tmp_path: Path, categories: object) -> str:
    path = tmp_path / "categories.json"
    path.write_text(json.dumps({"categories": categories}), encoding="utf-8")
    return str(path)


def _scalar(owner_engine: Engine, sql: str, tid: str) -> int:
    with owner_engine.begin() as c:
        c.execute(text("SELECT set_config('app.scope', 'system', true)"))
        return int(c.execute(text(sql), {"t": tid}).scalar_one())


def _categories(owner_engine: Engine, tid: str) -> int:
    return _scalar(owner_engine, "SELECT count(*) FROM machine_category WHERE tenant_id = :t", tid)


def _audits(owner_engine: Engine, tid: str) -> int:
    sql = "SELECT count(*) FROM audit_event WHERE tenant_id = :t AND action = 'fleet.category.created'"
    return _scalar(owner_engine, sql, tid)


def test_dry_run_seed_and_second_run(
    api: Api, tool: ModuleType, tmp_path: Path, owner_engine: Engine, capsys: pytest.CaptureFixture[str]
) -> None:
    tid = api.onboard("Seed Co", price="1")["tenant"]["id"]
    f = _file(tmp_path, [{"name": "Forklift"}, {"name": "Tractor", "description": "Farm tractor"}])
    assert tool.main(["--tenant-id", tid, "--file", f]) == 0
    assert "DRY RUN: 2 machine type(s)" in capsys.readouterr().out
    assert _categories(owner_engine, tid) == 0

    assert tool.main(["--tenant-id", tid, "--file", f, "--yes", "--operator", "me@host"]) == 0
    assert "ADDED: 2 machine type(s)" in capsys.readouterr().out
    assert _categories(owner_engine, tid) == 2
    assert _audits(owner_engine, tid) == 2

    assert tool.main(["--tenant-id", tid, "--file", f, "--yes"]) == 0
    assert "Nothing to add." in capsys.readouterr().out
    assert _categories(owner_engine, tid) == 2


def test_existing_names_are_skipped_in_any_capitals(
    api: Api, tool: ModuleType, tmp_path: Path, owner_engine: Engine, capsys: pytest.CaptureFixture[str]
) -> None:
    tid = api.onboard("Skip Co", price="1")["tenant"]["id"]
    assert tool.main(["--tenant-id", tid, "--file", _file(tmp_path, [{"name": "Forklift"}]), "--yes"]) == 0
    capsys.readouterr()
    f = _file(tmp_path, [{"name": "FORKLIFT"}, {"name": "Tractor"}])
    assert tool.main(["--tenant-id", tid, "--file", f, "--yes"]) == 0
    out = capsys.readouterr().out
    assert "Already there, skipped: 1" in out and "ADDED: 1 machine type(s)" in out
    assert _categories(owner_engine, tid) == 2


def test_only_the_named_company_changes(api: Api, tool: ModuleType, tmp_path: Path, owner_engine: Engine) -> None:
    tid = api.onboard("One Co", price="1")["tenant"]["id"]
    other = api.onboard("Other Co", price="1")["tenant"]["id"]
    assert tool.main(["--tenant-id", tid, "--file", _file(tmp_path, [{"name": "Forklift"}]), "--yes"]) == 0
    assert (_categories(owner_engine, tid), _categories(owner_engine, other)) == (1, 0)


@pytest.mark.parametrize(
    ("categories", "message"),
    [
        ([], "non-empty"),
        ([{"description": "no name"}], "needs a"),
        ([{"name": "x" * 101}], "needs a"),
        ([{"name": "Forklift"}, {"name": "forklift "}], "twice"),
        ([{"name": "Forklift", "description": "x" * 301}], "description"),
    ],
)
def test_a_bad_file_is_refused_before_anything_changes(
    api: Api,
    tool: ModuleType,
    tmp_path: Path,
    owner_engine: Engine,
    capsys: pytest.CaptureFixture[str],
    categories: object,
    message: str,
) -> None:
    tid = api.onboard("Bad Co", price="1")["tenant"]["id"]
    assert tool.main(["--tenant-id", tid, "--file", _file(tmp_path, categories), "--yes"]) == 2
    assert message in capsys.readouterr().err
    assert _categories(owner_engine, tid) == 0


def test_unknown_company_and_platform_scope_are_refused(
    tool: ModuleType, api: Api, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    f = _file(tmp_path, [{"name": "Forklift"}])
    assert tool.main(["--registration-number", "no/such/number", "--file", f, "--yes"]) == 2
    assert "no such tenant" in capsys.readouterr().err
    assert tool.main(["--tenant-id", "00000000-0000-0000-0000-000000000000", "--file", f, "--yes"]) == 2


def test_the_example_list_is_valid(tool: ModuleType) -> None:
    assert len(tool.read_file(EXAMPLE)) == 37
