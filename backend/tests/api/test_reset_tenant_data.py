"""Tenant data reset before go-live (backend/scripts/reset_tenant_data.py): a tenant with data across the modules
and a second tenant; the dry run changes nothing; the reset erases every business row of the tenant (and nothing of
the other tenant), keeps the subscription/platform billing, memberships, staff and the platform audit, leaves the
platform policy defaults, revokes the phones so they wipe and bootstrap afresh, records the platform audit event,
and refuses to run when the schema holds a tenant-scoped table nobody classified."""

import importlib.util
import io
import json
import sys
import uuid
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

import psycopg
import pytest
from sqlalchemy import Engine

from asseta.core.config import get_settings
from asseta.tools.gps_simulator import Fix
from tests.support.api import Actor, Api
from tests.support.finance import category, complete_job, expense_policy, issue_invoice, setup_finance
from tests.support.jobs import unique_jpeg
from tests.support.telemetry import Telemetry

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "reset_tenant_data.py"
DEVICE = "android-reset-device"


@pytest.fixture(scope="module")
def rt() -> ModuleType:
    spec = importlib.util.spec_from_file_location("reset_tenant_data", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["reset_tenant_data"] = module  # dataclasses resolve their module by name
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def conn(owner_engine: Engine) -> Iterator[psycopg.Connection[Any]]:
    url = get_settings().migration_database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(url, autocommit=True) as c:
        yield c


class FakeStore:
    def __init__(self, keys: list[str]):
        self.keys = set(keys)

    def list_keys(self, prefix: str) -> list[str]:
        return sorted(k for k in self.keys if k.startswith(prefix))

    def delete_keys(self, keys: list[str]) -> int:
        self.keys -= set(keys)
        return len(keys)


def counts(conn: psycopg.Connection[Any], rt: ModuleType, where: str, tid: str) -> dict[str, int]:
    """Rows per discovered tenant-scoped table (+ the specials) for `tenant_id = tid` or `<> tid`."""
    out: dict[str, int] = {}
    with conn.transaction(force_rollback=True):
        conn.execute("SELECT set_config('app.scope', 'system', true)")
        for table, has_tid in conn.execute(rt.DISCOVER).fetchall():
            if has_tid:
                query = f"SELECT count(*) FROM {table} WHERE tenant_id {where} %s"  # noqa: S608 - catalog names
                row = conn.execute(query, (tid,)).fetchone()
                out[table] = row[0] if row else 0
    return out


def q(conn: psycopg.Connection[Any], query: str, *params: Any) -> list[tuple[Any, ...]]:
    """A query in the system scope (the owner role is subject to the forced row-level security too)."""
    with conn.transaction(force_rollback=True):
        conn.execute("SELECT set_config('app.scope', 'system', true)")
        return conn.execute(query, params).fetchall()


def _h(actor: Actor) -> dict[str, str]:
    return {**actor.headers(True, None), "X-Device-Id": DEVICE}


def _seed_tenant(api: Api) -> dict[str, Any]:
    """Data across the modules: fleet + tracker + telemetry, jobs with readings and work logs, hire invoice and
    payment, expenses and cash custody, policies, platform invoice over enrolled machines, a phone in sync."""
    f = setup_finance(api, "Demo Hire", "DEMO-1")
    owner, tid = f.owner, f.tid
    complete_job(api, f, f.c.job_id, "500.0", "508.0", 9, downtime_h=1)
    issue_invoice(f, [f.c.job_id])
    assert (
        f.accountant.post(
            "/api/v1/tenant/customer-payments",
            {
                "customer_id": f.customer_id,
                "amount": "1000",
                "method": "BANK",
                "reference": "D-1",
                "received_at": api.clock.now.isoformat(),
            },
        ).status_code
        == 201
    )
    cat = category(f, "SPARES", "Spares")
    expense_policy(f, receipt_required_above="100000000", gps_required=False, auto_approve_limit="0")
    assert (
        f.supervisor.post(
            "/api/v1/tenant/expenses",
            {
                "category_id": cat,
                "description": "x",
                "amount": "500",
                "incurred_at": api.clock.now.isoformat(),
                "paid_from": "CASH_CUSTODY",
            },
        ).status_code
        == 201
    )
    f.accountant.post("/api/v1/tenant/cash/floats", {"staff_member_id": f.sup_staff_id, "amount": "5000"})
    f.supervisor.post("/api/v1/tenant/cash/handovers", {"amount": "100", "handed_at": api.clock.now.isoformat()})
    site = owner.post(
        "/api/v1/tenant/job-sites",
        {"code": "S1", "name": "Site 1", "center": {"type": "Point", "coordinates": [39.28, -6.8]}},
    )
    assert site.status_code == 201, site.text
    # Telemetry through the gateway (positions, latest position, ingestion events).
    tel = _telemetry(api)
    assert tel.send("DEMO-1", Fix(api.clock.now - timedelta(minutes=5), -6.8, 39.28, 0.0, 0.0))["accepted"] == 1
    # Two more machines enrolled mid-period (proration charges), then the next platform invoice bills them.
    sid = f.c.t.tenant["subscription_id"]
    api.generate(sid, api.clock.now.date())
    api.clock.set(date(2026, 11, 21))
    api.add_machines(owner, 2, enroll_on=date(2026, 11, 21), prefix="DMO")
    api.clock.set(date(2026, 12, 1))
    api.generate(sid, date(2026, 12, 1))
    # A phone in sync, with an uploaded photo.
    reg = api.client.post(
        "/api/v1/sync/devices",
        headers=_h(f.supervisor),
        json={"device_id": DEVICE, "platform": "ANDROID", "app_version": "1.0.0"},
    )
    assert reg.status_code == 201, reg.text
    boot = api.client.get("/api/v1/sync/bootstrap", headers=_h(f.supervisor))
    assert boot.status_code == 200 and boot.json()["data"]["machines"], boot.text
    data = unique_jpeg()
    import hashlib

    s = api.client.post(
        "/api/v1/sync/blobs",
        headers=_h(f.supervisor),
        json={"sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data), "purpose": "METER_PHOTO"},
    ).json()
    api.client.put(f"/api/v1/sync/blobs/{s['id']}/chunks/0", headers=_h(f.supervisor), content=data)
    assert api.client.post(f"/api/v1/sync/blobs/{s['id']}/complete", headers=_h(f.supervisor)).status_code == 200
    return {"f": f, "tid": tid, "cursor": boot.json()["cursor"], "owner": owner}


def _telemetry(api: Api) -> Telemetry:
    """The helper of the tracker model setup_job already registered, with a gateway key of its own."""
    tel = Telemetry.__new__(Telemetry)
    tel.api = api
    tel.model_id = api.platform.get("/api/v1/platform/tracker-models").json()[0]["id"]
    g = api.platform.post(
        "/api/v1/platform/telemetry-gateways", {"name": f"traccar-{uuid.uuid4().hex[:8]}", "adapter": "TRACCAR"}
    )
    assert g.status_code == 201, g.text
    tel.key = g.json()["gateway_key"]
    return tel


def test_reset_erases_one_tenant_keeps_the_rest_and_phones_start_afresh(
    api: Api, conn: psycopg.Connection[Any], rt: ModuleType, tmp_path: Path
) -> None:
    seeded = _seed_tenant(api)
    f, tid, owner = seeded["f"], seeded["tid"], seeded["owner"]
    other = _telemetry(api).tracked_machine("Other Hire", "OTHER-1")
    other_tid = other.tenant["tenant"]["id"]
    assert other.owner.post("/api/v1/tenant/customers", {"code": "C1", "name": "Their customer"}).status_code == 201
    store = FakeStore(
        [
            f"tenants/{tid}/evidence/a",
            f"tenants/{tid}/machines/m/photos/b",
            f"platform/ml-models/{tid}/x/1.pkl",
            f"tenants/{other_tid}/evidence/c",
            "platform/ml-models/other/1.pkl",
        ]
    )

    mine = counts(conn, rt, "=", tid)
    theirs = counts(conn, rt, "<>", tid)
    populated = {t for t in rt.DELETE if mine.get(t)}
    assert len(populated) >= 30, sorted(populated)  # really across the modules
    for must in ("machine", "tracker", "machine_position_event", "job", "meter_capture", "hire_invoice_line",
                 "customer_payment", "expense", "supervisor_cash_custody", "policy_version", "job_site",
                 "subscription_asset_enrollment", "capture_attachment", "blob_upload_session", "outbox_event"):  # fmt: skip
        assert mine.get(must, 0) > 0, must
    platform_policies = q(conn, "SELECT count(*) FROM policy_version WHERE tenant_id IS NULL")

    # --- dry run: reports, changes nothing ------------------------------------------------------------------------
    tenant = rt.find_tenant(conn, None, tid)
    with conn.transaction(force_rollback=True):
        plan = rt.classify(conn)
        report = rt.measure(conn, tenant, plan, store)
    assert report.objects == 3 and report.devices == 1 and report.invoice_lines_detached >= 1
    assert report.delete_counts["machine"] == mine["machine"] == 3
    assert [x[1] for x in report.trackers] == ["DEMO-1"]
    out = io.StringIO()
    rt.print_report(report, out)
    assert "WOULD DELETE" in out.getvalue() and "Demo Hire" in out.getvalue()
    assert counts(conn, rt, "=", tid) == mine and len(store.keys) == 5

    # --- the reset ------------------------------------------------------------------------------------------------
    result = rt.reset(conn, tenant, plan, "ops@host", backup_ref="20261028T000000Z", objects=report.objects)
    assert rt.delete_objects(store, tenant.id) == 3
    assert store.keys == {f"tenants/{other_tid}/evidence/c", "platform/ml-models/other/1.pkl"}
    assert result.total_deleted > 50
    # A second run would find nothing more to delete.
    with conn.transaction(force_rollback=True):
        again_report = rt.measure(conn, tenant, rt.classify(conn), None)
    assert again_report.total_deleted == 0

    after = counts(conn, rt, "=", tid)
    assert {t: n for t, n in after.items() if t in rt.DELETE and n} == {}
    for t in rt.KEEP:
        assert after[t] == mine[t], t
    assert after["platform_invoice_line"] == mine["platform_invoice_line"]
    assert after["tenant_membership"] > 0 and after["staff_member"] == mine["staff_member"] > 0
    assert after["tenant_subscription"] == 1 and after["platform_invoice"] >= 1
    assert counts(conn, rt, "<>", tid) == {**theirs, "audit_event": theirs["audit_event"]}
    assert q(conn, "SELECT count(*) FROM policy_version WHERE tenant_id IS NULL") == platform_policies
    assert platform_policies[0][0] > 5
    actions = [r[0] for r in q(conn, "SELECT action FROM audit_event WHERE tenant_id = %s", tid)]
    assert actions and all(a.startswith(("platform.", "billing.")) for a in actions)
    [(details,)] = q(
        conn, "SELECT after FROM audit_event WHERE tenant_id = %s AND action = 'platform.tenant.data_reset'", tid
    )
    assert (
        details["operator"] == "ops@host" and details["deleted"]["machine"] == 3 and details["objects_to_delete"] == 3
    )
    # Guard triggers and forced RLS are back on.
    assert conn.execute(
        "SELECT bool_and(tgenabled = 'O') FROM pg_trigger WHERE tgname = 'trg_audit_event_immutable'"
    ).fetchone() == (True,)
    assert conn.execute("SELECT relforcerowsecurity FROM pg_class WHERE relname = 'machine'").fetchone() == (True,)

    # --- the platform sees the reset (the demo seeder refuses such a tenant) ----------------------------------------
    seen = api.platform.get(
        "/api/v1/platform/audit-events", tenant_id=tid, action_prefix="platform.tenant.data_reset"
    ).json()
    assert seen["total"] == 1

    # --- the tenant works on, empty --------------------------------------------------------------------------------
    assert owner.get("/api/v1/tenant/machines", include_inactive="true").json()["total"] == 0
    assert owner.post("/api/v1/tenant/machines", {"asset_code": "REAL-1", "name": "Real machine"}).status_code == 201
    assert other.owner.get("/api/v1/tenant/machines").json()["total"] == 1

    # --- phones: wipe, sign in again, fresh bootstrap ------------------------------------------------------------
    sup = f.supervisor
    stale = api.client.get("/api/v1/sync/changes", headers=_h(sup), params={"cursor": seeded["cursor"]})
    assert stale.status_code == 403 and stale.json()["error"]["code"] == "DEVICE_REVOKED", stale.text
    again = api.client.post(
        "/api/v1/sync/devices", headers=_h(sup), json={"device_id": DEVICE, "platform": "ANDROID", "app_version": "1"}
    )
    assert again.status_code == 201, again.text  # a reset revocation does not lock the phone out
    # An app that registered but still holds the old cursor (Android registers first) is told to wipe ...
    demo_op = {
        "id": str(uuid.uuid4()),
        "op_type": "JOB_TRANSITION",
        "payload": {"job_id": f.c.job_id, "action": "START"},
        "created_at_device": api.clock.now.isoformat(),
        "depends_on": [],
    }
    for r in (
        api.client.get("/api/v1/sync/changes", headers=_h(sup), params={"cursor": seeded["cursor"]}),
        api.client.post(
            "/api/v1/sync/push",
            headers=_h(sup),
            json={"device_now": api.clock.now.isoformat(), "operations": [demo_op]},
        ),
    ):
        assert r.status_code == 403 and r.json()["error"]["code"] == "DEVICE_REVOKED", r.text
    # ... and after the wipe it bootstraps afresh, then syncs normally.
    boot = api.client.get("/api/v1/sync/bootstrap", headers=_h(sup))
    assert boot.status_code == 200 and boot.json()["data"]["machines"] == [] and boot.json()["data"]["jobs"] == []
    delta = api.client.get("/api/v1/sync/changes", headers=_h(sup), params={"cursor": boot.json()["cursor"]})
    assert delta.status_code == 200, delta.text

    # --- demo seeder state moved aside (only this tenant's) ---------------------------------------------------------
    (tmp_path / "demo-wambura-state.json").write_text(json.dumps({"tenant_id": tid}))
    (tmp_path / "demo-other-state.json").write_text(json.dumps({"tenant_id": other_tid}))
    moved = rt.retire_demo_state(tmp_path, tenant.id, datetime(2026, 10, 28, tzinfo=UTC))
    assert len(moved) == 1 and not (tmp_path / "demo-wambura-state.json").exists()
    assert (tmp_path / "demo-other-state.json").exists()


def test_unclassified_tenant_table_stops_the_run_and_platform_scope_is_refused(
    api: Api, conn: psycopg.Connection[Any], rt: ModuleType
) -> None:
    with conn.transaction(force_rollback=True):
        conn.execute("CREATE TABLE zz_new_module (id uuid PRIMARY KEY, tenant_id uuid NOT NULL)")
        with pytest.raises(rt.Unclassified) as refused:
            rt.classify(conn)
        assert refused.value.tables == ["zz_new_module"]
    with conn.transaction(force_rollback=True):
        conn.execute("CREATE TABLE zz_rls_only (id uuid PRIMARY KEY)")
        conn.execute("ALTER TABLE zz_rls_only ENABLE ROW LEVEL SECURITY")
        with pytest.raises(rt.Unclassified, match="zz_rls_only"):
            rt.classify(conn)
    with pytest.raises(rt.Refuse, match="platform"):
        rt.find_tenant(conn, None, str(uuid.UUID(int=0)))
    with pytest.raises(rt.Refuse, match="no tenant"):
        rt.find_tenant(conn, "2099/99/9999", None)
