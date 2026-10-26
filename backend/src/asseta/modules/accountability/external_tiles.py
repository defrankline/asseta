"""Dashboard tiles owned by other modules (customer hours, engine hours). Each adapter imports its module lazily and
calls that module's own service, so no rule is re-implemented here and the dashboard keeps working (tile reported
unavailable) in a deployment without the module. Each returns a JSON-able dict."""

import importlib
import uuid
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
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
        "open_overruns": _open_overruns(s),
    }


def _purchase_statuses(s: Session) -> dict[str, int]:
    """Count of open purchases per derived status (AWAITING_PAYMENT, PARTLY_ACTIVE, ...), from the hours ledger."""
    purchase = _optional("asseta.modules.hours.models", "HoursPurchase")
    totals = _optional("asseta.modules.hours.ledger", "purchase_totals")
    status_of = _optional("asseta.modules.hours.ledger", "derived_status")
    counts: dict[str, int] = {}
    for p in s.execute(select(purchase).where(purchase.cancelled_at.is_(None))).scalars():
        st = str(status_of(p, totals(s, p)))
        counts[st] = counts.get(st, 0) + 1
    return counts


def _open_overruns(s: Session) -> int:
    """Open HOURS_OVERRUN exceptions: prepaid work beyond the activated hours, awaiting a controlled outcome."""
    from asseta.modules.meter.models import ExceptionStatus, JobException

    overrun = getattr(_optional("asseta.modules.meter.models", "ExceptionType"), "HOURS_OVERRUN", None)
    if overrun is None:
        raise TileUnavailable("HOURS_OVERRUN")
    stmt = select(func.count()).where(
        JobException.exception_type == overrun, JobException.status == ExceptionStatus.OPEN
    )
    return int(s.execute(stmt).scalar_one())


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
                "job_id": str(r.job_id) if isinstance(r.job_id, uuid.UUID) else None,
            }
            for r in rows
        ],
    }


def revenue_differences_tile(s: Session, ctx: RequestContext, now: datetime) -> dict[str, Any]:
    """[DEC-031 R3] Revenue differences to explain / decide (revenue module)."""
    return dict(_optional("asseta.modules.revenue.tile", "revenue_differences_tile")(s, ctx, now))


def unbilled_work_tile(s: Session, ctx: RequestContext, now: datetime) -> dict[str, Any]:
    """[DEC-031 M2] Completed, billing-ready jobs not invoiced after the tenant's days (oversight module)."""
    return dict(_optional("asseta.modules.oversight.tile", "unbilled_work_tile")(s, ctx, now))


def idle_machines_tile(s: Session, ctx: RequestContext, now: datetime) -> dict[str, Any]:
    """[DEC-031 M2] Active machines with no job and no engine hours for the tenant's days (oversight module)."""
    return dict(_optional("asseta.modules.oversight.tile", "idle_machines_tile")(s, ctx, now))


EXTERNAL_TILES: dict[str, Tile] = {
    "customer_hours": customer_hours_tile,
    "hours_awaiting_activation": hours_awaiting_activation_tile,
    "engine_hours": engine_hours_tile,
    "unexplained_hours": unexplained_hours_tile,
    "missing_daily_reports": missing_daily_reports_tile,
    "revenue_differences": revenue_differences_tile,
    "unbilled_work": unbilled_work_tile,
    "idle_machines": idle_machines_tile,
}
