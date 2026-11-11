package com.asseta.core.sync.usecase

import com.asseta.core.database.AssetaDatabase
import com.asseta.core.database.AttachmentEntity
import com.asseta.core.database.inTransaction
import com.asseta.core.domain.accountability.RemittanceMethod
import com.asseta.core.domain.finance.FormCheck
import com.asseta.core.domain.finance.PettyCashRules
import com.asseta.core.model.DecimalAmount
import com.asseta.core.model.sync.BlobPurpose
import com.asseta.core.model.sync.PettyCashAckPayload
import com.asseta.core.model.sync.PettyCashAdvanceClearPayload
import com.asseta.core.model.sync.PettyCashCountPayload
import com.asseta.core.model.sync.PettyCashHolderChangePayload
import com.asseta.core.model.sync.PettyCashOps
import com.asseta.core.model.sync.PettyCashReturnPayload
import com.asseta.core.model.sync.PettyCashTopUpPayload
import com.asseta.core.model.sync.SyncCapabilities
import com.asseta.core.sync.data.FieldOutbox
import com.asseta.core.sync.evidence.EvidenceFiles
import com.asseta.core.sync.evidence.Sha256
import kotlinx.serialization.KSerializer
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import java.math.BigDecimal
import java.util.UUID

/** Entity types of the petty cash operations in the outbox (one answer per movement / holder change / advance). */
object PettyCashEntities {
    const val ACK = "petty_cash_ack"
    const val TOP_UP = "petty_cash_top_up"
    const val RETURN = "petty_cash_return"
    const val COUNT = "petty_cash_count"
    const val HOLDER_CHANGE = "petty_cash_holder_change"
    const val ADVANCE = "petty_cash_advance_clear"
}

data class PettyCashTopUpRequest(val tenantId: String, val clientId: String, val fundId: String, val amountText: String, val note: String,
    val aboveReason: String, val headroom: BigDecimal?)

data class PettyCashReturnRequest(
    val tenantId: String,
    val clientId: String,
    val fundId: String,
    val amountText: String,
    val method: RemittanceMethod?,
    val depositAccountId: String?,
    val reference: String,
    val note: String,
    /** Original JPEGs of the slip or the cash (stored encrypted on save); at most ten. */
    val evidenceJpegs: List<ByteArray>,
    val evidenceRequired: Boolean,
    val createdAtMs: Long,
)

data class PettyCashCountRequest(
    val tenantId: String,
    val clientId: String,
    val fundId: String,
    val countedText: String,
    /** The witness's login id (`/tenant/people`), null when none was chosen. */
    val witnessUserId: String?,
    val note: String,
    val evidenceJpegs: List<ByteArray>,
    val createdAtMs: Long,
)

/**
 * Offline petty cash field operations (DEC-033, capability OP_PETTY_CASH): acknowledgements, top-up requests, returns,
 * counts, holder-change answers and advance clearances. Each is checked with the domain rules, then stored and queued
 * atomically as one outbox operation keyed by its entity (the answered record, or the form's client id sent as
 * `client_id`; the server dedupes too). Returns and counts with photos wait for every upload (PETTY_CASH_EVIDENCE).
 */
