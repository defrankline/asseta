"""DEC-032 Phase 3 (independence and evidence, guideline 3.3, 4.4, 4.5, T5, T6, T8): segregation of duties on remittance
confirmation and credit activation, approved partial remittance, generated references, remittance evidence status,
collection links (online and at sync), per-type evidence policies, variance investigation and second-person closure,
customer-hour variances, the adjustment preview and the managed-service switch. Scenarios 8-10 of guideline section 9."""

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy.exc import DBAPIError

from asseta.core.db import get_sessionmaker
from asseta.modules.finance.custody_models import CashVariance
from asseta.modules.hours.variance_sweep import run_hour_variances
from tests.api.test_managed_service import assign, grant, refreshed, staff
from tests.support.api import PLATFORM_SUBJECT, Actor, Api
from tests.support.finance import allow_direct_void, cash_policy, setup_finance, tenant_sql
from tests.support.hours import RATE, get_purchase, hours_policy, purchase, verify
from tests.support.jobs import unique_jpeg
from tests.support.notify import member

T = "/api/v1/tenant"
C = f"{T}/cash"
T0 = "2026-11-01T06:00:00+00:00"
T1 = "2026-11-01T07:00:00+00:00"
DEVICE = "android-p3-0001"


def _ok(r: Any, status: int = 201) -> Any:
    assert r.status_code == status, r.text
    return r.json()


def _err(r: Any, status: int, code: str) -> None:
    assert r.status_code == status, r.text
    assert r.json()["error"]["code"] == code, r.text


def _setup(api: Api) -> Any:
    f = setup_finance(api, "Independence", "IND-1")
    return f


def _staff(f: Any, name: str, login: Actor | None = None) -> str:
    body: dict[str, Any] = {"full_name": name, "kind": "OPERATOR"}
    if login is not None:
        body["keycloak_subject"] = login.subject
    return str(_ok(f.owner.post(f"{T}/staff", body))["id"])


def _collect(actor: Actor, f: Any, staff_id: str, amount: str, **extra: Any) -> Any:
    body = {"customer_id": f.customer_id, "amount": amount, "received_at": T0, "staff_member_id": staff_id, **extra}
    return _ok(actor.post(f"{C}/collections", body))


