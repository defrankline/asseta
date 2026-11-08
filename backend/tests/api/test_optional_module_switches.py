"""DEC-032: the five per-company optional-module switches (platform default ON). Each one, switched off, omits its
menus, refuses its endpoints (422 <CAPABILITY>_DISABLED) and lists itself in /me disabled_capabilities; defaults
change nothing. Job sites, machines, cash variances, revenue differences and mandates are not touched by a switch."""

import uuid
from datetime import timedelta
from typing import Any

from asseta.core.db import DbScope, apply_scope, get_sessionmaker
from asseta.modules.geospatial.connectivity import sweep_tenant
from asseta.modules.intelligence.detectors_telemetry import detect_engine_activity
from asseta.modules.intelligence.linking import CaseItem, CaseLinker
from asseta.modules.intelligence.models import CaseSourceType, SignalSeverity, SubjectType
from asseta.tools.gps_simulator import Fix
from tests.api.test_managed_service import grant
from tests.api.test_oversight import _collect_and_remit
from tests.support.api import Actor, Api
from tests.support.finance import cash_policy, role, setup_finance
from tests.support.notify import sql
from tests.support.telemetry import DAR, Telemetry

T = "/api/v1/tenant"
ACCOUNTS = f"{T}/deposit-accounts"
DEFAULT_OFF = ("IDLE_MACHINES", "REVENUE_RECONCILIATION", "SCORECARD", "SITE_CHECKIN", "UNBILLED_WORK")
LAT, LON = DAR


def _ok(r: Any, status: int = 200) -> Any:
    assert r.status_code == status, r.text
    return r.json()


def _refused(r: Any, code: str) -> None:
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == code


def _nav(actor: Actor) -> dict[str, Any]:
    return dict(_ok(actor.get("/api/v1/me"))["tenants"][0])


def _menu(actor: Actor) -> dict[str, str]:
    return {m["key"]: m["label"] for m in _nav(actor)["menus"]}


def _policy(owner: Actor, ptype: str, **values: Any) -> None:
    _ok(
        owner.post(f"{T}/policies/{ptype}/versions", {"scope": "TENANT", "values": values, "reason": "Module switch"}),
        201,
    )


def _steps(actor: Actor) -> dict[str, dict[str, Any]]:
    return {s["key"]: s for s in _ok(actor.get(f"{T}/setup-checklist"))["steps"]}


def _fix(api: Api, minutes: int) -> Fix:
    return Fix(api.clock.now + timedelta(minutes=minutes), LAT, LON, 20.0, 0.0)


def test_defaults_change_nothing(api: Api) -> None:
    f = setup_finance(api, "Defaults Co", "DEF-1")
    o = f.owner
    nav = _nav(o)
    assert nav["disabled_capabilities"] == [*DEFAULT_OFF]
    keys = set(_menu(o))
    assert {"tenant.insights", "tenant.cases", "tenant.trackers", "tenant.alerts"} <= keys
    assert {"tenant.deposit_accounts", "tenant.managed_service"} <= keys
    assert _menu(o)["tenant.geofences"] == "Sites & geofences"
    for path in ("insights", "cases", "risk-signals", "trackers", "alerts", "geofences", "deposit-accounts"):
        _ok(o.get(f"{T}/{path}"))
    _ok(o.get(f"{T}/ml/status"))
    effective = _ok(o.get(f"{T}/policies/OVERSIGHT/effective"))["values"]
    assert (effective["insights_enabled"], effective["investigations_enabled"]) == (True, True)
    assert effective["managed_service_enabled"] is True
    assert _ok(o.get(f"{T}/policies/TRACKING/effective"))["values"]["enabled"] is True
    assert _ok(o.get(f"{T}/policies/CASH_CUSTODY/effective"))["values"]["deposit_accounts_enabled"] is True
    assert "investigations" not in _ok(o.get(f"{T}/accountability/summary"))["hidden_tiles"]


def test_insights_off(api: Api) -> None:
    f = setup_finance(api, "No Insights", "INS-1")
    o = f.owner
    _policy(o, "OVERSIGHT", insights_enabled=False)
    assert _nav(o)["disabled_capabilities"] == [*sorted({*DEFAULT_OFF, "INSIGHTS"})]
    assert "tenant.insights" not in _menu(o)
    for path in ("insights", "insights/manual-overrides", "ml/status", "ml/predictions"):
        _refused(o.get(f"{T}/{path}"), "INSIGHTS_DISABLED")
    _ok(o.get(f"{T}/cases"))  # the other switches are independent
    outsider = role(api, f.tid, "operator", "no-insights-operator")
    assert outsider.get(f"{T}/insights").status_code == 403  # the permission is checked first


