package com.asseta.core.sync.usecase

import com.asseta.core.database.AssetaDatabase
import com.asseta.core.database.AttachmentEntity
import com.asseta.core.database.inTransaction
import com.asseta.core.domain.inbox.ResetRules
import com.asseta.core.model.sync.BlobPurpose
import com.asseta.core.model.sync.MeterResetPayload
import com.asseta.core.model.sync.OpTypes
import com.asseta.core.model.sync.SyncCapabilities
import com.asseta.core.sync.data.FieldRepository
import com.asseta.core.sync.data.FieldOutbox
import com.asseta.core.sync.data.IsoTime
import com.asseta.core.sync.evidence.EvidenceFiles
import com.asseta.core.sync.evidence.Sha256
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import java.util.UUID

/** One meter reset request from the reset form. [clientId] is generated once per form visit (exactly once). */
data class MeterResetRequest(
    val tenantId: String,
    val clientId: String,
    val machineId: String,
    val oldReading: String,
    val newReading: String,
    val reason: String,
    /** Original evidence JPEG from the camera (encrypted at rest, never re-encoded). */
    val photoJpeg: ByteArray?,
    val effectiveAtMs: Long,
)

/**
 * Offline meter reset request (`METER_RESET_REQUEST`, server capability OP_METER_RESET_REQUEST): validated with
 * [ResetRules], the evidence photo stored encrypted (purpose RESET_EVIDENCE) and the operation queued atomically; it
 * waits for the photo upload and is then sent with the completed upload id. The office approves or rejects it; the
 * decision comes back in the inbox (`my_meter_resets`).
 */
class RequestMeterReset(
    private val db: () -> AssetaDatabase,
    private val field: FieldRepository,
    private val outbox: FieldOutbox,
    private val files: EvidenceFiles,
    private val json: Json,
    private val onQueued: () -> Unit = {},
) {
    /** Null when reset requests can be recorded, else why not. */
    suspend fun unavailable(tenantId: String): String? {
        val state = db().syncStateDao().get(tenantId)
        return when {
            state?.capabilities == null -> "Sync once while online before requesting a meter reset."
            !state.supports(SyncCapabilities.OP_METER_RESET_REQUEST) -> "Your company's server does not accept meter reset requests yet."
            else -> null
        }
    }

    suspend operator fun invoke(r: MeterResetRequest): FinanceResult {
        unavailable(r.tenantId)?.let { return FinanceResult.Blocked(it) }
        field.machine(r.machineId) ?: return FinanceResult.Blocked("This machine is not on this device.")
        val issues = ResetRules.validate(r.oldReading, r.newReading, r.reason, r.photoJpeg?.isNotEmpty() == true)
        if (issues.isNotEmpty()) return FinanceResult.Invalid(issues)
        val database = db()
        if (database.clientOperationDao().findByEntity(r.tenantId, ENTITY, r.clientId) != null) return FinanceResult.AlreadySaved
        val bytes = r.photoJpeg!!
        val fileName = files.write(bytes)
        val attachmentId = UUID.randomUUID().toString()
        val payload = MeterResetPayload(
            machineId = r.machineId,
            oldReading = ResetRules.parse(r.oldReading)!!,
            newReading = ResetRules.parse(r.newReading)!!,
            effectiveAt = IsoTime.format(r.effectiveAtMs),
            reason = r.reason.trim(),
        )
        return database.inTransaction {
            if (database.clientOperationDao().findByEntity(r.tenantId, ENTITY, r.clientId) != null) {
                files.delete(fileName)
                return@inTransaction FinanceResult.AlreadySaved
            }
            database.evidenceDao().insertAttachment(
                AttachmentEntity(attachmentId, r.tenantId, BlobPurpose.RESET_EVIDENCE, fileName, Sha256.hex(bytes), bytes.size.toLong(),
                    "image/jpeg", AttachmentEntity.PENDING, createdAt = r.effectiveAtMs),
            )
            val opId = outbox.enqueueOperation(
                r.tenantId, OpTypes.METER_RESET_REQUEST, ENTITY, r.clientId,
                json.encodeToJsonElement(MeterResetPayload.serializer(), payload).jsonObject, listOf(attachmentId),
            )
            FinanceResult.Saved(r.clientId, opId)
        }.also { if (it is FinanceResult.Saved) onQueued() }
    }

    companion object {
        const val ENTITY = "meter_reset"
    }
}
