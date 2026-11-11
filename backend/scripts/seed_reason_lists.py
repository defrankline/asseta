#!/usr/bin/env python
"""Add one company's starter reason lists (customer hours, engine hours, cash, revenue) from a JSON file.

Run through scripts/seed-reason-lists.sh. Without --yes it only prints what would be added. Entries already there are
skipped, active or not: customer-hour, engine-hour and revenue reasons by list and code (any capitals), cash reasons by
list and label (they have no code). A second run adds nothing. Each new entry gets an audit event, all in one
transaction. Nothing existing is changed or deactivated.

File format (deploy/reason-lists.example.json; every section is optional):
    {"customer_hours": {"DISCOUNT": [{"code": "LOYAL_CUSTOMER", "label": "Long-standing customer"}], ...},
     "engine_hours": {"NON_CUSTOMER_CATEGORY": [{"code": "MAINTENANCE", "label": "Maintenance and servicing"}], ...},
     "cash": {"VARIANCE": [{"label": "Counting error"}], ...},
     "revenue": [{"code": "ON_CREDIT", "label": "On credit, not yet paid", "description": "optional"}]}
"""

import argparse
import json
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

import asseta.core.model_registry  # noqa: F401
from asseta.core.audit import AuditActor, AuditService
from asseta.core.config import get_settings
from asseta.core.db import utcnow
from asseta.modules.finance.custody_models import CashReason, CashReasonKind
from asseta.modules.hours.models import HoursReasonCode, ReasonKind
from asseta.modules.meter.engine_models import EngineHourReason, EngineHourReasonKind
from asseta.modules.revenue.models import RevenueReason

NIL_TENANT = uuid.UUID(int=0)
CODE_MAX, DESCRIPTION_MAX = 32, 500
LABEL_MAX = {"customer_hours": 200, "engine_hours": 120, "cash": 120, "revenue": 120}
KINDS: dict[str, frozenset[str]] = {
    "customer_hours": frozenset(k.value for k in ReasonKind),
    "engine_hours": frozenset(k.value for k in EngineHourReasonKind),
    "cash": frozenset(k.value for k in CashReasonKind),
}
TITLES = {
    "customer_hours": "Customer-hours reasons",
    "engine_hours": "Engine-hour reasons",
    "cash": "Cash reasons",
    "revenue": "Revenue reasons",
}


class Refuse(Exception):
    """Stops the run with a plain message; nothing has been changed."""


@dataclass(frozen=True)
class Entry:
    section: str
    kind: str | None  # None for revenue reasons (one list)
    code: str | None  # None for cash reasons (matched by label)
    label: str
    description: str | None

    @property
    def key(self) -> tuple[str, str | None, str]:
        return (self.section, self.kind, (self.code or self.label).casefold())


def _entries(section: str, kind: str | None, items: Any) -> list[Entry]:
    where = f"{section}.{kind}" if kind else section
    if not isinstance(items, list) or not items:
        raise Refuse(f"{where} needs a non-empty list")
    out = []
    for item in items:
        if not isinstance(item, dict):
            raise Refuse(f"{where}: every entry is an object: {item!r}")
        label = item.get("label")
        if not isinstance(label, str) or len(label.strip()) < 2 or len(label.strip()) > LABEL_MAX[section]:
            raise Refuse(f'{where}: every entry needs a "label" of 2 to {LABEL_MAX[section]} characters: {item!r}')
        code = item.get("code")
        if section != "cash" and (not isinstance(code, str) or not code.strip() or len(code.strip()) > CODE_MAX):
            raise Refuse(f'{where}: every entry needs a "code" of 1 to {CODE_MAX} characters: {label.strip()}')
        description = item.get("description")
        if description is not None and (not isinstance(description, str) or len(description) > DESCRIPTION_MAX):
            raise Refuse(f'{where}: "description" must be text of at most {DESCRIPTION_MAX} characters: {label}')
        clean_code = code.strip() if section != "cash" and isinstance(code, str) else None
        out.append(Entry(section, kind, clean_code, label.strip(), description))
    return out


