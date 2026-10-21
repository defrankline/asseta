"""Gate 5 / prompt.md §10 #7 for finance capture: phones create expenses (receipts via resumable upload), cash
collections and handovers offline; on reconnection duplicates, rejections, dependency ordering (operations and
receipt uploads) and READ_ONLY quarantine still yield exactly one accepted effect with all evidence preserved."""

import hashlib
import uuid
from datetime import timedelta
from typing import Any

from tests.support.api import Actor, Api
from tests.support.finance import FinCtx, category, expense_policy, gps, setup_finance, tenant_sql
from tests.support.jobs import unique_jpeg

DEVICE = "android-cash-0001"


def _h(actor: Actor) -> dict[str, str]:
    return {**actor.headers(True, None), "X-Device-Id": DEVICE}


def _push(api: Api, actor: Actor, ops: list[dict[str, Any]]) -> list[dict[str, Any]]:
    r = api.client.post(
        "/api/v1/sync/push", headers=_h(actor), json={"device_now": api.clock.now.isoformat(), "operations": ops}
    )
    assert r.status_code == 200, r.text
    out: list[dict[str, Any]] = r.json()["results"]
    return out


def _op(op_type: str, payload: dict[str, Any], depends: list[str] | None = None) -> dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "op_type": op_type,
        "payload": payload,
        "created_at_device": "2026-11-01T09:00:00+00:00",
        "depends_on": depends or [],
    }


def _register(api: Api, f: FinCtx) -> None:
    r = api.client.post(
        "/api/v1/sync/devices",
        headers=_h(f.supervisor),
        json={"device_id": DEVICE, "platform": "ANDROID", "app_version": "1.1.0"},
    )
    assert r.status_code == 201, r.text


def _counts(f: FinCtx) -> tuple[int, ...]:
    row = tenant_sql(
        f.tid,
        "SELECT (SELECT count(*) FROM expense), (SELECT count(*) FROM expense_attachment),"
        " (SELECT count(*) FROM customer_payment), (SELECT count(*) FROM cash_handover),"
        " (SELECT count(*) FROM fuel_event)",
    )[0]
    return tuple(row)


