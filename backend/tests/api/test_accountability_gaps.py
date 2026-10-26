"""DEC-030 gap pass: menus follow tenant capabilities (G1), names next to ids on approval/queue/list records (G2),
offline cash retention requests (G3), the daily remittance cut-off sweep (G4) and exact-record deep links with
GET-by-id endpoints (G5)."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from asseta.core.db import get_sessionmaker
from asseta.modules.finance.remittance_cutoff import run_remittance_cutoff
from tests.support.api import Actor, Api
from tests.support.finance import FinCtx, cash_policy, setup_finance
from tests.support.hours import RATE, hours_policy, purchase, verify
from tests.support.notify import drain, sql, sync_mirror

C = "/api/v1/tenant/cash"
T0 = "2026-11-01T06:00:00+00:00"  # 09:00 tenant-local (Africa/Dar_es_Salaam)
T1 = "2026-11-01T07:00:00+00:00"
DEVICE = "android-gaps-0001"


def _ok(r: Any, status: int = 201) -> Any:
    assert r.status_code == status, r.text
    return r.json()


def _staff(f: FinCtx, name: str) -> str:
    return str(_ok(f.owner.post("/api/v1/tenant/staff", {"full_name": name, "kind": "OPERATOR"}))["id"])


def _collect(actor: Actor, f: FinCtx, staff_id: str, amount: str, at: str = T0) -> Any:
    body = {"customer_id": f.customer_id, "amount": amount, "received_at": at, "staff_member_id": staff_id}
    return _ok(actor.post(f"{C}/collections", body))


def _notification(tid: str, ntype: str) -> Any:
    rows = sql(
        "SELECT link, entity_type, entity_id, data FROM notification WHERE tenant_id = :t AND notification_type = :n",
        t=tid,
        n=ntype,
    )
    assert rows, f"no {ntype} notification"
    return rows[0]


# --- G1 ------------------------------------------------------------------------------------------------------------
def _tenant_nav(actor: Actor) -> dict[str, Any]:
    return dict(_ok(actor.get("/api/v1/me"), 200)["tenants"][0])


def test_menus_follow_the_tenant_capability_policy(api: Api) -> None:
    f = setup_finance(api)
    nav = _tenant_nav(f.owner)
    assert "tenant.hours" in {g["key"] for g in nav["menu_groups"]}
    assert {"tenant.hours.purchases", "tenant.field.hours"} <= {m["key"] for m in nav["menus"]}
    assert nav["disabled_capabilities"] == [
        "IDLE_MACHINES",
        "REVENUE_RECONCILIATION",
        "SCORECARD",
        "SITE_CHECKIN",
        "UNBILLED_WORK",
    ]  # off by default (DEC-031)

    hours_policy(f, enabled=False)  # the tenant switches customer hours off: its navigation goes with it
    nav = _tenant_nav(f.owner)
    assert nav["disabled_capabilities"] == [
        "CUSTOMER_HOURS",
        "IDLE_MACHINES",
        "REVENUE_RECONCILIATION",
        "SCORECARD",
        "SITE_CHECKIN",
        "UNBILLED_WORK",
    ]
    assert "tenant.hours" not in {g["key"] for g in nav["menu_groups"]}
    keys = {m["key"] for m in nav["menus"]}
    assert not {k for k in keys if k.startswith("tenant.hours") or k == "tenant.field.hours"}
    assert "tenant.cash_custody" in keys  # other features are untouched

    hours_policy(f, enabled=True)
    assert "tenant.hours.purchases" in {m["key"] for m in _tenant_nav(f.owner)["menus"]}


# --- G2 + G5 -------------------------------------------------------------------------------------------------------
def test_cash_records_carry_names_and_open_by_id(api: Api) -> None:
    f = setup_finance(api)
    mgr, acct, acct2 = f.manager, f.accountant, f.accountant2
    operator = _staff(f, "Operator Rehema")
    paid = _collect(mgr, f, operator, "50000")
    payments = _ok(acct.get("/api/v1/tenant/customer-payments"), 200)["items"]
    row = next(p for p in payments if p["id"] == paid["id"])
    assert row["received_by_staff_name"] == "Operator Rehema" and row["customer_name"]

    # Remittance (handover): list and exact record carry the custodian's and recorder's names.
    h = _ok(mgr.post(f"{C}/handovers", {"staff_member_id": operator, "amount": "30000", "handed_at": T1}))
    listed = _ok(acct.get(f"{C}/handovers"), 200)["items"]
    assert listed[0]["staff_member_name"] == "Operator Rehema" and listed[0]["recorded_by_name"]
    got = _ok(acct.get(f"{C}/handovers/{h['id']}"), 200)
    assert (got["id"], got["staff_member_name"]) == (h["id"], "Operator Rehema")
    assert acct.get(f"{C}/handovers/{uuid.uuid4()}").status_code == 404

    # A transfer names both custodians; its variance names the accountable custodian.
    receiver = _staff(f, "Operator Baraka")
    t = _ok(
        mgr.post(
            f"{C}/transfers",
            {"from_staff_id": operator, "to_staff_id": receiver, "amount": "20000", "transferred_at": T1},
        )
    )
    assert (t["from_staff_name"], t["to_staff_name"]) == ("Operator Rehema", "Operator Baraka")
    _ok(acct.post(f"{C}/transfers/{t['id']}/acknowledgement", {"acknowledged": True, "amount_received": "15000"}), 200)
    tl = _ok(acct.get(f"{C}/transfers", staff_member_id=receiver), 200)["items"][0]
    assert tl["to_staff_name"] == "Operator Baraka" and tl["acknowledged_by_name"]
    v = _ok(acct.get(f"{C}/variances"), 200)["items"][0]
    assert (v["staff_member_name"], v["counterparty_staff_name"]) == ("Operator Rehema", "Operator Baraka")

    # Float, retention and adjustment: each opens by id with names.
    fl = _ok(acct.post(f"{C}/floats", {"staff_member_id": receiver, "amount": "5000", "occurred_at": T1}))
    got_float = _ok(acct.get(f"{C}/floats/{fl['id']}"), 200)
    assert (got_float["staff_member_name"], got_float["created_by_name"] is not None) == ("Operator Baraka", True)
    ret = _ok(mgr.post(f"{C}/retentions", {"staff_member_id": operator, "amount": "1000", "reason": "Fuel float"}))
    got_ret = _ok(acct.get(f"{C}/retentions/{ret['id']}"), 200)
    assert got_ret["staff_member_name"] == "Operator Rehema" and got_ret["created_by_name"]
    decided = _ok(acct.post(f"{C}/retentions/{ret['id']}/decision", {"approve": True}), 200)
    assert decided["decided_by_name"]
    adj = _ok(
        acct.post(
            f"{C}/adjustments",
            {"staff_member_id": operator, "kind": "ADJUSTMENT", "amount": "100", "reason": "Recount surplus"},
        )
    )
    got_adj = _ok(acct2.get(f"{C}/adjustments/{adj['id']}"), 200)
    assert got_adj["staff_member_name"] == "Operator Rehema" and got_adj["status"] == "PENDING"
    assert acct.get(f"{C}/retentions/{uuid.uuid4()}").status_code == 404

    # Notifications open the exact record: link to its detail route, data {kind, record_id}.
    sync_mirror(api)
    drain(api)
    link, entity, entity_id, data = _notification(f.tid, "CASH_APPROVAL_REQUESTED")
    assert entity in ("cash_retention", "custody_adjustment")
    kind = {"cash_retention": "CASH_RETENTION", "custody_adjustment": "CUSTODY_ADJUSTMENT"}[entity]
    path = {"cash_retention": "retentions", "custody_adjustment": "adjustments"}[entity]
    assert link == f"/tenant/finance/cash/{path}/{entity_id}"
    assert data["kind"] == kind and data["record_id"] == entity_id
    vlink, _, vid, vdata = _notification(f.tid, "CASH_VARIANCE_OPENED")
    assert vlink == f"/tenant/finance/cash/variances/{vid}" and vdata == {"kind": "CASH_VARIANCE", "record_id": vid}


def test_hours_approvals_carry_customer_machine_and_people_names(api: Api) -> None:
    f = setup_finance(api)
    f.owner.post(f"/api/v1/tenant/jobs/{f.c.job_id}/transitions", {"action": "CANCEL", "reason": "Not needed"})
    body = {"customer_id": f.customer_id, "percent": "10", "effective_from": "2026-01-01", "reason": "Volume customer"}
    d = _ok(f.manager.post("/api/v1/tenant/customer-discounts", body))
    listed = _ok(f.owner.get("/api/v1/tenant/customer-discounts"), 200)["items"]
    row = next(x for x in listed if x["id"] == d["id"])
    assert row["customer_name"] and row["proposed_by_name"] and row["decided_by_name"] is None

    other = _ok(f.owner.post("/api/v1/tenant/machines", {"asset_code": "EXC-901", "name": "Spare excavator"}))["id"]
    p = purchase(api, f.accountant, f, "6", pay=str(6 * RATE))
    verify(f.accountant2, p["payment"]["id"])
    got = _ok(f.owner.get(f"/api/v1/tenant/hours-purchases/{p['id']}"), 200)
    assert got["machine_code"] and got["machine_name"] and got["created_by_name"]
    t = _ok(
        f.supervisor.post(
            "/api/v1/tenant/hours-transfers",
            {"purchase_id": p["id"], "to_machine_id": other, "hours": "2", "reason": "Breakdown"},
        )
    )
    tr = _ok(f.owner.get(f"/api/v1/tenant/hours-transfers/{t['id']}"), 200)
    assert (tr["to_machine_code"], tr["to_machine_name"]) == ("EXC-901", "Spare excavator")
    assert tr["purchase_number"] == p["purchase_number"] and tr["customer_name"] and tr["requested_by_name"]
    sync_mirror(api)
    drain(api)
    link, _, entity_id, data = _notification(f.tid, "HOURS_APPROVAL_REQUESTED")
    assert link.startswith("/tenant/hours/") and link.endswith(f"/{entity_id}")
    assert data["record_id"] == entity_id and data["kind"].startswith("HOURS_")


# --- G3 ------------------------------------------------------------------------------------------------------------
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
        "op_type": "CASH_RETENTION_REQUEST",
        "payload": payload,
        "created_at_device": T1,
        "depends_on": [],
    }


def test_offline_retention_request_is_idempotent_and_follows_policy(api: Api) -> None:
    f = setup_finance(api)
    sup = f.supervisor
    _ok(
        api.client.post(
            "/api/v1/sync/devices",
            headers=_h(sup),
            json={"device_id": DEVICE, "platform": "ANDROID", "app_version": "1.3.0"},
        )
    )
    boot = _ok(api.client.get("/api/v1/sync/bootstrap", headers=_h(sup)), 200)
    assert "OP_CASH_RETENTION_REQUEST" in boot["capabilities"]

    client_id = str(uuid.uuid4())
    op = _op({"client_id": client_id, "amount": "4000", "reason": "Fuel for tomorrow's early start"})
    first = _push(api, sup, [op])[0]
    assert first["status"] == "ACKED", first
    entity = first["result"]["entity"]
    assert (entity["status"], entity["client_id"], entity["staff_member_id"]) == ("PENDING", client_id, f.sup_staff_id)
    assert _push(api, sup, [op])[0]["status"] == "DUPLICATE"
    # Same client id under a new operation id (re-queued after a reinstall): still one retention.
    again = _push(api, sup, [{**op, "id": str(uuid.uuid4())}])[0]
    assert again["status"] == "ACKED" and again["result"]["entity"]["id"] == entity["id"]
    assert _ok(f.accountant.get(f"{C}/retentions"), 200)["total"] == 1
    audit = sql("SELECT source FROM audit_event WHERE action = 'finance.cash_retention.requested'")
    assert [r.source for r in audit] == ["sync"]
    assert _ok(f.accountant.get(f"{C}/retentions/{entity['id']}"), 200)["staff_member_name"] == "Cash Supervisor"

    # The tenant switches retention off after the device's snapshot: a conflict for review, never applied.
    cash_policy(f, retention_allowed=False)
    refused = _push(api, sup, [_op({"client_id": str(uuid.uuid4()), "amount": "10", "reason": "Keep some"})])[0]
    assert (refused["status"], refused["error"]["code"]) == ("CONFLICT", "RETENTION_NOT_ALLOWED")
    assert _ok(f.accountant.get(f"{C}/retentions"), 200)["total"] == 1


# --- G4 ------------------------------------------------------------------------------------------------------------
def test_remittance_cutoff_flags_custodians_once_per_day(api: Api) -> None:
    f = setup_finance(api)
    mgr, acct = f.manager, f.accountant
    holder = _staff(f, "Operator Zawadi")
    remitted = _staff(f, "Operator Imani")
    late = _staff(f, "Operator Late")
    _collect(mgr, f, holder, "60000")
    _collect(mgr, f, remitted, "20000")
    _ok(mgr.post(f"{C}/handovers", {"staff_member_id": remitted, "amount": "20000", "handed_at": T1}))
    _collect(mgr, f, late, "5000", at="2026-11-01T15:30:00+00:00")  # after today's cut-off: due tomorrow
    after_cutoff = datetime(2026, 11, 1, 15, 0, tzinfo=UTC) + timedelta(hours=1)  # 19:00 local

    # Off by default (null): nothing is flagged.
    assert run_remittance_cutoff(get_sessionmaker(), after_cutoff).flagged == 0

    cash_policy(f, remittance_cutoff_hour=17)
    before = run_remittance_cutoff(get_sessionmaker(), datetime(2026, 11, 1, 13, 0, tzinfo=UTC))  # 16:00 local
    assert before.flagged == 0
    sync_mirror(api)
    first = run_remittance_cutoff(get_sessionmaker(), after_cutoff)
    again = run_remittance_cutoff(get_sessionmaker(), after_cutoff + timedelta(hours=2))
    assert (first.flagged, again.flagged, first.failures) == (1, 0, 0)

    flags = _ok(acct.get(f"{C}/remittance-overdue"), 200)["items"]
    assert len(flags) == 1
    flag = flags[0]
    assert (flag["staff_member_id"], flag["staff_member_name"], flag["local_day"], flag["cutoff_hour"]) == (
        holder,
        "Operator Zawadi",
        "2026-11-01",
        17,
    )
    assert [(a["currency"], Decimal(a["amount"])) for a in flag["amounts"]] == [("TZS", Decimal(60000))]
    assert _ok(acct.get(f"{C}/remittance-overdue/{flag['id']}"), 200)["id"] == flag["id"]

    link, entity, entity_id, data = _notification(f.tid, "REMITTANCE_OVERDUE")
    assert (entity, entity_id) == ("cash_remittance_overdue", flag["id"])
    assert link == f"/tenant/finance/cash/remittance-overdue/{flag['id']}"
    assert (data["kind"], data["record_id"], data["staff_member_id"]) == ("REMITTANCE_OVERDUE", flag["id"], holder)
    total = sql("SELECT count(*) FROM notification WHERE notification_type = 'REMITTANCE_OVERDUE'")[0][0]
    run_remittance_cutoff(get_sessionmaker(), after_cutoff + timedelta(hours=3))
    assert sql("SELECT count(*) FROM notification WHERE notification_type = 'REMITTANCE_OVERDUE'")[0][0] == total

    api.clock.set_at(after_cutoff)
    tile = _ok(f.owner.get("/api/v1/tenant/accountability/summary"), 200)["cash"]
    assert (tile["remittance_cutoff_hour"], tile["remittances_overdue_today"]) == (17, 1)

    # The next tenant-local day is a new period: still holding -> flagged again (the late collection too).
    next_day = run_remittance_cutoff(get_sessionmaker(), after_cutoff + timedelta(days=1))
    assert next_day.flagged == 2
