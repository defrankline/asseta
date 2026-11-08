"""Read-only balance verification on the live server (run through scripts/verify-balances.sh, in a throwaway container
of the deployed API image). Recomputes every balance of a tenant from its underlying records and prints the
mismatches against every stored figure; the ledger prevails and nothing is written (READ ONLY transaction).

  verify_balances.py --all | --registration-number N | --tenant-id UUID  [--json]

Exit code 0: no mismatch. 1: at least one mismatch. 2: could not run."""

import argparse
import json
import sys
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # local runs (uv); the image has it installed

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from asseta.core.clock import system_clock
from asseta.core.db import DbScope, apply_scope, get_sessionmaker
from asseta.modules.tenancy.models import Tenant, TenantStatus

try:
    from asseta.modules.dataprotection.balance_checks import verify_tenant
    from asseta.modules.dataprotection.balance_report import Report
except ImportError:
    sys.exit("[verify-balances] the deployed API image predates balance verification; deploy it first")


def _tenants(s: Session, registration: str | None, tenant_id: str | None) -> list[tuple[uuid.UUID, str]]:
    stmt = (
        select(Tenant.id, Tenant.display_name).where(Tenant.status != TenantStatus.CLOSED).order_by(Tenant.display_name)
    )
    if tenant_id:
        stmt = stmt.where(Tenant.id == uuid.UUID(tenant_id))
    if registration:
        stmt = stmt.where(Tenant.registration_number == registration)
    return [(tid, name) for tid, name in s.execute(stmt).tuples()]


def _report_json(name: str, report: Report) -> dict[str, Any]:
    return {
        "tenant_id": str(report.tenant_id),
        "tenant": name,
        "as_of": report.as_of.isoformat(),
        "summary": report.summary(),
        "findings": [f.to_json() for f in report.findings],
    }


def _print_report(name: str, report: Report) -> None:
    print(f"\n=== {name} ({report.tenant_id}) as of {report.as_of.isoformat()}")
    for row in report.summary():
        print(f"  {row['check']:<22} checked {row['checked']:>8}   mismatches {row['mismatches']:>6}")
    for f in report.findings:
        unit = f" {f.currency}" if f.currency else ""
        print(
            f"  MISMATCH {f.check.value} {f.label}: ledger {f.ledger_value}{unit}, stored {f.stored_value}{unit} "
            f"(difference {f.difference}) [{f.source}]"
        )
    if not report.findings:
        print("  every recorded figure matches its underlying records")


def run(argv: Sequence[str]) -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    who = p.add_mutually_exclusive_group(required=True)
    who.add_argument("--all", action="store_true")
    who.add_argument("--registration-number")
    who.add_argument("--tenant-id")
    p.add_argument("--json", action="store_true", dest="as_json")
    a = p.parse_args(argv)

    factory = get_sessionmaker()
    with factory() as s, s.begin():
        s.execute(text("SET TRANSACTION READ ONLY"))
        apply_scope(s, DbScope.SYSTEM, None, None)
        tenants = _tenants(s, a.registration_number, a.tenant_id)
    if not tenants:
        print("[verify-balances] no such tenant", file=sys.stderr)
        return 2
    now = system_clock()
    mismatches = 0
    out = []
    for tid, name in tenants:
        with factory() as s, s.begin():
            s.execute(text("SET TRANSACTION READ ONLY"))
            apply_scope(s, DbScope.TENANT, tid, None)
            report = verify_tenant(s, tid, now)
        mismatches += len(report.findings)
        if a.as_json:
            out.append(_report_json(name, report))
        else:
            _print_report(name, report)
    if a.as_json:
        print(json.dumps(out, indent=1))
    else:
        print(
            f"\n{len(tenants)} tenant(s) verified, {mismatches} mismatch(es). The ledger prevails; nothing was changed."
        )
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
