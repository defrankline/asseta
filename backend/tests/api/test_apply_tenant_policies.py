"""apply_tenant_policies.py: one company's settings from a file, as ordinary tenant policy versions."""

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest
from sqlalchemy import Engine, text

from tests.support.api import Api

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "apply_tenant_policies.py"
CUSTOMER_HOURS = "/api/v1/tenant/policies/CUSTOMER_HOURS/effective"


@pytest.fixture(scope="module")
def tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("apply_tenant_policies", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["apply_tenant_policies"] = module  # dataclasses resolve their module by name
    spec.loader.exec_module(module)
    return module


def _file(tmp_path: Path, policies: dict[str, object], reason: str = "Go-live settings") -> str:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"reason": reason, "policies": policies}), encoding="utf-8")
    return str(path)


def _versions(owner_engine: Engine, tid: str) -> int:
    with owner_engine.begin() as c:
        c.execute(text("SELECT set_config('app.scope', 'system', true)"))
        return int(c.execute(text("SELECT count(*) FROM policy_version WHERE tenant_id = :t"), {"t": tid}).scalar_one())


def test_dry_run_apply_and_second_run(
    api: Api, tool: ModuleType, tmp_path: Path, owner_engine: Engine, capsys: pytest.CaptureFixture[str]
) -> None:
    a = api.onboard("Apply Co", price="1")
    tid = a["tenant"]["id"]
    f = _file(
        tmp_path,
        {
            "CUSTOMER_HOURS": {"default_billing_mode": "PREPAID_HOURS", "expiry_days": 365},
            "DEVICE_SYNC": {"offline_grant_hours": 336, "snapshot_validity_hours": 336},
        },
    )
    assert tool.main(["--tenant-id", tid, "--file", f]) == 0
    assert "DRY RUN: 4 setting(s)" in capsys.readouterr().out
    assert _versions(owner_engine, tid) == 0

    assert tool.main(["--tenant-id", tid, "--file", f, "--yes", "--operator", "me@host"]) == 0
    assert "APPLIED: 4 setting(s)" in capsys.readouterr().out
    assert _versions(owner_engine, tid) == 2
    effective = a["owner"].get(CUSTOMER_HOURS).json()
    assert effective["values"]["default_billing_mode"] == "PREPAID_HOURS"
    assert effective["values"]["expiry_days"] == 365
    with owner_engine.begin() as c:
        c.execute(text("SELECT set_config('app.scope', 'system', true)"))
        audits = c.execute(
            text("SELECT reason FROM audit_event WHERE tenant_id = :t AND action LIKE 'policy.%.versioned'"), {"t": tid}
        ).all()
    assert len(audits) == 2 and "me@host" in audits[0][0]

    assert tool.main(["--tenant-id", tid, "--file", f, "--yes"]) == 0  # nothing left to change
    assert "Nothing to change" in capsys.readouterr().out
    assert _versions(owner_engine, tid) == 2


def test_refusals_change_nothing(
    api: Api, tool: ModuleType, tmp_path: Path, owner_engine: Engine, capsys: pytest.CaptureFixture[str]
) -> None:
    tid = api.onboard("Refuse Co", price="1")["tenant"]["id"]
    bad: list[dict[str, object]] = [
        {"NOPE": {"x": 1}},
        {"CUSTOMER_HOURS": {"not_a_field": 1}},
        {"OVERSIGHT": {"managed_service_enabled": False}},
        {"DEVICE_SYNC": {"offline_grant_hours": 100000}},
        # The whole set is validated together, and one bad type stops the good one.
        {"ENGINE_HOURS": {"daily_report_required": True}, "CUSTOMER_HOURS": {"default_billing_mode": "NOT_A_MODE"}},
    ]
    for policies in bad:
        assert tool.main(["--tenant-id", tid, "--file", _file(tmp_path, policies), "--yes"]) == 2, policies
        assert "REFUSED" in capsys.readouterr().err
    assert _versions(owner_engine, tid) == 0
    assert tool.main(["--tenant-id", "00000000-0000-0000-0000-000000000000", "--file", _file(tmp_path, bad[1])]) == 2
