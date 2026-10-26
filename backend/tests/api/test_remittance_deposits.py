"""DEC-031 Phase 3 (money reaches the owner): company deposit accounts (D1), stronger remittances with method,
deposit account, reference and evidence photos online and offline (D2), surplus/shortfall labels on variances, and
the remote-site cash holding allowance with site and staff overrides (D3). Every new control is off by default:
existing clients keep working unchanged."""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from asseta.core.db import get_sessionmaker
from asseta.modules.finance.deposit_accounts import mask_account_number
from asseta.modules.finance.remittance_cutoff import run_remittance_cutoff
from tests.support.api import Actor, Api
from tests.support.finance import FinCtx, cash_policy, setup_finance
from tests.support.jobs import capture, unique_jpeg
from tests.support.notify import sql, sync_mirror

C = "/api/v1/tenant/cash"
D = "/api/v1/tenant/deposit-accounts"
T0 = "2026-11-01T06:00:00+00:00"  # 09:00 tenant-local (Africa/Dar_es_Salaam)
T1 = "2026-11-01T07:00:00+00:00"
DEVICE = "android-dec031-p3"


def _ok(r: Any, status: int = 201) -> Any:
    assert r.status_code == status, r.text
    return r.json()


def _err(r: Any, status: int, code: str) -> None:
    assert r.status_code == status, r.text
    assert r.json()["error"]["code"] == code, r.text


def _staff(f: FinCtx, name: str) -> str:
    return str(_ok(f.owner.post("/api/v1/tenant/staff", {"full_name": name, "kind": "OPERATOR"}))["id"])


def _collect(actor: Actor, f: FinCtx, staff_id: str, amount: str, at: str = T0) -> Any:
    body = {"customer_id": f.customer_id, "amount": amount, "received_at": at, "staff_member_id": staff_id}
    return _ok(actor.post(f"{C}/collections", body))


def _account(f: FinCtx, name: str, kind: str = "BANK", number: str | None = "0150 2233 4821") -> dict[str, Any]:
    body = {"name": name, "account_type": kind, "institution": "CRDB", "account_number": number}
    return dict(_ok(f.accountant.post(D, body)))


def _photo(api: Api, actor: Actor) -> str:
    r = api.client.post(
        f"{C}/remittance-evidence",
        headers=actor.headers(True, None),
        files={"file": ("slip.jpg", unique_jpeg(), "image/jpeg")},
    )
    return str(_ok(r)["id"])


def _policy(f: FinCtx, scope: str, ref: str | None, **values: Any) -> Any:
    body = {"scope": scope, "scope_ref_id": ref, "values": values, "reason": "Holding allowance"}
    return f.owner.post("/api/v1/tenant/policies/CASH_CUSTODY/versions", body)


