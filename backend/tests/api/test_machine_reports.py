"""ADR-008 §2: machine reports. A supervisor accounts for every engine hour of a machine assigned to them, from the
last approved reading to a new one, split across customers (from the hours they bought) and non-productive reasons;
someone else approves. Every rule the server enforces, online and offline."""

import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.exc import DBAPIError

from asseta.modules.machine_reports.reasons import DEFAULT_REASONS
from tests.support.api import Api
from tests.support.finance import role, tenant_sql
from tests.support.hours import hours_policy
from tests.support.machine_reports import (
    ReportCtx,
    T,
    baseline,
    bought,
    code,
    cust,
    customer,
    idle,
    later,
    ok,
    opening_body,
    reading,
    report_body,
    second_machine,
    setup_reports,
    submit,
)
from tests.support.meter import fix
from tests.support.notify import drain, member, sql
from tests.support.telemetry import DAR

DEVICE = "android-machine-report-01"


def _available(ctx: ReportCtx, customer_id: str, machine_id: str | None = None) -> Decimal:
    rows = ok(
        ctx.f.supervisor.get(
            f"{T}/machine-reports/available-hours", machine_id=machine_id or ctx.machine_id, customer_id=customer_id
        )
    )
    return Decimal(rows[0]["available"]) if rows else Decimal(0)


# --- the split ---------------------------------------------------------------------------------------------------
def test_lines_must_add_up_to_the_meter_difference(api: Api) -> None:
    ctx = setup_reports(api)
    f, m = ctx.f, ctx.machine_id
    bought(api, f, 10)
    at = later(api, 6)
    r = f.supervisor.post(
        f"{T}/machine-reports", report_body(m, "1005.0", at, [cust(f.customer_id, 3), idle(ctx.reasons["TRANSIT"], 1)])
    )
    assert r.status_code == 422 and code(r) == "REPORT_SUM_MISMATCH", r.text
    assert "4.0" in r.json()["error"]["message"] or "4" in r.json()["error"]["message"]
    r = f.supervisor.post(
        f"{T}/machine-reports",
        report_body(m, "1005.0", at, [cust(f.customer_id, "4.255"), idle(ctx.reasons["TRANSIT"], "0.745")]),
    )
    assert r.status_code == 422 and code(r) == "HOURS_PRECISION", r.text
    assert "at most 2 decimals" in r.json()["error"]["message"]
    # Nothing was kept from the refused reports (not even the reading).
    assert tenant_sql(f.tid, "SELECT count(*) FROM meter_capture WHERE kind = 'DAILY'")[0][0] == 0

    rep = submit(f.supervisor, report_body(m, "1005.0", at, [cust(f.customer_id, 4), idle(ctx.reasons["TRANSIT"], 1)]))
    assert rep["status"] == "SUBMITTED" and rep["report_number"].startswith("MR-2026-")
    assert Decimal(rep["start_reading"]) == 1000 and Decimal(rep["end_reading"]) == 1005
    assert Decimal(rep["hours"]) == 5 and Decimal(rep["customer_hours"]) == 4
    assert Decimal(rep["non_productive_hours"]) == 1 and rep["start_source"] == "BASELINE"
    assert rep["lines"][1]["reason_name"] == "Transit between sites"
    assert rep["machine_name"] and rep["submitted_by_name"] is not None


def test_a_reading_not_above_the_last_approved_one_is_refused(api: Api) -> None:
    ctx = setup_reports(api)
    f, m = ctx.f, ctx.machine_id
    at = later(api, 1)
    r = f.supervisor.post(f"{T}/machine-reports", report_body(m, "1000.0", at, [idle(ctx.reasons["IDLE_ON_SITE"], 1)]))
    assert code(r) == "NOTHING_TO_REPORT", r.text
    r = f.supervisor.post(f"{T}/machine-reports", report_body(m, "999.0", at, [idle(ctx.reasons["IDLE_ON_SITE"], 1)]))
    assert code(r) == "READING_NOT_HIGHER", r.text
    note_missing = idle(ctx.reasons["IDLE_ON_SITE"], 1)
    note_missing.pop("note")
    r = f.supervisor.post(f"{T}/machine-reports", report_body(m, "1001.0", at, [note_missing]))
    assert r.status_code == 422 and code(r) == "VALIDATION_FAILED", r.text


def _bare_machine(api: Api, ctx: ReportCtx) -> str:
    """A machine assigned to the supervisor with no approved report, baseline or reset (no starting reading)."""
    f = ctx.f
    [bare] = api.add_machines(f.owner, 1, prefix="BARE")
    ok(
        f.owner.post(
            f"{T}/machines/{bare}/assignments",
            {"staff_member_id": f.sup_staff_id, "role": "SUPERVISOR", "effective_from": api.clock.now.isoformat()},
        ),
        201,
    )
    return str(bare)


