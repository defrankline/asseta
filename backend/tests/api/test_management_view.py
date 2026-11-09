"""DEC-032 Phase 4: the section 8 dashboard, the employee view, the transaction lookup, the role templates and the
smaller management additions (guideline sections 6, 8, 10)."""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Engine, event

from asseta.core.db import get_sessionmaker
from asseta.modules.finance.cash_service import CashCustodyService
from asseta.modules.finance.custody_totals import all_custody_balances
from asseta.modules.identity.authz_sync import AuthzSyncService
from asseta.modules.identity.catalog import CATALOG, PermissionScope
from asseta.modules.identity.principal import RequestContext
from asseta.modules.identity.role_templates import DECISION_PERMISSIONS, TENANT_TEMPLATES, template_permissions
from tests.support.api import Actor, Api
from tests.support.finance import FinCtx, cash_policy, role, setup_finance
from tests.support.hours import purchase, verify
from tests.support.jobs import capture, unique_jpeg

T = "/api/v1/tenant"
C = f"{T}/cash"


def _ok(r: Any, status: int = 200) -> Any:
    assert r.status_code == status, r.text
    return r.json()


def _template(key: str) -> set[str]:
    return template_permissions(next(t for t in TENANT_TEMPLATES if t.key == key))


def _summary(actor: Actor, **params: Any) -> Any:
    return _ok(actor.get(f"{T}/accountability/summary", **params))


def _amounts(figure: dict[str, Any]) -> list[tuple[str, str]]:
    return [(x["currency"], x["amount"]) for x in figure["lines"]]


def _operator(f: FinCtx, name: str = "Operator Zuberi") -> str:
    return str(_ok(f.owner.post(f"{T}/staff", {"full_name": name, "kind": "OPERATOR"}), 201)["id"])


def _collect(api: Api, f: FinCtx, staff: str, amount: str) -> Any:
    body = {"customer_id": f.customer_id, "amount": amount, "received_at": api.clock.now.isoformat()}
    return _ok(f.manager.post(f"{C}/collections", {**body, "staff_member_id": staff}), 201)


def _remit(api: Api, f: FinCtx, staff: str, amount: str) -> Any:
    body = {"staff_member_id": staff, "amount": amount, "handed_at": api.clock.now.isoformat()}
    return _ok(f.manager.post(f"{C}/handovers", {**body, "partial_reason": "Bank closed early"}), 201)


# --- role templates -----------------------------------------------------------------------------------------------
def test_field_and_administrator_templates_hold_no_decision_permission() -> None:
    every = {p.code for p in CATALOG.permissions() if p.scope is PermissionScope.TENANT}
    assert every >= DECISION_PERMISSIONS  # the list names real permissions
    words = ("approve", "decide", "verify", "writeoff", "variance_close", "resolve", "classify")
    for key in ("supervisor", "operator", "operator-readings", "administrator"):
        held = _template(key)
        assert not held & DECISION_PERMISSIONS, key
        assert not [c for c in held if any(w in c for w in words)], key
    assert "tenant.hours.transfer" in _template("supervisor")
    assert "tenant.hours.transfer_approve" not in _template("supervisor")


def test_template_contents() -> None:
    manager = _template("manager")
    assert {"tenant.meter.read", "tenant.meter.review", "tenant.meter.approve", "tenant.meter.classify"} <= manager
    assert "tenant.meter.capture" not in _template("operator")
    assert "tenant.meter.capture" in _template("operator-readings")
    admin = _template("administrator")
    assert {"tenant.access.manage", "tenant.policy.manage"} <= admin
    assert not [c for c in admin if c.startswith(("tenant.collection.", "tenant.job.", "tenant.adjustment."))]
    finance = _template("accountant")
    assert "tenant.finance.verify" in finance
    assert not [c for c in finance if c.startswith("tenant.meter.")]
    assert "tenant.job.approve" not in finance


def _sync(api: Api) -> None:
    with get_sessionmaker().begin() as s:
        AuthzSyncService(api.idp).full_sync(s)


