"""Real responses the phones and the web decode, kept as fixtures under `contracts/fixtures/` (machine reports, the
report status / context / available hours, credit sales, credit invoices, customer hours and the Supervisor app's
ADR-008 sync snapshot). The Android, iOS and web suites decode every fixture, so a field the apps get wrong (a missing
optional, an unknown enum value, a differently shaped finding) fails their build instead of a screen on live.

The scenario covers the shapes that differ: an OPENING report (first reading: no lines, 0 hours, a finding on its
reading), a normal SUBMITTED report, a REJECTED report and its APPROVED correction (lots), and a cash + credit sale
with a part-paid credit invoice. `ASSETA_WRITE_FIXTURES=1` rewrites the files; otherwise the test checks that every
committed fixture still has exactly the fields the server sends (recursively), so the fixtures cannot drift."""

import json
import os
import uuid
from pathlib import Path
from typing import Any

from tests.support.api import Actor, Api
from tests.support.hours import RATE
from tests.support.machine_reports import (
    T,
    bought,
    cust,
    field_credit,
    idle,
    later,
    ok,
    reading,
    report_body,
    setup_reports,
    submit,
)
from tests.support.meter import fix

ROOT = Path(__file__).parents[3] / "contracts" / "fixtures"
REPORTS = ROOT / "machine-reports"
CREDIT = ROOT / "credit-sales"
DEVICE = "android-contract-fixtures-01"


