package com.asseta.core.database

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Transaction
import com.asseta.core.model.ClientOperationStatus
import kotlinx.coroutines.flow.Flow

data class StatusCount(val status: ClientOperationStatus, val count: Int)

/**
 * Outbox persistence. Status changes are guarded in SQL so the state machine (domain `OutboxTransitions`) cannot be
 * bypassed: outcomes only apply to SENT rows, and nothing becomes ACKED without a server acknowledgement.
 */
@Dao
abstract class ClientOperationDao {

    /** Enqueue; an existing id is kept untouched (idempotent enqueue). Returns -1 when ignored. */
    @Insert(onConflict = OnConflictStrategy.IGNORE)
    abstract suspend fun enqueue(operation: ClientOperationEntity): Long

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    protected abstract suspend fun insertDependencies(edges: List<ClientOperationDependencyEntity>)

    /** Enqueue with v2 multi-parent dependencies, atomically. */
    @Transaction
    open suspend fun enqueueWithDependencies(operation: ClientOperationEntity, dependsOn: List<String>): Long {
        val row = enqueue(operation)
        if (row != -1L) insertDependencies(dependsOn.distinct().map { ClientOperationDependencyEntity(operation.id, it) })
        return row
    }

    @Query("SELECT * FROM client_operation WHERE id = :id")
    abstract suspend fun findById(id: String): ClientOperationEntity?

    @Query("SELECT depends_on_id FROM client_operation_dependency WHERE operation_id = :id ORDER BY depends_on_id")
    abstract suspend fun dependenciesOf(id: String): List<String>

    /**
     * Operations ready to send for a tenant, oldest first: PENDING or QUARANTINED (resent until applied), every
     * dependency (legacy column and dependency table) durably ACKED, and any evidence attachment uploaded.
     * REJECTED (FAILED) and CONFLICT rows are never resent automatically. Bounded batch size.
     */
    @Query(
        """
        SELECT op.* FROM client_operation op
        WHERE op.tenant_id = :tenantId
          AND op.status IN ('PENDING', 'QUARANTINED')
          AND (op.depends_on IS NULL OR EXISTS (
                SELECT 1 FROM client_operation dep WHERE dep.id = op.depends_on AND dep.status = 'ACKED'))
          AND NOT EXISTS (
                SELECT 1 FROM client_operation_dependency d
                LEFT JOIN client_operation p ON p.id = d.depends_on_id
                WHERE d.operation_id = op.id AND (p.status IS NULL OR p.status != 'ACKED'))
          AND (op.attachment_local_id IS NULL OR EXISTS (
                SELECT 1 FROM attachment a WHERE a.id = op.attachment_local_id AND a.status = 'COMPLETE'
                  AND a.server_attachment_id IS NOT NULL))
        ORDER BY op.created_at_device ASC, op.id ASC
        LIMIT :limit
        """,
    )
    abstract suspend fun dispatchable(tenantId: String, limit: Int): List<ClientOperationEntity>

    @Query(
        """UPDATE client_operation SET status = 'SENT', attempt_count = attempt_count + 1, last_attempt_at = :now
           WHERE id = :id AND status IN ('PENDING', 'QUARANTINED')""",
    )
    abstract suspend fun markSent(id: String, now: Long = System.currentTimeMillis()): Int

    /** Only a SENT operation can be acknowledged; ACK carries the server's monotonic revision. */
    @Query("UPDATE client_operation SET status = 'ACKED', server_revision = :serverRevision, last_error = NULL WHERE id = :id AND status = 'SENT'")
    abstract suspend fun markAcked(id: String, serverRevision: Long): Int

    /** ACK/DUPLICATE: store the server result. [serverRevision] is null when the server result carries none. */
    @Query(
        """UPDATE client_operation SET status = 'ACKED', server_revision = :serverRevision, result_json = :resultJson,
           last_error = NULL, error_code = NULL WHERE id = :id AND status = 'SENT'""",
    )
    abstract suspend fun ackWithResult(id: String, resultJson: String, serverRevision: Long?): Int

    /** DEFERRED or transport failure: back to PENDING (kept, resent later); never counted as synced. */
    @Query("UPDATE client_operation SET status = 'PENDING', error_code = :code, last_error = :error WHERE id = :id AND status = 'SENT'")
    abstract suspend fun returnToPending(id: String, code: String?, error: String?): Int

    @Query("UPDATE client_operation SET status = 'FAILED', last_error = :error WHERE id = :id AND status = 'SENT'")
    abstract suspend fun markFailed(id: String, error: String): Int

