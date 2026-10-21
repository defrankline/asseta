package com.asseta.core.sync.engine

import com.asseta.core.database.AssetaDatabase
import com.asseta.core.database.AttachmentEntity
import com.asseta.core.database.inTransaction
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
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody

/**
 * Resumable, checksum-verified evidence upload (`POST /sync/blobs` -> `PUT chunks` -> `POST complete`).
 * The session id, chunk size and server-confirmed chunks are persisted after every chunk, so an interrupted upload
 * resumes with only the missing indexes. CHECKSUM_MISMATCH (server discarded the chunks) or an expired/unknown session
 * restarts from a new session. Known content completes immediately (server dedupe).
 *
 * On completion the server attachment id (or, for an expense receipt, the completed upload id) is written into the
 * waiting operations' payloads in the same transaction, which is what makes those operations dispatchable (a capture
 * is never sent before its photo has an attachment id; an expense never before its receipt upload completed).
 */
class BlobUploader(
    private val api: SyncApi,
    private val db: () -> AssetaDatabase,
    private val files: EvidenceFiles,
    private val json: Json,
) {
    /** Uploads pending attachments; returns how many completed. Transport/5xx errors propagate (retry later). */
    suspend fun uploadPending(tenantId: String, limit: Int = 20): Int =
        db().evidenceDao().pendingAttachments(tenantId, limit).count { upload(tenantId, it) }

    private suspend fun upload(tenantId: String, attachment: AttachmentEntity): Boolean {
        val bytes = files.read(attachment.fileName)
        if (Sha256.hex(bytes) != attachment.sha256 || bytes.size.toLong() != attachment.sizeBytes) {
            // Never upload altered evidence; keep it visible instead.
            db().evidenceDao().recordAttachmentError(attachment.id, "LOCAL_EVIDENCE_CORRUPT")
            return false
        }
        var current = attachment
        repeat(MAX_RESTARTS + 1) {
            when (val result = attempt(tenantId, current, bytes)) {
                is Attempt.Done -> return true
                is Attempt.Restart -> {
                    db().evidenceDao().setSession(current.id, null, null, null)
                    db().evidenceDao().recordAttachmentError(current.id, result.code)
                    current = db().evidenceDao().attachment(current.id) ?: return false
                }
            }
        }
        return false
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
                    // The sync EXPENSE op references receipts by blob upload id (resolved server-side to attachments).
                    OpTypes.EXPENSE -> "receipt_upload_ids" to JsonArray(listOf(JsonPrimitive(dto.id)))
                    else -> return@forEach
                }
                val payload = json.parseToJsonElement(op.payloadJson).jsonObject
                ops.patchUnsentPayload(op.id, json.encodeToString(JsonObject(payload + patch)))
            }
        }
        return Attempt.Done
    }

    private fun BlobSessionDto.isComplete() = status == "COMPLETE" && attachmentId != null

    private fun Set<Int>.encode() = sorted().joinToString(",")

    private companion object {
        const val MAX_RESTARTS = 1
        val OCTET_STREAM = "application/octet-stream".toMediaType()
    }
}