# --- D1 ------------------------------------------------------------------------------------------------------------
def test_deposit_account_lifecycle_masking_permissions_and_menu(api: Api) -> None:
    f = setup_finance(api)
    acc = _account(f, "CRDB main account")
    assert (acc["account_type"], acc["account_number_masked"], acc["currency"]) == ("BANK", "•••• 4821", "TZS")
    assert acc["created_by_name"] is not None and acc["is_active"] is True
    assert mask_account_number("1234") == "1234" and mask_account_number("•••• 9999") == "•••• 9999"
    _err(f.accountant.post(D, {"name": "crdb MAIN account", "account_type": "BANK"}), 409, "DUPLICATE_DEPOSIT_ACCOUNT")
    mm = _account(f, "M-Pesa till", "MOBILE_MONEY", "0754 000 111")

    # Field recorders read the picker but cannot manage accounts.
    names = [a["name"] for a in _ok(f.supervisor.get(D), 200)["items"]]
    assert names == ["CRDB main account", "M-Pesa till"]
    _err(f.supervisor.post(D, {"name": "Mine", "account_type": "BANK"}), 403, "PERMISSION_DENIED")
    assert [a["id"] for a in _ok(f.accountant.get(D, q="pesa"), 200)["items"]] == [mm["id"]]
    assert _ok(f.accountant.get(D, account_type="BANK"), 200)["total"] == 1

    edited = _ok(
        f.accountant.patch(
            f"{D}/{acc['id']}", {"institution": "CRDB Bank", "account_number": "99887766", "version": 1}
        ),
        200,
    )
    assert (edited["institution"], edited["account_number_masked"], edited["version"]) == ("CRDB Bank", "•••• 7766", 2)
    _err(f.accountant.patch(f"{D}/{acc['id']}", {"note": "x", "version": 1}), 409, "STALE_VERSION")
    off = _ok(f.accountant.post(f"{D}/{acc['id']}/deactivate", {"reason": "Account closed"}), 200)
    assert (off["is_active"], off["deactivation_reason"]) == (False, "Account closed")
    assert _ok(f.accountant.get(D), 200)["total"] == 1
    assert _ok(f.accountant.get(D, include_inactive=True), 200)["total"] == 2
    assert _ok(f.supervisor.get(f"{D}/{acc['id']}"), 200)["is_active"] is False
    back = _ok(f.accountant.post(f"{D}/{acc['id']}/reactivate", {"reason": "Reopened"}), 200)
    assert back["is_active"] is True
    _err(f.accountant.get(f"{D}/{uuid.uuid4()}"), 404, "DEPOSIT_ACCOUNT_NOT_FOUND")
    audit = sql("SELECT action FROM audit_event WHERE entity_type = 'company_deposit_account' ORDER BY occurred_at")
    assert {r.action for r in audit} >= {
        "finance.deposit_account.created",
        "finance.deposit_account.updated",
        "finance.deposit_account.deactivated",
        "finance.deposit_account.reactivated",
    }

    nav = _ok(f.owner.get("/api/v1/me"), 200)["tenants"][0]
    menu = next(m for m in nav["menus"] if m["key"] == "tenant.deposit_accounts")
    assert (menu["group"], menu["path"]) == ("tenant.finance", "/tenant/finance/deposit-accounts")
    sup_nav = _ok(f.supervisor.get("/api/v1/me"), 200)["tenants"][0]
    assert "tenant.deposit_accounts" not in {m["key"] for m in sup_nav["menus"]}


# --- D2 ------------------------------------------------------------------------------------------------------------
def test_remittance_details_are_optional_by_default_and_carry_account_and_evidence(api: Api) -> None:
    f = setup_finance(api)
    mgr, acct = f.manager, f.accountant
    op = _staff(f, "Operator Baraka")
    _collect(mgr, f, op, "90000")

    # An older client: no method, account, reference or evidence -> recorded exactly as before.
    legacy = _ok(mgr.post(f"{C}/handovers", {"staff_member_id": op, "amount": "10000", "handed_at": T1}))
    assert (legacy["method"], legacy["deposit_account_id"], legacy["evidence_attachment_ids"]) == (None, None, [])

    bank = _account(f, "CRDB main account")
    photo = _photo(api, mgr)
    body = {
        "staff_member_id": op,
        "amount": "50000",
        "handed_at": T1,
        "deposit_account_id": bank["id"],
        "reference": "DEP-778812",
        "evidence_attachment_ids": [photo],
    }
    h = _ok(mgr.post(f"{C}/handovers", body))
    assert (h["method"], h["deposit_account_id"], h["deposit_account_name"]) == (
        "BANK_DEPOSIT",
        bank["id"],
        "CRDB main account",
    )
    assert (h["reference"], h["evidence_attachment_ids"]) == ("DEP-778812", [photo])
    got = _ok(acct.get(f"{C}/handovers/{h['id']}"), 200)
    assert (got["deposit_account_name"], got["evidence_attachment_ids"]) == ("CRDB main account", [photo])
    listed = _ok(acct.get(f"{C}/handovers"), 200)["items"]
    assert {x["id"]: x["deposit_account_name"] for x in listed}[h["id"]] == "CRDB main account"
    ev = _ok(acct.get(f"{C}/handovers/{h['id']}/evidence"), 200)
    assert [e["attachment_id"] for e in ev] == [photo]
    assert _ok(acct.get(f"{C}/handovers/{h['id']}/evidence/{photo}/url"), 200)["url"]
    _err(acct.get(f"{C}/handovers/{legacy['id']}/evidence/{photo}/url"), 404, "NOT_FOUND")

    # Evidence can be added later while awaiting confirmation, never after the decision.
    late = _photo(api, mgr)
    added = _ok(mgr.post(f"{C}/handovers/{legacy['id']}/evidence", {"attachment_ids": [late]}))
    assert [e["attachment_id"] for e in added] == [late]
    assert _ok(acct.get(f"{C}/handovers/{legacy['id']}"), 200)["evidence_attachment_ids"] == [late]
    _ok(acct.post(f"{C}/handovers/{legacy['id']}/decision", {"verified": True}), 200)
    _err(
        mgr.post(f"{C}/handovers/{legacy['id']}/evidence", {"attachment_ids": [late]}), 409, "HANDOVER_ALREADY_DECIDED"
    )

    # Method and account must agree; inactive accounts and unknown evidence are refused.
    base = {"staff_member_id": op, "amount": "1000", "handed_at": T1}
    _err(
        mgr.post(f"{C}/handovers", {**base, "method": "MOBILE_MONEY", "deposit_account_id": bank["id"]}),
        422,
        "REMITTANCE_ACCOUNT_MISMATCH",
    )
    _err(
        mgr.post(f"{C}/handovers", {**base, "evidence_attachment_ids": [str(uuid.uuid4())]}),
        404,
        "ATTACHMENT_NOT_FOUND",
    )
    _ok(acct.post(f"{D}/{bank['id']}/deactivate", {"reason": "Closed"}), 200)
    _err(mgr.post(f"{C}/handovers", {**base, "deposit_account_id": bank["id"]}), 422, "DEPOSIT_ACCOUNT_INACTIVE")
    mm = _ok(mgr.post(f"{C}/handovers", {**base, "method": "MOBILE_MONEY", "reference": "QK12"}))
    assert (mm["method"], mm["deposit_account_id"]) == ("MOBILE_MONEY", None)


