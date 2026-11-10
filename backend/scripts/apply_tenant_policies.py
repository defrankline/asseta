#!/usr/bin/env python
"""Apply one company's policy settings from a JSON file, as ordinary tenant policy versions.

Run through scripts/apply-tenant-policies.sh. It is the same change as Administration -> Policies -> New override:
each policy type that really changes gets a new tenant version with a reason and an audit event, validated by the
policy service, in one transaction. Without --yes it only prints what would change. Fields already at the wanted value
are skipped, so a second run changes nothing.

File format (policy types and field names are the "Key" column of the Policies page):
    {"reason": "Go-live settings agreed with the company",
     "policies": {"CUSTOMER_HOURS": {"default_billing_mode": "PREPAID_HOURS", "expiry_days": 365}}}
"""

import argparse
import json
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

import asseta.core.model_registry  # noqa: F401
from asseta.core.audit import AuditActor
from asseta.core.config import get_settings
from asseta.core.errors import BusinessRuleViolation
from asseta.modules.policy.schemas import SCHEMAS, PolicyScope, PolicyType
from asseta.modules.policy.service import PolicyService

NIL_TENANT = uuid.UUID(int=0)
# Changed only from the Policies page, where the open-mandate and mandate-actor guards run.
GUARDED_FIELDS = {PolicyType.OVERSIGHT: {"managed_service_enabled"}}


class Refuse(Exception):
    """Stops the run with a plain message; nothing has been changed."""


@dataclass(frozen=True)
class Change:
    ptype: PolicyType
    field: str
    current: Any
    wanted: Any


def read_file(path: Path) -> tuple[str, dict[PolicyType, dict[str, Any]]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise Refuse(f"file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise Refuse(f"{path} is not valid JSON: {exc}") from exc
    reason = raw.get("reason") if isinstance(raw, dict) else None
    policies = raw.get("policies") if isinstance(raw, dict) else None
    if not isinstance(reason, str) or len(reason.strip()) < 3:
        raise Refuse('the file needs a "reason" of at least 3 characters')
    if not isinstance(policies, dict) or not policies:
        raise Refuse('the file needs a non-empty "policies" object')
    wanted: dict[PolicyType, dict[str, Any]] = {}
    for name, values in policies.items():
        try:
            ptype = PolicyType(name)
        except ValueError as exc:
            raise Refuse(f"unknown policy type {name}; known: {sorted(t.value for t in PolicyType)}") from exc
        if not isinstance(values, dict) or not values:
            raise Refuse(f"{name} needs an object of field names and values")
        unknown = set(values) - set(SCHEMAS[ptype].model_fields)
        if unknown:
            raise Refuse(f"{name}: unknown fields {sorted(unknown)}")
        guarded = set(values) & GUARDED_FIELDS.get(ptype, set())
        if guarded:
            raise Refuse(f"{name}: {sorted(guarded)} can only be changed on the Policies page")
        wanted[ptype] = values
    return reason.strip(), wanted


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
        raise Refuse("refusing the platform scope: this script only sets one company's policies")
    return rows[0][0], rows[0][1]


def plain(model: BaseModel, field: str) -> Any:
    return model.model_dump(mode="json")[field]


def normalised(ptype: PolicyType, field: str, value: Any, effective: BaseModel) -> Any:
    """The wanted value as the schema would store it, so "365" vs 365 or a Decimal never reads as a change."""
    merged = effective.model_dump(mode="json") | {field: value}
    try:
        return plain(SCHEMAS[ptype].model_validate(merged), field)
    except ValueError:
        return value  # create_version reports invalid combinations of the whole set with the field names


def plan(service: PolicyService, tid: uuid.UUID, wanted: dict[PolicyType, dict[str, Any]]) -> list[Change]:
    changes: list[Change] = []
    for ptype, values in wanted.items():
        effective = service.resolve(ptype, tid).policy
        for field, value in values.items():
            current = plain(effective, field)
            if normalised(ptype, field, value, effective) != current:
                changes.append(Change(ptype, field, current, value))
    return changes


def apply(service: PolicyService, tid: uuid.UUID, changes: list[Change], reason: str, operator: str) -> None:
    actor = AuditActor(user_id=None, roles=["platform-operator-script"], source="script")
    by_type: dict[PolicyType, dict[str, Any]] = {}
    for c in changes:
        by_type.setdefault(c.ptype, {})[c.field] = c.wanted
    for ptype, values in by_type.items():
        service.create_version(
            ptype=ptype,
            scope=PolicyScope.TENANT,
            tenant_id=tid,
            scope_ref_id=None,
            values=values,
            effective_from=None,
            reason=f"{reason} (applied by {operator})",
            actor=actor,
        )


def run(path: Path, registration_number: str | None, tenant_id: str | None, yes: bool, operator: str) -> int:
    reason, wanted = read_file(path)
    engine = create_engine(get_settings().migration_database_url)
    with Session(engine) as session, session.begin():
        session.execute(text("SELECT set_config('app.scope', 'system', true)"))
        tid, name = find_tenant(session, registration_number, tenant_id)
        # From here on the transaction acts inside this one company, as a request from that company would.
        session.execute(
            text("SELECT set_config('app.scope', 'tenant', true), set_config('app.tenant_id', :t, true)"),
            {"t": str(tid)},
        )
        print(f"Company: {name} ({tid})")
        service = PolicyService(session)
        changes = plan(service, tid, wanted)
        if not changes:
            print("Nothing to change: every setting already has the wanted value.")
            return 0
        for c in changes:
            print(f"  {c.ptype.value}.{c.field}: {json.dumps(c.current)} -> {json.dumps(c.wanted)}")
        if not yes:
            session.rollback()
            print(f"\nDRY RUN: {len(changes)} setting(s) would change. Add --yes to apply.")
            return 0
        apply(service, tid, changes, reason, operator)
    print(f"\nAPPLIED: {len(changes)} setting(s), as new company policy versions, with audit events.")
    return 0


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    who = p.add_mutually_exclusive_group(required=True)
    who.add_argument("--registration-number")
    who.add_argument("--tenant-id")
    p.add_argument("--file", required=True, type=Path, help="JSON file with the settings")
    p.add_argument("--yes", action="store_true", help="really apply (otherwise a dry run that changes nothing)")
    p.add_argument("--operator", default="operator", help="who runs it (recorded with the reason)")
    args = p.parse_args(argv)
    try:
        return run(args.file, args.registration_number, args.tenant_id, args.yes, args.operator)
    except Refuse as exc:
        print(f"REFUSED: {exc}. Nothing was changed.", file=sys.stderr)
        return 2
    except BusinessRuleViolation as exc:
        details = "; ".join(f"{d.field}: {d.issue}" for d in (exc.details or []))
        print(f"REFUSED: {exc} {details}. Nothing was changed.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
