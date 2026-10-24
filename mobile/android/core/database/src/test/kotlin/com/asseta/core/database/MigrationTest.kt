package com.asseta.core.database

import androidx.room.Room
import androidx.room.testing.MigrationTestHelper
import androidx.test.platform.app.InstrumentationRegistry
import com.asseta.core.model.SyncAccount
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

/**
 * v1 -> v2 keeps every outbox row (unsynced evidence) and carries legacy dependencies into the new table.
 * v2 -> v3 adds the field-finance tables without touching the outbox, attachments or cached server data.
 * v3 -> v4 adds the Owner app's `read_snapshot` cache table.
 * v4 -> v5 moves queued single-attachment gates into `client_operation_attachment` (several receipts per expense).
 * v5 -> v6 records the owning user of sync state, outbox operations, attachments and work-log entries.
 * v6 -> v7 adds the supervisor inbox table `inbox_record` (server copies of the supervisor's own records).
 * v7 -> v8 adds the nullable job request columns (`cancellation_reason`, `requested_by_staff_id`, `request_note`).
 */
@RunWith(RobolectricTestRunner::class)
class MigrationTest {
    @get:Rule
    val helper = MigrationTestHelper(InstrumentationRegistry.getInstrumentation(), AssetaDatabase::class.java)

    @Test
    fun migrate1To2KeepsOutboxAndDependencies() {
        helper.createDatabase(DB, 1).use { db ->
            db.execSQL(
                """INSERT INTO client_operation (id, tenant_id, op_type, entity_type, entity_id, payload_json, depends_on,
                   created_at_device, status, attempt_count, last_error, server_revision) VALUES
                   ('p', 't', 'METER_CAPTURE', 'e', 'x', '{}', NULL, 1, 'PENDING', 0, NULL, NULL),
                   ('c', 't', 'JOB_TRANSITION', 'e', 'y', '{}', 'p', 2, 'PENDING', 0, NULL, NULL)""",
            )
        }
        helper.runMigrationsAndValidate(DB, 2, true).use { db ->
            db.query("SELECT COUNT(*) FROM client_operation").use { c -> c.moveToFirst(); assertEquals(2, c.getInt(0)) }
            db.query("SELECT operation_id, depends_on_id FROM client_operation_dependency").use { c ->
                c.moveToFirst()
                assertEquals("c" to "p", c.getString(0) to c.getString(1))
                assertEquals(1, c.count)
            }
            db.query("SELECT job_id, error_code, result_json FROM client_operation WHERE id = 'c'").use { c ->
                c.moveToFirst()
                assertEquals(true, c.isNull(0) && c.isNull(1) && c.isNull(2))
            }
        }
    }

