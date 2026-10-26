"""Display names next to ids on approval, queue and list DTOs (names, not ids). Batched: one `IN` query per kind of
record for a whole response (never one query per row), in the caller's RLS scope.

A DTO opts in by declaring nullable name fields next to its id fields; the convention is mechanical:

- `<x>_by` (a user id)            -> `<x>_by_name`             (the user's display name)
- `<x>staff_id` / `staff_member_id` -> `<x>staff_name` / `staff_member_name` (the staff member's full name)
- `<x>customer_id`                -> `<x>customer_name`
- `<x>machine_id`                 -> `<x>machine_name` and `<x>machine_code` (asset code)
- `<x>job_site_id` / `<x>site_id` -> `<x>job_site_name` / `<x>site_name`
- `<x>job_id`                     -> `<x>job_number`
- `<x>purchase_id`                -> `<x>purchase_number` (customer hours purchase) and `customer_name`
- `<x>deposit_account_id`         -> `<x>deposit_account_name` (company deposit account)

Only empty (None) name fields are filled, so a DTO that already carries a name keeps it."""

import functools
import uuid
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from asseta.modules.finance.deposit_models import CompanyDepositAccount
from asseta.modules.fleet.models import Machine, StaffMember
from asseta.modules.geospatial.models import JobSite
from asseta.modules.hours.models import HoursPurchase
from asseta.modules.identity.models import AppUser
from asseta.modules.jobs.models import Customer, Job

# kind -> loader(session, ids) -> {id: {target suffix: value}}
_Loader = Callable[[Session, set[uuid.UUID]], dict[uuid.UUID, dict[str, str]]]


def _pairs(session: Session, cols: tuple[Any, ...], key: Any, ids: set[uuid.UUID]) -> list[Any]:
    return list(session.execute(select(key, *cols).where(key.in_(ids))).all())


def _users(s: Session, ids: set[uuid.UUID]) -> dict[uuid.UUID, dict[str, str]]:
    return {i: {"name": n} for i, n in _pairs(s, (AppUser.display_name,), AppUser.id, ids)}


def _staff(s: Session, ids: set[uuid.UUID]) -> dict[uuid.UUID, dict[str, str]]:
    return {i: {"name": n} for i, n in _pairs(s, (StaffMember.full_name,), StaffMember.id, ids)}


def _customers(s: Session, ids: set[uuid.UUID]) -> dict[uuid.UUID, dict[str, str]]:
    return {i: {"name": n} for i, n in _pairs(s, (Customer.name,), Customer.id, ids)}


def _machines(s: Session, ids: set[uuid.UUID]) -> dict[uuid.UUID, dict[str, str]]:
    return {i: {"name": n, "code": c} for i, n, c in _pairs(s, (Machine.name, Machine.asset_code), Machine.id, ids)}


def _sites(s: Session, ids: set[uuid.UUID]) -> dict[uuid.UUID, dict[str, str]]:
    return {i: {"name": n} for i, n in _pairs(s, (JobSite.name,), JobSite.id, ids)}


def _jobs(s: Session, ids: set[uuid.UUID]) -> dict[uuid.UUID, dict[str, str]]:
    return {i: {"number": n} for i, n in _pairs(s, (Job.job_number,), Job.id, ids)}


def _purchases(s: Session, ids: set[uuid.UUID]) -> dict[uuid.UUID, dict[str, str]]:
    rows = s.execute(
        select(HoursPurchase.id, HoursPurchase.purchase_number, Customer.name)
        .join(Customer, Customer.id == HoursPurchase.customer_id)
        .where(HoursPurchase.id.in_(ids))
    ).all()
    return {i: {"number": n, "customer": c} for i, n, c in rows}


def _deposit_accounts(s: Session, ids: set[uuid.UUID]) -> dict[uuid.UUID, dict[str, str]]:
    return {i: {"name": n} for i, n in _pairs(s, (CompanyDepositAccount.name,), CompanyDepositAccount.id, ids)}


LOADERS: dict[str, _Loader] = {
    "user": _users,
    "staff": _staff,
    "customer": _customers,
    "machine": _machines,
    "site": _sites,
    "job": _jobs,
    "purchase": _purchases,
    "deposit_account": _deposit_accounts,
}


def _rule(field: str) -> tuple[str, dict[str, str]] | None:
    """(kind, {loader value key: target field}) for an id field, or None when it names nothing."""
    if field.endswith("_by"):
        return "user", {"name": f"{field}_name"}
    if not field.endswith("_id"):
        return None
    stem = field.removesuffix("_id")
    if stem.endswith("staff") or stem == "staff_member":
        return "staff", {"name": f"{stem}_name"}
    if stem.endswith("customer"):
        return "customer", {"name": f"{stem}_name"}
    if stem.endswith("machine"):
        return "machine", {"name": f"{stem}_name", "code": f"{stem}_code"}
    if stem.endswith("site"):
        return "site", {"name": f"{stem}_name"}
    if stem.endswith("job"):
        return "job", {"number": f"{stem}_number"}
    if stem.endswith("deposit_account"):
        return "deposit_account", {"name": f"{stem}_name"}
    if stem.endswith("purchase"):
        return "purchase", {"number": f"{stem}_number", "customer": "customer_name"}
    return None


@functools.cache
def _spec(cls: type[BaseModel]) -> tuple[tuple[str, str, tuple[tuple[str, str], ...]], ...]:
    """Per DTO class: (id field, kind, ((value key, name field), ...)) for every id field with a declared name."""
    fields = cls.model_fields
    out = []
    for name in fields:
        rule = _rule(name)
        if rule is None:
            continue
        kind, targets = rule
        present = tuple((k, t) for k, t in targets.items() if t in fields)
        if present:
            out.append((name, kind, present))
    return tuple(out)


def _walk(obj: Any, found: list[BaseModel]) -> None:
    if isinstance(obj, BaseModel):
        found.append(obj)
        for name in type(obj).model_fields:
            value = getattr(obj, name, None)
            if isinstance(value, BaseModel | list):
                _walk(value, found)
    elif isinstance(obj, list):
        for item in obj:
            _walk(item, found)


def _as_uuid(value: Any) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    if isinstance(value, str):
        try:
            return uuid.UUID(value)
        except ValueError:
            return None
    return None


def fill_names[T](session: Session, result: T) -> T:
    """Fill the display-name fields of `result` (a DTO, a page of DTOs or a list) in one query per kind."""
    models: list[BaseModel] = []
    _walk(result, models)
    wanted: dict[str, set[uuid.UUID]] = defaultdict(set)
    jobs: list[tuple[BaseModel, uuid.UUID, str, tuple[tuple[str, str], ...]]] = []
    for m in models:
        for field, kind, targets in _spec(type(m)):
            ident = _as_uuid(getattr(m, field))
            if ident is None or all(getattr(m, t) is not None for _, t in targets):
                continue
            wanted[kind].add(ident)
            jobs.append((m, ident, kind, targets))
    if not jobs:
        return result
    found = {kind: LOADERS[kind](session, ids) for kind, ids in wanted.items()}
    for m, ident, kind, targets in jobs:
        values = found[kind].get(ident)
        if values is None:
            continue
        for key, target in targets:
            if getattr(m, target) is None and key in values:
                setattr(m, target, values[key])
    return result


def named[**P, R](fn: Callable[P, R]) -> Callable[P, R]:
    """Endpoint decorator: fills display names on the response using the endpoint's `session` argument."""

    @functools.wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        result = fn(*args, **kwargs)
        session = kwargs.get("session")
        if isinstance(session, Session):
            fill_names(session, result)
        return result

    return wrapper
