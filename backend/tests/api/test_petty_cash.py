"""DEC-033 petty cash funds: the fund ledger (acknowledged fundings - approved spending - confirmed returns
+/- adjustments - written-off differences - advances + change), pending vs confirmed, segregation of duties on every
decision, overspend online/offline, the collections switch online/offline, the imprest top-up cap, every variance
path (a write-off moves the fund, never the holder's collections custody), holder change, the deactivation guard,
capability off (refusals, hidden menus), RLS isolation, idempotent sync, profitability counting petty expenses once
and never fundings, and today's behaviour unchanged with the platform defaults."""

import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

from asseta.core.db import get_sessionmaker
from asseta.modules.pettycash.sweep import run_petty_cash_sweep
from tests.support.api import Actor, Api
from tests.support.finance import FinCtx, cash_policy, category, expense_policy, role, setup_finance, tenant_sql

P = "/api/v1/tenant/petty-cash"
C = "/api/v1/tenant/cash"
DEVICE = "android-petty-0001"
D = Decimal


def _ok(r: Any, status: int = 201) -> Any:
    assert r.status_code == status, r.text
    return r.json()


def _err(r: Any, status: int, code: str) -> None:
    assert r.status_code == status, r.text
    assert r.json()["error"]["code"] == code, r.text


def petty_policy(f: FinCtx, **values: Any) -> None:
    r = f.owner.post(
        "/api/v1/tenant/policies/PETTY_CASH/versions",
        {"scope": "TENANT", "values": {"enabled": True, **values}, "reason": "Petty cash for this test"},
    )
    assert r.status_code == 201, r.text


def _setup(api: Api, name: str = "Petty Co", device: str = "PET-1") -> tuple[FinCtx, str]:
    f = setup_finance(api, name, device)
    petty_policy(f)
    expense_policy(f, receipt_required_above="100000000", gps_required=False, auto_approve_limit="50000")
    return f, category(f, "SUNDRY", "Sundries")


def _fund(f: FinCtx, code: str = "BOX-1", holder: str | None = None, limit: str = "500000", **kw: Any) -> Any:
    body = {"code": code, "name": f"Office box {code}", "holder_staff_id": holder or f.sup_staff_id}
    return _ok(f.manager.post(f"{P}/funds", {**body, "approved_limit": limit, **kw}))


MONEY_KEYS = (
    "balance",
    "available_to_spend",
    "funded",
    "spent",
    "returned",
    "adjustments",
    "written_off",
    "advances_issued",
    "advance_change_returned",
    "pending_spending",
    "awaiting_acknowledgement",
    "returns_claimed",
    "open_return_differences",
    "pending_adjustments",
    "advances_outstanding",
    "advance_spending",
)


def _bal(actor: Actor, fund_id: str) -> dict[str, Decimal]:
    body = _ok(actor.get(f"{P}/funds/{fund_id}/balance"), 200)
    return {k: D(body[k]) for k in MONEY_KEYS}


def _fund_and_fill(f: FinCtx, fund_id: str, amount: str | None = None, received: str | None = None) -> Any:
    """Propose (accountant) -> approve (owner) -> issue (accountant) -> acknowledge (holder)."""
    body: dict[str, Any] = {"fund_id": fund_id, "kind": "FUNDING"}
    if amount:
        body["amount"] = amount
    m = _ok(f.accountant.post(f"{P}/fundings", body))
    _ok(f.owner.post(f"{P}/movements/{m['id']}/decision", {"approve": True}), 200)
    _ok(f.accountant.post(f"{P}/movements/{m['id']}/issue", {"reference": "SAFE-1"}), 200)
    ack: dict[str, Any] = {"acknowledged": True}
    if received:
        ack["amount_received"] = received
    return _ok(f.supervisor.post(f"{P}/movements/{m['id']}/acknowledgement", ack), 200)


def _spend(f: FinCtx, actor: Actor, cat: str, fund_id: str, amount: str, **kw: Any) -> Any:
    body = {
        "category_id": cat,
        "description": "fuel for the site",
        "amount": amount,
        "machine_id": f.c.t.machine_id,
        "paid_from": "PETTY_CASH",
        "petty_cash_fund_id": fund_id,
        **kw,
    }
    return actor.post("/api/v1/tenant/expenses", body)


def _h(actor: Actor) -> dict[str, str]:
    return {**actor.headers(True, None), "X-Device-Id": DEVICE}


def _register(api: Api, actor: Actor) -> None:
    r = api.client.post(
        "/api/v1/sync/devices", headers=_h(actor), json={"device_id": DEVICE, "platform": "ANDROID", "app_version": "2"}
    )
    assert r.status_code == 201, r.text


def _push(api: Api, actor: Actor, ops: list[dict[str, Any]]) -> list[dict[str, Any]]:
    r = api.client.post(
        "/api/v1/sync/push", headers=_h(actor), json={"device_now": api.clock.now.isoformat(), "operations": ops}
    )
    assert r.status_code == 200, r.text
    out: list[dict[str, Any]] = r.json()["results"]
    return out


def _op(op_type: str, payload: dict[str, Any], op_id: str | None = None) -> dict[str, Any]:
    return {
        "id": op_id or str(uuid.uuid4()),
        "op_type": op_type,
        "payload": payload,
        "created_at_device": "2026-11-01T09:00:00+00:00",
        "depends_on": [],
    }