def _attach(api: Api, actor: Actor) -> str:
    r = api.client.post(
        f"{T}/attachments",
        headers=actor.headers(True, None),
        files={"file": ("e.jpg", unique_jpeg(), "image/jpeg")},
        data={"purpose": "ADJUSTMENT_EVIDENCE"},
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


def _device(api: Api, actor: Actor) -> dict[str, str]:
    h = {**actor.headers(True, None), "X-Device-Id": DEVICE}
    reg = api.client.post(
        "/api/v1/sync/devices", headers=h, json={"device_id": DEVICE, "platform": "ANDROID", "app_version": "2.0.0"}
    )
    assert reg.status_code == 201, reg.text
    return h


def _push(api: Api, headers: dict[str, str], op_type: str, payload: dict[str, Any]) -> Any:
    op = {"id": str(uuid.uuid4()), "op_type": op_type, "created_at_device": T0, "payload": payload}
    r = api.client.post("/api/v1/sync/push", headers=headers, json={"device_now": T1, "operations": [op]})
    assert r.status_code == 200, r.text
    return r.json()["results"][0]


# --- 1. custodian independence ----------------------------------------------------------------------------------
def test_custodian_cannot_confirm_own_remittance_even_recorded_by_someone_else(api: Api) -> None:
    f = _setup(api)
    custodian = _staff(f, "Cashier Custodian", login=f.accountant)
    _collect(f.manager, f, custodian, "1000")
    h = _ok(f.manager.post(f"{C}/handovers", {"staff_member_id": custodian, "amount": "1000", "handed_at": T1}))
    _err(f.accountant.post(f"{C}/handovers/{h['id']}/decision", {"verified": True}), 422, "SEGREGATION_OF_DUTIES")
    _ok(f.accountant2.post(f"{C}/handovers/{h['id']}/decision", {"verified": True}), 200)


# --- 2. credit activation and zero-amount purchases --------------------------------------------------------------
def test_credit_activation_approver_differs_from_recorder(api: Api) -> None:
    f = _setup(api)
    p = purchase(api, f.manager, f, "2")
    arrangement = _ok(
        f.manager.post(
            f"{T}/credit-arrangements",
            {
                "customer_id": f.customer_id,
                "limit_amount": str(100 * RATE),
                "effective_from": "2026-01-01",
                "reason": "Trusted account",
            },
        )
    )
    _ok(f.owner.post(f"{T}/credit-arrangements/{arrangement['id']}/decision", {"approve": True}), 200)
    url = f"{T}/hours-purchases/{p['id']}/credit-activations"
    _err(f.manager.post(url, {"hours": "1", "reason": "Urgent"}), 422, "SEGREGATION_OF_DUTIES")
    _ok(f.accountant.post(url, {"hours": "1", "reason": "Urgent"}), 200)


def _full_discount(f: Any) -> None:
    body = {"customer_id": f.customer_id, "percent": "100", "effective_from": "2026-01-01", "reason": "Goodwill"}
    d = _ok(f.manager.post(f"{T}/customer-discounts", body))
    _ok(f.owner.post(f"{T}/customer-discounts/{d['id']}/decision", {"approve": True}), 200)


def test_zero_amount_purchase_needs_approval_before_activating(api: Api) -> None:
    f = _setup(api)
    _full_discount(f)
    p = purchase(api, f.manager, f, "4")
    assert Decimal(p["amount"]) == 0
    assert p["status"] != "ACTIVE" and Decimal(p["totals"]["activated"]) == 0
    assert p["pending_zero_amount_request_id"]
    req_url = f"{T}/adjustment-requests/{p['pending_zero_amount_request_id']}"
    req = _ok(f.owner.get(req_url), 200)
    assert (req["request_type"], req["effects"]["hours_to_activate"]) == ("ZERO_AMOUNT_ACTIVATION", "4.00")
    assert req["request_number"].startswith("ARQ-")
    _err(f.manager.post(f"{req_url}/decision", {"decision": "APPROVE"}), 403, "PERMISSION_DENIED")
    # proposer != approver holds even with the permission
    own = f.accountant.post(
        f"{T}/hours-purchases", {"customer_id": f.customer_id, "machine_id": f.c.t.machine_id, "hours": "1"}
    )
    other = _ok(own)
    _err(
        f.accountant.post(
            f"{T}/adjustment-requests/{other['pending_zero_amount_request_id']}/decision", {"decision": "APPROVE"}
        ),
        422,
        "SEGREGATION_OF_DUTIES",
    )
    decided = _ok(f.owner.post(f"{req_url}/decision", {"decision": "APPROVE"}), 200)
    assert decided["status"] == "APPROVED"
    got = get_purchase(f.owner, p["id"])
    assert got["status"] == "ACTIVE" and Decimal(got["totals"]["activated"]) == 4
    assert got["pending_zero_amount_request_id"] is None
    entry = _ok(f.owner.get(f"{T}/adjustments", type="ZERO_AMOUNT_ACTIVATION"), 200)["items"][0]
    assert entry["entry_number"].startswith("ADJ-")

    # The tenant can waive it: it then activates on recording (the earlier behaviour).
    hours_policy(f, zero_amount_requires_approval=False)
    waived = purchase(api, f.manager, f, "1")
    assert waived["status"] == "ACTIVE" and waived["pending_zero_amount_request_id"] is None


# --- 3. per-type evidence policies -------------------------------------------------------------------------------
def test_evidence_policies_transfer_credit_custody_adjustment_void(api: Api) -> None:
    f = _setup(api)
    evidence = _attach(api, f.owner)
    p = purchase(api, f.accountant, f, "10", pay=str(10 * RATE))
    verify(f.accountant2, p["payment"]["id"])
    other = _ok(f.owner.post(f"{T}/machines", {"asset_code": "EX-99", "name": "Second excavator"}))["id"]
    hours_policy(f, transfer_evidence_required=True, credit_evidence_required=True)
    body = {"purchase_id": p["id"], "to_machine_id": other, "hours": "2", "reason": "Moved to second site"}
    _err(f.manager.post(f"{T}/hours-transfers", body), 422, "EVIDENCE_REQUIRED")
    done = _ok(f.manager.post(f"{T}/hours-transfers", {**body, "evidence_attachment_ids": [evidence]}))
    assert done["evidence_attachment_ids"] == [evidence] and done["transfer_number"].startswith("HTR-")

    cred = {"customer_id": f.customer_id, "limit_amount": "1000", "effective_from": "2026-01-01", "reason": "Regular"}
    _err(f.manager.post(f"{T}/credit-arrangements", cred), 422, "EVIDENCE_REQUIRED")
    arrangement = _ok(f.manager.post(f"{T}/credit-arrangements", {**cred, "evidence_attachment_ids": [evidence]}))
    assert arrangement["evidence_attachment_ids"] == [evidence]

    cash_policy(f, custody_adjustment_evidence_required=True)
    staff_id = _staff(f, "Field Staff")
    adj = {"staff_member_id": staff_id, "kind": "ADJUSTMENT", "amount": "5", "reason": "Recount"}
    _err(f.accountant.post(f"{C}/adjustments", adj), 422, "EVIDENCE_REQUIRED")
    made = _ok(f.accountant.post(f"{C}/adjustments", {**adj, "evidence_attachment_ids": [evidence]}))
    assert made["adjustment_number"].startswith("CADJ-") and made["evidence_attachment_ids"] == [evidence]


def test_void_of_an_issued_invoice_enforces_adjustment_evidence(api: Api) -> None:
    from tests.support.finance import complete_job, issue_invoice

    f = _setup(api)
    complete_job(api, f, f.c.job_id, "1000", "1008", 8)
    invoice = issue_invoice(f, [f.c.job_id])
    url = f"{T}/hire-invoices/{invoice['id']}/void"
    _err(f.accountant.post(url, {"reason": "Wrong customer"}), 422, "EVIDENCE_REQUIRED")
    evidence = _attach(api, f.owner)
    pending = _ok(f.accountant.post(url, {"reason": "Wrong customer", "evidence_attachment_ids": [evidence]}), 200)
    assert pending["status"] == "ISSUED" and pending["pending_void_request_id"]


def test_direct_void_also_enforces_evidence_unless_relaxed(api: Api) -> None:
    from tests.support.finance import complete_job, issue_invoice

    f = _setup(api)
    complete_job(api, f, f.c.job_id, "1000", "1008", 8)
    invoice = issue_invoice(f, [f.c.job_id])
    r = f.owner.post(
        f"{T}/policies/HIRE_BILLING/versions",
        {"scope": "TENANT", "values": {"invoice_void_requires_approval": False}, "reason": "Direct voids"},
    )
    assert r.status_code == 201, r.text
    _err(
        f.accountant.post(f"{T}/hire-invoices/{invoice['id']}/void", {"reason": "Wrong customer"}),
        422,
        "EVIDENCE_REQUIRED",
    )
    allow_direct_void(f)  # also relaxes the evidence requirement for the plain void path
    assert (
        _ok(f.accountant.post(f"{T}/hire-invoices/{invoice['id']}/void", {"reason": "Wrong customer"}), 200)["status"]
        == "VOIDED"
    )


# --- 4/6/10. partial remittance, evidence status, partial confirmation --------------------------------------------
def test_partial_remittance_reason_approval_and_evidence_status_scenarios_9_and_10(api: Api) -> None:
    f = _setup(api)
    mgr, acct = f.manager, f.accountant
    operator = _staff(f, "Operator Partial")
    _collect(mgr, f, operator, "100000")
    cash_policy(f, remit_full_balance=True)
    short = {
        "staff_member_id": operator,
        "amount": "60000",
        "handed_at": T1,
        "reference": "BANK-77",
        "method": "BANK_DEPOSIT",
    }
    _err(mgr.post(f"{C}/handovers", short), 422, "PARTIAL_REMITTANCE_REASON_REQUIRED")
    reason = _ok(acct.post(f"{C}/reasons", {"kind": "PARTIAL_REMITTANCE", "label": "Bank closed early"}))
    _err(mgr.post(f"{C}/handovers", {**short, "partial_reason": "Bank closed"}), 422, "REASON_REQUIRED")
    h = _ok(
        mgr.post(f"{C}/handovers", {**short, "partial_reason": "Bank closed early", "partial_reason_id": reason["id"]})
    )
    # The bank's reference and the generated reference are separate things.
    assert h["reference"] == "BANK-77" and h["remittance_number"].startswith("RMT-")
    assert h["partial_shortfall"] == "40000.0000" and h["partial_approval"]["status"] == "PENDING"
    # Scenario 9: declared, not cleared until the company confirms.
    assert h["status"] == "CLAIMED" and h["evidence_status"] == "DECLARED"

    url = f"{C}/handovers/{h['id']}/partial-reason-decision"
    _err(mgr.post(url, {"approve": True}), 403, "PERMISSION_DENIED")
    decided = _ok(f.owner.post(url, {"approve": True, "note": "Accepted"}), 200)
    assert decided["partial_approval"]["status"] == "APPROVED"
    assert decided["partial_approval"]["decided_by_name"]

    attachment = _attach(api, f.owner)
    ev = _ok(mgr.post(f"{C}/handovers/{h['id']}/evidence", {"attachment_ids": [attachment]}))
    assert len(ev) == 1
    assert _ok(acct.get(f"{C}/handovers/{h['id']}"), 200)["evidence_status"] == "SUPPORTED"

    # Scenario 10: partially confirmed; only the confirmed amount reduces the balance, the rest stays visible.
    done = _ok(acct.post(f"{C}/handovers/{h['id']}/decision", {"verified": True, "amount_received": "50000"}), 200)
    assert done["evidence_status"] == "CONFIRMED" and done["outstanding_difference"] == "10000.0000"
    balance = _ok(acct.get(f"{C}/custody", staff_member_id=operator), 200)[0]
    assert Decimal(balance["outstanding"]) == 50000

    # Offline: the reason requirement is a conflict kept for review, never applied.
    full = {"staff_member_id": operator, "amount": "1", "handed_at": T1, "client_id": str(uuid.uuid4())}
    h2 = _device(api, f.supervisor)
    res = _push(api, h2, "CASH_HANDOVER", full)
    assert (res["status"], res["error"]["code"]) == ("CONFLICT", "PARTIAL_REMITTANCE_REASON_REQUIRED")


def test_transfer_is_never_a_remittance_scenario_8(api: Api) -> None:
    f = _setup(api)
    operator = _staff(f, "Operator Eight")
    mgr_staff = _staff(f, "Field Manager Eight", login=f.manager)
    _collect(f.manager, f, operator, "30000")
    t = _ok(
        f.manager.post(
            f"{C}/transfers",
            {"from_staff_id": operator, "to_staff_id": mgr_staff, "amount": "30000", "transferred_at": T1},
        )
    )
    assert t["transfer_number"].startswith("CTR-") and t["status"] == "ACKNOWLEDGED"
    assert Decimal(_ok(f.accountant.get(f"{C}/custody", staff_member_id=mgr_staff), 200)[0]["outstanding"]) == 30000
    assert Decimal(_ok(f.accountant.get(f"{C}/custody", staff_member_id=operator), 200)[0]["outstanding"]) == 0
    assert (
        _ok(
            f.accountant.get(
                f"{C}/reconciliation/transactions",
                staff_member_id=operator,
                **{"from": "2026-11-01", "to": "2026-11-01"},
            ),
            200,
        )["total"]
        >= 1
    )


# --- 5. references and backfill-shaped uniqueness ------------------------------------------------------------------
def test_generated_references_are_unique_and_year_scoped(api: Api) -> None:
    f = _setup(api)
    operator = _staff(f, "Operator Refs")
    first = _collect(f.manager, f, operator, "100")
    second = _collect(f.manager, f, operator, "100")
    year = api.clock.now.year
    assert first["collection_number"] == f"COL-{year}-00001"
    assert second["collection_number"] == f"COL-{year}-00002"
    bank = _ok(
        f.accountant.post(
            f"{T}/customer-payments",
            {
                "customer_id": f.customer_id,
                "amount": "100",
                "method": "BANK",
                "reference": "BANK-1",
                "received_at": T0,
            },
        )
    )
    assert bank["collection_number"] == f"PAY-{year}-00001" and bank["reference"] == "BANK-1"
    retention = _ok(f.manager.post(f"{C}/retentions", {"staff_member_id": operator, "amount": "10", "reason": "Float"}))
    assert retention["retention_number"].startswith("RET-") and retention["client_created_at"] is None


def test_references_cannot_be_rewritten(api: Api) -> None:
    f = _setup(api)
    operator = _staff(f, "Operator Guard")
    _collect(f.manager, f, operator, "100")
    try:
        tenant_sql(f.tid, "UPDATE customer_payment SET collection_number = 'COL-X'")
    except DBAPIError as exc:
        assert "permission denied" in str(exc) or "immutable" in str(exc) or "not permitted" in str(exc)
    else:
        raise AssertionError("expected refusal")


# --- 7. collection link -------------------------------------------------------------------------------------------
def test_collection_link_required_online_and_offline(api: Api) -> None:
    f = _setup(api)
    cash_policy(f, collection_link_required=True)
    operator = _staff(f, "Operator Link")
    body = {"customer_id": f.customer_id, "amount": "100", "received_at": T0, "staff_member_id": operator}
    _err(f.manager.post(f"{C}/collections", body), 422, "COLLECTION_LINK_REQUIRED")
    p = purchase(api, f.manager, f, "3")
    linked = _ok(f.manager.post(f"{C}/collections", {**body, "purchase_id": p["id"], "amount": str(RATE)}))
    assert linked["purchase_links"][0]["purchase_id"] == p["id"]
    assert linked["purchase_links"][0]["purchase_number"] == p["purchase_number"]
    assert Decimal(get_purchase(f.owner, p["id"])["totals"]["amount_claimed_unverified"]) == RATE

    h = _device(api, f.supervisor)
    payload = {"customer_id": f.customer_id, "amount": "100", "received_at": T0, "staff_member_id": f.sup_staff_id}
    res = _push(api, h, "CASH_COLLECTION", {**payload, "client_id": str(uuid.uuid4())})
    assert (res["status"], res["error"]["code"]) == ("CONFLICT", "COLLECTION_LINK_REQUIRED")
    res = _push(api, h, "CASH_COLLECTION", {**payload, "client_id": str(uuid.uuid4()), "purchase_id": p["id"]})
    assert res["status"] == "ACKED", res


def test_collection_links_an_offline_purchase_by_its_client_id(api: Api) -> None:
    f = _setup(api)
    h = _device(api, f.supervisor)
    purchase_op = str(uuid.uuid4())
    op = {
        "id": purchase_op,
        "op_type": "HOURS_PURCHASE",
        "created_at_device": T0,
        "payload": {"walk_in": {"name": "Roadside"}, "machine_id": f.c.t.machine_id, "hours": "2"},
    }
    r = api.client.post("/api/v1/sync/push", headers=h, json={"device_now": T1, "operations": [op]})
    assert r.json()["results"][0]["status"] == "ACKED", r.text
    pid = r.json()["results"][0]["result"]["entity"]["id"]
    got = get_purchase(f.owner, pid)
    assert got["client_created_at"] is not None and got["client_created_at"].startswith("2026-11-01T06:00")
    customer = got["customer_id"]
    res = _push(
        api,
        h,
        "CASH_COLLECTION",
        {
            "client_id": str(uuid.uuid4()),
            "customer_id": customer,
            "amount": str(RATE),
            "received_at": T0,
            "staff_member_id": f.sup_staff_id,
            "purchase_id": purchase_op,
        },
    )
    assert res["status"] == "ACKED", res
    assert res["result"]["entity"]["purchase_links"][0]["purchase_id"] == pid


def test_offline_hours_transfer_carries_evidence_and_conflicts_when_required(api: Api) -> None:
    f = _setup(api)
    p = purchase(api, f.accountant, f, "5", pay=str(5 * RATE))
    verify(f.accountant2, p["payment"]["id"])
    other = _ok(f.owner.post(f"{T}/machines", {"asset_code": "EX-77", "name": "Other excavator"}))["id"]
    hours_policy(f, transfer_evidence_required=True)
    h = _device(api, f.supervisor)
    body = {"purchase_id": p["id"], "to_machine_id": other, "hours": "1", "reason": "Moved to the other site"}
    res = _push(api, h, "HOURS_TRANSFER_REQUEST", body)
    assert (res["status"], res["error"]["code"]) == ("CONFLICT", "EVIDENCE_REQUIRED")
    res = _push(api, h, "HOURS_TRANSFER_REQUEST", {**body, "evidence_attachment_ids": [_attach(api, f.supervisor)]})
    assert res["status"] == "ACKED", res


# --- 9. client-created time from sync -------------------------------------------------------------------------------
def test_retention_carries_client_created_time_from_sync(api: Api) -> None:
    f = _setup(api)
    h = _device(api, f.supervisor)
    res = _push(
        api,
        h,
        "CASH_RETENTION_REQUEST",
        {"client_id": str(uuid.uuid4()), "amount": "10", "reason": "Keep float"},
    )
    assert res["status"] == "ACKED", res
    entity = res["result"]["entity"]
    assert entity["client_created_at"].startswith("2026-11-01T06:00")


# --- 8. variance investigation -------------------------------------------------------------------------------------
def _variance(f: Any, api: Api, amount_received: str = "9000") -> tuple[Any, str]:
    operator = _staff(f, "Operator Variance")
    _collect(f.manager, f, operator, "10000")
    h = _ok(f.manager.post(f"{C}/handovers", {"staff_member_id": operator, "amount": "10000", "handed_at": T1}))
    _ok(
        f.accountant.post(f"{C}/handovers/{h['id']}/decision", {"verified": True, "amount_received": amount_received}),
        200,
    )
    v = _ok(f.accountant2.get(f"{C}/variances"), 200)["items"][0]
    return v, operator


def test_variance_assignment_explanation_second_person_and_history(api: Api) -> None:
    f = _setup(api)
    v, _ = _variance(f, api)
    url = f"{C}/variances/{v['id']}"
    investigator = member(api, f.tid, "accountant", "acct-investigator")
    from tests.support.notify import user_id

    assignees = _ok(f.owner.get(f"{C}/variances/assignees"), 200)
    assert any(a["user_id"] == str(user_id(investigator.subject)) for a in assignees)
    _err(f.owner.post(f"{url}/assignment", {"assignee_user_id": str(uuid.uuid4())}), 422, "ASSIGNEE_NOT_ELIGIBLE")
    assigned = _ok(f.owner.post(f"{url}/assignment", {"assignee_user_id": str(user_id(investigator.subject))}), 200)
    assert assigned["assignee_user_id"] == str(user_id(investigator.subject)) and assigned["assignee_user_name"]
    assert assigned["assigned_by_name"]
    listed = _ok(f.owner.get(f"{C}/variances", assignee_user_id=str(user_id(investigator.subject))), 200)
    assert listed["total"] == 1

    evidence = _attach(api, f.owner)
    note = "Recount at the office found a 1,000 note under the tray"
    explained = _ok(
        investigator.post(f"{url}/explanation", {"explanation": note, "evidence_attachment_ids": [evidence]}), 200
    )
    assert explained["explanation"] == note and explained["evidence_attachment_ids"] == [evidence]
    assert explained["status"] == "OPEN"

    # Evidence required by policy: met by the explanation already on the record.
    cash_policy(f, variance_evidence_required=True)
    proposed = _ok(investigator.post(f"{url}/resolution", {"outcome": "RECOVERED", "note": "Found in the tray"}), 200)
    assert (proposed["status"], proposed["proposed_outcome"]) == ("CLOSURE_PROPOSED", "RECOVERED")
    assert proposed["outcome"] is None

    # Whoever proposed, opened or is a party cannot close it; the rest can with the permission.
    _err(investigator.post(f"{url}/closure-decision", {"approve": True}), 422, "SEGREGATION_OF_DUTIES")
    _err(f.accountant.post(f"{url}/closure-decision", {"approve": True}), 422, "SEGREGATION_OF_DUTIES")
    _err(f.manager.post(f"{url}/closure-decision", {"approve": True}), 403, "PERMISSION_DENIED")
    rejected = _ok(f.accountant2.post(f"{url}/closure-decision", {"approve": False, "note": "Show the recount"}), 200)
    assert rejected["status"] == "OPEN" and rejected["proposed_by"] is None

    _ok(investigator.post(f"{url}/resolution", {"outcome": "RECOVERED", "note": "Recount sheet attached"}), 200)
    closed = _ok(f.accountant2.post(f"{url}/closure-decision", {"approve": True, "note": "Agreed"}), 200)
    assert (closed["status"], closed["outcome"], closed["resolved_by_name"] is not None) == (
        "RESOLVED",
        "RECOVERED",
        True,
    )
    entry = _ok(f.accountant2.get(f"{T}/adjustments", type="CASH_VARIANCE_RESOLUTION"), 200)["items"][0]
    assert entry["evidence_attachment_ids"] == [evidence]

    actions = [e["action"] for e in _ok(f.accountant2.get(f"{url}/history"), 200)]
    assert actions == [
        "OPENED",
        "ASSIGNED",
        "EXPLAINED",
        "CLOSURE_PROPOSED",
        "CLOSURE_REJECTED",
        "CLOSURE_PROPOSED",
        "CLOSURE_APPROVED",
        "RESOLVED",
    ]


def test_direct_closure_when_policy_relaxed_and_counterparty_refused(api: Api) -> None:
    f = _setup(api)
    cash_policy(f, variance_closure_requires_second_person=False, writeoff_requires_approval=False)
    v, _ = _variance(f, api)
    url = f"{C}/variances/{v['id']}"
    # The opener never closes it.
    _err(
        f.accountant.post(f"{url}/resolution", {"outcome": "RECOVERED", "note": "Found it"}),
        422,
        "SEGREGATION_OF_DUTIES",
    )
    closed = _ok(f.accountant2.post(f"{url}/resolution", {"outcome": "RECOVERED", "note": "Found it"}), 200)
    assert closed["status"] == "RESOLVED"

    # Counterparty of a transfer cannot decide its closure.
    operator = _staff(f, "Operator Sender")
    counter = member(api, f.tid, "accountant", "acct-counter")
    receiver = _staff(f, "Receiver Staff", login=counter)
    _collect(f.manager, f, operator, "500")
    t = _ok(
        f.manager.post(
            f"{C}/transfers",
            {"from_staff_id": operator, "to_staff_id": receiver, "amount": "500", "transferred_at": T1},
        )
    )
    _ok(counter.post(f"{C}/transfers/{t['id']}/acknowledgement", {"acknowledged": True, "amount_received": "400"}), 200)
    variance = next(x for x in _ok(f.owner.get(f"{C}/variances"), 200)["items"] if x["source_type"] == "TRANSFER")
    url2 = f"{C}/variances/{variance['id']}"
    _err(counter.post(f"{url2}/resolution", {"outcome": "RECOVERED", "note": "ok then"}), 422, "SEGREGATION_OF_DUTIES")


def test_customer_hour_variance_swept_assigned_and_closed(api: Api) -> None:
    f = _setup(api)
    p = purchase(api, f.accountant, f, "5", pay=str(5 * RATE))
    verify(f.accountant2, p["payment"]["id"])
    assert run_hour_variances(get_sessionmaker(), api.clock.now) == 0  # consistent records: nothing to report

    # A purchase activating more hours than were bought (the records must be wrong somewhere).
    tenant_sql(
        f.tid,
        "INSERT INTO hours_ledger_entry (id, tenant_id, purchase_id, customer_id, machine_id, entry_type, hours,"
        " occurred_at, reason, activation_source, policy_version, created_at) VALUES (gen_random_uuid(), :t, :p, :c, :m,"
        " 'ACTIVATED', 2, now(), 'Injected for the test', 'PAYMENT', 'x', now()) RETURNING id",
        t=f.tid,
        p=p["id"],
        c=f.customer_id,
        m=f.c.t.machine_id,
    )
    assert run_hour_variances(get_sessionmaker(), api.clock.now) == 1
    assert run_hour_variances(get_sessionmaker(), api.clock.now) == 0  # idempotent
    items = _ok(f.owner.get(f"{C}/variances", source_type="CUSTOMER_HOUR"), 200)["items"]
    [v] = items
    assert (v["unit"], v["check_code"], v["purchase_id"]) == ("HOURS", "PURCHASE_OVER_ACTIVATED", p["id"])
    assert (Decimal(v["declared_amount"]), Decimal(v["received_amount"])) == (Decimal(5), Decimal(7))
    url = f"{C}/variances/{v['id']}"
    _err(
        f.accountant.post(f"{url}/resolution", {"outcome": "WRITTEN_OFF", "note": "Lost hours"}),
        422,
        "VARIANCE_OUTCOME_NOT_ALLOWED",
    )
    proposed = _ok(
        f.accountant.post(f"{url}/resolution", {"outcome": "EXPLAINED", "note": "Ledger entry reversed"}), 200
    )
    assert proposed["status"] == "CLOSURE_PROPOSED"
    closed = _ok(f.accountant2.post(f"{url}/closure-decision", {"approve": True}), 200)
    assert closed["outcome"] == "EXPLAINED"
    entry = _ok(f.owner.get(f"{T}/adjustments", type="HOURS_VARIANCE_RESOLUTION"), 200)["items"][0]
    assert entry["unit"] == "HOURS" and entry["currency"] is None

    # Written-off is not an outcome for hours; a resolved variance with the same figures does not reopen.
    assert run_hour_variances(get_sessionmaker(), api.clock.now) == 0

    # Off: the sweep stops (the capability check) and CUSTOMER_HOUR listing follows the hours capability.
    hours_policy(f, variance_sweep_enabled=False)
    assert run_hour_variances(get_sessionmaker(), api.clock.now) == 0


def test_variance_tables_are_append_only(api: Api) -> None:
    f = _setup(api)
    v, _ = _variance(f, api)
    with_row = tenant_sql(f.tid, "SELECT count(*) FROM cash_variance_event WHERE variance_id = :v", v=v["id"])
    assert with_row[0][0] == 1
    try:
        tenant_sql(f.tid, "UPDATE cash_variance_event SET note = 'x'")
    except DBAPIError as exc:
        assert "permission denied" in str(exc) or "not permitted" in str(exc)
    else:
        raise AssertionError("expected refusal")
    # The variance row's evidence (declared/received) stays frozen.
    with get_sessionmaker().begin() as s:
        from asseta.core.db import DbScope, apply_scope

        apply_scope(s, DbScope.TENANT, uuid.UUID(f.tid), None)
        row = s.get(CashVariance, uuid.UUID(v["id"]))
        assert row is not None
        s.expunge(row)
    try:
        tenant_sql(f.tid, "UPDATE cash_variance SET declared_amount = 1 WHERE id = :v", v=v["id"])
    except DBAPIError as exc:
        assert "immutable" in str(exc)
    else:
        raise AssertionError("expected refusal")


# --- 10. preview ----------------------------------------------------------------------------------------------------
def test_adjustment_preview_returns_effects_without_saving(api: Api) -> None:
    f = _setup(api)
    p = purchase(api, f.accountant, f, "10", pay=str(10 * RATE))
    verify(f.accountant2, p["payment"]["id"])
    body = {"request_type": "HOURS_CORRECTION", "purchase_id": p["id"], "hours": "-2"}
    before = tenant_sql(f.tid, "SELECT count(*) FROM adjustment_request")[0][0]
    preview = _ok(f.manager.post(f"{T}/adjustment-requests/preview", body), 200)
    assert preview["effects"] == {"lot_hours_before": "10.00", "lot_hours_after": "8.00"}
    assert preview["original_reference"] == p["purchase_number"]
    assert tenant_sql(f.tid, "SELECT count(*) FROM adjustment_request")[0][0] == before
    assert tenant_sql(f.tid, "SELECT count(*) FROM hours_sequence WHERE series = 'ARQ'")[0][0] == 0
    # Same field checks as proposing it; `refused` when the checks at the end would fail it.
    _err(
        f.manager.post(f"{T}/adjustment-requests/preview", {"request_type": "HOURS_CORRECTION", "hours": "1"}),
        422,
        "ADJUSTMENT_FIELDS_MISSING",
    )


# --- case closure second person -------------------------------------------------------------------------------------
def test_case_resolution_second_person_when_policy_on(api: Api) -> None:
    from tests.support.finance import category, expense_policy
    from tests.support.intelligence import cases, expense, feed_events, receipt

    f = setup_finance(api, "Case Co", "CASE-1")
    submitter = f.supervisor
    cat = category(f, "SPARES", "Spares")
    expense_policy(f, receipt_required_above="0", gps_required=False, auto_approve_limit="0")
    image = unique_jpeg()
    for _ in range(2):
        expense(api, submitter, cat, "45000", receipt_attachment_ids=[receipt(api, submitter, image)])
    feed_events(api, f.tid)
    [case] = cases(f.owner)
    r = f.owner.post(
        f"{T}/policies/OVERSIGHT/versions",
        {"scope": "TENANT", "values": {"case_closure_requires_second_person": True}, "reason": "Two people on cases"},
    )
    assert r.status_code == 201, r.text
    reviewer = member(api, f.tid, "owner", "case-reviewer", sync=False)
    reviewer2 = member(api, f.tid, "owner", "case-reviewer2")
    url = f"{T}/cases/{case['id']}"
    body = {
        "outcome": "UNCONFIRMED",
        "explanation": "Duplicate photo was a scanning mistake",
        "version": case["version"],
    }
    proposed = _ok(reviewer.post(f"{url}/resolve", body), 200)
    assert proposed["case"]["status"] == "IN_REVIEW" and proposed["case"]["closure_outcome"] == "UNCONFIRMED"
    version = proposed["case"]["version"]
    _err(
        reviewer.post(f"{url}/resolution-decision", {"approve": True, "version": version}), 422, "SEGREGATION_OF_DUTIES"
    )
    _err(reviewer2.post(f"{url}/resolve", {**body, "version": version}), 409, "CASE_CLOSURE_PENDING")
    decided = _ok(reviewer2.post(f"{url}/resolution-decision", {"approve": True, "version": version}), 200)
    assert decided["case"]["status"] == "RESOLVED" and decided["case"]["closure_proposed_by"] is None


# --- 11. managed service safety -------------------------------------------------------------------------------------
def _switch(actor: Actor, enabled: bool) -> Any:
    return actor.post(
        f"{T}/policies/OVERSIGHT/versions",
        {"scope": "TENANT", "values": {"managed_service_enabled": enabled}, "reason": "Managed service switch"},
    )


def test_managed_service_switch_cannot_hide_an_active_mandate(api: Api) -> None:
    staff(api, PLATFORM_SUBJECT, "platform@asseta.local")
    tenant = api.onboard("Earthworks Ltd", price="1")
    tid, owner = tenant["tenant"]["id"], tenant["owner"]
    m = grant(api, tid)
    _err(_switch(owner, False), 422, "MANAGED_SERVICE_MANDATE_ACTIVE")
    revoked = owner.post(
        f"{T}/managed-service/{m['id']}/revoke", {"version": 1, "reason": "We hired our own dispatcher"}
    )
    assert revoked.status_code == 200, revoked.text
    assert _switch(owner, False).status_code == 201


def test_mandate_staff_cannot_change_the_switch_at_all(api: Api) -> None:
    staff(api, PLATFORM_SUBJECT, "platform@asseta.local")
    tenant = api.onboard("Earthworks Two", price="1")
    tid = tenant["tenant"]["id"]
    m = grant(api, tid)
    asha = staff(api, "staff-asha", "asha@asseta.local")
    assert assign(api, m, "asha@asseta.local", "owner").status_code == 200
    asha = refreshed(api, asha, tid)
    _err(_switch(asha, False), 403, "MANAGED_SERVICE_SWITCH_LOCKED")
    # Sending the unchanged value is not a change.
    assert _switch(asha, True).status_code == 201


def test_revoke_is_never_refused_by_the_switch(api: Api) -> None:
    staff(api, PLATFORM_SUBJECT, "platform@asseta.local")
    tenant = api.onboard("Earthworks Three", price="1")
    tid, owner = tenant["tenant"]["id"], tenant["owner"]
    assert _switch(owner, False).status_code == 201  # off while no mandate exists
    m = grant(api, tid)  # the platform grants one afterwards
    # The page shows again while a mandate is open, even though the switch is off.
    assert owner.get(f"{T}/managed-service").status_code == 200
    r = owner.post(f"{T}/managed-service/{m['id']}/revoke", {"version": 1, "reason": "No longer needed"})
    assert r.status_code == 200, r.text
    assert owner.get(f"{T}/managed-service").status_code == 422  # hidden again once no mandate is open
