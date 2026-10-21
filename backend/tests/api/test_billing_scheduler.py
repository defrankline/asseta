"""Scheduled billing cycle: generates due invoices for all billable tenants, re-evaluates entitlements, and is
idempotent across repeated runs (hourly schedule / restarts)."""

from datetime import date

from asseta.workers.billing_scheduler import run_billing_cycle
from tests.support.api import Api


def test_cycle_generates_renewals_and_suspends_idempotently(api: Api) -> None:
    a = api.onboard("Sched A", price="1000", terms_days=7)
    b = api.onboard("Sched B", price="2000", cadence="YEARLY")
    pending = api.onboard("Sched Pending", price="5")  # not activated -> not billable
    for t in (a, b):
        api.activate(t)
        api.add_machines(t["owner"], 2, enroll_on=date(2026, 11, 1))

    first = run_billing_cycle(date(2026, 11, 1))
    assert (first.subscriptions, first.invoices_created, first.failures) == (2, 2, [])
    again = run_billing_cycle(date(2026, 11, 1))
    assert again.invoices_created == 0  # idempotent re-run

    # Monthly renewal on Dec 1; tenant A never paid Nov (due Nov 8) -> past grace (7) and suspend window (30)
    dec = run_billing_cycle(date(2026, 12, 15))
    assert dec.invoices_created == 1 and dec.entitlement_changes == 1
    sub_a = api.platform.get(f"/api/v1/platform/tenants/{a['tenant']['id']}/subscription").json()
    assert sub_a["status"] == "SUSPENDED"
    sub_b = api.platform.get(f"/api/v1/platform/tenants/{b['tenant']['id']}/subscription").json()
    # B's yearly invoice was due Nov 15: 30 days overdue = past grace (7) but not > suspend threshold (30);
    # PAST_DUE keeps FULL access under the seeded policy, so only A produced an entitlement change.
    assert sub_b["status"] == "PAST_DUE"
    invoices = api.platform.get("/api/v1/platform/invoices", tenant_id=pending["tenant"]["id"]).json()
    assert invoices["total"] == 0
