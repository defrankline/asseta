"""Reset ONE tenant's business data before go-live (docs/operating-runbook.md, "Reset a tenant's data before go-live").
Run through scripts/reset-tenant-data.sh, which starts it in a throwaway container of the deployed API image on the
compose network (database and object-store settings come from that container's environment).

  reset_tenant_data.py (--registration-number N | --tenant-id UUID)               dry run: prints what would happen
  reset_tenant_data.py (--registration-number N | --tenant-id UUID) --yes --backup-confirmed --operator WHO

KEPT: the tenant row and its settings, the Asseta subscription and platform-billing records (agreements, rate versions,
subscriptions, status/entitlement events, platform invoices, payments, credits, SMS wallet), the role mirror and
tenant memberships (Keycloak accounts and their groups are never touched), staff records with their login links,
managed-service mandates, push-device registrations and the platform-level audit events (`platform.%`, `billing.%`).
DELETED: every other row of the tenant in every tenant-scoped table (fleet, trackers, telemetry, sites, customers,
contracts, rate cards, jobs, readings, work logs, exceptions, expenses, fuel, receipts, cash, invoices, payments,
customer hours, engine hours, revenue reconciliation, deposit accounts, cases/signals, notifications, site check-ins,
reason lists, the tenant's own policy versions (platform defaults remain), number counters, the tenant's business
audit and security events, ML models trained on its data) plus its objects in the object store (`tenants/<id>/`,
`platform/ml-models/<id>/`). Per-machine billing enrollments and their un-invoiced charges go with the machines (an
open enrollment of a deleted machine would keep billing it); an issued platform invoice line that pointed at such a
charge keeps every printed field, only that internal pointer is cleared.
PHONES: every device session of the tenant is revoked with a reset reason. The next sync call answers the wipe
instruction (the app erases its local data and asks the user to sign in again); the device may then register again
and starts from a fresh bootstrap (asseta.modules.sync.models.TENANT_DATA_RESET_REVOKE_REASON).

Tables are discovered from the schema (a `tenant_id` column, row-level security or a foreign key to `tenant`). Every
discovered table must be classified below: an unclassified one stops the run before anything is changed, so a new
module can neither be skipped silently nor wiped by accident. The deletion runs as the schema owner (the role the
migrations use) in ONE transaction: the guard triggers and forced row-level security of the touched tables are
switched off inside it and restored before commit (ALTER TABLE is transactional; other sessions wait on its lock and
never see them off). Anything unexpected rolls the whole transaction back. A platform audit event
`platform.tenant.data_reset` records the counts and the operator; scripts/seed-demo-tenant.sh refuses a tenant that
carries it.

Environment: ASSETA_MIGRATION_DATABASE_URL (schema owner), ASSETA_S3_ENDPOINT / ASSETA_S3_BUCKET / ASSETA_S3_ACCESS_KEY
/ ASSETA_S3_SECRET_KEY; optional ASSETA_TRACCAR_API_URL (http://traccar:8082) with TRACCAR_ADMIN_EMAIL /
TRACCAR_ADMIN_PASSWORD for --remove-traccar-devices.
"""

import argparse
import contextlib
import json
import os
import sys
import uuid
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import psycopg
from psycopg import sql

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # local runs (uv); the image has it installed
try:
    from asseta.modules.sync.models import TENANT_DATA_RESET_REVOKE_REASON
except ImportError:  # an API image older than this script: its phones could not register again after the reset
    sys.exit("[reset-tenant-data] refused: the deployed API image predates the tenant data reset; deploy it first")

AUDIT_ACTION = "platform.tenant.data_reset"
NIL_TENANT = uuid.UUID(int=0)

