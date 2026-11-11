"""Sell hours and book the job in one step: the sale books its prepaid field job (linked, exactly once online and
offline), the contract is resolved or refused, approval may follow the verified money (tenant policy), approved jobs
on one machine conflict only when their planned windows overlap, and the cash of an hours sale may count as verified
with the confirmed handover or when recorded (tenant policy cash_activation). Every switch defaults to today."""

import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError

from tests.support.api import Actor, Api
from tests.support.finance import FinCtx, setup_finance, tenant_sql
from tests.support.hours import RATE, get_purchase, hours_policy, prepaid_job, verify
from tests.support.jobs import capture
from tests.support.notify import drain, member

T = "/api/v1/tenant"
C = f"{T}/cash"
DEVICE = "android-salebook-0001"


def _setup(api: Api) -> FinCtx:
    f = setup_finance(api)
    r = f.owner.post(f"{T}/jobs/{f.c.job_id}/transitions", {"action": "CANCEL", "reason": "Not needed"})
    assert r.status_code == 200, r.text  # frees the machine for the bookings below
    _policy(f)
    return f


def _policy(f: FinCtx, **values: Any) -> None:
    """The tenant's CUSTOMER_HOURS version for these tests: field staff may also record bank/mobile-money parts."""
    hours_policy(f, field_noncash_payments=True, **values)


def _code(r: Any) -> str:
    return str(r.json()["error"]["code"])


def _pay(api: Api, amount: Decimal | int | str, method: str = "CASH") -> dict[str, Any]:
    return {
        "amount": str(amount),
        "method": method,
        "reference": None if method == "CASH" else f"REF-{uuid.uuid4().hex[:10]}",
        "received_at": api.clock.now.isoformat(),
    }


def _sale(
    api: Api,
    f: FinCtx,
    hours: str,
    *,
    job: dict[str, Any] | None = None,
    payments: list[dict[str, Any]] | None = None,
    customer_id: str | None = None,
    walk_in: dict[str, Any] | None = None,
    client_id: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "machine_id": f.c.t.machine_id,
        "hours": hours,
        "client_id": client_id or str(uuid.uuid4()),
        "payments": payments if payments is not None else [_pay(api, Decimal(hours) * RATE)],
    }
    if walk_in is not None:
        body["walk_in"] = walk_in
    else:
        body["customer_id"] = customer_id or f.customer_id
    if job is not None:
        body["job"] = job
    return body


def _booking(api: Api, start_in_h: float = 0, **extra: Any) -> dict[str, Any]:
    return {"planned_start": (api.clock.now + timedelta(hours=start_in_h)).isoformat(), **extra}


def _ok(r: Any, status: int = 201) -> Any:
    assert r.status_code == status, r.text
    return r.json()


def _job(f: FinCtx, job_id: str) -> dict[str, Any]:
    out: dict[str, Any] = _ok(f.owner.get(f"{T}/jobs/{job_id}"), 200)["job"]
    return out


def _office_job(api: Api, f: FinCtx, number: str, start_in_h: float, hours: float | None) -> str:
    start = api.clock.now + timedelta(hours=start_in_h)
    body: dict[str, Any] = {
        "contract_id": f.c.contract_id,
        "job_number": number,
        "machine_id": f.c.t.machine_id,
        "planned_start": start.isoformat(),
    }
    if hours is not None:
        body["planned_end"] = (start + timedelta(hours=hours)).isoformat()
    job_id = str(_ok(f.owner.post(f"{T}/jobs", body))["id"])
    assert f.owner.post(f"{T}/jobs/{job_id}/transitions", {"action": "SUBMIT"}).status_code == 200
    return job_id


def _approve(f: FinCtx, job_id: str) -> Any:
    return f.owner.post(f"{T}/jobs/{job_id}/transitions", {"action": "APPROVE"})