def _expense_body(f: FinCtx, api: Api, cat: str, fund_id: str, amount: str) -> dict[str, Any]:
    return {
        "category_id": cat,
        "description": "spares",
        "amount": amount,
        "incurred_at": api.clock.now.isoformat(),
        "machine_id": f.c.t.machine_id,
        "paid_from": "PETTY_CASH",
        "petty_cash_fund_id": fund_id,
    }


def _variance(f: FinCtx, source: str, fund_id: str) -> Any:
    items = _ok(f.accountant.get(f"{C}/variances", source_type=source), 200)["items"]
    return next(v for v in items if v["petty_cash_fund_id"] == fund_id)


# --- the ledger, pending vs confirmed, imprest top-ups and returns -----------------------------------------------
def test_fund_ledger_funding_spending_top_up_and_return(api: Api) -> None:
    f, cat = _setup(api)
    fund = _fund(f)
    assert fund["holder_staff_name"] == "Cash Supervisor" and D(fund["balance"]["balance"]) == 0
    fid = fund["id"]

    # Funding: proposed with the cap (limit - balance) pre-filled; nothing counts before the holder acknowledges.
    m = _ok(f.accountant.post(f"{P}/fundings", {"fund_id": fid, "kind": "FUNDING"}))
    assert (m["status"], D(m["amount"]), m["number"].startswith("PC-")) == ("PROPOSED", D(500000), True)
    _err(f.accountant.post(f"{P}/movements/{m['id']}/decision", {"approve": True}), 403, "PERMISSION_DENIED")
    _err(f.accountant.post(f"{P}/movements/{m['id']}/issue", {}), 409, "PETTY_CASH_NOT_APPROVED")
    _ok(f.owner.post(f"{P}/movements/{m['id']}/decision", {"approve": True}), 200)
    _err(f.supervisor.post(f"{P}/movements/{m['id']}/issue", {}), 403, "PERMISSION_DENIED")
    issued = _ok(f.accountant.post(f"{P}/movements/{m['id']}/issue", {"reference": "SAFE-1"}), 200)
    assert issued["status"] == "ISSUED"
    b = _bal(f.accountant, fid)
    assert (b["balance"], b["awaiting_acknowledgement"]) == (D(0), D(500000))
    ack = _ok(
        f.supervisor.post(
            f"{P}/movements/{m['id']}/acknowledgement", {"acknowledged": True, "amount_received": "490000"}
        ),
        200,
    )
    assert ack["status"] == "ACKNOWLEDGED" and ack["variance_id"]
    funding_var = _variance(f, "PETTY_CASH_FUNDING", fid)
    assert (D(funding_var["amount"]), funding_var["staff_member_id"], funding_var["counterparty_staff_id"]) == (
        D(10000),
        None,
        f.sup_staff_id,
    )
    assert _bal(f.accountant, fid)["balance"] == D(490000)
    api.clock.set_at(api.clock.now + timedelta(minutes=5))

    # Spending: auto-approved under the limit counts; pending is shown apart; above available is refused online.
    a = _ok(_spend(f, f.supervisor, cat, fid, "30000", incurred_at=api.clock.now.isoformat()))
    b2 = _ok(_spend(f, f.supervisor, cat, fid, "120000", incurred_at=api.clock.now.isoformat()))
    assert (a["status"], b2["status"], a["petty_cash_fund_id"], a["control_flags"]) == (
        "APPROVED",
        "PENDING_APPROVAL",
        fid,
        [],
    )
    b = _bal(f.accountant, fid)
    assert (b["balance"], b["pending_spending"], b["available_to_spend"]) == (D(460000), D(120000), D(340000))
    _err(
        _spend(f, f.supervisor, cat, fid, "350000", incurred_at=api.clock.now.isoformat()),
        422,
        "PETTY_CASH_INSUFFICIENT",
    )
    _err(
        _spend(f, f.supervisor, cat, fid, "10", currency="USD", incurred_at=api.clock.now.isoformat()),
        422,
        "PETTY_CASH_CURRENCY_MISMATCH",
    )
    _ok(f.manager.post(f"/api/v1/tenant/approvals/{b2['approval_request_id']}/decision", {"approve": True}), 200)
    assert _bal(f.accountant, fid)["balance"] == D(340000)

    # Imprest top-up: approved spending since the last issue (150,000), capped at limit - balance (160,000).
    api.clock.set_at(api.clock.now + timedelta(hours=1))
    sug = _ok(f.supervisor.get(f"{P}/funds/{fid}/top-up-suggestion"), 200)
    assert (D(sug["spending_since"]), D(sug["cap"]), D(sug["suggested"]), len(sug["expenses"])) == (
        D(150000),
        D(160000),
        D(150000),
        2,
    )
    req = _ok(f.supervisor.post(f"{P}/funds/{fid}/top-up-requests", {"note": "weekly refill"}))
    assert (req["kind"], D(req["amount"]), req["status"]) == ("TOP_UP", D(150000), "PROPOSED")
    assert len(_ok(f.owner.get(f"{P}/movements/{req['id']}/expenses"), 200)) == 2
    over = f.accountant.post(f"{P}/fundings", {"fund_id": fid, "kind": "TOP_UP", "amount": "20000"})
    _err(over, 422, "PETTY_CASH_ABOVE_CAP_REASON_REQUIRED")  # 150,000 already on its way: cap is 10,000
    extra = _ok(
        f.accountant.post(
            f"{P}/fundings",
            {"fund_id": fid, "kind": "TOP_UP", "amount": "20000", "above_cap_reason": "Site trip next week"},
        )
    )
    _ok(f.owner.post(f"{P}/movements/{extra['id']}/decision", {"approve": False, "note": "not needed"}), 200)
    _ok(f.owner.post(f"{P}/movements/{req['id']}/decision", {"approve": True}), 200)
    _ok(f.accountant.post(f"{P}/movements/{req['id']}/issue", {}), 200)
    _ok(f.supervisor.post(f"{P}/movements/{req['id']}/acknowledgement", {"acknowledged": True}), 200)
    assert _bal(f.accountant, fid)["balance"] == D(490000)

    # Return: claimed never reduces the balance; the office confirms what it counted (difference -> variance).
    ret = _ok(f.supervisor.post(f"{P}/returns", {"fund_id": fid, "amount": "100000", "note": "end of month"}))
    b = _bal(f.accountant, fid)
    assert (b["balance"], b["returns_claimed"], b["available_to_spend"]) == (D(490000), D(100000), D(390000))
    _err(
        f.supervisor.post(f"{P}/movements/{ret['id']}/confirmation", {"amount_received": "100000"}),
        403,
        "PERMISSION_DENIED",
    )
    conf = _ok(f.accountant.post(f"{P}/movements/{ret['id']}/confirmation", {"amount_received": "95000"}), 200)
    assert conf["status"] == "CONFIRMED" and conf["variance_id"]
    b = _bal(f.accountant, fid)
    assert (b["balance"], b["returned"], b["open_return_differences"], b["available_to_spend"]) == (
        D(395000),
        D(95000),
        D(5000),
        D(390000),
    )

    # Statement: running balance, fundings in and spending/returns out; references searchable (Find a reference).
    st = _ok(f.accountant.get(f"{P}/funds/{fid}/statement", **{"from": "2026-11-01", "to": "2026-11-01"}), 200)
    assert D(st["opening_balance"]) == 0 and D(st["closing_balance"]) == D(395000)
    assert D(st["lines"][-1]["running_balance"]) == D(395000)
    found = _ok(f.owner.get("/api/v1/tenant/lookup", reference=m["number"].lower()), 200)["matches"]
    assert [x["record_type"] for x in found] == ["petty_cash_movement"]
    assert found[0]["route"] == f"/tenant/finance/petty-cash/movements/{m['id']}"
    trx = _ok(f.accountant.get(f"{P}/funds/{fid}/transactions", figure="spent"), 200)
    assert {t["entity_id"] for t in trx} == {a["id"], b2["id"]}

    # Pending approvals list (Owner app) carries the petty cash proposals.
    _ok(f.accountant.post(f"{P}/fundings", {"fund_id": fid, "kind": "TOP_UP", "amount": "5000"}))
    pending = _ok(f.owner.get("/api/v1/tenant/accountability/pending-adjustments", all_approvals="true"), 200)
    assert any(i["record_type"] == "petty_cash_movement" for i in pending["items"])

    # Money section: petty cash held per currency; fundings never count as expenses.
    money = _ok(f.owner.get("/api/v1/tenant/overview"), 200)["money"]["currencies"]
    tzs = next(c for c in money if c["currency"] == "TZS")
    assert D(tzs["petty_cash_held"]) == D(395000) and D(tzs["approved_expenses_mtd"]) == D(150000)
    prof = _ok(
        f.owner.get(
            "/api/v1/tenant/finance/profitability", group_by="MACHINE", **{"from": "2026-11-01", "to": "2026-11-02"}
        ),
        200,
    )
    assert sum(D(r["expense_cost"]) for r in prof["rows"]) == D(150000)  # petty expenses once, fundings never


