package com.asseta.core.database

import androidx.room.migration.AutoMigrationSpec
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase

/**
 * Every schema change bumps [AssetaDatabase.VERSION], commits the exported schema JSON under
 * `schemas/`, and adds an explicit [Migration] (or a Room AutoMigration) here with a migration test.
 * Destructive fallback is never enabled: the outbox may hold unsynced field evidence.
 */
object AssetaMigrations {
    val ALL: Array<Migration> = emptyArray()

    /**
     * v1 -> v2 (Gate 4): outbox columns (job, error code, server result, attachment gate, last attempt), multi-parent
     * dependency table, cached server data, policy snapshots, sync state and local evidence tables. Room generates the
     * DDL from the committed schemas; this spec carries v1 single dependencies over into the new dependency table.
     */
    /*
     * v2 -> v3 (Gate 5 field finance): new tables `expense_category` and `cash_custody_balance` plus the nullable
     * `job.currency` column (Room AutoMigration, purely additive). Finance operations reuse the existing outbox and
     * attachment tables; the EXPENSE_CAPTURE policy snapshot reuses `policy_snapshot`. No existing row is changed.
     */
    /*
     * v3 -> v4 (Gate 7 Owner app): new table `read_snapshot` (offline read-only cache of server responses, bounded and
     * wiped on sign-out). Purely additive AutoMigration; the Supervisor's outbox and cached field data are untouched.
     */

    /**
     * v4 -> v5 (mobile parity with iOS): several evidence files per operation (an expense carries up to ten receipt
     * photos) in the new `client_operation_attachment` link table; `attachment.next_attempt_at` (an upload the server
     * refused is retried later, not in a tight loop) and the FAILED attachment status (evidence that can never be
     * uploaded, shown on the sync screen); `sync_state.next_sync_at` (the backoff time of the next automatic retry).
     * Additive AutoMigration; this spec carries every queued operation's legacy single attachment gate into the link
     * table so operations queued before the update keep waiting for (and are patched by) their upload.
     */
    class V4ToV5 : AutoMigrationSpec {
        override fun onPostMigrate(db: SupportSQLiteDatabase) {
            db.execSQL(
                """INSERT OR IGNORE INTO client_operation_attachment (operation_id, attachment_local_id)
                   SELECT id, attachment_local_id FROM client_operation WHERE attachment_local_id IS NOT NULL""",
            )
        }
    }

    class V1ToV2 : AutoMigrationSpec {
        override fun onPostMigrate(db: SupportSQLiteDatabase) {
            db.execSQL(
                """INSERT OR IGNORE INTO client_operation_dependency (operation_id, depends_on_id)
                   SELECT id, depends_on FROM client_operation WHERE depends_on IS NOT NULL""",
            )
        }
    }
}
