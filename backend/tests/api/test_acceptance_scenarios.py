"""Guideline section 9: the thirteen scenarios the developer must demonstrate, one test each. Each runs against the API
and asserts the outcome the guideline states; scenario 13 traces a customer-hour, an excavator-hour and a cash balance
back to the records underneath them and checks the arithmetic."""

from datetime import timedelta
from decimal import Decimal
from itertools import pairwise
from typing import Any

from asseta.modules.hours.models import SIGN, LedgerEntryType
from tests.api.test_adjustments import _approve, _ledger, _paid_purchase, _propose
from tests.api.test_cash_custody_chain import _collect, _held, _staff
from tests.api.test_customer_hours import _setup
from tests.api.test_finance_sync import _h, _op, _push, _register
from tests.api.test_work_allocation import (
    _allocations,
    _baseline,
    _by_kind,
    _cancel_setup_job,
    _cap,
    _close,
    _ctx,
    _day,
    _flags,
    _job,
    _reading,
    _start,
)
from tests.support.api import Actor, Api
from tests.support.finance import FinCtx, complete_job, setup_finance, tenant_sql
from tests.support.hours import RATE, balance, get_purchase, hours_policy, prepaid_job, purchase, verify
from tests.support.jobs import capture

T = "/api/v1/tenant"
C = f"{T}/cash"
T1 = "2026-11-01T07:00:00+00:00"


def _ok(r: Any, status: int = 200) -> Any:
    assert r.status_code == status, r.text
    return r.json()


def _code(r: Any) -> str:
    return str(r.json()["error"]["code"])


def _remaining(f: FinCtx, machine_id: str | None = None) -> Decimal:
    b = balance(f.owner, f.customer_id, machine_id or f.c.t.machine_id)
    return Decimal(0) if b is None else Decimal(b["remaining"])


def _lookup(actor: Actor, reference: str) -> list[dict[str, Any]]:
    return list(_ok(actor.get(f"{T}/lookup", reference=reference))["matches"])


def _one(actor: Actor, reference: str, record_type: str) -> dict[str, Any]:
    return next(m for m in _lookup(actor, reference) if m["record_type"] == record_type)


def _cash_summary(actor: Actor) -> dict[str, Any]:
    return dict(_ok(actor.get(f"{T}/accountability/summary"))["cash_section"])


def _lines(figure: dict[str, Any]) -> list[tuple[str, str]]:
    return [(x["currency"], x["amount"]) for x in figure["lines"]]


def _paid(api: Api, f: FinCtx, hours: int) -> dict[str, Any]:
    """A purchase paid in full; verified by someone other than the person who recorded it."""
    p = purchase(api, f.accountant, f, str(hours), pay=str(hours * RATE))
    verify(f.accountant2, p["payment"]["id"])
    return get_purchase(f.owner, p["id"])


def _handover(f: FinCtx, staff: str, amount: str) -> dict[str, Any]:
    body = {"staff_member_id": staff, "amount": amount, "handed_at": T1, "partial_reason": "Bank closed early"}
    out: dict[str, Any] = _ok(f.manager.post(f"{C}/handovers", body), 201)
    return out


def _sole(f: FinCtx) -> str:
    """A custodian with cash of their own (a login-less operator keeps the recorders independent of them)."""
    return _staff(f, "Operator Selemani")


# --- 1 to 5: customer hours ---------------------------------------------------------------------------------------
def test_scenario_01_confirmed_payment_makes_the_hours_available(api: Api) -> None:
    f = _setup(api)
    p = purchase(api, f.accountant, f, "10", pay=str(10 * RATE))
    assert p["status"] == "AWAITING_PAYMENT" and _remaining(f) == 0
    recorder_verifies = f.accountant.post(
        f"{T}/customer-payments/{p['payment']['id']}/decision", {"verified": True, "note": "Mine"}
    )
    assert recorder_verifies.status_code == 422 and _code(recorder_verifies) == "SEGREGATION_OF_DUTIES"

    verify(f.accountant2, p["payment"]["id"])

    after = get_purchase(f.owner, p["id"])
    assert after["status"] == "ACTIVE" and Decimal(after["totals"]["activated_from_payments"]) == 10
    assert _remaining(f) == 10