def test_existing_groups_narrowed_once_and_edited_groups_not_widened(api: Api) -> None:
    t = api.onboard("Roles Co", price="1")
    tid = t["tenant"]["id"]
    from tests.support.notify import sql

    def group(key: str) -> str:
        return str(api.idp.groups[f"/tenants/{tid}/{key}"])

    def forget(key: str, code: str) -> None:
        sql(
            "DELETE FROM role_template_grant WHERE group_path = :p AND permission_code = :c",
            p=f"/tenants/{tid}/{key}",
            c=code,
        )

    # A deployment from before this release: the leak is held and was offered, the manager never had meter approval.
    sup, mgr = group("supervisor"), group("manager")
    api.idp.group_perms[sup].add("tenant.hours.transfer_approve")
    sql(
        "INSERT INTO role_template_grant (group_path, permission_code, offered_at) VALUES (:p, :c, now())",
        p=f"/tenants/{tid}/supervisor",
        c="tenant.hours.transfer_approve",
    )
    forget("supervisor", "retired:tenant.hours.transfer_approve")
    api.idp.group_perms[mgr] -= {"tenant.meter.approve", "tenant.meter.review"}
    for code in ("tenant.meter.approve", "tenant.meter.review"):
        forget("manager", code)
    custom = api.idp.ensure_group(f"/tenants/{tid}/night-shift")
    api.idp.group_perms[custom] = {"tenant.job.read"}

    _sync(api)
    assert "tenant.hours.transfer_approve" not in api.idp.group_perms[sup]
    assert "tenant.meter.approve" in api.idp.group_perms[mgr]  # nobody edited this group: it gains the approvals
    assert api.idp.group_perms[custom] == {"tenant.job.read"}  # a custom role is never touched

    api.idp.group_perms[sup].add("tenant.hours.transfer_approve")  # the tenant deliberately grants it back
    _sync(api)
    assert "tenant.hours.transfer_approve" in api.idp.group_perms[sup]

    # An owner who edited their manager group keeps their arrangement.
    api.idp.group_perms[mgr] -= {"tenant.meter.approve", "tenant.meter.review", "tenant.case.manage"}
    for code in ("tenant.meter.approve", "tenant.meter.review"):
        forget("manager", code)
    _sync(api)
    assert not api.idp.group_perms[mgr] & {"tenant.meter.approve", "tenant.meter.review"}


def test_new_templates_reach_tenants_provisioned_earlier(api: Api) -> None:
    t = api.onboard("Earlier Co", price="1")
    from tests.support.notify import sql

    path = f"/tenants/{t['tenant']['id']}/administrator"
    api.idp.groups.pop(path)
    sql("DELETE FROM role_template_grant WHERE group_path = :p", p=path)
    _sync(api)
    assert "tenant.access.manage" in api.idp.group_perms[api.idp.groups[path]]


# --- section 8 ----------------------------------------------------------------------------------------------------
def test_customer_hours_section(api: Api) -> None:
    f = setup_finance(api, "Hours View", "HV-1")
    paid = purchase(api, f.owner, f, "10", pay="850000")
    verify(f.accountant, paid["payment"]["id"])
    claimed = purchase(api, f.owner, f, "4", pay="340000")
    unpaid = purchase(api, f.manager, f, "3")
    s = _summary(f.owner)["hours_section"]
    assert s["purchased"]["hours"] == "17.00" and s["purchased"]["count"] == 3
    assert s["activated"]["hours"] == "10.00" and "entry_type=ACTIVATED" in s["activated"]["route"]
    assert s["consumed"]["hours"] == "0"
    assert s["remaining"]["hours"] == "10.00"
    row = s["remaining_by_customer"][0]
    assert row["customer_id"] == f.customer_id and row["customer_name"] and row["remaining"] == "10.00"
    assert [i["purchase_id"] for i in s["unconfirmed_purchases"]["items"]] == [claimed["id"]]
    assert [i["purchase_id"] for i in s["unpaid_purchases"]["items"]] == [unpaid["id"]]
    assert s["awaiting_activation"]["hours"] == "7.00" and s["awaiting_activation"]["count"] == 2
    assert s["unpaid_purchases"]["items"][0]["purchase_number"].startswith("HP-")
    listed = _ok(f.owner.get(f"{T}/hours-purchases", queue="UNPAID"))["items"]
    assert [p["id"] for p in listed] == [unpaid["id"]]

    tomorrow = (api.clock.now + timedelta(days=1)).date().isoformat()
    later = _summary(f.owner, date_from=tomorrow, date_to=tomorrow)["hours_section"]
    assert later["purchased"]["count"] == 0 and later["activated"]["count"] == 0
    assert later["remaining"]["hours"] == "10.00" and later["awaiting_activation"]["count"] == 2  # position now


