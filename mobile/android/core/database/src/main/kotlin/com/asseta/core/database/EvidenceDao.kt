package com.asseta.core.database

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import kotlinx.coroutines.flow.Flow

/** Device-owned evidence: attachments queued for upload, captures and work-log entries. */
@Dao
interface EvidenceDao {
    @Insert(onConflict = OnConflictStrategy.ABORT)
    suspend fun insertAttachment(attachment: AttachmentEntity)

    @Query("SELECT * FROM attachment WHERE id = :id")
    suspend fun attachment(id: String): AttachmentEntity?

    @Query("SELECT * FROM attachment WHERE tenant_id = :tenantId AND status != 'COMPLETE' ORDER BY created_at ASC LIMIT :limit")
    suspend fun pendingAttachments(tenantId: String, limit: Int): List<AttachmentEntity>

    /** Starts (or, with nulls, resets) the upload session used to resume chunk uploads. */
    @Query(
        """UPDATE attachment SET session_id = :sessionId, chunk_size = :chunkSize, received_chunks = :received,
           attempt_count = attempt_count + 1 WHERE id = :id AND status != 'COMPLETE'""",
    )
    suspend fun setSession(id: String, sessionId: String?, chunkSize: Int?, received: String?): Int

    @Query("UPDATE attachment SET received_chunks = :received WHERE id = :id AND session_id = :sessionId")
    suspend fun setReceivedChunks(id: String, sessionId: String, received: String): Int

    @Query("UPDATE attachment SET status = 'COMPLETE', server_attachment_id = :serverId, last_error = NULL WHERE id = :id")
    suspend fun markAttachmentComplete(id: String, serverId: String): Int

    @Query("UPDATE attachment SET last_error = :error WHERE id = :id")
    suspend fun recordAttachmentError(id: String, error: String?): Int

    @Query("SELECT COUNT(*) FROM attachment WHERE tenant_id = :tenantId AND status != 'COMPLETE'")
    fun observePendingAttachmentCount(tenantId: String): Flow<Int>

    @Insert(onConflict = OnConflictStrategy.ABORT)
    suspend fun insertCapture(capture: MeterCaptureEntity)

    @Query("SELECT * FROM meter_capture WHERE job_id = :jobId ORDER BY captured_at ASC")
    fun observeCaptures(jobId: String): Flow<List<MeterCaptureEntity>>

    @Insert(onConflict = OnConflictStrategy.ABORT)
    suspend fun insertWorkLog(entry: WorkLogEntryEntity)

    @Query("SELECT * FROM work_log_entry WHERE client_id = :clientId")
    suspend fun workLog(clientId: String): WorkLogEntryEntity?

    /** Closes an open entry exactly once (the activity op is queued in the same transaction by the caller). */
    @Query("UPDATE work_log_entry SET ended_at = :endedAt, operation_id = :operationId WHERE client_id = :clientId AND operation_id IS NULL")
    suspend fun closeWorkLog(clientId: String, endedAt: Long?, operationId: String): Int

    @Query("SELECT * FROM work_log_entry WHERE job_id = :jobId ORDER BY started_at ASC")
    fun observeWorkLog(jobId: String): Flow<List<WorkLogEntryEntity>>
}
