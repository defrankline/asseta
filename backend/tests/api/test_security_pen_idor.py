"""IDOR sweep (prompt.md §10 #11, check v): tenant B owns a populated data set (machines, trackers, sites, geofences,
customers, contracts, jobs, meter evidence, hire invoices, payments, expenses + receipts, cases, notifications…);
tenant A's OWNER — the most privileged tenant role — addresses B's real ids under A's own tenant context.

* every tenant GET route whose path ids can be filled with B's ids -> 404 (never B's data, never an empty 200);
* every tenant write route with B's ids -> never 2xx, and B's data is byte-for-byte unchanged afterwards;
* well-formed writes that *reference* B's ids in the body (cross-tenant foreign keys) -> 404.
"""

import uuid
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI

from asseta.core.db import get_sessionmaker
from asseta.modules.finance.remittance_cutoff import run_remittance_cutoff
from asseta.modules.revenue.reconciliation import run_revenue_reconciliation
from tests.support.api import Actor, Api
from tests.support.finance import (
    FinCtx,
    cash_policy,
    category,
    complete_job,
    expense_policy,
    issue_invoice,
    role,
    setup_finance,
)
from tests.support.intelligence import cases, expense, feed_events, receipt
from tests.support.jobs import capture, photo, unique_jpeg
from tests.support.notify import drain, sql
from tests.support.routes import Kind, RouteSpec, concrete, inventory, params

T = "/api/v1/tenant"
SQUARE = {
    "type": "Polygon",
    "coordinates": [[[39.27, -6.81], [39.29, -6.81], [39.29, -6.79], [39.27, -6.79], [39.27, -6.81]]],
}


def _first_id(actor: Actor, path: str, **q: Any) -> str | None:
    body = actor.get(path, **q).json()
    items = body.get("items", body) if isinstance(body, dict) else body
    return str(items[0]["id"]) if isinstance(items, list) and items else None


