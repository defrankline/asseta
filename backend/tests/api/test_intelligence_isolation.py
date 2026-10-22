"""Gate 6 tenant isolation (API + RLS as the application role) and database-level immutability of signals, case
links, notes and outcomes (no DELETE grant; guard triggers)."""

from datetime import timedelta

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError

from asseta.core.config import get_settings
from tests.support.api import Api
from tests.support.finance import setup_finance
from tests.support.intelligence import cases, signals, sweep
from tests.support.notify import member

TABLES = ("risk_signal", "anomaly_case", "anomaly_case_counter", "case_signal", "case_note", "case_outcome")


def _scope(conn: Connection, tid: str) -> None:
    conn.execute(text("SELECT set_config('app.scope','tenant',true), set_config('app.tenant_id',:t,true)"), {"t": tid})


def test_intelligence_isolation_and_immutability(api: Api) -> None:
    f = setup_finance(api, "Iso Co", "ISO-1")
    reviewer = member(api, f.tid, "manager", "reviewer-iso")
    f.accountant.post("/api/v1/tenant/cash/floats", {"staff_member_id": f.sup_staff_id, "amount": "250000"})
    api.clock.set_at(api.clock.now + timedelta(hours=72))
    sweep(api, f.tid)
    [case] = cases(f.owner)
    path = f"/api/v1/tenant/cases/{case['id']}"
    assert reviewer.post(f"{path}/notes", {"body": "Checking the float"}).status_code == 201
    resolved = reviewer.post(f"{path}/resolve", {"outcome": "UNCONFIRMED", "explanation": "Handover delayed."})
    assert resolved.status_code == 200, resolved.text
    [sig] = signals(f.owner)

    # --- API: another tenant sees nothing and cannot act on A's case ------------------------------------------
    b = api.onboard("Other Co", price="1000")
    ob, bid = b["owner"], b["tenant"]["id"]
    assert ob.get("/api/v1/tenant/cases").json()["total"] == 0
    assert ob.get("/api/v1/tenant/risk-signals").json()["total"] == 0
    assert ob.get(path).status_code == 404
    assert ob.post(f"{path}/notes", {"body": "sabotage"}).status_code == 404
    assert ob.post(f"{path}/reopen", {"reason": "sabotage attempt here"}).status_code == 404
    assert ob.get("/api/v1/tenant/cases", tenant=f.tid).json()["error"]["code"] == "TENANT_ACCESS_DENIED"
    assert api.platform.get("/api/v1/tenant/cases", tenant=f.tid).status_code == 403
    assert sweep(api, bid).signals == 0  # B's sweep never reads A's custody

    # --- RLS as the application role ---------------------------------------------------------------------------
    engine = create_engine(get_settings().database_url)
    count_all = " UNION ALL ".join(f"SELECT '{t}', count(*) FROM {t}" for t in TABLES)  # noqa: S608 (constants)
    with engine.begin() as conn:
        assert all(n == 0 for _, n in conn.execute(text(count_all)))  # no scope: nothing
        conn.execute(text("SELECT set_config('app.scope','platform',true)"))
        assert all(n == 0 for _, n in conn.execute(text(count_all)))
    with engine.begin() as conn:
        _scope(conn, bid)
        assert all(n == 0 for _, n in conn.execute(text(count_all)))
    with engine.begin() as conn:
        _scope(conn, f.tid)
        seen: dict[str, int] = dict(conn.execute(text(count_all)).tuples().all())
        assert all(seen[t] >= 1 for t in TABLES), seen
    with pytest.raises(DBAPIError, match="row-level security"), engine.begin() as conn:
        _scope(conn, bid)
        conn.execute(
            text(
                "INSERT INTO case_note (id, tenant_id, case_id, kind, body, created_at)"
                " VALUES (gen_random_uuid(), :a, :c, 'NOTE', 'forged', now())"
            ),
            {"a": f.tid, "c": case["id"]},
        )

    # --- immutability (application role, own tenant) -----------------------------------------------------------
    refused = [
        "UPDATE case_outcome SET outcome = 'CONFIRMED_ISSUE'",
        "DELETE FROM case_outcome",
        "UPDATE case_note SET body = 'edited'",
        "DELETE FROM case_signal",
        "UPDATE case_signal SET evidence = '{}'::jsonb",
        "DELETE FROM anomaly_case",
        "UPDATE anomaly_case SET subject_id = gen_random_uuid()",
        "UPDATE anomaly_case SET status = 'OPEN'",  # RESOLVED -> OPEN is not a transition
        "UPDATE anomaly_case SET status = 'IN_REVIEW', severity = 'INFO'",  # never lowered
        "UPDATE risk_signal SET evidence = '{}'::jsonb",
        "UPDATE risk_signal SET status = 'OPEN'",
        "DELETE FROM risk_signal",
    ]
    for stmt in refused:
        with (
            pytest.raises(DBAPIError, match=r"not permitted|immutable|permission denied|never lowered"),
            engine.begin() as conn,
        ):
            _scope(conn, f.tid)
            conn.execute(text(stmt))
    with engine.begin() as conn:
        _scope(conn, f.tid)
        assert conn.execute(text("SELECT outcome FROM case_outcome")).scalar_one() == "UNCONFIRMED"
        assert conn.execute(text("SELECT status FROM risk_signal WHERE id = :i"), {"i": sig["id"]}).scalar_one() == (
            "LINKED"
        )
    engine.dispose()
