"""ADR-008 offline paths and switches: MACHINE_REPORT and CREDIT_INVOICE_PAYMENT operations, the CREDIT line of an
offline sale, the snapshots phones work from, the capabilities announced (and "Book the job" no longer announced),
retired booking settings, and the company fuel switch (§3)."""

import uuid
from decimal import Decimal
from typing import Any

from tests.support.api import Actor, Api
from tests.support.finance import FinCtx, setup_finance, tenant_sql
from tests.support.hours import RATE
from tests.support.machine_reports import (
    T,
    bought,
    code,
    cust,
    field_credit,
    idle,
    later,
    ok,
    reading,
    setup_reports,
)

DEVICE = "android-adr008-sync-001"


def _h(actor: Actor) -> dict[str, str]:
    return {**actor.headers(True, None), "X-Device-Id": DEVICE}


def _register(api: Api, actor: Actor) -> dict[str, Any]:
    ok(
        api.client.post(
            "/api/v1/sync/devices",
            headers=_h(actor),
            json={"device_id": DEVICE, "platform": "ANDROID", "app_version": "2.0.0"},
        ),
        201,
    )
    boot: dict[str, Any] = ok(api.client.get("/api/v1/sync/bootstrap", headers=_h(actor)))
    return boot


def _push(api: Api, actor: Actor, *ops: dict[str, Any]) -> list[dict[str, Any]]:
    r = api.client.post(
        "/api/v1/sync/push", headers=_h(actor), json={"device_now": api.clock.now.isoformat(), "operations": list(ops)}
    )
    assert r.status_code == 200, r.text
    return list(r.json()["results"])


def _op(api: Api, op_type: str, payload: dict[str, Any], op_id: str | None = None) -> dict[str, Any]:
    return {
        "id": op_id or str(uuid.uuid4()),
        "op_type": op_type,
        "payload": payload,
        "created_at_device": api.clock.now.isoformat(),
        "depends_on": [],
    }


def _report(machine_id: str, value: str, at: Any, lines: list[dict[str, Any]]) -> dict[str, Any]:
    return {"machine_id": machine_id, "capture": reading(machine_id, value, at), "lines": lines}


def _nav(actor: Actor) -> dict[str, Any]:
    return dict(ok(actor.get("/api/v1/me"))["tenants"][0])


# --- capabilities and snapshots ---------------------------------------------------------------------------------
def test_phones_are_told_what_they_can_do_and_get_what_they_need(api: Api) -> None:
    ctx = setup_reports(api)
    f = ctx.f
    bought(api, f, 7)
    boot = _register(api, f.supervisor)
    caps = set(boot["capabilities"])
    assert {"OP_MACHINE_REPORT", "OP_CREDIT_INVOICE_PAYMENT", "OP_HOURS_SALE_CREDIT"} <= caps
    assert "OP_HOURS_SALE_BOOKING" not in caps
    data = boot["data"]
    assert {r["code"] for r in data["machine_report_reasons"]} >= {"TRANSIT", "BREAKDOWN", "WEATHER"}
    [state] = data["machine_report_states"]
    assert state["machine_id"] == ctx.machine_id and Decimal(state["previous_reading"]) == 1000
    assert state["previous_source"] == "BASELINE" and state["pending_report_id"] is None
    [hours] = data["machine_report_hours"]
    assert hours["customer_id"] == f.customer_id and Decimal(hours["available"]) == 7
    assert hours["customer_name"] == "Road Builders Ltd"
    assert data["my_machine_reports"] == [] and data["open_credit_invoices"] == []


# --- MACHINE_REPORT ----------------------------------------------------------------------------------------------
def test_machine_reports_sync_offline_and_refusals_are_kept_for_review(api: Api) -> None:
    ctx = setup_reports(api)
    f, m = ctx.f, ctx.machine_id
    bought(api, f, 5)
    _register(api, f.supervisor)
    at = later(api, 4)
    first = _op(
        api, "MACHINE_REPORT", _report(m, "1004", at, [cust(f.customer_id, 3), idle(ctx.reasons["TRANSIT"], 1)])
    )
    [res] = _push(api, f.supervisor, first)
    assert res["status"] == "ACKED", res
    report = res["result"]["entity"]
    assert report["id"] == first["id"] and report["source"] == "SYNC" and report["status"] == "SUBMITTED"
    # A retry of the same operation returns the same report.
    [again] = _push(api, f.supervisor, first)
    assert again["status"] == "DUPLICATE" and again["result"]["entity"]["id"] == report["id"]
    assert tenant_sql(f.tid, "SELECT count(*) FROM machine_report")[0][0] == 1
    # The next report on the machine waits: kept for review (the reading was taken in the field).
    nxt = _op(api, "MACHINE_REPORT", _report(m, "1006", later(api, 2), [idle(ctx.reasons["IDLE_ON_SITE"], 6)]))
    [held] = _push(api, f.supervisor, nxt)
    assert held["status"] == "CONFLICT" and held["error"]["code"] == "REPORT_PENDING", held
    # Malformed splits are rejected outright.
    ok(f.manager.post(f"{T}/machine-reports/{report['id']}/approve", {}))
    bad = _op(
        api,
        "MACHINE_REPORT",
        _report(
            m, "1006", api.clock.now, [idle(ctx.reasons["IDLE_ON_SITE"], "1.25"), idle(ctx.reasons["TRANSIT"], "0.75")]
        ),
    )
    [rej] = _push(api, f.supervisor, bad)
    assert rej["status"] == "REJECTED" and rej["error"]["code"] == "HOURS_PRECISION", rej
    # Hours another report took meanwhile: kept for review.
    over = _op(api, "MACHINE_REPORT", _report(m, "1007", api.clock.now, [cust(f.customer_id, 3)]))
    [held] = _push(api, f.supervisor, over)
    assert held["status"] == "CONFLICT" and held["error"]["code"] == "HOURS_NOT_AVAILABLE", held
    # The phone's snapshot shows its report and the machine's new starting point.
    changes = ok(api.client.get("/api/v1/sync/changes", headers=_h(f.supervisor), params={"cursor": 0}))
    assert [r["status"] for r in changes["data"]["my_machine_reports"]] == ["APPROVED"]
    assert Decimal(changes["data"]["machine_report_states"][0]["previous_reading"]) == 1004
    assert Decimal(changes["data"]["machine_report_hours"][0]["available"]) == 2


