"""IDOR sweep (prompt.md §10 #11, check v): tenant B owns a populated data set (machines, trackers, sites, geofences,
customers, contracts, jobs, meter evidence, hire invoices, payments, expenses + receipts, cases, notifications…);
tenant A's OWNER — the most privileged tenant role — addresses B's real ids under A's own tenant context.

* every tenant GET route whose path ids can be filled with B's ids -> 404 (never B's data, never an empty 200);
* every tenant write route with B's ids -> never 2xx, and B's data is byte-for-byte unchanged afterwards;
* well-formed writes that *reference* B's ids in the body (cross-tenant foreign keys) -> 404.
"""

import uuid
from datetime import timedelta
from typing import Any

import pytest
from fastapi import FastAPI

from tests.support.api import Actor, Api
from tests.support.finance import (
    FinCtx,
    category,
    complete_job,
    expense_policy,
    issue_invoice,
    setup_finance,
)
from tests.support.intelligence import cases, expense, feed_events, receipt
from tests.support.jobs import capture, photo, unique_jpeg
from tests.support.notify import drain
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
    return {u: f.owner.get(u, **_query(u)).json() for u in urls}


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