def test_scenario_02_unconfirmed_payment_leaves_the_hours_inactive(api: Api) -> None:
    f = _setup(api)
    p = purchase(api, f.accountant, f, "10", pay=str(10 * RATE))

    still = get_purchase(f.owner, p["id"])
    assert still["status"] == "AWAITING_PAYMENT" and p["payment"]["status"] == "CLAIMED"
    assert Decimal(still["totals"]["activated"]) == 0 and _remaining(f) == 0
    assert _ok(f.owner.get(f"{T}/hours-ledger", purchase_id=p["id"]))["total"] == 0
    # Inactive means unusable: a prepaid job cannot start against them.
    job = prepaid_job(api, f, "S2-1")
    _ok(f.owner.post(f"{T}/meter-captures", capture(job, "OPENING", "100", api.clock.now, mode="MANUAL")), 201)
    blocked = f.owner.post(f"{T}/jobs/{job}/transitions", {"action": "START"})
    assert blocked.status_code == 422 and _code(blocked) == "NO_AVAILABLE_HOURS"


def test_scenario_03_part_use_leaves_the_right_balance(api: Api) -> None:
    f = _setup(api)
    p = _paid(api, f, 10)
    complete_job(api, f, prepaid_job(api, f, "S3-1"), "100", "104", 4)

    b = balance(f.owner, f.customer_id, f.c.t.machine_id)
    assert b is not None and (Decimal(b["activated"]), Decimal(b["consumed"]), Decimal(b["remaining"])) == (
        Decimal(10),
        Decimal(4),
        Decimal(6),
    )
    assert Decimal(get_purchase(f.owner, p["id"])["totals"]["remaining"]) == 6


def test_scenario_04_each_purchase_keeps_its_own_history_and_balance(api: Api) -> None:
    f = _setup(api)
    first, second = _paid(api, f, 4), _paid(api, f, 3)
    complete_job(api, f, prepaid_job(api, f, "S4-1"), "100", "105", 5)  # oldest lot first, then one hour of the next

    one, two = get_purchase(f.owner, first["id"]), get_purchase(f.owner, second["id"])
    assert (Decimal(one["hours"]), Decimal(one["totals"]["remaining"])) == (Decimal(4), Decimal(0))
    assert (Decimal(two["hours"]), Decimal(two["totals"]["remaining"])) == (Decimal(3), Decimal(2))
    assert _remaining(f) == 2
    for p, expected in ((one, {"ACTIVATED", "CONSUMED"}), (two, {"ACTIVATED", "CONSUMED"})):
        rows = _ok(f.owner.get(f"{T}/hours-ledger", purchase_id=p["id"]))["items"]
        assert {e["entry_type"] for e in rows} == expected
        assert {e["purchase_number"] for e in rows} == {p["purchase_number"]}


def test_scenario_05_hours_reassigned_with_approval_keep_the_original_assignment(api: Api) -> None:
    f = _setup(api)
    other = _ok(f.owner.post(f"{T}/machines", {"asset_code": "EXC-900", "name": "Backup excavator"}), 201)["id"]
    p = _paid(api, f, 6)
    body = {"purchase_id": p["id"], "to_machine_id": other, "hours": "4", "reason": "Breakdown"}

    t = _ok(f.supervisor.post(f"{T}/hours-transfers", body), 201)
    assert t["status"] == "PENDING" and _remaining(f, other) == 0  # nothing moves before approval
    approved = _ok(f.manager.post(f"{T}/hours-transfers/{t['id']}/decision", {"approve": True}))
    assert approved["status"] == "APPROVED"

    got = get_purchase(f.owner, p["id"])
    assert got["machine_id"] == f.c.t.machine_id  # the original assignment
    assert {m["machine_id"]: Decimal(m["remaining"]) for m in got["machines"]} == {
        f.c.t.machine_id: Decimal(2),
        other: Decimal(4),
    }
    assert _ok(f.owner.get(f"{T}/hours-transfers", purchase_id=p["id"]))["total"] == 1