def test_a_supervisor_without_the_machine_gets_a_conflict(api: Api) -> None:
    ctx = setup_reports(api)
    f = ctx.f
    other = ok(f.owner.post(f"{T}/staff", {"full_name": "Someone Else", "kind": "SUPERVISOR"}), 201)["id"]
    [m2] = api.add_machines(f.owner, 1, prefix="OTH")
    ok(
        f.owner.post(
            f"{T}/machines/{m2}/assignments",
            {"staff_member_id": other, "role": "SUPERVISOR", "effective_from": api.clock.now.isoformat()},
        ),
        201,
    )
    _register(api, f.supervisor)
    op = _op(api, "MACHINE_REPORT", _report(m2, "5", later(api, 1), [idle(ctx.reasons["TRANSIT"], 5)]))
    [res] = _push(api, f.supervisor, op)
    assert res["status"] == "CONFLICT" and res["error"]["code"] == "MACHINE_NOT_ASSIGNED", res


# --- credit offline ----------------------------------------------------------------------------------------------
def _sale(f: FinCtx, api: Api, credit: int, cash: int) -> dict[str, Any]:
    return {
        "customer_id": f.customer_id,
        "machine_id": f.c.t.machine_id,
        "hours": str(credit + cash),
        "payments": [
            {"method": "CASH", "amount": str(cash * RATE), "received_at": api.clock.now.isoformat()},
            {"method": "CREDIT", "amount": str(credit * RATE)},
        ],
    }


def test_credit_sales_and_invoice_payments_offline(api: Api) -> None:
    f = setup_finance(api, "Credit Sync Co", "CRS-1")
    _register(api, f.supervisor)
    # The company has not allowed field credit: the sale is kept for review (money changed hands).
    [held] = _push(api, f.supervisor, _op(api, "HOURS_PURCHASE", _sale(f, api, 3, 1)))
    assert held["status"] == "CONFLICT" and held["error"]["code"] == "CREDIT_SALES_NOT_ALLOWED", held
    field_credit(f)
    [sold] = _push(api, f.supervisor, _op(api, "HOURS_PURCHASE", _sale(f, api, 3, 1)))
    assert sold["status"] == "ACKED", sold
    invoice = sold["result"]["entity"]["credit_invoice"]
    assert Decimal(invoice["amount"]) == 3 * RATE and invoice["status"] == "UNPAID"
    snapshot = ok(api.client.get("/api/v1/sync/changes", headers=_h(f.supervisor), params={"cursor": 0}))["data"]
    [open_inv] = snapshot["open_credit_invoices"]
    assert open_inv["id"] == invoice["id"] and open_inv["customer_name"] == "Road Builders Ltd"

    pay = {
        "invoice_id": invoice["id"],
        "amount": str(RATE),
        "method": "CASH",
        "received_at": api.clock.now.isoformat(),
    }
    op = _op(api, "CREDIT_INVOICE_PAYMENT", pay)
    [paid] = _push(api, f.supervisor, op)
    assert paid["status"] == "ACKED", paid
    assert paid["result"]["entity"]["status"] == "PART_PAID"
    [dup] = _push(api, f.supervisor, op)
    assert dup["status"] == "DUPLICATE"
    payments = tenant_sql(f.tid, "SELECT count(*) FROM credit_invoice_payment")[0][0]
    assert payments == 1
    # The supervisor holds the cash: two cash collections (the sale's cash and the invoice part).
    custody = ok(f.supervisor.get(f"{T}/cash/custody/me"))
    assert sum(Decimal(c["outstanding"]) for c in custody) == 2 * RATE
    too_much = _op(api, "CREDIT_INVOICE_PAYMENT", {**pay, "amount": str(5 * RATE)})
    [held] = _push(api, f.supervisor, too_much)
    assert held["status"] == "CONFLICT" and held["error"]["code"] == "INVOICE_OVERPAYMENT", held


