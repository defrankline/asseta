import Foundation

/// Migration 8 (stronger remittances, DEC-031 D2), non-destructive like migration 7: `local_attachment` also allows
/// purpose `REMITTANCE_EVIDENCE` (deposit slip / payment confirmation photo of a CASH_HANDOVER, uploaded like reading
/// photos and appended to `evidence_upload_ids` when complete). `operation_attachment` is copied unchanged (its
/// `evidence_upload_ids` field already exists) because it references `local_attachment`.
enum RemittanceV8 {
    static let statements: [String] = [
        "ALTER TABLE operation_attachment RENAME TO operation_attachment_v7",
        "ALTER TABLE local_attachment RENAME TO local_attachment_v7",
        """
        CREATE TABLE local_attachment (
            id TEXT PRIMARY KEY NOT NULL CHECK (length(id) = 36),
            tenant_id TEXT NOT NULL CHECK (length(tenant_id) = 36),
            purpose TEXT NOT NULL
                CHECK (purpose IN ('METER_PHOTO','SIGNATURE','RESET_EVIDENCE','EXPENSE_RECEIPT','PAYMENT_EVIDENCE',
                    'REMITTANCE_EVIDENCE')),
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
            owner_subject TEXT NULL,
            CHECK (status <> 'COMPLETE' OR attachment_id IS NOT NULL)
        )
        """,
        """
        INSERT INTO local_attachment (id, tenant_id, purpose, file_name, sha256, size_bytes, content_type, status,
            session_id, session_expires_at, chunk_size, received_chunks, attachment_id, attempt_count, last_error,
            next_attempt_at, created_at, owner_subject)
        SELECT id, tenant_id, purpose, file_name, sha256, size_bytes, content_type, status, session_id,
            session_expires_at, chunk_size, received_chunks, attachment_id, attempt_count, last_error,
            next_attempt_at, created_at, owner_subject
        FROM local_attachment_v7
        """,
        """
        CREATE TABLE operation_attachment (
            operation_id TEXT NOT NULL REFERENCES client_operation(id) ON DELETE CASCADE,
            attachment_local_id TEXT NOT NULL REFERENCES local_attachment(id) ON DELETE RESTRICT,
            payload_field TEXT NOT NULL CHECK (payload_field IN
                ('photo_attachment_id','signature_attachment_id','receipt_upload_ids','evidence_upload_id',
                 'evidence_upload_ids','replacement.photo_attachment_id')),
            PRIMARY KEY (operation_id, attachment_local_id)
        )
        """,
        """
        INSERT INTO operation_attachment (operation_id, attachment_local_id, payload_field)
        SELECT operation_id, attachment_local_id, payload_field FROM operation_attachment_v7
        """,
        "DROP TABLE operation_attachment_v7",
        "DROP TABLE local_attachment_v7",
        "CREATE INDEX ix_local_attachment_status ON local_attachment (tenant_id, status, created_at)",
        "CREATE INDEX ix_operation_attachment_local ON operation_attachment (attachment_local_id)",
    ]
}