def test_excavator_operations_section(api: Api) -> None:
    f = setup_finance(api, "Ops View", "OV-1")
    machine = f.c.t.machine_id
    start = api.clock.now
    for value, at in (("100", start), ("108", start + timedelta(hours=8))):
        body = capture("", "DAILY", value, at, mode="MANUAL")
        body.pop("job_id")
        api.clock.set_at(at)
        _ok(f.owner.post(f"{T}/meter-captures", {**body, "machine_id": machine}), 201)
    s = _summary(f.owner)["operations_section"]
    assert s["unexplained_hours"]["hours"] == s["operating_hours"]["hours"]
    assert float(s["unexplained_hours"]["hours"]) > 0
    assert "kind=UNEXPLAINED" in s["unexplained_hours"]["route"]
    row = s["by_excavator"][0]
    assert (
        row["machine_id"] == machine and row["machine_code"] and row["operating_hours"] == s["operating_hours"]["hours"]
    )
    assert s["pending_reports"]["count"] == 0 and s["meter_discrepancies"]["count"] == 0
    exceptions = _summary(f.owner)["exceptions_section"]
    assert exceptions["unexplained_engine_hours"]["hours"] == s["unexplained_hours"]["hours"]


def test_cash_section_and_bulk_balances_match_the_ledger(api: Api) -> None:
    f = setup_finance(api, "Cash View", "CV-1")
    a, b = _operator(f), _operator(f, "Operator Baraka")
    _collect(api, f, a, "70000")
    now = api.clock.now.isoformat()
    moved = _ok(
        f.manager.post(
            f"{C}/transfers", {"from_staff_id": a, "to_staff_id": b, "amount": "20000", "transferred_at": now}
        ),
        201,
    )
    _ok(
        f.owner.post(f"{C}/transfers/{moved['id']}/acknowledgement", {"acknowledged": True, "amount_received": "20000"})
    )
    done = _remit(api, f, a, "10000")
    _ok(f.accountant.post(f"{C}/handovers/{done['id']}/decision", {"verified": True, "amount_received": "10000"}))
    refused = _remit(api, f, a, "5000")
    _ok(f.accountant.post(f"{C}/handovers/{refused['id']}/decision", {"verified": False, "note": "Not received"}))
    waiting = _remit(api, f, a, "3000")

    s = _summary(f.owner)["cash_section"]
    assert _amounts(s["collected"]) == [("TZS", "70000.0000")] and "method=CASH" in s["collected"]["route"]
    assert _amounts(s["transferred"]) == [("TZS", "20000.0000")]
    assert _amounts(s["declared_for_remittance"]) == [("TZS", "13000.0000")]
    assert _amounts(s["confirmed_by_company"]) == [("TZS", "10000.0000")]
    assert _amounts(s["unconfirmed_remittances"]) == [("TZS", "3000.0000")]
    assert _amounts(s["disputed_remittances"]) == [("TZS", "5000.0000")]
    held = {r["staff_member_id"]: r for r in s["held_by_employee"]}
    assert held[a]["outstanding"] == "40000.0000" and held[b]["outstanding"] == "20000.0000"
    assert held[a]["staff_member_name"] == "Operator Zuberi" and held[a]["route"].endswith(f"{a}/accountability")
    assert _amounts(s["outstanding"]) == [("TZS", "60000.0000")]
    assert waiting["remittance_number"].startswith("RMT-")

    with get_sessionmaker().begin() as session:
        from asseta.core.db import DbScope, apply_scope

        apply_scope(session, DbScope.TENANT, uuid.UUID(f.tid), None)
        ctx = RequestContext(uuid.UUID(int=0), "test", DbScope.TENANT, uuid.UUID(f.tid), frozenset(), frozenset())
        custody = CashCustodyService(session, ctx, api.clock.now)
        bulk = {(b.staff_member_id, b.currency): b for b in all_custody_balances(session, api.clock.now)}
        for staff in (uuid.UUID(a), uuid.UUID(b)):
            for one in custody.balances(staff):
                total = bulk[(staff, one.currency)]
                assert total.outstanding == one.outstanding
                assert total.in_transit_out == one.in_transit_out
                assert total.claimed_unverified_handovers == one.claimed_unverified_handovers