    @Test
    fun migrate2To3KeepsUnsyncedWorkAndAddsFinanceTables() {
        helper.createDatabase(DB, 2).use { db ->
            db.execSQL(
                """INSERT INTO attachment (id, tenant_id, purpose, file_name, sha256, size_bytes, content_type, status,
                   attempt_count, created_at) VALUES ('a1', 't', 'METER_PHOTO', 'f.bin', 'abc', 10, 'image/jpeg', 'PENDING', 0, 1)""",
            )
            db.execSQL(
                """INSERT INTO client_operation (id, tenant_id, op_type, entity_type, entity_id, payload_json, depends_on,
                   created_at_device, status, attempt_count, last_error, server_revision, job_id, attachment_local_id) VALUES
                   ('p', 't', 'METER_CAPTURE', 'meter_capture.OPENING', 'x', '{"reading":"1.5"}', NULL, 1, 'PENDING', 0,
                    NULL, NULL, 'j', 'a1'),
                   ('c', 't', 'JOB_TRANSITION', 'job_transition.START', 'j', '{}', NULL, 2, 'QUARANTINED', 3,
                    NULL, NULL, 'j', NULL)""",
            )
            db.execSQL("INSERT INTO client_operation_dependency (operation_id, depends_on_id) VALUES ('c', 'p')")
            db.execSQL(
                """INSERT INTO policy_snapshot (tenant_id, policy_type, scope_key, version_ids_json, version_stamp,
                   values_json, valid_until, received_at) VALUES ('t', 'METER_CAPTURE', 'tenant', '[]', 's', '{}', 5, 1)""",
            )
            db.execSQL("INSERT INTO sync_state (tenant_id, cursor, failure_streak, server_clock_alert) VALUES ('t', 42, 0, 0)")
            db.execSQL(
                """INSERT INTO job (id, tenant_id, job_number, machine_id, contract_id, job_site_id, status, version,
                   planned_start, planned_end, standby_treatment) VALUES ('j', 't', 'J-1', 'm', 'c', NULL, 'APPROVED', 3,
                   '2026-10-21T06:00:00Z', NULL, NULL)""",
            )
        }
        helper.runMigrationsAndValidate(DB, 3, true).use { db ->
            fun count(sql: String) = db.query(sql).use { c -> c.moveToFirst(); c.getInt(0) }
            assertEquals(2, count("SELECT COUNT(*) FROM client_operation"))
            assertEquals(1, count("SELECT COUNT(*) FROM client_operation WHERE id = 'p' AND status = 'PENDING' AND attachment_local_id = 'a1'"))
            assertEquals(1, count("SELECT COUNT(*) FROM client_operation WHERE id = 'c' AND status = 'QUARANTINED' AND attempt_count = 3"))
            assertEquals(1, count("SELECT COUNT(*) FROM client_operation_dependency"))
            assertEquals(1, count("SELECT COUNT(*) FROM attachment WHERE status = 'PENDING'"))
            assertEquals(1, count("SELECT COUNT(*) FROM policy_snapshot"))
            assertEquals(42, count("SELECT cursor FROM sync_state WHERE tenant_id = 't'"))
            assertEquals(1, count("SELECT COUNT(*) FROM job WHERE id = 'j' AND version = 3 AND currency IS NULL"))
            assertEquals(0, count("SELECT COUNT(*) FROM expense_category"))
            db.execSQL(
                """INSERT INTO expense_category (id, tenant_id, code, name, is_active, sync_revision, version)
                   VALUES ('cat', 't', 'FUEL', 'Fuel', 1, 7, 1)""",
            )
            db.execSQL(
                """INSERT INTO cash_custody_balance (tenant_id, currency, staff_member_id, outstanding,
                   claimed_unverified_handovers, pending_spending, as_of, received_at)
                   VALUES ('t', 'TZS', 's', '500000.0000', '0', '0', 1, 1)""",
            )
            db.query("SELECT outstanding FROM cash_custody_balance").use { c ->
                c.moveToFirst()
                assertEquals("500000.0000", c.getString(0)) // exact decimal text, never a REAL
            }
        }
    }

    @Test
    fun migrate1To3InOneGo() {
        helper.createDatabase(DB, 1).use { db ->
            db.execSQL(
                """INSERT INTO client_operation (id, tenant_id, op_type, entity_type, entity_id, payload_json, depends_on,
                   created_at_device, status, attempt_count, last_error, server_revision) VALUES
                   ('p', 't', 'METER_CAPTURE', 'e', 'x', '{}', NULL, 1, 'PENDING', 0, NULL, NULL)""",
            )
        }
        helper.runMigrationsAndValidate(DB, 3, true).use { db ->
            db.query("SELECT COUNT(*) FROM client_operation").use { c -> c.moveToFirst(); assertEquals(1, c.getInt(0)) }
        }
    }

    @Test
    fun migrate3To4KeepsFieldDataAndAddsOwnerSnapshots() {
        helper.createDatabase(DB, 3).use { db ->
            db.execSQL(
                """INSERT INTO client_operation (id, tenant_id, op_type, entity_type, entity_id, payload_json, depends_on,
                   created_at_device, status, attempt_count, last_error, server_revision) VALUES
                   ('p', 't', 'METER_CAPTURE', 'e', 'x', '{}', NULL, 1, 'PENDING', 0, NULL, NULL)""",
            )
        }
        helper.runMigrationsAndValidate(DB, 4, true).use { db ->
            fun count(sql: String) = db.query(sql).use { c -> c.moveToFirst(); c.getInt(0) }
            assertEquals(1, count("SELECT COUNT(*) FROM client_operation WHERE status = 'PENDING'"))
            db.execSQL("INSERT INTO read_snapshot (tenant_id, cache_key, payload_json, fetched_at) VALUES ('t', 'overview', '{}', 1)")
            assertEquals(1, count("SELECT COUNT(*) FROM read_snapshot"))
        }
    }

