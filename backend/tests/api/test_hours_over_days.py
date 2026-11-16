"""DEC-031 Phase 4: prepaid hours used over days and weeks — the low-balance warning (P2) and the customer hours
statement (P3). Hours leave a customer's balance when a machine report naming them is approved (ADR-008); the
default keeps warnings off."""

from datetime import timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from asseta.core.db import get_sessionmaker
from asseta.modules.hours.low_balance import LowBalanceSummary, run_low_balance
from tests.support.api import Api
from tests.support.finance import setup_finance, tenant_sql
from tests.support.hours import RATE, get_purchase, hours_policy, purchase, verify
from tests.support.machine_reports import ReportCtx, cust, later, report_body, setup_reports, submit
from tests.support.notify import drain, sql

T = "/api/v1/tenant"
TZ = ZoneInfo("Africa/Dar_es_Salaam")


def _ok(r: Any, status: int = 200) -> Any:
    assert r.status_code == status, r.text
    return r.json()


def _sweep(api: Api) -> LowBalanceSummary:
    summary = run_low_balance(get_sessionmaker(), api.clock.now)
    assert summary.failures == 0
    return summary


def _bought(api: Api, ctx: ReportCtx, hours: int) -> dict[str, Any]:
    f = ctx.f
    p = purchase(api, f.accountant, f, str(hours), pay=str(hours * RATE))
    verify(f.accountant2, p["payment"]["id"])
    return p


def _report(api: Api, ctx: ReportCtx, reading: str, hours: int, after_h: float) -> dict[str, Any]:
    """A report giving the customer `hours` (the meter moved exactly that much), approved by the manager."""
    f = ctx.f
    at = later(api, after_h)
    rep = submit(f.supervisor, report_body(ctx.machine_id, reading, at, [cust(f.customer_id, hours)]))
    done: dict[str, Any] = _ok(f.manager.post(f"{T}/machine-reports/{rep['id']}/approve", {}))
    return done


def test_defaults_keep_warnings_off_and_hours_leave_at_approval(api: Api) -> None:
    ctx = setup_reports(api)
    f = ctx.f
    eff = _ok(f.owner.get(f"{T}/policies/CUSTOMER_HOURS/effective"))["values"]
    assert (eff["low_balance_hours"], eff["low_balance_notify_customer"]) == (None, False)
    assert "drawdown" not in eff
    p = _bought(api, ctx, 5)
    at = later(api, 5)
    rep = submit(f.supervisor, report_body(ctx.machine_id, "1004.5", at, [cust(f.customer_id, "4.5")]))
    assert Decimal(get_purchase(f.owner, p["id"])["totals"]["remaining"]) == 5  # nothing leaves before approval
    _ok(f.manager.post(f"{T}/machine-reports/{rep['id']}/approve", {}))
    got = get_purchase(f.owner, p["id"])["totals"]
    assert (Decimal(got["consumed"]), Decimal(got["remaining"])) == (Decimal("4.5"), Decimal("0.5"))
    assert "provisional" not in got
    types = tenant_sql(f.tid, "SELECT DISTINCT entry_type FROM hours_ledger_entry ORDER BY 1")
    assert [t for (t,) in types] == ["ACTIVATED", "CONSUMED"]
    summary = _sweep(api)
    assert (summary.low_balance_alerts, summary.customer_sms) == (0, 0)
    assert sql("SELECT count(*) FROM hours_low_balance_alert")[0][0] == 0