# --- retired booking settings ------------------------------------------------------------------------------------
def test_versions_written_with_the_booking_settings_still_resolve(api: Api) -> None:
    f = setup_finance(api, "Old Settings Co", "OLD-1")
    tenant_sql(
        f.tid,
        "INSERT INTO policy_version (id, policy_type, scope, tenant_id, scope_ref_id, version, effective_from, values,"
        " reason, created_at, source) VALUES (gen_random_uuid(), 'CUSTOMER_HOURS', 'TENANT', :t, NULL, 90,"
        " TIMESTAMPTZ '2026-10-01 00:00:00+00', CAST(:v AS jsonb), 'Before ADR-008', now(), 'api') RETURNING id",
        t=f.tid,
        v='{"walk_in_standard_contract": true, "prepaid_job_auto_approval": true, "field_noncash_payments": true}',
    )
    eff = ok(f.owner.get(f"{T}/policies/CUSTOMER_HOURS/effective"))
    assert eff["values"]["field_noncash_payments"] is True
    assert "walk_in_standard_contract" not in eff["values"] and "prepaid_job_auto_approval" not in eff["values"]
    r = f.owner.post(
        f"{T}/policies/CUSTOMER_HOURS/versions",
        {"scope": "TENANT", "values": {"prepaid_job_auto_approval": True}, "reason": "Old setting"},
    )
    assert r.status_code == 422 and code(r) == "POLICY_UNKNOWN_FIELD", r.text


# --- fuel switch (ADR-008 §3) ------------------------------------------------------------------------------------
def _fuel(api: Api, machine_id: str) -> dict[str, Any]:
    return {
        "event_type": "ISSUE",
        "litres": "40",
        "machine_id": machine_id,
        "unit_price": "3000",
        "occurred_at": api.clock.now.isoformat(),
    }


def test_fuel_switched_off_is_refused_and_hidden_everywhere(api: Api) -> None:
    f = setup_finance(api, "No Fuel Co", "NFU-1")
    o, m = f.owner, f.c.t.machine_id
    ok(f.supervisor.post(f"{T}/fuel-events", _fuel(api, m)), 201)  # recorded while fuel was on
    before = _nav(o)
    assert "FUEL" not in before["disabled_capabilities"]
    labels = {x["key"]: x["label"] for x in before["menus"]}
    assert labels["tenant.expenses"] == "Expenses & fuel" and "tenant.field.fuel" in labels
    rows = ok(
        f.accountant.get(
            "/api/v1/tenant/finance/profitability", group_by="MACHINE", **{"from": "2026-11-01", "to": "2026-11-02"}
        )
    )["rows"]
    assert sum(Decimal(r["fuel_cost"]) for r in rows) == 120000

    ok(
        o.post(
            f"{T}/policies/EXPENSE_CAPTURE/versions",
            {"scope": "TENANT", "values": {"fuel_enabled": False}, "reason": "The customer bears fuel"},
        ),
        201,
    )
    nav = _nav(o)
    assert "FUEL" in nav["disabled_capabilities"]
    labels = {x["key"]: x["label"] for x in nav["menus"]}
    assert labels["tenant.expenses"] == "Expenses" and "tenant.field.fuel" not in labels
    sup_menus = {x["key"] for x in _nav(f.supervisor)["menus"]}
    assert "tenant.field.fuel" not in sup_menus and "tenant.field.expenses" in sup_menus
    for r in (f.supervisor.post(f"{T}/fuel-events", _fuel(api, m)), o.get(f"{T}/fuel-events")):
        assert r.status_code == 422 and code(r) == "FUEL_DISABLED", r.text
    # Offline: a fuel event queued before the switch is kept for review, never applied.
    _register(api, f.supervisor)
    [held] = _push(api, f.supervisor, _op(api, "FUEL_EVENT", {**_fuel(api, m), "client_id": str(uuid.uuid4())}))
    assert held["status"] == "CONFLICT" and held["error"]["code"] == "FUEL_DISABLED", held
    changes = ok(api.client.get("/api/v1/sync/changes", headers=_h(f.supervisor), params={"cursor": 0}))
    assert changes["data"]["my_fuel_events"] == []
    # Fuel already recorded is kept (hidden): no fuel line in profitability, no fuel insights.
    assert tenant_sql(f.tid, "SELECT count(*) FROM fuel_event")[0][0] == 1
    rows = ok(
        f.accountant.get(
            "/api/v1/tenant/finance/profitability", group_by="MACHINE", **{"from": "2026-11-01", "to": "2026-11-02"}
        )
    )["rows"]
    assert all(Decimal(r["fuel_cost"]) == 0 for r in rows)
    assert ok(o.get(f"{T}/insights"))["fuel_efficiency"] == []