# --- 6 and 7: excavator hours -------------------------------------------------------------------------------------
def test_scenario_06_operating_hours_reconcile_against_customer_and_authorized_work(api: Api) -> None:
    c, approver, _ = _ctx(api, "Scenario Six")
    o, t0 = c.owner, api.clock.now
    _baseline(o, approver, c, "1000", t0 - timedelta(hours=1))
    _start(c, c.job_id, "1000", t0)
    _close(c, c.job_id, "1006", t0 + timedelta(hours=6))
    _ok(_cap(o, _reading(None, c.t.machine_id, "DAILY", "1008", t0 + timedelta(hours=8))), 201)
    # The two hours outside the job are authorized by a second person: moved to the yard for a service.
    reason = _ok(
        o.post(f"{T}/engine-hour-reasons", {"code": "MAINT", "name": "Servicing", "kind": "NON_CUSTOMER_CATEGORY"}), 201
    )
    segment = _ok(o.get(f"{T}/engine-hours/unallocated"))["items"][0]
    proposed = _ok(
        o.post(
            f"{T}/engine-hours/classifications",
            {
                "machine_id": c.t.machine_id,
                "start_ref": segment["start"]["ref"],
                "end_ref": segment["end"]["ref"],
                "outcome": "APPROVED_NON_CUSTOMER",
                "reason_id": reason["id"],
                "note": "Moved to the yard for a service",
            },
        ),
        201,
    )
    decide = {"decision": "APPROVE", "note": "Service record seen"}
    _ok(approver.post(f"{T}/engine-hours/classifications/{proposed['id']}/decision", decide))

    rows = _allocations(o, machine_id=c.t.machine_id)
    assert _by_kind(rows) == {"CUSTOMER_WORK": Decimal(6), "AUTHORIZED_ACTIVITY": Decimal(2)}
    day = _day(c, t0.date())
    assert (Decimal(day["total_engine_hours"]), Decimal(day["difference_hours"])) == (Decimal(8), Decimal(0))
    assert (Decimal(day["customer_hours"]), Decimal(day["authorized_hours"]), Decimal(day["unexplained_hours"])) == (
        Decimal(6),
        Decimal(2),
        Decimal(0),
    )
    assert day["reconciled"] is True


def test_scenario_07_unexplained_hours_are_flagged_not_billable_not_wasted(api: Api) -> None:
    c, approver, tid = _ctx(api, "Scenario Seven")
    o, t0 = c.owner, api.clock.now
    _ok(
        o.post(
            f"{T}/policies/REVENUE_RECONCILIATION/versions",
            {"scope": "TENANT", "values": {"enabled": True, "period": "DAY"}, "reason": "On for this scenario"},
        ),
        201,
    )
    _baseline(o, approver, c, "1000", t0 - timedelta(hours=1))
    _cancel_setup_job(c)
    job = _job(api, c, "J-S7", rate="85000")
    _start(c, job, "1000", t0)
    _close(c, job, "1004", t0 + timedelta(hours=4))
    _ok(_cap(o, _reading(None, c.t.machine_id, "DAILY", "1006", t0 + timedelta(hours=6))), 201)

    # Flagged.
    assert _flags(tid, c, "UNEXPLAINED_HOURS") == 1
    assert [e["status"] for e in _ok(o.get(f"{T}/exceptions", exception_type="UNEXPLAINED_HOURS"))["items"]] == ["OPEN"]
    # Visible as its own kind, on nobody's account.
    [unexplained] = _allocations(o, kind="UNEXPLAINED")
    assert Decimal(unexplained["hours"]) == 2 and unexplained["status"] == "ACTIVE"
    assert unexplained["customer_id"] is None and unexplained["job_id"] is None
    # Not billable: expected revenue comes from the job alone and the invoice can only be for the job's hours.
    money = _ok(o.get(f"{T}/daily-machine-sheet", day_from=t0.date(), day_to=t0.date()))["items"][0]["money"][0]
    assert Decimal(money["expected"]) == 4 * Decimal(85000)
    assert Decimal(money["unexplained_hours"]) == 2 and Decimal(money["unexplained_expected"]) == 0
    # Not wasted: no decision was taken about them, and nothing wrote them off.
    assert _ok(o.get(f"{T}/engine-hours/classifications"))["total"] == 0
    assert _ok(o.get(f"{T}/non-revenue-approvals"))["total"] == 0
    assert _by_kind(_allocations(o, machine_id=c.t.machine_id)).get("AUTHORIZED_ACTIVITY") is None
    # The value at risk is a separate line from expected revenue.
    assert Decimal(money["value_at_risk"]) == 2 * Decimal(85000)
    tile = _ok(o.get(f"{T}/accountability/summary"))["unexplained_hours"]
    assert Decimal(tile["hours"]) == 2 and Decimal(tile["value_at_risk"][0]["amount"]) == 2 * Decimal(85000)