def test_a_machine_without_a_starting_reading_needs_an_opening_report_first(api: Api) -> None:
    ctx = setup_reports(api)
    f = ctx.f
    bare = _bare_machine(api, ctx)
    context = ok(f.supervisor.get(f"{T}/machine-reports/context/{bare}"))
    assert context["previous_reading"] is None and context["opening_required"] is True
    status = next(s for s in ok(f.supervisor.get(f"{T}/machine-reports/status")) if s["machine_id"] == bare)
    assert status["opening_required"] is True
    at = later(api, 1)
    r = f.supervisor.post(f"{T}/machine-reports", report_body(bare, "10", at, [idle(ctx.reasons["TRANSIT"], 10)]))
    assert r.status_code == 422 and code(r) == "OPENING_REPORT_REQUIRED", r.text
    # An opening report carries no lines; a normal report needs at least one.
    r = f.supervisor.post(f"{T}/machine-reports", opening_body(bare, "10", at, lines=[idle(ctx.reasons["TRANSIT"], 1)]))
    assert r.status_code == 422 and code(r) == "VALIDATION_FAILED", r.text
    r = f.supervisor.post(f"{T}/machine-reports", report_body(bare, "10", at, []))
    assert r.status_code == 422 and code(r) == "VALIDATION_FAILED", r.text

    opening = submit(f.supervisor, opening_body(bare, "10", at))
    assert opening["opening"] is True and opening["status"] == "SUBMITTED" and opening["start_source"] == "OPENING"
    assert Decimal(opening["hours"]) == 0 and opening["lines"] == []
    assert Decimal(opening["start_reading"]) == Decimal(opening["end_reading"]) == 10
    # `submitted_by` is the caller's app user id, the one /me returns.
    assert opening["submitted_by"] == ok(f.supervisor.get("/api/v1/me"))["user_id"]
    done = ok(f.manager.post(f"{T}/machine-reports/{opening['id']}/approve", {}))
    assert done["status"] == "APPROVED" and Decimal(done["customer_hours"]) == 0
    context = ok(f.supervisor.get(f"{T}/machine-reports/context/{bare}"))
    assert Decimal(context["previous_reading"]) == 10 and context["opening_required"] is False
    assert context["previous_source"] == "REPORT"

    # Now the machine starts from 10: a second opening report is refused; a normal one reports the difference.
    at = later(api, 3)
    r = f.supervisor.post(f"{T}/machine-reports", opening_body(bare, "13", at))
    assert code(r) == "OPENING_NOT_ALLOWED", r.text
    normal = submit(f.supervisor, report_body(bare, "13", at, [idle(ctx.reasons["TRANSIT"], 3)]))
    assert normal["opening"] is False and Decimal(normal["start_reading"]) == 10 and Decimal(normal["hours"]) == 3


def test_the_phone_sends_the_reading_first_then_the_report_naming_it(api: Api) -> None:
    """The phones' two-step contract over REST: a DAILY reading (POST /meter-captures), then the report with
    `capture_id` (opening report with no lines; later a normal report with lines)."""
    ctx = setup_reports(api)
    f = ctx.f
    bare = _bare_machine(api, ctx)
    at = later(api, 1)
    first = reading(bare, "250", at)
    assert ok(f.supervisor.post(f"{T}/meter-captures", first), 201)["capture"]["state"] == "ACCEPTED"
    body = {"id": str(uuid.uuid4()), "machine_id": bare, "capture_id": first["id"], "opening": True, "lines": []}
    opening = submit(f.supervisor, body)
    assert opening["capture_id"] == first["id"] and opening["opening"] is True
    ok(f.manager.post(f"{T}/machine-reports/{opening['id']}/approve", {}))

    at = later(api, 2)
    second = reading(bare, "252", at)
    ok(f.supervisor.post(f"{T}/meter-captures", second), 201)
    body = {
        "id": str(uuid.uuid4()),
        "machine_id": bare,
        "capture_id": second["id"],
        "lines": [idle(ctx.reasons["TRANSIT"], 2)],
    }
    normal = submit(f.supervisor, body)
    assert normal["opening"] is False and Decimal(normal["start_reading"]) == 250 and Decimal(normal["hours"]) == 2


def test_an_opening_report_is_not_approved_once_the_machine_got_a_start_meanwhile(api: Api) -> None:
    ctx = setup_reports(api)
    f = ctx.f
    bare = _bare_machine(api, ctx)
    opening = submit(f.supervisor, opening_body(bare, "40", later(api, 1)))
    baseline(api, f, bare, "35")
    r = f.manager.post(f"{T}/machine-reports/{opening['id']}/approve", {})
    assert r.status_code == 422 and code(r) == "REPORT_READINGS_CHANGED", r.text
    assert ok(f.manager.post(f"{T}/machine-reports/{opening['id']}/reject", {"reason": "Baseline set"}))["status"] == (
        "REJECTED"
    )