# Tenant-scoped tables whose rows of the tenant are KEPT (owner decision, go-live without demo data).
KEEP: dict[str, str] = {
    "tenant_settings": "company settings (timezone, currency, locale)",
    "commercial_agreement": "Asseta subscription",
    "subscription_rate_version": "Asseta subscription",
    "tenant_subscription": "Asseta subscription",
    "subscription_status_event": "Asseta subscription",
    "entitlement_event": "Asseta subscription",
    "entitlement_policy": "Asseta subscription",
    "platform_invoice": "platform billing",
    "platform_payment": "platform billing",
    "credit_adjustment": "platform billing",
    "platform_line_allocation": "platform billing",
    "platform_line_fulfilment": "platform billing",
    "sms_wallet_entry": "platform billing (SMS credits)",
    "tenant_membership": "user role assignments",
    "role": "role mirror of the Keycloak groups",
    "staff_member": "staff records and their login links",
    "managed_service_mandate": "platform access governance (DEC-018)",
    "mandate_assignment": "platform access governance (DEC-018)",
    "push_device": "phones' push registrations",
}
# Kept, with one change each (see the module docstring).
SPECIAL: dict[str, str] = {
    "platform_invoice_line": "kept; pointer to a deleted per-machine charge cleared",
    "device_session": "kept, revoked with the reset reason (phones wipe and bootstrap afresh)",
    "audit_event": "platform/billing events kept; the tenant's business audit deleted",
}
# Discovered through row-level security but holding no tenant rows (platform catalogs, per-user settings).
PLATFORM_LEVEL: dict[str, str] = {
    "feature_definition": "ML feature catalog",
    "ml_setting": "platform ML switch",
    "platform_product": "platform product catalog",
    "telemetry_gateway": "telemetry gateway keys",
    "tracker_model": "tracker model catalog",
    "notification_profile": "per-user contact profile (not tenant data)",
}
# Tenant business records: every row of the tenant is DELETED.
DELETE: frozenset[str] = frozenset(
    {
        # fleet, trackers, telemetry, sites
        "machine", "machine_category", "machine_assignment", "machine_photo", "machine_state_event",
        "machine_latest_position", "machine_position_event", "machine_meter_baseline", "operating_area",
        "tracker", "tracker_assignment", "tracker_capability", "tracker_ingestion_event", "tracking_alert",
        "geofence", "geofence_event", "geofence_machine", "job_site", "site_checkin",
        # per-machine billing of the deleted fleet
        "subscription_asset_enrollment", "subscription_pending_charge",
        # customers, contracts, rate cards, jobs, readings, work logs, exceptions
        "customer", "rental_contract", "rental_rate_policy", "job", "job_activity", "job_exception",
        "customer_acknowledgement", "meter_capture", "meter_correction", "meter_reset_event", "capture_attachment",
        "approval_request", "non_revenue_approval", "work_execution_allocation",
        # engine hours
        "engine_hour_classification", "engine_hour_reason",
        # expenses, fuel, receipts
        "expense", "expense_attachment", "expense_category", "fuel_event",
        # cash custody chain
        "supervisor_cash_custody", "cash_handover", "cash_transfer", "cash_variance", "cash_retention",
        "custody_adjustment", "cash_remittance_overdue", "cash_float_acknowledgement", "cash_reason",
        "remittance_evidence", "company_deposit_account",
        # hire invoices, payments, allocations
        "tenant_hire_invoice", "hire_invoice_job", "hire_invoice_line", "hire_invoice_counter", "customer_payment",
        "hire_payment_allocation", "payment_evidence", "financial_adjustment",
        # customer hours
        "hours_purchase", "hours_ledger_entry", "hours_payment_allocation", "hours_transfer", "hours_cancellation",
        "hours_low_balance_alert", "hours_reason_code", "hours_sequence", "credit_arrangement", "customer_discount",
        # revenue reconciliation
        "revenue_difference", "revenue_difference_adjustment", "revenue_reason",
        # intelligence: cases, signals, insights, ML trained on the tenant's data
        "anomaly_case", "anomaly_case_counter", "case_note", "case_outcome", "case_signal", "risk_signal",
        "feature_snapshot", "prediction", "inference_audit", "model_version", "model_approval", "model_evaluation",
        "model_readiness", "model_drift",
        # notifications and inbox
        "notification", "notification_delivery", "notification_preference", "notification_routing", "sms_delivery",
        # offline sync state of the erased records
        "client_operation", "sync_operation_resolution", "blob_upload_session", "blob_chunk",
        "device_policy_snapshot",
        # the tenant's own policy versions (platform defaults have no tenant)
        "policy_version",
        # the tenant's accountability trail of the erased records, and its undelivered events
        "security_event", "outbox_event",
    }
)  # fmt: skip
OBJECT_PREFIXES = ("tenants/{tid}/", "platform/ml-models/{tid}/")

