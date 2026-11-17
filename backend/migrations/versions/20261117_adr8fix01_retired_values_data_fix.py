"""ADR-008 data fix: rows that still hold values the code no longer has.

Why: the data steps of adr8rm01 ran without a row-level-security scope. Every tenant table FORCEs RLS, so on a real
database (rows exist, the migration role is RLS-bound) they matched no rows; some tables (policy_version,
feature_definition) have no DELETE policy at all, so even the system scope cannot delete there. Readings, ledger rows,
signals and policy versions kept retired enum values and loading them failed (LookupError, e.g. `GET /sync/changes`
on a capture of kind OPENING). mrep01 and crrej01 have no data steps.

Each step runs under `app.scope = system` with the table's RLS temporarily not forced (the migration role owns the
tables, so it then reads and writes every row) and only the table's own guard/immutability trigger disabled; both are
restored immediately. Sync-revision triggers stay on, so a corrected reading is delivered to phones again. Every step
only touches rows that still hold a retired value: running it again changes nothing (idempotent).

What happens to each retired value:
- meter_capture.kind OPENING / CLOSING (job opening/closing readings) -> DAILY (they stay the machine's readings).
- risk_signal / anomaly_case subject_type JOB -> MACHINE, subject_id = the row's machine_id (every job signal carried
  it; the job id is kept when it did not, the job table being gone).
- hours_ledger_entry entry_type PROVISIONAL / PROVISIONAL_REVERSED (daily drawdown of running jobs) -> deleted: they
  only held hours for running jobs, which no longer exist (no other row references them).
- financial_adjustment kind INVOICE_REVERSAL (reversals of the removed hire invoices) -> deleted (not referenced).
- policy_version policy_type HIRE_BILLING / REVENUE_RECONCILIATION (platform and tenant versions) -> deleted (no
  rule reads them any more; not referenced).
- feature_snapshot entity_type JOB / feature_definition entity JOB (ML features of jobs) -> deleted.
- notification types that no longer exist (job, revenue-difference, non-revenue, unbilled-work, hire-invoice,
  job-readings and hours-overrun notifications) and notifications that open a job: deleted, unless an SMS or channel
  delivery record refers to them (billing/audit history); those are kept but hidden from the in-app inbox
  (in_app = false) without a link to the removed screen. Preferences for the retired types are deleted.

Not changed (they load as plain strings and stay as history): client_operation.op_type of retired sync operations
(JOB_*, SITE_CHECKIN) and their conflicts, device_policy_snapshot.policy_type, tenant_setup_choice.step_key,
adjustment_request / adjustment_ledger_entry INVOICE_VOID (still enum members, refused for new requests), retired
policy fields and scorecard items inside policy payloads (dropped when read: policy/schemas.py RETIRED_FIELDS /
RETIRED_VALUES).

The downgrade is a no-op: this is a data fix; the deleted rows described removed mechanics and are not restored.

Revision ID: adr8fix01
Revises: crrej01
Create Date: 2026-11-17 18:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "adr8fix01"
down_revision: str | Sequence[str] | None = "crrej01"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RETIRED_NOTIFICATION_TYPES = (
    "JOB_AWAITING_APPROVAL",
    "JOB_ASSIGNED",
    "JOB_REQUEST_APPROVED",
    "JOB_AUTO_APPROVAL_HELD",
    "JOB_CANCELLED",
    "JOB_MISSING_READINGS",
    "REVENUE_DIFFERENCE",
    "NON_REVENUE_APPROVAL_REQUESTED",
    "UNBILLED_WORK",
    "HIRE_INVOICE_OVERDUE",
    "HOURS_OVERRUN",
)
_TYPES = ", ".join(f"'{t}'" for t in RETIRED_NOTIFICATION_TYPES)
RETIRED_NOTIFICATION = (
    f"(n.notification_type IN ({_TYPES}) OR n.entity_type = 'job' OR n.link LIKE '/tenant/jobs%' "
    f"OR n.link LIKE '/tenant/field/jobs%')"
)
REFERENCED = (
    "(EXISTS (SELECT 1 FROM sms_delivery d WHERE d.notification_id = n.id) "
    "OR EXISTS (SELECT 1 FROM notification_delivery d WHERE d.notification_id = n.id))"
)


def _fix(table: str, trigger: str | None, *statements: str) -> None:
    """Run data statements on every row of `table` (RLS not forced for the owner meanwhile, guard trigger off)."""
    op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    if trigger:
        op.execute(f"ALTER TABLE {table} DISABLE TRIGGER {trigger}")
    for sql in statements:
        op.execute(sql)
    if trigger:
        op.execute(f"ALTER TABLE {table} ENABLE TRIGGER {trigger}")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def upgrade() -> None:
    op.execute("SELECT set_config('app.scope', 'system', true)")
    _fix(
        "meter_capture",
        "trg_meter_capture_guard",
        "UPDATE meter_capture SET kind = 'DAILY' WHERE kind IN ('OPENING', 'CLOSING')",
    )
    for table in ("risk_signal", "anomaly_case"):
        _fix(
            table,
            f"trg_{table}_guard",
            f"UPDATE {table} SET subject_type = 'MACHINE', subject_id = COALESCE(machine_id, subject_id) "
            f"WHERE subject_type = 'JOB'",
        )
    _fix(
        "hours_ledger_entry",
        "trg_hours_ledger_entry_immutable",
        "DELETE FROM hours_ledger_entry WHERE entry_type IN ('PROVISIONAL', 'PROVISIONAL_REVERSED')",
    )
    _fix(
        "financial_adjustment",
        "trg_financial_adjustment_immutable",
        "DELETE FROM financial_adjustment WHERE kind = 'INVOICE_REVERSAL'",
    )
    _fix(
        "policy_version",
        "trg_policy_version_immutable",
        "DELETE FROM policy_version WHERE policy_type IN ('REVENUE_RECONCILIATION', 'HIRE_BILLING')",
    )
    _fix("feature_snapshot", "trg_feature_snapshot_immutable", "DELETE FROM feature_snapshot WHERE entity_type = 'JOB'")
    _fix(
        "feature_definition", "trg_feature_definition_immutable", "DELETE FROM feature_definition WHERE entity = 'JOB'"
    )
    # sms_delivery / notification_delivery are only read here (their read policies admit the system scope).
    _fix(
        "notification",
        "trg_notification_guard",
        f"DELETE FROM notification n WHERE {RETIRED_NOTIFICATION} AND NOT {REFERENCED}",
        f"UPDATE notification n SET in_app = false, link = NULL, entity_type = NULL, entity_id = NULL "
        f"WHERE {RETIRED_NOTIFICATION} AND (n.in_app OR n.link IS NOT NULL OR n.entity_type IS NOT NULL)",
    )
    _fix(
        "notification_preference",
        None,
        f"DELETE FROM notification_preference WHERE notification_type IN ({_TYPES})",
    )


def downgrade() -> None:
    """No-op: a data fix (the deleted rows described removed mechanics and are not restored)."""