# --- 8 to 10: cash ------------------------------------------------------------------------------------------------
def test_scenario_08_cash_to_a_manager_moves_custody_but_is_not_remitted(api: Api) -> None:
    f = setup_finance(api)
    operator = _sole(f)
    manager = _staff(f, "Field Manager", "OTHER", login=f.manager)
    _collect(f.manager, f, operator, "300000")

    moved = _ok(
        f.manager.post(
            f"{C}/transfers",
            {"from_staff_id": operator, "to_staff_id": manager, "amount": "300000", "transferred_at": T1},
        ),
        201,
    )

    assert moved["status"] == "ACKNOWLEDGED"
    assert _held(f.accountant, operator)["outstanding"] == 0
    assert _held(f.accountant, manager)["outstanding"] == 300000
    assert _ok(f.owner.get(f"{C}/handovers"))["total"] == 0  # no remittance exists
    s = _cash_summary(f.owner)
    assert _lines(s["confirmed_by_company"]) == [] and _lines(s["declared_for_remittance"]) == []
    assert _lines(s["outstanding"]) == [("TZS", "300000.0000")]  # still with the company's people, not the company


def test_scenario_09_a_declared_deposit_clears_nothing_until_confirmed(api: Api) -> None:
    f = setup_finance(api)
    operator = _sole(f)
    _collect(f.manager, f, operator, "150000")

    deposit = _handover(f, operator, "150000")

    assert deposit["status"] == "CLAIMED" and deposit["evidence_status"] == "DECLARED"
    held = _held(f.accountant, operator)
    assert held["outstanding"] == 150000 and held["claimed_unverified_handovers"] == 150000
    assert _lines(_cash_summary(f.owner)["confirmed_by_company"]) == []
    own = f.manager.post(f"{C}/handovers/{deposit['id']}/decision", {"verified": True})
    assert own.status_code == 403  # the person declaring it holds no confirmation permission

    confirmed = _ok(f.accountant.post(f"{C}/handovers/{deposit['id']}/decision", {"verified": True}))

    assert confirmed["status"] == "VERIFIED" and confirmed["evidence_status"] == "CONFIRMED"
    assert _held(f.accountant, operator)["outstanding"] == 0
    assert _lines(_cash_summary(f.owner)["confirmed_by_company"]) == [("TZS", "150000.0000")]


def test_scenario_10_a_partial_confirmation_reduces_only_what_was_confirmed(api: Api) -> None:
    f = setup_finance(api)
    operator = _sole(f)
    _collect(f.manager, f, operator, "200000")
    deposit = _handover(f, operator, "100000")

    confirmed = _ok(
        f.accountant.post(f"{C}/handovers/{deposit['id']}/decision", {"verified": True, "amount_received": "60000"})
    )

    assert Decimal(confirmed["amount_received"]) == 60000
    assert _held(f.accountant, operator)["outstanding"] == 140000  # 200,000 less the 60,000 received, never the 100,000
    assert _lines(_cash_summary(f.owner)["confirmed_by_company"]) == [("TZS", "60000.0000")]
    [variance] = _ok(f.owner.get(f"{C}/variances", source_type="REMITTANCE"))["items"]
    assert variance["source_id"] == deposit["id"] and Decimal(variance["amount"]) == 40000
    assert variance["status"] == "OPEN"