def test_investigations_off_records_but_opens_no_cases(api: Api) -> None:
    f = setup_finance(api, "No Cases", "CAS-1")
    o = f.owner
    cash_policy(f, variance_case_threshold="20000")
    on = _collect_and_remit(f, "2026-11-01T10:00:00+00:00", "100000", "70000")  # above the threshold: a case
    assert _ok(f.accountant.get(f"{T}/cash/variances/{on}"))["case_id"] is not None
    assert len(sql("SELECT id FROM anomaly_case WHERE tenant_id = :t", t=f.tid)) == 1

    _policy(o, "OVERSIGHT", investigations_enabled=False)
    assert "INVESTIGATIONS" in _nav(o)["disabled_capabilities"] and "tenant.cases" not in _menu(o)
    _refused(o.get(f"{T}/cases"), "INVESTIGATIONS_DISABLED")
    _refused(o.get(f"{T}/risk-signals"), "INVESTIGATIONS_DISABLED")
    assert "investigations" in _ok(o.get(f"{T}/accountability/summary"))["hidden_tiles"]
    overview = _ok(o.get(f"{T}/overview"))
    assert overview["risk"] is None

    # The difference is still recorded; only the case is not opened.
    off = _collect_and_remit(f, "2026-11-01T11:00:00+00:00", "100000", "70000")
    assert off != on and _ok(f.accountant.get(f"{T}/cash/variances/{off}"))["case_id"] is None
    assert len(sql("SELECT id FROM anomaly_case WHERE tenant_id = :t", t=f.tid)) == 1
    # The linker opens nothing, directly either.
    with get_sessionmaker().begin() as session:
        tid = uuid.UUID(f.tid)
        apply_scope(session, DbScope.TENANT, tid, None)
        linker = CaseLinker(session, tid, api.clock.now, 24)
        item = CaseItem(
            CaseSourceType.ADJUSTMENT,
            tid,
            "X",
            "Direct",
            SignalSeverity.WARNING,
            api.clock.now,
            {},
            SubjectType.CUSTOMER,
            tid,
            "v1",
        )
        assert linker.link(item) is None


def test_tracking_off_keeps_machines_sites_and_billing(api: Api) -> None:
    tel = Telemetry(api)
    a = tel.tracked_machine("No Tracking", "TRK-1")
    o = a.owner
    assert tel.send("TRK-1", _fix(api, 1))["accepted"] == 1
    geofence = {
        "name": "Yard",
        "kind": "ALLOWED_AREA",
        "polygon": {
            "type": "Polygon",
            "coordinates": [[[LON, LAT], [LON + 0.01, LAT], [LON + 0.01, LAT + 0.01], [LON, LAT]]],
        },
    }
    fence = _ok(o.post(f"{T}/geofences", geofence), 201)
    before = _ok(o.get(f"{T}/machines/{a.machine_id}"))
    site = _ok(o.post(f"{T}/job-sites", {"code": "Q-1", "name": "Quarry", "center": {"coordinates": [LON, LAT]}}), 201)

    _policy(o, "TRACKING", enabled=False)
    nav = _nav(o)
    assert "TRACKING" in nav["disabled_capabilities"]
    menus = _menu(o)
    assert not {"tenant.trackers", "tenant.alerts"} & set(menus)
    assert menus["tenant.geofences"] == "Job sites" and "tenant.machines" in menus and "tenant.fleet_map" in menus

    for path in ("trackers", "alerts", "geofences", f"geofences/{fence['id']}", "telemetry/ingestion-events"):
        _refused(o.get(f"{T}/{path}"), "TRACKING_DISABLED")
    _refused(o.post(f"{T}/geofences", geofence), "TRACKING_DISABLED")
    # Job sites and machines are not tracking; billing enrollment is untouched.
    assert [s["id"] for s in _ok(o.get(f"{T}/job-sites"))] == [site["id"]]
    assert _ok(o.get(f"{T}/machines/{a.machine_id}"))["billing_enrolled"] == before["billing_enrolled"]

    # A tracker message is ignored safely: acknowledged, stored as quarantined, no position.
    result = tel.send("TRK-1", _fix(api, 2))
    assert (result["accepted"], result["quarantined"], result["reasons"]) == (0, 1, ["TRACKING_DISABLED"])
    positions = sql("SELECT count(*) FROM machine_position_event WHERE machine_id = :m", m=a.machine_id)
    assert positions[0][0] == 1  # only the message from before the switch
    # Trackers that stop reporting raise nothing, and engine evidence is skipped.
    later = api.clock.now + timedelta(days=3)
    tid = a.tenant["tenant"]["id"]
    with get_sessionmaker().begin() as session:
        apply_scope(session, DbScope.TENANT, tid, None)
        assert sweep_tenant(session, tid, later).transitions == 0
        assert detect_engine_activity(session, tid, later, later - timedelta(days=4)) == []

    steps = _steps(o)
    assert steps["TRACKERS"]["status"] == "NOT_APPLICABLE"
    assert {c["key"] for c in steps["SITES"]["checks"]} == {"JOB_SITES"}
    assert steps["SITES"]["status"] == "DONE"
    overview = _ok(o.get(f"{T}/overview"))["fleet"]
    assert overview["machines"] == 1 and overview["connectivity"]["live"] == 0 and overview["open_alerts"]["info"] == 0


