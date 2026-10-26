"""DEC-031 Phase 4: prepaid hours used over days and weeks — daily drawdown (P1), low-balance warning (P2) and the
customer hours statement (P3). Defaults keep today's behaviour (drawdown at completion, no warning)."""

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from asseta.core.db import get_sessionmaker
from asseta.modules.hours.drawdown import DrawdownSummary, run_hours_drawdown
from tests.support.api import Actor, Api
from tests.support.finance import FinCtx, setup_finance, tenant_sql
from tests.support.hours import RATE, get_purchase, hours_policy, prepaid_job, purchase, verify
from tests.support.jobs import capture
from tests.support.notify import drain, sql

T = "/api/v1/tenant"
TZ = ZoneInfo("Africa/Dar_es_Salaam")


def _setup(api: Api) -> FinCtx:
    f = setup_finance(api)
    r = f.owner.post(f"{T}/jobs/{f.c.job_id}/transitions", {"action": "CANCEL", "reason": "Not needed"})
    assert r.status_code == 200, r.text  # frees the machine for prepaid jobs
    return f


def _ok(r: Any, status: int = 200) -> Any:
    assert r.status_code == status, r.text
    return r.json()


def _reading(api: Api, o: Actor, job: str, kind: str, reading: str, at: datetime) -> None:
    api.clock.set_at(at)
    _ok(o.post(f"{T}/meter-captures", capture(job, kind, reading, at, mode="MANUAL")), 201)


def _sweep(at: datetime) -> DrawdownSummary:
    summary = run_hours_drawdown(get_sessionmaker(), at)
    assert summary.failures == 0
    return summary


def _held(f: FinCtx, job: str) -> dict[date, Decimal]:
    rows = tenant_sql(
        f.tid,
        "SELECT usage_day, sum(CASE WHEN entry_type = 'PROVISIONAL' THEN hours ELSE -hours END) FROM"
        " hours_ledger_entry WHERE job_id = :j AND entry_type IN ('PROVISIONAL', 'PROVISIONAL_REVERSED')"
        " GROUP BY usage_day",
        j=job,
    )
    return {d: Decimal(h) for d, h in rows if Decimal(h) != 0}


def _start(api: Api, f: FinCtx, number: str, opening: str) -> tuple[str, datetime]:
    job = prepaid_job(api, f, number)
    t0 = api.clock.now
    _reading(api, f.owner, job, "OPENING", opening, t0)
    _ok(f.owner.post(f"{T}/jobs/{job}/transitions", {"action": "START"}))
    return job, t0


def _complete(api: Api, f: FinCtx, job: str, closing: str, at: datetime) -> None:
    _reading(api, f.owner, job, "CLOSING", closing, at)
    ack = {"client_id": str(uuid.uuid4())}
    _ok(
        f.owner.post(
            f"{T}/jobs/{job}/acknowledgements",
            {**ack, "method": "NAME_CONFIRMATION", "signer_name": "Engineer", "captured_at": at.isoformat()},
        ),
        201,
    )
    _ok(f.owner.post(f"{T}/jobs/{job}/transitions", {"action": "COMPLETE"}))


def test_defaults_keep_drawdown_at_completion_and_no_warning(api: Api) -> None:
    f = _setup(api)
    eff = _ok(f.owner.get(f"{T}/policies/CUSTOMER_HOURS/effective"))["values"]
    assert (eff["drawdown"], eff["low_balance_hours"], eff["low_balance_notify_customer"]) == (
        "AT_COMPLETION",
        None,
        False,
    )
    p = purchase(api, f.accountant, f, "5", pay=str(5 * RATE))
    verify(f.accountant2, p["payment"]["id"])
    job, t0 = _start(api, f, "P-DEF", "1000")
    _reading(api, f.owner, job, "DAILY", "1004", t0 + timedelta(hours=5))
    summary = _sweep(t0 + timedelta(hours=5, minutes=1))
    assert (summary.drawn_entries, summary.low_balance_alerts, summary.customer_sms) == (0, 0, 0)
    assert _held(f, job) == {}
    assert Decimal(get_purchase(f.owner, p["id"])["totals"]["remaining"]) == 5
    _complete(api, f, job, "1004.5", t0 + timedelta(hours=6))
    got = get_purchase(f.owner, p["id"])
    assert Decimal(got["totals"]["consumed"]) == Decimal("4.5") and Decimal(got["totals"]["provisional"]) == 0
    types = tenant_sql(f.tid, "SELECT DISTINCT entry_type FROM hours_ledger_entry ORDER BY 1")
    assert [t for (t,) in types] == ["ACTIVATED", "CONSUMED"]
    assert sql("SELECT count(*) FROM hours_low_balance_alert")[0][0] == 0


