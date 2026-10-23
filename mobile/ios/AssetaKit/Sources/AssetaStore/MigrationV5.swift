import AssetaModel
import Foundation

/// Migration 5 (per-user field data on a shared phone), additive: the owner (Keycloak `sub`, plus a
/// readable label) of every outbox operation and evidence file. The owner of a tenant's sync state
/// (cursor, registration, cached server data) is the `owner_subject` key in `sync_kv`, and a running
/// work-log entry's key carries its owner. Rows from before this migration have no owner until
/// ``LocalStore/adoptLegacyData(owner:)`` gives them to the user signed in at app launch (or to
/// ``AccountIdentity/unknownSubject``, "a previous account").
enum OwnersV5 {
    static let statements: [String] = [
        "ALTER TABLE client_operation ADD COLUMN owner_subject TEXT NULL",
        "ALTER TABLE client_operation ADD COLUMN owner_label TEXT NULL",
        "ALTER TABLE local_attachment ADD COLUMN owner_subject TEXT NULL",
        "CREATE INDEX ix_client_operation_owner ON client_operation (tenant_id, owner_subject, status)",
    ]
}

extension LocalStore {
    /// Gives field data written before owners were recorded (migration 5) to `owner` — the user
    /// signed in when the app launched, before any new sign-in — or, when nobody was, to an unknown
    /// previous account (its work is held, never given to whoever signs in next). Idempotent: rows
    /// written since always carry their owner.
    public func adoptLegacyData(owner: AccountIdentity?) throws {
        let subject = owner?.subject ?? AccountIdentity.unknownSubject
        try database.transaction {
            try database.execute("UPDATE client_operation SET owner_subject = ?, owner_label = ? WHERE owner_subject IS NULL",
                                 [.text(subject), .optionalText(owner?.label)])
            try database.execute("UPDATE local_attachment SET owner_subject = ? WHERE owner_subject IS NULL", [.text(subject)])
            // Tenants synced before: their cursor and cached data belong to the same owner.
            try database.execute(
                """
                INSERT INTO sync_kv (tenant_id, key, value)
                SELECT DISTINCT tenant_id, ?, ? FROM sync_kv
                WHERE tenant_id <> ? AND key NOT LIKE 'work_log_running.%'
                  AND tenant_id NOT IN (SELECT tenant_id FROM sync_kv WHERE key = ?)
                """,
                [.text(SyncStateStore.ownerKey), .text(subject), .text(SyncStateStore.deviceScope),
                 .text(SyncStateStore.ownerKey)]
            )
            // Running work-log entries ("work_log_running.<job>") move to their owner's key.
            try database.execute(
                """
                UPDATE sync_kv SET key = 'work_log_running.' || ? || '.' || substr(key, 18)
                WHERE key LIKE 'work_log_running.%' AND length(key) = 53
                """,
                [.text(subject)]
            )
        }
    }
}