# --- available hours, reservations ------------------------------------------------------------------------------
def test_a_customer_cannot_be_given_more_than_their_available_hours(api: Api) -> None:
    ctx = setup_reports(api)
    f, m = ctx.f, ctx.machine_id
    bought(api, f, 3)
    at = later(api, 5)
    r = f.supervisor.post(f"{T}/machine-reports", report_body(m, "1005", at, [cust(f.customer_id, 5)]))
    assert r.status_code == 422 and code(r) == "HOURS_NOT_AVAILABLE", r.text
    assert "3" in r.json()["error"]["message"]
    other = customer(f, "C9", "No Hours Ltd")
    r = f.supervisor.post(
        f"{T}/machine-reports",
        report_body(m, "1005", at, [cust(other, 1), cust(f.customer_id, 3), idle(ctx.reasons["WEATHER"], 1)]),
    )
    assert code(r) == "HOURS_NOT_AVAILABLE", r.text
    rep = submit(f.supervisor, report_body(m, "1005", at, [cust(f.customer_id, 3), idle(ctx.reasons["WEATHER"], 2)]))
    assert rep["lines"][0]["available_hours"] is not None


def test_reservations_hold_hours_across_pending_reports_on_different_machines(api: Api) -> None:
    ctx = setup_reports(api)
    f = ctx.f
    m2 = second_machine(api, ctx)
    bought(api, f, 10)
    at = later(api, 6)
    submit(f.supervisor, report_body(ctx.machine_id, "1006", at, [cust(f.customer_id, 6)]))
    assert _available(ctx, f.customer_id) == 4
    ctx_rows = ok(f.supervisor.get(f"{T}/machine-reports/context/{m2}"))["customers"]
    assert [Decimal(c["reserved"]) for c in ctx_rows] == [6]
    r = f.supervisor.post(f"{T}/machine-reports", report_body(m2, "1005", at, [cust(f.customer_id, 5)]))
    assert code(r) == "HOURS_NOT_AVAILABLE", r.text
    submit(f.supervisor, report_body(m2, "1005", at, [cust(f.customer_id, 4), idle(ctx.reasons["SERVICING"], 1)]))
    assert _available(ctx, f.customer_id) == 0


def test_machine_scope_counts_only_the_hours_on_the_reported_machine(api: Api) -> None:
    from tests.support.hours import hours_policy

    ctx = setup_reports(api)
    f = ctx.f
    m2 = second_machine(api, ctx)
    bought(api, f, 10)  # the order names the first machine
    hours_policy(f, report_hours_scope="MACHINE")
    at = later(api, 2)
    r = f.supervisor.post(f"{T}/machine-reports", report_body(m2, "1002", at, [cust(f.customer_id, 2)]))
    assert code(r) == "HOURS_NOT_AVAILABLE", r.text
    submit(f.supervisor, report_body(ctx.machine_id, "1002", at, [cust(f.customer_id, 2)]))


def test_one_report_per_machine_waits_for_its_decision(api: Api) -> None:
    ctx = setup_reports(api)
    f, m = ctx.f, ctx.machine_id
    first = submit(f.supervisor, report_body(m, "1003", later(api, 3), [idle(ctx.reasons["IDLE_ON_SITE"], 3)]))
    r = f.supervisor.post(
        f"{T}/machine-reports", report_body(m, "1005", later(api, 2), [idle(ctx.reasons["IDLE_ON_SITE"], 5)])
    )
    assert code(r) == "REPORT_PENDING" and first["report_number"] in r.json()["error"]["message"], r.text
    status = ok(f.supervisor.get(f"{T}/machine-reports/status"))
    assert [s["pending_report_id"] for s in status] == [first["id"]]
    ok(f.manager.post(f"{T}/machine-reports/{first['id']}/approve", {}))
    nxt = submit(f.supervisor, report_body(m, "1005", api.clock.now, [idle(ctx.reasons["IDLE_ON_SITE"], 2)]))
    assert Decimal(nxt["start_reading"]) == 1003 and nxt["start_source"] == "REPORT"


