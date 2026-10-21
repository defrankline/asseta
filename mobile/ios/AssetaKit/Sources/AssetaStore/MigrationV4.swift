import Foundation

/// Migration 4 (Gate 5 field finance), non-destructive:
/// - rebuilds `local_attachment` so its purpose CHECK also allows `EXPENSE_RECEIPT`, and
///   `operation_attachment` so a receipt upload can fill `receipt_upload_ids` (an array) in the
///   waiting EXPENSE payload. SQLite cannot alter CHECKs, so both tables are copied row by row.
///   With `foreign_keys = ON` (and no way to switch it off inside the migration transaction) the
///   child table is renamed first, then the parent, so dropping the old copies never violates a
///   reference;
/// - adds `cash_custody_balance`: the supervisor's server-computed custody per currency, replaced
///   on every bootstrap/changes response (it is a balance, not an entity with an id).
/// Expense categories are server-owned entities and live in `sync_entity` (type `expense_category`).
enum FinanceV4 {
    static let statements: [String] = [
        "ALTER TABLE operation_attachment RENAME TO operation_attachment_v3",
        "ALTER TABLE local_attachment RENAME TO local_attachment_v3",
        """
        CREATE TABLE local_attachment (
            id TEXT PRIMARY KEY NOT NULL CHECK (length(id) = 36),
            tenant_id TEXT NOT NULL CHECK (length(tenant_id) = 36),
            purpose TEXT NOT NULL
                CHECK (purpose IN ('METER_PHOTO','SIGNATURE','RESET_EVIDENCE','EXPENSE_RECEIPT')),
            file_name TEXT NOT NULL CHECK (length(file_name) > 0),
            sha256 TEXT NOT NULL CHECK (length(sha256) = 64),
            size_bytes INTEGER NOT NULL CHECK (size_bytes > 0),
            content_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','COMPLETE','FAILED')),
            session_id TEXT NULL,
            session_expires_at INTEGER NULL,
            chunk_size INTEGER NULL CHECK (chunk_size IS NULL OR chunk_size > 0),
            received_chunks TEXT NOT NULL DEFAULT '',
            attachment_id TEXT NULL,
            attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
            last_error TEXT NULL,
            next_attempt_at INTEGER NULL,
            created_at INTEGER NOT NULL,
            CHECK (status <> 'COMPLETE' OR attachment_id IS NOT NULL)
        )
        """,
        """
        INSERT INTO local_attachment (id, tenant_id, purpose, file_name, sha256, size_bytes, content_type, status,
            session_id, session_expires_at, chunk_size, received_chunks, attachment_id, attempt_count, last_error,
            next_attempt_at, created_at)
        SELECT id, tenant_id, purpose, file_name, sha256, size_bytes, content_type, status, session_id,
            session_expires_at, chunk_size, received_chunks, attachment_id, attempt_count, last_error,
            next_attempt_at, created_at
        FROM local_attachment_v3
        """,
        """
        CREATE TABLE operation_attachment (
            operation_id TEXT NOT NULL REFERENCES client_operation(id) ON DELETE CASCADE,
            attachment_local_id TEXT NOT NULL REFERENCES local_attachment(id) ON DELETE RESTRICT,
            payload_field TEXT NOT NULL
                CHECK (payload_field IN ('photo_attachment_id','signature_attachment_id','receipt_upload_ids')),
            PRIMARY KEY (operation_id, attachment_local_id)
        )
        """,
        """
        INSERT INTO operation_attachment (operation_id, attachment_local_id, payload_field)
        SELECT operation_id, attachment_local_id, payload_field FROM operation_attachment_v3
        """,
        "DROP TABLE operation_attachment_v3",
        "DROP TABLE local_attachment_v3",
        "CREATE INDEX ix_local_attachment_status ON local_attachment (tenant_id, status, created_at)",
        "CREATE INDEX ix_operation_attachment_local ON operation_attachment (attachment_local_id)",
        """
        CREATE TABLE cash_custody_balance (
            tenant_id TEXT NOT NULL CHECK (length(tenant_id) = 36),
            staff_member_id TEXT NOT NULL CHECK (length(staff_member_id) = 36),
            currency TEXT NOT NULL CHECK (length(currency) = 3),
            json TEXT NOT NULL CHECK (json_valid(json)),
            as_of INTEGER NOT NULL,
            PRIMARY KEY (tenant_id, staff_member_id, currency)
        )
        """,
    ]
}
