package com.asseta.core.database

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

/**
 * Evidence file (meter photo / signature PNG) queued for resumable upload. The bytes live encrypted in app-private
 * storage ([fileName]); [sha256] is of the original, unmodified bytes. [serverAttachmentId] is set on COMPLETE;
 * [status] FAILED is permanent and keeps [lastError] for the sync status screen.
 */
@Entity(tableName = "attachment", indices = [Index(value = ["tenant_id", "status"])])
data class AttachmentEntity(
    @PrimaryKey @ColumnInfo(name = "id") val id: String,
    @ColumnInfo(name = "tenant_id") val tenantId: String,
    @ColumnInfo(name = "purpose") val purpose: String,
    @ColumnInfo(name = "file_name") val fileName: String,
    @ColumnInfo(name = "sha256") val sha256: String,
    @ColumnInfo(name = "size_bytes") val sizeBytes: Long,
    @ColumnInfo(name = "content_type") val contentType: String,
    @ColumnInfo(name = "status") val status: String,
    @ColumnInfo(name = "session_id") val sessionId: String? = null,
    /** Server chunk size of [sessionId] and the chunk indexes the server confirmed (comma separated), for resume. */
    @ColumnInfo(name = "chunk_size") val chunkSize: Int? = null,
    @ColumnInfo(name = "received_chunks") val receivedChunks: String? = null,
    @ColumnInfo(name = "server_attachment_id") val serverAttachmentId: String? = null,
    @ColumnInfo(name = "attempt_count") val attemptCount: Int = 0,
    @ColumnInfo(name = "last_error") val lastError: String? = null,
    @ColumnInfo(name = "created_at") val createdAt: Long,
    /** A PENDING upload is not tried again before this time (set after the server refused it). */
    @ColumnInfo(name = "next_attempt_at") val nextAttemptAt: Long? = null,
    /** v6: the user who captured this file; it is uploaded only under that user's token. */
    @ColumnInfo(name = "owner_sub") val ownerSub: String? = null,
) {
    companion object {
        const val PENDING = "PENDING"
        const val COMPLETE = "COMPLETE"

        /** Permanent: the evidence can never be uploaded (file missing or changed, unknown purpose, too large). */
        const val FAILED = "FAILED"
    }
}

/** Local copy of a meter capture (the original evidence the device owns), linked to its outbox operation. */
@Entity(tableName = "meter_capture", indices = [Index(value = ["job_id"])])
data class MeterCaptureEntity(
    @PrimaryKey @ColumnInfo(name = "id") val id: String,
    @ColumnInfo(name = "tenant_id") val tenantId: String,
    @ColumnInfo(name = "job_id") val jobId: String,
    @ColumnInfo(name = "kind") val kind: String,
    @ColumnInfo(name = "capture_mode") val captureMode: String,
    @ColumnInfo(name = "reading") val reading: String,
    @ColumnInfo(name = "ocr_value") val ocrValue: String?,
    @ColumnInfo(name = "ocr_raw_text") val ocrRawText: String?,
    @ColumnInfo(name = "ocr_confidence") val ocrConfidence: Double?,
    @ColumnInfo(name = "photo_attachment_local_id") val photoAttachmentLocalId: String?,
    @ColumnInfo(name = "gps_status") val gpsStatus: String,
    @ColumnInfo(name = "latitude") val latitude: Double?,
    @ColumnInfo(name = "longitude") val longitude: Double?,
    @ColumnInfo(name = "accuracy_m") val accuracyM: Double?,
    @ColumnInfo(name = "gps_captured_at") val gpsCapturedAt: Long?,
    @ColumnInfo(name = "gps_provider") val gpsProvider: String?,
    @ColumnInfo(name = "captured_at") val capturedAt: Long,
    @ColumnInfo(name = "policy_version_ids_json") val policyVersionIdsJson: String,
    @ColumnInfo(name = "operation_id") val operationId: String,
)

/** Supervisor work-log entry. Open entries (no end) are local until stopped; then one JOB_ACTIVITY op is queued. */
@Entity(tableName = "work_log_entry", indices = [Index(value = ["job_id"])])
data class WorkLogEntryEntity(
    @PrimaryKey @ColumnInfo(name = "client_id") val clientId: String,
    @ColumnInfo(name = "tenant_id") val tenantId: String,
    @ColumnInfo(name = "job_id") val jobId: String,
    @ColumnInfo(name = "activity_type") val activityType: String,
    @ColumnInfo(name = "started_at") val startedAt: Long,
    @ColumnInfo(name = "ended_at") val endedAt: Long?,
    @ColumnInfo(name = "note") val note: String?,
    @ColumnInfo(name = "operation_id") val operationId: String?,
    /** v6: the user who logged this entry (a running entry is only shown to, and stopped by, that user). */
    @ColumnInfo(name = "owner_sub") val ownerSub: String? = null,
)