def test_remittance_requirements_follow_policy_and_master_switch(api: Api) -> None:
    f = setup_finance(api)
    mgr = f.manager
    op = _staff(f, "Operator Neema")
    _collect(mgr, f, op, "90000")
    bank = _account(f, "NMB collections")
    office = _account(f, "Head office safe", "CASH_OFFICE", None)
    base = {"staff_member_id": op, "amount": "1000", "handed_at": T1}

    cash_policy(f, remittance_account_required=True)
    _err(mgr.post(f"{C}/handovers", base), 422, "REMITTANCE_ACCOUNT_REQUIRED")
    cash = _ok(mgr.post(f"{C}/handovers", {**base, "deposit_account_id": office["id"]}))
    assert cash["method"] == "CASH_TO_OFFICE"

    cash_policy(f, remittance_account_required=True, remittance_reference_required=True)
    _err(mgr.post(f"{C}/handovers", {**base, "deposit_account_id": bank["id"]}), 422, "REMITTANCE_REFERENCE_REQUIRED")
    _ok(mgr.post(f"{C}/handovers", {**base, "deposit_account_id": office["id"]}))  # cash needs no reference
    _ok(mgr.post(f"{C}/handovers", {**base, "deposit_account_id": bank["id"], "reference": "NMB-1"}))

    cash_policy(f, remittance_evidence_required=True)
    _err(mgr.post(f"{C}/handovers", {**base, "deposit_account_id": bank["id"]}), 422, "REMITTANCE_EVIDENCE_REQUIRED")
    _ok(mgr.post(f"{C}/handovers", {**base, "evidence_attachment_ids": [_photo(api, mgr)]}))

    # The CASH_CUSTODY master switch off: the DEC-031 requirements read as off (the details stay optional).
    cash_policy(f, enabled=False, remittance_evidence_required=True, remittance_account_required=True)
    _ok(f.accountant.post(f"{C}/handovers", base))  # office cash staff (recording for others is a control too)
    eff = _ok(f.owner.get("/api/v1/tenant/policies/CASH_CUSTODY/effective"), 200)["values"]
    assert eff["remittance_evidence_required"] is True  # configured value shown; enforcement follows the switch


