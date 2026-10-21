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
    ],
)
data class ClientOperationEntity(
    @PrimaryKey @ColumnInfo(name = "id") val id: String,
    @ColumnInfo(name = "tenant_id") val tenantId: String,
    @ColumnInfo(name = "op_type") val opType: String,
    @ColumnInfo(name = "entity_type") val entityType: String,
    @ColumnInfo(name = "entity_id") val entityId: String,
    @ColumnInfo(name = "payload_json") val payloadJson: String,
    /** Id of the operation that must be ACKED before this one may be dispatched (dependency ordering). */
    @ColumnInfo(name = "depends_on") val dependsOn: String?,
    /** UTC epoch milliseconds of local capture; the server records its own receive time separately. */
    @ColumnInfo(name = "created_at_device") val createdAtDevice: Long,
    @ColumnInfo(name = "status") val status: ClientOperationStatus,
    @ColumnInfo(name = "attempt_count") val attemptCount: Int,
    @ColumnInfo(name = "last_error") val lastError: String?,
    @ColumnInfo(name = "server_revision") val serverRevision: Long?,
)