def _audit(f: FinCtx, entity_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = _ok(f.owner.get(f"{T}/audit-events", entity_id=entity_id), 200)["items"]
    return items


def _inbox(actor: Actor) -> list[tuple[str, str, str]]:
    r = actor.get(f"{T}/notifications")
    assert r.status_code == 200, r.text
    return [(n["type"], n["title"], n["body"]) for n in r.json()["items"]]


def _device(api: Api, actor: Actor) -> dict[str, str]:
    h = {**actor.headers(True, None), "X-Device-Id": DEVICE}
    reg = api.client.post(
        "/api/v1/sync/devices", headers=h, json={"device_id": DEVICE, "platform": "ANDROID", "app_version": "0.6.0"}
    )
    assert reg.status_code == 201, reg.text
    return h


def _push(api: Api, h: dict[str, str], op: dict[str, Any]) -> dict[str, Any]:
    r = api.client.post(
        "/api/v1/sync/push", headers=h, json={"device_now": api.clock.now.isoformat(), "operations": [op]}
    )
    assert r.status_code == 200, r.text
    out: dict[str, Any] = r.json()["results"][0]
    return out


def _handover(api: Api, f: FinCtx, amount: Decimal | int) -> Any:
    """The supervisor declares a cash handover; the office counts the declared amount and confirms it."""
    h = _ok(f.supervisor.post(f"{C}/handovers", {"amount": str(amount), "handed_at": api.clock.now.isoformat()}))
    _ok(f.accountant.post(f"{C}/handovers/{h['id']}/decision", {"verified": True, "note": "Counted"}), 200)
    return h


def _payment(f: FinCtx, payment_id: str) -> Any:
    return _ok(f.accountant.get(f"{T}/customer-payments/{payment_id}"), 200)


def _outstanding(f: FinCtx) -> Decimal:
    rows = _ok(f.supervisor.get(f"{C}/custody/me"), 200)
    return Decimal(next(b["outstanding"] for b in rows if b["currency"] == "TZS"))


# --- booking with the sale ---------------------------------------------------------------------------------------
def test_sale_books_the_job_linked_and_exactly_once_online(api: Api) -> None:
    f = _setup(api)
    body = _sale(api, f, "6", job=_booking(api, 24, note="Trenching on plot 7"))
    p = _ok(f.supervisor.post(f"{T}/hours-purchases", body))
    job = p["job"]
    assert job is not None and job["status"] == "PENDING_APPROVAL"
    assert job["id"] == str(uuid.uuid5(uuid.UUID(body["client_id"]), "job"))
    assert (job["contract_id"], job["contract_number"]) == (f.c.contract_id, "CT-001")
    full = _job(f, job["id"])
    assert full["hours_purchase_id"] == p["id"] and full["billing_mode"] == "PREPAID_HOURS"
    assert (full["requested_by_staff_id"], full["supervisor_id"]) == (f.sup_staff_id, f.sup_staff_id)
    assert full["request_note"] == "Trenching on plot 7" and full["rate_source"].startswith("RATE_CARD:")
    assert "jobs.job.requested" in {e["action"] for e in _audit(f, job["id"])}

    # The same sale again (offline retry with the same client id) returns the one sale and the one job.
    again = _ok(f.supervisor.post(f"{T}/hours-purchases", body))
    assert (again["id"], again["job"]["id"]) == (p["id"], job["id"])
    assert get_purchase(f.owner, p["id"])["job"]["job_number"] == job["job_number"]
    counts = tenant_sql(f.tid, "SELECT count(*) FROM job WHERE hours_purchase_id IS NOT NULL")[0]
    assert counts[0] == 1
    # Approval stays with the approvers by default: the payment is claimed, the job waits.
    verify(f.accountant2, p["payments"][0]["id"])
    assert _job(f, job["id"])["status"] == "PENDING_APPROVAL"
    # A sale without a job books nothing (today's behaviour).
    plain = _ok(f.supervisor.post(f"{T}/hours-purchases", _sale(api, f, "1")))
    assert plain["job"] is None


def test_offline_sale_booking_is_applied_exactly_once(api: Api) -> None:
    f = _setup(api)
    h = _device(api, f.supervisor)
    boot = _ok(api.client.get("/api/v1/sync/bootstrap", headers=h), 200)
    assert "OP_HOURS_SALE_BOOKING" in boot["capabilities"]
    op_id = str(uuid.uuid4())
    payload = _sale(api, f, "3", job=_booking(api, 2, planned_end=(api.clock.now + timedelta(hours=10)).isoformat()))
    payload.pop("client_id")
    op = {"id": op_id, "op_type": "HOURS_PURCHASE", "created_at_device": api.clock.now.isoformat(), "payload": payload}
    first = _push(api, h, op)
    assert first["status"] == "ACKED", first
    job = first["result"]["entity"]["job"]
    assert job["id"] == str(uuid.uuid5(uuid.UUID(op_id), "job")) and job["status"] == "PENDING_APPROVAL"
    assert _push(api, h, op)["status"] == "DUPLICATE"
    counts = tenant_sql(
        f.tid,
        "SELECT (SELECT count(*) FROM hours_purchase), (SELECT count(*) FROM job WHERE hours_purchase_id IS NOT NULL)",
    )[0]
    assert tuple(counts) == (1, 1)

    # A booking the server cannot place is kept for review (the cash changed hands), never applied.
    other = f.owner.post(
        f"{T}/contracts",
        {"customer_id": f.customer_id, "contract_number": "CT-002", "starts_on": api.clock.now.isoformat()},
    )
    assert other.status_code == 201, other.text
    held = {**op, "id": str(uuid.uuid4())}
    res = _push(api, h, held)
    assert res["status"] == "CONFLICT" and res["error"]["code"] == "CONTRACT_CHOICE_REQUIRED", res
    assert tenant_sql(f.tid, "SELECT count(*) FROM hours_purchase")[0][0] == 1


def test_contract_resolution_given_single_walk_in_standard_and_required(api: Api) -> None:
    f = _setup(api)
    # Two active contracts: the sale must name one.
    second = _ok(
        f.owner.post(
            f"{T}/contracts",
            {"customer_id": f.customer_id, "contract_number": "CT-002", "starts_on": api.clock.now.isoformat()},
        )
    )
    r = f.supervisor.post(f"{T}/hours-purchases", _sale(api, f, "2", job=_booking(api)))
    assert r.status_code == 422 and _code(r) == "CONTRACT_CHOICE_REQUIRED"
    given = _ok(
        f.supervisor.post(f"{T}/hours-purchases", _sale(api, f, "2", job=_booking(api, contract_id=second["id"])))
    )
    assert given["job"]["contract_number"] == "CT-002"
    # The field list narrows to the customer's contracts.
    listed = _ok(f.supervisor.get(f"{T}/field/contracts", customer_id=f.customer_id), 200)
    assert {c["contract_number"] for c in listed} == {"CT-001", "CT-002"}

    # A contract of another customer is refused.
    other_customer = _ok(f.owner.post(f"{T}/customers", {"code": "C2", "name": "Bridge Works"}))["id"]
    theirs = _ok(
        f.owner.post(
            f"{T}/contracts",
            {"customer_id": other_customer, "contract_number": "CT-BW", "starts_on": api.clock.now.isoformat()},
        )
    )
    r = f.supervisor.post(f"{T}/hours-purchases", _sale(api, f, "2", job=_booking(api, contract_id=theirs["id"])))
    assert r.status_code == 422 and _code(r) == "CONTRACT_CUSTOMER_MISMATCH"
    # Exactly one active contract: used without naming it.
    single = _ok(
        f.supervisor.post(f"{T}/hours-purchases", _sale(api, f, "2", customer_id=other_customer, job=_booking(api)))
    )
    assert single["job"]["contract_number"] == "CT-BW"

    # A walk-in has no contract: refused by default, and nothing of the sale is kept.
    before = tenant_sql(f.tid, "SELECT count(*) FROM hours_purchase")[0][0]
    r = f.supervisor.post(f"{T}/hours-purchases", _sale(api, f, "2", walk_in={"name": "Roadside"}, job=_booking(api)))
    assert r.status_code == 422 and _code(r) == "CONTRACT_REQUIRED", r.text
    assert r.json()["error"]["message"] == "This customer has no contract yet; the office creates one"
    assert tenant_sql(f.tid, "SELECT count(*) FROM hours_purchase")[0][0] == before

    # The tenant lets a walk-in get a standard contract with the sale.
    _policy(f, walk_in_standard_contract=True)
    p = _ok(
        f.supervisor.post(f"{T}/hours-purchases", _sale(api, f, "2", walk_in={"name": "Roadside"}, job=_booking(api)))
    )
    assert p["job"]["contract_number"] == "CON-2026-00001"
    contract = _ok(f.owner.get(f"{T}/contracts/{p['job']['contract_id']}"), 200)
    assert (contract["customer_id"], contract["status"], contract["reference"]) == (
        p["customer_id"],
        "ACTIVE",
        p["purchase_number"],
    )
    created = [e for e in _audit(f, contract["id"]) if e["action"] == "jobs.contract.created"]
    assert created and p["purchase_number"] in (created[0]["reason"] or "")
    # The switch is for walk-ins: a registered customer without a contract is still refused.
    bare = _ok(f.owner.post(f"{T}/customers", {"code": "C3", "name": "No Contract Ltd"}))["id"]
    r = f.supervisor.post(f"{T}/hours-purchases", _sale(api, f, "2", customer_id=bare, job=_booking(api)))
    assert r.status_code == 422 and _code(r) == "CONTRACT_REQUIRED"


def test_booking_needs_the_job_request_permission_and_a_staff_record(api: Api) -> None:
    f = _setup(api)
    # The accountant may sell hours but not request jobs: refused, nothing recorded.
    r = f.accountant.post(f"{T}/hours-purchases", _sale(api, f, "2", payments=[], job=_booking(api)))
    assert r.status_code == 403 and _code(r) == "JOB_REQUEST_NOT_PERMITTED", r.text
    assert tenant_sql(f.tid, "SELECT count(*) FROM hours_purchase")[0][0] == 0
    # The owner holds both permissions but no staff record.
    r = f.owner.post(f"{T}/hours-purchases", _sale(api, f, "2", payments=[], job=_booking(api)))
    assert r.status_code == 422 and _code(r) == "NO_STAFF_RECORD"
    assert tenant_sql(f.tid, "SELECT count(*) FROM hours_purchase")[0][0] == 0


# --- approval follows the money ----------------------------------------------------------------------------------
def test_auto_approval_follows_fully_verified_money(api: Api) -> None:
    f = _setup(api)
    sup = member(api, f.tid, "supervisor", "sup-salebook")
    staff = _ok(
        f.owner.post(f"{T}/staff", {"full_name": "Neema Field", "kind": "SUPERVISOR", "keycloak_subject": sup.subject})
    )
    _policy(f, prepaid_job_auto_approval=True)

    # Partly paid and verified: partial activation, never approval.
    part = _ok(
        sup.post(f"{T}/hours-purchases", _sale(api, f, "4", payments=[_pay(api, 2 * RATE, "BANK")], job=_booking(api)))
    )
    verify(f.accountant2, part["payments"][0]["id"])
    assert get_purchase(f.owner, part["id"])["status"] == "PARTLY_ACTIVE"
    assert _job(f, part["job"]["id"])["status"] == "PENDING_APPROVAL"
    f.owner.post(f"{T}/jobs/{part['job']['id']}/transitions", {"action": "CANCEL", "reason": "Rebooked"})

    # Fully paid and verified: approved by the system, audited, the supervisor told.
    p = _ok(
        sup.post(f"{T}/hours-purchases", _sale(api, f, "4", payments=[_pay(api, 4 * RATE, "BANK")], job=_booking(api)))
    )
    assert p["job"]["status"] == "PENDING_APPROVAL"
    drain(api)
    verify(f.accountant2, p["payments"][0]["id"])
    job = _job(f, p["job"]["id"])
    assert job["status"] == "APPROVED" and job["approved_at"] is not None
    approved = [e for e in _audit(f, job["id"]) if e["action"] == "jobs.job.approve"]
    assert approved and approved[0]["actor_user_id"] is None
    assert approved[0]["reason"] == "Approved automatically: fully covered by verified prepaid hours (policy)"
    drain(api)
    num = job["job_number"]
    assert (
        "JOB_REQUEST_APPROVED",
        f"Job {num} approved",
        f"Your job request {num} was approved automatically: the customer's prepaid hours are paid and verified; "
        "you can start it.",
    ) in _inbox(sup)
    assert staff["id"] == job["requested_by_staff_id"]


def test_auto_approval_off_keeps_the_owner_approving(api: Api) -> None:
    f = _setup(api)
    p = _ok(
        f.supervisor.post(
            f"{T}/hours-purchases", _sale(api, f, "2", payments=[_pay(api, 2 * RATE, "BANK")], job=_booking(api))
        )
    )
    verify(f.accountant2, p["payments"][0]["id"])
    assert get_purchase(f.owner, p["id"])["status"] == "ACTIVE"
    assert _job(f, p["job"]["id"])["status"] == "PENDING_APPROVAL"
    assert _approve(f, p["job"]["id"]).status_code == 200


def test_auto_approval_on_credit_completing_the_sale(api: Api) -> None:
    f = _setup(api)
    _policy(f, prepaid_job_auto_approval=True)
    arr = f.manager.post(
        f"{T}/credit-arrangements",
        {
            "customer_id": f.customer_id,
            "limit_amount": str(10 * RATE),
            "effective_from": "2026-11-01",
            "reason": "Trusted",
        },
    )
    assert arr.status_code == 201, arr.text
    _ok(f.owner.post(f"{T}/credit-arrangements/{arr.json()['id']}/decision", {"approve": True}), 200)
    p = _ok(f.supervisor.post(f"{T}/hours-purchases", _sale(api, f, "3", payments=[], job=_booking(api))))
    r = f.accountant.post(f"{T}/hours-purchases/{p['id']}/credit-activations", {"hours": "3", "reason": "Pays Friday"})
    assert r.status_code == 200, r.text
    assert _job(f, p["job"]["id"])["status"] == "APPROVED"


def test_busy_machine_keeps_the_paid_job_pending_and_tells_the_approvers(api: Api) -> None:
    f = _setup(api)
    _policy(f, prepaid_job_auto_approval=True)
    prepaid_job(api, f, "P-OPEN")  # approved, open-ended from now: the machine is taken from now on
    drain(api)
    p = _ok(
        f.supervisor.post(
            f"{T}/hours-purchases", _sale(api, f, "2", payments=[_pay(api, 2 * RATE, "BANK")], job=_booking(api, 48))
        )
    )
    verify(f.accountant2, p["payments"][0]["id"])
    job = _job(f, p["job"]["id"])
    assert job["status"] == "PENDING_APPROVAL"
    held = [e for e in _audit(f, job["id"]) if e["action"] == "jobs.job.auto_approval_held"]
    assert held and held[0]["after"]["code"] == "MACHINE_BUSY"
    drain(api)
    notes = [n for n in _inbox(f.owner) if n[0] == "JOB_AUTO_APPROVAL_HELD"]
    assert notes and notes[0][1] == f"Job {job['job_number']} needs approval"
    assert "another approved or running job in that period" in notes[0][2]
    assert p["purchase_number"] in notes[0][2]


# --- future bookings on one machine ------------------------------------------------------------------------------
def test_approved_jobs_conflict_only_when_their_windows_overlap(api: Api) -> None:
    f = _setup(api)
    first = _office_job(api, f, "W-1", 0, 8)
    assert _approve(f, first).status_code == 200
    after = _office_job(api, f, "W-2", 8, 8)  # starts when the first ends
    assert _approve(f, after).status_code == 200
    overlap = _office_job(api, f, "W-3", 4, 2)
    r = _approve(f, overlap)
    assert r.status_code == 409 and _code(r) == "MACHINE_BUSY"
    assert r.json()["error"]["message"] == "The machine already has an approved or running job in this period"
    open_ended = _office_job(api, f, "W-4", 48, None)
    assert _approve(f, open_ended).status_code == 200
    later = _office_job(api, f, "W-5", 72, 4)  # inside the open-ended booking
    assert _approve(f, later).status_code == 409

    # The first job runs; the next booking cannot take readings (or start) until it is completed.
    t0 = api.clock.now
    assert f.owner.post(f"{T}/meter-captures", capture(first, "OPENING", "1000", t0, mode="MANUAL")).status_code == 201
    assert f.owner.post(f"{T}/jobs/{first}/transitions", {"action": "START"}).status_code == 200
    r = f.owner.post(f"{T}/meter-captures", capture(after, "OPENING", "1001", t0 + timedelta(hours=1), mode="MANUAL"))
    assert r.status_code == 422 and _code(r) == "MACHINE_BUSY", r.text
    # A cancelled booking frees its window.
    assert (
        f.owner.post(f"{T}/jobs/{open_ended}/transitions", {"action": "CANCEL", "reason": "Moved"}).status_code == 200
    )
    assert _approve(f, later).status_code == 200


def test_one_running_job_per_machine_is_enforced_by_the_database(api: Api) -> None:
    f = _setup(api)
    a = _office_job(api, f, "R-1", 0, 4)
    b = _office_job(api, f, "R-2", 10, 4)
    assert _approve(f, a).status_code == 200 and _approve(f, b).status_code == 200
    run = "UPDATE job SET status = 'IN_PROGRESS' WHERE id = :id RETURNING id"
    tenant_sql(f.tid, run, id=a)
    with pytest.raises(IntegrityError, match="uq_job_machine_running"):  # START of a second job is refused
        tenant_sql(f.tid, run, id=b)


# --- cash activation ---------------------------------------------------------------------------------------------
def test_cash_verify_mode_is_unchanged(api: Api) -> None:
    f = _setup(api)
    p = _ok(f.supervisor.post(f"{T}/hours-purchases", _sale(api, f, "2")))
    pay = _payment(f, p["payments"][0]["id"])
    assert pay["status"] == "CLAIMED" and pay["verifies_on_handover"] is False
    _handover(api, f, 2 * RATE)
    assert _payment(f, pay["id"])["status"] == "CLAIMED"  # a person still verifies it
    assert get_purchase(f.owner, p["id"])["status"] == "AWAITING_PAYMENT"


def test_cash_on_handover_verifies_oldest_first_up_to_the_amount_received(api: Api) -> None:
    f = _setup(api)
    _policy(f, cash_activation="ON_HANDOVER")
    # One sale of 4 h paid in two cash parts and a bank part on a later sale.
    first = _ok(
        f.supervisor.post(
            f"{T}/hours-purchases", _sale(api, f, "4", payments=[_pay(api, 2 * RATE), _pay(api, 2 * RATE)])
        )
    )
    api.clock.set_at(api.clock.now + timedelta(hours=1))
    second = _ok(
        f.supervisor.post(
            f"{T}/hours-purchases", _sale(api, f, "3", payments=[_pay(api, 2 * RATE), _pay(api, RATE, "MOBILE_MONEY")])
        )
    )
    cash1, cash2 = (x["id"] for x in first["payments"])
    cash3, mobile = (x["id"] for x in second["payments"])
    assert _payment(f, cash1)["verifies_on_handover"] is True
    assert _payment(f, mobile)["verifies_on_handover"] is False  # bank and mobile money: a person verifies
    held = _outstanding(f)
    assert held == 6 * RATE

    # A short handover (declared 3 h of cash, the office counts it) covers only the oldest part.
    api.clock.set_at(api.clock.now + timedelta(hours=1))
    h1 = _handover(api, f, 3 * RATE)
    one = _payment(f, cash1)
    assert one["status"] == "VERIFIED" and one["verified_by"] is None
    assert one["decision_note"] == f"Verified by the confirmed cash handover {h1['remittance_number']}"
    assert (one["verified_automatically"], one["verified_by_handover_id"], one["verified_by_remittance_number"]) == (
        "ON_HANDOVER",
        h1["id"],
        h1["remittance_number"],
    )
    assert _payment(f, cash2)["status"] == "CLAIMED"  # only partly covered so far
    got = get_purchase(f.owner, first["id"])
    assert got["status"] == "PARTLY_ACTIVE" and Decimal(got["totals"]["activated"]) == 2
    assert _outstanding(f) == held - 3 * RATE  # custody moves by the handover only

    # The next handover covers the rest of the cash; the mobile-money part still waits for a person.
    api.clock.set_at(api.clock.now + timedelta(hours=1))
    h2 = _handover(api, f, 3 * RATE)
    assert _payment(f, cash2)["verified_by_remittance_number"] == h2["remittance_number"]
    assert _payment(f, cash3)["status"] == "VERIFIED"
    assert get_purchase(f.owner, first["id"])["status"] == "ACTIVE"
    assert _payment(f, mobile)["status"] == "CLAIMED"
    assert get_purchase(f.owner, second["id"])["status"] == "PARTLY_ACTIVE"
    verify(f.accountant2, mobile)
    assert get_purchase(f.owner, second["id"])["status"] == "ACTIVE"
    assert _outstanding(f) == 0
    audit = [e for e in _audit(f, cash1) if e["action"] == "finance.payment.verified"]
    assert audit and audit[0]["actor_user_id"] is None and audit[0]["reason"] == one["decision_note"]


def test_cash_on_recording_activates_at_once_and_custody_stays_owed(api: Api) -> None:
    f = _setup(api)
    _policy(f, cash_activation="ON_RECORDING")
    p = _ok(
        f.supervisor.post(
            f"{T}/hours-purchases", _sale(api, f, "3", payments=[_pay(api, 2 * RATE), _pay(api, RATE, "BANK")])
        )
    )
    cash, bank = p["payments"]
    assert cash["status"] == "VERIFIED" and cash["verified_automatically"] == "ON_RECORDING"
    assert cash["decision_note"] == "Cash accepted on recording (policy); held by Cash Supervisor until handed over"
    assert bank["status"] == "CLAIMED"
    got = get_purchase(f.owner, p["id"])
    assert got["status"] == "PARTLY_ACTIVE" and Decimal(got["totals"]["activated"]) == 2
    assert _outstanding(f) == 2 * RATE  # the custodian still owes the cash
    # Nobody is asked to verify the cash part; the bank part is still verified by a person.
    drain(api)
    to_verify = [n[2] for n in _inbox(f.owner) if n[0] == "CUSTOMER_PAYMENT_TO_VERIFY"]
    assert any("(BANK)" in body for body in to_verify) and not any("(CASH)" in body for body in to_verify)
    verify(f.accountant2, bank["id"])
    assert get_purchase(f.owner, p["id"])["status"] == "ACTIVE"

    # Cash collected later against an hours purchase (the collection names it) is accepted the same way.
    later = _ok(f.supervisor.post(f"{T}/hours-purchases", _sale(api, f, "1", payments=[])))
    col = _ok(
        f.supervisor.post(
            f"{C}/collections",
            {
                "customer_id": f.customer_id,
                "amount": str(RATE),
                "received_at": api.clock.now.isoformat(),
                "purchase_id": later["id"],
            },
        )
    )
    assert col["status"] == "VERIFIED" and col["verified_automatically"] == "ON_RECORDING"
    assert get_purchase(f.owner, later["id"])["status"] == "ACTIVE"
    # Cash for an invoice keeps its manual verification.
    loose = _ok(
        f.supervisor.post(
            f"{C}/collections",
            {"customer_id": f.customer_id, "amount": "1000", "received_at": api.clock.now.isoformat()},
        )
    )
    assert loose["status"] == "CLAIMED"
    assert _outstanding(f) == 3 * RATE + 1000


def test_cash_on_recording_with_auto_approval_approves_the_booking_at_once(api: Api) -> None:
    f = _setup(api)
    _policy(f, cash_activation="ON_RECORDING", prepaid_job_auto_approval=True)
    p = _ok(f.supervisor.post(f"{T}/hours-purchases", _sale(api, f, "2", job=_booking(api))))
    assert p["status"] == "ACTIVE" and p["job"]["status"] == "APPROVED"
    # Offline the same: the acked sale carries the approved job.
    h = _device(api, f.supervisor)
    payload = _sale(api, f, "2", job=_booking(api, 30, planned_end=(api.clock.now + timedelta(hours=40)).isoformat()))
    payload.pop("client_id")
    op = {
        "id": str(uuid.uuid4()),
        "op_type": "HOURS_PURCHASE",
        "created_at_device": api.clock.now.isoformat(),
        "payload": payload,
    }
    res = _push(api, h, op)
    assert res["status"] == "ACKED" and res["result"]["entity"]["job"]["status"] == "PENDING_APPROVAL", res
    # The first booking is open-ended from now, so the second (later) one overlaps it and waits for the approvers.
    held = [e for e in _audit(f, res["result"]["entity"]["job"]["id"]) if e["action"] == "jobs.job.auto_approval_held"]
    assert held and held[0]["after"]["code"] == "MACHINE_BUSY"
