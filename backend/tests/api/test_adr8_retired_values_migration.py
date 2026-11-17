# ruff: noqa: S608 - the SQL is built from this file's constants (table names, fixture ids), never from input
"""Migration adr8fix01: rows that still hold values the ADR-008 code no longer has are mapped or removed.

Live had real rows when adr8rm01 ran; its data steps ran as the migration role (FORCE row-level security) without a
scope and matched nothing. This test recreates that state: real records through the API, the database back at
crrej01 (the release with the bug), rows holding every retired value written as the RLS-bound owner role, the proof
that adr8rm01's statements are no-ops there and that a supervisor's sync pull crashes, then the upgrade and every
affected read."""

import json
import uuid
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, Engine, create_engine, text

from asseta.core.config import get_settings
from tests.support.api import Actor, Api
from tests.support.machine_reports import bought, ok, reading, setup_reports
from tests.support.notify import user_id

T = "/api/v1/tenant"
DEVICE = "android-retired-0001"
JOB_ID = str(uuid.uuid4())  # a job of the removed job table
RETIRED_POLICIES = {
    "HIRE_BILLING": {"rounding": "HALF_UP", "billable_hours_increment": "0.1", "invoice_void_requires_approval": True},
    "REVENUE_RECONCILIATION": {"enabled": True, "period": "WEEK", "recheck_days": 28},
}


def _cfg() -> Config:
    cfg = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    cfg.attributes["url"] = get_settings().migration_database_url
    return cfg


@pytest.fixture
def owner() -> Iterator[Engine]:
    engine = create_engine(get_settings().migration_database_url)  # asseta_owner: RLS-bound (FORCE), like live
    yield engine
    engine.dispose()
    command.upgrade(_cfg(), "head")  # whatever happened, the rest of the suite runs at head


def _h(actor: Actor) -> dict[str, str]:
    return {**actor.headers(True, None), "X-Device-Id": DEVICE}


