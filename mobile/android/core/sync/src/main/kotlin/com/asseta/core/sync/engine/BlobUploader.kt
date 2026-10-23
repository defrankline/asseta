package com.asseta.core.sync.engine

import com.asseta.core.database.AssetaDatabase
import com.asseta.core.database.AttachmentEntity
import com.asseta.core.database.inTransaction
import com.asseta.core.model.sync.BlobPurpose
import com.asseta.core.model.sync.BlobSessionDto
import com.asseta.core.model.sync.BlobStartIn
import com.asseta.core.model.sync.OpTypes
import com.asseta.core.model.sync.SyncErrorCodes
import com.asseta.core.network.ApiException
import com.asseta.core.network.SyncApi
import com.asseta.core.sync.evidence.EvidenceFiles
import com.asseta.core.sync.evidence.Sha256
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.FileNotFoundException
import java.io.IOException
import javax.crypto.AEADBadTagException

/**
 * Resumable, checksum-verified evidence upload (`POST /sync/blobs` -> `PUT chunks` -> `POST complete`).
 * The session id, chunk size and server-confirmed chunks are persisted after every chunk, so an interrupted upload
 * resumes with only the missing indexes. CHECKSUM_MISMATCH (server discarded the chunks) or an expired/unknown session
 * restarts from a new session. Known content completes immediately (server dedupe).
 *
 * On completion the server attachment id (or, for an expense receipt, the completed upload id, appended to the
 * operation's `receipt_upload_ids`) is written into the waiting operations' payloads in the same transaction; an
 * operation becomes dispatchable only once every file it waits for is complete (a capture is never sent before its
 * photo has an attachment id; an expense never before all of its receipt uploads completed).
 *
 * Failure rules (as on iOS): evidence that is missing, unreadable or changed on the device, an unknown purpose and a
 * server FILE_TOO_LARGE mark the file FAILED for good (shown on the sync screen, never retried); any other
 * non-retryable server refusal is recorded and that file alone is retried after [retryRefusedAfterMs] while the other
 * files continue. Transport/5xx/401 and device errors propagate (the whole sync backs off).
 */
