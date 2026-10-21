"""Record lifecycle for job sites, geofences, trackers, the platform tracker-model catalog, tenant company details
and expense categories; READ_ONLY subscriptions refuse lifecycle writes; devices drop deactivated reference data."""

from typing import Any

from tests.support.api import Actor, Api
from tests.support.jobs import setup_job
from tests.support.telemetry import DAR, Telemetry

T = "/api/v1/tenant"
P = "/api/v1/platform"
REASON = {"reason": "No longer used"}
LAT, LON = DAR
POINT = {"type": "Point", "coordinates": [LON, LAT]}
SQUARE = {
    "type": "Polygon",
    "coordinates": [
        [[LON - 0.002, LAT - 0.002], [LON + 0.002, LAT - 0.002], [LON + 0.002, LAT + 0.002], [LON - 0.002, LAT - 0.002]]
    ],
}


def _ids(rows: list[dict[str, Any]]) -> set[str]:
    return {r["id"] for r in rows}


def _role(api: Api, tid: str, key: str) -> Actor:
    return Actor(api, f"{key}-lc", [f"/tenants/{tid}/{key}"], tid, email=f"{key}@lc.example.com")


def test_job_site_and_geofence_lifecycle(api: Api) -> None:
    c = setup_job(api, "Site Co", "SITE-1")
    o, tid = c.owner, c.t.tenant["tenant"]["id"]
    site = o.post(f"{T}/job-sites", {"code": "S1", "name": "Bridge", "center": POINT}).json()
    assert (site["version"], site["is_active"]) == (1, True)
    assert o.get(f"{T}/job-sites/{site['id']}").json()["code"] == "S1"
    moved = {"code": "S1", "name": "Bridge north", "address": "Km 12", "center": {**POINT, "coordinates": [LON, -6.9]}}
    r = o.put(f"{T}/job-sites/{site['id']}", {**moved, "version": 1})
    assert r.status_code == 200 and r.json()["version"] == 2 and r.json()["center"]["coordinates"][1] == -6.9
    assert o.put(f"{T}/job-sites/{site['id']}", {**moved, "version": 1}).json()["error"]["code"] == "STALE_VERSION"
    o.post(f"{T}/job-sites", {"code": "S2", "name": "Quarry", "center": POINT})
    assert (
        o.put(f"{T}/job-sites/{site['id']}", {**moved, "code": "S2", "version": 2}).json()["error"]["code"]
        == "DUPLICATE_SITE"
    )

    # A job at the site blocks deactivation (draft counts: it would otherwise point at a hidden site).
    [m2] = api.add_machines(o, 1, prefix="SIT")
    job = o.post(
        f"{T}/jobs",
        {
            "contract_id": c.contract_id,
            "job_number": "J-SITE",
            "machine_id": m2,
            "job_site_id": site["id"],
            "planned_start": api.clock.now.isoformat(),
            "hourly_rate": "1000",
        },
    ).json()
    in_use = o.post(f"{T}/job-sites/{site['id']}/deactivate", REASON)
    assert (in_use.status_code, in_use.json()["error"]["code"]) == (422, "SITE_IN_USE")
    o.post(f"{T}/jobs/{job['id']}/transitions", {"action": "CANCEL", "reason": "Moved"})
    off = o.post(f"{T}/job-sites/{site['id']}/deactivate", REASON)
    assert off.status_code == 200 and off.json()["is_active"] is False and off.json()["deactivated_at"]
    assert site["id"] not in _ids(o.get(f"{T}/job-sites").json())
    assert site["id"] in _ids(o.get(f"{T}/job-sites", include_inactive="true").json())
    new_job = o.post(
        f"{T}/jobs",
        {
            "contract_id": c.contract_id,
            "job_number": "J-SITE2",
            "machine_id": m2,
            "job_site_id": site["id"],
            "planned_start": api.clock.now.isoformat(),
            "hourly_rate": "1000",
        },
    )
    assert new_job.json()["error"]["code"] == "SITE_INACTIVE"
    assert o.post(f"{T}/job-sites/{site['id']}/reactivate", {"reason": "Phase 2"}).json()["is_active"] is True

    fence = o.post(f"{T}/geofences", {"name": "Yard", "kind": "ALLOWED_AREA", "polygon": SQUARE}).json()
    assert o.get(f"{T}/geofences/{fence['id']}").json()["name"] == "Yard"
    stale = o.post(f"{T}/geofences/{fence['id']}/deactivate", {**REASON, "version": 7})
    assert stale.json()["error"]["code"] == "STALE_VERSION"
    g_off = o.post(f"{T}/geofences/{fence['id']}/deactivate", {**REASON, "version": 1})
    assert g_off.status_code == 200, g_off.text
    assert (g_off.json()["is_active"], g_off.json()["version"]) == (False, 2)
    assert fence["id"] not in _ids(o.get(f"{T}/geofences").json())
    assert fence["id"] in _ids(o.get(f"{T}/geofences", include_inactive="true").json())
    stale_put = o.put(
        f"{T}/geofences/{fence['id']}", {"name": "Yard", "kind": "ALLOWED_AREA", "polygon": SQUARE, "version": 1}
    )
    assert stale_put.json()["error"]["code"] == "STALE_VERSION"
    assert o.post(f"{T}/geofences/{fence['id']}/reactivate", {"reason": "Back"}).json()["is_active"] is True

    stranger = api.onboard("Site Other", price="1")["owner"]
    assert stranger.get(f"{T}/job-sites/{site['id']}").status_code == 404
    assert stranger.post(f"{T}/geofences/{fence['id']}/deactivate", REASON).status_code == 404
    acct = _role(api, tid, "accountant")
    assert acct.post(f"{T}/job-sites/{site['id']}/deactivate", REASON).status_code == 403
    assert acct.get(f"{T}/geofences/{fence['id']}").status_code == 403


