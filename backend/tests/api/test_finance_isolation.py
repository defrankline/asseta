"""Gate 5: tenant finance isolation — cross-tenant denial at API and RLS, platform scope cannot read tenant finance,
and tenant credit invoices are a separate ledger from platform subscription invoices."""

import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from asseta.core.config import get_settings
from tests.support.api import Api
from tests.support.finance import category, expense_policy, setup_finance
from tests.support.hours import RATE

TABLES = (
    "hours_purchase",
    "credit_invoice",
    "credit_invoice_payment",
    "financial_adjustment",
    "customer_payment",
    "hours_payment_allocation",
    "supervisor_cash_custody",
    "cash_handover",
    "expense_category",
    "expense",
    "expense_attachment",
    "fuel_event",
    "approval_request",
)


def test_finance_rls_cross_tenant_platform_denial_and_ledger_separation(api: Api) -> None:
    f = setup_finance(api, "Alpha Hire", "ALPHA-1")
    sale = f.accountant.post(
        "/api/v1/tenant/hours-purchases",
        {
            "customer_id": f.customer_id,
            "machine_id": f.c.t.machine_id,
            "hours": "8",
            "client_id": str(uuid.uuid4()),
            "payments": [{"amount": str(8 * RATE), "method": "CREDIT"}],
        },
    )
    assert sale.status_code == 201, sale.text
    inv = sale.json()["credit_invoice"]
    paid = f.accountant.post(
        f"/api/v1/tenant/credit-invoices/{inv['id']}/payments",
        {"amount": "1000", "method": "BANK", "reference": "A-1", "received_at": api.clock.now.isoformat()},
    )
    assert paid.status_code == 201, paid.text
    pay = {"id": paid.json()["payments"][0]["payment_id"]}
    cat = category(f, "SPARES", "Spares")
    expense_policy(f, receipt_required_above="100000000", gps_required=False, auto_approve_limit="0")
    exp = f.supervisor.post(
        "/api/v1/tenant/expenses",
        {
            "category_id": cat,
            "description": "x",
            "amount": "500",
            "incurred_at": api.clock.now.isoformat(),
            "paid_from": "CASH_CUSTODY",
        },
    ).json()
    f.accountant.post("/api/v1/tenant/cash/floats", {"staff_member_id": f.sup_staff_id, "amount": "5000"})
    hand = f.supervisor.post(
        "/api/v1/tenant/cash/handovers", {"amount": "100", "handed_at": api.clock.now.isoformat()}
    ).json()
    f.supervisor.post(
        "/api/v1/tenant/fuel-events",
        {
            "event_type": "USAGE",
            "litres": "3",
            "machine_id": f.c.t.machine_id,
            "occurred_at": api.clock.now.isoformat(),
        },
    )

    # --- API: another tenant sees nothing and cannot reference A's records by id ---------------------------
    b = api.onboard("Bravo Earthmovers", price="1000")
    ob = b["owner"]
    assert ob.get("/api/v1/tenant/credit-invoices").json()["total"] == 0
    assert ob.get(f"/api/v1/tenant/credit-invoices/{inv['id']}").status_code == 404
    sabotage = {"amount": "1", "method": "BANK", "reference": "B-1", "received_at": api.clock.now.isoformat()}
    assert ob.post(f"/api/v1/tenant/credit-invoices/{inv['id']}/payments", sabotage).status_code == 404
    assert ob.get(f"/api/v1/tenant/customers/{f.customer_id}/balance").status_code == 404
    assert ob.post(f"/api/v1/tenant/customer-payments/{pay['id']}/decision", {"verified": True}).status_code == 404
    assert ob.post(f"/api/v1/tenant/cash/handovers/{hand['id']}/decision", {"verified": True}).status_code == 404
    assert (
        ob.post(f"/api/v1/tenant/approvals/{exp['approval_request_id']}/decision", {"approve": True}).status_code == 404
    )
    assert ob.get("/api/v1/tenant/expenses").json()["total"] == 0
    assert (
        ob.get(
            "/api/v1/tenant/cash/reconciliation",
            staff_member_id=f.sup_staff_id,
            **{"from": "2026-11-01", "to": "2026-11-01"},
        ).status_code
        == 404
    )
    assert (
        ob.get(
            "/api/v1/tenant/finance/profitability", group_by="MACHINE", **{"from": "2026-11-01", "to": "2026-11-02"}
        ).json()["rows"]
        == []
    )
    cross = ob.post(
        "/api/v1/tenant/customer-payments",
        {"customer_id": f.customer_id, "amount": "1", "method": "CASH", "received_at": api.clock.now.isoformat()},
    )
    assert cross.status_code == 404
    assert ob.get("/api/v1/tenant/credit-invoices", tenant=f.tid).json()["error"]["code"] == "TENANT_ACCESS_DENIED"
    # Platform scope never reaches tenant finance routes.
    assert api.platform.get("/api/v1/tenant/credit-invoices", tenant=f.tid).status_code == 403
    assert (
        api.platform.get(
            "/api/v1/tenant/finance/profitability",
            tenant=f.tid,
            group_by="MACHINE",
            **{"from": "2026-11-01", "to": "2026-11-02"},
        ).status_code
        == 403
    )

    # --- ledger separation: platform subscription invoices vs tenant credit invoices -------------------------
    api.generate(f.c.t.tenant["subscription_id"], api.clock.now.date())
    platform_invs = f.owner.get("/api/v1/tenant/billing/invoices").json()
    assert platform_invs and all(i["invoice_number"].startswith("AST-") for i in platform_invs)
    credit = f.owner.get("/api/v1/tenant/credit-invoices").json()["items"]
    assert [i["invoice_number"] for i in credit] == [inv["invoice_number"]]
    assert not inv["invoice_number"].startswith("AST-")
    assert inv["id"] not in {i["id"] for i in platform_invs}
    assert f.accountant.get("/api/v1/tenant/billing/invoices").status_code == 200  # accountant: billing.read only
    assert f.supervisor.get("/api/v1/tenant/customer-payments").status_code == 403  # supervisor: no finance read

    # --- database (RLS, application role) ----------------------------------------------------------------------
    engine = create_engine(get_settings().database_url)
    count_all = " UNION ALL ".join(f"SELECT '{t}', count(*) FROM {t}" for t in TABLES)  # noqa: S608 (constants)
    with engine.begin() as conn:
        assert all(n == 0 for _, n in conn.execute(text(count_all)))  # no scope: nothing
        conn.execute(text("SELECT set_config('app.scope','platform',true)"))
        assert all(n == 0 for _, n in conn.execute(text(count_all)))  # platform: no tenant finance
        assert conn.execute(text("SELECT count(*) FROM platform_invoice")).scalar_one() >= 1
        assert conn.execute(text("SELECT count(*) FROM audit_event WHERE action LIKE 'finance.%'")).scalar_one() == 0
    with engine.begin() as conn:
        conn.execute(
            text("SELECT set_config('app.scope','tenant',true), set_config('app.tenant_id',:t,true)"),
            {"t": b["tenant"]["id"]},
        )
        assert all(n == 0 for _, n in conn.execute(text(count_all)))
    with engine.begin() as conn:
        conn.execute(text("SELECT set_config('app.scope','system',true)"))
        seen: dict[str, int] = dict(conn.execute(text(count_all)).tuples().all())
        missing = [t for t in TABLES if seen[t] == 0 and t not in ("expense_attachment", "financial_adjustment")]
        assert missing == [], seen  # the data exists; RLS alone hid it above
    with pytest.raises(DBAPIError, match="row-level security"), engine.begin() as conn:
        conn.execute(
            text("SELECT set_config('app.scope','tenant',true), set_config('app.tenant_id',:t,true)"),
            {"t": b["tenant"]["id"]},
        )
        conn.execute(
            text(
                "INSERT INTO financial_adjustment (id, tenant_id, customer_id, kind, amount, currency, reason,"
                " created_at) VALUES (gen_random_uuid(), :a, :c, 'PAYMENT_REVERSAL', 1, 'TZS', 'forged', now())"
            ),
            {"a": f.tid, "c": f.customer_id},
        )
    engine.dispose()