class BlobUploader(
    private val api: SyncApi,
    private val db: () -> AssetaDatabase,
    private val files: EvidenceFiles,
    private val json: Json,
    private val nowMs: () -> Long = System::currentTimeMillis,
    private val retryRefusedAfterMs: Long = 30 * 60_000,
) {
    /**
     * Uploads [ownerSub]'s attachments that are due (never another user's evidence under this token); returns how many
     * completed. Transport/5xx errors propagate (retry later).
     */
    suspend fun uploadPending(tenantId: String, ownerSub: String, limit: Int = 20): Int {
        val evidence = db().evidenceDao()
        var done = 0
        for (attachment in evidence.uploadableAttachments(tenantId, ownerSub, nowMs(), limit)) {
            try {
                if (upload(tenantId, attachment)) done++
            } catch (e: ApiException) {
                if (propagates(e)) {
                    evidence.recordAttemptFailure(attachment.id, "${e.code}: ${e.message}", null)
                    throw e
                }
                // A permanent server refusal for this file: record it and move on to the others.
                evidence.recordAttemptFailure(attachment.id, "${e.code}: ${e.message}", nowMs() + retryRefusedAfterMs)
            } catch (e: IOException) {
                evidence.recordAttemptFailure(attachment.id, e.message ?: e.javaClass.simpleName, null)
                throw e
            }
        }
        return done
    }

    private fun propagates(e: ApiException) = e.isRetryable || e.isUnauthenticated ||
        e.code == SyncErrorCodes.DEVICE_REVOKED || e.code == SyncErrorCodes.DEVICE_NOT_REGISTERED ||
        e.code == SyncErrorCodes.UPLOAD_INCOMPLETE

    private suspend fun upload(tenantId: String, attachment: AttachmentEntity): Boolean {
        val evidence = db().evidenceDao()
        val bytes = readVerified(attachment) ?: return false
        if (attachment.purpose !in KNOWN_PURPOSES) {
            evidence.markAttachmentFailed(attachment.id, UNKNOWN_PURPOSE)
            return false
        }
        var current = attachment
        repeat(MAX_RESTARTS + 1) {
            val result = try {
                attempt(tenantId, current, bytes)
            } catch (e: ApiException) {
                if (e.code != FILE_TOO_LARGE) throw e
                evidence.markAttachmentFailed(current.id, FILE_TOO_LARGE)
                return false
            }
            when (result) {
                is Attempt.Done -> return true
                is Attempt.Restart -> {
                    evidence.setSession(current.id, null, null, null)
                    evidence.recordAttachmentError(current.id, result.code)
                    current = evidence.attachment(current.id) ?: return false
                }
            }
        }
        return false
    }

    /** The original bytes, or null after marking the file FAILED when it is missing, unreadable or changed. */
    private suspend fun readVerified(attachment: AttachmentEntity): ByteArray? {
        val reason = try {
            val bytes = files.read(attachment.fileName)
            if (Sha256.hex(bytes) == attachment.sha256 && bytes.size.toLong() == attachment.sizeBytes) return bytes
            "file changed" // never upload altered evidence; keep it visible instead
        } catch (e: FileNotFoundException) {
            "file missing"
        } catch (e: AEADBadTagException) {
            "file unreadable" // authentication tag mismatch: the encrypted file was damaged or replaced
        } catch (e: IllegalStateException) {
            "file unreadable"
        }
        db().evidenceDao().markAttachmentFailed(attachment.id, "$LOCAL_EVIDENCE_UNAVAILABLE: $reason")
        return null
    }

    private sealed interface Attempt {
        data object Done : Attempt
        data class Restart(val code: String) : Attempt
    }

    private suspend fun attempt(tenantId: String, attachment: AttachmentEntity, bytes: ByteArray): Attempt {
        val evidence = db().evidenceDao()
        var sessionId = attachment.sessionId
        var chunkSize = attachment.chunkSize
        val received = attachment.receivedChunks.orEmpty().split(',').mapNotNull { it.toIntOrNull() }.toMutableSet()
        if (sessionId == null || chunkSize == null) {
            val started = api.startBlob(tenantId, BlobStartIn(attachment.sha256, attachment.sizeBytes, attachment.purpose))
            if (started.isComplete()) return complete(attachment, started)
            sessionId = started.id
            chunkSize = started.chunkSize
            received.clear()
            received += started.receivedChunks
            evidence.setSession(attachment.id, sessionId, chunkSize, received.encode())
        }
        val total = ((bytes.size + chunkSize - 1) / chunkSize).coerceAtLeast(1)
        try {
            for (index in 0 until total) {
                if (index in received) continue
                val from = index * chunkSize
                val chunk = bytes.copyOfRange(from, minOf(bytes.size, from + chunkSize))
                val dto = api.putChunk(tenantId, sessionId, index, chunk.toRequestBody(OCTET_STREAM))
                if (dto.isComplete()) return complete(attachment, dto)
                received += dto.receivedChunks
                received += index
                evidence.setReceivedChunks(attachment.id, sessionId, received.encode())
            }
            val done = api.completeBlob(tenantId, sessionId)
            return if (done.isComplete()) complete(attachment, done) else Attempt.Restart("UPLOAD_NOT_COMPLETE")
        } catch (e: ApiException) {
            return when {
                e.code == SyncErrorCodes.CHECKSUM_MISMATCH -> Attempt.Restart(e.code)
                e.code == SyncErrorCodes.UPLOAD_EXPIRED || e.httpStatus == 404 -> Attempt.Restart(e.code)
                e.code == SyncErrorCodes.UPLOAD_INCOMPLETE -> {
                    // Server is missing chunks we believed confirmed: forget local progress and resend (idempotent).
                    evidence.setReceivedChunks(attachment.id, sessionId, "")
                    throw e
                }
                else -> throw e
            }
        }
    }

    private suspend fun complete(attachment: AttachmentEntity, dto: BlobSessionDto): Attempt {
        val serverId = dto.attachmentId ?: return Attempt.Restart("COMPLETE_WITHOUT_ATTACHMENT")
        val database = db()
        database.inTransaction {
            database.evidenceDao().markAttachmentComplete(attachment.id, serverId)
            val ops = database.clientOperationDao()
            ops.forAttachment(attachment.id).forEach { op ->
                val patch: Pair<String, JsonElement> = when (op.opType) {
                    OpTypes.METER_CAPTURE -> "photo_attachment_id" to JsonPrimitive(serverId)
                    OpTypes.JOB_ACKNOWLEDGEMENT -> "signature_attachment_id" to JsonPrimitive(serverId)
                    // The sync EXPENSE op references receipts by blob upload id (resolved server-side to attachments);
                    // each completed receipt appends its id, so an expense with several receipts carries them all.
                    OpTypes.EXPENSE -> "receipt_upload_ids" to appendUploadId(op.payloadJson, dto.id)
                    else -> return@forEach
                }
                val payload = json.parseToJsonElement(op.payloadJson).jsonObject
                ops.patchUnsentPayload(op.id, json.encodeToString(JsonObject(payload + patch)))
            }
        }
        return Attempt.Done
    }

    private fun appendUploadId(payloadJson: String, uploadId: String): JsonElement {
        val existing = (json.parseToJsonElement(payloadJson).jsonObject["receipt_upload_ids"] as? JsonArray).orEmpty()
        return if (existing.any { it.jsonPrimitive.content == uploadId }) JsonArray(existing) else JsonArray(existing + JsonPrimitive(uploadId))
    }

    private fun BlobSessionDto.isComplete() = status == "COMPLETE" && attachmentId != null

    private fun Set<Int>.encode() = sorted().joinToString(",")

    private companion object {
        const val MAX_RESTARTS = 1
        const val FILE_TOO_LARGE = "FILE_TOO_LARGE"
        const val UNKNOWN_PURPOSE = "UNKNOWN_PURPOSE"
        const val LOCAL_EVIDENCE_UNAVAILABLE = "LOCAL_EVIDENCE_UNAVAILABLE"
        val KNOWN_PURPOSES = setOf(BlobPurpose.METER_PHOTO, BlobPurpose.SIGNATURE, BlobPurpose.EXPENSE_RECEIPT)
        val OCTET_STREAM = "application/octet-stream".toMediaType()
    }
}