def test_a_supervisor_reports_only_on_machines_assigned_to_them(api: Api) -> None:
    ctx = setup_reports(api)
    f = ctx.f
    other_staff = ok(f.owner.post(f"{T}/staff", {"full_name": "Other Supervisor", "kind": "SUPERVISOR"}), 201)["id"]
    m2 = second_machine(api, ctx, assign_to=other_staff)
    body = report_body(m2, "1002", later(api, 2), [idle(ctx.reasons["TRANSIT"], 2)])
    r = f.supervisor.post(f"{T}/machine-reports", body)
    assert r.status_code == 422 and code(r) == "MACHINE_NOT_ASSIGNED", r.text
    r = f.supervisor.get(f"{T}/machine-reports/context/{m2}")
    assert code(r) == "MACHINE_NOT_ASSIGNED"
    # The owner may report on any machine (web); someone else decides it.
    rep = submit(f.owner, body)
    assert rep["status"] == "SUBMITTED"
    # The supervisor sees neither the report nor the machine's status.
    assert ok(f.supervisor.get(f"{T}/machine-reports"))["total"] == 0
    assert f.supervisor.get(f"{T}/machine-reports/{rep['id']}").status_code == 404
    assert {s["machine_id"] for s in ok(f.supervisor.get(f"{T}/machine-reports/status"))} == {ctx.machine_id}


# --- decisions ---------------------------------------------------------------------------------------------------
def test_the_person_who_submitted_a_report_never_decides_it(api: Api) -> None:
    ctx = setup_reports(api)
    f, m = ctx.f, ctx.machine_id
    rep = submit(f.owner, report_body(m, "1002", later(api, 2), [idle(ctx.reasons["TRANSIT"], 2)]))
    r = f.owner.post(f"{T}/machine-reports/{rep['id']}/approve", {})
    assert r.status_code == 422 and code(r) == "SEGREGATION_OF_DUTIES", r.text
    r = f.owner.post(f"{T}/machine-reports/{rep['id']}/reject", {"reason": "Wrong split of hours"})
    assert code(r) == "SEGREGATION_OF_DUTIES", r.text
    assert f.supervisor.post(f"{T}/machine-reports/{rep['id']}/approve", {}).status_code == 403
    done = ok(f.manager.post(f"{T}/machine-reports/{rep['id']}/approve", {"note": "Matches the tracker"}))
    assert done["status"] == "APPROVED" and done["decided_by_name"] is not None
    r = f.manager.post(f"{T}/machine-reports/{rep['id']}/reject", {"reason": "Changed my mind"})
    assert code(r) == "REPORT_NOT_PENDING", r.text


def test_split_lines_take_hundredths_whatever_the_meter_precision(api: Api) -> None:
    """Customers' hours are kept with 2 decimals: a customer with 1.15 h gets exactly 1.15 h of a 1-decimal meter's
    difference (no 0.05 h stranded); the reading and the difference keep the meter's precision."""
    ctx = setup_reports(api)
    f, m = ctx.f, ctx.machine_id
    bought(api, f, 2)
    lines = [cust(f.customer_id, "0.85"), idle(ctx.reasons["TRANSIT"], "0.05")]
    rep = submit(f.supervisor, report_body(m, "1000.9", later(api, 1), lines))
    assert Decimal(rep["lines"][0]["hours"]) == Decimal("0.85") and Decimal(rep["hours"]) == Decimal("0.9")
    ok(f.manager.post(f"{T}/machine-reports/{rep['id']}/approve", {}))
    assert _available(ctx, f.customer_id) == Decimal("1.15")
    # The whole 1.15 h left go to the customer; the lines still add up to the difference exactly.
    at = later(api, 2)
    over = [cust(f.customer_id, "1.16"), idle(ctx.reasons["TRANSIT"], "0.84")]
    r = f.supervisor.post(f"{T}/machine-reports", report_body(m, "1002.9", at, over))
    assert code(r) == "HOURS_NOT_AVAILABLE", r.text
    short = [cust(f.customer_id, "1.15"), idle(ctx.reasons["TRANSIT"], "0.84")]
    assert code(f.supervisor.post(f"{T}/machine-reports", report_body(m, "1002.9", at, short))) == "REPORT_SUM_MISMATCH"
    exact = [cust(f.customer_id, "1.15"), idle(ctx.reasons["TRANSIT"], "0.85")]
    done = submit(f.supervisor, report_body(m, "1002.9", at, exact))
    assert Decimal(done["hours"]) == 2 and Decimal(done["customer_hours"]) == Decimal("1.15")


