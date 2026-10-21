"""Case-insensitive substring search shared by list endpoints (`q` query param)."""

from typing import Any

from sqlalchemy import ColumnElement, or_
from sqlalchemy.orm import QueryableAttribute

ESCAPE = "\\"


def normalize_q(q: str | None) -> str | None:
    """Strip the search text; blank or whitespace-only means "no filter"."""
    q = (q or "").strip()
    return q or None


def like_pattern(q: str) -> str:
    """`%q%` with the LIKE wildcards (`%`, `_`) and the escape char in the user text matched literally."""
    escaped = q.replace(ESCAPE, ESCAPE * 2).replace("%", ESCAPE + "%").replace("_", ESCAPE + "_")
    return f"%{escaped}%"


def ilike_any(q: str | None, *cols: QueryableAttribute[Any]) -> ColumnElement[bool] | None:
    """OR of escaped ILIKE `%q%` over `cols`, or None when `q` is blank (caller adds no filter)."""
    term = normalize_q(q)
    if term is None:
        return None
    pattern = like_pattern(term)
    return or_(*[c.ilike(pattern, escape=ESCAPE) for c in cols])


def matches(q: str | None, *values: str | None) -> bool:
    """In-memory counterpart of `ilike_any` for data not held in SQL (e.g. IdP users): casefolded substring."""
    term = normalize_q(q)
    if term is None:
        return True
    needle = term.casefold()
    return any(needle in v.casefold() for v in values if v)