def test_daily_drawdown_live_balance_overrun_low_balance_and_final_allocation(api: Api) -> None:
    f = _setup(api)
    hours_policy(f, drawdown="DAILY", low_balance_hours="3", low_balance_notify_customer=True)
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
    first = purchase(api, f.accountant, f, "10", pay=str(10 * RATE))
    verify(f.accountant2, first["payment"]["id"])
    job, t0 = _start(api, f, "P-DAY", "1000")  # 12:00 local on day 1
    d1 = t0.astimezone(TZ).date()
    d2 = d1 + timedelta(days=1)
    assert _sweep(t0 + timedelta(minutes=5)).drawn_entries == 0  # no hours read yet

    # Day 1, 18:00 local: 6 hours read -> drawn the same day; the balance is live.
    _reading(api, f.owner, job, "DAILY", "1006", t0 + timedelta(hours=6))
    assert _sweep(t0 + timedelta(hours=6, minutes=1)).drawn_entries == 1
    assert _held(f, job) == {d1: Decimal(6)}
    got = get_purchase(f.owner, first["id"])
    assert (Decimal(got["totals"]["remaining"]), Decimal(got["totals"]["provisional"])) == (Decimal(4), Decimal(6))
    again = _sweep(t0 + timedelta(hours=6, minutes=30))
    assert (again.drawn_entries, again.overruns) == (0, 0)  # idempotent

    # Day 2, 06:00 local: 3 more hours over the night, split by wall-clock time (6 h on day 1, 6 h on day 2).
    _reading(api, f.owner, job, "DAILY", "1009", t0 + timedelta(hours=18))
    s2 = _sweep(t0 + timedelta(hours=18, minutes=1))
    assert _held(f, job) == {d1: Decimal("7.5"), d2: Decimal("1.5")}
    alerts_sql = "SELECT count(*) FROM hours_low_balance_alert"
    assert sql(alerts_sql)[0][0] == 1 and s2.customer_sms == 1  # 1 h left (threshold 3), nothing else on the machine
    again2 = _sweep(t0 + timedelta(hours=18, minutes=2))
    assert (again2.low_balance_alerts, again2.customer_sms, sql(alerts_sql)[0][0]) == (0, 0, 1)  # once per crossing

    # Day 2, 08:00: 4 more hours but only 1 left -> drawn 1, the rest is an overrun the day it happens.
    _reading(api, f.owner, job, "DAILY", "1013", t0 + timedelta(hours=20))
    s3 = _sweep(t0 + timedelta(hours=20, minutes=1))
    assert s3.overruns == 1
    assert _held(f, job) == {d1: Decimal("7.5"), d2: Decimal("2.5")}
    exc = tenant_sql(
        f.tid,
        "SELECT status, blocking, evidence FROM job_exception WHERE job_id = :j AND dedupe_key LIKE :k",
        j=job,
        k="%:DAILY",
    )
    assert len(exc) == 1 and exc[0][0] == "OPEN" and exc[0][1] is True
    assert Decimal(exc[0][2]["excess_hours"]) == 3

    # New verified hours cover the shortfall at the next sweep and clear the exception.
    top_up = purchase(api, f.accountant, f, "5", pay=str(5 * RATE))
    verify(f.accountant2, top_up["payment"]["id"])
    s4 = _sweep(t0 + timedelta(hours=20, minutes=10))
    assert s4.overruns == 0
    assert _held(f, job) == {d1: Decimal("7.5"), d2: Decimal("5.5")}
    status = tenant_sql(f.tid, "SELECT status FROM job_exception WHERE dedupe_key LIKE :k", k="%:DAILY")
    assert status == [("EXPLAINED",)]

    # Completion: the final allocation replaces the provisional hours; totals reconcile.
    _complete(api, f, job, "1013", t0 + timedelta(hours=21))
    wea = _ok(f.owner.get(f"{T}/work-execution-allocations", job_id=job))["items"][0]
    assert (Decimal(wea["billable_hours"]), Decimal(wea["consumed_hours"]), Decimal(wea["overrun_hours"])) == (
        Decimal(13),
        Decimal(13),
        Decimal(0),
    )
    assert _held(f, job) == {}
    assert Decimal(get_purchase(f.owner, first["id"])["totals"]["consumed"]) == 10
    second = get_purchase(f.owner, top_up["id"])["totals"]
    assert (Decimal(second["consumed"]), Decimal(second["remaining"]), Decimal(second["provisional"])) == (
        Decimal(3),
        Decimal(2),
        Decimal(0),
    )
    sums = dict(
        tenant_sql(
            f.tid,
            "SELECT entry_type, sum(hours) FROM hours_ledger_entry WHERE job_id = :j GROUP BY entry_type",
            j=job,
        )
    )
    assert Decimal(sums["PROVISIONAL"]) == Decimal(sums["PROVISIONAL_REVERSED"]) == 13
    assert Decimal(sums["CONSUMED"]) == 13

    # Office notification once per crossing, linked to the purchase; the customer's SMS was queued (SMS credits).
    drain(api)
    rows = sql(
        "SELECT link, entity_type, entity_id, data FROM notification WHERE notification_type = 'HOURS_LOW_BALANCE'"
    )
    assert rows
    by_purchase = {r[2] for r in rows}
    assert first["id"] in by_purchase
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

    # Statement for the two days: bought, activated, used per day/job, remaining; the PDF is the same statement.
    st = _ok(
        f.owner.get(f"{T}/customers/{f.customer_id}/hours-statement", date_from=d1.isoformat(), date_to=d2.isoformat())
    )
    tot = st["totals"]
    assert Decimal(tot["opening_balance"]) == 0 and Decimal(tot["bought"]) == 15 and Decimal(tot["activated"]) == 15
    assert Decimal(tot["used"]) == 13 and Decimal(tot["closing_balance"]) == 2
    assert Decimal(tot["provisional_at_close"]) == 0
    usage = {(u["day"], u["basis"]): Decimal(u["hours"]) for u in st["usage"]}
    assert usage[(d1.isoformat(), "DAILY")] == Decimal("7.5")
    assert sum(usage.values()) == 13
    assert {u["job_number"] for u in st["usage"]} == {"P-DAY"}
    assert st["customer_name"] and [p["purchase_number"] for p in st["purchases"]] == [
        first["purchase_number"],
        top_up["purchase_number"],
    ]
    assert Decimal(st["lines"][-1]["balance_after"]) == 2
    pdf = f.owner.get(st["pdf_path"])
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")