def test_tracker_edit_and_platform_tracker_model_catalog(api: Api) -> None:
    tel = Telemetry(api)
    a = tel.tracked_machine("Track Co", "TRK-1")
    o, tid = a.owner, a.tenant["tenant"]["id"]
    tr = o.get(f"{T}/trackers/{a.tracker_id}").json()
    edit = {"label": "Excavator unit", "sim_iccid": "8925500000000000001", "sim_msisdn": "+255711000001"}
    r = o.put(f"{T}/trackers/{a.tracker_id}", {**edit, "carrier": "Vodacom", "version": tr["version"]})
    assert r.status_code == 200 and (r.json()["label"], r.json()["version"]) == ("Excavator unit", 2)
    assert r.json()["current_assignment"]["machine_id"] == a.machine_id  # edits never touch the assignment
    assert o.put(f"{T}/trackers/{a.tracker_id}", {**edit, "version": 1}).json()["error"]["code"] == "STALE_VERSION"
    assert o.get(f"{T}/trackers", q="+255711").json()["total"] == 1

    spare = tel.register(o, "TRK-SPARE")
    retired = o.post(f"{T}/trackers/{spare}/state", {"state": "RETIRED", "reason": "Water damage"})
    assert retired.status_code == 200, retired.text
    assert spare not in _ids(o.get(f"{T}/trackers").json()["items"])
    assert spare in _ids(o.get(f"{T}/trackers", include_inactive="true").json()["items"])
    assert spare in _ids(o.get(f"{T}/trackers", state="RETIRED").json()["items"])
    ro = o.put(f"{T}/trackers/{spare}", {"label": "x", "version": 1})
    assert ro.json()["error"]["code"] == "TRACKER_RETIRED"
    stranger = api.onboard("Track Other", price="1")["owner"]
    assert stranger.put(f"{T}/trackers/{a.tracker_id}", {**edit, "version": 2}).status_code == 404
    assert _role(api, tid, "accountant").put(f"{T}/trackers/{a.tracker_id}", {**edit, "version": 2}).status_code == 403

    # Platform catalog: details, edit (adapter fixed), withdraw/restore; withdrawn models are not offered.
    mid = tel.model_id
    model = api.platform.get(f"{P}/tracker-models/{mid}").json()
    assert (model["approved"], model["version"]) == (True, 1)
    upd = {
        "manufacturer": "Simulated",
        "model": "OsmAnd v2",
        "protocol": "osmand",
        "declared_capabilities": ["GNSS", "IGNITION"],
        "notes": "Firmware 2.x",
    }
    r = api.platform.put(f"{P}/tracker-models/{mid}", {**upd, "version": 1})
    assert r.status_code == 200 and (r.json()["model"], r.json()["version"]) == ("OsmAnd v2", 2)
    assert api.platform.put(f"{P}/tracker-models/{mid}", {**upd, "version": 1}).json()["error"]["code"] == (
        "STALE_VERSION"
    )
    assert [m["id"] for m in api.platform.get(f"{P}/tracker-models", q="osmand v2").json()] == [mid]
    off = api.platform.post(f"{P}/tracker-models/{mid}/deactivate", {"reason": "Vendor end of life"})
    assert off.status_code == 200 and off.json()["approved"] is False and off.json()["deactivated_at"]
    assert mid not in _ids(api.platform.get(f"{P}/tracker-models").json())
    assert mid in _ids(api.platform.get(f"{P}/tracker-models", include_inactive="true").json())
    assert mid not in _ids(o.get(f"{T}/tracker-models").json())  # tenants no longer offered it
    new = o.post(f"{T}/trackers", {"tracker_model_id": mid, "external_id": "TRK-NEW", "label": "new"})
    assert new.json()["error"]["code"] == "TRACKER_MODEL_NOT_APPROVED"
    assert o.get(f"{T}/trackers/{a.tracker_id}").json()["tracker_model_id"] == mid  # existing tracker unaffected
    on = api.platform.post(f"{P}/tracker-models/{mid}/reactivate", {"reason": "Firmware fixed"})
    assert on.json()["approved"] is True
    assert o.get(f"{P}/tracker-models").status_code == 403  # tenant users cannot use the platform catalog

    # Telemetry gateways: listed (never their keys) and revocable; a deactivated gateway's key stops working.
    [gw] = api.platform.get(f"{P}/telemetry-gateways").json()
    assert "gateway_key" not in gw and api.platform.get(f"{P}/telemetry-gateways/{gw['id']}").json()["active"]
    g_off = api.platform.post(f"{P}/telemetry-gateways/{gw['id']}/deactivate", {"reason": "Key leaked"})
    assert g_off.status_code == 200 and g_off.json()["active"] is False
    assert api.platform.get(f"{P}/telemetry-gateways").json() == []
    assert len(api.platform.get(f"{P}/telemetry-gateways", include_inactive="true").json()) == 1
    denied = api.client.post("/api/v1/telemetry/traccar", json={}, headers={"X-Asseta-Gateway-Key": tel.key})
    assert denied.status_code == 401
    assert api.platform.post(f"{P}/telemetry-gateways/{gw['id']}/reactivate", {"reason": "Rotated"}).status_code == 200
    assert o.post(f"{P}/telemetry-gateways/{gw['id']}/deactivate", {"reason": "nope"}).status_code == 403
    assert o.put(f"{P}/tracker-models/{mid}", {**upd, "version": 3}).status_code == 403