def test_offline_expense_collection_handover_exactly_once(api: Api) -> None:
    f = setup_finance(api)
    sup = f.supervisor
    spares = category(f, "SPARES", "Spares")
    expense_policy(f, auto_approve_limit="100000")  # receipts always required, GPS required (platform default)
    _register(api, f)
    boot = api.client.get("/api/v1/sync/bootstrap", headers=_h(sup)).json()
    assert [c["code"] for c in boot["data"]["expense_categories"]] == ["SPARES"]
    assert any(s["policy_type"] == "EXPENSE_CAPTURE" for s in boot["policy_snapshots"])
    assert [(c["currency"], c["outstanding"]) for c in boot["data"]["cash_custody"]] == [("TZS", "0.0000")]

    # Receipt photo upload started while offline-ish; not yet complete.
    data = unique_jpeg()
    upload = api.client.post(
        "/api/v1/sync/blobs",
        headers=_h(sup),
        json={"sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data), "purpose": "EXPENSE_RECEIPT"},
    ).json()
    t0 = api.clock.now
    expense = _op(
        "EXPENSE",
        {
            "client_id": str(uuid.uuid4()),
            "category_id": spares,
            "description": "Hose clamp",
            "supplier": "Roadside spares",
            "amount": "40000",
            "incurred_at": t0.isoformat(),
            "job_id": f.c.job_id,
            "paid_from": "CASH_CUSTODY",
            "gps": gps(t0),
            "device_id": DEVICE,
            "receipt_upload_ids": [upload["id"]],
        },
    )
    collection = _op(
        "CASH_COLLECTION",
        {
            "client_id": str(uuid.uuid4()),
            "customer_id": f.customer_id,
            "amount": "300000",
            "received_at": t0.isoformat(),
        },
    )
    handover = _op(
        "CASH_HANDOVER",
        {"client_id": str(uuid.uuid4()), "amount": "250000", "handed_at": (t0 + timedelta(hours=1)).isoformat()},
        [collection["id"]],
    )
    no_gps = _op(
        "EXPENSE",
        {
            "client_id": str(uuid.uuid4()),
            "category_id": spares,
            "description": "Lunch",
            "amount": "5000",
            "incurred_at": t0.isoformat(),
            "paid_from": "CASH_CUSTODY",
            "receipt_upload_ids": [upload["id"]],
            "gps": {"status": "PERMISSION_DENIED"},
        },
    )
    fuel = _op(
        "FUEL_EVENT",
        {
            "client_id": str(uuid.uuid4()),
            "event_type": "USAGE",
            "litres": "12.5",
            "job_id": f.c.job_id,
            "occurred_at": t0.isoformat(),
        },
    )
    ghost = _op(
        "EXPENSE", {**expense["payload"], "client_id": str(uuid.uuid4()), "receipt_upload_ids": [str(uuid.uuid4())]}
    )
    api.clock.set_at(t0 + timedelta(hours=5))  # reconnect

    early = _push(api, sup, [handover])
    assert (early[0]["status"], early[0]["error"]["code"]) == ("DEFERRED", "DEPENDENCY_PENDING")
    first = _push(api, sup, [expense, collection, handover, no_gps, fuel, ghost])
    assert [r["status"] for r in first] == ["DEFERRED", "ACKED", "ACKED", "DEFERRED", "ACKED", "REJECTED"]
    assert first[0]["error"] == {"code": "ATTACHMENT_PENDING", "upload_ids": [upload["id"]]}
    assert first[5]["error"]["code"] == "RECEIPT_NOT_FOUND"
    assert _counts(f) == (0, 0, 1, 1, 1)  # nothing half-applied for the waiting expense

    api.client.put(f"/api/v1/sync/blobs/{upload['id']}/chunks/0", headers=_h(sup), content=data)
    done = api.client.post(f"/api/v1/sync/blobs/{upload['id']}/complete", headers=_h(sup)).json()
    assert done["status"] == "COMPLETE"
    batch = [expense, collection, handover, no_gps, fuel, ghost]
    second = _push(api, sup, batch)  # client never saw the first response: resends everything
    assert [r["status"] for r in second] == ["ACKED", "DUPLICATE", "DUPLICATE", "REJECTED", "DUPLICATE", "DUPLICATE"]
    assert second[3]["error"]["code"] == "GPS_REQUIRED"
    third = _push(api, sup, batch)
    assert [r["status"] for r in third] == ["DUPLICATE"] * 6
    assert third[3]["error"]["code"] == "GPS_REQUIRED"  # rejection is stable on replay
    assert _counts(f) == (1, 1, 1, 1, 1)  # exactly one effect per accepted operation

    e = second[0]["result"]["entity"]
    assert (e["status"], e["source"], e["receipt_attachment_ids"]) == ("APPROVED", "SYNC", [done["attachment_id"]])
    assert e["policy_version"] == "EXPENSE_CAPTURE@P1.T1"
    pay = f.accountant.get("/api/v1/tenant/customer-payments").json()["items"]
    assert [(p["status"], p["source"], p["received_by_staff_id"]) for p in pay] == [("CLAIMED", "SYNC", f.sup_staff_id)]
    changes = api.client.get("/api/v1/sync/changes", headers=_h(sup), params={"cursor": boot["cursor"]}).json()
    [custody] = changes["data"]["cash_custody"]
    assert (custody["outstanding"], custody["claimed_unverified_handovers"]) == ("260000.0000", "250000.0000")
    ops = tenant_sql(f.tid, "SELECT op_type, status FROM client_operation ORDER BY op_type, status")
    assert sorted(tuple(r) for r in ops) == sorted(
        [
            ("CASH_COLLECTION", "ACKED"),
            ("CASH_HANDOVER", "ACKED"),
            ("EXPENSE", "ACKED"),
            ("EXPENSE", "REJECTED"),
            ("EXPENSE", "REJECTED"),
            ("FUEL_EVENT", "ACKED"),
        ]
    )


def test_offline_finance_quarantined_while_read_only(api: Api) -> None:
    f = setup_finance(api)
    _register(api, f)
    sid = api.platform.get(f"/api/v1/platform/tenants/{f.tid}/subscription").json()["id"]
    today = api.clock.now.date().isoformat()
    api.platform.post(
        f"/api/v1/platform/subscriptions/{sid}/transitions",
        {"to_status": "SUSPENDED", "effective_date": today, "reason": "Non-payment"},
    )
    body = {
        "client_id": str(uuid.uuid4()),
        "customer_id": f.customer_id,
        "amount": "90000",
        "received_at": api.clock.now.isoformat(),
    }
    collection = _op("CASH_COLLECTION", body)
    q = _push(api, f.supervisor, [collection])[0]
    assert (q["status"], q["error"]["code"]) == ("QUARANTINED", "SUBSCRIPTION_READ_ONLY")
    online = f.supervisor.post("/api/v1/tenant/cash/collections", body)
    assert online.status_code == 403 and online.json()["error"]["code"] == "SUBSCRIPTION_READ_ONLY"
    assert f.accountant.get("/api/v1/tenant/customer-payments").json()["total"] == 0  # reads still allowed
    assert _push(api, f.supervisor, [collection])[0]["status"] == "DUPLICATE"  # still quarantined, kept
    api.platform.post(
        f"/api/v1/platform/subscriptions/{sid}/transitions",
        {"to_status": "ACTIVE", "effective_date": today, "reason": "Paid"},
    )
    assert _push(api, f.supervisor, [collection])[0]["status"] == "ACKED"  # applied after reactivation
    assert _push(api, f.supervisor, [collection])[0]["status"] == "DUPLICATE"
    assert _counts(f)[2] == 1
