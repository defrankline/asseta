"""What a tenant data export contains. Every tenant-scoped table (one with a `tenant_id` column) is exported by default
so a new module is never silently left out; EXCLUDED lists the few that are not business records, and REDACTED_COLUMNS
the credentials that must never leave. tests/api/test_data_export.py fails on an unclassified credential-like column."""

import re

from sqlalchemy import text
from sqlalchemy.orm import Session

EXCLUDED: dict[str, str] = {
    "tenant_data_export": "the export jobs themselves",
    "outbox_event": "undelivered internal events, not business records",
    "blob_chunk": "partial upload chunks in transit",
    "blob_upload_session": "partial upload sessions in transit",
    "device_policy_snapshot": "policy copies pushed to phones",
}

# Credentials and device secrets: the column is dropped from the file.
REDACTED_COLUMNS: dict[str, frozenset[str]] = {
    "push_device": frozenset({"token", "token_sha256"}),
    "tracker": frozenset({"credentials_ref"}),
}

# Columns whose name looks like a credential but which are not (matched by SECRET_LIKE in the guard test).
NOT_SECRETS: frozenset[str] = frozenset(
    {
        "anomaly_case.group_key",
        "app_user.keycloak_subject",
        "capture_attachment.object_key",
        "customer_acknowledgement.signature_attachment_id",
        "device_policy_snapshot.scope_key",
        "job_exception.dedupe_key",
        "machine_photo.object_key",
        "mandate_assignment.role_key",
        "model_readiness.feature_set_hash",
        "model_version.artifact_key",
        "model_version.feature_set_hash",
        "notification.dedupe_key",
        "notification_preference.scope_key",
        "notification_routing.scope_key",
        "prediction.feature_set_hash",
        "revenue_difference.period_key",
        "risk_signal.dedupe_key",
        "staff_member.keycloak_subject",
        "tenant_setup_choice.step_key",
        "tracking_alert.dedupe_key",
        "work_allocation.origin_key",
    }
)
SECRET_LIKE = re.compile(r"(token|secret|password|credential|hash|_key|pin$|^pin|otp|signature|encrypted)", re.I)

# Partitions are skipped: selecting from the parent table already covers them.
TENANT_TABLES = """
SELECT c.relname FROM pg_class c
WHERE c.relnamespace = 'public'::regnamespace AND c.relkind IN ('r', 'p') AND NOT c.relispartition
  AND c.relname <> 'tenant'
  AND EXISTS (SELECT 1 FROM pg_attribute a WHERE a.attrelid = c.oid AND a.attname = 'tenant_id' AND NOT a.attisdropped)
ORDER BY 1
"""
TABLE_COLUMNS = """
SELECT a.attname FROM pg_attribute a
WHERE a.attrelid = to_regclass(:t) AND a.attnum > 0 AND NOT a.attisdropped
ORDER BY a.attnum
"""


def export_tables(session: Session) -> list[str]:
    return [t for t in session.execute(text(TENANT_TABLES)).scalars() if t not in EXCLUDED]


def table_columns(session: Session, table: str) -> list[str]:
    redacted = REDACTED_COLUMNS.get(table, frozenset())
    return [c for c in session.execute(text(TABLE_COLUMNS), {"t": table}).scalars() if c not in redacted]
