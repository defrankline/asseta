"""Gate 1 acceptance (prompt.md §10 #1, #2): two isolated tenants (1 vs 100 assets) with different negotiated
monthly/yearly prices, idempotent immutable invoices, Decimal amounts, mid-cycle proration and renewal."""

import threading
from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine, text

from asseta.core.config import get_settings
from tests.support.api import Api

NOV1 = date(2026, 11, 1)


def test_one_asset_monthly_vs_hundred_asset_yearly(api: Api) -> None:
    small = api.onboard("Solo Excavation", price="75000.00", cadence="MONTHLY", currency="TZS")
    large = api.onboard(
        "Mega Fleet", price="600000.00", cadence="YEARLY", currency="TZS", discount="10", tax="18", minimum=50
    )
    for t in (small, large):
        api.activate(t)
    api.add_machines(small["owner"], 1, enroll_on=NOV1)
    api.add_machines(large["owner"], 100, enroll_on=NOV1)

    inv_small = api.generate(small["subscription_id"], NOV1)["created"]
    inv_large = api.generate(large["subscription_id"], NOV1)["created"]
    assert len(inv_small) == 1 and len(inv_large) == 1
    s, big = inv_small[0], inv_large[0]
    assert (s["period_start"], s["period_end"], s["total"], s["billable_assets"]) == (
        "2026-11-01",
        "2026-12-01",
        "75000.0000",
        1,
    )
    # 100 x 600,000 = 60,000,000; -10% = 54,000,000; +18% VAT = 63,720,000
    assert (big["period_end"], big["subtotal"], big["discount_total"], big["tax_total"], big["total"]) == (
        "2027-11-01",
        "60000000.0000",
        "6000000.0000",
        "9720000.0000",
        "63720000.0000",
    )
    assert big["billable_assets"] == 100 and len(big["lines"]) == 102
    assert big["invoice_number"] != s["invoice_number"]

    # Each tenant sees only its own platform invoices.
    mine = small["owner"].get("/api/v1/tenant/billing/invoices").json()
    assert [i["id"] for i in mine] == [s["id"]]

    # Platform dashboard: contracted MRR per currency; yearly normalized /12 (54,000,000/12 = 4,500,000).
    dash = api.platform.get("/api/v1/platform/dashboard").json()
    [tzs] = dash["by_currency"]
    assert Decimal(tzs["contracted_mrr"]) == Decimal("4575000.00")
    assert tzs["billable_assets"] == 101 and tzs["enrolled_assets"] == 101 and tzs["open_invoices"] == 2


