"""Records that open by their own id, and the variance list filters the dashboard figures link to (guideline 8, 10)."""

from datetime import timedelta
from typing import Any
from urllib.parse import parse_qs, urlparse

from tests.support.api import Actor, Api
from tests.support.finance import FinCtx, category, expense_policy, role, setup_finance, tenant_sql
from tests.support.intelligence import expense
from tests.support.jobs import capture

T = "/api/v1/tenant"
C = f"{T}/cash"


def _ok(r: Any, status: int = 200) -> Any:
    assert r.status_code == status, r.text
    return r.json()


def _remittance_difference(api: Api, f: FinCtx, staff: str, declared: str, received: str) -> str:
    """A collection handed over and received at another amount: returns the variance id it opened."""
    at = api.clock.now.isoformat()
    _ok(
        f.manager.post(
            f"{C}/collections",
            {"customer_id": f.customer_id, "amount": declared, "received_at": at, "staff_member_id": staff},
        ),
        201,
    )
    handover = _ok(
        f.manager.post(
            f"{C}/handovers",
            {"staff_member_id": staff, "amount": declared, "handed_at": at, "partial_reason": "Bank closed early"},
        ),
        201,
    )
    _ok(f.accountant.post(f"{C}/handovers/{handover['id']}/decision", {"verified": True, "amount_received": received}))
    rows = _ok(f.owner.get(f"{C}/variances", staff_member_id=staff))["items"]
    return str(next(v["id"] for v in rows if v["source_id"] == handover["id"]))


def _ids(actor: Actor, **query: Any) -> set[str]:
    return {v["id"] for v in _ok(actor.get(f"{C}/variances", **query))["items"]}


def test_variances_filter_by_opening_day_and_open_state_and_the_dashboard_links_say_so(api: Api) -> None:
    f = setup_finance(api, "Variance Period", "VP-1")
    staff = _ok(f.owner.post(f"{T}/staff", {"full_name": "Operator Rashidi", "kind": "OPERATOR"}), 201)["id"]
    first_day = api.clock.now
    old = _remittance_difference(api, f, staff, "10000", "9000")
    api.clock.set_at(first_day + timedelta(days=3))
    third_day = api.clock.now.date().isoformat()
    recent = _remittance_difference(api, f, staff, "10000", "9500")
    over = _remittance_difference(api, f, staff, "10000", "10200")

    assert _ids(f.owner, date_from=third_day, date_to=third_day) == {recent, over}
    assert _ids(f.owner, date_to=first_day.date().isoformat()) == {old}
    assert _ids(f.owner, direction="SHORTAGE", date_from=third_day) == {recent}
    backwards = f.owner.get(f"{C}/variances", date_from=third_day, date_to=first_day.date().isoformat())
    assert backwards.status_code == 422 and backwards.json()["error"]["code"] == "INVALID_PERIOD"

    closed = {"outcome": "CORRECTED_ERROR", "note": "Counting slip found on the deposit slip"}
    _ok(f.owner.post(f"{C}/variances/{old}/resolution", closed))
    _ok(f.accountant2.post(f"{C}/variances/{old}/closure-decision", {"approve": True, "note": "Slip seen"}))
    assert _ids(f.owner, open_only=True) == {recent, over}
    assert _ids(f.owner) == {old, recent, over}

    period = {"date_from": third_day, "date_to": third_day}
    section = _ok(f.owner.get(f"{T}/accountability/summary", **period))["exceptions_section"]
    opened = parse_qs(urlparse(section["shortages_opened_in_period"]["route"]).query)
    assert opened == {"direction": ["SHORTAGE"], "date_from": [third_day], "date_to": [third_day]}
    assert section["shortages_opened_in_period"]["count"] == 1
    position = parse_qs(urlparse(section["shortages"]["route"]).query)
    assert position == {"direction": ["SHORTAGE"], "open_only": ["true"]}
    # Following each link lists exactly the records the figure counted.
    assert _ids(f.owner, **{k: v[0] for k, v in opened.items()}) == {recent}
    assert _ids(f.owner, **{k: v[0] for k, v in position.items()}) == {recent}
    listed = {s["source"]: s["route"] for s in section["unresolved_variances"]["by_source"]}
    assert all("open_only=true" in route for route in listed.values())