def test_deposit_accounts_off_requires_no_account(api: Api) -> None:
    f = setup_finance(api, "No Deposits", "DEP-1")
    o, acct = f.owner, f.accountant
    cash_policy(f, remittance_account_required=True)
    base = {"staff_member_id": f.sup_staff_id, "amount": "1000", "handed_at": "2026-11-01T10:00:00+00:00"}
    refused = acct.post(f"{T}/cash/handovers", base)
    assert refused.status_code == 422 and refused.json()["error"]["code"] == "REMITTANCE_ACCOUNT_REQUIRED"

    cash_policy(f, remittance_account_required=True, deposit_accounts_enabled=False)
    nav = _nav(o)
    assert "DEPOSIT_ACCOUNTS" in nav["disabled_capabilities"] and "tenant.deposit_accounts" not in _menu(o)
    _refused(o.get(ACCOUNTS), "DEPOSIT_ACCOUNTS_DISABLED")
    _refused(
        o.post(ACCOUNTS, {"name": "NMB", "account_type": "BANK", "account_number": "1", "currency": "TZS"}),
        "DEPOSIT_ACCOUNTS_DISABLED",
    )
    # remittance_account_required reads as off: the remittance needs no account.
    assert acct.post(f"{T}/cash/handovers", base).status_code == 201
    assert _steps(o)["DEPOSIT_ACCOUNTS"]["status"] == "NOT_APPLICABLE"


def test_managed_service_off_hides_only_the_tenant_page(api: Api) -> None:
    t = api.onboard("No Mandate Page", price="1")
    owner, tid = t["owner"], t["tenant"]["id"]
    mandate = grant(api, tid)
    assert _ok(owner.get(f"{T}/managed-service"))

    _policy(owner, "OVERSIGHT", managed_service_enabled=False)
    assert "MANAGED_SERVICE" in _nav(owner)["disabled_capabilities"]
    assert "tenant.managed_service" not in _menu(owner)
    _refused(owner.get(f"{T}/managed-service"), "MANAGED_SERVICE_DISABLED")
    _refused(
        owner.post(f"{T}/managed-service/{mandate['id']}/revoke", {"reason": "Not needed"}), "MANAGED_SERVICE_DISABLED"
    )

    # The mandate stays in force and the platform still governs it.
    detail = _ok(api.platform.get(f"/api/v1/platform/mandates/{mandate['id']}"))
    assert detail["status"] == mandate["status"]
    assert [m["id"] for m in _ok(api.platform.get("/api/v1/platform/mandates")) if m["tenant_id"] == tid] == [
        mandate["id"]
    ]


def test_tracking_enabled_cannot_be_set_per_machine(api: Api) -> None:
    tel = Telemetry(api)
    a = tel.tracked_machine("Tenant Level", "LVL-1")
    r = a.owner.post(
        f"{T}/policies/TRACKING/versions",
        {"scope": "MACHINE", "scope_ref_id": a.machine_id, "values": {"enabled": False}, "reason": "Machine only"},
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "POLICY_FIELD_NOT_OVERRIDABLE"