# --- 11 and 12 ----------------------------------------------------------------------------------------------------
def test_scenario_11_an_adjustment_keeps_the_original_and_its_approval_history(api: Api) -> None:
    f = _setup(api)
    hours_policy(f, adjustment_evidence_required=False)
    p = _paid_purchase(api, f, "10")
    before = _ok(f.owner.get(f"{T}/hours-ledger", purchase_id=p["id"]))["items"]

    request = _ok(_propose(f.manager, request_type="HOURS_CORRECTION", purchase_id=p["id"], hours="-2"), 201)
    assert request["status"] == "PROPOSED" and _ledger(f.owner, original_id=p["id"]) == []
    own = _approve(f.manager, request["id"])
    assert own.status_code in (403, 422)
    _ok(_approve(f.owner, request["id"]))

    [entry] = _ledger(f.owner, original_id=p["id"])
    assert entry["original_type"] == "hours_purchase" and entry["original_reference"] == p["purchase_number"]
    assert (Decimal(entry["original_value"]), Decimal(entry["new_value"])) == (Decimal(10), Decimal(8))
    assert entry["requested_by_name"] and entry["approved_by_name"] and entry["requested_by"] != entry["approved_by"]
    assert entry["reason"] and entry["requested_at"] and entry["approved_at"]
    # The original purchase and its ledger entries are as they were; the correction is an addition beside them.
    kept = get_purchase(f.owner, p["id"])
    assert kept["purchase_number"] == p["purchase_number"] and Decimal(kept["hours"]) == 10
    after = _ok(f.owner.get(f"{T}/hours-ledger", purchase_id=p["id"]))["items"]
    assert {e["id"] for e in before} < {e["id"] for e in after}
    assert _remaining(f) == 8


def test_scenario_12_offline_entries_synchronize_without_duplication_or_loss(api: Api) -> None:
    f = _setup(api)
    _register(api, f)
    assert api.client.get("/api/v1/sync/bootstrap", headers=_h(f.supervisor)).status_code == 200
    now = api.clock.now.isoformat()
    collection = _op(
        "CASH_COLLECTION",
        {"client_id": "6b1f7a52-2d5a-4f43-9d7e-0c9a3b0e0001", "customer_id": f.customer_id, "amount": "300000"}
        | {"received_at": now},
    )
    hours = _op(
        "HOURS_PURCHASE",
        {
            "walk_in": {"name": "Roadside customer"},
            "machine_id": f.c.t.machine_id,
            "hours": "3",
            "payment": {"method": "CASH", "received_at": now},
        },
    )
    batch = [collection, hours]

    assert [r["status"] for r in _push(api, f.supervisor, batch)] == ["ACKED", "ACKED"]
    assert [r["status"] for r in _push(api, f.supervisor, batch)] == ["DUPLICATE", "DUPLICATE"]  # a retried upload
    assert [r["status"] for r in _push(api, f.supervisor, batch)] == ["DUPLICATE", "DUPLICATE"]

    [(purchases, payments, walk_ins, ops)] = tenant_sql(
        f.tid,
        "SELECT (SELECT count(*) FROM hours_purchase), (SELECT count(*) FROM customer_payment),"
        " (SELECT count(*) FROM customer WHERE kind = 'WALK_IN'), (SELECT count(*) FROM client_operation)",
    )
    assert (purchases, payments, walk_ins) == (1, 2, 1) and ops == 2  # both arrived, each exactly once
    p = _ok(f.owner.get(f"{T}/hours-purchases"))["items"][0]
    assert p["source"] == "SYNC" and p["status"] == "AWAITING_PAYMENT"  # offline never bypasses confirmation
    # The cash of both entries is in the recorder's custody, once: 300,000 collected and the purchase's 3 hours.
    assert _held(f.accountant, f.sup_staff_id)["outstanding"] == 300000 + 3 * RATE