def test_low_balance_warning_once_per_crossing_and_the_statement_over_days(api: Api) -> None:
    ctx = setup_reports(api)
    f = ctx.f
    hours_policy(f, low_balance_hours="3", low_balance_notify_customer=True)
    customer = _ok(f.owner.get(f"{T}/customers/{f.customer_id}"))
    _ok(
        f.owner.put(
            f"{T}/customers/{f.customer_id}",
            {
                "code": customer["code"],
                "name": customer["name"],
                "contact_phone": "0712 345 678",
                "version": customer["version"],
            },
        )
    )
    first = _bought(api, ctx, 10)
    d1 = api.clock.now.astimezone(TZ).date()

    # Day 1: 6 hours reported and approved -> 4 left, above the threshold: no warning.
    r1 = _report(api, ctx, "1006", 6, 1)
    assert api.clock.now.astimezone(TZ).date() == d1
    assert sql("SELECT count(*) FROM hours_low_balance_alert")[0][0] == 0

    # Day 2: 3 more hours -> 1 left: one warning at approval; the sweep queues the customer's SMS once.
    r2 = _report(api, ctx, "1009", 3, 24)
    d2 = api.clock.now.astimezone(TZ).date()
    assert d2 == d1 + timedelta(days=1)
    alerts_sql = "SELECT count(*) FROM hours_low_balance_alert"
    assert sql(alerts_sql)[0][0] == 1
    s1 = _sweep(api)
    assert (s1.low_balance_alerts, s1.customer_sms) == (0, 1)
    s2 = _sweep(api)
    assert (s2.low_balance_alerts, s2.customer_sms, sql(alerts_sql)[0][0]) == (0, 0, 1)  # once per crossing

    # A top-up does not re-arm the used-up purchase (it stays at 1 hour).
    top_up = _bought(api, ctx, 5)
    assert _sweep(api).low_balance_alerts == 0

    # Office notification once per crossing, linked to the purchase; the customer's SMS was queued (SMS credits).
    drain(api)
    rows = sql(
        "SELECT link, entity_type, entity_id, data FROM notification WHERE notification_type = 'HOURS_LOW_BALANCE'"
    )
    assert rows and first["id"] in {r[2] for r in rows}
    link, entity, _, data = next(r for r in rows if r[2] == first["id"])
    assert (link, entity) == (f"/tenant/hours/purchases/{first['id']}", "hours_purchase")
    assert (data["kind"], data["record_id"]) == ("HOURS_PURCHASE", first["id"])
    assert Decimal(data["threshold_hours"]) == 3 and data["alert_id"]
    sms = sql(
        "SELECT msisdn, billable, recipient_user_id FROM sms_delivery WHERE notification_type = 'HOURS_LOW_BALANCE'"
    )
    assert sms and sms[0] == ("255712345678", True, None)
    alerts = _ok(f.owner.get(f"{T}/hours-low-balance-alerts", purchase_id=first["id"]))["items"]
    assert len(alerts) == 1 and alerts[0]["customer_sms_status"] == "QUEUED"
    assert alerts[0]["purchase_number"] == first["purchase_number"]
    one = _ok(f.owner.get(f"{T}/hours-low-balance-alerts/{alerts[0]['id']}"))
    assert one["id"] == alerts[0]["id"] and Decimal(one["remaining_hours"]) == 1

    # Statement for the two days: bought, activated, used per day and machine report, remaining; same as PDF.
    st = _ok(
        f.owner.get(f"{T}/customers/{f.customer_id}/hours-statement", date_from=d1.isoformat(), date_to=d2.isoformat())
    )
    tot = st["totals"]
    assert Decimal(tot["opening_balance"]) == 0 and Decimal(tot["bought"]) == 15 and Decimal(tot["activated"]) == 15
    assert Decimal(tot["used"]) == 9 and Decimal(tot["closing_balance"]) == 6
    assert "provisional_at_close" not in tot
    usage = {(u["day"], u["machine_report_number"]): Decimal(u["hours"]) for u in st["usage"]}
    assert usage == {
        (d1.isoformat(), r1["report_number"]): Decimal(6),
        (d2.isoformat(), r2["report_number"]): Decimal(3),
    }
    assert {u["machine_report_id"] for u in st["usage"]} == {r1["id"], r2["id"]}
    assert st["customer_name"] and [p["purchase_number"] for p in st["purchases"]] == [
        first["purchase_number"],
        top_up["purchase_number"],
    ]
    consumed = [line for line in st["lines"] if line["entry_type"] == "CONSUMED"]
    assert {line["machine_report_number"] for line in consumed} == {r1["report_number"], r2["report_number"]}
    assert Decimal(st["lines"][-1]["balance_after"]) == 6
    pdf = f.owner.get(st["pdf_path"])
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")


def test_statement_validates_the_period_and_the_customer(api: Api) -> None:
    f = setup_finance(api)
    url = f"{T}/customers/{f.customer_id}/hours-statement"
    bad = f.owner.get(url, date_from="2026-02-01", date_to="2026-01-01")
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "INVALID_PERIOD"
    long = f.owner.get(url, date_from="2025-01-01", date_to="2026-06-01")
    assert long.status_code == 422 and long.json()["error"]["code"] == "PERIOD_TOO_LONG"
    missing = f.owner.get(f"{T}/customers/00000000-0000-4000-8000-000000000000/hours-statement")
    assert missing.status_code == 404
    empty = _ok(f.owner.get(url, machine_id=f.c.t.machine_id))
    assert empty["purchases"] == [] and Decimal(empty["totals"]["closing_balance"]) == 0
    assert empty["machine_code"] and "hours-statement.pdf" in empty["pdf_path"]
    pdf = f.owner.get(f"{url}.pdf", machine_id=f.c.t.machine_id)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
