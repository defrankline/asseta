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

    class V1ToV2 : AutoMigrationSpec {
        override fun onPostMigrate(db: SupportSQLiteDatabase) {
            db.execSQL(
                """INSERT OR IGNORE INTO client_operation_dependency (operation_id, depends_on_id)
                   SELECT id, depends_on FROM client_operation WHERE depends_on IS NOT NULL""",
            )
        }
    }
}