def test_exceptions_section_separates_shortages_and_overages_and_unions_pending(api: Api) -> None:
    f = setup_finance(api, "Exception View", "EV-1")
    a = _operator(f)
    _collect(api, f, a, "90000")
    short = _remit(api, f, a, "10000")
    _ok(f.accountant.post(f"{C}/handovers/{short['id']}/decision", {"verified": True, "amount_received": "9000"}))
    over = _remit(api, f, a, "10000")
    _ok(f.accountant.post(f"{C}/handovers/{over['id']}/decision", {"verified": True, "amount_received": "10500"}))
    bought = purchase(api, f.owner, f, "5", pay="425000")
    verify(f.accountant, bought["payment"]["id"])
    _ok(
        f.manager.post(f"{T}/hours-purchases/{bought['id']}/cancellation", {"reason": "Customer changed plans"}),
        201,
    )
    _ok(f.manager.post(f"{C}/retentions", {"staff_member_id": a, "amount": "100", "reason": "Float for fuel"}), 201)

    summary = _summary(f.owner)
    s = summary["exceptions_section"]
    assert _amounts(s["shortages"]) == [("TZS", "1000.0000")] and "direction=SHORTAGE" in s["shortages"]["route"]
    assert _amounts(s["overages"]) == [("TZS", "500.0000")]
    assert _amounts(s["shortages_opened_in_period"]) == [("TZS", "1000.0000")]
    kinds = {k["kind"]: k for k in s["pending_adjustments"]["by_kind"]}
    assert kinds["hours_cancellations"]["count"] == 1 and s["pending_adjustments"]["total"] == 1
    approvals = {k["kind"]: k["count"] for k in s["outstanding_approvals"]["by_kind"]}
    assert approvals["cash_retentions"] == 1 and approvals["payments_to_verify"] == 1  # the collection
    assert summary["outstanding_approvals"]["hours_cancellations"] == 1
    assert s["outstanding_approvals"]["total"] == summary["outstanding_approvals"]["total"]
    sources = {r["source"]: r for r in s["unresolved_variances"]["by_source"]}
    assert sum(r["count"] for r in sources.values()) == s["unresolved_variances"]["total"] == 2

    listed = _ok(f.owner.get(f"{T}/accountability/pending-adjustments"))
    assert listed["total"] == 1 and listed["items"][0]["record_type"] == "hours_cancellation"
    assert listed["items"][0]["requested_by_name"] and listed["items"][0]["route"].startswith(
        "/tenant/hours/cancellations/"
    )
    everything = _ok(f.owner.get(f"{T}/accountability/pending-adjustments", all_approvals=True))
    assert {"hours_cancellation", "cash_retention", "customer_payment"} <= {
        i["record_type"] for i in everything["items"]
    }
    assert _ok(f.owner.get(f"{C}/variances", direction="OVERAGE"))["total"] == 1


@contextmanager
def _statements(engine: Engine) -> Iterator[list[str]]:
    seen: list[str] = []

    def count(_c: Any, _cur: Any, statement: str, *_: Any) -> None:
        seen.append(statement)

    event.listen(engine, "before_cursor_execute", count)
    try:
        yield seen
    finally:
        event.remove(engine, "before_cursor_execute", count)


def test_summary_queries_do_not_grow_with_the_data(api: Api) -> None:
    f = setup_finance(api, "Scale Co", "SC-1")
    engine = get_sessionmaker().kw["bind"]
    purchase(api, f.manager, f, "1")
    _collect(api, f, _operator(f, "First Custodian"), "1000")
    with _statements(engine) as small:
        _summary(f.owner)
    for i in range(4):
        customer = _ok(f.owner.post(f"{T}/customers", {"code": f"S{i}", "name": f"Scale Customer {i}"}), 201)["id"]
        purchase(api, f.manager, f, "1", customer_id=customer)
        _collect(api, f, _operator(f, f"Custodian {i}"), "1000")
    with _statements(engine) as large:
        _summary(f.owner)
    assert len(large) == len(small)