def _populate_b(api: Api) -> tuple[FinCtx, dict[tuple[str, str], str]]:
    """Tenant B with one of everything; returns (ctx, {(path prefix, param name): id})."""
    f = setup_finance(api, "Idor Bravo", "IDOR-B")
    o = f.owner
    ids: dict[tuple[str, str], str] = {
        ("/machines/", "machine_id"): f.c.t.machine_id,
        ("/fleet/machines/", "machine_id"): f.c.t.machine_id,
        ("/machine-categories/", "category_id"): f.c.category_id,
        ("/staff/", "staff_id"): f.sup_staff_id,
        ("/trackers/", "tracker_id"): f.c.t.tracker_id,
        ("/customers/", "customer_id"): f.customer_id,
        ("/contracts/", "contract_id"): f.c.contract_id,
        ("/jobs/", "job_id"): f.c.job_id,
    }
    ids[("/operating-areas/", "area_id")] = o.post(f"{T}/operating-areas", {"code": "BAR", "name": "B area"}).json()[
        "id"
    ]
    site = o.post(
        f"{T}/job-sites", {"code": "BS1", "name": "B site", "center": {"type": "Point", "coordinates": [39.28, -6.8]}}
    )
    ids[("/job-sites/", "site_id")] = site.json()["id"]
    geo = o.post(f"{T}/geofences", {"name": "B yard", "kind": "ALLOWED_AREA", "polygon": SQUARE})
    ids[("/geofences/", "geofence_id")] = geo.json()["id"]
    ph = api.client.post(
        f"{T}/machines/{f.c.t.machine_id}/photos",
        headers=o.headers(True, None),
        files={"file": ("p.jpg", unique_jpeg(), "image/jpeg")},
        data={"caption": "B front"},
    )
    ids[("/photos/", "photo_id")] = ph.json()["id"]
    ids[("/attachments/", "attachment_id")] = photo(api, o)
    # Completed job -> issued invoice -> claimed payment.
    complete_job(api, f, f.c.job_id, "100.0", "108.0", 8)
    inv = issue_invoice(f, [f.c.job_id])
    ids[("/hire-invoices/", "invoice_id")] = inv["id"]
    pay = f.accountant.post(
        f"{T}/customer-payments",
        {
            "customer_id": f.customer_id,
            "amount": "1000",
            "method": "BANK",
            "reference": "B-PAY-1",
            "received_at": api.clock.now.isoformat(),
        },
    )
    assert pay.status_code == 201, pay.text
    ids[("/customer-payments/", "payment_id")] = pay.json()["id"]
    ids |= _engine_hours_records(api, f)
    # Duplicate receipt -> expense + receipt + investigation case.
    cat = category(f, "SPARES", "Spares")
    ids[("/expense-categories/", "category_id")] = cat
    expense_policy(f, receipt_required_above="0", gps_required=False, auto_approve_limit="0")
    image = unique_jpeg()
    rec = ""
    for _ in range(2):
        rec = receipt(api, f.supervisor, image)
        exp = expense(api, f.supervisor, cat, "45000", receipt_attachment_ids=[rec])
        api.clock.set_at(api.clock.now + timedelta(minutes=30))
    ids[("/expenses/", "expense_id")] = exp["id"]
    ids[("/receipts/", "attachment_id")] = rec
    feed_events(api, f.tid)
    ids[("/cases/", "case_id")] = cases(o)[0]["id"]
    drain(api)
    ids.update(_customer_hours_b(api, f))
    ids.update(_cash_chain_b(api, f))
    ids.update(_revenue_b(api, f))
    ids.update(_oversight_b(api, f))
    optional = {
        ("/notifications/", "notification_id"): f"{T}/notifications",
        ("/assignments/", "assignment_id"): f"{T}/machines/{f.c.t.machine_id}/assignments",
        ("/enrollments/", "eid"): f"{T}/billing/enrollments",
        ("/exceptions/", "exception_id"): f"{T}/exceptions",
        ("/approvals/", "approval_id"): f"{T}/approvals",
        ("/alerts/", "alert_id"): f"{T}/alerts",
    }
    for key, path in optional.items():
        found = _first_id(o, path)
        if found:
            ids[key] = found
    return f, ids


