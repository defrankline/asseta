"""DEC-032 Phase 5 (guideline 6 and 9): full tenant data export (background job, audited, evidence manifest), balance
verification against stored figures (planted mismatch; the ledger prevails), the go-live marker and the reset lock."""

import csv
import importlib.util
import io
import json
import sys
import uuid
import zipfile
from collections.abc import Iterator
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from typing import Any

import psycopg
import pytest
from sqlalchemy import Engine, text

from asseta.core.config import get_settings
from asseta.core.db import DbScope, apply_scope, get_sessionmaker
from asseta.modules.dataprotection.balance_checks import verify_tenant
from asseta.modules.dataprotection.balance_report import CheckKind
from asseta.modules.dataprotection.export_tables import EXCLUDED, NOT_SECRETS, REDACTED_COLUMNS, SECRET_LIKE
from asseta.modules.dataprotection.export_worker_core import expire_exports, run_pending
from asseta.modules.dataprotection.verification import run_balance_verification_sweep
from tests.support.api import Api
from tests.support.finance import FinCtx, setup_finance
from tests.support.hours import RATE, balance, hours_policy, purchase, verify
from tests.support.jobs import unique_jpeg

T = "/api/v1/tenant"
P = "/api/v1/platform"
SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "reset_tenant_data.py"