def test_a_rejected_report_is_final_and_a_new_report_needs_a_new_reading(api: Api) -> None:
    ctx = setup_reports(api)
    f, m = ctx.f, ctx.machine_id
    bought(api, f, 5)
    at = later(api, 4)
    first = submit(f.supervisor, report_body(m, "1004", at, [cust(f.customer_id, 4)]))
    assert _available(ctx, f.customer_id) == 1
    rejected = ok(f.manager.post(f"{T}/machine-reports/{first['id']}/reject", {"reason": "One hour was transit"}))
    assert rejected["status"] == "REJECTED" and rejected["decision_note"] == "One hour was transit"
    assert _available(ctx, f.customer_id) == 5
    status = ok(f.supervisor.get(f"{T}/machine-reports/status"))[0]
    assert status["rejected_report_id"] == first["id"] and status["pending_report_id"] is None

    # No correction: corrects_report_id is refused whatever it names, and the rejected report's reading is used.
    lines = [cust(f.customer_id, 3), idle(ctx.reasons["TRANSIT"], 1, "Moved to the second site")]
    again = report_body(m, None, None, lines, capture_id=first["capture_id"], corrects_report_id=first["id"])
    r = f.supervisor.post(f"{T}/machine-reports", again)
    assert r.status_code == 422 and code(r) == "CORRECTION_NOT_ALLOWED", r.text
    assert r.json()["error"]["message"] == "A rejected report can't be corrected; send a new report with a new reading."
    new_lines = [cust(f.customer_id, 3), idle(ctx.reasons["TRANSIT"], 2)]
    fresh = report_body(m, "1005", later(api, 1), new_lines, corrects_report_id=first["id"])
    assert code(f.supervisor.post(f"{T}/machine-reports", fresh)) == "CORRECTION_NOT_ALLOWED"
    r = f.supervisor.post(f"{T}/machine-reports", report_body(m, None, None, lines, capture_id=first["capture_id"]))
    assert r.status_code == 422 and code(r) == "CAPTURE_ALREADY_USED", r.text
    # The rejected report stays as it was (a record).
    kept = ok(f.supervisor.get(f"{T}/machine-reports/{first['id']}"))
    assert kept["status"] == "REJECTED" and kept["corrected_by_id"] is None and len(kept["lines"]) == 1

    # A brand-new report with a new reading, from the last APPROVED reading (the baseline).
    new = submit(f.supervisor, report_body(m, "1005", later(api, 1), new_lines))
    assert new["corrects_id"] is None and new["capture_id"] != first["capture_id"]
    assert Decimal(new["start_reading"]) == 1000 and Decimal(new["hours"]) == 5
    ok(f.manager.post(f"{T}/machine-reports/{new['id']}/approve", {}))
    r = f.manager.post(f"{T}/machine-reports", report_body(m, None, None, lines, capture_id=new["capture_id"]))
    assert code(r) == "CAPTURE_ALREADY_USED"


def _yard(f: Any) -> None:
    """The company's yard: a job site with a site-boundary geofence around DAR (about 1 km each way)."""
    centre = {"type": "Point", "coordinates": [DAR[1], DAR[0]]}
    site = ok(f.owner.post(f"{T}/job-sites", {"code": "YARD", "name": "Kigamboni yard", "center": centre}), 201)
    corners = ((-0.01, -0.01), (0.01, -0.01), (0.01, 0.01), (-0.01, 0.01), (-0.01, -0.01))
    ring = [[DAR[1] + dx, DAR[0] + dy] for dx, dy in corners]
    fence = {
        "name": "Yard fence",
        "kind": "SITE_BOUNDARY",
        "job_site_id": site["id"],
        "polygon": {"type": "Polygon", "coordinates": [ring]},
    }
    ok(f.owner.post(f"{T}/geofences", fence), 201)