def _customer_hours_b(api: Api, f: FinCtx) -> dict[tuple[str, str], str]:
    """B's customer hours records: a reason code, discount and credit proposals, a verified purchase with a pending
    transfer, a pending cancellation, payment evidence and a work execution allocation."""
    o = f.owner
    reason = o.post(f"{T}/hours-reason-codes", {"kind": "TRANSFER", "code": "BRK", "label": "Breakdown"})
    assert reason.status_code == 201, reason.text
    since = {"customer_id": f.customer_id, "effective_from": "2026-01-01"}
    disc = o.post(f"{T}/customer-discounts", {**since, "percent": "5", "reason": "B discount"})
    credit = o.post(f"{T}/credit-arrangements", {**since, "limit_amount": "100000", "reason": "B account"})
    assert disc.status_code == credit.status_code == 201, disc.text + credit.text
    now = api.clock.now.isoformat()
    bought = f.accountant.post(
        f"{T}/hours-purchases",
        {
            "customer_id": f.customer_id,
            "machine_id": f.c.t.machine_id,
            "hours": "2",
            "payment": {"method": "BANK", "reference": "B-HP-1", "received_at": now},
        },
    )
    assert bought.status_code == 201, bought.text
    verified = f.accountant2.post(
        f"{T}/customer-payments/{bought.json()['payment']['id']}/decision", {"verified": True}
    )
    assert verified.status_code == 200, verified.text
    spare = o.post(f"{T}/machines", {"asset_code": "B-SPARE", "name": "B spare"}).json()["id"]
    transfer = o.post(
        f"{T}/hours-transfers",
        {"purchase_id": bought.json()["id"], "to_machine_id": spare, "hours": "1", "reason": "B breakdown"},
    )
    assert transfer.status_code == 201, transfer.text
    other = f.accountant.post(
        f"{T}/hours-purchases", {"customer_id": f.customer_id, "machine_id": f.c.t.machine_id, "hours": "1"}
    )
    cancel = o.post(f"{T}/hours-purchases/{other.json()['id']}/cancellation", {"reason": "B changed plans"})
    assert cancel.status_code == 201, cancel.text
    up = api.client.post(
        f"{T}/payment-evidence",
        headers=f.accountant.headers(True, None),
        files={"file": ("r.jpg", unique_jpeg(), "image/jpeg")},
    )
    pay = bought.json()["payment"]["id"]
    assert (
        f.accountant.post(f"{T}/customer-payments/{pay}/evidence", {"attachment_ids": [up.json()["id"]]}).status_code
        == 201
    )
    allocation = str(uuid.uuid4())
    sql(
        "INSERT INTO work_execution_allocation (id, tenant_id, job_id, customer_id, machine_id, billable_hours,"
        " policy_version, created_at) VALUES (:i, :t, :j, :c, :m, 0, 'test', now())",
        i=allocation,
        t=f.tid,
        j=f.c.job_id,
        c=f.customer_id,
        m=f.c.t.machine_id,
    )
    alert = str(uuid.uuid4())
    sql(
        "INSERT INTO hours_low_balance_alert (id, tenant_id, purchase_id, customer_id, machine_id, sequence,"
        " threshold_hours, remaining_hours, available_hours, crossed_at, notify_customer, customer_sms_status,"
        " policy_version, created_at) VALUES (:i, :t, :p, :c, :m, 1, 2, 1, 1, now(), false, 'NOT_REQUESTED',"
        " 'test', now())",
        i=alert,
        t=f.tid,
        p=bought.json()["id"],
        c=f.customer_id,
        m=f.c.t.machine_id,
    )
    return {
        ("/hours-low-balance-alerts/", "alert_id"): alert,
        ("/hours-reason-codes/", "code_id"): reason.json()["id"],
        ("/customer-discounts/", "discount_id"): disc.json()["id"],
        ("/credit-arrangements/", "arrangement_id"): credit.json()["id"],
        ("/hours-purchases/", "purchase_id"): bought.json()["id"],
        ("/hours-transfers/", "transfer_id"): transfer.json()["id"],
        ("/hours-cancellations/", "cancellation_id"): cancel.json()["id"],
        ("/work-execution-allocations/", "allocation_id"): allocation,
        ("/customer-payments/", "payment_id"): pay,
        ("/evidence/", "attachment_id"): up.json()["id"],
    }