def test_invoice_generation_is_idempotent_and_concurrency_safe(api: Api) -> None:
    t = api.onboard("Retry Co", price="1000")
    api.activate(t)
    api.add_machines(t["owner"], 3, enroll_on=NOV1)
    sid = t["subscription_id"]
    results: list[int] = []

    def run() -> None:
        r = api.platform.post(f"/api/v1/platform/subscriptions/{sid}/invoices/generate", {"as_of": "2026-11-01"})
        results.append(len(r.json()["created"]))

    threads = [threading.Thread(target=run) for _ in range(4)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    assert sorted(results) == [0, 0, 0, 1]
    again = api.generate(sid, NOV1)
    assert again["created"] == [] and again["existing_periods"] == ["2026-11-01"]
    assert api.platform.get("/api/v1/platform/invoices", tenant_id=t["tenant"]["id"]).json()["total"] == 1


def test_minimum_commitment_applies(api: Api) -> None:
    t = api.onboard("Min Co", price="500", minimum=5)
    api.activate(t)
    api.add_machines(t["owner"], 2, enroll_on=NOV1)
    inv = api.generate(t["subscription_id"], NOV1)["created"][0]
    assert inv["billable_assets"] == 5 and inv["total"] == "2500.0000"
    assert inv["lines"][-1]["line_type"] == "MINIMUM_COMMITMENT"


def test_mid_cycle_add_remove_preview_and_next_invoice(api: Api) -> None:
    t = api.onboard("Prorate Co", price="30000")
    api.activate(t)
    owner, sid = t["owner"], t["subscription_id"]
    [_m1, m2] = api.add_machines(owner, 2, enroll_on=NOV1)
    api.generate(sid, NOV1)  # November issued: 2 x 30,000

    api.clock.set(date(2026, 11, 21))
    [m3] = api.add_machines(owner, 1, prefix="NEW")
    preview = owner.post(
        "/api/v1/tenant/billing/enrollments/preview", {"machine_id": m3, "effective_from": "2026-11-21"}
    ).json()
    assert (preview["days"], preview["period_days"], preview["amount"]) == (10, 30, "10000.0000")
    r = owner.post("/api/v1/tenant/billing/enrollments", {"machine_id": m3, "effective_from": "2026-11-21"})
    assert r.json()["charge"]["amount"] == "10000.0000"
    # Duplicate enrollment of same machine is rejected: no double billing.
    dup = owner.post("/api/v1/tenant/billing/enrollments", {"machine_id": m3, "effective_from": "2026-11-22"})
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "ALREADY_ENROLLED"

    enrollments = api.platform.get(f"/api/v1/platform/subscriptions/{sid}/enrollments").json()
    e2 = next(e for e in enrollments if e["machine_id"] == m2)
    end_body = {"effective_to": "2026-11-26", "reason": "REMOVED_FROM_FLEET"}
    prev = api.platform.post(f"/api/v1/platform/subscriptions/{sid}/enrollments/{e2['id']}/end-preview", end_body)
    assert prev.json()["amount"] == "-5000.0000"
    r = api.platform.post(f"/api/v1/platform/subscriptions/{sid}/enrollments/{e2['id']}/end", end_body)
    assert r.status_code == 200 and r.json()["charge"]["amount"] == "-5000.0000"

    pending = api.platform.get(f"/api/v1/platform/subscriptions/{sid}/pending-charges").json()
    assert sorted(p["amount"] for p in pending) == ["-5000.0000", "10000.0000"]
    # Editable before invoicing (audited override).
    charge = next(p for p in pending if p["line_type"] == "PRORATION_CHARGE")
    ov = api.platform.patch(
        f"/api/v1/platform/pending-charges/{charge['id']}",
        {"amount": "9000.00", "reason": "Negotiated goodwill on late install"},
    )
    assert ov.status_code == 200 and ov.json()["computed_amount"] == "10000.0000"

    api.clock.set(date(2026, 12, 1))
    dec = api.generate(sid, date(2026, 12, 1))["created"][0]
    # December: m1 + m3 enrolled at period start (2 x 30,000) + 9,000 - 5,000
    assert dec["enrolled_assets"] == 2 and dec["total"] == "64000.0000"
    nov = api.platform.get("/api/v1/platform/invoices", tenant_id=t["tenant"]["id"], status="ISSUED").json()
    assert {i["total"] for i in nov["items"]} == {"60000.0000", "64000.0000"}  # November untouched
    late = api.platform.patch(f"/api/v1/platform/pending-charges/{charge['id']}", {"amount": "1", "reason": "too late"})
    assert late.status_code == 409


def test_backdated_and_out_of_period_changes_rejected(api: Api) -> None:
    t = api.onboard("Strict Co", price="100")
    api.activate(t)
    api.clock.set(date(2026, 12, 5))
    [m] = api.add_machines(t["owner"], 1)
    r = t["owner"].post("/api/v1/tenant/billing/enrollments", {"machine_id": m, "effective_from": "2026-11-20"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "DATE_OUTSIDE_CURRENT_PERIOD"


def test_renewal_catch_up_and_rate_renegotiation(api: Api) -> None:
    t = api.onboard("Renew Co", price="1000.00")
    api.activate(t)
    sid = t["subscription_id"]
    api.add_machines(t["owner"], 2, enroll_on=NOV1)
    r = api.platform.post(
        f"/api/v1/platform/subscriptions/{sid}/rate-versions",
        {
            "currency": "TZS",
            "cadence": "MONTHLY",
            "unit_price": "1200.00",
            "minimum_billable_assets": 1,
            "effective_from": "2027-01-01",
            "reason": "Annual renegotiation",
        },
    )
    assert r.status_code == 201 and r.json()["version"] == 2
    api.clock.set(date(2027, 2, 10))
    created = api.generate(sid, date(2027, 2, 10))["created"]
    assert [(i["period_start"], i["total"]) for i in created] == [
        ("2026-11-01", "2000.0000"),
        ("2026-12-01", "2000.0000"),
        ("2027-01-01", "2400.0000"),
        ("2027-02-01", "2400.0000"),
    ]
    back = api.platform.post(
        f"/api/v1/platform/subscriptions/{sid}/rate-versions",
        {
            "currency": "TZS",
            "cadence": "MONTHLY",
            "unit_price": "1",
            "minimum_billable_assets": 1,
            "effective_from": "2027-01-15",
            "reason": "attempt to rewrite",
        },
    )
    assert back.status_code == 422 and back.json()["error"]["code"] == "RATE_BACKDATED"
    stale = api.platform.post(
        f"/api/v1/platform/subscriptions/{sid}/rate-versions",
        {
            "currency": "TZS",
            "cadence": "MONTHLY",
            "unit_price": "1",
            "minimum_billable_assets": 1,
            "effective_from": "2026-12-15",
            "reason": "older than latest version",
        },
    )
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "RATE_NOT_LATEST"
    # Issued invoices kept the rate they were computed with.
    invoices = api.platform.get("/api/v1/platform/invoices", tenant_id=t["tenant"]["id"]).json()["items"]
    assert sorted(i["total"] for i in invoices) == ["2000.0000", "2000.0000", "2400.0000", "2400.0000"]


def test_issued_invoice_is_immutable_in_database(api: Api) -> None:
    t = api.onboard("Immutable Co", price="100")
    api.activate(t)
    api.add_machines(t["owner"], 1, enroll_on=NOV1)
    inv = api.generate(t["subscription_id"], NOV1)["created"][0]
    engine = create_engine(get_settings().database_url)
    for stmt in (
        "UPDATE platform_invoice SET total = 1 WHERE id = :i",
        "UPDATE platform_invoice_line SET amount = 1 WHERE invoice_id = :i",
        "DELETE FROM platform_invoice WHERE id = :i",
    ):
        with engine.connect() as conn:
            conn.execute(text("SELECT set_config('app.scope','platform',false)"))
            try:
                conn.execute(text(stmt), {"i": inv["id"]})
                raise AssertionError(f"mutation allowed: {stmt}")
            except Exception as exc:
                assert "immutable" in str(exc) or "permission denied" in str(exc)
            conn.rollback()
    engine.dispose()