def read_file(path: Path) -> list[Entry]:
    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise Refuse(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise Refuse(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise Refuse("the file must be a JSON object")
    unknown = set(raw) - {*TITLES, "_comment"}
    if unknown:
        raise Refuse(f"unknown section(s): {', '.join(sorted(unknown))}; known: {', '.join(TITLES)}")
    out: list[Entry] = []
    for section, kinds in KINDS.items():
        lists = raw.get(section)
        if lists is None:
            continue
        if not isinstance(lists, dict):
            raise Refuse(f"{section} must map a list name to its entries")
        for kind, items in lists.items():
            if kind not in kinds:
                raise Refuse(f"{section}: unknown list {kind}; known: {', '.join(sorted(kinds))}")
            out += _entries(section, kind, items)
    if "revenue" in raw:
        out += _entries("revenue", None, raw["revenue"])
    if not out:
        raise Refuse("the file holds no reasons")
    seen: set[tuple[str, str | None, str]] = set()
    for e in out:
        if e.key in seen:
            raise Refuse(f"the file lists {e.code or e.label} twice in {e.section}{'.' + e.kind if e.kind else ''}")
        seen.add(e.key)
    return out


def find_tenant(session: Session, registration_number: str | None, tenant_id: str | None) -> tuple[uuid.UUID, str]:
    if tenant_id:
        try:
            parsed = uuid.UUID(tenant_id)
        except ValueError as exc:
            raise Refuse(f"not a tenant id: {tenant_id}") from exc
        rows = session.execute(text("SELECT id, display_name FROM tenant WHERE id = :v"), {"v": parsed}).all()
    else:
        rows = session.execute(
            text("SELECT id, display_name FROM tenant WHERE lower(trim(registration_number)) = lower(trim(:v))"),
            {"v": registration_number},
        ).all()
    if not rows:
        raise Refuse("no such tenant")
    if len(rows) > 1:
        raise Refuse("more than one tenant matches; use --tenant-id")
    if rows[0][0] == NIL_TENANT:
        raise Refuse("refusing the platform scope: this script only adds one company's reason lists")
    return rows[0][0], rows[0][1]


def existing_keys(session: Session) -> set[tuple[str, str | None, str]]:
    keys: set[tuple[str, str | None, str]] = set()
    for kind, code in session.execute(text("SELECT kind, code FROM hours_reason_code")).all():
        keys.add(("customer_hours", str(kind), str(code).casefold()))
    for kind, code in session.execute(text("SELECT kind, code FROM engine_hour_reason")).all():
        keys.add(("engine_hours", str(kind), str(code).casefold()))
    for kind, label in session.execute(text("SELECT kind, label FROM cash_reason")).all():
        keys.add(("cash", str(kind), str(label).casefold()))
    for (code,) in session.execute(text("SELECT code FROM revenue_reason")).all():
        keys.add(("revenue", None, str(code).casefold()))
    return keys


def add(session: Session, audit: AuditService, actor: AuditActor, tid: uuid.UUID, e: Entry, reason: str) -> None:
    row: Any
    kind, code = str(e.kind), str(e.code)  # a list name for every list section; a code for all but cash
    if e.section == "customer_hours":
        row = HoursReasonCode(
            id=uuid.uuid4(), tenant_id=tid, kind=ReasonKind(kind), code=code, label=e.label, created_at=utcnow()
        )
        action, entity = "hours.reason_code.created", "hours_reason_code"
    elif e.section == "engine_hours":
        row = EngineHourReason(
            id=uuid.uuid4(),
            tenant_id=tid,
            kind=EngineHourReasonKind(kind),
            code=code,
            name=e.label,
            description=e.description,
            is_active=True,
        )
        action, entity = "meter.reason.created", "engine_hour_reason"
    elif e.section == "cash":
        row = CashReason(
            id=uuid.uuid4(), tenant_id=tid, kind=CashReasonKind(kind), label=e.label, description=e.description
        )
        action, entity = "finance.cash_reason.created", "cash_reason"
    else:
        row = RevenueReason(id=uuid.uuid4(), tenant_id=tid, code=code, name=e.label, description=e.description)
        action, entity = "revenue.reason.created", "revenue_reason"
    session.add(row)
    session.flush()
    after = {"list": e.kind, "code": e.code, "label": e.label, "description": e.description}
    audit.record(
        actor=actor,
        action=action,
        entity_type=entity,
        entity_id=row.id,
        tenant_id=tid,
        after={k: v for k, v in after.items() if v is not None},
        reason=reason,
    )


def run(path: Path, registration_number: str | None, tenant_id: str | None, yes: bool, operator: str) -> int:
    wanted = read_file(path)
    engine = create_engine(get_settings().migration_database_url)
    with Session(engine) as session, session.begin():
        session.execute(text("SELECT set_config('app.scope', 'system', true)"))
        tid, name = find_tenant(session, registration_number, tenant_id)
        session.execute(
            text("SELECT set_config('app.scope', 'tenant', true), set_config('app.tenant_id', :t, true)"),
            {"t": str(tid)},
        )
        have = existing_keys(session)
        new = [e for e in wanted if e.key not in have]
        print(f"Company: {name} ({tid})")
        print(f"Already there, skipped: {len(wanted) - len(new)}")
        for section, title in TITLES.items():
            mine = [e for e in new if e.section == section]
            if mine:
                print(f"  {title}:")
            for e in mine:
                print(f"    + {(e.kind + ': ') if e.kind else ''}{e.label}{f' ({e.code})' if e.code else ''}")
        if not new:
            print("Nothing to add.")
            return 0
        if not yes:
            session.rollback()
            print(f"\nDRY RUN: {len(new)} reason(s) would be added. Add --yes to add them.")
            return 0
        audit = AuditService(session)
        actor = AuditActor(user_id=None, roles=["platform-operator-script"], source="script")
        for e in new:
            add(session, audit, actor, tid, e, f"Seeded from a file (by {operator})")
    print(f"\nADDED: {len(new)} reason(s), with audit events. The company can rename or deactivate any of them.")
    return 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    who = p.add_mutually_exclusive_group(required=True)
    who.add_argument("--registration-number")
    who.add_argument("--tenant-id")
    p.add_argument("--file", required=True, type=Path, help="JSON file with the reason lists")
    p.add_argument("--yes", action="store_true", help="really add them (otherwise a dry run that changes nothing)")
    p.add_argument("--operator", default="operator", help="who runs it (recorded with the audit events)")
    args = p.parse_args(argv)
    try:
        return run(args.file, args.registration_number, args.tenant_id, args.yes, args.operator)
    except Refuse as exc:
        print(f"REFUSED: {exc}. Nothing was changed.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