# --- 13: tracing balances back --------------------------------------------------------------------------------------
def _trace_customer_hours(f: FinCtx, machine: str, job_number: str) -> None:
    """The balance is exactly the ledger under it; each line names its purchase and its source record."""
    b = balance(f.owner, f.customer_id, machine)
    assert b is not None
    remaining = Decimal(b["remaining"])
    assert remaining == 3  # 6 + 4 activated less 7 consumed

    entries = _ok(f.owner.get(f"{T}/hours-ledger", customer_id=f.customer_id, machine_id=machine))["items"]
    assert sum(SIGN[LedgerEntryType(e["entry_type"])] * Decimal(e["hours"]) for e in entries) == remaining
    activated = [e for e in entries if e["entry_type"] == "ACTIVATED"]
    consumed = [e for e in entries if e["entry_type"] == "CONSUMED"]
    assert sum(Decimal(e["hours"]) for e in activated) == Decimal(b["activated"]) == 10
    assert sum(Decimal(e["hours"]) for e in consumed) == Decimal(b["consumed"]) == 7

    # Each activation goes back to the payment that was independently confirmed.
    for e in activated:
        purchase_row = _one(f.owner, e["purchase_number"], "hours_purchase")
        assert purchase_row["id"] == e["purchase_id"] and purchase_row["route"].endswith(e["purchase_id"])
        payment = _ok(f.owner.get(f"{T}/customer-payments/{e['payment_id']}"))
        assert payment["status"] == "VERIFIED" and payment["verified_by"] != payment["recorded_by"]
    # Each purchase's remainder adds up to the balance.
    numbers = {e["purchase_number"] for e in entries}
    assert sum(Decimal(_one(f.owner, n, "hours_purchase")["hours_remaining"]) for n in numbers) == remaining
    # Each consumption goes back to the job, and the job to the excavator work allocated to its purchases.
    assert {e["job_number"] for e in consumed} == {job_number}
    job = _one(f.owner, job_number, "job")
    assert job["route"] == f"/tenant/jobs/{job['id']}"
    work = _allocations(f.owner, job_id=job["id"])
    assert sum(Decimal(row["hours"]) for row in work) == 7
    by_purchase: dict[str, Decimal] = {}
    for row in work:
        for lot in row["lots"]:
            by_purchase[lot["purchase_number"]] = by_purchase.get(lot["purchase_number"], Decimal(0)) + Decimal(
                lot["hours"]
            )
    assert by_purchase == {e["purchase_number"]: Decimal(e["hours"]) for e in consumed}


def _trace_excavator_hours(f: FinCtx, day: Any, job_number: str) -> None:
    """Every engine hour of the day is an allocation; every allocation is the difference of two recorded readings."""
    machine = f.c.t.machine_id
    params = {"machine_id": machine, "from": day.isoformat(), "to": day.isoformat()}
    [balance_row] = _ok(f.owner.get(f"{T}/work-allocations/reconciliation", **params))
    total = Decimal(balance_row["total_engine_hours"])
    assert total == 9 and balance_row["reconciled"] is True and Decimal(balance_row["difference_hours"]) == 0
    assert Decimal(balance_row["customer_hours"]) == 7 and Decimal(balance_row["unexplained_hours"]) == 2

    rows = _allocations(f.owner, machine_id=machine)
    assert sum(Decimal(r["hours"]) for r in rows) == total
    assert _by_kind(rows) == {"CUSTOMER_WORK": Decimal(7), "UNEXPLAINED": Decimal(2)}
    for row in rows:
        assert Decimal(row["hours"]) == Decimal(row["end_reading"]) - Decimal(row["start_reading"])
        start = _ok(f.owner.get(f"{T}/meter-captures/{row['start_ref']}"))
        end = _ok(f.owner.get(f"{T}/meter-captures/{row['end_ref']}"))
        assert (Decimal(start["reading"]), Decimal(end["reading"])) == (
            Decimal(row["start_reading"]),
            Decimal(row["end_reading"]),
        )
        assert start["machine_id"] == end["machine_id"] == machine
        assert _ok(f.owner.get(f"{T}/work-allocations/{row['id']}"))["id"] == row["id"]
    customer = next(r for r in rows if r["kind"] == "CUSTOMER_WORK")
    assert customer["job_number"] == job_number and customer["customer_id"] == f.customer_id
    # The readings line up with no gap: the hours cannot have been counted twice or dropped.
    ordered = sorted(rows, key=lambda r: Decimal(r["start_reading"]))
    assert all(a["end_reading"] == b["start_reading"] for a, b in pairwise(ordered))


