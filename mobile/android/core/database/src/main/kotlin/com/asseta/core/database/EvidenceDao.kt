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

    /** Every PENDING upload (any retry time), oldest first. */
    @Query("SELECT * FROM attachment WHERE tenant_id = :tenantId AND status = 'PENDING' ORDER BY created_at ASC, id ASC LIMIT :limit")
    suspend fun pendingAttachments(tenantId: String, limit: Int): List<AttachmentEntity>

    /** [ownerSub]'s PENDING uploads whose retry time has come, oldest first (only uploaded under their owner's token). */
    @Query(
        """SELECT * FROM attachment WHERE tenant_id = :tenantId AND owner_sub = :ownerSub AND status = 'PENDING'
           AND (next_attempt_at IS NULL OR next_attempt_at <= :now) ORDER BY created_at ASC, id ASC LIMIT :limit""",
    )
    suspend fun uploadableAttachments(tenantId: String, ownerSub: String, now: Long, limit: Int): List<AttachmentEntity>

    /** Records who captured these files (set together with the operation that waits for them). */
    @Query("UPDATE attachment SET owner_sub = :ownerSub WHERE id IN (:ids)")
    suspend fun assignOwner(ids: List<String>, ownerSub: String): Int

    /** Starts (or, with nulls, resets) the upload session used to resume chunk uploads. */
    @Query(
        """UPDATE attachment SET session_id = :sessionId, chunk_size = :chunkSize, received_chunks = :received,
           attempt_count = attempt_count + 1 WHERE id = :id AND status = 'PENDING'""",
    )
    suspend fun setSession(id: String, sessionId: String?, chunkSize: Int?, received: String?): Int

    @Query("UPDATE attachment SET received_chunks = :received WHERE id = :id AND session_id = :sessionId")
    suspend fun setReceivedChunks(id: String, sessionId: String, received: String): Int

    @Query(
        """UPDATE attachment SET status = 'COMPLETE', server_attachment_id = :serverId, last_error = NULL,
           next_attempt_at = NULL WHERE id = :id""",
    )
    suspend fun markAttachmentComplete(id: String, serverId: String): Int

    @Query("UPDATE attachment SET last_error = :error WHERE id = :id")
    suspend fun recordAttachmentError(id: String, error: String?): Int

    /** A failed attempt: the upload stays PENDING and is tried again at [retryAt] (null: on the next sync). */
    @Query(
        """UPDATE attachment SET attempt_count = attempt_count + 1, last_error = :error, next_attempt_at = :retryAt
           WHERE id = :id AND status = 'PENDING'""",
    )
    suspend fun recordAttemptFailure(id: String, error: String, retryAt: Long?): Int

    /** Permanent failure (the local evidence is missing or changed, or the server can never accept it). */
    @Query("UPDATE attachment SET status = 'FAILED', last_error = :error WHERE id = :id AND status = 'PENDING'")
    suspend fun markAttachmentFailed(id: String, error: String): Int

    @Query("SELECT COUNT(*) FROM attachment WHERE tenant_id = :tenantId AND owner_sub = :ownerSub AND status = 'PENDING'")
    fun observePendingAttachmentCount(tenantId: String, ownerSub: String): Flow<Int>

    /** [ownerSub]'s evidence files that can never be uploaded, oldest first (shown on the sync status screen). */
    @Query(
        """SELECT * FROM attachment WHERE tenant_id = :tenantId AND owner_sub = :ownerSub AND status = 'FAILED'
           ORDER BY created_at ASC, id ASC""",
    )
    fun observeFailedAttachments(tenantId: String, ownerSub: String): Flow<List<AttachmentEntity>>

    @Insert(onConflict = OnConflictStrategy.ABORT)
    suspend fun insertCapture(capture: MeterCaptureEntity)

    /** [ownerSub]'s captures of a job (through the operation that recorded each one). */
    @Query(
        """SELECT * FROM meter_capture WHERE job_id = :jobId
           AND operation_id IN (SELECT id FROM client_operation WHERE owner_sub = :ownerSub) ORDER BY captured_at ASC""",
    )
    fun observeCaptures(jobId: String, ownerSub: String): Flow<List<MeterCaptureEntity>>

    @Insert(onConflict = OnConflictStrategy.ABORT)
    suspend fun insertWorkLog(entry: WorkLogEntryEntity)

    @Query("SELECT * FROM work_log_entry WHERE client_id = :clientId")
    suspend fun workLog(clientId: String): WorkLogEntryEntity?

    /** Closes an open entry exactly once (the activity op is queued in the same transaction by the caller). */
    @Query("UPDATE work_log_entry SET ended_at = :endedAt, operation_id = :operationId WHERE client_id = :clientId AND operation_id IS NULL")
    suspend fun closeWorkLog(clientId: String, endedAt: Long?, operationId: String): Int

    @Query("SELECT * FROM work_log_entry WHERE job_id = :jobId AND owner_sub = :ownerSub ORDER BY started_at ASC")
    fun observeWorkLog(jobId: String, ownerSub: String): Flow<List<WorkLogEntryEntity>>

    /** [ownerSub]'s captures in the tenant (every job), newest first: the Readings tab. */
    @Query(
        """SELECT * FROM meter_capture WHERE tenant_id = :tenantId
           AND operation_id IN (SELECT id FROM client_operation WHERE owner_sub = :ownerSub) ORDER BY captured_at DESC""",
    )
    fun observeAllCaptures(tenantId: String, ownerSub: String): Flow<List<MeterCaptureEntity>>

    /** [ownerSub]'s work-log entries in the tenant (every job). */
    @Query("SELECT * FROM work_log_entry WHERE tenant_id = :tenantId AND owner_sub = :ownerSub ORDER BY started_at ASC")
    fun observeAllWorkLog(tenantId: String, ownerSub: String): Flow<List<WorkLogEntryEntity>>
}