def _cash_chain_b(api: Api, f: FinCtx) -> dict[tuple[str, str], str]:
    """B's cash custody chain records: a transfer, a remittance variance, a reason and a rejected device op."""
    c = f"{T}/cash"
    now = api.clock.now.isoformat()
    other = f.owner.post(f"{T}/staff", {"full_name": "B operator", "kind": "OPERATOR"}).json()["id"]
    transfer = f.supervisor.post(f"{c}/transfers", {"to_staff_id": other, "amount": "10", "transferred_at": now})
    assert transfer.status_code == 201, transfer.text
    slip = api.client.post(
        f"{c}/remittance-evidence",
        headers=f.supervisor.headers(True, None),
        files={"file": ("slip.jpg", unique_jpeg(), "image/jpeg")},
    ).json()["id"]
    account = f.accountant.post(f"{T}/deposit-accounts", {"name": "B bank", "account_type": "BANK"}).json()["id"]
    h = f.supervisor.post(
        f"{c}/handovers",
        {"amount": "10", "handed_at": now, "deposit_account_id": account, "evidence_attachment_ids": [slip]},
    ).json()
    f.accountant.post(f"{c}/handovers/{h['id']}/decision", {"verified": True, "amount_received": "9"})
    variance = f.accountant.get(f"{c}/variances").json()["items"][0]["id"]
    reason = f.accountant.post(f"{c}/reasons", {"kind": "VARIANCE", "label": "B reason"}).json()["id"]
    issued = f.accountant.post(f"{c}/floats", {"staff_member_id": other, "amount": "5", "occurred_at": now})
    assert issued.status_code == 201, issued.text
    retention = f.supervisor.post(f"{c}/retentions", {"amount": "1", "reason": "B keeps a float"}).json()["id"]
    adjustment = f.accountant.post(
        f"{c}/adjustments", {"staff_member_id": other, "kind": "ADJUSTMENT", "amount": "1", "reason": "B recount"}
    ).json()["id"]
    # Unremitted cash held from before today's cut-off (00:00 local) -> one REMITTANCE_OVERDUE flag.
    earlier = (api.clock.now - timedelta(days=2)).isoformat()
    paid = f.accountant.post(
        f"{c}/collections",
        {"customer_id": f.customer_id, "amount": "3", "received_at": earlier, "staff_member_id": other},
    )
    assert paid.status_code == 201, paid.text
    cash_policy(f, remittance_cutoff_hour=0)
    assert run_remittance_cutoff(get_sessionmaker(), api.clock.now).flagged >= 1
    overdue = f.accountant.get(f"{c}/remittance-overdue").json()["items"][0]["id"]
    headers = {**f.supervisor.headers(True, None), "X-Device-Id": "idor-b-device-01"}
    api.client.post(
        "/api/v1/sync/devices",
        headers=headers,
        json={"device_id": "idor-b-device-01", "platform": "ANDROID", "app_version": "1"},
    )
    op_id = str(uuid.uuid4())
    op = {"id": op_id, "op_type": "CASH_TRANSFER_ACKNOWLEDGEMENT", "created_at_device": now,
          "payload": {"transfer_id": str(uuid.uuid4()), "acknowledged": True}}  # fmt: skip
    pushed = api.client.post("/api/v1/sync/push", headers=headers, json={"device_now": now, "operations": [op]})
    assert pushed.json()["results"][0]["status"] == "REJECTED", pushed.text
    return {
        ("/transfers/", "transfer_id"): transfer.json()["id"],
        ("/variances/", "variance_id"): variance,
        ("/reasons/", "reason_id"): reason,
        ("/handovers/", "handover_id"): h["id"],
        ("{handover_id}/evidence/", "attachment_id"): slip,
        ("/deposit-accounts/", "account_id"): account,
        ("/floats/", "entry_id"): issued.json()["id"],
        ("/retentions/", "retention_id"): retention,
        ("/adjustments/", "adjustment_id"): adjustment,
        ("/remittance-overdue/", "overdue_id"): overdue,
        ("/sync/conflicts/", "operation_id"): op_id,
    }


def _revenue_policy(owner: Actor) -> None:
    r = owner.post(
        f"{T}/policies/REVENUE_RECONCILIATION/versions",
        {
            "scope": "TENANT",
            "values": {"enabled": True, "period": "DAY", "deduct_non_revenue_from_working_hours": True},
            "reason": "Revenue checks on",
        },
    )
    assert r.status_code == 201, r.text


