"""Dashboard tiles owned by other modules (customer hours, engine hours). Each adapter imports its module lazily and
calls that module's own service, so no rule is re-implemented here and the dashboard keeps working (tile reported
unavailable) in a deployment without the module. Each returns a JSON-able dict."""

import importlib
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.modules.identity.principal import RequestContext

Tile = Callable[[Session, RequestContext, datetime], dict[str, Any]]


class TileUnavailable(Exception):
    """The module behind the tile is not part of this deployment (yet)."""


def _optional(module: str, name: str) -> Any:
    """`module.name` when that module is part of this deployment, else TileUnavailable."""
    try:
        return getattr(importlib.import_module(module), name)
    except (ImportError, AttributeError) as exc:
        raise TileUnavailable(module) from exc


def _hours_balances(s: Session) -> list[Any]:
    return list(_optional("asseta.modules.hours.service", "balances")(s))


def _sum(rows: list[Any], field: str) -> str:
    return str(sum((Decimal(getattr(r, field)) for r in rows), Decimal(0)))


def customer_hours_tile(s: Session, _: RequestContext, __: datetime) -> dict[str, Any]:
    """[3.6.2] Hours activated / consumed / remaining across customers and machines (the hours ledger)."""
    rows = _hours_balances(s)
    return {
        "customers": len({r.customer_id for r in rows}),
        "machines": len({r.machine_id for r in rows}),
        "activated": _sum(rows, "activated"),
        "consumed": _sum(rows, "consumed"),
        "remaining": _sum(rows, "remaining"),
        "awaiting_activation": _sum(rows, "awaiting_activation"),
        "expired": _sum(rows, "expired"),
        "purchases_by_status": _purchase_statuses(s),
    }


def _purchase_statuses(s: Session) -> dict[str, int]:
    """Count of open purchases per derived status (AWAITING_PAYMENT, PARTLY_ACTIVE, ...), from the hours ledger."""
    purchase = _optional("asseta.modules.hours.models", "HoursPurchase")
    totals = _optional("asseta.modules.hours.ledger", "purchase_totals_bulk")
    status_of = _optional("asseta.modules.hours.ledger", "derived_status")
    purchases = list(s.execute(select(purchase).where(purchase.cancelled_at.is_(None))).scalars())
    totals_of = totals(s, purchases)
    counts: dict[str, int] = {}
    for p in purchases:
        st = str(status_of(p, totals_of[p.id]))
        counts[st] = counts.get(st, 0) + 1
    return counts


def hours_awaiting_activation_tile(s: Session, _: RequestContext, __: datetime) -> dict[str, Any]:
    """[3.6.8] Purchased hours not yet activated (awaiting verified payment or approved credit)."""
    rows = [r for r in _hours_balances(s) if Decimal(r.awaiting_activation) > 0]
    statuses = _purchase_statuses(s)
    return {
        "count": len(rows),
        "hours": _sum(rows, "awaiting_activation"),
        "purchases_awaiting_payment": statuses.get("AWAITING_PAYMENT", 0),
        "purchases_partly_active": statuses.get("PARTLY_ACTIVE", 0),
        "items": [
            {"customer_id": str(r.customer_id), "machine_id": str(r.machine_id), "hours": str(r.awaiting_activation)}
            for r in rows[:50]
        ],
    }


def _engine_summaries(s: Session, ctx: RequestContext, now: datetime) -> list[Any]:
    service = _optional("asseta.modules.meter.engine_service", "EngineHoursService")
    return list(service(s, ctx, now).summaries(None, None))


def engine_hours_tile(s: Session, ctx: RequestContext, now: datetime) -> dict[str, Any]:
    """[3.6.3] Engine-hour reconciliation status per machine."""
    rows = _engine_summaries(s, ctx, now)
    by_status: dict[str, int] = {}
    for r in rows:
        by_status[str(r.status)] = by_status.get(str(r.status), 0) + 1
    return {
        "machines": len(rows),
        "by_status": by_status,
        "items": [r.model_dump(mode="json") for r in rows[:100]],
    }


def unexplained_hours_tile(s: Session, ctx: RequestContext, now: datetime) -> dict[str, Any]:
    """[3.6.4] Verified engine hours not yet explained, per machine (oldest open item age)."""
    rows = [r for r in _engine_summaries(s, ctx, now) if Decimal(r.totals.unexplained_hours) > 0]
    return {
        "machines": len(rows),
        "hours": str(sum((Decimal(r.totals.unexplained_hours) for r in rows), Decimal(0))),
        "value_at_risk": _value_at_risk(s, ctx, now, rows),
        "items": [
            {
                "machine_id": str(r.machine_id),
                "machine_code": r.machine_code,
                "unexplained_hours": str(r.totals.unexplained_hours),
                "oldest_open_item_days": r.oldest_open_item_days,
            }
            for r in rows
        ],
    }


def _value_at_risk(s: Session, ctx: RequestContext, now: datetime, rows: list[Any]) -> list[dict[str, str]]:
    """[DEC-032 A5] Unexplained hours x the machine category's rate card in force, per currency (machines without a
    rate card are left out)."""
    machine_model = _optional("asseta.modules.fleet.models", "Machine")
    rate_card = _optional("asseta.modules.customers.models", "RentalRatePolicy")
    amounts: dict[str, Decimal] = {}
    for r in rows:
        machine = s.get(machine_model, r.machine_id)
        if machine is None or machine.category_id is None:
            continue
        card = s.execute(
            select(rate_card)
            .where(rate_card.machine_category_id == machine.category_id, rate_card.effective_from <= now)
            .order_by(rate_card.effective_from.desc())
            .limit(1)
        ).scalar_one_or_none()
        if card is not None:
            amounts[card.currency] = amounts.get(card.currency, Decimal(0)) + Decimal(
                r.totals.unexplained_hours
            ) * Decimal(card.hourly_rate)
    return [{"currency": c, "amount": str(a.quantize(Decimal("0.01")))} for c, a in sorted(amounts.items())]


def missing_daily_reports_tile(s: Session, ctx: RequestContext, now: datetime) -> dict[str, Any]:
    """[3.6.9] Working machines without the daily operational report by the policy cut-off."""
    missing_daily_reports = _optional("asseta.modules.meter.engine_hours", "missing_daily_reports")
    assert ctx.tenant_id is not None
    rows = missing_daily_reports(s, ctx.tenant_id, now)
    return {
        "count": len(rows),
        "items": [
            {
                "machine_id": str(r.machine_id),
                "machine_code": r.machine_code,
                "day": r.day.isoformat(),
                "basis": r.basis,
            }
            for r in rows
        ],
    }


def idle_machines_tile(s: Session, ctx: RequestContext, now: datetime) -> dict[str, Any]:
    """[DEC-031 M2] Active machines with no approved machine-report hours for the tenant's days (oversight module)."""
    return dict(_optional("asseta.modules.oversight.tile", "idle_machines_tile")(s, ctx, now))


EXTERNAL_TILES: dict[str, Tile] = {
    "customer_hours": customer_hours_tile,
    "hours_awaiting_activation": hours_awaiting_activation_tile,
    "engine_hours": engine_hours_tile,
    "unexplained_hours": unexplained_hours_tile,
    "missing_daily_reports": missing_daily_reports_tile,
    "idle_machines": idle_machines_tile,
}