# --- employee view ------------------------------------------------------------------------------------------------
def test_employee_view_shows_cash_history_and_decisions(api: Api) -> None:
    f = setup_finance(api, "Employee View", "EM-1")
    staff = f.sup_staff_id
    collected = _collect(api, f, staff, "50000")
    remitted = _remit(api, f, staff, "20000")
    _ok(f.owner.post(f"{C}/retentions", {"staff_member_id": staff, "amount": "100", "reason": "Float for fuel"}), 201)
    f.supervisor.get(f"{T}/lookup", reference="x")  # the login exists once it has been used
    gid = api.idp.groups[f"/tenants/{f.tid}/supervisor"]
    api.idp.users[f.supervisor.subject] = "sup@fin.example.com"
    api.idp.add_user_to_group(f.supervisor.subject, gid)
    _sync(api)
    view = _ok(f.owner.get(f"{T}/employees/{staff}/accountability"))
    assert view["identity"]["full_name"] == "Cash Supervisor" and view["identity"]["roles"] == ["supervisor"]
    assert [b["outstanding"] for b in view["cash_held"]] == ["50000.0000"]
    row = view["collections"][0]
    assert row["id"] == collected["id"] and row["reference"].startswith("COL-")
    assert row["route"] == f"/tenant/customer-payments/{collected['id']}"
    assert view["remittances"][0]["id"] == remitted["id"] and view["retentions"][0]["reference"].startswith("RET-")
    assert view["scorecard_visible"] is False and view["truncated"] == []

    _ok(f.accountant.post(f"{C}/handovers/{remitted['id']}/decision", {"verified": True, "amount_received": "20000"}))
    decider = _ok(
        f.owner.post(
            f"{T}/staff",
            {"full_name": "Fatuma Cashier", "kind": "SUPERVISOR", "keycloak_subject": f.accountant.subject},
        ),
        201,
    )
    made = _ok(f.owner.get(f"{T}/employees/{decider['id']}/accountability"))["approvals_made"]
    assert [(r["record_type"], r["id"], r["status"]) for r in made] == [("cash_handover", remitted["id"], "VERIFIED")]
    assert made[0]["route"] == f"/tenant/finance/cash/remittances/{remitted['id']}"


def test_employee_view_is_permission_gated_and_period_filtered(api: Api) -> None:
    f = setup_finance(api, "Employee Gate", "EG-1")
    staff = f.sup_staff_id
    _collect(api, f, staff, "50000")
    url = f"{T}/employees/{staff}/accountability"
    assert f.supervisor.get(url).status_code == 403
    assert f.accountant.get(url).status_code == 200
    assert _ok(f.manager.get(url))["identity"]["staff_member_id"] == staff
    earlier = (api.clock.now - timedelta(days=30)).date().isoformat()
    old = _ok(f.owner.get(url, date_from=earlier, date_to=earlier))
    assert old["collections"] == [] and old["cash_held"][0]["outstanding"] == "50000.0000"  # held is the position now
    assert f.owner.get(f"{T}/employees/{uuid.uuid4()}/accountability").status_code == 404


