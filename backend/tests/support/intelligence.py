"""Gate 6 helpers: run the intelligence sweep / event handler as the worker does (application role, tenant RLS
scope), set FRAUD_CONTROLS thresholds through the API, and read signals/cases."""

import uuid
from typing import Any

from asseta.core.db import DbScope, apply_scope, get_sessionmaker
from asseta.modules.intelligence.sweep import IntelligenceSweepResult, handle_event, sweep_tenant
from tests.support.api import Actor, Api
from tests.support.notify import sql

INTEL_EVENTS = ("ExpenseSubmitted", "TrackingAlertRaised", "MeterExceptionRaised", "SegregationOfDutiesViolation")


def sweep(api: Api, tid: str) -> IntelligenceSweepResult:
    with get_sessionmaker().begin() as s:
        apply_scope(s, DbScope.TENANT, uuid.UUID(tid), None)
        return sweep_tenant(s, uuid.UUID(tid), api.clock.now)


def feed_events(api: Api, tid: str) -> int:
    """Kafka stand-in for the intelligence consumer: every relevant outbox event of the tenant, in order."""
    rows = sql(
        "SELECT id, event_type, payload FROM outbox_event WHERE tenant_id = :t AND event_type = ANY(:types)"
        " ORDER BY created_at, id",
        t=tid,
        types=list(INTEL_EVENTS),
    )
    for r in rows:
        with get_sessionmaker().begin() as s:
            apply_scope(s, DbScope.TENANT, uuid.UUID(tid), None)
            handle_event(s, uuid.UUID(tid), api.clock.now, r.id, r.event_type, r.payload)
    return len(rows)


def fraud_policy(owner: Actor, scope: str = "TENANT", ref: str | None = None, **values: Any) -> None:
    body: dict[str, Any] = {"scope": scope, "values": values, "reason": "Owner risk thresholds"}
    if ref:
        body["scope_ref_id"] = ref
    r = owner.post("/api/v1/tenant/policies/FRAUD_CONTROLS/versions", body)
    assert r.status_code == 201, r.text


def signals(actor: Actor, **params: Any) -> list[dict[str, Any]]:
    r = actor.get("/api/v1/tenant/risk-signals", page_size=200, **params)
    assert r.status_code == 200, r.text
    items: list[dict[str, Any]] = r.json()["items"]
    return items


def cases(actor: Actor, **params: Any) -> list[dict[str, Any]]:
    r = actor.get("/api/v1/tenant/cases", page_size=200, **params)
    assert r.status_code == 200, r.text
    items: list[dict[str, Any]] = r.json()["items"]
    return items


def receipt(api: Api, actor: Actor, content: bytes) -> str:
    r = api.client.post(
        "/api/v1/tenant/attachments",
        headers=actor.headers(True, None),
        files={"file": ("r.jpg", content, "image/jpeg")},
        data={"purpose": "EXPENSE_RECEIPT"},
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


def expense(api: Api, actor: Actor, category_id: str, amount: str, **extra: Any) -> dict[str, Any]:
    body = {
        "category_id": category_id,
        "description": "Spare parts",
        "amount": amount,
        "incurred_at": api.clock.now.isoformat(),
        "paid_from": "COMPANY",
        **extra,
    }
    r = actor.post("/api/v1/tenant/expenses", body)
    assert r.status_code == 201, r.text
    out: dict[str, Any] = r.json()
    return out
