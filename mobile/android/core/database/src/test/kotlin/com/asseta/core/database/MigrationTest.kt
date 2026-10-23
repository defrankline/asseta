package com.asseta.core.database

import androidx.room.Room
import androidx.room.testing.MigrationTestHelper
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

/**
 * v1 -> v2 keeps every outbox row (unsynced evidence) and carries legacy dependencies into the new table.
 * v2 -> v3 adds the field-finance tables without touching the outbox, attachments or cached server data.
 * v3 -> v4 adds the Owner app's `read_snapshot` cache table.
 * v4 -> v5 moves queued single-attachment gates into `client_operation_attachment` (several receipts per expense).
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
        val room = Room.databaseBuilder(context, AssetaDatabase::class.java, DB).allowMainThreadQueries().build()
        try {
            runBlocking {
                val ops = room.clientOperationDao()
                assertEquals(listOf("h"), ops.dispatchable("t", 10).map { it.id })
                assertEquals(listOf("a1"), ops.attachmentsOf("e"))
                assertEquals(listOf("e"), ops.forAttachment("a1").map { it.id })
                room.evidenceDao().markAttachmentComplete("a1", "srv-1")
                assertEquals(listOf("e", "h"), ops.dispatchable("t", 10).map { it.id })
            }
        } finally {
            room.close()
        }
    }

    private companion object {
        const val DB = "migration-test.db"
    }
}
