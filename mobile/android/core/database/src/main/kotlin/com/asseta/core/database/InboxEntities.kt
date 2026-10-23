package com.asseta.core.database

import androidx.room.ColumnInfo
import androidx.room.Dao
import androidx.room.Entity
import androidx.room.Index
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Transaction
import kotlinx.coroutines.flow.Flow

/**
 * v7 supervisor inbox: the signed-in supervisor's own field records as the server knows them (capability
 * SUPERVISOR_INBOX_V1: readings with findings, meter resets, work log, acknowledgements, expenses, fuel, cash
 * collections and handovers). Server-owned and read-only: kept as the server JSON with the columns lists filter and
 * sort on, upserted by (kind, id, sync_revision) and cleared with the tenant's other server data on a user switch.
 */
@Entity(
    tableName = "inbox_record",
    primaryKeys = ["kind", "id"],
    indices = [Index(value = ["tenant_id", "kind", "occurred_at"]), Index(value = ["client_id"]), Index(value = ["job_id"])],
)
data class InboxRecordEntity(
    @ColumnInfo(name = "kind") val kind: String,
    @ColumnInfo(name = "id") val id: String,
    @ColumnInfo(name = "tenant_id") val tenantId: String,
    /** Device client id of the record (null for server-created ones); a meter capture's id is its client id. */
    @ColumnInfo(name = "client_id") val clientId: String?,
    @ColumnInfo(name = "job_id") val jobId: String?,
    @ColumnInfo(name = "machine_id") val machineId: String?,
    /** Server status (capture state or review status, expense/settlement/reset status); null when it has none. */
    @ColumnInfo(name = "status") val status: String?,
    /** When it happened (captured / started / incurred / received / handed), epoch ms: list order and pruning. */
    @ColumnInfo(name = "occurred_at") val occurredAt: Long,
    @ColumnInfo(name = "sync_revision") val syncRevision: Long,
    @ColumnInfo(name = "json") val json: String,
) {
    companion object {
        const val METER_CAPTURE = "METER_CAPTURE"
        const val METER_RESET = "METER_RESET"
        const val JOB_ACTIVITY = "JOB_ACTIVITY"
        const val ACKNOWLEDGEMENT = "ACKNOWLEDGEMENT"
        const val EXPENSE = "EXPENSE"
        const val FUEL_EVENT = "FUEL_EVENT"
        const val CASH_COLLECTION = "CASH_COLLECTION"
        const val CASH_HANDOVER = "CASH_HANDOVER"

        /** Statuses that keep a record past the pruning window (still waiting for the office). */
        val OPEN_STATUSES = listOf("PENDING_APPROVAL", "CLAIMED", "PENDING", "PENDING_REVIEW", "PROVISIONAL")
    }
}

@Dao
abstract class InboxDao {
    @Query("SELECT sync_revision FROM inbox_record WHERE kind = :kind AND id = :id")
    protected abstract suspend fun revision(kind: String, id: String): Long?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    protected abstract suspend fun put(record: InboxRecordEntity)

    /** Upsert by (kind, id, sync_revision): an older (lookback replay) revision never overwrites a newer one. */
    @Transaction
    open suspend fun upsert(records: List<InboxRecordEntity>): Int = records.count { r ->
        val current = revision(r.kind, r.id)
        (current == null || r.syncRevision >= current).also { if (it) put(r) }
    }

    @Query("DELETE FROM inbox_record WHERE tenant_id = :tenantId")
    abstract suspend fun deleteTenant(tenantId: String): Int

    /** Drops records older than [before] that no longer wait for the office (the server window is 30 days). */
    @Query("DELETE FROM inbox_record WHERE tenant_id = :tenantId AND occurred_at < :before AND (status IS NULL OR status NOT IN (:open))")
    abstract suspend fun prune(tenantId: String, before: Long, open: List<String>): Int

    @Query("SELECT * FROM inbox_record WHERE tenant_id = :tenantId AND kind = :kind ORDER BY occurred_at DESC, id")
    abstract fun observeKind(tenantId: String, kind: String): Flow<List<InboxRecordEntity>>

    @Query("SELECT * FROM inbox_record WHERE tenant_id = :tenantId ORDER BY occurred_at DESC, id")
    abstract fun observeAll(tenantId: String): Flow<List<InboxRecordEntity>>

    @Query("SELECT * FROM inbox_record WHERE tenant_id = :tenantId AND kind = :kind")
    abstract suspend fun kind(tenantId: String, kind: String): List<InboxRecordEntity>

    @Query("SELECT COUNT(*) FROM inbox_record WHERE tenant_id = :tenantId")
    abstract suspend fun count(tenantId: String): Int
}