@pytest.fixture(scope="module")
def rt() -> ModuleType:
    spec = importlib.util.spec_from_file_location("reset_tenant_data", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["reset_tenant_data"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def conn(owner_engine: Engine) -> Iterator[psycopg.Connection[Any]]:
    url = get_settings().migration_database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(url, autocommit=True) as c:
        yield c


def _ok(r: Any, status: int = 200) -> Any:
    assert r.status_code == status, r.text
    return r.json()


def _err(r: Any, status: int, code: str) -> None:
    assert r.status_code == status, r.text
    assert r.json()["error"]["code"] == code, r.text


def _store(api: Api) -> Any:
    return api.client.app.state.object_store  # type: ignore[attr-defined]


def _audit(owner_engine: Engine, tid: str, prefix: str) -> list[Any]:
    with owner_engine.begin() as c:
        c.execute(text("SELECT set_config('app.scope', 'system', true)"))
        return list(
            c.execute(
                text(
                    "SELECT action, after, reason FROM audit_event WHERE tenant_id = :t AND action LIKE :p ORDER BY occurred_at"
                ),
                {"t": tid, "p": f"{prefix}%"},
            ).all()
        )


def _sql(owner_engine: Engine, sql: str, **params: Any) -> None:
    with owner_engine.begin() as c:
        c.execute(text("SELECT set_config('app.scope', 'system', true)"))
        c.execute(text(sql), params)


def _attachment(api: Api, f: FinCtx) -> str:
    h = f.owner.headers(True, None)
    h.pop("Idempotency-Key", None)
    r = api.client.post(
        f"{T}/attachments",
        headers=h,
        files={"file": ("p.jpg", unique_jpeg(), "image/jpeg")},
        data={"purpose": "METER_PHOTO"},
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


def _run_worker(api: Api) -> int:
    return run_pending(get_sessionmaker(), _store(api), api.clock.now)


def test_export_is_gated_built_in_background_and_audited(api: Api, owner_engine: Engine) -> None:
    f = setup_finance(api)
    att = _attachment(api, f)
    assert f.manager.post(f"{T}/data-exports", {}).status_code == 403
    row = _ok(f.owner.post(f"{T}/data-exports", {"format": "CSV"}), 201)
    assert row["status"] == "QUEUED"
    _err(f.owner.post(f"{T}/data-exports", {"format": "JSON"}), 409, "EXPORT_IN_PROGRESS")
    _err(f.owner.post(f"{T}/data-exports/{row['id']}/download"), 422, "EXPORT_NOT_READY")

    assert _run_worker(api) == 1
    done = _ok(f.owner.get(f"{T}/data-exports/{row['id']}"))
    assert done["status"] == "COMPLETED" and done["row_count"] > 0 and done["evidence_count"] == 1
    link = _ok(f.owner.post(f"{T}/data-exports/{row['id']}/download"))
    assert link["url"].startswith("https://objects.test/") and link["expires_in_seconds"] > 0
    assert f.manager.get(f"{T}/data-exports").status_code == 403

    key = f"tenants/{f.tid}/exports/{row['id']}.zip"
    archive = zipfile.ZipFile(io.BytesIO(_store(api).objects[key][0]))
    names = set(archive.namelist())
    assert {
        "README.txt",
        "manifest.json",
        "evidence/manifest.csv",
        "data/audit_event.csv",
        "data/customer.csv",
    } <= names
    assert not any(name.endswith(("tenant_data_export.csv", "outbox_event.csv")) for name in names)
    manifest = json.loads(archive.read("manifest.json"))
    assert manifest["tenant_id"] == f.tid and manifest["format"] == "CSV"
    customers = next(t for t in manifest["tables"] if t["file"] == "data/customer.csv")
    rows = list(csv.DictReader(io.StringIO(archive.read("data/customer.csv").decode())))
    assert customers["rows"] == len(rows) >= 1 and all(r["tenant_id"] == f.tid for r in rows)
    evidence = list(csv.DictReader(io.StringIO(archive.read("evidence/manifest.csv").decode())))
    assert [e["id"] for e in evidence] == [att] and evidence[0]["source"] == "capture_attachment"

    fetched = _ok(f.owner.get(evidence[0]["fetch_path"]))
    assert fetched["url"].startswith("https://objects.test/tenants/")
    assert f.manager.get(evidence[0]["fetch_path"]).status_code == 403
    actions = [a[0] for a in _audit(owner_engine, f.tid, "tenant.data_export.")]
    assert actions == [
        "tenant.data_export.requested",
        "tenant.data_export.completed",
        "tenant.data_export.downloaded",
        "tenant.data_export.evidence_fetched",
    ]


def test_export_is_tenant_isolated_and_json_format_and_excludes_credentials(api: Api, owner_engine: Engine) -> None:
    f = setup_finance(api, name="One Co", device="ONE-1")
    g = api.onboard("Two Co", price="1")["owner"]
    row = _ok(f.owner.post(f"{T}/data-exports", {"format": "JSON"}), 201)
    _err(g.get(f"{T}/data-exports/{row['id']}"), 404, "NOT_FOUND")
    _run_worker(api)
    _err(g.post(f"{T}/data-exports/{row['id']}/download"), 404, "NOT_FOUND")
    att = _attachment(api, f)
    assert f.owner.get(f"{T}/data-exports/evidence/capture_attachment/{att}/url").status_code == 200
    _err(g.get(f"{T}/data-exports/evidence/capture_attachment/{att}/url"), 404, "NOT_FOUND")
    _err(g.get(f"{T}/data-exports/evidence/anything/{att}/url"), 404, "NOT_FOUND")
    run = _run(f)
    _err(g.get(f"{T}/balance-verification/runs/{run['id']}"), 404, "NOT_FOUND")
    archive = zipfile.ZipFile(io.BytesIO(_store(api).objects[f"tenants/{f.tid}/exports/{row['id']}.zip"][0]))
    customers = json.loads(archive.read("data/customer.json"))
    assert customers and {c["tenant_id"] for c in customers} == {f.tid}
    tracker = next(t for t in json.loads(archive.read("manifest.json"))["tables"] if t["file"] == "data/tracker.json")
    assert "credentials_ref" not in tracker["columns"]


def test_every_credential_like_column_is_classified(api: Api, owner_engine: Engine) -> None:
    with owner_engine.begin() as c:
        rows = c.execute(
            text(
                "SELECT c.table_name, c.column_name FROM information_schema.columns c"
                " JOIN information_schema.columns t ON t.table_name = c.table_name AND t.column_name = 'tenant_id'"
                " WHERE c.table_schema = 'public' AND t.table_schema = 'public'"
            )
        ).all()
    unclassified = sorted(
        f"{table}.{column}"
        for table, column in rows
        if SECRET_LIKE.search(column)
        and table not in EXCLUDED
        and column not in REDACTED_COLUMNS.get(table, frozenset())
        and f"{table}.{column}" not in NOT_SECRETS
    )
    assert unclassified == [], "add to REDACTED_COLUMNS, EXCLUDED or NOT_SECRETS in export_tables.py"


def test_expired_export_is_deleted_and_refused(api: Api) -> None:
    f = setup_finance(api)
    row = _ok(f.owner.post(f"{T}/data-exports", {}), 201)
    _run_worker(api)
    done = _ok(f.owner.get(f"{T}/data-exports/{row['id']}"))
    assert done["expires_at"] is not None
    assert expire_exports(get_sessionmaker(), _store(api), api.clock.now) == 0
    later = api.clock.now + timedelta(days=8)
    assert expire_exports(get_sessionmaker(), _store(api), later) == 1
    assert f"tenants/{f.tid}/exports/{row['id']}.zip" not in _store(api).objects
    assert _ok(f.owner.get(f"{T}/data-exports/{row['id']}"))["status"] == "EXPIRED"
    _err(f.owner.post(f"{T}/data-exports/{row['id']}/download"), 422, "EXPORT_EXPIRED")


def _purchase(api: Api, f: FinCtx, hours: str = "10") -> Any:
    hours_policy(f, adjustment_evidence_required=False)
    p = purchase(api, f.accountant, f, hours, pay=str(int(hours) * RATE), method="BANK")
    verify(f.owner, p["allocations"][0]["payment_id"])
    return p


def _run(f: FinCtx) -> Any:
    return _ok(f.owner.post(f"{T}/balance-verification/runs"), 201)


def _check(run: Any, kind: CheckKind) -> Any:
    return next(c for c in run["summary"] if c["check"] == kind.value)


def test_clean_records_verify_and_every_check_is_reported(api: Api) -> None:
    f = setup_finance(api)
    _purchase(api, f)
    assert f.manager.post(f"{T}/balance-verification/runs").status_code == 403
    run = _run(f)
    assert run["outcome"] == "MATCHED" and run["mismatch_count"] == 0 and run["findings"] == []
    assert {c["check"] for c in run["summary"]} == {k.value for k in CheckKind}
    assert _check(run, CheckKind.CUSTOMER_HOURS_LOT)["checked"] >= 1
    assert _check(run, CheckKind.CUSTOMER_RECEIVABLE)["checked"] >= 1
    assert _ok(f.owner.get(f"{T}/balance-verification/runs/{run['id']}"))["id"] == run["id"]
    assert f.owner.get(f"{T}/balance-verification/runs").json()["items"][0]["id"] == run["id"]


def test_planted_snapshot_mismatch_is_reported_and_the_ledger_prevails(api: Api, owner_engine: Engine) -> None:
    f = setup_finance(api)
    p = _purchase(api, f)
    down = _ok(
        f.accountant.post(
            f"{T}/adjustment-requests",
            {"request_type": "HOURS_CORRECTION", "purchase_id": p["id"], "hours": "-2.5", "reason": "Meter misread"},
        ),
        201,
    )
    _ok(f.owner.post(f"{T}/adjustment-requests/{down['id']}/decision", {"decision": "APPROVE"}))
    clean = _run(f)
    assert clean["outcome"] == "MATCHED" and _check(clean, CheckKind.CUSTOMER_HOURS_LOT)["checked"] >= 2

    wrong = Decimal("999.00")
    _sql(owner_engine, "ALTER TABLE adjustment_ledger_entry DISABLE TRIGGER trg_adjustment_ledger_entry_immutable")
    try:
        _sql(
            owner_engine,
            "UPDATE adjustment_ledger_entry SET new_value = :v WHERE tenant_id = :t AND adjustment_type = 'HOURS_CORRECTION'",
            v=wrong,
            t=f.tid,
        )
    finally:
        _sql(owner_engine, "ALTER TABLE adjustment_ledger_entry ENABLE TRIGGER trg_adjustment_ledger_entry_immutable")
    run = _run(f)
    assert run["outcome"] == "MISMATCHES" and run["mismatch_count"] == 1
    finding = run["findings"][0]
    assert finding["check"] == CheckKind.CUSTOMER_HOURS_LOT.value and Decimal(finding["stored_value"]) == wrong
    assert Decimal(finding["ledger_value"]) == Decimal("7.5") and Decimal(finding["difference"]) == wrong - Decimal(
        "7.5"
    )
    assert finding["subject_id"] == p["id"]
    # Reporting corrects nothing: the ledger is untouched.
    left = balance(f.owner, f.customer_id, f.c.t.machine_id)
    assert left is not None and Decimal(left["remaining"]) == Decimal("7.5")


def test_planted_invoice_and_report_figures_are_flagged(api: Api, owner_engine: Engine) -> None:
    f = setup_finance(api)
    with get_sessionmaker()() as s, s.begin():
        apply_scope(s, DbScope.TENANT, uuid.UUID(f.tid), None)
        report = verify_tenant(s, uuid.UUID(f.tid), api.clock.now)
    assert report.findings == []
    _sql(
        owner_engine,
        "INSERT INTO tenant_hire_invoice (id, tenant_id, customer_id, invoice_number, status, currency, subtotal,"
        " discount_total, tax_total, total, created_at, issued_at) VALUES (gen_random_uuid(), :t, :c, 'INV-PLANT',"
        " 'ISSUED', :cur, 100, 0, 0, 90, now(), now())",
        t=f.tid,
        c=f.customer_id,
        cur="TZS",
    )
    run = _run(f)
    assert _check(run, CheckKind.INVOICE_TOTAL)["mismatches"] == 1
    assert any(x["label"] == "INV-PLANT" for x in run["findings"])


def test_sweep_is_off_by_default_and_runs_when_enabled(api: Api) -> None:
    f = setup_finance(api)
    assert run_balance_verification_sweep(get_sessionmaker(), api.clock.now).verified == 0
    assert _ok(f.owner.get(f"{T}/balance-verification/runs"))["total"] == 0
    r = f.owner.post(
        f"{T}/policies/DATA_PROTECTION/versions",
        {
            "values": {"balance_verification_enabled": True, "balance_verification_interval_days": 7},
            "reason": "Weekly check",
            "scope": "TENANT",
        },
    )
    _ok(r, 201)
    assert run_balance_verification_sweep(get_sessionmaker(), api.clock.now).verified == 1
    assert run_balance_verification_sweep(get_sessionmaker(), api.clock.now).verified == 0  # interval not elapsed
    later = api.clock.now + timedelta(days=8)
    assert run_balance_verification_sweep(get_sessionmaker(), later).verified == 1
    runs = _ok(f.owner.get(f"{T}/balance-verification/runs"))["items"]
    assert len(runs) == 2 and runs[0]["trigger"] == "SCHEDULED"


def test_platform_sees_counts_only(api: Api) -> None:
    f = setup_finance(api)
    assert f.owner.get(f"{P}/balance-verification").status_code == 403
    run = _ok(api.platform.post(f"{P}/tenants/{f.tid}/balance-verification"), 201)
    assert "findings" not in run and run["trigger"] == "PLATFORM"
    listing = _ok(api.platform.get(f"{P}/balance-verification"))["items"]
    line = next(t for t in listing if t["tenant_id"] == f.tid)
    assert line["latest"]["id"] == run["id"] and "findings" not in line["latest"] and line["live_at"] is None


def test_go_live_marker_needs_permission_and_confirmation_and_is_audited(api: Api, owner_engine: Engine) -> None:
    f = setup_finance(api)
    tenant = _ok(api.platform.get(f"{P}/tenants/{f.tid}"))
    assert tenant["live_at"] is None
    assert f.owner.post(f"{P}/tenants/{f.tid}/go-live", {"confirm_name": tenant["display_name"]}).status_code == 403
    _err(api.platform.post(f"{P}/tenants/{f.tid}/go-live", {"confirm_name": "wrong"}), 422, "CONFIRMATION_MISMATCH")
    marked = _ok(
        api.platform.post(
            f"{P}/tenants/{f.tid}/go-live", {"confirm_name": tenant["display_name"], "note": "Contract signed"}
        )
    )
    assert marked["live_at"] is not None and marked["live_note"] == "Contract signed"
    _err(
        api.platform.post(f"{P}/tenants/{f.tid}/go-live", {"confirm_name": tenant["display_name"]}),
        409,
        "TENANT_ALREADY_LIVE",
    )
    events = _audit(owner_engine, f.tid, "platform.tenant.go_live")
    assert len(events) == 1 and events[0][1]["note"] == "Contract signed"


def test_reset_refuses_a_live_tenant_without_deliberate_override(
    api: Api, conn: psycopg.Connection[Any], rt: ModuleType, owner_engine: Engine
) -> None:
    f = setup_finance(api)
    name = _ok(api.platform.get(f"{P}/tenants/{f.tid}"))["display_name"]
    tenant = rt.find_tenant(conn, None, f.tid)
    assert tenant.live_at is None and rt.require_live_override(tenant, False) is None
    _ok(api.platform.post(f"{P}/tenants/{f.tid}/go-live", {"confirm_name": name}))
    tenant = rt.find_tenant(conn, None, f.tid)
    assert tenant.live_at is not None
    with pytest.raises(rt.Refuse, match="LIVE"):
        rt.require_live_override(tenant, False)
    with pytest.raises(rt.Refuse, match="does not match"):
        rt.require_live_override(tenant, True, typed="yes")
    override = rt.require_live_override(tenant, True, typed=f"ERASE LIVE {name}")
    plan = rt.classify(conn)
    rt.reset(conn, tenant, plan, "tester", backup_ref="b", objects=None, live_override=override)
    events = _audit(owner_engine, f.tid, "platform.tenant.data_reset")
    assert events and events[-1][1]["live_override"]["confirmation"] == f"ERASE LIVE {name}"
    assert "LIVE tenant data reset" in events[-1][2]