def _total(rows: list[dict[str, Any]]) -> Decimal:
    return sum((Decimal(r["amount"]) for r in rows), Decimal(0))


def _trace_cash(f: FinCtx, staff: str, day: Any, records: dict[str, dict[str, Any]]) -> None:
    """The custodian's balance is the sum of the signed transactions behind each figure, each opening by its number."""
    outstanding = _held(f.accountant, staff)["outstanding"]
    assert outstanding == 220000  # 500,000 collected - 100,000 handed on - 180,000 received by the company

    def drill(figure: str) -> list[dict[str, Any]]:
        q = {"staff_member_id": staff, "from": day.isoformat(), "to": day.isoformat(), "figure": figure}
        return list(_ok(f.accountant.get(f"{C}/reconciliation/transactions", **q))["items"])

    collections, moved_out, received = drill("collections"), drill("transfers_out"), drill("verified_handovers")
    assert (_total(collections), _total(moved_out), _total(received)) == (
        Decimal(500000),
        Decimal(100000),
        Decimal(180000),
    )
    assert _total(collections) - _total(moved_out) - _total(received) == outstanding
    [recon] = _ok(
        f.accountant.get(f"{C}/reconciliation", staff_member_id=staff, **{"from": day, "to": day}),
    )["days"]
    assert Decimal(recon["outstanding"]) == outstanding

    for number, record_type, record in (
        (records["collection"]["collection_number"], "customer_payment", records["collection"]),
        (records["remittance"]["remittance_number"], "cash_handover", records["remittance"]),
        (records["transfer"]["transfer_number"], "cash_transfer", records["transfer"]),
    ):
        match = _one(f.owner, number, record_type)
        assert match["id"] == record["id"] and match["route"].endswith(record["id"]) and match["recorded_by_name"]
    remitted = _one(f.owner, records["remittance"]["remittance_number"], "cash_handover")
    assert Decimal(remitted["amount"]) == 200000 and remitted["decided_by_name"]
    # The 20,000 the company did not receive is a record of its own, reachable by id, not netted away.
    variance = _one(f.owner, records["variance"]["id"], "cash_variance")
    assert Decimal(variance["amount"]) == 20000
    # The same balance on the employee's page.
    employee = _ok(f.owner.get(f"{T}/employees/{staff}/accountability", date_from=day, date_to=day))
    held = next(c for c in employee["cash_held"] if c["currency"] == "TZS")
    assert Decimal(held["outstanding"]) == outstanding
    assert _total(employee["collections"]) == 500000


def test_scenario_13_management_traces_each_balance_to_its_transactions(api: Api) -> None:
    f = _setup(api)
    t0 = api.clock.now
    machine = f.c.t.machine_id
    # Customer-hour balance: two purchases, part used by one job.
    _paid(api, f, 6)
    _paid(api, f, 4)
    job_number = "S13-1"
    job = prepaid_job(api, f, job_number)
    complete_job(api, f, job, "1000", "1007", 7)
    # Excavator-hour balance: the machine ran two more hours nobody has explained.
    _ok(_cap(f.owner, _reading(None, machine, "DAILY", "1009", t0 + timedelta(hours=9))), 201)
    # Cash balance: a collection, part handed to a manager, part deposited and short at the company.
    operator = _sole(f)
    manager = _staff(f, "Field Manager", "OTHER", login=f.manager)
    collection = _collect(f.manager, f, operator, "500000")
    transfer = _ok(
        f.manager.post(
            f"{C}/transfers",
            {"from_staff_id": operator, "to_staff_id": manager, "amount": "100000", "transferred_at": T1},
        ),
        201,
    )
    remittance = _handover(f, operator, "200000")
    _ok(
        f.accountant.post(f"{C}/handovers/{remittance['id']}/decision", {"verified": True, "amount_received": "180000"})
    )
    [variance] = _ok(f.owner.get(f"{C}/variances", source_type="REMITTANCE"))["items"]

    _trace_customer_hours(f, machine, job_number)
    _trace_excavator_hours(f, t0.date(), job_number)
    _trace_cash(
        f,
        operator,
        t0.date(),
        {"collection": collection, "transfer": transfer, "remittance": remittance, "variance": variance},
    )