def test_direction_lists_money_only_like_the_figures(api: Api) -> None:
    f = setup_finance(api, "Variance Unit", "VU-1")
    staff = _ok(f.owner.post(f"{T}/staff", {"full_name": "Operator Asha", "kind": "OPERATOR"}), 201)["id"]
    money = _remittance_difference(api, f, staff, "10000", "9000")
    tenant_sql(
        f.tid,
        "INSERT INTO cash_variance (id, tenant_id, source_type, source_id, currency, declared_amount, received_amount,"
        " amount, opened_at, status, unit, evidence_attachment_ids) VALUES (gen_random_uuid(), :t, 'CUSTOMER_HOUR', gen_random_uuid(), 'TZS',"
        " 5, 0, 5, now(), 'OPEN', 'HOURS', '{}') RETURNING id",
        t=f.tid,
    )
    assert len(_ids(f.owner)) == 2
    assert _ids(f.owner, direction="SHORTAGE") == {money}


def _capture_job(api: Api, f: FinCtx) -> tuple[str, str]:
    """A job with an accepted opening reading; returns (job id, capture id)."""
    body = capture(f.c.job_id, "OPENING", "500.0", api.clock.now, mode="MANUAL")
    _ok(f.owner.post(f"{T}/meter-captures", body), 201)
    return f.c.job_id, str(body["id"])


def _reset(api: Api, f: FinCtx) -> str:
    body = {
        "machine_id": f.c.t.machine_id,
        "old_reading": "600.0",
        "new_reading": "1.0",
        "effective_at": api.clock.now.isoformat(),
        "reason": "Instrument cluster replaced after fault",
    }
    return str(_ok(f.owner.post(f"{T}/meter-resets", body), 201)["id"])


def test_each_record_opens_by_its_own_id(api: Api) -> None:
    f = setup_finance(api, "By Id", "BYID-1")
    _, capture_id = _capture_job(api, f)
    assert _ok(f.owner.get(f"{T}/meter-captures/{capture_id}"))["reading"].startswith("500")
    reset_id = _reset(api, f)
    assert _ok(f.owner.get(f"{T}/meter-resets/{reset_id}"))["status"] == "PENDING"
    assert f.supervisor.get(f"{T}/security-events").status_code == 403
    event = _ok(f.owner.get(f"{T}/security-events"))["items"][0]
    got = _ok(f.owner.get(f"{T}/security-events/{event['id']}"))
    assert got == event

    expense_policy(f, receipt_required_above="100000000", gps_required=False, auto_approve_limit="0")
    created = expense(api, f.supervisor, category(f, "FUEL", "Fuel"), "50000")
    approval = _ok(f.owner.get(f"{T}/approvals", status="PENDING"))["items"][0]
    assert approval["subject_id"] == created["id"]
    assert _ok(f.owner.get(f"{T}/approvals/{approval['id']}"))["id"] == approval["id"]

    missing = "00000000-0000-4000-8000-000000000001"
    for path in ("meter-captures", "meter-resets", "security-events", "approvals", "exceptions", "alerts"):
        assert f.owner.get(f"{T}/{path}/{missing}").status_code == 404, path


def test_exception_opens_by_id_with_the_field_rule(api: Api) -> None:
    f = setup_finance(api, "By Id Findings", "BYID-2")
    body = capture(f.c.job_id, "OPENING", "500.0", api.clock.now, mode="MANUAL", gps={"status": "NO_FIX"})
    _ok(f.owner.post(f"{T}/meter-captures", body), 201)
    [listed] = _ok(f.owner.get(f"{T}/exceptions"))["items"]
    assert _ok(f.owner.get(f"{T}/exceptions/{listed['id']}")) == listed
    assert f.supervisor.get(f"{T}/exceptions/{listed['id']}").status_code == 200  # the job's own supervisor
    stranger = role(api, f.tid, "supervisor", "stranger-BYID-2")
    _ok(
        f.owner.post(
            f"{T}/staff", {"full_name": "Other Supervisor", "kind": "SUPERVISOR", "keycloak_subject": stranger.subject}
        ),
        201,
    )
    assert stranger.get(f"{T}/exceptions/{listed['id']}").status_code == 404


def test_field_users_open_only_their_own_records_by_id(api: Api) -> None:
    f = setup_finance(api, "By Id Field", "BYID-3")
    _, capture_id = _capture_job(api, f)
    reset_id = _reset(api, f)
    stranger = role(api, f.tid, "supervisor", "stranger-BYID-3")
    _ok(
        f.owner.post(
            f"{T}/staff", {"full_name": "Other Supervisor", "kind": "SUPERVISOR", "keycloak_subject": stranger.subject}
        ),
        201,
    )
    assert stranger.get(f"{T}/meter-captures/{capture_id}").status_code == 404
    assert stranger.get(f"{T}/meter-resets/{reset_id}").status_code == 404
    # The assigned supervisor is not a stranger to this machine's records.
    assert f.supervisor.get(f"{T}/meter-resets/{reset_id}").status_code == 200
    assert f.supervisor.get(f"{T}/meter-captures/{capture_id}").status_code == 200
