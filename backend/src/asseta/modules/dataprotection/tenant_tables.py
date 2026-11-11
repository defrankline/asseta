"""Which tables hold a tenant's rows, and what happens to them when the tenant's data is erased. Shared by the
go-live data reset (backend/scripts/reset_tenant_data.py) and the company deletion (closure_executor.py), so a new
module is classified once for both.

Tables are discovered from the schema (a `tenant_id` column, row-level security or a foreign key to `tenant`). Every
discovered table must be classified below: an unclassified one stops a reset or a company deletion before anything is
changed, so a new module can neither be skipped silently nor wiped by accident.

The go-live reset keeps KEEP and SPECIAL and deletes DELETE. A company deletion deletes everything except
CLOSURE_KEEP (the platform operator's own billing records about the company, the company's settings and the closure
request itself) and the two CLOSURE_SPECIAL tables.
"""

import contextlib
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any

import psycopg
from psycopg import sql

# Tenant-scoped tables whose rows of the tenant a go-live reset KEEPS (owner decision, go-live without demo data).
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
    "company_deletion_request": "company closure requests (the minimal closure record)",
}
# Kept by a reset, with one change each (see backend/scripts/reset_tenant_data.py).
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
# Tenant business records: every row of the tenant is DELETED by a reset (and by a company deletion).
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
        "engine_hour_classification", "engine_hour_reason", "work_allocation", "machine_changeover",
        "daily_operational_report",
        # expenses, fuel, receipts
        "expense", "expense_attachment", "expense_category", "fuel_event",
        # cash custody chain
        "supervisor_cash_custody", "cash_handover", "cash_transfer", "cash_variance", "cash_retention",
        "custody_adjustment", "cash_remittance_overdue", "cash_float_acknowledgement", "cash_reason",
        "remittance_evidence", "company_deposit_account", "partial_remittance_approval", "cash_variance_event",
        # petty cash funds (DEC-033)
        "petty_cash_fund", "petty_cash_movement", "petty_cash_count", "petty_cash_holder_change",
        "petty_cash_adjustment", "petty_cash_advance",
        # hire invoices, payments, allocations
        "tenant_hire_invoice", "hire_invoice_job", "hire_invoice_line", "hire_invoice_counter", "customer_payment",
        "hire_payment_allocation", "payment_evidence", "payment_auto_verification", "financial_adjustment",
        # customer hours
        "hours_purchase", "hours_ledger_entry", "hours_payment_allocation", "hours_transfer", "hours_cancellation",
        "hours_low_balance_alert", "hours_reason_code", "hours_sequence", "credit_arrangement", "customer_discount",
        # revenue reconciliation
        "revenue_difference", "revenue_difference_adjustment", "revenue_reason",
        # adjustments ledger (Ledger 6) and its propose/decide flow
        "adjustment_ledger_entry", "adjustment_request",
        # data protection: export jobs and balance verification runs of the erased records
        "tenant_data_export", "balance_verification_run",
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
        # the go-live checklist choices made for the erased setup (not needed marks, confirmations, dismissal)
        "tenant_setup_choice",
        # the tenant's accountability trail of the erased records, and its undelivered events
        "security_event", "outbox_event",
    }
)  # fmt: skip

# A company deletion keeps ONLY these rows of the company (owner decision: delete everything after the waiting
# period). The platform operator keeps its own billing records about the company and the closure record.
CLOSURE_KEEP: dict[str, str] = {
    "tenant_settings": "company settings (timezone, currency, locale: no personal data) for the billing records",
    "commercial_agreement": "platform billing: the agreement the invoices were issued under",
    "subscription_rate_version": "platform billing: the rates the invoices were computed with",
    "tenant_subscription": "platform billing: the subscription (cancelled by the deletion)",
    "subscription_status_event": "platform billing: subscription history",
    "entitlement_event": "platform billing: access history",
    "entitlement_policy": "platform billing: access rules",
    "platform_invoice": "platform billing: invoices",
    "platform_payment": "platform billing: payments",
    "credit_adjustment": "platform billing: credits",
    "platform_line_allocation": "platform billing: payment allocations",
    "platform_line_fulfilment": "platform billing: what paid lines delivered",
    "sms_wallet_entry": "platform billing: SMS credits bought and used",
    "company_deletion_request": "the closure record",
}
# Kept by a company deletion with one change each.
CLOSURE_SPECIAL: dict[str, str] = {
    "platform_invoice_line": "kept; pointer to a deleted per-machine charge cleared",
    "audit_event": "platform billing and closure events kept; every other event of the company deleted",
}
# Audit events a company deletion keeps (SQL LIKE patterns on `action`): the platform operator's billing trail and
# the closure itself. Onboarding and company-detail events carry contact details and go.
CLOSURE_AUDIT_KEEP: tuple[str, ...] = (
    "billing.%",
    "platform.invoice.%",
    "platform.payment.%",
    "platform.credit.%",
    "platform.subscription.%",
    "platform.rate_version.%",
    "platform.pending_charge.%",
    "platform.entitlement.%",
    "platform.company_closure.%",
)

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
            + ". Add each to KEEP, SPECIAL, PLATFORM_LEVEL or DELETE in "
            "backend/src/asseta/modules/dataprotection/tenant_tables.py (decide whether a go-live reset keeps or "
            "erases it, and whether a company deletion keeps it: CLOSURE_KEEP); nothing was changed."
        )


@dataclass
class Plan:
    delete: list[str]  # in a foreign-key safe order (children first)
    keep: list[str]
    platform_level: list[str]
    stale: list[str] = field(default_factory=list)  # classified but absent from this schema (older database)


def classify(conn: psycopg.Connection[Any]) -> Plan:
    """The go-live reset's plan. Fail closed: every discovered tenant-scoped table must be classified, and every
    DELETE/KEEP/SPECIAL table has a tenant_id column."""
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
        delete=children_first(conn, present),
        keep=sorted(t for t in KEEP if t in found),
        platform_level=sorted(t for t in PLATFORM_LEVEL if t in found),
        stale=stale,
    )


def closure_plan(conn: psycopg.Connection[Any]) -> Plan:
    """A company deletion's plan: every tenant-scoped table except CLOSURE_KEEP and CLOSURE_SPECIAL, children first.
    Fails closed exactly like `classify` (the same classification must be complete)."""
    reset = classify(conn)
    found = set(reset.delete) | set(reset.keep) | {t for t in SPECIAL if t not in reset.stale}
    delete = sorted(t for t in found if t not in CLOSURE_KEEP and t not in CLOSURE_SPECIAL)
    return Plan(
        delete=children_first(conn, delete),
        keep=sorted(t for t in CLOSURE_KEEP if t in found),
        platform_level=reset.platform_level,
        stale=reset.stale,
    )


def children_first(conn: psycopg.Connection[Any], tables: list[str]) -> list[str]:
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
    return order + sorted(members - set(order))  # cycles (none today): resolved by the callers' retry loops


@contextlib.contextmanager
def guards_off(conn: psycopg.Connection[Any], tables: Iterable[str]) -> Iterator[None]:
    """Inside the caller's transaction: user triggers off (recurses to partitions) and FORCE RLS off on `tables`,
    restored before the transaction commits (ALTER TABLE is transactional; other sessions wait on its lock and never
    see them off). Needs the schema owner's connection."""
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