    /** REJECTED: terminal until the user acts; error code visible. */
    @Query(
        """UPDATE client_operation SET status = 'FAILED', error_code = :code, last_error = :error, result_json = :resultJson
           WHERE id = :id AND status = 'SENT'""",
    )
    abstract suspend fun markRejected(id: String, code: String?, error: String?, resultJson: String?): Int

    /** CONFLICT: kept with the server state for the user; never auto-overwritten or resent. */
    @Query(
        """UPDATE client_operation SET status = 'CONFLICT', error_code = :code, last_error = :error, result_json = :resultJson
           WHERE id = :id AND status = 'SENT'""",
    )
    abstract suspend fun markConflict(id: String, code: String?, error: String?, resultJson: String?): Int

    /** Server QUARANTINED (read-only subscription): stored server-side, held locally and resent later. */
    @Query(
        """UPDATE client_operation SET status = 'QUARANTINED', error_code = :code, last_error = :error, result_json = :resultJson
           WHERE id = :id AND status = 'SENT'""",
    )
    abstract suspend fun markQuarantined(id: String, code: String?, error: String?, resultJson: String?): Int

    /** Non-retryable (e.g. structured conflict/validation); kept visible for review, never deleted. */
    @Query("UPDATE client_operation SET status = 'QUARANTINED', last_error = :error WHERE id = :id AND status != 'ACKED'")
    abstract suspend fun quarantine(id: String, error: String): Int

    /**
     * User "Retry" on a rejected operation: back to PENDING with the same id and payload (the server replays its stored
     * outcome for a known id, so this only helps when the cause was on the device). Never touches other states.
     */
    @Query("UPDATE client_operation SET status = 'PENDING' WHERE id = :id AND status = 'FAILED'")
    abstract suspend fun requeueFailed(id: String): Int

    /** After process death an in-flight batch has no known outcome; resend it (idempotent by operation id). */
    @Query("UPDATE client_operation SET status = 'PENDING' WHERE status = 'SENT'")
    abstract suspend fun recoverInFlight(): Int

    /** Patches a payload only while the op has never been sent (the server hashes payloads for idempotency). */
    @Query("UPDATE client_operation SET payload_json = :payloadJson WHERE id = :id AND attempt_count = 0 AND status = 'PENDING'")
    abstract suspend fun patchUnsentPayload(id: String, payloadJson: String): Int

    /** The operation that recorded a device-generated business id (exactly-once enqueue per form visit). */
    @Query("SELECT * FROM client_operation WHERE tenant_id = :tenantId AND entity_type = :entityType AND entity_id = :entityId LIMIT 1")
    abstract suspend fun findByEntity(tenantId: String, entityType: String, entityId: String): ClientOperationEntity?

    /** All operations of the given types (any status), newest first: the field-finance records of this device. */
    @Query("SELECT * FROM client_operation WHERE tenant_id = :tenantId AND op_type IN (:opTypes) ORDER BY created_at_device DESC")
    abstract fun observeByOpTypes(tenantId: String, opTypes: List<String>): Flow<List<ClientOperationEntity>>

    @Query("SELECT * FROM client_operation WHERE attachment_local_id = :attachmentId")
    abstract suspend fun forAttachment(attachmentId: String): List<ClientOperationEntity>

    @Query("SELECT * FROM client_operation WHERE tenant_id = :tenantId AND job_id = :jobId ORDER BY created_at_device ASC")
    abstract suspend fun forJob(tenantId: String, jobId: String): List<ClientOperationEntity>

    @Query("SELECT * FROM client_operation WHERE tenant_id = :tenantId AND job_id = :jobId ORDER BY created_at_device ASC")
    abstract fun observeForJob(tenantId: String, jobId: String): Flow<List<ClientOperationEntity>>

    @Query("SELECT status, COUNT(*) AS count FROM client_operation WHERE tenant_id = :tenantId GROUP BY status")
    abstract fun observeStatusCounts(tenantId: String): Flow<List<StatusCount>>

    @Query(
        """SELECT * FROM client_operation WHERE tenant_id = :tenantId AND status IN ('FAILED', 'QUARANTINED', 'CONFLICT')
           ORDER BY created_at_device ASC""",
    )
    abstract fun observeProblems(tenantId: String): Flow<List<ClientOperationEntity>>

    /** Everything not yet durably acknowledged (pending, in flight, failed, conflict, quarantined). */
    @Query("SELECT * FROM client_operation WHERE tenant_id = :tenantId AND status != 'ACKED' ORDER BY created_at_device ASC")
    abstract fun observeUnsynced(tenantId: String): Flow<List<ClientOperationEntity>>
}