def test_surplus_and_shortfall_are_labelled(api: Api) -> None:
    f = setup_finance(api)
    mgr, acct = f.manager, f.accountant
    op = _staff(f, "Operator Juma")
    _collect(mgr, f, op, "90000")
    short = _ok(mgr.post(f"{C}/handovers", {"staff_member_id": op, "amount": "30000", "handed_at": T1}))
    more = _ok(mgr.post(f"{C}/handovers", {"staff_member_id": op, "amount": "20000", "handed_at": T1}))
    _ok(acct.post(f"{C}/handovers/{short['id']}/decision", {"verified": True, "amount_received": "25000"}), 200)
    _ok(acct.post(f"{C}/handovers/{more['id']}/decision", {"verified": True, "amount_received": "21000"}), 200)
    kinds = {
        v["source_id"]: (v["kind"], Decimal(v["amount"]))
        for v in _ok(acct.get(f"{C}/variances", source_type="REMITTANCE"), 200)["items"]
    }
    assert kinds == {short["id"]: ("SHORTFALL", Decimal(5000)), more["id"]: ("SURPLUS", Decimal(-1000))}


# --- D2 offline --------------------------------------------------------------------------------------------------
def _h(actor: Actor) -> dict[str, str]:
    return {**actor.headers(True, None), "X-Device-Id": DEVICE}


def _push(api: Api, actor: Actor, ops: list[dict[str, Any]]) -> list[dict[str, Any]]:
    r = api.client.post(
        "/api/v1/sync/push", headers=_h(actor), json={"device_now": api.clock.now.isoformat(), "operations": ops}
    )
    assert r.status_code == 200, r.text
    return list(r.json()["results"])


def _op(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "op_type": "CASH_HANDOVER",
        "payload": {"client_id": str(uuid.uuid4()), "amount": "1000", "handed_at": T1, **payload},
        "created_at_device": T1,
        "depends_on": [],
    }