def test_count_variance_write_off_moves_the_fund_not_the_holders_custody(api: Api) -> None:
    f, _cat = _setup(api, "Count Co", "PCN-1")
    fid = _fund(f)["id"]
    _fund_and_fill(f, fid, "200000")
    count = _ok(f.supervisor.post(f"{P}/counts", {"fund_id": fid, "counted_amount": "195000", "note": "Friday"}))
    assert (D(count["expected_amount"]), D(count["difference"]), count["self_count"]) == (D(200000), D(-5000), False)
    v = _variance(f, "PETTY_CASH_COUNT", fid)
    assert v["id"] == count["variance_id"] and (D(v["amount"]), v["staff_member_id"]) == (D(5000), None)
    assert v["petty_cash_fund_name"] == "Office box BOX-1"
    # the holder is a party: never decides; write-off proposed by one person, approved by another
    _err(f.supervisor.post(f"{C}/variances/{v['id']}/write-off-proposal", {"note": "lost"}), 403, "PERMISSION_DENIED")
    _ok(f.accountant.post(f"{C}/variances/{v['id']}/write-off-proposal", {"note": "Could not be found"}), 200)
    _err(
        f.accountant.post(f"{C}/variances/{v['id']}/write-off-decision", {"approve": True}),
        422,
        "SEGREGATION_OF_DUTIES",
    )
    done = _ok(f.accountant2.post(f"{C}/variances/{v['id']}/write-off-decision", {"approve": True}), 200)
    assert (done["status"], done["outcome"]) == ("RESOLVED", "WRITTEN_OFF")
    b = _bal(f.accountant, fid)
    assert (b["balance"], b["written_off"], b["available_to_spend"]) == (D(195000), D(5000), D(195000))
    custody = _ok(f.supervisor.get(f"{C}/custody/me"), 200)
    assert all(D(c["outstanding"]) == 0 for c in custody)  # collections custody untouched
    # the variance belongs to petty cash: refused while petty cash is off
    petty_policy(f, enabled=False)
    _err(f.accountant.get(f"{C}/variances/{v['id']}"), 422, "PETTY_CASH_DISABLED")
    _err(f.accountant.get(f"{C}/variances", source_type="PETTY_CASH_COUNT"), 422, "PETTY_CASH_DISABLED")