# --- lookup -------------------------------------------------------------------------------------------------------
def _lookup(actor: Actor, reference: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = _ok(actor.get(f"{T}/lookup", reference=reference))["matches"]
    return result


def test_lookup_resolves_numbers_and_ids_across_types(api: Api) -> None:
    f = setup_finance(api, "Lookup Co", "LK-1")
    bought = purchase(api, f.manager, f, "6")
    number = bought["purchase_number"]
    hit = _lookup(f.owner, number)
    assert [(m["record_type"], m["id"]) for m in hit] == [("hours_purchase", bought["id"])]
    assert hit[0]["route"] == f"/tenant/hours/purchases/{bought['id']}"
    assert hit[0]["balance_outstanding"] == hit[0]["amount"] and hit[0]["recorded_by_name"]
    assert _lookup(f.owner, number.lower())[0]["id"] == bought["id"]

    staff = _operator(f)
    collection = _collect(api, f, staff, "9000")
    remittance = _remit(api, f, staff, "4000")
    now = api.clock.now.isoformat()
    other = _operator(f, "Operator Other")
    moved = _ok(
        f.manager.post(
            f"{C}/transfers", {"from_staff_id": staff, "to_staff_id": other, "amount": "100", "transferred_at": now}
        ),
        201,
    )
    retained = _ok(
        f.manager.post(f"{C}/retentions", {"staff_member_id": staff, "amount": "50", "reason": "Fuel float"}), 201
    )
    for record_type, record, field in (
        ("customer_payment", collection, "collection_number"),
        ("cash_handover", remittance, "remittance_number"),
        ("cash_transfer", moved, "transfer_number"),
        ("cash_retention", retained, "retention_number"),
    ):
        found = _lookup(f.owner, record[field])
        assert [(m["record_type"], m["id"]) for m in found] == [(record_type, record["id"])]
        assert _lookup(f.owner, record["id"])[0]["record_type"] == record_type
    assert _lookup(f.owner, remittance["remittance_number"])[0]["balance_outstanding"] == "4000.0000"
    job = _ok(f.owner.get(f"{T}/jobs/{f.c.job_id}"))["job"]
    assert _lookup(f.owner, job["job_number"])[0]["record_type"] == "job"
    assert _lookup(f.owner, "NO-SUCH-NUMBER") == []
    assert f.supervisor.get(f"{T}/lookup", reference=number).status_code == 403


# --- isolation ----------------------------------------------------------------------------------------------------
def test_tenant_isolation_sweep(api: Api) -> None:
    a = setup_finance(api, "Tenant A", "TA-1")
    b = api.onboard("Tenant B", price="1")["owner"]
    staff = _operator(a)
    collection = _collect(api, a, staff, "7000")
    bought = purchase(api, a.manager, a, "2")
    assert b.get(f"{T}/employees/{staff}/accountability").status_code == 404
    for reference in (
        collection["collection_number"],
        collection["id"],
        bought["purchase_number"],
        bought["id"],
    ):
        assert _lookup(a.owner, reference) != []
        assert _lookup(b, reference) == [], reference
    other = _summary(b)
    assert other["cash_section"]["held_by_employee"] == [] and other["hours_section"]["purchased"]["count"] == 0
    assert other["exceptions_section"]["outstanding_approvals"]["total"] == 0
    assert _ok(b.get(f"{T}/accountability/pending-adjustments", all_approvals=True))["total"] == 0


# --- smaller additions --------------------------------------------------------------------------------------------
def test_lists_search_human_numbers(api: Api) -> None:
    f = setup_finance(api, "Search Co", "SR-1")
    staff, other = _operator(f), _operator(f, "Operator Other")
    collection = _collect(api, f, staff, "9000")
    remittance = _remit(api, f, staff, "4000")
    now = api.clock.now.isoformat()
    moved = _ok(
        f.manager.post(
            f"{C}/transfers", {"from_staff_id": staff, "to_staff_id": other, "amount": "100", "transferred_at": now}
        ),
        201,
    )
    retained = _ok(
        f.manager.post(f"{C}/retentions", {"staff_member_id": staff, "amount": "50", "reason": "Fuel float"}), 201
    )
    for path, number in (
        (f"{T}/customer-payments", collection["collection_number"]),
        (f"{C}/handovers", remittance["remittance_number"]),
        (f"{C}/transfers", moved["transfer_number"]),
        (f"{C}/retentions", retained["retention_number"]),
    ):
        assert _ok(f.owner.get(path, q=number[-9:]))["total"] == 1, path
        assert _ok(f.owner.get(path, q="ZZZ-NOTHING"))["total"] == 0, path


def test_remittance_filter_for_pending_partial_reason(api: Api) -> None:
    f = setup_finance(api, "Partial Co", "PR-1")
    cash_policy(f, remit_full_balance=True)
    staff = _operator(f)
    _collect(api, f, staff, "9000")
    remittance = _remit(api, f, staff, "4000")
    assert [h["id"] for h in _ok(f.owner.get(f"{C}/handovers", partial_reason_pending=True))["items"]] == [
        remittance["id"]
    ]
    assert _ok(f.owner.get(f"{C}/handovers", partial_reason_pending=False))["total"] == 0


def test_evidence_upload_open_to_variance_handlers(api: Api) -> None:
    f = setup_finance(api, "Evidence Co", "EU-1")
    files = {"file": ("e.jpg", unique_jpeg(), "image/jpeg")}
    r = api.client.post(
        f"{T}/attachments",
        files=files,
        data={"purpose": "ADJUSTMENT_EVIDENCE"},
        headers=f.accountant.headers(True, None),
    )
    assert r.status_code == 201, r.text


def test_credit_update_accepts_evidence(api: Api) -> None:
    f = setup_finance(api, "Credit Co", "CR-1")
    today = api.clock.now.date().isoformat()
    body = {"limit_amount": "1000", "effective_from": today, "reason": "Long-standing customer"}
    made = _ok(f.manager.post(f"{T}/credit-arrangements", {**body, "customer_id": f.customer_id}), 201)
    files = {"file": ("e.jpg", unique_jpeg(), "image/jpeg")}
    attachment = api.client.post(
        f"{T}/attachments", files=files, data={"purpose": "ADJUSTMENT_EVIDENCE"}, headers=f.manager.headers(True, None)
    ).json()["id"]
    update = {**body, "version": made["version"], "evidence_attachment_ids": [attachment]}
    assert _ok(f.manager.put(f"{T}/credit-arrangements/{made['id']}", update))["evidence_attachment_ids"] == [
        attachment
    ]
    bad = {**body, "version": made["version"] + 1, "evidence_attachment_ids": [str(uuid.uuid4())]}
    assert f.manager.put(f"{T}/credit-arrangements/{made['id']}", bad).status_code == 404


def test_sync_offers_open_invoices_to_collection_recorders(api: Api) -> None:
    from tests.support.finance import complete_job, issue_invoice

    f = setup_finance(api, "Invoice Sync", "IS-1")
    complete_job(api, f, f.c.job_id, "500.0", "508.0", 9)
    invoice = issue_invoice(f, [f.c.job_id])
    device = {"device_id": "android-open-invoices", "platform": "ANDROID", "app_version": "1.0.0"}
    headers = {**f.supervisor.headers(True, None), "X-Device-Id": device["device_id"]}
    _ok(api.client.post("/api/v1/sync/devices", headers=headers, json=device), 201)
    boot = _ok(api.client.get("/api/v1/sync/bootstrap", headers=headers))
    assert "SYNC_OPEN_INVOICES" in boot["capabilities"]
    open_invoices = boot["data"]["open_invoices"]
    assert [(i["id"], i["balance"]) for i in open_invoices] == [(invoice["id"], invoice["balance"])]


def test_unapproved_changeover_job_is_flagged_with_its_age(api: Api) -> None:
    from tests.support.notify import sql

    f = setup_finance(api, "Changeover Co", "CO-1")
    next_job = _ok(
        f.owner.post(
            f"{T}/jobs",
            {
                "contract_id": f.c.contract_id,
                "job_number": "J-NEXT-1",
                "machine_id": f.c.t.machine_id,
                "planned_start": api.clock.now.isoformat(),
            },
        ),
        201,
    )["id"]
    _ok(f.owner.post(f"{T}/jobs/{next_job}/transitions", {"action": "SUBMIT"}))
    capture_id = uuid.uuid4()
    three_days_ago: datetime = api.clock.now - timedelta(days=3)
    body = capture(f.c.job_id, "OPENING", "50", three_days_ago, mode="MANUAL", capture_id=str(capture_id))
    api.clock.set_at(three_days_ago)
    assert f.owner.post(f"{T}/meter-captures", body).status_code in (200, 201)
    api.clock.set_at(three_days_ago + timedelta(days=3))
    sql(
        "INSERT INTO machine_changeover (id, tenant_id, machine_id, capture_id, job_id, from_customer_id, to_customer_id,"
        " to_job_id, created_at) VALUES (gen_random_uuid(), :t, :m, :c, :j, :cu, :cu, :n, :at)",
        t=f.tid,
        m=f.c.t.machine_id,
        c=capture_id,
        j=f.c.job_id,
        cu=f.customer_id,
        n=next_job,
        at=three_days_ago,
    )
    flag = _summary(f.owner)["exceptions_section"]["changeover_jobs_awaiting_approval"]
    assert flag["count"] == 1 and flag["oldest_days"] == 3 and flag["items"][0]["job_id"] == next_job
    assert flag["items"][0]["job_number"] == "J-NEXT-1" and flag["items"][0]["customer_name"]


def test_administrator_manages_access_but_not_accountability(api: Api) -> None:
    f = setup_finance(api, "Admin Co", "AD-1")
    admin = role(api, f.tid, "administrator", "admin-AD-1")
    assert admin.get(f"{T}/access/members").status_code == 200
    assert admin.get(f"{T}/accountability/summary").status_code == 403