def test_time_and_place_since_the_last_visit_are_recorded(api: Api) -> None:
    """Last visit = the latest earlier reading of the machine that belongs to any report (a rejected one counts), by
    the reading's taken-at time; the first report has none. Its place is the phone's area label for the reading; the
    company site containing the point is a hint (null outside every site)."""
    ctx = setup_reports(api)
    f, m = ctx.f, ctx.machine_id
    bought(api, f, 20)
    _yard(f)
    before = ok(f.supervisor.get(f"{T}/machine-reports/context/{m}"))
    assert before["last_visit_at"] is None and before["last_visit_place"] is None

    first_at = later(api, 3)
    body = report_body(m, "1003", first_at, [cust(f.customer_id, 3)])
    body["capture"]["place_name"] = "Mbezi Beach, Kinondoni, Dar es Salaam"
    first = submit(f.supervisor, body)
    assert first["previous_visit_at"] is None and first["since_previous_visit_seconds"] is None
    assert first["visit_place"] == "Mbezi Beach, Kinondoni, Dar es Salaam"
    assert first["visit_site_name"] == "Kigamboni yard" and first["visit_lat"] == DAR[0]
    ok(f.manager.post(f"{T}/machine-reports/{first['id']}/reject", {"reason": "Wrong customer"}))

    context = ok(f.supervisor.get(f"{T}/machine-reports/context/{m}"))
    assert context["last_visit_at"] is not None and context["last_visit_site_name"] == "Kigamboni yard"
    assert context["last_visit_place"] == "Mbezi Beach, Kinondoni, Dar es Salaam"
    assert context["last_visit_lat"] == DAR[0] and context["last_visit_accuracy_m"] == 8.0
    state = ok(f.supervisor.get(f"{T}/machine-reports/status"))[0]
    assert state["last_visit_at"] == context["last_visit_at"] and state["last_visit_site_name"] == "Kigamboni yard"

    # 27 h 30 min later, outside the yard, no area label: the rejected report's reading is the last visit.
    second_at = later(api, 27.5)
    body = report_body(m, "1005", second_at, [cust(f.customer_id, 5)])
    body["capture"]["gps"] = fix(second_at, lat=DAR[0] + 0.5, lon=DAR[1] + 0.5)
    second = submit(f.supervisor, body)
    assert second["since_previous_visit_seconds"] == int(27.5 * 3600)
    assert second["previous_visit_at"] == context["last_visit_at"]
    assert second["previous_visit_place"] == "Mbezi Beach, Kinondoni, Dar es Salaam"
    assert second["previous_visit_site_name"] == "Kigamboni yard" and second["previous_visit_lat"] == DAR[0]
    assert second["visit_place"] is None and second["visit_site_name"] is None
    assert second["visit_lat"] == DAR[0] + 0.5
    listed = ok(f.owner.get(f"{T}/machine-reports", queue="PENDING"))["items"][0]
    assert listed["since_previous_visit_seconds"] == int(27.5 * 3600)

    # Never changed afterwards: the report's guard refuses it.
    with pytest.raises(DBAPIError):
        tenant_sql(f.tid, "UPDATE machine_report SET since_previous_visit_seconds = 60 WHERE id = :i", i=second["id"])
    assert ok(f.owner.get(f"{T}/machine-reports/{second['id']}"))["since_previous_visit_seconds"] == int(27.5 * 3600)


def test_a_reading_carries_an_optional_area_label(api: Api) -> None:
    ctx = setup_reports(api)
    f, m = ctx.f, ctx.machine_id
    at = later(api, 1)
    labelled = reading(m, "1001", at)
    labelled["place_name"] = "  Mbezi Beach, Kinondoni, Dar es Salaam  "
    saved = ok(f.supervisor.post(f"{T}/meter-captures", labelled), 201)
    assert saved["capture"]["place_name"] == "Mbezi Beach, Kinondoni, Dar es Salaam"
    too_long = reading(m, "1002", later(api, 1))
    too_long["place_name"] = "x" * 201
    r = f.supervisor.post(f"{T}/meter-captures", too_long)
    assert r.status_code == 422 and code(r) == "VALIDATION_FAILED", r.text
    # Older apps send no label at all.
    plain = ok(f.supervisor.post(f"{T}/meter-captures", reading(m, "1002", later(api, 1))), 201)
    assert plain["capture"]["place_name"] is None


def test_the_visit_gap_warning_is_a_company_setting(api: Api) -> None:
    ctx = setup_reports(api)
    effective = ok(ctx.f.owner.get(f"{T}/policies/CUSTOMER_HOURS/effective"))
    assert effective["values"]["visit_gap_warning_hours"] == 24
    hours_policy(ctx.f, visit_gap_warning_hours=36)
    effective = ok(ctx.f.owner.get(f"{T}/policies/CUSTOMER_HOURS/effective"))
    assert effective["values"]["visit_gap_warning_hours"] == 36
    hours_policy(ctx.f, visit_gap_warning_hours=None)
    assert ok(ctx.f.owner.get(f"{T}/policies/CUSTOMER_HOURS/effective"))["values"]["visit_gap_warning_hours"] is None


