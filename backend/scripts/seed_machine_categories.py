#!/usr/bin/env python
"""Add one company's machine types (categories) from a JSON file.

Run through scripts/seed-machine-categories.sh. Without --yes it only prints what would be added. Names that already
exist, active or not and in any capitals, are skipped, so a second run adds nothing. Each new type gets an audit event,
all in one transaction. No rates are created: hourly rates stay a decision for the company.

File format:
    {"categories": [{"name": "Excavator - Crawler", "description": "Tracked excavator"}, {"name": "Forklift"}]}
"""

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

import asseta.core.model_registry  # noqa: F401
from asseta.core.audit import AuditActor, AuditService
from asseta.core.config import get_settings
from asseta.modules.fleet.models import MachineCategory

NIL_TENANT = uuid.UUID(int=0)
NAME_MAX, DESCRIPTION_MAX = 100, 300


class Refuse(Exception):
    """Stops the run with a plain message; nothing has been changed."""


def read_file(path: Path) -> list[tuple[str, str | None]]:
    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise Refuse(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise Refuse(f"{path} is not valid JSON: {exc}") from exc
    items = raw.get("categories") if isinstance(raw, dict) else None
    if not isinstance(items, list) or not items:
        raise Refuse('the file needs a non-empty "categories" list')
    out: list[tuple[str, str | None]] = []
    seen: set[str] = set()
    for item in items:
        name = item.get("name") if isinstance(item, dict) else None
        if not isinstance(name, str) or not name.strip() or len(name.strip()) > NAME_MAX:
            raise Refuse(f'every category needs a "name" of 1 to {NAME_MAX} characters: {item!r}')
        description = item.get("description")
        if description is not None and (not isinstance(description, str) or len(description) > DESCRIPTION_MAX):
            raise Refuse(f'"description" must be text of at most {DESCRIPTION_MAX} characters: {name}')
        key = name.strip().casefold()
        if key in seen:
            raise Refuse(f"the file lists {name.strip()} twice")
        seen.add(key)
        out.append((name.strip(), description))
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
        raise Refuse("refusing the platform scope: this script only adds one company's machine types")
    return rows[0][0], rows[0][1]


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
        existing = {str(n).casefold() for n in session.execute(text("SELECT name FROM machine_category")).scalars()}
        new = [w for w in wanted if w[0].casefold() not in existing]
        print(f"Company: {name} ({tid})")
        print(f"Already there, skipped: {len(wanted) - len(new)}")
        for cat_name, _ in new:
            print(f"  + {cat_name}")
        if not new:
            print("Nothing to add.")
            return 0
        if not yes:
            session.rollback()
            print(f"\nDRY RUN: {len(new)} machine type(s) would be added. Add --yes to add them.")
            return 0
        audit = AuditService(session)
        actor = AuditActor(user_id=None, roles=["platform-operator-script"], source="script")
        for cat_name, description in new:
            cat = MachineCategory(id=uuid.uuid4(), tenant_id=tid, name=cat_name, description=description)
            session.add(cat)
            session.flush()
            audit.record(
                actor=actor,
                action="fleet.category.created",
                entity_type="machine_category",
                entity_id=cat.id,
                tenant_id=tid,
                after={"name": cat_name, "description": description},
                reason=f"Seeded from a file (by {operator})",
            )
    print(f"\nADDED: {len(new)} machine type(s), with audit events. Hourly rates are still to be set.")
    return 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    who = p.add_mutually_exclusive_group(required=True)
    who.add_argument("--registration-number")
    who.add_argument("--tenant-id")
    p.add_argument("--file", required=True, type=Path, help="JSON file with the machine types")
    p.add_argument("--yes", action="store_true", help="really add them (otherwise a dry run that changes nothing)")
    p.add_argument("--operator", default="operator", help="who runs it (recorded with the audit event)")
    args = p.parse_args(argv)
    try:
        return run(args.file, args.registration_number, args.tenant_id, args.yes, args.operator)
    except Refuse as exc:
        print(f"REFUSED: {exc}. Nothing was changed.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