def _revenue_b(api: Api, f: FinCtx) -> dict[tuple[str, str], str]:
    """B's revenue records (DEC-031): a reason, a non-revenue approval proposal and a revenue difference (the
    unexplained engine hours after the job are expected revenue), plus a machine-day of the daily sheet."""
    o = f.owner
    _revenue_policy(o)
    job = o.get(f"{T}/jobs/{f.c.job_id}").json()["job"]
    start = datetime.fromisoformat(job["started_at"])
    move = o.post(
        f"{T}/jobs/{f.c.job_id}/activities",
        {
            "client_id": str(uuid.uuid4()),
            "activity_type": "MOBILIZATION",
            "started_at": start.isoformat(),
            "ended_at": (start + timedelta(minutes=30)).isoformat(),
        },
    )
    assert move.status_code == 201, move.text
    reason = o.post(f"{T}/revenue-reasons", {"code": "MOVE", "name": "B move"}).json()["id"]
    approval = f.accountant.post(
        f"{T}/non-revenue-approvals",
        {"activity_id": move.json()["id"], "reason_id": reason, "note": "B moved to site"},
    )
    assert approval.status_code == 201, approval.text
    assert run_revenue_reconciliation(get_sessionmaker(), api.clock.now + timedelta(days=2)).opened >= 1
    diff = o.get(f"{T}/revenue-differences").json()["items"][0]["id"]
    return {
        ("/revenue-reasons/", "reason_id"): reason,
        ("/non-revenue-approvals/", "approval_id"): approval.json()["id"],
        ("/revenue-differences/", "difference_id"): diff,
        ("/daily-machine-sheet/", "machine_id"): f.c.t.machine_id,
        ("{machine_id}/", "day"): start.astimezone(ZoneInfo("Africa/Dar_es_Salaam")).date().isoformat(),
    }


def _oversight_policy(owner: Actor) -> None:
    r = owner.post(
        f"{T}/policies/OVERSIGHT/versions",
        {
            "scope": "TENANT",
            "values": {"scorecard_enabled": True, "site_checkin_required": True, "site_checkin_times": ["09:00"]},
            "reason": "Oversight on",
        },
    )
    assert r.status_code == 201, r.text


def _oversight_b(api: Api, f: FinCtx) -> dict[tuple[str, str], str]:
    """B's oversight records (DEC-031 Phase 5): a person's scorecard and a site check-in."""
    _oversight_policy(f.owner)
    now = api.clock.now.isoformat()
    checkin = f.supervisor.post(
        f"{T}/site-checkins",
        {"client_id": str(uuid.uuid4()), "captured_at": now, "gps": {"status": "NO_FIX"}},
    )
    assert checkin.status_code == 201, checkin.text
    return {
        ("/scorecard/", "staff_member_id"): f.sup_staff_id,
        ("/site-checkins/", "checkin_id"): checkin.json()["id"],
    }


def _engine_hours_records(api: Api, f: FinCtx) -> dict[tuple[str, str], str]:
    """Baseline (from the earliest reading, approved by a second owner), a list entry, a classification proposal
    and a correction proposal on B's machine."""
    o, machine = f.owner, f.c.t.machine_id
    approver = role(api, f.tid, "owner", "idor-b-approver")
    base = o.post(f"{T}/meter-baselines/from-reading", {"machine_id": machine})
    assert base.status_code == 201, base.text
    ok = approver.post(
        f"{T}/meter-baselines/{base.json()['id']}/decision", {"decision": "APPROVE", "note": "Evidence checked"}
    )
    assert ok.status_code == 200, ok.text
    reason = o.post(f"{T}/engine-hour-reasons", {"kind": "NON_CUSTOMER_CATEGORY", "code": "MAINT", "name": "Service"})
    api.clock.set_at(api.clock.now + timedelta(hours=3))
    daily = capture("", "DAILY", "110.0", api.clock.now, mode="MANUAL")
    daily.pop("job_id")
    daily["machine_id"] = machine
    assert o.post(f"{T}/meter-captures", daily).status_code == 201
    seg = o.get(f"{T}/engine-hours/unallocated").json()["items"][0]
    cls = o.post(
        f"{T}/engine-hours/classifications",
        {
            "machine_id": machine,
            "start_ref": seg["start"]["ref"],
            "end_ref": seg["end"]["ref"],
            "outcome": "APPROVED_NON_CUSTOMER",
            "reason_id": reason.json()["id"],
            "note": "Moved to the yard",
        },
    )
    assert cls.status_code == 201, cls.text
    fix = {**daily, "id": str(uuid.uuid4()), "reading": "109.5"}
    corr = o.post(
        f"{T}/meter-corrections",
        {"superseded_capture_id": daily["id"], "reason": "Misread the last digit", "replacement": fix},
    )
    assert corr.status_code == 201, corr.text
    return {
        ("/meter-baselines/", "baseline_id"): base.json()["id"],
        ("/engine-hour-reasons/", "reason_id"): reason.json()["id"],
        ("/engine-hours/classifications/", "classification_id"): cls.json()["id"],
        ("/meter-corrections/", "correction_id"): corr.json()["id"],
    }