    @Test
    fun migrate4To5MovesQueuedAttachmentGatesIntoTheLinkTable() {
        helper.createDatabase(DB, 4).use { db ->
            db.execSQL(
                """INSERT INTO attachment (id, tenant_id, purpose, file_name, sha256, size_bytes, content_type, status,
                   attempt_count, created_at) VALUES
                   ('a1', 't', 'EXPENSE_RECEIPT', 'f.bin', 'abc', 10, 'image/jpeg', 'PENDING', 2, 1),
                   ('a2', 't', 'METER_PHOTO', 'g.bin', 'def', 10, 'image/jpeg', 'COMPLETE', 1, 1)""",
            )
            db.execSQL("UPDATE attachment SET server_attachment_id = 'srv-2' WHERE id = 'a2'")
            db.execSQL(
                """INSERT INTO client_operation (id, tenant_id, op_type, entity_type, entity_id, payload_json, depends_on,
                   created_at_device, status, attempt_count, last_error, server_revision, job_id, attachment_local_id) VALUES
                   ('e', 't', 'EXPENSE', 'expense', 'x', '{"receipt_upload_ids":[]}', NULL, 1, 'PENDING', 0, NULL, NULL, NULL, 'a1'),
                   ('m', 't', 'METER_CAPTURE', 'meter_capture.OPENING', 'y', '{}', NULL, 2, 'ACKED', 1, NULL, 3, 'j', 'a2'),
                   ('h', 't', 'CASH_HANDOVER', 'cash_handover', 'z', '{}', NULL, 3, 'PENDING', 0, NULL, NULL, NULL, NULL)""",
            )
            db.execSQL("INSERT INTO sync_state (tenant_id, cursor, failure_streak, server_clock_alert) VALUES ('t', 42, 2, 0)")
        }
        helper.runMigrationsAndValidate(DB, 5, true).use { db ->
            fun count(sql: String) = db.query(sql).use { c -> c.moveToFirst(); c.getInt(0) }
            assertEquals(3, count("SELECT COUNT(*) FROM client_operation"))
            assertEquals(2, count("SELECT COUNT(*) FROM client_operation_attachment"))
            assertEquals(1, count("SELECT COUNT(*) FROM client_operation_attachment WHERE operation_id = 'e' AND attachment_local_id = 'a1'"))
            assertEquals(1, count("SELECT COUNT(*) FROM client_operation_attachment WHERE operation_id = 'm' AND attachment_local_id = 'a2'"))
            assertEquals(1, count("SELECT COUNT(*) FROM attachment WHERE id = 'a1' AND status = 'PENDING' AND attempt_count = 2 AND next_attempt_at IS NULL"))
            assertEquals(1, count("SELECT COUNT(*) FROM sync_state WHERE cursor = 42 AND failure_streak = 2 AND next_sync_at IS NULL"))
        }
        // The migrated outbox keeps working through Room: the expense still waits for its receipt, then is sent.
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val room = Room.databaseBuilder(context, AssetaDatabase::class.java, DB).allowMainThreadQueries()
            .addMigrations(*AssetaMigrations.all(LEGACY)).build()
        try {
            runBlocking {
                val ops = room.clientOperationDao()
                assertEquals(listOf("h"), ops.dispatchable("t", LEGACY.subject, 10).map { it.id })
                assertEquals(listOf("a1"), ops.attachmentsOf("e"))
                assertEquals(listOf("e"), ops.forAttachment("a1").map { it.id })
                room.evidenceDao().markAttachmentComplete("a1", "srv-1")
                assertEquals(listOf("e", "h"), ops.dispatchable("t", LEGACY.subject, 10).map { it.id })
            }
        } finally {
            room.close()
        }
    }

