#!/usr/bin/env python
"""Add the starting machine-report reasons (ADR-008 §2) to companies created before machine reports existed.

Run through scripts/seed-machine-report-reasons.sh. Without --yes it only prints what would be added. For every company
that is not closed (or the one named), each default reason it does not have yet (same code, any capitals, active or
deactivated) is added with an audit event; nothing existing is changed. A second run adds nothing. New companies get
the same list at onboarding. The list itself is the company's own data afterwards (rename, add, deactivate in the app).
"""

import argparse
import sys
import uuid

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

import asseta.core.model_registry  # noqa: F401
from asseta.core.audit import AuditActor
from asseta.core.config import get_settings
from asseta.modules.machine_reports.reasons import missing_default_reasons, seed_default_reasons

NIL_TENANT = uuid.UUID(int=0)


class Refuse(Exception):
    """Stops the run with a plain message; nothing has been changed."""


def _tenants(session: Session, registration_number: str | None, tenant_id: str | None) -> list[tuple[uuid.UUID, str]]:
    if tenant_id:
        try:
            parsed = uuid.UUID(tenant_id)
        except ValueError as exc:
            raise Refuse(f"not a tenant id: {tenant_id}") from exc
        rows = session.execute(text("SELECT id, display_name FROM tenant WHERE id = :v"), {"v": parsed}).all()
    elif registration_number:
        rows = session.execute(
            text("SELECT id, display_name FROM tenant WHERE lower(trim(registration_number)) = lower(trim(:v))"),
            {"v": registration_number},
        ).all()
    else:
        rows = session.execute(
            text("SELECT id, display_name FROM tenant WHERE status <> 'CLOSED' ORDER BY display_name")
        ).all()
    if (tenant_id or registration_number) and not rows:
        raise Refuse("no such tenant")
    return [(r[0], r[1]) for r in rows if r[0] != NIL_TENANT]


def _scope(session: Session, tenant_id: uuid.UUID) -> None:
    session.execute(
        text("SELECT set_config('app.scope', 'tenant', true), set_config('app.tenant_id', :t, true)"),
        {"t": str(tenant_id)},
    )


def run(registration_number: str | None, tenant_id: str | None, yes: bool, operator: str) -> int:
    engine = create_engine(get_settings().migration_database_url)
    total = 0
    with Session(engine) as session, session.begin():
        session.execute(text("SELECT set_config('app.scope', 'system', true)"))
        tenants = _tenants(session, registration_number, tenant_id)
        actor = AuditActor(user_id=None, roles=["platform-operator-script"], source="script")
        for tid, name in tenants:
            _scope(session, tid)
            missing = missing_default_reasons(session)
            print(f"{name} ({tid}): {len(missing)} to add")
            for code, label in missing:
                print(f"    + {label} ({code})")
            if yes and missing:
                total += seed_default_reasons(session, tid, actor, f"Starting machine-report reasons (by {operator})")
            else:
                total += len(missing)
            session.execute(text("SELECT set_config('app.scope', 'system', true)"))
        if not yes:
            session.rollback()
            print(f"\nDRY RUN: {total} reason(s) would be added. Add --yes to add them.")
            return 0
    print(f"\nADDED: {total} reason(s), with audit events.")
    return 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    who = p.add_mutually_exclusive_group()
    who.add_argument("--registration-number", help="only this company (default: every company not closed)")
    who.add_argument("--tenant-id", help="only this company")
    p.add_argument("--yes", action="store_true", help="really add them (otherwise a dry run that changes nothing)")
    p.add_argument("--operator", default="operator", help="who runs it (recorded with the audit events)")
    args = p.parse_args(argv)
    try:
        return run(args.registration_number, args.tenant_id, args.yes, args.operator)
    except Refuse as exc:
        print(f"REFUSED: {exc}. Nothing was changed.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