def test_witness_and_self_count(api: Api) -> None:
    f, _ = _setup(api, "Witness Co", "PWC-1")
    petty_policy(f, count_witness_required=True)
    fid = _fund(f)["id"]
    alone = _ok(f.supervisor.post(f"{P}/counts", {"fund_id": fid, "counted_amount": "0"}))
    assert alone["self_count"] is True and alone["variance_id"] is None
    acct_user = _ok(f.owner.get("/api/v1/me"), 200)["user_id"]  # the owner witnesses (holds the count permission)
    office = _ok(f.manager.post(f"{P}/counts", {"fund_id": fid, "counted_amount": "0", "witness_user_id": acct_user}))
    assert office["self_count"] is False and office["witness_user_id"] == acct_user
    me = _ok(f.manager.get("/api/v1/me"), 200)
    _err(
        f.manager.post(f"{P}/counts", {"fund_id": fid, "counted_amount": "0", "witness_user_id": me["user_id"]}),
        422,
        "PETTY_CASH_WITNESS_INVALID",
    )


# --- segregation of duties -----------------------------------------------------------------------------------------
def test_segregation_of_duties_on_every_decision(api: Api) -> None:
    f, _cat = _setup(api, "SoD Co", "PSD-1")
    owner_staff = _ok(
        f.owner.post(
            "/api/v1/tenant/staff",
            {"full_name": "The Owner", "kind": "SUPERVISOR", "keycloak_subject": f.owner.subject},
        )
    )
    fid = _fund(f, "OWN-1", holder=owner_staff["id"])["id"]
    # the owner proposes and tries to approve their own proposal
    own = _ok(f.owner.post(f"{P}/fundings", {"fund_id": fid, "kind": "FUNDING", "amount": "1000"}))
    _err(f.owner.post(f"{P}/movements/{own['id']}/decision", {"approve": True}), 422, "SEGREGATION_OF_DUTIES")
    # someone else proposes; the holder (owner) still cannot approve or issue money into their own fund
    m = _ok(f.accountant.post(f"{P}/fundings", {"fund_id": fid, "kind": "FUNDING", "amount": "1000"}))
    _err(f.owner.post(f"{P}/movements/{m['id']}/decision", {"approve": True}), 422, "SEGREGATION_OF_DUTIES")
    # adjustments: never the proposer, never the holder
    adj = _ok(f.accountant.post(f"{P}/adjustments", {"fund_id": fid, "amount": "-500", "reason": "Counting slip"}))
    _err(f.owner.post(f"{P}/adjustments/{adj['id']}/decision", {"approve": True}), 422, "SEGREGATION_OF_DUTIES")
    _err(f.accountant.post(f"{P}/adjustments/{adj['id']}/decision", {"approve": True}), 403, "PERMISSION_DENIED")

    # a fund held by the supervisor: issue (not holder) then the issuer may not acknowledge on the holder's behalf
    sfid = _fund(f, "SUP-1")["id"]
    s = _ok(f.accountant.post(f"{P}/fundings", {"fund_id": sfid, "kind": "FUNDING", "amount": "1000"}))
    _ok(f.owner.post(f"{P}/movements/{s['id']}/decision", {"approve": True}), 200)
    _ok(f.accountant.post(f"{P}/movements/{s['id']}/issue", {}), 200)
    _err(
        f.accountant.post(f"{P}/movements/{s['id']}/acknowledgement", {"acknowledged": True}),
        422,
        "SEGREGATION_OF_DUTIES",
    )
    _ok(f.supervisor.post(f"{P}/movements/{s['id']}/acknowledgement", {"acknowledged": True}), 200)
    # return: never confirmed by the person who claimed it
    r = _ok(f.accountant.post(f"{P}/returns", {"fund_id": sfid, "amount": "100"}))  # on the holder's behalf
    _err(
        f.accountant.post(f"{P}/movements/{r['id']}/confirmation", {"amount_received": "100"}),
        422,
        "SEGREGATION_OF_DUTIES",
    )
    _ok(f.accountant2.post(f"{P}/movements/{r['id']}/confirmation", {"amount_received": "100"}), 200)
    # adjustment approved by a different person, then counted
    adj2 = _ok(f.accountant.post(f"{P}/adjustments", {"fund_id": sfid, "amount": "-50", "reason": "Coins short"}))
    _ok(f.owner.post(f"{P}/adjustments/{adj2['id']}/decision", {"approve": True}), 200)
    assert _bal(f.accountant, sfid)["balance"] == D(850)
    assert _bal(f.accountant, sfid)["adjustments"] == D(-50)


