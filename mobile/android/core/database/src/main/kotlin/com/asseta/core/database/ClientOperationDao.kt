package com.asseta.core.database

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.asseta.core.model.ClientOperationStatus
import kotlinx.coroutines.flow.Flow

data class StatusCount(val status: ClientOperationStatus, val count: Int)

@Dao
interface ClientOperationDao {

    /** Enqueue; an existing id is kept untouched (idempotent enqueue). Returns -1 when ignored. */
    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun enqueue(operation: ClientOperationEntity): Long

    @Query("SELECT * FROM client_operation WHERE id = :id")
    suspend fun findById(id: String): ClientOperationEntity?

    /**
     * Operations ready to send for a tenant, oldest first: PENDING or FAILED, and whose dependency
     * (if any) has been durably ACKED by the server. Bounded batch size.
     */
    @Query(
        """
        SELECT op.* FROM client_operation op
        WHERE op.tenant_id = :tenantId
          AND op.status IN ('PENDING', 'FAILED')
          AND (op.depends_on IS NULL OR EXISTS (
                SELECT 1 FROM client_operation dep WHERE dep.id = op.depends_on AND dep.status = 'ACKED'))
        ORDER BY op.created_at_device ASC, op.id ASC
        LIMIT :limit
        """,
    )
    suspend fun dispatchable(tenantId: String, limit: Int): List<ClientOperationEntity>

    @Query("UPDATE client_operation SET status = 'SENT', attempt_count = attempt_count + 1 WHERE id = :id AND status IN ('PENDING', 'FAILED')")
    suspend fun markSent(id: String): Int

    /** Only a SENT operation can be acknowledged; ACK carries the server's monotonic revision. */
    @Query("UPDATE client_operation SET status = 'ACKED', server_revision = :serverRevision, last_error = NULL WHERE id = :id AND status = 'SENT'")
    suspend fun markAcked(id: String, serverRevision: Long): Int

    @Query("UPDATE client_operation SET status = 'FAILED', last_error = :error WHERE id = :id AND status = 'SENT'")
    suspend fun markFailed(id: String, error: String): Int

    /** Non-retryable (e.g. structured conflict/validation); kept visible for review, never deleted. */
    @Query("UPDATE client_operation SET status = 'QUARANTINED', last_error = :error WHERE id = :id AND status != 'ACKED'")
    suspend fun quarantine(id: String, error: String): Int

    @Query("SELECT status, COUNT(*) AS count FROM client_operation WHERE tenant_id = :tenantId GROUP BY status")
    fun observeStatusCounts(tenantId: String): Flow<List<StatusCount>>

    @Query("SELECT * FROM client_operation WHERE tenant_id = :tenantId AND status IN ('FAILED', 'QUARANTINED') ORDER BY created_at_device ASC")
    fun observeProblems(tenantId: String): Flow<List<ClientOperationEntity>>
}