QUERY = {
    "/history": {"from": "2026-10-20T00:00:00Z", "to": "2026-11-15T00:00:00Z"},  # <= 31 days
    "/statement": {"from": "2026-10-01", "to": "2026-12-01"},
}


def _query(path: str) -> dict[str, str]:
    return next((q for suffix, q in QUERY.items() if path.endswith(suffix)), {})


def _fill(path: str, ids: dict[tuple[str, str], str]) -> dict[str, str] | None:
    """B's id for every path parameter (matched on the closest preceding collection segment), else None."""
    out: dict[str, str] = {}
    for name in params(path):
        prefix = path.split("{" + name + "}")[0]
        best = [(p, v) for (p, n), v in ids.items() if n == name and prefix.endswith(p)]
        if not best:
            return None
        out[name] = max(best, key=lambda pv: len(pv[0]))[1]
    return out


@pytest.fixture
def world(api: Api) -> tuple[Actor, FinCtx, dict[tuple[str, str], str]]:
    f, ids = _populate_b(api)
    a = api.onboard("Idor Alpha", price="1000")
    api.activate(a)
    _revenue_policy(a["owner"])  # A has the capability too: B's revenue records are still not found
    _oversight_policy(a["owner"])
    return a["owner"], f, ids


def _tenant_routes(api: Api) -> list[RouteSpec]:
    app: FastAPI = api.client.app  # type: ignore[assignment]
    return [r for r in inventory(app) if r.kind is Kind.TENANT and params(r.path)]


def test_every_tenant_read_by_id_of_another_tenant_is_not_found(
    api: Api, world: tuple[Actor, FinCtx, dict[tuple[str, str], str]]
) -> None:
    owner_a, f, ids = world
    failures, checked, skipped = [], 0, []
    for spec in (r for r in _tenant_routes(api) if r.method == "GET"):
        values = _fill(spec.path, ids)
        if values is None:
            skipped.append(spec.path)
            continue
        url, q = concrete(spec.path, values), _query(spec.path)
        assert f.owner.get(url, **q).status_code == 200, f"control: B's own owner must read {url}"
        r = owner_a.get(url, **q)
        checked += 1
        if r.status_code != 404:
            failures.append(f"{spec.label} -> {r.status_code} {r.text[:160]}")
    assert not failures, "\n".join(failures)
    # Only non-id parameters may remain (policy type enum).
    assert all("{ptype}" in p for p in skipped), skipped
    print(f"\n(v) IDOR reads: {checked} GET-by-id routes with B's real ids -> 404 (skipped: {skipped})")