# --- overspend and the collections switch, online and offline ------------------------------------------------------
def test_overspend_and_collections_switch_online_and_offline(api: Api) -> None:
    f, cat = _setup(api, "Spend Co", "PSP-1")
    fid = _fund(f)["id"]
    _fund_and_fill(f, fid, "10000")
    _register(api, f.supervisor)
    boot = api.client.get("/api/v1/sync/bootstrap", headers=_h(f.supervisor)).json()
    assert "OP_PETTY_CASH" in boot["capabilities"]
    funds = boot["data"]["petty_cash_funds"]
    assert [x["id"] for x in funds] == [fid] and D(funds[0]["balance"]["available_to_spend"]) == D(10000)
    assert any(s["policy_type"] == "PETTY_CASH" for s in boot["policy_snapshots"])

    # offline above available: accepted, kept for approval whatever the limit, flagged; exactly once on retry
    op = _op("EXPENSE", {"client_id": str(uuid.uuid4()), **_expense_body(f, api, cat, fid, "15000")})
    first = _push(api, f.supervisor, [op])[0]
    assert first["status"] == "ACKED", first
    entity = first["result"]["entity"]
    assert (entity["status"], entity["control_flags"]) == ("PENDING_APPROVAL", ["OVERSPEND"])
    approval = _ok(f.owner.get(f"/api/v1/tenant/approvals/{entity['approval_request_id']}"), 200)
    assert "offline above" in approval["reason"]
    assert _push(api, f.supervisor, [op])[0]["status"] == "DUPLICATE"
    assert tenant_sql(f.tid, "SELECT count(*) FROM expense")[0][0] == 1
    # online the same is refused; with overspend offline switched off, the offline one is held for review
    _err(
        _spend(f, f.supervisor, cat, fid, "15000", incurred_at=api.clock.now.isoformat()),
        422,
        "PETTY_CASH_INSUFFICIENT",
    )
    petty_policy(f, overspend_allowed_offline=False)
    held = _push(
        api,
        f.supervisor,
        [_op("EXPENSE", {"client_id": str(uuid.uuid4()), **_expense_body(f, api, cat, fid, "15000")})],
    )[0]
    assert (held["status"], held["error"]["code"]) == ("CONFLICT", "PETTY_CASH_INSUFFICIENT")

    _ok(
        f.manager.post(f"/api/v1/tenant/approvals/{entity['approval_request_id']}/decision", {"approve": False}), 200
    )  # rejected: stays as evidence and never touches the fund
    assert _bal(f.accountant, fid)["available_to_spend"] == D(10000)
    # maximum per expense: always a human approval, even under the auto-approve limit
    petty_policy(f, max_expense_amount="1000")
    small = _ok(_spend(f, f.supervisor, cat, fid, "2000", incurred_at=api.clock.now.isoformat()))
    assert (small["status"], small["control_flags"]) == ("PENDING_APPROVAL", ["ABOVE_PETTY_CASH_MAXIMUM"])

    # collections: allowed by default (today's behaviour) ...
    custody = {
        "category_id": cat,
        "description": "spares",
        "amount": "1000",
        "incurred_at": api.clock.now.isoformat(),
        "paid_from": "CASH_CUSTODY",
    }
    assert _ok(f.supervisor.post("/api/v1/tenant/expenses", custody))["status"] == "APPROVED"
    # ... switched off: refused online; from sync kept for approval (never auto-approved) and flagged
    cash_policy(f, spend_from_collections_allowed=False)
    _err(f.supervisor.post("/api/v1/tenant/expenses", custody), 422, "SPENDING_FROM_COLLECTIONS_NOT_ALLOWED")
    synced = _push(api, f.supervisor, [_op("EXPENSE", {"client_id": str(uuid.uuid4()), **custody})])[0]
    assert synced["status"] == "ACKED", synced
    assert (synced["result"]["entity"]["status"], synced["result"]["entity"]["control_flags"]) == (
        "PENDING_APPROVAL",
        ["SPENT_FROM_COLLECTIONS"],
    )
    # the fund's holder is not the recorder: someone without a fund and without recording rights is refused
    cash_policy(f, recorders_may_record_for_others=False)
    staff = _ok(f.owner.post("/api/v1/tenant/staff", {"full_name": "Someone Else", "kind": "OPERATOR"}))
    else_fund = _fund(f, "ELSE", holder=staff["id"])["id"]
    _err(_spend(f, f.supervisor, cat, else_fund, "10", incurred_at=api.clock.now.isoformat()), 403, "NOT_FUND_HOLDER")


def test_offline_fund_operations_are_idempotent_and_refused_when_switched_off(api: Api) -> None:
    f, _ = _setup(api, "Sync Co", "PSY-1")
    fid = _fund(f)["id"]
    m = _ok(f.accountant.post(f"{P}/fundings", {"fund_id": fid, "kind": "FUNDING", "amount": "5000"}))
    _ok(f.owner.post(f"{P}/movements/{m['id']}/decision", {"approve": True}), 200)
    _ok(f.accountant.post(f"{P}/movements/{m['id']}/issue", {}), 200)
    _register(api, f.supervisor)
    boot = api.client.get("/api/v1/sync/bootstrap", headers=_h(f.supervisor)).json()
    assert [x["id"] for x in boot["data"]["petty_cash_awaiting"]] == [m["id"]]
    ops = [
        _op("PETTY_CASH_ACKNOWLEDGEMENT", {"movement_id": m["id"], "acknowledged": True}),
        _op("PETTY_CASH_COUNT", {"fund_id": fid, "counted_amount": "5000"}),
        _op("PETTY_CASH_RETURN", {"fund_id": fid, "amount": "1000"}),
        _op("PETTY_CASH_TOP_UP_REQUEST", {"fund_id": fid, "amount": "1000"}),
    ]
    results = _push(api, f.supervisor, ops)
    assert [r["status"] for r in results] == ["ACKED"] * 4, results
    assert [r["status"] for r in _push(api, f.supervisor, ops)] == ["DUPLICATE"] * 4
    assert tenant_sql(f.tid, "SELECT count(*) FROM petty_cash_count")[0][0] == 1
    assert tenant_sql(f.tid, "SELECT count(*) FROM petty_cash_movement WHERE kind = 'RETURN'")[0][0] == 1
    b = _bal(f.accountant, fid)
    assert (b["balance"], b["returns_claimed"]) == (D(5000), D(1000))
    petty_policy(f, enabled=False)
    off = _push(api, f.supervisor, [_op("PETTY_CASH_COUNT", {"fund_id": fid, "counted_amount": "4000"})])[0]
    assert (off["status"], off["error"]["code"]) == ("CONFLICT", "PETTY_CASH_DISABLED")
    boot = api.client.get("/api/v1/sync/bootstrap", headers=_h(f.supervisor)).json()
    assert "OP_PETTY_CASH" not in boot["capabilities"] and boot["data"]["petty_cash_funds"] == []