def _shape(value: Any) -> Any:
    """The field structure of a JSON value: keys (recursively) of objects, the merged shape of list items."""
    if isinstance(value, dict):
        return {k: _shape(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        merged: dict[str, Any] = {}
        for item in value:
            s = _shape(item)
            if isinstance(s, dict):
                merged.update(s)
        return [merged] if merged else []
    return None


def _keep(path: Path, body: Any) -> None:
    if os.environ.get("ASSETA_WRITE_FIXTURES") == "1":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(body, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
        return
    assert path.exists(), f"{path} is missing: run with ASSETA_WRITE_FIXTURES=1"
    assert _shape(json.loads(path.read_text())) == _shape(body), f"{path.name} drifted: rerun ASSETA_WRITE_FIXTURES=1"


def _bare(api: Api, owner: Actor, staff_id: str, prefix: str) -> str:
    """A machine assigned to the supervisor without any starting reading (its first report is an opening one)."""
    [machine] = api.add_machines(owner, 1, prefix=prefix)
    ok(
        owner.post(
            f"{T}/machines/{machine}/assignments",
            {"staff_member_id": staff_id, "role": "SUPERVISOR", "effective_from": api.clock.now.isoformat()},
        ),
        201,
    )
    return str(machine)


def test_contract_fixtures_for_reports_credit_and_customer_hours(api: Api) -> None:
    ctx = setup_reports(api, "Fixture Hire Ltd", "FIX-1")
    f, m = ctx.f, ctx.machine_id
    bought(api, f, 10)
    bare = _bare(api, f.owner, f.sup_staff_id, "OPEN")

    # The machine without a starting reading: its context and status ask for an opening report.
    _keep(REPORTS / "context-opening-required.json", ok(f.supervisor.get(f"{T}/machine-reports/context/{bare}")))

    # Opening report as the Supervisor app sends it: the DAILY reading first (an inaccurate GPS fix gives the reading
    # a finding), then the report naming it, no lines.
    at = later(api, 1)
    first = reading(bare, "1520.4", at)
    first["gps"] = fix(at, accuracy=900.0)
    ok(f.supervisor.post(f"{T}/meter-captures", first), 201)
    opening = submit(
        f.supervisor, {"id": str(uuid.uuid4()), "machine_id": bare, "capture_id": first["id"], "opening": True}
    )
    assert opening["opening"] is True and opening["start_source"] == "OPENING" and opening["lines"] == []
    detail = ok(f.owner.get(f"{T}/machine-reports/{opening['id']}"))
    assert detail["findings"], "the opening reading should carry a finding"
    _keep(REPORTS / "report-opening-submitted.json", detail)
    _keep(REPORTS / "meter-capture-opening.json", ok(f.owner.get(f"{T}/meter-captures/{first['id']}")))

    # A normal report, rejected, then corrected on the same reading and approved (its customer line gets lots).
    at = later(api, 4)
    lines = [cust(f.customer_id, 3), idle(ctx.reasons["TRANSIT"], 1)]
    rejected = submit(f.supervisor, report_body(m, "1004", at, lines))
    ok(f.manager.post(f"{T}/machine-reports/{rejected['id']}/reject", {"reason": "Customer hours look too high"}))
    fixed_lines = [cust(f.customer_id, 2), idle(ctx.reasons["TRANSIT"], 2, "Moved to the second site")]
    body = report_body(m, None, None, fixed_lines, capture_id=rejected["capture_id"])
    fixed = submit(f.supervisor, {**body, "corrects_report_id": rejected["id"]})
    _keep(REPORTS / "report-rejected.json", ok(f.owner.get(f"{T}/machine-reports/{rejected['id']}")))
    _keep(REPORTS / "report-approved.json", ok(f.manager.post(f"{T}/machine-reports/{fixed['id']}/approve", {})))

    # The next report waits for a decision (customer line with available hours, non-productive line with a note).
    at = later(api, 3)
    pending = submit(
        f.supervisor,
        report_body(m, "1007", at, [cust(f.customer_id, 2), idle(ctx.reasons["IDLE_ON_SITE"], 1)], note="Rain"),
    )
    _keep(REPORTS / "report-submitted.json", ok(f.owner.get(f"{T}/machine-reports/{pending['id']}")))

    # Lists and per-machine state, as the Owner and Supervisor apps read them.
    _keep(REPORTS / "list-pending.json", ok(f.owner.get(f"{T}/machine-reports", queue="PENDING")))
    _keep(REPORTS / "list-all.json", ok(f.owner.get(f"{T}/machine-reports")))
    _keep(REPORTS / "list-mine.json", ok(f.supervisor.get(f"{T}/machine-reports", mine="true")))
    _keep(REPORTS / "status.json", ok(f.owner.get(f"{T}/machine-reports/status")))
    _keep(REPORTS / "context.json", ok(f.supervisor.get(f"{T}/machine-reports/context/{m}")))
    _keep(
        REPORTS / "available-hours.json",
        ok(f.supervisor.get(f"{T}/machine-reports/available-hours", machine_id=m)),
    )

    # A field sale: cash 400,000 + credit 450,000 (850,000 for 10 hours), then a part payment of the credit invoice.
    field_credit(f)
    sale = ok(
        f.supervisor.post(
            f"{T}/hours-purchases",
            {
                "machine_id": m,
                "customer_id": f.customer_id,
                "hours": "10",
                "client_id": str(uuid.uuid4()),
                "payments": [
                    {"amount": "400000", "method": "CASH", "received_at": api.clock.now.isoformat()},
                    {"amount": str(10 * RATE - 400000), "method": "CREDIT"},
                ],
            },
        ),
        201,
    )
    invoice_id = sale["credit_invoice"]["id"]
    ok(
        f.accountant.post(
            f"{T}/credit-invoices/{invoice_id}/payments",
            {
                "client_id": str(uuid.uuid4()),
                "amount": "150000",
                "method": "MOBILE_MONEY",
                "reference": "MM-FIXTURE-0001",
                "received_at": api.clock.now.isoformat(),
            },
        ),
        201,
    )
    queue = ok(f.owner.get(f"{T}/hours-purchases", queue="CREDIT_TO_ACTIVATE"))
    assert [p["id"] for p in queue["items"]] == [sale["id"]]
    # Lists carry the order's own payment parts (not the credit invoice's payments), so the Owner app can sum the
    # money sold by method.
    assert [(x["method"], x["amount"]) for x in queue["items"][0]["payments"]] == [("CASH", "400000.0000")]
    _keep(CREDIT / "hours-purchases-credit-to-activate.json", queue)
    _keep(
        CREDIT / "hours-purchases-awaiting-activation.json",
        ok(f.owner.get(f"{T}/hours-purchases", queue="AWAITING_ACTIVATION")),
    )
    _keep(CREDIT / "credit-invoices.json", ok(f.owner.get(f"{T}/credit-invoices")))
    _keep(CREDIT / "credit-invoice.json", ok(f.owner.get(f"{T}/credit-invoices/{invoice_id}")))
    _keep(CREDIT / "customer-hours.json", ok(f.owner.get(f"{T}/customer-hours")))

    # The Supervisor app's ADR-008 snapshot (sync changes from the start).
    headers = {**f.supervisor.headers(True, None), "X-Device-Id": DEVICE}
    ok(
        api.client.post(
            "/api/v1/sync/devices",
            headers=headers,
            json={"device_id": DEVICE, "platform": "ANDROID", "app_version": "0.6.4"},
        ),
        201,
    )
    data = ok(api.client.get("/api/v1/sync/changes", headers=headers, params={"cursor": 0}))["data"]
    adr008 = (
        "machine_report_reasons",
        "machine_report_states",
        "machine_report_hours",
        "my_machine_reports",
        "open_credit_invoices",
    )
    _keep(REPORTS / "sync-snapshot.json", {k: data[k] for k in adr008})