class PettyCashCapture(
    private val db: () -> AssetaDatabase,
    private val outbox: FieldOutbox,
    private val files: EvidenceFiles,
    private val json: Json,
    private val onQueued: () -> Unit = {},
) {
    private suspend fun unavailable(tenantId: String): String? {
        val state = db().syncStateDao().get(tenantId)
        return when {
            state?.capabilities == null -> CaptureMeterReading.NEEDS_SYNC
            !state.supports(SyncCapabilities.OP_PETTY_CASH) -> CaptureMeterReading.SERVER_TOO_OLD
            else -> null
        }
    }

    suspend fun acknowledge(tenantId: String, movementId: String, acknowledge: Boolean, receivedText: String, note: String): FinanceResult {
        unavailable(tenantId)?.let { return FinanceResult.Blocked(it) }
        val values = when (val c = PettyCashRules.acknowledgement(acknowledge, receivedText, note)) {
            is FormCheck.Invalid -> return FinanceResult.Invalid(c.messages)
            is FormCheck.Valid -> c.value
        }
        val payload = PettyCashAckPayload(movementId, acknowledge, values.amountReceived?.let(DecimalAmount::of), values.note)
        return queue(tenantId, PettyCashOps.ACKNOWLEDGEMENT, PettyCashEntities.ACK, movementId, PettyCashAckPayload.serializer(), payload)
    }

    suspend fun topUp(r: PettyCashTopUpRequest): FinanceResult {
        unavailable(r.tenantId)?.let { return FinanceResult.Blocked(it) }
        val values = when (val c = PettyCashRules.topUp(r.amountText, r.note, r.aboveReason, r.headroom)) {
            is FormCheck.Invalid -> return FinanceResult.Invalid(c.messages)
            is FormCheck.Valid -> c.value
        }
        val payload = PettyCashTopUpPayload(r.clientId, r.fundId, values.amount?.let(DecimalAmount::of), values.note, values.aboveCapReason)
        return queue(r.tenantId, PettyCashOps.TOP_UP_REQUEST, PettyCashEntities.TOP_UP, r.clientId, PettyCashTopUpPayload.serializer(), payload)
    }

    suspend fun returnFund(r: PettyCashReturnRequest): FinanceResult {
        unavailable(r.tenantId)?.let { return FinanceResult.Blocked(it) }
        val photos = r.evidenceJpegs.filter { it.isNotEmpty() }.take(PettyCashRules.MAX_PHOTOS)
        val values = when (val c = PettyCashRules.returnFund(r.amountText, r.reference, r.note, photos.size, r.evidenceRequired)) {
            is FormCheck.Invalid -> return FinanceResult.Invalid(c.messages)
            is FormCheck.Valid -> c.value
        }
        val payload = PettyCashReturnPayload(
            r.clientId, r.fundId, DecimalAmount.of(values.amount), r.depositAccountId, r.method?.wire, values.reference, values.note,
        )
        return withPhotos(r.tenantId, PettyCashOps.RETURN, PettyCashEntities.RETURN, r.clientId, PettyCashReturnPayload.serializer(), payload, photos, r.createdAtMs)
    }

    suspend fun count(r: PettyCashCountRequest): FinanceResult {
        unavailable(r.tenantId)?.let { return FinanceResult.Blocked(it) }
        val counted = when (val c = PettyCashRules.count(r.countedText)) {
            is FormCheck.Invalid -> return FinanceResult.Invalid(c.messages)
            is FormCheck.Valid -> c.value
        }
        val photos = r.evidenceJpegs.filter { it.isNotEmpty() }.take(PettyCashRules.MAX_PHOTOS)
        val payload = PettyCashCountPayload(r.clientId, r.fundId, DecimalAmount.of(counted), r.witnessUserId, PettyCashRules.note(r.note))
        return withPhotos(r.tenantId, PettyCashOps.COUNT, PettyCashEntities.COUNT, r.clientId, PettyCashCountPayload.serializer(), payload, photos, r.createdAtMs)
    }

    suspend fun holderChange(tenantId: String, holderChangeId: String, accept: Boolean, note: String): FinanceResult {
        unavailable(tenantId)?.let { return FinanceResult.Blocked(it) }
        val text = when (val c = PettyCashRules.holderDecision(accept, note)) {
            is FormCheck.Invalid -> return FinanceResult.Invalid(c.messages)
            is FormCheck.Valid -> c.value
        }
        return queue(tenantId, PettyCashOps.HOLDER_CHANGE_ACKNOWLEDGEMENT, PettyCashEntities.HOLDER_CHANGE, holderChangeId,
            PettyCashHolderChangePayload.serializer(), PettyCashHolderChangePayload(holderChangeId, accept, text))
    }

    suspend fun clearAdvance(tenantId: String, advanceId: String, changeText: String, note: String): FinanceResult {
        unavailable(tenantId)?.let { return FinanceResult.Blocked(it) }
        val change = when (val c = PettyCashRules.advanceClear(changeText)) {
            is FormCheck.Invalid -> return FinanceResult.Invalid(c.messages)
            is FormCheck.Valid -> c.value
        }
        return queue(tenantId, PettyCashOps.ADVANCE_CLEARANCE, PettyCashEntities.ADVANCE, advanceId,
            PettyCashAdvanceClearPayload.serializer(), PettyCashAdvanceClearPayload(advanceId, DecimalAmount.of(change), PettyCashRules.note(note)))
    }

    /** This phone already queued an answer for [entityId] (movement, holder change or advance). */
    suspend fun answered(tenantId: String, entityType: String, entityId: String): Boolean = alreadySaved(tenantId, entityType, entityId)

    private suspend fun alreadySaved(tenantId: String, entityType: String, entityId: String): Boolean =
        db().clientOperationDao().findByEntity(tenantId, entityType, entityId) != null

    private suspend fun <T> withPhotos(
        tenantId: String, opType: String, entityType: String, clientId: String, serializer: KSerializer<T>, payload: T,
        photos: List<ByteArray>, createdAtMs: Long,
    ): FinanceResult {
        if (photos.isEmpty()) return queue(tenantId, opType, entityType, clientId, serializer, payload)
        if (alreadySaved(tenantId, entityType, clientId)) return FinanceResult.AlreadySaved
        val stored = photos.map { bytes -> Triple(UUID.randomUUID().toString(), files.write(bytes), bytes) }
        val database = db()
        return database.inTransaction {
            if (alreadySaved(tenantId, entityType, clientId)) {
                stored.forEach { files.delete(it.second) }
                return@inTransaction FinanceResult.AlreadySaved
            }
            stored.forEach { (id, file, bytes) ->
                database.evidenceDao().insertAttachment(
                    AttachmentEntity(id, tenantId, BlobPurpose.PETTY_CASH_EVIDENCE, file, Sha256.hex(bytes), bytes.size.toLong(),
                        "image/jpeg", AttachmentEntity.PENDING, createdAt = createdAtMs),
                )
            }
            FinanceResult.Saved(clientId, enqueue(tenantId, opType, entityType, clientId, serializer, payload, stored.map { it.first }))
        }.also { if (it is FinanceResult.Saved) onQueued() }
    }

    private suspend fun <T> queue(tenantId: String, opType: String, entityType: String, entityId: String, serializer: KSerializer<T>, payload: T): FinanceResult {
        val database = db()
        return database.inTransaction {
            if (alreadySaved(tenantId, entityType, entityId)) return@inTransaction FinanceResult.AlreadySaved
            FinanceResult.Saved(entityId, enqueue(tenantId, opType, entityType, entityId, serializer, payload, emptyList()))
        }.also { if (it is FinanceResult.Saved) onQueued() }
    }

    private suspend fun <T> enqueue(tenantId: String, opType: String, entityType: String, entityId: String, serializer: KSerializer<T>, payload: T, attachments: List<String>): String =
        outbox.enqueueOperation(tenantId, opType, entityType, entityId, json.encodeToJsonElement(serializer, payload).jsonObject, attachments)
}
