package com.asseta.core.database

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

/**
 * Evidence file (meter photo, receipt, payment evidence) queued for resumable upload. The bytes live encrypted in
 * app-private storage ([fileName]); [sha256] is of the original, unmodified bytes. [serverAttachmentId] is set on
 * COMPLETE; [status] FAILED is permanent and keeps [lastError] for the sync status screen.
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