def test_approval_consumes_the_oldest_orders_first_and_writes_both_ledgers(api: Api) -> None:
    ctx = setup_reports(api)
    f, m = ctx.f, ctx.machine_id
    old = bought(api, f, 2)
    later(api, 1)
    new = bought(api, f, 5)
    at = later(api, 5)
    rep = submit(
        f.supervisor,
        report_body(m, "1005", at, [cust(f.customer_id, 4), idle(ctx.reasons["BREAKDOWN"], 1, "Hydraulic hose")]),
    )
    approver = role(api, f.tid, "manager", "mgr-approver-2")
    done = ok(approver.post(f"{T}/machine-reports/{rep['id']}/approve", {}))
    lots = done["lines"][0]["lots"]
    assert [(lot["purchase_id"], Decimal(lot["hours"])) for lot in lots] == [
        (old["id"], Decimal(2)),
        (new["id"], Decimal(2)),
    ]
    assert lots[0]["purchase_number"] == old["purchase_number"]
    # Hours ledger: CONSUMED entries linked to the report; the customer has 3 hours left.
    consumed = tenant_sql(
        f.tid,
        "SELECT purchase_id, hours FROM hours_ledger_entry WHERE machine_report_id = :r AND entry_type = 'CONSUMED' "
        "ORDER BY created_at",
        r=rep["id"],
    )
    assert {str(p): Decimal(h) for p, h in consumed} == {old["id"]: 2, new["id"]: 2}
    assert _available(ctx, f.customer_id) == 3
    # Allocation ledger: the split laid over the meter range, customer work with its lots, the reason's hours.
    rows = tenant_sql(
        f.tid,
        "SELECT kind, start_reading, end_reading, customer_id, reason_id, lots, source, approval_ref_ids "
        "FROM work_allocation WHERE status = 'ACTIVE' AND machine_id = :m ORDER BY start_reading",
        m=m,
    )
    assert [(r[0], Decimal(r[1]), Decimal(r[2])) for r in rows] == [
        ("CUSTOMER_WORK", Decimal(1000), Decimal(1004)),
        ("AUTHORIZED_ACTIVITY", Decimal(1004), Decimal(1005)),
    ]
    assert str(rows[0][3]) == f.customer_id and str(rows[1][4]) == ctx.reasons["BREAKDOWN"]
    assert {lot["purchase_id"] for lot in rows[0][5]} == {old["id"], new["id"]}
    assert rows[0][6] == "MACHINE_REPORT" and [str(x) for x in rows[0][7]] == [rep["id"]]
    # The purchases show the hours used.
    used = ok(f.owner.get(f"{T}/hours-purchases/{old['id']}"))
    assert Decimal(used["totals"]["consumed"]) == 2 and used["status"] == "CONSUMED"
    # The reading is now the machine's last approved one.
    assert Decimal(ok(f.supervisor.get(f"{T}/machine-reports/context/{m}"))["previous_reading"]) == 1005


def test_detail_carries_the_tracker_cross_check(api: Api) -> None:
    ctx = setup_reports(api)
    f, m = ctx.f, ctx.machine_id
    first = submit(f.supervisor, report_body(m, "1003", later(api, 3), [idle(ctx.reasons["TRANSIT"], 3)]))
    detail = ok(f.manager.get(f"{T}/machine-reports/{first['id']}"))
    assert detail["tracker"]["available"] is False and Decimal(detail["tracker"]["meter_hours"]) == 3
    ok(f.manager.post(f"{T}/machine-reports/{first['id']}/approve", {}))

    # The tracker counted 2.5 engine hours between the two readings: the approver sees the difference.
    start = api.clock.now
    for at, hours in ((start - timedelta(minutes=5), "500.0"), (start + timedelta(hours=3), "502.5")):
        sql(
            "INSERT INTO machine_position_event (id, event_time, received_at, tenant_id, machine_id, tracker_id, "
            "ingestion_event_id, location, engine_hours, quality, is_late, clock_offset_seconds, policy_version) "
            "VALUES (gen_random_uuid(), :t, :t, :tid, :m, :tr, gen_random_uuid(), "
            "ST_SetSRID(ST_MakePoint(39.28, -6.8), 4326), :h, 'GOOD', false, 0, 'test')",
            t=at,
            tid=f.tid,
            m=m,
            tr=f.c.t.tracker_id,
            h=Decimal(hours),
        )
    rep = submit(f.supervisor, report_body(m, "1006", later(api, 3), [idle(ctx.reasons["TRANSIT"], 3)]))
    detail = ok(f.manager.get(f"{T}/machine-reports/{rep['id']}"))
    tracker = detail["tracker"]
    assert tracker["available"] is True
    assert Decimal(tracker["tracker_hours"]) == Decimal("2.5") and Decimal(tracker["difference"]) == Decimal("0.5")
    assert detail["capture_state"] in {"ACCEPTED", "PROVISIONAL"}
    pending = ok(f.manager.get(f"{T}/machine-reports", queue="PENDING"))
    assert [p["id"] for p in pending["items"]] == [rep["id"]]


# --- reasons ------------------------------------------------------------------------------------------------------
def test_every_new_company_starts_with_the_default_reasons_and_may_edit_them(api: Api) -> None:
    ctx = setup_reports(api)
    f = ctx.f
    rows = ok(f.supervisor.get(f"{T}/machine-report-reasons"))
    assert {r["code"] for r in rows} == {c for c, _ in DEFAULT_REASONS}
    admin = role(api, f.tid, "administrator", "admin-reasons")
    created = ok(admin.post(f"{T}/machine-report-reasons", {"code": "FUEL_WAIT", "name": "Waiting for fuel"}), 201)
    weather = next(r for r in rows if r["code"] == "WEATHER")
    ok(admin.post(f"{T}/machine-report-reasons/{weather['id']}/deactivate", {"reason": "Not used", "version": 1}))
    codes = {r["code"] for r in ok(f.supervisor.get(f"{T}/machine-report-reasons"))}
    assert "FUEL_WAIT" in codes and "WEATHER" not in codes
    assert created["is_active"] is True
    r = f.supervisor.post(
        f"{T}/machine-reports", report_body(ctx.machine_id, "1001", later(api, 1), [idle(weather["id"], 1)])
    )
    assert code(r) == "REASON_INVALID", r.text
    assert f.supervisor.post(f"{T}/machine-report-reasons", {"code": "X", "name": "Nope"}).status_code == 403