    private fun seedV5(db: androidx.sqlite.db.SupportSQLiteDatabase) {
        db.execSQL(
            """INSERT INTO attachment (id, tenant_id, purpose, file_name, sha256, size_bytes, content_type, status,
               attempt_count, created_at) VALUES ('a1', 't', 'METER_PHOTO', 'f.bin', 'abc', 10, 'image/jpeg', 'PENDING', 0, 1)""",
        )
        db.execSQL(
            """INSERT INTO client_operation (id, tenant_id, op_type, entity_type, entity_id, payload_json, depends_on,
               created_at_device, status, attempt_count, last_error, server_revision, job_id) VALUES
               ('p', 't', 'METER_CAPTURE', 'meter_capture.OPENING', 'x', '{}', NULL, 1, 'PENDING', 0, NULL, NULL, 'j'),
               ('h', 't', 'CASH_HANDOVER', 'cash_handover', 'z', '{}', NULL, 2, 'PENDING', 0, NULL, NULL, NULL)""",
        )
        db.execSQL("INSERT INTO client_operation_attachment (operation_id, attachment_local_id) VALUES ('p', 'a1')")
        db.execSQL(
            """INSERT INTO work_log_entry (client_id, tenant_id, job_id, activity_type, started_at, ended_at, note, operation_id)
               VALUES ('w', 't', 'j', 'WORK', 1, NULL, NULL, NULL)""",
        )
        db.execSQL("INSERT INTO sync_state (tenant_id, cursor, failure_streak, server_clock_alert) VALUES ('t', 53, 0, 0)")
    }

    @Test
    fun migrate5To6GivesExistingFieldDataToTheUserSignedInAtUpgrade() {
        helper.createDatabase(DB, 5).use(::seedV5)
        helper.runMigrationsAndValidate(DB, 6, true, AssetaMigrations.V5ToV6(LEGACY)).use { db ->
            fun count(sql: String) = db.query(sql).use { c -> c.moveToFirst(); c.getInt(0) }
            val owner = LEGACY.subject
            assertEquals(2, count("SELECT COUNT(*) FROM client_operation WHERE owner_sub = '$owner' AND owner_label = '${LEGACY.label}'"))
            assertEquals(1, count("SELECT COUNT(*) FROM attachment WHERE owner_sub = '$owner'"))
            assertEquals(1, count("SELECT COUNT(*) FROM work_log_entry WHERE owner_sub = '$owner'"))
            assertEquals(1, count("SELECT COUNT(*) FROM sync_state WHERE owner_sub = '$owner' AND cursor = 53"))
        }
        // Through Room: the same user keeps working on (and syncing) everything; another user gets none of it.
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val room = Room.databaseBuilder(context, AssetaDatabase::class.java, DB).allowMainThreadQueries()
            .addMigrations(*AssetaMigrations.all(LEGACY)).build()
        try {
            runBlocking {
                val ops = room.clientOperationDao()
                assertEquals(listOf("h"), ops.dispatchable("t", LEGACY.subject, 10).map { it.id })
                assertEquals(emptyList<String>(), ops.dispatchable("t", "someone-else", 10).map { it.id })
                assertEquals(listOf("a1"), room.evidenceDao().uploadableAttachments("t", LEGACY.subject, 10, 10).map { it.id })
                assertEquals(emptyList<String>(), room.syncStateDao().tenantsNotOwnedBy(LEGACY.subject))
                assertEquals(listOf("t"), room.syncStateDao().tenantsNotOwnedBy("someone-else"))
            }
        } finally {
            room.close()
        }
    }

    @Test
    fun migrate5To6WithNobodySignedInHoldsExistingWorkForAnUnknownPreviousUser() {
        helper.createDatabase(DB, 5).use(::seedV5)
        helper.runMigrationsAndValidate(DB, 6, true, AssetaMigrations.V5ToV6(null)).use { db ->
            fun count(sql: String) = db.query(sql).use { c -> c.moveToFirst(); c.getInt(0) }
            val unknown = SyncAccount.UNKNOWN_SUBJECT
            assertEquals(2, count("SELECT COUNT(*) FROM client_operation WHERE owner_sub = '$unknown' AND owner_label IS NULL"))
            assertEquals(1, count("SELECT COUNT(*) FROM attachment WHERE owner_sub = '$unknown'"))
            assertEquals(1, count("SELECT COUNT(*) FROM sync_state WHERE owner_sub = '$unknown'"))
        }
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val room = Room.databaseBuilder(context, AssetaDatabase::class.java, DB).allowMainThreadQueries()
            .addMigrations(*AssetaMigrations.all(null)).build()
        try {
            runBlocking {
                val ops = room.clientOperationDao()
                // Whoever signs in next resets the tenant's sync state and never sends or sees the held work.
                assertEquals(listOf("t"), room.syncStateDao().tenantsNotOwnedBy("next-user"))
                assertEquals(emptyList<String>(), ops.dispatchable("t", "next-user", 10).map { it.id })
                val held = ops.observeHeld("t", "next-user").first().single()
                assertEquals(SyncAccount.UNKNOWN_SUBJECT to 2, held.ownerSub to held.count)
                assertNull(held.ownerLabel)
            }
        } finally {
            room.close()
        }
    }