def _start_upload(api: Api, actor: Actor) -> tuple[str, bytes]:
    data = unique_jpeg()
    s = api.client.post(
        "/api/v1/sync/blobs",
        headers=_h(actor),
        json={"sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data), "purpose": "REMITTANCE_EVIDENCE"},
    )
    return str(_ok(s, 201)["id"]), data


def test_offline_remittance_details_evidence_uploads_and_conflicts(api: Api) -> None:
    f = setup_finance(api)
    sup = f.supervisor
    _collect(sup, f, f.sup_staff_id, "90000")
    bank = _account(f, "CRDB main account")
    _ok(
        api.client.post(
            "/api/v1/sync/devices",
            headers=_h(sup),
            json={"device_id": DEVICE, "platform": "ANDROID", "app_version": "1.4.0"},
        )
    )
    boot = _ok(api.client.get("/api/v1/sync/bootstrap", headers=_h(sup)), 200)
    assert "REMITTANCE_DETAILS_V1" in boot["capabilities"]
    assert [a["id"] for a in boot["data"]["deposit_accounts"]] == [bank["id"]]

    # The existing payload keeps working.
    assert _push(api, sup, [_op({})])[0]["status"] == "ACKED"

    upload_id, data = _start_upload(api, sup)
    op = _op({"deposit_account_id": bank["id"], "reference": "DEP-1", "evidence_upload_ids": [upload_id]})
    deferred = _push(api, sup, [op])[0]
    assert (deferred["status"], deferred["error"]["code"]) == ("DEFERRED", "ATTACHMENT_PENDING")
    api.client.put(f"/api/v1/sync/blobs/{upload_id}/chunks/0", headers=_h(sup), content=data)
    done = _ok(api.client.post(f"/api/v1/sync/blobs/{upload_id}/complete", headers=_h(sup)), 200)
    acked = _push(api, sup, [op])[0]
    assert acked["status"] == "ACKED", acked
    entity = acked["result"]["entity"]
    assert (entity["method"], entity["deposit_account_id"], entity["evidence_attachment_ids"]) == (
        "BANK_DEPOSIT",
        bank["id"],
        [done["attachment_id"]],
    )
    assert _push(api, sup, [op])[0]["status"] == "DUPLICATE"

    # The tenant switched a requirement on after the device queued the remittance: a conflict, never applied.
    cash_policy(f, remittance_evidence_required=True)
    refused = _push(api, sup, [_op({"deposit_account_id": bank["id"]})])[0]
    assert (refused["status"], refused["error"]["code"]) == ("CONFLICT", "REMITTANCE_EVIDENCE_REQUIRED")
    _ok(f.accountant.post(f"{D}/{bank['id']}/deactivate", {"reason": "Closed"}), 200)
    gone = _push(api, sup, [_op({"deposit_account_id": bank["id"], "evidence_upload_ids": [upload_id]})])[0]
    assert (gone["status"], gone["error"]["code"]) == ("CONFLICT", "DEPOSIT_ACCOUNT_INACTIVE")
    delta = _ok(api.client.get("/api/v1/sync/changes", headers=_h(sup), params={"cursor": boot["cursor"]}), 200)
    assert [(a["id"], a["is_active"]) for a in delta["data"]["deposit_accounts"]] == [(bank["id"], False)]


# --- D3 ------------------------------------------------------------------------------------------------------------
def _held_flags() -> list[Any]:
    return list(
        sql(
            "SELECT staff_member_id, reason, local_day, max_holding_days, held_since FROM cash_remittance_overdue "
            "ORDER BY local_day, reason"
        )
    )


def test_holding_allowance_flags_cash_held_too_long_with_overrides(api: Api) -> None:
    f = setup_finance(api)
    mgr, acct = f.manager, f.accountant
    zawadi = _staff(f, "Operator Zawadi")
    imani = _staff(f, "Operator Imani")
    kept = _staff(f, "Operator Kept")
    _collect(mgr, f, zawadi, "60000")
    _collect(mgr, f, imani, "20000")
    _collect(mgr, f, kept, "5000")
    r = _ok(mgr.post(f"{C}/retentions", {"staff_member_id": kept, "amount": "5000", "reason": "Fuel float"}))
    _ok(acct.post(f"{C}/retentions/{r['id']}/decision", {"approve": True}), 200)
    day3 = datetime(2026, 11, 4, 7, 0, tzinfo=UTC)  # 10:00 local, three days after the collections

    # Default: no allowance (null) -> nothing flagged, whatever the age of the cash.
    assert run_remittance_cutoff(get_sessionmaker(), day3).flagged == 0

    cash_policy(f, max_holding_days=2)
    assert run_remittance_cutoff(get_sessionmaker(), datetime(2026, 11, 2, 7, 0, tzinfo=UTC)).flagged == 0
    _ok(_policy(f, "STAFF", imani, max_holding_days=5))  # Imani works far away: a longer allowance
    sync_mirror(api)
    first = run_remittance_cutoff(get_sessionmaker(), day3)
    again = run_remittance_cutoff(get_sessionmaker(), day3 + timedelta(hours=3))
    assert (first.flagged, again.flagged, first.failures) == (1, 0, 0)  # Kept's cash is covered by his retention
    [flag] = _ok(acct.get(f"{C}/remittance-overdue"), 200)["items"]
    assert (flag["staff_member_id"], flag["reason"], flag["max_holding_days"], flag["local_day"]) == (
        zawadi,
        "HELD_TOO_LONG",
        2,
        "2026-11-04",
    )
    assert flag["held_since"].startswith("2026-11-01T06:00")
    assert [(a["currency"], Decimal(a["amount"])) for a in flag["amounts"]] == [("TZS", Decimal(60000))]
    note = sql(
        "SELECT body, data FROM notification WHERE notification_type = 'REMITTANCE_OVERDUE' AND entity_id = :e",
        e=flag["id"],
    )
    assert note and note[0].data["reason"] == "HELD_TOO_LONG" and note[0].data["record_id"] == flag["id"]
    assert "longer than the allowed 2 days" in note[0].body

    # The cut-off works alongside: both reasons can flag the same custodian on the same day, once each.
    cash_policy(f, max_holding_days=2, remittance_cutoff_hour=17)
    evening = datetime(2026, 11, 4, 15, 0, tzinfo=UTC)  # 18:00 local
    assert run_remittance_cutoff(get_sessionmaker(), evening).flagged == 2  # Zawadi and Imani past the cut-off
    reasons = sorted((str(r.staff_member_id), r.reason) for r in _held_flags())
    assert reasons == sorted([(zawadi, "HELD_TOO_LONG"), (zawadi, "CUTOFF"), (imani, "CUTOFF")])
    only = _ok(acct.get(f"{C}/remittance-overdue", reason="HELD_TOO_LONG"), 200)["items"]
    assert [x["staff_member_id"] for x in only] == [zawadi]
    api.clock.set_at(evening)
    tile = _ok(f.owner.get("/api/v1/tenant/accountability/summary"), 200)["cash"]
    assert tile["remittances_overdue_today"] == 2  # custodians, not flags

    # Imani's own allowance (5 days) passes on day 6; remitting everything clears Zawadi.
    _ok(mgr.post(f"{C}/handovers", {"staff_member_id": zawadi, "amount": "60000", "handed_at": "2026-11-05T06:00Z"}))
    day6 = datetime(2026, 11, 6, 7, 0, tzinfo=UTC)
    run_remittance_cutoff(get_sessionmaker(), day6)
    day6_flags = [(str(r.staff_member_id), r.reason) for r in _held_flags() if str(r.local_day) == "2026-11-06"]
    assert day6_flags == [(imani, "HELD_TOO_LONG")]

    # Master switch off: no holding allowance.
    cash_policy(f, enabled=False, max_holding_days=1)
    assert run_remittance_cutoff(get_sessionmaker(), day6 + timedelta(days=1)).flagged == 0


def test_site_override_and_staff_scope_rules(api: Api) -> None:
    f = setup_finance(api)
    o = f.owner
    site = _ok(
        o.post(
            "/api/v1/tenant/job-sites",
            {"code": "FAR", "name": "Remote quarry", "center": {"type": "Point", "coordinates": [39.28, -6.8]}},
        )
    )
    [m2] = api.add_machines(o, 1, prefix="FAR")
    job = _ok(
        o.post(
            "/api/v1/tenant/jobs",
            {
                "contract_id": f.c.contract_id,
                "job_number": "J-FAR",
                "machine_id": m2,
                "job_site_id": site["id"],
                "supervisor_id": f.sup_staff_id,
                "planned_start": api.clock.now.isoformat(),
                "hourly_rate": "90000",
            },
        )
    )
    for action in ("SUBMIT", "APPROVE"):
        _ok(o.post(f"/api/v1/tenant/jobs/{job['id']}/transitions", {"action": action}), 200)
    _ok(o.post("/api/v1/tenant/meter-captures", capture(job["id"], "OPENING", "100", api.clock.now, mode="MANUAL")))
    _ok(o.post(f"/api/v1/tenant/jobs/{job['id']}/transitions", {"action": "START"}), 200)
    _collect(f.manager, f, f.sup_staff_id, "40000")
    office = _staff(f, "Office Cashier")
    _collect(f.manager, f, office, "40000")

    cash_policy(f, max_holding_days=1)
    _ok(_policy(f, "SITE", site["id"], max_holding_days=10))  # the remote site gets ten days
    run_remittance_cutoff(get_sessionmaker(), datetime(2026, 11, 4, 7, 0, tzinfo=UTC))
    assert [str(r.staff_member_id) for r in _held_flags()] == [office]  # the supervisor on the remote site waits

    # Only `max_holding_days` may be overridden per site/staff, and staff overrides exist only for cash custody.
    _err(_policy(f, "STAFF", office, retention_allowed=False), 422, "POLICY_FIELD_NOT_OVERRIDABLE")
    _err(_policy(f, "STAFF", str(uuid.uuid4()), max_holding_days=3), 404, "NOT_FOUND")
    _err(_policy(f, "STAFF", None, max_holding_days=3), 404, "NOT_FOUND")
    other = o.post(
        "/api/v1/tenant/policies/EXPENSE_CAPTURE/versions",
        {"scope": "STAFF", "scope_ref_id": office, "values": {"gps_required": False}, "reason": "Per person"},
    )
    _err(other, 422, "POLICY_FIELD_NOT_OVERRIDABLE")
    eff = _ok(o.get("/api/v1/tenant/policies/CASH_CUSTODY/effective", site_id=site["id"]), 200)
    assert eff["values"]["max_holding_days"] == 10 and ".S" in eff["version_stamp"]