def test_the_one_off_script_adds_missing_defaults_once(api: Api, monkeypatch: Any) -> None:
    import importlib.util
    import sys
    from pathlib import Path

    ctx = setup_reports(api)
    f = ctx.f
    sql("DELETE FROM engine_hour_reason WHERE kind = 'NON_PRODUCTIVE' AND code IN ('WEATHER', 'TRANSIT')")
    script = Path(__file__).resolve().parents[2] / "scripts" / "seed_machine_report_reasons.py"
    spec = importlib.util.spec_from_file_location("seed_machine_report_reasons", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["seed_machine_report_reasons"] = module
    spec.loader.exec_module(module)
    count = "SELECT count(*) FROM engine_hour_reason WHERE kind = 'NON_PRODUCTIVE'"
    assert tenant_sql(f.tid, count)[0][0] == len(DEFAULT_REASONS) - 2
    assert module.main(["--tenant-id", f.tid]) == 0  # a dry run changes nothing
    assert tenant_sql(f.tid, count)[0][0] == len(DEFAULT_REASONS) - 2
    assert module.main(["--yes"]) == 0  # every company: the two missing come back
    assert tenant_sql(f.tid, count)[0][0] == len(DEFAULT_REASONS)
    assert module.main(["--yes"]) == 0  # a second run adds nothing
    assert tenant_sql(f.tid, count)[0][0] == len(DEFAULT_REASONS)
    audited = sql(
        "SELECT count(*) FROM audit_event WHERE tenant_id = :t AND action = 'meter.reason.created' "
        "AND reason LIKE 'Starting machine-report reasons%'",
        t=f.tid,
    )[0][0]
    assert audited == 2


# --- notifications -------------------------------------------------------------------------------------------------
def test_approvers_and_the_submitter_are_told(api: Api) -> None:
    ctx = setup_reports(api)
    f, m = ctx.f, ctx.machine_id
    approver = member(api, f.tid, "manager", "mr-notify-manager")
    sup = member(api, f.tid, "supervisor", "mr-notify-sup")
    ok(
        f.owner.post(
            f"{T}/staff", {"full_name": "Notified Supervisor", "kind": "SUPERVISOR", "keycloak_subject": sup.subject}
        ),
        201,
    )
    staff_id = next(s["id"] for s in ok(f.owner.get(f"{T}/staff", q="Notified"))["items"])
    m2 = second_machine(api, ctx, assign_to=staff_id, prefix="NTF")
    drain(api)
    rep = submit(sup, report_body(m2, "1002", later(api, 2), [idle(ctx.reasons["TRANSIT"], 2)]))
    drain(api)
    inbox = ok(approver.get(f"{T}/notifications"))["items"]
    note = next(n for n in inbox if n["type"] == "MACHINE_REPORT_SUBMITTED")
    assert rep["report_number"] in note["title"] and note["target"]["path"] == f"/tenant/machine-reports/{rep['id']}"
    assert "fraud" not in (note["title"] + note["body"]).lower()
    ok(approver.post(f"{T}/machine-reports/{rep['id']}/reject", {"reason": "Split the transit hours"}))
    drain(api)
    mine = ok(sup.get(f"{T}/notifications"))["items"]
    told = next(n for n in mine if n["type"] == "MACHINE_REPORT_REJECTED")
    assert "Split the transit hours" in told["body"]
    assert m  # the first machine is not involved


def test_machines_that_moved_without_a_report_are_flagged(api: Api) -> None:
    from asseta.core.db import DbScope, apply_scope, get_sessionmaker
    from asseta.modules.machine_reports.missing import machines_without_reports

    ctx = setup_reports(api)
    f, m = ctx.f, ctx.machine_id
    # A reading above the baseline with no report about it.
    ok(f.supervisor.post(f"{T}/meter-captures", reading(m, "1004", later(api, 4))), 201)
    later(api, 24 * 4)

    def missing() -> list[Any]:
        with get_sessionmaker().begin() as s:
            apply_scope(s, DbScope.TENANT, uuid.UUID(f.tid), None)
            return machines_without_reports(s, uuid.UUID(f.tid), api.clock.now)

    [miss] = missing()
    assert str(miss.machine_id) == m and miss.basis == "meter reading"
    from tests.support.hours import hours_policy

    hours_policy(f, machine_report_reminder_days=None)
    assert missing() == []