def test_platform_tenant_company_details(api: Api) -> None:
    t = api.onboard("Company Co", price="1")
    tid = t["tenant"]["id"]
    body = {
        "legal_name": "Company Co Holdings Ltd",
        "display_name": "Company Co",
        "registration_number": "BRELA-1",
        "contact_name": "Jane Owner",
        "contact_email": "jane@company.example.com",
        "contact_phone": "+255700000000",
    }
    r = api.platform.put(f"{P}/tenants/{tid}", {**body, "version": 1})
    assert r.status_code == 200 and (r.json()["legal_name"], r.json()["version"]) == ("Company Co Holdings Ltd", 2)
    assert api.platform.put(f"{P}/tenants/{tid}", {**body, "version": 1}).json()["error"]["code"] == "STALE_VERSION"
    other = api.onboard("Company Two", price="1")["tenant"]["id"]
    dup = api.platform.put(f"{P}/tenants/{other}", {**body, "display_name": "Two", "version": 1})
    assert dup.json()["error"]["code"] == "TENANT_EXISTS"
    api.activate(t)  # verifies the company record
    fixed = api.platform.put(f"{P}/tenants/{tid}", {**body, "registration_number": "BRELA-2", "version": 2})
    assert fixed.json()["error"]["code"] == "TENANT_VERIFIED_FIELD"
    ok = api.platform.put(f"{P}/tenants/{tid}", {**body, "contact_name": "New Contact", "version": 2})
    assert ok.status_code == 200 and ok.json()["contact_name"] == "New Contact"
    assert api.platform.get(f"{P}/tenants/{tid}").json()["version"] == 3
    assert t["owner"].put(f"{P}/tenants/{tid}", {**body, "version": 3}).status_code == 403
    missing = api.platform.put(f"{P}/tenants/00000000-0000-0000-0000-000000000000", {**body, "version": 1})
    assert missing.status_code == 404


