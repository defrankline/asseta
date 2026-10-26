"""DEC-030 follow-up: the ENGINE_HOURS and CASH_CUSTODY master switches (F1) and field users opening their own
overdue-remittance flag (F2). A switched-off capability hides its menus and dashboard tiles, refuses its endpoints
(422, <CAPABILITY>_DISABLED) and offline operations (CONFLICT, same code), is no longer announced to devices and its
sweeps do nothing — while the behaviour that existed before it keeps working."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from asseta.core.db import get_sessionmaker
from asseta.modules.finance.remittance_cutoff import run_remittance_cutoff
from tests.support.api import Actor, Api
from tests.support.finance import FinCtx, cash_policy, role, setup_finance
from tests.support.intelligence import sweep
from tests.support.jobs import capture, engine_hours_policy
from tests.support.notify import sql

T = "/api/v1/tenant"
C = f"{T}/cash"
T0 = "2026-11-01T06:00:00+00:00"  # 09:00 tenant-local (Africa/Dar_es_Salaam)
T1 = "2026-11-01T07:00:00+00:00"
AFTER_CUTOFF = datetime(2026, 11, 1, 16, 0, tzinfo=UTC)  # 19:00 local
DEVICE = "android-switch-0001"


def _ok(r: Any, status: int = 200) -> Any:
    assert r.status_code == status, r.text
    return r.json()


def _refused(r: Any, code: str) -> None:
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == code


def _nav(actor: Actor) -> dict[str, Any]:
    return dict(_ok(actor.get("/api/v1/me"))["tenants"][0])


def _h(actor: Actor) -> dict[str, str]:
    return {**actor.headers(True, None), "X-Device-Id": DEVICE}


def _device(api: Api, actor: Actor) -> list[str]:
    _ok(
        api.client.post(
            "/api/v1/sync/devices",
            headers=_h(actor),
            json={"device_id": DEVICE, "platform": "ANDROID", "app_version": "1.4.0"},
        ),
        201,
    )
    return list(_ok(api.client.get("/api/v1/sync/bootstrap", headers=_h(actor)))["capabilities"])


def _push(api: Api, actor: Actor, *ops: dict[str, Any]) -> list[dict[str, Any]]:
    r = api.client.post(
        "/api/v1/sync/push",
        headers=_h(actor),
        json={"device_now": api.clock.now.isoformat(), "operations": list(ops)},
    )
    assert r.status_code == 200, r.text
    return list(r.json()["results"])


def _op(op_type: str, payload: dict[str, Any], at: str = T1) -> dict[str, Any]:
    return {"id": str(uuid.uuid4()), "op_type": op_type, "payload": payload, "created_at_device": at, "depends_on": []}


def _reading(job_id: str | None, machine_id: str, kind: str, value: str, at: datetime) -> dict[str, Any]:
    body = capture(job_id or "", kind, value, at, mode="MANUAL")
    if job_id is None:
        body.pop("job_id")
    body["machine_id"] = machine_id
    return body


def _staff(f: FinCtx, name: str, subject: str | None = None) -> str:
    body: dict[str, Any] = {"full_name": name, "kind": "SUPERVISOR" if subject else "OPERATOR"}
    if subject:
        body["keycloak_subject"] = subject
    return str(_ok(f.owner.post(f"{T}/staff", body), 201)["id"])


# --- ENGINE_HOURS ----------------------------------------------------------------------------------------------
def test_engine_hours_switched_off_keeps_the_job_meter_flow_from_before(api: Api) -> None:
    f = setup_finance(api, "Switch Engines", "SWE-1")
    o, sup, c, machine = f.owner, f.supervisor, f.c, f.c.t.machine_id
    t0 = api.clock.now
    nav = _nav(o)
    assert nav["disabled_capabilities"] == ["REVENUE_RECONCILIATION"] and "tenant.engine_hours" in {
        g["key"] for g in nav["menu_groups"]
    }
    assert "OP_METER_BASELINE" in _device(api, sup)

    # Switched off, with its controls still configured on underneath: the master switch wins.
    engine_hours_policy(o, enabled=False, baseline_required_before_start=True, daily_report_required=True)
    nav = _nav(o)
    assert nav["disabled_capabilities"] == ["ENGINE_HOURS", "REVENUE_RECONCILIATION"]
    assert "tenant.engine_hours" not in {g["key"] for g in nav["menu_groups"]}
    keys = {m["key"] for m in nav["menus"]}
    assert not keys & {"tenant.engine_hours", "tenant.meter_baselines", "tenant.meter_corrections"}
    assert {"tenant.jobs", "tenant.exceptions", "tenant.cash_custody"} <= keys  # the rest is untouched

    # Its endpoints are refused, reads included.
    _refused(o.get(f"{T}/meter-baselines"), "ENGINE_HOURS_DISABLED")
    _refused(o.get(f"{T}/engine-hours/machines/{machine}"), "ENGINE_HOURS_DISABLED")
    _refused(o.get(f"{T}/meter-corrections"), "ENGINE_HOURS_DISABLED")
    body = {"machine_id": machine, "reading": "999", "captured_at": t0.isoformat()}
    _refused(o.post(f"{T}/meter-baselines", body), "ENGINE_HOURS_DISABLED")
    _refused(o.post(f"{T}/meter-captures", _reading(None, machine, "DAILY", "1001", t0)), "ENGINE_HOURS_DISABLED")
    outsider = role(api, f.tid, "operator", "swe-operator")
    assert outsider.post(f"{T}/meter-baselines", body).status_code == 403  # the permission is checked first

    # Job meter readings work exactly as before: START without an approved baseline, then a closing reading.
    _ok(o.post(f"{T}/meter-captures", _reading(c.job_id, machine, "OPENING", "1000", t0)), 201)
    _ok(o.post(f"{T}/jobs/{c.job_id}/transitions", {"action": "START"}))
    api.clock.set_at(t0 + timedelta(hours=3))
    _ok(o.post(f"{T}/meter-captures", _reading(c.job_id, machine, "CLOSING", "1003", api.clock.now)), 201)

    # Sweeps do nothing: a running machine without a reading past the next day's cut-off is not flagged.
    api.clock.set_at(t0 + timedelta(days=1, hours=8))
    sweep(api, f.tid)
    flags = sql(
        "SELECT count(*) FROM job_exception WHERE tenant_id = :t AND exception_type IN"
        " ('MISSING_DAILY_REPORT', 'UNEXPLAINED_HOURS', 'OVERLAPPING_ALLOCATION')",
        t=f.tid,
    )
    assert flags[0][0] == 0

    # Its dashboard tiles are hidden.
    summary = _ok(o.get(f"{T}/accountability/summary"))
    assert {"engine_hours", "unexplained_hours", "missing_daily_reports"} <= set(summary["hidden_tiles"])
    assert summary["engine_hours"] is None and summary["disabled_capabilities"] == [
        "ENGINE_HOURS",
        "REVENUE_RECONCILIATION",
    ]
    assert summary["cash"] is not None

    # Devices: its operations are no longer announced, and queued ones are refused for review (never applied).
    caps = _ok(api.client.get("/api/v1/sync/bootstrap", headers=_h(sup)))["capabilities"]
    assert not {"OP_METER_BASELINE", "OP_METER_CORRECTION", "METER_DAILY_READING"} & set(caps)
    assert {"OP_CASH_TRANSFER", "OP_JOB_REQUEST"} <= set(caps)
    at = api.clock.now
    baseline = _op("METER_BASELINE", {"machine_id": machine, "reading": "1003", "captured_at": at.isoformat()})
    daily = _op("METER_CAPTURE", _reading(None, machine, "DAILY", "1003.5", at))
    results = _push(api, sup, baseline, daily)
    assert [(r["status"], r["error"]["code"]) for r in results] == [("CONFLICT", "ENGINE_HOURS_DISABLED")] * 2
    assert sql("SELECT count(*) FROM machine_meter_baseline WHERE tenant_id = :t", t=f.tid)[0][0] == 0

    # Back on: everything returns.
    engine_hours_policy(o, enabled=True)
    _ok(o.get(f"{T}/meter-baselines"))
    assert "tenant.engine_hours" in {g["key"] for g in _nav(o)["menu_groups"]}


# --- CASH_CUSTODY ----------------------------------------------------------------------------------------------
def test_cash_custody_switched_off_keeps_the_cash_basics(api: Api) -> None:
    f = setup_finance(api, "Switch Cash", "SWC-1")
    sup, acct, acct2, o = f.supervisor, f.accountant, f.accountant2, f.owner
    operator = _staff(f, "Operator Neema")
    assert "OP_CASH_TRANSFER" in _device(api, sup)
    cash_policy(
        f,
        enabled=False,
        recorders_may_record_for_others=True,
        float_ack_required=True,
        remit_full_balance=True,
        remittance_cutoff_hour=17,
        variance_case_threshold="0",
    )
    nav = _nav(o)
    assert nav["disabled_capabilities"] == ["CASH_CUSTODY", "REVENUE_RECONCILIATION"]
    assert "tenant.cash_custody" in {m["key"] for m in nav["menus"]}  # the cash basics keep their page

    # The DEC-030 additions are refused.
    transfer = {"from_staff_id": f.sup_staff_id, "to_staff_id": operator, "amount": "10", "transferred_at": T1}
    _refused(sup.post(f"{C}/transfers", transfer), "CASH_CUSTODY_DISABLED")
    _refused(acct.get(f"{C}/transfers"), "CASH_CUSTODY_DISABLED")
    _refused(acct.get(f"{C}/variances"), "CASH_CUSTODY_DISABLED")
    _refused(sup.post(f"{C}/retentions", {"amount": "5", "reason": "Fuel"}), "CASH_CUSTODY_DISABLED")
    _refused(acct.get(f"{C}/retentions"), "CASH_CUSTODY_DISABLED")
    _refused(acct.get(f"{C}/adjustments"), "CASH_CUSTODY_DISABLED")
    _refused(acct.get(f"{C}/reasons"), "CASH_CUSTODY_DISABLED")
    _refused(acct.get(f"{C}/remittance-overdue"), "CASH_CUSTODY_DISABLED")

    # The basics work as before: own collection; recording for someone else is office-only again.
    body = {"customer_id": f.customer_id, "amount": "50000", "received_at": T0}
    _ok(sup.post(f"{C}/collections", body), 201)
    other = sup.post(f"{C}/collections", {**body, "staff_member_id": operator})
    assert other.status_code == 403 and other.json()["error"]["code"] == "NOT_CUSTODIAN"
    # A float counts when issued (no acknowledgement step) and opens by id.
    fl = _ok(acct.post(f"{C}/floats", {"staff_member_id": f.sup_staff_id, "amount": "5000", "occurred_at": T1}), 201)
    got = _ok(acct.get(f"{C}/floats/{fl['id']}"))
    assert (got["ack_required"], got["ack_status"]) == (False, "NOT_REQUIRED")
    _refused(sup.post(f"{C}/floats/{fl['id']}/acknowledgement", {"acknowledged": True}), "CASH_CUSTODY_DISABLED")
    mine = _ok(sup.get(f"{C}/custody/me"))
    assert sum(float(b["outstanding"]) for b in mine) == 55000 and all(float(b["pending_floats"]) == 0 for b in mine)
    # A partial remittance is not flagged; verifying a different amount opens no variance.
    h = _ok(sup.post(f"{C}/handovers", {"amount": "30000", "handed_at": T1}), 201)
    assert h["partial_shortfall"] is None
    _ok(acct2.post(f"{C}/handovers/{h['id']}/decision", {"verified": True, "amount_received": "29000"}))
    assert sql("SELECT count(*) FROM cash_variance WHERE tenant_id = :t", t=f.tid)[0][0] == 0
    period = {"staff_member_id": f.sup_staff_id, "from": "2026-11-01", "to": "2026-11-01"}
    _ok(acct.get(f"{C}/reconciliation", **period))
    _ok(acct.get(f"{C}/reconciliation/transactions", **period))

    # The remittance cut-off sweep is skipped (cut-off configured, capability off).
    assert run_remittance_cutoff(get_sessionmaker(), AFTER_CUTOFF).flagged == 0

    # Dashboard: the cash tile keeps the basics, its cash-control figures are empty.
    summary = _ok(o.get(f"{T}/accountability/summary"))
    assert summary["disabled_capabilities"] == ["CASH_CUSTODY", "REVENUE_RECONCILIATION"]
    tile = summary["cash"]
    assert tile["custodians"] and tile["transfers_awaiting_acknowledgement"] == []
    assert (tile["remittance_cutoff_hour"], tile["remittances_overdue_today"]) == (None, None)
    assert summary["discrepancies"]["open_variances"] == []
    assert summary["outstanding_approvals"]["cash_retentions"] == 0

    # Devices: transfer/retention operations are not announced and are refused; collections still apply.
    caps = _ok(api.client.get("/api/v1/sync/bootstrap", headers=_h(sup)))["capabilities"]
    assert not {"OP_CASH_TRANSFER", "OP_CASH_RETENTION_REQUEST"} & set(caps) and "OP_METER_BASELINE" in caps
    retention = _op("CASH_RETENTION_REQUEST", {"client_id": str(uuid.uuid4()), "amount": "10", "reason": "Fuel"})
    moved = _op("CASH_TRANSFER", {**transfer, "client_id": str(uuid.uuid4())})
    collected = _op("CASH_COLLECTION", {**body, "client_id": str(uuid.uuid4()), "amount": "700"})
    results = _push(api, sup, retention, moved, collected)
    assert [(r["status"], (r.get("error") or {}).get("code")) for r in results] == [
        ("CONFLICT", "CASH_CUSTODY_DISABLED"),
        ("CONFLICT", "CASH_CUSTODY_DISABLED"),
        ("ACKED", None),
    ]


# --- F2: overdue remittance for field users -------------------------------------------------------------------
def test_field_users_open_their_own_overdue_remittance_only(api: Api) -> None:
    f = setup_finance(api, "Overdue Co", "OVD-1")
    sup, acct = f.supervisor, f.accountant
    other_sup = role(api, f.tid, "supervisor", "sup2-OVD-1")
    _staff(f, "Second Supervisor", other_sup.subject)
    operator = _staff(f, "Operator Juma")
    body = {"customer_id": f.customer_id, "amount": "40000", "received_at": T0}
    _ok(sup.post(f"{C}/collections", {**body, "staff_member_id": operator}), 201)  # recorded for the operator
    _ok(sup.post(f"{C}/collections", body), 201)  # the supervisor's own custody
    # Recorders keep to their own records from here (so the participant rule decides what each may open).
    cash_policy(f, remittance_cutoff_hour=17, recorders_may_record_for_others=False)
    assert run_remittance_cutoff(get_sessionmaker(), AFTER_CUTOFF).flagged == 2
    flags = {x["staff_member_id"]: x["id"] for x in _ok(acct.get(f"{C}/remittance-overdue"))["items"]}
    own, recorded = flags[f.sup_staff_id], flags[operator]

    assert _ok(sup.get(f"{C}/remittance-overdue/{own}"))["staff_member_name"] == "Cash Supervisor"  # custodian
    assert _ok(sup.get(f"{C}/remittance-overdue/{recorded}"))["staff_member_id"] == operator  # recorded that day
    for flag in (own, recorded):  # someone else's flag: not found (never revealed)
        r = other_sup.get(f"{C}/remittance-overdue/{flag}")
        assert r.status_code == 404 and r.json()["error"]["code"] == "REMITTANCE_OVERDUE_NOT_FOUND"
    assert _ok(acct.get(f"{C}/remittance-overdue/{recorded}"))["id"] == recorded  # office readers open any
    assert sup.get(f"{C}/remittance-overdue").status_code == 403  # the list stays an office view