DISCOVER = """
SELECT c.relname,
       EXISTS (SELECT 1 FROM pg_attribute a WHERE a.attrelid = c.oid AND a.attname = 'tenant_id' AND NOT a.attisdropped)
FROM pg_class c
WHERE c.relnamespace = 'public'::regnamespace AND c.relkind IN ('r', 'p') AND NOT c.relispartition
  AND c.relname <> 'tenant'
  AND (c.relrowsecurity
       OR EXISTS (SELECT 1 FROM pg_attribute a WHERE a.attrelid = c.oid AND a.attname = 'tenant_id'
                  AND NOT a.attisdropped)
       OR EXISTS (SELECT 1 FROM pg_constraint k WHERE k.conrelid = c.oid AND k.contype = 'f'
                  AND k.confrelid = 'public.tenant'::regclass))
ORDER BY 1
"""
FK_EDGES = """
SELECT k.conrelid::regclass::text, k.confrelid::regclass::text
FROM pg_constraint k JOIN pg_class c ON c.oid = k.conrelid
WHERE k.contype = 'f' AND k.connamespace = 'public'::regnamespace AND NOT c.relispartition
"""
USER_TRIGGERS = """
SELECT t.tgname FROM pg_trigger t
WHERE t.tgrelid = %s::regclass AND NOT t.tgisinternal AND t.tgparentid = 0 AND t.tgenabled <> 'D'
"""


class Refuse(Exception):
    """Stops before anything is changed; the message says why and what to do."""


class Unclassified(Refuse):
    def __init__(self, tables: list[str]):
        self.tables = tables
        super().__init__(
            "unclassified tenant-scoped table(s): "
            + ", ".join(tables)
            + ". Add each to KEEP, SPECIAL, PLATFORM_LEVEL or DELETE in backend/scripts/reset_tenant_data.py "
            "(decide whether a go-live reset keeps or erases it); nothing was changed."
        )


@dataclass
class Tenant:
    id: uuid.UUID
    display_name: str
    legal_name: str
    registration_number: str | None


@dataclass
class Plan:
    delete: list[str]  # in a foreign-key safe order (children first)
    keep: list[str]
    platform_level: list[str]
    stale: list[str] = field(default_factory=list)  # classified but absent from this schema (older database)


@dataclass
class Report:
    tenant: Tenant
    plan: Plan
    delete_counts: dict[str, int]
    keep_counts: dict[str, int]
    audit_delete: int
    audit_keep: int
    devices: int
    invoice_lines_detached: int
    idempotency_records: int
    objects: int | None
    trackers: list[tuple[str, str, str]]

    @property
    def total_deleted(self) -> int:
        return sum(self.delete_counts.values()) + self.audit_delete + self.idempotency_records


class ObjectStore(Protocol):
    def list_keys(self, prefix: str) -> list[str]: ...

    def delete_keys(self, keys: list[str]) -> int: ...


# --- discovery and classification -------------------------------------------------------------------------------------
def classify(conn: psycopg.Connection[Any]) -> Plan:
    """Fail closed: every discovered tenant-scoped table must be classified, and every DELETE table has tenant_id."""
    found: dict[str, bool] = dict(conn.execute(DISCOVER).fetchall())
    known = set(KEEP) | set(SPECIAL) | set(PLATFORM_LEVEL) | DELETE
    unknown = sorted(set(found) - known)
    if unknown:
        raise Unclassified(unknown)
    broken = sorted(t for t in DELETE | set(KEEP) | set(SPECIAL) if t in found and not found[t])
    if broken:
        raise Refuse(f"classified as tenant data but without a tenant_id column: {', '.join(broken)}")
    stale = sorted(known - set(found))
    present = [t for t in DELETE if t in found]
    return Plan(
        delete=_children_first(conn, present),
        keep=sorted(t for t in KEEP if t in found),
        platform_level=sorted(t for t in PLATFORM_LEVEL if t in found),
        stale=stale,
    )