# --- lifecycle, holder change, deactivation ------------------------------------------------------------------------
def test_fund_lifecycle_holder_change_and_deactivation_guard(api: Api) -> None:
    f, cat = _setup(api, "Life Co", "PLC-1")
    fund = _fund(f, low_balance_level="1000")
    fid = fund["id"]
    _err(
        f.manager.post(
            f"{P}/funds", {"code": "BOX-1", "name": "dup", "holder_staff_id": f.sup_staff_id, "approved_limit": "1"}
        ),
        409,
        "DUPLICATE_PETTY_CASH_FUND",
    )
    upd = _ok(
        f.manager.put(
            f"{P}/funds/{fid}",
            {
                "code": "BOX-1",
                "name": "Main box",
                "approved_limit": "600000",
                "low_balance_level": "1000",
                "version": fund["version"],
            },
        ),
        200,
    )
    assert upd["name"] == "Main box" and upd["version"] == fund["version"] + 1
    _err(
        f.manager.put(
            f"{P}/funds/{fid}", {"code": "BOX-1", "name": "x", "approved_limit": "1", "version": fund["version"]}
        ),
        409,
        "STALE_VERSION",
    )
    listed = _ok(f.manager.get(f"{P}/funds", q="main", with_balance="false"), 200)
    assert [x["id"] for x in listed["items"]] == [fid] and listed["items"][0]["balance"] is None
    _fund_and_fill(f, fid, "3000")

    # deactivation only at zero with nothing pending
    _err(f.manager.post(f"{P}/funds/{fid}/deactivate", {"reason": "closing the box"}), 422, "PETTY_CASH_FUND_NOT_EMPTY")

    # holder change: counted at the change; the old holder stays accountable until the new one acknowledges
    sup2 = role(api, f.tid, "supervisor", "sup2-PLC-1")
    staff2 = _ok(
        f.owner.post(
            "/api/v1/tenant/staff",
            {"full_name": "Second Supervisor", "kind": "SUPERVISOR", "keycloak_subject": sup2.subject},
        )
    )
    ch = _ok(f.manager.post(f"{P}/funds/{fid}/holder-changes", {"to_staff_id": staff2["id"], "counted_amount": "3000"}))
    assert ch["status"] == "PENDING"
    _err(
        f.manager.post(f"{P}/funds/{fid}/holder-changes", {"to_staff_id": staff2["id"], "counted_amount": "3000"}),
        409,
        "PETTY_CASH_HOLDER_CHANGE_PENDING",
    )
    assert _ok(f.manager.get(f"{P}/funds/{fid}"), 200)["holder_staff_id"] == f.sup_staff_id
    assert _ok(sup2.get(f"{P}/funds/{fid}"), 200)["pending_holder_change_id"] == ch["id"]
    _err(
        f.supervisor.post(f"{P}/holder-changes/{ch['id']}/acknowledgement", {"accept": True}),
        422,
        "SEGREGATION_OF_DUTIES",
    )
    _ok(sup2.post(f"{P}/holder-changes/{ch['id']}/acknowledgement", {"accept": True}), 200)
    assert _ok(f.manager.get(f"{P}/funds/{fid}"), 200)["holder_staff_id"] == staff2["id"]
    _err(f.supervisor.get(f"{P}/funds/{fid}"), 404, "PETTY_CASH_FUND_NOT_FOUND")  # no longer theirs
    cash_policy(f, recorders_may_record_for_others=False)  # recorders may not record for someone else
    _err(_spend(f, f.supervisor, cat, fid, "10", incurred_at=api.clock.now.isoformat()), 403, "NOT_FUND_HOLDER")
    assert _ok(_spend(f, sup2, cat, fid, "100", incurred_at=api.clock.now.isoformat()))["status"] == "APPROVED"

    # pending return blocks; once confirmed and at zero the fund deactivates; then it refuses spending
    r = _ok(sup2.post(f"{P}/returns", {"fund_id": fid, "amount": "2900"}))
    _err(f.manager.post(f"{P}/funds/{fid}/deactivate", {"reason": "closing the box"}), 422, "PETTY_CASH_FUND_NOT_EMPTY")
    _ok(f.accountant.post(f"{P}/movements/{r['id']}/confirmation", {"amount_received": "2900"}), 200)
    _ok(f.accountant.post(f"{P}/fundings", {"fund_id": fid, "kind": "FUNDING", "amount": "10"}))
    _err(f.manager.post(f"{P}/funds/{fid}/deactivate", {"reason": "closing the box"}), 422, "PETTY_CASH_FUND_BUSY")
    pending = _ok(f.manager.get(f"{P}/movements", fund_id=fid, status="PROPOSED"), 200)["items"][0]
    _ok(f.owner.post(f"{P}/movements/{pending['id']}/decision", {"approve": False}), 200)
    off = _ok(f.manager.post(f"{P}/funds/{fid}/deactivate", {"reason": "closing the box"}), 200)
    assert off["is_active"] is False
    _err(_spend(f, sup2, cat, fid, "1", incurred_at=api.clock.now.isoformat()), 422, "PETTY_CASH_FUND_INACTIVE")
    assert _ok(f.manager.get(f"{P}/funds"), 200)["total"] == 0
    assert _ok(f.manager.get(f"{P}/funds", include_inactive="true"), 200)["total"] == 1
    assert _ok(f.manager.post(f"{P}/funds/{fid}/reactivate", {"reason": "reopened"}), 200)["is_active"] is True

    # employee view shows the fund held (apart from collections custody)
    view = _ok(f.owner.get(f"/api/v1/tenant/employees/{staff2['id']}/accountability"), 200)
    assert [x["fund_id"] for x in view["petty_cash_funds"]] == [fid]