def test_switching_daily_drawdown_off_mid_job_keeps_totals_reconciled(api: Api) -> None:
    f = _setup(api)
    hours_policy(f, drawdown="DAILY")
    p = purchase(api, f.accountant, f, "8", pay=str(8 * RATE))
    verify(f.accountant2, p["payment"]["id"])
    job, t0 = _start(api, f, "P-OFF", "500")
    _reading(api, f.owner, job, "DAILY", "503", t0 + timedelta(hours=3))
    _sweep(t0 + timedelta(hours=3, minutes=1))
    got = get_purchase(f.owner, p["id"])["totals"]
    assert (Decimal(got["remaining"]), Decimal(got["provisional"])) == (Decimal(5), Decimal(3))
    bal = _ok(f.owner.get(f"{T}/customers/{f.customer_id}/hours-balances"))
    assert Decimal(bal[0]["remaining"]) == 5 and Decimal(bal[0]["provisional"]) == 3
    ledger = _ok(f.owner.get(f"{T}/hours-ledger", job_id=job, entry_type="PROVISIONAL"))["items"]
    assert len(ledger) == 1 and ledger[0]["usage_day"] and Decimal(ledger[0]["signed_hours"]) == -3

    hours_policy(f, drawdown="AT_COMPLETION")  # held hours stay until completion; nothing more is drawn daily
    _reading(api, f.owner, job, "DAILY", "505", t0 + timedelta(hours=5))
    assert _sweep(t0 + timedelta(hours=5, minutes=1)).drawn_entries == 0
    assert Decimal(get_purchase(f.owner, p["id"])["totals"]["provisional"]) == 3
    _complete(api, f, job, "506", t0 + timedelta(hours=6))
    got = get_purchase(f.owner, p["id"])["totals"]
    assert (Decimal(got["consumed"]), Decimal(got["provisional"]), Decimal(got["remaining"])) == (
        Decimal(6),
        Decimal(0),
        Decimal(2),
    )


def test_statement_validates_the_period_and_the_customer(api: Api) -> None:
    f = _setup(api)
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