    @Test
    fun migrate6To7KeepsEverythingAndAddsTheInbox() {
        helper.createDatabase(DB, 5).use(::seedV5)
        helper.runMigrationsAndValidate(DB, 6, true, AssetaMigrations.V5ToV6(LEGACY)).close()
        helper.runMigrationsAndValidate(DB, 7, true, AssetaMigrations.V5ToV6(LEGACY)).use { db ->
            fun count(sql: String) = db.query(sql).use { c -> c.moveToFirst(); c.getInt(0) }
            assertEquals(2, count("SELECT COUNT(*) FROM client_operation WHERE owner_sub = '${LEGACY.subject}'"))
            assertEquals(1, count("SELECT COUNT(*) FROM work_log_entry"))
            assertEquals(1, count("SELECT COUNT(*) FROM sync_state WHERE cursor = 53 AND capabilities IS NULL"))
            assertEquals(0, count("SELECT COUNT(*) FROM inbox_record"))
        }
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val room = Room.databaseBuilder(context, AssetaDatabase::class.java, DB).allowMainThreadQueries()
            .addMigrations(*AssetaMigrations.all(LEGACY)).build()
        try {
            runBlocking {
                val inbox = room.inboxDao()
                fun rec(rev: Long, status: String, at: Long) =
                    InboxRecordEntity(InboxRecordEntity.EXPENSE, "e1", "t", "c1", null, null, status, at, rev, "{\"rev\":$rev}")
                assertEquals(1, inbox.upsert(listOf(rec(5, "PENDING_APPROVAL", 10))))
                // An older (replayed) revision never overwrites a newer one; a newer one does.
                assertEquals(0, inbox.upsert(listOf(rec(4, "APPROVED", 10))))
                assertEquals("PENDING_APPROVAL", inbox.kind("t", InboxRecordEntity.EXPENSE).single().status)
                assertEquals(1, inbox.upsert(listOf(rec(6, "REJECTED", 10))))
                assertEquals("REJECTED", inbox.observeKind("t", InboxRecordEntity.EXPENSE).first().single().status)
                // Pruning keeps records still waiting for the office.
                inbox.upsert(listOf(rec(7, "PENDING_APPROVAL", 10).copy(id = "e2")))
                assertEquals(1, inbox.prune("t", 100, InboxRecordEntity.OPEN_STATUSES))
                assertEquals(listOf("e2"), inbox.kind("t", InboxRecordEntity.EXPENSE).map { it.id })
                assertEquals(1, inbox.deleteTenant("t"))
            }
        } finally {
            room.close()
        }
    }

    @Test
    fun migrate7To8KeepsJobsAndAddsRequestColumns() {
        helper.createDatabase(DB, 7).use { db ->
            db.execSQL(
                """INSERT INTO job (id, tenant_id, job_number, machine_id, contract_id, job_site_id, status, version,
                   planned_start, planned_end, standby_treatment, currency) VALUES ('j', 't', 'J-1', 'm', 'c', NULL, 'APPROVED', 3,
                   '2026-10-21T06:00:00Z', NULL, NULL, 'TZS')""",
            )
        }
        helper.runMigrationsAndValidate(DB, 8, true).use { db ->
            db.query("SELECT job_number, cancellation_reason, requested_by_staff_id, request_note FROM job").use { c ->
                c.moveToFirst()
                assertEquals("J-1", c.getString(0))
                assertEquals(true, c.isNull(1) && c.isNull(2) && c.isNull(3))
            }
        }
    }

    private companion object {
        const val DB = "migration-test.db"
        val LEGACY = SyncAccount("legacy-user-sub", "sam@example.com")
    }
}