# --- phase 3 advances ---------------------------------------------------------------------------------------------
def test_advances_switched_off_by_default_then_cleared_with_change(api: Api) -> None:
    f, cat = _setup(api, "Advance Co", "PAD-1")
    fid = _fund(f)["id"]
    _fund_and_fill(f, fid, "200000")
    sup2 = role(api, f.tid, "supervisor", "sup2-PAD-1")
    staff2 = _ok(
        f.owner.post(
            "/api/v1/tenant/staff", {"full_name": "Driver", "kind": "SUPERVISOR", "keycloak_subject": sup2.subject}
        )
    )
    body = {"fund_id": fid, "recipient_staff_id": staff2["id"], "amount": "40000", "purpose": "Diesel at the quarry"}
    _err(f.supervisor.post(f"{P}/advances", body), 422, "PETTY_CASH_ADVANCES_DISABLED")
    petty_policy(f, advances_enabled=True, advance_clear_within_days=2)
    _err(
        f.supervisor.post(f"{P}/advances", {**body, "recipient_staff_id": f.sup_staff_id}),
        422,
        "PETTY_CASH_ADVANCE_TO_HOLDER",
    )
    adv = _ok(f.supervisor.post(f"{P}/advances", body))
    assert adv["status"] == "OUTSTANDING" and adv["number"].startswith("PC-")
    b = _bal(f.accountant, fid)
    assert (b["balance"], b["advances_outstanding"]) == (D(160000), D(40000))
    spent = _ok(
        _spend(f, sup2, cat, fid, "30000", petty_cash_advance_id=adv["id"], incurred_at=api.clock.now.isoformat())
    )
    assert spent["status"] == "APPROVED"
    _err(
        _spend(f, sup2, cat, fid, "20000", petty_cash_advance_id=adv["id"], incurred_at=api.clock.now.isoformat()),
        422,
        "PETTY_CASH_INSUFFICIENT",
    )
    b = _bal(f.accountant, fid)
    assert (b["balance"], b["advance_spending"]) == (D(160000), D(30000))  # not deducted twice
    assert D(_ok(sup2.get(f"{P}/advances/{adv['id']}"), 200)["remaining"]) == D(10000)
    _err(sup2.post(f"{P}/advances/{adv['id']}/clearance", {"change_returned": "10000"}), 422, "SEGREGATION_OF_DUTIES")
    cleared = _ok(f.supervisor.post(f"{P}/advances/{adv['id']}/clearance", {"change_returned": "5000"}), 200)
    assert cleared["status"] == "CLEARED" and cleared["variance_id"]
    v = _variance(f, "PETTY_CASH_ADVANCE", fid)
    assert (D(v["amount"]), v["counterparty_staff_id"]) == (D(5000), staff2["id"])
    b = _bal(f.accountant, fid)
    assert (b["balance"], b["advance_change_returned"], b["advances_outstanding"]) == (D(165000), D(5000), D(0))
    money = _ok(f.owner.get("/api/v1/tenant/overview"), 200)["money"]["currencies"]
    assert D(next(c for c in money if c["currency"] == "TZS")["approved_expenses_mtd"]) == D(30000)


