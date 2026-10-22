"""Shared report definitions (R1-I "essential reports"; no arbitrary report builder). A definition names the
columns (label + value kind) and the permission; its row source reuses the SAME query, filters and sort as the
module's list endpoint, so an export always matches what the screen lists for the same filters."""

import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel
from sqlalchemy.orm import Session

from asseta.modules.identity.catalog import PermissionScope
from asseta.modules.identity.principal import RequestContext

Kind = Literal["text", "int", "money", "decimal", "instant", "date", "bool"]
NUMERIC: frozenset[Kind] = frozenset({"int", "money", "decimal"})
MONEY_SCALE = Decimal("0.0001")  # same textual form as the JSON API (`Money`)
CSV_ROW_CAP = 10_000
PDF_ROW_CAP = 2_000


@dataclass(frozen=True)
class ReportColumn:
    key: str
    label: str
    kind: Kind = "text"
    width: float = 1.0  # relative PDF column width


@dataclass(frozen=True)
class ReportEnv:
    """Rendering context: tenant-local timezone for instants, header metadata."""

    timezone: str
    owner_name: str  # tenant display name, or "Asseta platform"
    generated_at: datetime
    generated_by: str


@dataclass
class ReportRows:
    rows: list[dict[str, Any]]
    truncated: bool


# A row source returns at most `limit + 1` rows so the caller can tell that the cap truncated the result.
RowSource = Callable[[Session, RequestContext, datetime, BaseModel, int], list[dict[str, Any]]]


@dataclass(frozen=True)
class ReportDefinition:
    code: str
    title: str
    description: str
    scope: PermissionScope
    permission: str  # the list endpoint's permission
    columns: tuple[ReportColumn, ...]
    source: RowSource
    filters: type[BaseModel]
    list_operation: str  # operationId of the list endpoint the rows come from
    landscape: bool = True
    notes: tuple[str, ...] = field(default_factory=tuple)

    def fetch(self, session: Session, ctx: RequestContext, now: datetime, filters: BaseModel, cap: int) -> ReportRows:
        rows = self.source(session, ctx, now, filters, cap)
        return ReportRows(rows[:cap], len(rows) > cap)


def applied_filters(filters: BaseModel) -> dict[str, str]:
    """Non-empty filters as display strings (header line, audit record)."""
    out: dict[str, str] = {}
    for key, value in filters.model_dump().items():
        if value is None or value is False or value == "":
            continue
        out[key] = value.value if isinstance(value, Enum) else str(value)
    return out


def format_value(value: Any, kind: Kind, tz: str, human: bool = False) -> str:
    """One cell as text. Machine form (CSV): ISO instants in the tenant timezone with offset, money at the API's
    4-decimal scale. Human form (PDF): `YYYY-MM-DD HH:MM`, grouped amounts with 2 decimals."""
    if value is None:
        return ""
    if isinstance(value, Enum):
        value = value.value
    if kind == "instant" and isinstance(value, datetime):
        local = value.astimezone(ZoneInfo(tz))
        return local.strftime("%Y-%m-%d %H:%M") if human else local.isoformat(timespec="seconds")
    if kind == "date" and isinstance(value, date):
        return value.isoformat()
    if kind == "bool":
        return "Yes" if value else "No"
    if kind == "money":
        amount = Decimal(value)
        return f"{amount:,.2f}" if human else format(amount.quantize(MONEY_SCALE), "f")
    if kind == "decimal":
        amount = Decimal(str(value))
        return f"{amount:,}" if human else format(amount, "f")
    if kind == "int":
        return str(int(value))
    if isinstance(value, uuid.UUID):
        return str(value)
    return str(value)


def names(rows: Mapping[uuid.UUID, str], key: uuid.UUID | None) -> str | None:
    return rows.get(key) if key is not None else None