def test_expense_categories_read_only_and_device_sync(api: Api) -> None:
    c = setup_job(api, "Exp Co", "EXP-1")
    o, tid = c.owner, c.t.tenant["tenant"]["id"]
    cat = o.post(f"{T}/expense-categories", {"code": "FUEL", "name": "Fuel"}).json()
    keep = o.post(f"{T}/expense-categories", {"code": "MEALS", "name": "Meals"}).json()
    assert o.get(f"{T}/expense-categories/{cat['id']}").json()["code"] == "FUEL"
    r = o.put(f"{T}/expense-categories/{cat['id']}", {"code": "FUEL", "name": "Fuel & lubricants", "version": 1})
    assert r.status_code == 200 and r.json()["version"] == 2
    assert (
        o.put(f"{T}/expense-categories/{cat['id']}", {"code": "FUEL", "name": "x", "version": 1}).json()["error"][
            "code"
        ]
        == "STALE_VERSION"
    )
    dup = o.put(f"{T}/expense-categories/{keep['id']}", {"code": "FUEL", "name": "Meals", "version": 1})
    assert dup.json()["error"]["code"] == "DUPLICATE_EXPENSE_CATEGORY"

    # A supervisor device: bootstrap ships active categories only; a delta carries the deactivation.
    sup = _role(api, tid, "supervisor")
    h = {**sup.headers(True, None), "X-Device-Id": "dev-lc-1"}
    reg = api.client.post(
        "/api/v1/sync/devices", headers=h, json={"device_id": "dev-lc-1", "platform": "ANDROID", "app_version": "1.0.0"}
    )
    assert reg.status_code == 201, reg.text
    boot = api.client.get("/api/v1/sync/bootstrap", headers=h).json()
    assert {x["code"] for x in boot["data"]["expense_categories"]} == {"FUEL", "MEALS"}
    off = o.post(f"{T}/expense-categories/{cat['id']}/deactivate", REASON)
    assert off.status_code == 200 and off.json()["is_active"] is False
    assert [x["code"] for x in o.get(f"{T}/expense-categories").json()] == ["MEALS"]
    assert len(o.get(f"{T}/expense-categories", include_inactive="true").json()) == 2
    delta = api.client.get("/api/v1/sync/changes", headers=h, params={"cursor": boot["cursor"]}).json()
    pulled = {x["code"]: x["is_active"] for x in delta["data"]["expense_categories"]}  # (lookback may resend)
    assert pulled["FUEL"] is False and pulled.get("MEALS", True) is True
    boot2 = api.client.get("/api/v1/sync/bootstrap", headers=h).json()
    assert {x["code"] for x in boot2["data"]["expense_categories"]} == {"MEALS"}
    assert sup.post(f"{T}/expense-categories/{cat['id']}/reactivate", REASON).status_code == 403
    assert api.onboard("Exp Other", price="1")["owner"].get(f"{T}/expense-categories/{cat['id']}").status_code == 404

    # READ_ONLY subscription: details stay visible, every lifecycle write is refused.
    sid = c.t.tenant["subscription_id"]
    s = api.platform.post(
        f"{P}/subscriptions/{sid}/transitions",
        {"to_status": "SUSPENDED", "effective_date": api.clock.now.date().isoformat(), "reason": "Overdue"},
    )
    assert s.json()["access_state"] == "READ_ONLY"
    assert o.get(f"{T}/expense-categories/{cat['id']}").status_code == 200
    for resp in (
        o.post(f"{T}/expense-categories/{cat['id']}/reactivate", {"reason": "Back"}),
        o.put(f"{T}/machines/{c.t.machine_id}", {"name": "x", "status": "ACTIVE", "version": 1}),
        o.post(f"{T}/machines/{c.t.machine_id}/deactivate", REASON),
        o.post(f"{T}/contracts/{c.contract_id}/close", REASON),
    ):
        assert (resp.status_code, resp.json()["error"]["code"]) == (403, "SUBSCRIPTION_READ_ONLY")