# --- capability off, permissions, isolation, sweep -----------------------------------------------------------------
def test_capability_off_hides_menus_and_refuses_everything(api: Api) -> None:
    f = setup_finance(api, "Off Co", "POF-1")
    cat = category(f, "SUNDRY", "Sundries")
    nav = _ok(f.owner.get("/api/v1/me"), 200)["tenants"][0]
    assert "PETTY_CASH" in nav["disabled_capabilities"]
    assert not {"tenant.petty_cash", "tenant.field.petty_cash"} & {m["key"] for m in nav["menus"]}
    _err(f.owner.get(f"{P}/funds"), 422, "PETTY_CASH_DISABLED")
    _err(
        f.manager.post(
            f"{P}/funds", {"code": "X", "name": "X", "holder_staff_id": f.sup_staff_id, "approved_limit": "1"}
        ),
        422,
        "PETTY_CASH_DISABLED",
    )
    body = {
        "category_id": cat,
        "description": "x",
        "amount": "1",
        "incurred_at": api.clock.now.isoformat(),
        "paid_from": "PETTY_CASH",
        "petty_cash_fund_id": str(uuid.uuid4()),
    }
    _err(f.supervisor.post("/api/v1/tenant/expenses", body), 422, "PETTY_CASH_DISABLED")
    reports = _ok(f.owner.get("/api/v1/tenant/reports"), 200)
    assert not {r["code"] for r in reports} & {"petty_cash_statement", "petty_cash_expenses"}
    # whoever manages funds versions the petty cash policy, and nothing else
    on = f.manager.post(
        "/api/v1/tenant/policies/PETTY_CASH/versions",
        {"scope": "TENANT", "values": {"enabled": True}, "reason": "Switch petty cash on"},
    )
    assert on.status_code == 201, on.text
    other = f.manager.post(
        "/api/v1/tenant/policies/CASH_CUSTODY/versions",
        {"scope": "TENANT", "values": {"enabled": True}, "reason": "Not theirs"},
    )
    assert other.status_code == 403, other.text
    nav = _ok(f.supervisor.get("/api/v1/me"), 200)["tenants"][0]
    assert "tenant.field.petty_cash" in {m["key"] for m in nav["menus"]}
    assert {r["code"] for r in _ok(f.owner.get("/api/v1/tenant/reports"), 200)} >= {"petty_cash_statement"}


def test_tenants_are_isolated_and_field_users_see_only_their_funds(api: Api) -> None:
    a, _ = _setup(api, "Iso A", "PIA-1")
    onboarded = api.onboard("Iso Bravo", price="1000")
    api.activate(onboarded)
    b_owner = onboarded["owner"]
    _ok(
        b_owner.post(
            "/api/v1/tenant/policies/PETTY_CASH/versions",
            {"scope": "TENANT", "values": {"enabled": True}, "reason": "Petty cash for tenant B"},
        )
    )
    b_staff = _ok(b_owner.post("/api/v1/tenant/staff", {"full_name": "B Holder", "kind": "OPERATOR"}))
    _ok(
        b_owner.post(
            f"{P}/funds", {"code": "OTHER", "name": "B box", "holder_staff_id": b_staff["id"], "approved_limit": "1"}
        )
    )
    fa = _fund(a)["id"]
    _err(b_owner.get(f"{P}/funds/{fa}"), 404, "PETTY_CASH_FUND_NOT_FOUND")
    assert tenant_sql(onboarded["tenant"]["id"], "SELECT count(*) FROM petty_cash_fund")[0][0] == 1
    assert [x["code"] for x in _ok(b_owner.get(f"{P}/funds"), 200)["items"]] == ["OTHER"]
    staff = _ok(a.owner.post("/api/v1/tenant/staff", {"full_name": "Someone Else", "kind": "OPERATOR"}))
    other = _fund(a, "ELSE", holder=staff["id"])["id"]
    assert [x["id"] for x in _ok(a.supervisor.get(f"{P}/funds"), 200)["items"]] == [fa]
    _err(a.supervisor.get(f"{P}/funds/{other}"), 404, "PETTY_CASH_FUND_NOT_FOUND")
    _err(
        a.supervisor.get("/api/v1/tenant/reports/petty_cash_statement.csv", fund_id=other),
        404,
        "PETTY_CASH_FUND_NOT_FOUND",
    )
    csv = a.supervisor.get("/api/v1/tenant/reports/petty_cash_statement.csv", fund_id=fa)
    assert csv.status_code == 200 and "Opening balance" in csv.text


def _system_sql(sql: str) -> list[Any]:
    from sqlalchemy import text

    from asseta.core.db import DbScope, apply_scope

    with get_sessionmaker().begin() as s:
        apply_scope(s, DbScope.SYSTEM, None, None)
        return list(s.execute(text(sql)).scalars())


def test_sweep_reminds_counts_due_and_low_funds(api: Api) -> None:
    f, _ = _setup(api, "Sweep Co", "PSW-1")
    petty_policy(f, count_every_days=1)
    fid = _fund(f, low_balance_level="1000")["id"]
    run_petty_cash_sweep(get_sessionmaker(), api.clock.now + timedelta(days=2))
    types = set(_system_sql("SELECT notification_type FROM notification"))
    assert {"PETTY_CASH_COUNT_OVERDUE", "PETTY_CASH_FUND_LOW"} <= types
    run_petty_cash_sweep(get_sessionmaker(), api.clock.now + timedelta(days=2))  # deduplicated per day
    once = _system_sql("SELECT count(*) FROM notification WHERE notification_type = 'PETTY_CASH_FUND_LOW'")
    assert once[0] >= 1
    assert _ok(f.accountant.get(f"{P}/funds/{fid}/balance"), 200)["next_count_due_at"] is not None


def test_balance_verification_recomputes_fund_balances(api: Api) -> None:
    f, _ = _setup(api, "Verify Co", "PVF-1")
    fid = _fund(f)["id"]
    _fund_and_fill(f, fid, "1000")
    _ok(f.supervisor.post(f"{P}/counts", {"fund_id": fid, "counted_amount": "1000"}))
    from asseta.core.db import DbScope, apply_scope
    from asseta.modules.dataprotection.balance_checks import verify_tenant
    from asseta.modules.dataprotection.balance_report import CheckKind

    with get_sessionmaker().begin() as s:
        apply_scope(s, DbScope.TENANT, uuid.UUID(f.tid), None)
        report = verify_tenant(s, uuid.UUID(f.tid), api.clock.now)
    assert report.checked[CheckKind.PETTY_CASH_FUND] == 2 and not report.findings
