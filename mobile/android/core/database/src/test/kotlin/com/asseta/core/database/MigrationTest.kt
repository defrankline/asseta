package com.asseta.core.database

import androidx.room.testing.MigrationTestHelper
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

/** v1 -> v2 keeps every outbox row (unsynced evidence) and carries legacy dependencies into the new table. */
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

    private companion object {
        const val DB = "migration-test.db"
    }
}