def _children_first(conn: psycopg.Connection[Any], tables: list[str]) -> list[str]:
    """Topological order over the foreign keys among `tables`: a referencing table before the one it references."""
    members = set(tables)
    parents: dict[str, set[str]] = {t: set() for t in tables}
    for child, parent in conn.execute(FK_EDGES).fetchall():
        if child in members and parent in members and child != parent:
            parents[child].add(parent)
    children: dict[str, set[str]] = {t: set() for t in tables}
    for child, ps in parents.items():
        for p in ps:
            children[p].add(child)
    order: list[str] = []
    ready = sorted(t for t in tables if not children[t])  # nothing references it: delete first
    pending = {t: len(children[t]) for t in tables}
    while ready:
        t = ready.pop(0)
        order.append(t)
        for p in sorted(parents[t]):
            pending[p] -= 1
            if pending[p] == 0:
                ready.append(p)
    return order + sorted(members - set(order))  # cycles (none today): resolved by the retry loop in _delete_all


# --- tenant selection -------------------------------------------------------------------------------------------------
def find_tenant(conn: psycopg.Connection[Any], registration_number: str | None, tenant_id: str | None) -> Tenant:
    if tenant_id is not None:
        try:
            tid = uuid.UUID(tenant_id)
        except ValueError:
            raise Refuse(f"--tenant-id {tenant_id!r} is not a UUID") from None
        if tid == NIL_TENANT:
            raise Refuse("refusing the platform scope (nil tenant id): platform data is never reset")
        rows = conn.execute(
            "SELECT id, display_name, legal_name, registration_number FROM tenant WHERE id = %s", (tid,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, display_name, legal_name, registration_number FROM tenant "
            "WHERE lower(trim(registration_number)) = lower(trim(%s))",
            (registration_number,),
        ).fetchall()
    if not rows:
        raise Refuse(
            f"no tenant with id {tenant_id}"
            if tenant_id
            else f"no tenant with registration number {registration_number}"
        )
    if len(rows) > 1:
        raise Refuse("more than one tenant matches; use --tenant-id")
    tid, display, legal, reg = rows[0]
    if tid == NIL_TENANT:
        raise Refuse("refusing the platform scope (nil tenant id): platform data is never reset")
    return Tenant(tid, display, legal, reg)


# --- counting (dry run and the report) --------------------------------------------------------------------------------
def _system(conn: psycopg.Connection[Any]) -> None:
    conn.execute("SELECT set_config('app.scope', 'system', true)")


def _count(conn: psycopg.Connection[Any], table: str, tid: uuid.UUID, extra: str = "") -> int:
    q = sql.SQL("SELECT count(*) FROM {} WHERE tenant_id = %s" + extra).format(sql.Identifier(table))  # noqa: S608
    row = conn.execute(q, (tid,)).fetchone()
    return int(row[0]) if row else 0


PLATFORM_AUDIT = " AND (action LIKE 'platform.%%' OR action LIKE 'billing.%%')"
TENANT_AUDIT = " AND NOT (action LIKE 'platform.%%' OR action LIKE 'billing.%%')"
DETACHABLE_LINES = (
    " AND pending_charge_id IN (SELECT id FROM subscription_pending_charge WHERE tenant_id = %s)"  # same tenant
)


def measure(conn: psycopg.Connection[Any], tenant: Tenant, plan: Plan, store: ObjectStore | None) -> Report:
    """Read-only: what a reset of `tenant` would delete and keep (run inside a transaction that is rolled back)."""
    _system(conn)
    tid = tenant.id
    delete_counts = {t: _count(conn, t, tid) for t in plan.delete}
    keep_counts = {t: _count(conn, t, tid) for t in [*plan.keep, "platform_invoice_line", "device_session"]}
    lines = conn.execute(
        "SELECT count(*) FROM platform_invoice_line WHERE tenant_id = %s" + DETACHABLE_LINES,  # noqa: S608
        (tid, tid),
    ).fetchone()
    idem = conn.execute("SELECT count(*) FROM idempotency_record WHERE scope_key = %s", (str(tid),)).fetchone()
    trackers = [
        (str(a), str(e), str(lb))
        for a, e, lb in conn.execute(
            "SELECT adapter, external_id, label FROM tracker WHERE tenant_id = %s ORDER BY adapter, external_id",
            (tid,),
        ).fetchall()
    ]
    objects = None
    if store is not None:
        objects = sum(len(store.list_keys(p.format(tid=tid))) for p in OBJECT_PREFIXES)
    return Report(
        tenant=tenant,
        plan=plan,
        delete_counts=delete_counts,
        keep_counts=keep_counts,
        audit_delete=_count(conn, "audit_event", tid, TENANT_AUDIT),
        audit_keep=_count(conn, "audit_event", tid, PLATFORM_AUDIT),
        devices=_count(conn, "device_session", tid, " AND status = 'ACTIVE'"),
        invoice_lines_detached=int(lines[0]) if lines else 0,
        idempotency_records=int(idem[0]) if idem else 0,
        objects=objects,
        trackers=trackers,
    )


def print_report(r: Report, out: Any = sys.stdout) -> None:
    t = r.tenant

    def p(line: str) -> None:
        print(line, file=out)

    p(f"Tenant: {t.display_name} (legal name {t.legal_name}; registration {t.registration_number or '-'})")
    p(f"Tenant id: {t.id}")
    p("")
    p("WOULD DELETE (rows of this tenant):")
    for table in sorted(r.delete_counts):
        if r.delete_counts[table]:
            p(f"  {table:<34} {r.delete_counts[table]:>10}")
    empty = sorted(t for t, n in r.delete_counts.items() if not n)
    if empty:
        p(f"  (already empty: {len(empty)} more tables)")
    p(f"  {'audit_event (tenant business audit)':<34} {r.audit_delete:>10}")
    p(f"  {'idempotency_record':<34} {r.idempotency_records:>10}")
    p(f"  {'TOTAL rows':<34} {r.total_deleted:>10}")
    p(f"  object-store objects ({', '.join(x.format(tid=t.id) for x in OBJECT_PREFIXES)}): "
      f"{'not checked' if r.objects is None else r.objects}")  # fmt: skip
    p("")
    p("KEEP (rows of this tenant):")
    for table in sorted(r.keep_counts):
        p(f"  {table:<34} {r.keep_counts[table]:>10}  {KEEP.get(table) or SPECIAL.get(table, '')}")
    p(f"  {'audit_event (platform/billing)':<34} {r.audit_keep:>10}")
    p("  Keycloak accounts, their groups and the tenant row itself are not touched.")
    p("")
    p(f"Phones: {r.devices} active device session(s) will be revoked for the reset (wipe, then fresh bootstrap).")
    if r.invoice_lines_detached:
        p(
            f"Platform invoices: {r.invoice_lines_detached} issued line(s) billed a demo machine; they stay as issued "
            "(amounts, descriptions, machine id), only their pointer to the deleted per-machine charge is cleared."
        )
    if r.trackers:
        p(f"Traccar devices of the deleted trackers ({len(r.trackers)}), remove them in Traccar if no longer used:")
        for adapter, ext, label in r.trackers:
            p(f"  {adapter:<10} {ext:<24} {label}")
    if r.plan.stale:
        p(f"(classified tables absent from this schema, ignored: {', '.join(r.plan.stale)})")


# --- the reset --------------------------------------------------------------------------------------------------------
@contextlib.contextmanager
def _guards_off(conn: psycopg.Connection[Any], tables: Iterable[str]) -> Iterator[None]:
    """Inside the caller's transaction: user triggers off (recurses to partitions) and FORCE RLS off on `tables`,
    restored before the transaction commits. The ACCESS EXCLUSIVE lock keeps every other session out meanwhile."""
    triggers: list[tuple[str, str]] = []
    forced: list[str] = []
    for table in tables:
        for (name,) in conn.execute(USER_TRIGGERS, (table,)).fetchall():
            conn.execute(
                sql.SQL("ALTER TABLE {} DISABLE TRIGGER {}").format(sql.Identifier(table), sql.Identifier(name))
            )
            triggers.append((table, name))
        row = conn.execute("SELECT relforcerowsecurity FROM pg_class WHERE oid = %s::regclass", (table,)).fetchone()
        if row and row[0]:
            conn.execute(sql.SQL("ALTER TABLE {} NO FORCE ROW LEVEL SECURITY").format(sql.Identifier(table)))
            forced.append(table)
    yield
    for table, name in triggers:
        conn.execute(sql.SQL("ALTER TABLE {} ENABLE TRIGGER {}").format(sql.Identifier(table), sql.Identifier(name)))
    for table in forced:
        conn.execute(sql.SQL("ALTER TABLE {} FORCE ROW LEVEL SECURITY").format(sql.Identifier(table)))


def _delete_all(conn: psycopg.Connection[Any], tables: list[str], tid: uuid.UUID) -> dict[str, int]:
    """Deletes in the planned order; a table still referenced (a cycle) is retried after the others (savepoints)."""
    counts: dict[str, int] = {}
    pending = list(tables)
    while pending:
        progressed, failed = False, []
        last_error: Exception | None = None
        for table in pending:
            try:
                with conn.transaction():  # savepoint
                    cur = conn.execute(
                        sql.SQL("DELETE FROM {} WHERE tenant_id = %s").format(sql.Identifier(table)), (tid,)
                    )
                counts[table] = cur.rowcount
                progressed = True
            except psycopg.errors.ForeignKeyViolation as e:
                failed.append(table)
                last_error = e
        if failed and not progressed:
            raise Refuse(f"rolled back: rows still referenced in {', '.join(failed)}: {last_error}")
        pending = failed
    return counts


def reset(
    conn: psycopg.Connection[Any],
    tenant: Tenant,
    plan: Plan,
    operator: str,
    *,
    backup_ref: str,
    objects: int | None,
    now: datetime | None = None,
) -> Report:
    """The whole database part in ONE transaction (the caller's connection must not be inside one)."""
    now = now or datetime.now(UTC)
    tid = tenant.id
    with conn.transaction():
        conn.execute("SET LOCAL lock_timeout = '20s'")
        _system(conn)
        locked = conn.execute("SELECT id FROM tenant WHERE id = %s FOR UPDATE", (tid,)).fetchone()
        if locked is None:
            raise Refuse("the tenant disappeared")
        touched = [*plan.delete, "audit_event", "platform_invoice_line", "device_session"]
        # Every table this transaction reads to verify or changes, locked first: nothing moves between the
        # measurement and the deletion (other sessions wait a few seconds; lock_timeout aborts instead of hanging).
        conn.execute(
            sql.SQL("LOCK TABLE {} IN ACCESS EXCLUSIVE MODE").format(
                sql.SQL(", ").join(sql.Identifier(t) for t in sorted({*touched, *plan.keep, "idempotency_record"}))
            )
        )
        before = measure(conn, tenant, plan, None)
        before.objects = objects
        with _guards_off(conn, touched):
            detached = conn.execute(
                "UPDATE platform_invoice_line SET pending_charge_id = NULL WHERE tenant_id = %s"  # noqa: S608
                + DETACHABLE_LINES,
                (tid, tid),
            ).rowcount
            deleted = _delete_all(conn, plan.delete, tid)
            audit_deleted = conn.execute(
                "DELETE FROM audit_event WHERE tenant_id = %s" + TENANT_AUDIT,  # noqa: S608 - constant fragment
                (tid,),
            ).rowcount
            revoked = conn.execute(
                "UPDATE device_session SET status = 'REVOKED', revoked_at = %s, revoked_by = NULL, revoke_reason = %s "
                "WHERE tenant_id = %s AND status = 'ACTIVE'",
                (now, TENANT_DATA_RESET_REVOKE_REASON, tid),
            ).rowcount
        idem = conn.execute("DELETE FROM idempotency_record WHERE scope_key = %s", (str(tid),)).rowcount
        # Verify before commit: counts match what was measured, kept rows untouched, nothing of the tenant left.
        problems = [f"{t}: measured {before.delete_counts[t]}, deleted {n}" for t, n in deleted.items()
                    if n != before.delete_counts[t]]  # fmt: skip
        after = measure(conn, tenant, plan, None)
        problems += [f"{t}: {n} row(s) left" for t, n in after.delete_counts.items() if n]
        problems += [
            f"kept {t}: {before.keep_counts[t]} -> {n}"
            for t, n in after.keep_counts.items()
            if n != before.keep_counts[t]
        ]
        if after.audit_delete or after.audit_keep != before.audit_keep:
            problems.append("audit_event split changed unexpectedly")
        if detached != before.invoice_lines_detached or revoked != before.devices:
            problems.append(
                f"invoice lines {detached}/{before.invoice_lines_detached}, devices {revoked}/{before.devices}"
            )
        if problems:
            raise Refuse("rolled back, nothing changed: " + "; ".join(problems))
        details = {
            "operator": operator,
            "backup": backup_ref,
            "tenant": tenant.display_name,
            "registration_number": tenant.registration_number,
            "deleted": {t: n for t, n in sorted(deleted.items()) if n},
            "deleted_total": sum(deleted.values()) + audit_deleted + idem,
            "tenant_audit_events_deleted": audit_deleted,
            "idempotency_records_deleted": idem,
            "kept": {t: n for t, n in sorted(before.keep_counts.items()) if n},
            "platform_audit_events_kept": before.audit_keep,
            "device_sessions_revoked": revoked,
            "invoice_lines_detached": detached,
            "objects_to_delete": objects,
            "trackers": [{"adapter": a, "external_id": e, "label": lb} for a, e, lb in before.trackers],
        }
        conn.execute(
            "INSERT INTO audit_event (id, occurred_at, tenant_id, actor_user_id, actor_roles, device_id, source,"
            " action, entity_type, entity_id, before, after, reason, correlation_id)"
            " VALUES (%s, %s, %s, NULL, %s, NULL, 'operator-script', %s, 'tenant', %s, NULL, %s, %s, %s)",
            (
                uuid.uuid4(),
                now,
                tid,
                json.dumps(["platform-operator"]),
                AUDIT_ACTION,
                str(tid),
                json.dumps(details),
                f"Tenant data reset before go-live by {operator} (scripts/reset-tenant-data.sh)",
                str(uuid.uuid4()),
            ),
        )
    return before


# --- object store, Traccar, demo state files --------------------------------------------------------------------------
class S3Store:
    def __init__(self) -> None:
        import boto3

        from asseta.core.config import get_settings

        cfg = get_settings()  # the API's own object-store settings (ASSETA_S3_*), as the evidence was written
        self._bucket = cfg.s3_bucket
        self._s3 = boto3.client(
            "s3",
            endpoint_url=cfg.s3_endpoint,
            aws_access_key_id=cfg.s3_access_key.get_secret_value(),
            aws_secret_access_key=cfg.s3_secret_key.get_secret_value(),
            region_name="us-east-1",
        )

    def list_keys(self, prefix: str) -> list[str]:
        keys: list[str] = []
        for page in self._s3.get_paginator("list_objects_v2").paginate(Bucket=self._bucket, Prefix=prefix):
            keys += [o["Key"] for o in page.get("Contents", []) if "Key" in o]
        return keys

    def delete_keys(self, keys: list[str]) -> int:
        done = 0
        for i in range(0, len(keys), 1000):
            batch = keys[i : i + 1000]
            res = self._s3.delete_objects(
                Bucket=self._bucket, Delete={"Objects": [{"Key": k} for k in batch], "Quiet": True}
            )
            errors = res.get("Errors", [])
            if errors:
                raise RuntimeError(f"{len(errors)} object(s) not deleted, first: {errors[0]}")
            done += len(batch)
        return done


def delete_objects(store: ObjectStore, tid: uuid.UUID) -> int:
    return sum(store.delete_keys(store.list_keys(p.format(tid=tid))) for p in OBJECT_PREFIXES)


def remove_traccar_devices(trackers: list[tuple[str, str, str]]) -> list[str]:
    import httpx

    base = (os.environ.get("ASSETA_TRACCAR_API_URL") or "http://traccar:8082").rstrip("/")
    auth = (os.environ.get("TRACCAR_ADMIN_EMAIL", ""), os.environ.get("TRACCAR_ADMIN_PASSWORD", ""))
    if not all(auth):
        return ["--remove-traccar-devices needs TRACCAR_ADMIN_EMAIL and TRACCAR_ADMIN_PASSWORD; nothing removed"]
    lines = []
    for _adapter, ext, label in trackers:
        try:
            r = httpx.get(f"{base}/api/devices", params={"uniqueId": ext}, auth=auth, timeout=30.0)
            r.raise_for_status()
            found = r.json()
            if not found:
                lines.append(f"Traccar: {ext} ({label}) not registered")
                continue
            for d in found:
                httpx.delete(f"{base}/api/devices/{d['id']}", auth=auth, timeout=30.0).raise_for_status()
                lines.append(f"Traccar: removed device {ext} ({label}, id {d['id']})")
        except httpx.HTTPError as e:
            lines.append(f"Traccar: {ext} ({label}) NOT removed: {e}")
    return lines


def retire_demo_state(state_dir: Path, tid: uuid.UUID, now: datetime) -> list[str]:
    """Moves the demo seeder's state file(s) of this tenant aside, so `feed`/`field`/`retire` stop using them."""
    moved: list[str] = []
    if not state_dir.is_dir():
        return moved
    for path in sorted(state_dir.glob("demo-*-state.json")):
        try:
            if json.loads(path.read_text()).get("tenant_id") != str(tid):
                continue
        except (OSError, ValueError):
            continue
        target = path.with_name(f"{path.name}.reset-{now.strftime('%Y%m%dT%H%M%SZ')}")
        path.rename(target)
        moved.append(f"{path.name} -> {target.name}")
    return moved


# --- command line -----------------------------------------------------------------------------------------------------
def dsn() -> str:
    url = os.environ.get("ASSETA_MIGRATION_DATABASE_URL", "")
    if not url:
        raise Refuse("ASSETA_MIGRATION_DATABASE_URL is not set (the schema owner's connection, as the migrations use)")
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def confirm_name(tenant: Tenant) -> None:
    if not sys.stdin.isatty():
        raise Refuse("a real reset needs an interactive terminal to type the tenant name; nothing was changed")
    try:
        typed = input(f"Type the tenant name exactly ({tenant.display_name}) to erase its data: ")
    except EOFError:
        typed = ""
    if typed != tenant.display_name:
        raise Refuse("the name typed does not match; nothing was changed")


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    who = p.add_mutually_exclusive_group(required=True)
    who.add_argument("--registration-number")
    who.add_argument("--tenant-id")
    p.add_argument("--yes", action="store_true", help="really reset (otherwise a dry run that changes nothing)")
    p.add_argument("--backup-confirmed", action="store_true", help="a backup taken just before exists")
    p.add_argument("--backup-ref", default="confirmed by the operator", help="recorded in the audit event")
    p.add_argument("--operator", default="", help="who runs the reset (recorded in the audit event)")
    p.add_argument("--state-dir", default="/out", help="demo seeder state files (moved aside after the reset)")
    p.add_argument("--no-objects", action="store_true", help="do not count/delete object-store objects")
    p.add_argument("--remove-traccar-devices", action="store_true", help="also delete the trackers' Traccar devices")
    a = p.parse_args(argv)

    store: ObjectStore | None = None if a.no_objects else S3Store()
    with psycopg.connect(dsn(), autocommit=True) as conn:  # every step below is an explicit transaction
        with conn.transaction(force_rollback=True):  # dry run and preflight: read-only, always rolled back
            tenant = find_tenant(conn, a.registration_number, a.tenant_id)
            plan = classify(conn)
            report = measure(conn, tenant, plan, store)
        print_report(report)
        sys.stdout.flush()
        if not a.yes:
            print("\nDRY RUN: nothing was changed. Add --yes (after a backup) to reset.")
            return 0
        if not a.backup_confirmed:
            raise Refuse("no recent backup confirmed: run scripts/backup-live.sh first (or pass --backup-confirmed)")
        if not a.operator.strip():
            raise Refuse("--operator is required for a real reset (recorded in the audit event)")
        print("")
        confirm_name(tenant)
        result = reset(conn, tenant, plan, a.operator.strip(), backup_ref=a.backup_ref, objects=report.objects)
    print(f"\nDATABASE RESET OK: {result.total_deleted} rows deleted, {result.devices} device session(s) revoked.")
    if store is not None:
        try:
            print(f"Object store: {delete_objects(store, tenant.id)} object(s) deleted.")
        except Exception as e:
            print(f"Object store: NOT finished ({e}). Re-run the same command: the database part is then a no-op.")
    if a.remove_traccar_devices and result.trackers:
        for line in remove_traccar_devices(result.trackers):
            print(line)
    for line in retire_demo_state(Path(a.state_dir), tenant.id, datetime.now(UTC)):
        print(f"Demo state file moved aside: {line}")
    print(f"Audit: {AUDIT_ACTION} recorded for tenant {tenant.id} by {a.operator.strip()}.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Refuse as refused:
        print(f"[reset-tenant-data] refused: {refused}", file=sys.stderr, flush=True)
        sys.exit(2)