def _b_state(f: FinCtx, urls: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for u in urls:
        r = f.owner.get(u, **_query(u))
        out[u] = r.json() if r.headers.get("content-type", "").startswith("application/json") else len(r.content)
    return out


def test_every_tenant_write_on_another_tenants_ids_fails_and_changes_nothing(
    api: Api, world: tuple[Actor, FinCtx, dict[tuple[str, str], str]]
) -> None:
    owner_a, f, ids = world
    reads = [
        concrete(r.path, v) for r in _tenant_routes(api) if r.method == "GET" and (v := _fill(r.path, ids)) is not None
    ]
    before = _b_state(f, reads)
    failures, checked = [], 0
    for spec in (r for r in _tenant_routes(api) if r.method != "GET"):
        values = _fill(spec.path, ids)
        if values is None:
            continue
        for body in ({}, {"reason": "pen test", "version": 1, "action": "CANCEL", "body": "x", "verified": True}):
            r = api.client.request(
                spec.method, concrete(spec.path, values), headers=owner_a.headers(True, None), json=body
            )
            checked += 1
            if r.status_code < 300 or r.status_code >= 500:
                failures.append(f"{spec.label} -> {r.status_code} {r.text[:160]}")
    assert not failures, "\n".join(failures)
    assert _b_state(f, reads) == before  # nothing of B changed
    print(f"\n(v) IDOR writes: {checked} write attempts on B's ids, none succeeded, B unchanged ({len(reads)} reads)")


def test_crafted_cross_tenant_writes_are_not_found(
    api: Api, world: tuple[Actor, FinCtx, dict[tuple[str, str], str]]
) -> None:
    owner_a, f, ids = world
    now = api.clock.now.isoformat()
    b_job, b_machine = ids[("/jobs/", "job_id")], ids[("/machines/", "machine_id")]
    job_before = f.owner.get(f"{T}/jobs/{b_job}").json()
    m = f.owner.get(f"{T}/machines/{b_machine}").json()
    keys = ("name", "operating_area_id", "manufacturer", "model", "serial_number", "category_id", "status", "version")
    attempts: list[tuple[str, str, dict[str, Any]]] = [
        ("PUT", f"{T}/machines/{b_machine}", {k: m[k] for k in keys}),
        ("POST", f"{T}/jobs/{b_job}/transitions", {"action": "CANCEL", "reason": "hostile cancel"}),
        (
            "POST",
            f"{T}/jobs/{b_job}/activities",
            {"client_id": str(uuid.uuid4()), "activity_type": "NOTE", "started_at": now, "note": "x"},
        ),
        (
            "POST",
            f"{T}/trackers/{ids[('/trackers/', 'tracker_id')]}/unassign",
            {"effective_to": now, "reason": "hostile"},
        ),
        ("POST", f"{T}/hire-invoices/{ids[('/hire-invoices/', 'invoice_id')]}/void", {"reason": "hostile void"}),
        ("POST", f"{T}/customer-payments/{ids[('/customer-payments/', 'payment_id')]}/decision", {"verified": True}),
        ("POST", f"{T}/cases/{ids[('/cases/', 'case_id')]}/notes", {"body": "hostile note"}),
        ("POST", f"{T}/customers/{ids[('/customers/', 'customer_id')]}/deactivate", {"reason": "hostile"}),
        # Body references to B's records from A's context (cross-tenant foreign keys).
        ("POST", f"{T}/meter-captures", capture(b_job, "OPENING", "1.0", api.clock.now, mode="MANUAL")),
        ("POST", f"{T}/billing/enrollments", {"machine_id": b_machine, "effective_from": now[:10]}),
        ("POST", f"{T}/hire-invoices", {"customer_id": ids[("/customers/", "customer_id")], "job_ids": [b_job]}),
        (
            "POST",
            f"{T}/jobs",
            {
                "contract_id": ids[("/contracts/", "contract_id")],
                "job_number": "X-1",
                "machine_id": b_machine,
                "planned_start": now,
            },
        ),
        (
            "POST",
            f"{T}/customer-payments",
            {"customer_id": ids[("/customers/", "customer_id")], "amount": "1", "method": "CASH", "received_at": now},
        ),
    ]
    # Indistinguishable from a non-existent id (same code + message as for a random UUID) is acceptable too.
    not_found_equivalent = {(422, "CONTRACT_NOT_ACTIVE")}
    failures = []
    for method, url, body in attempts:
        r = api.client.request(method, url, headers=owner_a.headers(True, None), json=body)
        code = r.json().get("error", {}).get("code") if r.status_code >= 400 else None
        if r.status_code != 404 and (r.status_code, code) not in not_found_equivalent:
            failures.append(f"{method} {url} -> {r.status_code} {r.text[:200]}")
    assert not failures, "\n".join(failures)
    assert f.owner.get(f"{T}/jobs/{b_job}").json() == job_before