def _push(api: Api, actor: Actor, op_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    op = {
        "id": str(uuid.uuid4()),
        "op_type": op_type,
        "payload": payload,
        "created_at_device": api.clock.now.isoformat(),
    }
    r = api.client.post(
        "/api/v1/sync/push", headers=_h(actor), json={"device_now": api.clock.now.isoformat(), "operations": [op]}
    )
    assert r.status_code == 200, r.text
    result: dict[str, Any] = r.json()["results"][0]
    return result


def _changes(api: Api, actor: Actor) -> Any:
    return api.client.get("/api/v1/sync/changes", headers=_h(actor), params={"cursor": 0})


def _copy(conn: Connection, table: str, where: str, **overrides: Any) -> None:
    """Insert a copy of one row of `table` with some columns replaced (a fresh id)."""
    conn.execute(
        text(
            f"INSERT INTO {table} SELECT (jsonb_populate_record(NULL::{table}, to_jsonb(t) || CAST(:o AS jsonb))).* "
            f"FROM {table} t WHERE {where} LIMIT 1"
        ),
        {"o": json.dumps({"id": str(uuid.uuid4()), **overrides})},
    )


def _seed_retired(conn: Connection, tid: str, machine_id: str, owner_user: uuid.UUID, captures: list[str]) -> None:
    """What live holds after adr8rm01's no-op data steps (written as asseta_owner under the system scope)."""
    conn.execute(text("SELECT set_config('app.scope', 'system', true)"))
    conn.execute(text("ALTER TABLE meter_capture DISABLE TRIGGER trg_meter_capture_guard"))
    for kind, capture_id in zip(("OPENING", "CLOSING"), captures, strict=True):
        conn.execute(text("UPDATE meter_capture SET kind = :k WHERE id = :i"), {"k": kind, "i": capture_id})
    conn.execute(text("ALTER TABLE meter_capture ENABLE TRIGGER trg_meter_capture_guard"))
    activated = f"tenant_id = '{tid}' AND entry_type = 'ACTIVATED'"
    for entry_type in ("PROVISIONAL", "PROVISIONAL_REVERSED"):
        _copy(
            conn,
            "hours_ledger_entry",
            activated,
            entry_type=entry_type,
            activation_source=None,
            expires_at=None,
            payment_id=None,
            hours="1.5",
        )
    conn.execute(
        text(
            "INSERT INTO financial_adjustment (id, tenant_id, customer_id, kind, amount, currency, reason, created_at) "
            "SELECT gen_random_uuid(), tenant_id, customer_id, 'INVOICE_REVERSAL', 85000, 'TZS', 'Invoice voided', "
            "now() - interval '1 day' FROM hours_ledger_entry WHERE " + activated + " LIMIT 1"
        )
    )
    common = (
        "tenant_id, severity, subject_type, subject_id, machine_id, policy_version, created_at",
        f"'{tid}', 'WARNING', 'JOB', '{JOB_ID}', '{machine_id}', 'v1', now()",
    )
    conn.execute(
        text(
            f"INSERT INTO risk_signal (id, rule_code, rule_version, window_start, window_end, evidence, dedupe_key, "
            f"involved_user_ids, involved_staff_ids, status, {common[0]}) VALUES (gen_random_uuid(), "
            f"'WORK_WITHOUT_AUTHORIZATION', 1, now(), now(), '{{}}', 'WWA:old', '{{}}', '{{}}', 'OPEN', {common[1]})"
        )
    )
    conn.execute(
        text(
            f"INSERT INTO anomaly_case (id, case_number, title, status, opened_at, last_signal_at, updated_at, version, "
            f"{common[0]}) VALUES (gen_random_uuid(), 'CASE-OLD-1', 'Work outside the job', 'OPEN', now(), now(), "
            f"now(), 1, {common[1]})"
        )
    )
    # Policy versions: platform and tenant rows of the retired types, plus current types carrying retired fields.
    conn.execute(text("ALTER TABLE policy_version NO FORCE ROW LEVEL SECURITY"))  # seeding a tenant row here
    rows = [
        ("HIRE_BILLING", None, RETIRED_POLICIES["HIRE_BILLING"]),
        ("REVENUE_RECONCILIATION", tid, RETIRED_POLICIES["REVENUE_RECONCILIATION"]),
        ("OVERSIGHT", tid, {"repeat_pattern_items": ["CASH_DIFFERENCE", "REVENUE_DIFFERENCE", "MISSED_CHECKIN"]}),
        ("CUSTOMER_HOURS", tid, {"drawdown": "DAILY", "billing_modes": ["PREPAID_HOURS"]}),
    ]
    for ptype, tenant, values in rows:
        conn.execute(
            text(
                "INSERT INTO policy_version (id, policy_type, scope, tenant_id, scope_ref_id, version, effective_from, "
                "values, reason, created_at, source) VALUES (gen_random_uuid(), :t, :s, :tid, NULL, 99, "
                "now() - interval '2 days', CAST(:v AS jsonb), 'Before ADR-008', now(), 'api')"
            ),
            {"t": ptype, "s": "TENANT" if tenant else "PLATFORM", "tid": tenant, "v": json.dumps(values)},
        )
    conn.execute(text("ALTER TABLE policy_version FORCE ROW LEVEL SECURITY"))
    conn.execute(
        text(
            'INSERT INTO feature_definition (id, code, version, entity, domain, "window", window_seconds, unit, '
            "description, inputs, created_at) VALUES (gen_random_uuid(), 'job_hours', 1, 'JOB', 'WORK', '7d', 604800, "
            "'h', 'Hours of a job', '[]', now())"
        )
    )
    conn.execute(
        text(
            "INSERT INTO feature_snapshot (id, tenant_id, entity_type, entity_id, feature_code, feature_version, as_of, "
            f"window_start, window_end, n_inputs, computed_at) VALUES (gen_random_uuid(), '{tid}', 'JOB', '{JOB_ID}', "
            "'job_hours', 1, now(), now() - interval '7 days', now(), 0, now())"
        )
    )
    # Notifications: two retired types (one with a delivery record), one current type opening a job, one current.
    for ntype, link, entity in (
        ("JOB_ASSIGNED", f"/tenant/field/jobs/{JOB_ID}", "job"),
        ("HOURS_OVERRUN", "/tenant/exceptions", None),
        ("APPROVAL_REQUESTED", f"/tenant/jobs/{JOB_ID}", "job"),
        ("APPROVAL_REQUESTED", "/tenant/approvals", None),
    ):
        conn.execute(
            text(
                "INSERT INTO notification (id, tenant_id, recipient_user_id, notification_type, category, severity, "
                "title, body, link, entity_type, entity_id, data, in_app, dedupe_key, created_at) VALUES "
                "(gen_random_uuid(), :tid, :u, :t, 'ACTION', 'INFO', :t, 'Before ADR-008', :l, :e, :j, '{}', true, "
                ":d, now())"
            ),
            {"tid": tid, "u": owner_user, "t": ntype, "l": link, "e": entity, "j": JOB_ID, "d": f"{ntype}:{link}"},
        )
    conn.execute(
        text(
            "INSERT INTO notification_delivery (id, tenant_id, notification_id, recipient_user_id, channel, destination,"
            " notification_type, severity, title, body, status, attempts, next_attempt_at, created_at, updated_at) "
            "SELECT gen_random_uuid(), tenant_id, id, recipient_user_id, 'EMAIL', 'owner@example.com', "
            "notification_type, severity, title, body, 'SENT', 1, now(), now(), now() FROM notification "
            "WHERE notification_type = 'HOURS_OVERRUN'"
        )
    )
    conn.execute(
        text(
            "INSERT INTO notification_preference (id, tenant_id, scope_key, user_id, notification_type, in_app, sms, "
            "updated_at) VALUES (gen_random_uuid(), CAST(:tid AS uuid), :tid, :u, 'JOB_ASSIGNED', true, false, now())"
        ),
        {"tid": tid, "u": owner_user},
    )
    # A job activity a pre-ADR-008 phone had queued, kept as a sync conflict for review.
    conn.execute(
        text(
            "INSERT INTO client_operation (id, tenant_id, device_session_id, op_type, payload_sha256, payload, status, "
            "result, created_at_device, received_at, attempts) SELECT gen_random_uuid(), tenant_id, id, "
            "'JOB_ACTIVITY', repeat('0', 64), '{}', 'CONFLICT', '{\"error\": {\"code\": \"JOB_NOT_ACTIVE\"}}', now(), "
            "now(), 1 FROM device_session WHERE tenant_id = :tid LIMIT 1"
        ),
        {"tid": tid},
    )


def _count(conn: Connection, sql: str, **params: Any) -> int:
    return int(conn.execute(text(sql), params).scalar_one())


def test_retired_values_are_mapped_or_removed(api: Api, owner: Engine) -> None:
    ctx = setup_reports(api, "Retired Co", "RET-1")
    f = ctx.f
    tid, machine_id = f.tid, ctx.machine_id
    bought(api, f, 10)
    r = api.client.post(
        "/api/v1/sync/devices",
        headers=_h(f.supervisor),
        json={"device_id": DEVICE, "platform": "ANDROID", "app_version": "0.5.7"},
    )
    assert r.status_code == 201, r.text
    captures = []
    for i, value in enumerate(("1002", "1005")):
        at = api.clock.now - timedelta(hours=3 - i)
        payload = reading(machine_id, value, at)
        result = _push(api, f.supervisor, "METER_CAPTURE", payload)
        assert result["status"] == "ACKED", result
        captures.append(payload["id"])
    ok(f.owner.get(f"{T}/notifications"))  # the owner's login exists (app_user)
    owner_user = user_id(f.owner.subject)

    command.downgrade(_cfg(), "crrej01")
    with owner.begin() as conn:
        _seed_retired(conn, tid, machine_id, owner_user, captures)
    with owner.begin() as conn:  # adr8rm01's statements, as it ran on live: no scope -> nothing matches
        assert conn.execute(text("UPDATE meter_capture SET kind = 'DAILY' WHERE kind = 'OPENING'")).rowcount == 0
        conn.execute(text("SELECT set_config('app.scope', 'system', true)"))  # no DELETE policy on policy_version
        assert conn.execute(text("DELETE FROM policy_version WHERE policy_type = 'HIRE_BILLING'")).rowcount == 0
        conn.rollback()
    assert _changes(api, f.supervisor).status_code == 500  # the production crash (LookupError: 'OPENING')

    command.upgrade(_cfg(), "head")
    with owner.begin() as conn:
        conn.execute(text("SELECT set_config('app.scope', 'system', true)"))
        kinds = conn.execute(text("SELECT kind FROM meter_capture WHERE id = ANY(:i)"), {"i": captures}).scalars()
        assert set(kinds) == {"DAILY"}
        for table in ("risk_signal", "anomaly_case"):
            row = conn.execute(text(f"SELECT subject_type, subject_id FROM {table} WHERE tenant_id = :t"), {"t": tid})
            assert [(s, str(i)) for s, i in row] == [("MACHINE", machine_id)]
        gone = {
            "hours_ledger_entry": "entry_type IN ('PROVISIONAL', 'PROVISIONAL_REVERSED')",
            "financial_adjustment": "kind = 'INVOICE_REVERSAL'",
            "feature_snapshot": "entity_type = 'JOB'",
            "notification_preference": "notification_type = 'JOB_ASSIGNED'",
        }
        for table, where in gone.items():
            assert _count(conn, f"SELECT count(*) FROM {table} WHERE {where}") == 0, table
        assert _count(conn, "SELECT count(*) FROM feature_definition WHERE entity = 'JOB'") == 0
        assert _count(conn, "SELECT count(*) FROM hours_ledger_entry WHERE tenant_id = :t", t=tid) >= 1  # kept
        assert (
            _count(
                conn,
                "SELECT count(*) FROM policy_version WHERE policy_type IN ('HIRE_BILLING', 'REVENUE_RECONCILIATION')",
            )
            == 0
        )
        notes = conn.execute(
            text("SELECT notification_type, in_app, link, entity_type FROM notification WHERE tenant_id = :t"),
            {"t": tid},
        ).all()
        by = {(n.notification_type, n.in_app, n.link, n.entity_type) for n in notes}
        assert ("JOB_ASSIGNED", True, f"/tenant/field/jobs/{JOB_ID}", "job") not in by  # deleted
        assert ("HOURS_OVERRUN", False, None, None) in by  # kept for its delivery record, hidden
        assert ("APPROVAL_REQUESTED", True, "/tenant/approvals", None) in by  # untouched
        assert not [n for n in notes if n.link and "/jobs" in n.link]
        assert _count(conn, "SELECT count(*) FROM client_operation WHERE op_type = 'JOB_ACTIVITY'") == 1  # history

    changes = _changes(api, f.supervisor)
    assert changes.status_code == 200, changes.text
    inbox = changes.json()["data"]
    pulled = {c["id"]: c["kind"] for c in inbox["my_meter_captures"]}
    assert set(captures) <= set(pulled) and set(pulled.values()) == {"DAILY"}
    inbox_items = ok(f.owner.get(f"{T}/notifications"))["items"]
    assert {n["type"] for n in inbox_items} == {"APPROVAL_REQUESTED"}
    assert [s["subject_type"] for s in ok(f.owner.get(f"{T}/risk-signals"))["items"]] == ["MACHINE"]
    [case] = ok(f.owner.get(f"{T}/cases"))["items"]
    assert case["subject_type"] == "MACHINE"
    ok(f.owner.get(f"{T}/cases/{case['id']}"))
    ledger = ok(f.owner.get(f"{T}/hours-ledger"))["items"]
    assert ledger and {e["entry_type"] for e in ledger} == {"ACTIVATED"}
    ok(f.owner.get(f"{T}/customers/{f.customer_id}/hours-statement"))
    ok(f.owner.get(f"{T}/customer-hours"))
    day = api.clock.now.date()
    ok(
        f.owner.get(
            f"{T}/customers/{f.customer_id}/statement", **{"from": str(day - timedelta(days=30)), "to": str(day)}
        )
    )
    ok(f.owner.get(f"{T}/adjustments"))
    ok(f.owner.get(f"{T}/exceptions"))
    ok(f.owner.get(f"{T}/meter-captures"))
    conflicts = ok(f.owner.get(f"{T}/sync/conflicts"))["items"]
    assert [c["op_type"] for c in conflicts] == ["JOB_ACTIVITY"]
    for ptype in ("OVERSIGHT", "CUSTOMER_HOURS", "METER_CAPTURE", "ENGINE_HOURS"):
        ok(f.owner.get(f"{T}/policies/{ptype}/versions"))
        ok(f.owner.get(f"{T}/policies/{ptype}/effective"))


def test_retired_sync_operations_are_refused_one_by_one(api: Api) -> None:
    """A phone still on a pre-ADR-008 app: its job and check-in operations are REJECTED (OPERATION_RETIRED), an
    unknown type UNKNOWN_OPERATION, an opening reading fails validation; the rest of the batch applies and a retry is
    a DUPLICATE."""
    ctx = setup_reports(api, "Old Phone Co", "OLD-1")
    f = ctx.f
    r = api.client.post(
        "/api/v1/sync/devices",
        headers=_h(f.supervisor),
        json={"device_id": DEVICE, "platform": "ANDROID", "app_version": "0.5.7"},
    )
    assert r.status_code == 201, r.text
    now = api.clock.now
    old_opening = {**reading(ctx.machine_id, "1001", now - timedelta(hours=2)), "kind": "OPENING", "job_id": JOB_ID}
    ops = [
        ("JOB_ACTIVITY", {"job_id": JOB_ID, "activity_type": "WORK"}),
        ("JOB_TRANSITION", {"job_id": JOB_ID, "action": "COMPLETE"}),
        ("SITE_CHECKIN", {"client_id": str(uuid.uuid4())}),
        ("TELEPORT", {}),
        ("METER_CAPTURE", old_opening),
        ("METER_CAPTURE", reading(ctx.machine_id, "1003", now - timedelta(hours=1))),
    ]
    batch = [
        {"id": str(uuid.uuid4()), "op_type": t, "payload": p, "created_at_device": now.isoformat()} for t, p in ops
    ]
    body = {"device_now": now.isoformat(), "operations": batch}
    r = api.client.post("/api/v1/sync/push", headers=_h(f.supervisor), json=body)
    assert r.status_code == 200, r.text
    results = r.json()["results"]
    codes = [(x["status"], (x["error"] or {}).get("code")) for x in results]
    assert codes == [
        ("REJECTED", "OPERATION_RETIRED"),
        ("REJECTED", "OPERATION_RETIRED"),
        ("REJECTED", "OPERATION_RETIRED"),
        ("REJECTED", "UNKNOWN_OPERATION"),
        ("REJECTED", "VALIDATION_FAILED"),
        ("ACKED", None),
    ]
    again = api.client.post("/api/v1/sync/push", headers=_h(f.supervisor), json=body)
    assert again.status_code == 200, again.text
    assert [x["status"] for x in again.json()["results"]] == ["DUPLICATE"] * 6
    rejected = ok(f.owner.get(f"{T}/sync/conflicts", status="REJECTED"))["items"]
    assert {"JOB_ACTIVITY", "JOB_TRANSITION", "SITE_CHECKIN", "TELEPORT"} <= {c["op_type"] for c in rejected}
    assert _changes(api, f.supervisor).status_code == 200
