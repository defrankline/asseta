package com.asseta.core.database

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey
import com.asseta.core.model.ClientOperationStatus

/**
 * Durable offline outbox row. `id` is the device-generated operation UUID and doubles as the server
 * idempotency key, so retries can never duplicate a business record.
 */
@Entity(
    tableName = "client_operation",
    indices = [
        Index(value = ["tenant_id", "status", "created_at_device"]),
        Index(value = ["depends_on"]),
        Index(value = ["entity_type", "entity_id"]),
        Index(value = ["job_id"]),
        Index(value = ["attachment_local_id"]),
    ],
)
data class ClientOperationEntity(
    @PrimaryKey @ColumnInfo(name = "id") val id: String,
    @ColumnInfo(name = "tenant_id") val tenantId: String,
    @ColumnInfo(name = "op_type") val opType: String,
    @ColumnInfo(name = "entity_type") val entityType: String,
    @ColumnInfo(name = "entity_id") val entityId: String,
    @ColumnInfo(name = "payload_json") val payloadJson: String,
    /** Legacy single dependency (v1). v2 dependencies live in `client_operation_dependency`; both are honoured. */
    @ColumnInfo(name = "depends_on") val dependsOn: String?,
    /** UTC epoch milliseconds of local capture; the server records its own receive time separately. */
    @ColumnInfo(name = "created_at_device") val createdAtDevice: Long,
    @ColumnInfo(name = "status") val status: ClientOperationStatus,
    @ColumnInfo(name = "attempt_count") val attemptCount: Int,
    @ColumnInfo(name = "last_error") val lastError: String?,
    @ColumnInfo(name = "server_revision") val serverRevision: Long?,
    /** Job this field operation belongs to (UI grouping and dependency planning). */
    @ColumnInfo(name = "job_id") val jobId: String? = null,
    /** Server error code of the last outcome (REJECTED/CONFLICT/QUARANTINED/DEFERRED), shown to the user. */
    @ColumnInfo(name = "error_code") val errorCode: String? = null,
    /** Server per-op `result` (entity on ACK, `server_state` on CONFLICT); kept for audit and display. */
    @ColumnInfo(name = "result_json") val resultJson: String? = null,
    /** Local evidence attachment that must be uploaded (server attachment id known) before dispatch. */
    @ColumnInfo(name = "attachment_local_id") val attachmentLocalId: String? = null,
    @ColumnInfo(name = "last_attempt_at") val lastAttemptAt: Long? = null,
)

/** v2 multi-parent dependency edge: [operationId] may be dispatched only after [dependsOnId] is ACKED. */
@Entity(
    tableName = "client_operation_dependency",
    primaryKeys = ["operation_id", "depends_on_id"],
    indices = [Index(value = ["depends_on_id"])],
)
data class ClientOperationDependencyEntity(
    @ColumnInfo(name = "operation_id") val operationId: String,
    @ColumnInfo(name = "depends_on_id") val dependsOnId: String,
)
