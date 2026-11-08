package com.asseta.core.sync.usecase

import com.asseta.core.database.AssetaDatabase
import com.asseta.core.database.AttachmentEntity
import com.asseta.core.database.inTransaction
import com.asseta.core.domain.accountability.AccountabilityRules
import com.asseta.core.domain.accountability.DailyReportDraft
import com.asseta.core.domain.accountability.DailyReportRules
import com.asseta.core.domain.finance.FormCheck
import com.asseta.core.domain.policy.ReadingKind
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.model.sync.AccountabilityOps
import com.asseta.core.model.sync.BlobPurpose
import com.asseta.core.model.sync.DailyReportPayload
import com.asseta.core.model.sync.SyncCapabilities
import com.asseta.core.model.sync.UnbillableLinePayload
import com.asseta.core.sync.data.FieldOps
import com.asseta.core.sync.data.FieldOutbox
import com.asseta.core.sync.data.FieldRepository
import com.asseta.core.sync.data.IsoTime
import com.asseta.core.sync.evidence.EvidenceFiles
import com.asseta.core.sync.evidence.Sha256
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import java.util.UUID

/** One daily report from the form; [clientId] is generated once per form visit. */
data class DailyReportRequest(
    val tenantId: String,
    val clientId: String,
    val machineId: String,
    /** The local day, `yyyy-MM-dd`. */
    val reportDate: String,
    val draft: DailyReportDraft,
    val evidenceJpegs: List<ByteArray>,
    val supersedesId: String?,
    val createdAtMs: Long,
)

/**
 * Queues a `DAILY_REPORT` (DEC-032 A4) once per form visit. The operation id becomes the report id. It waits for every
 * photo upload and for the operations of any chosen reading the server does not have yet; the server applies every control.
 */
class DailyReportCapture(
    private val db: () -> AssetaDatabase,
    private val field: FieldRepository,
    private val outbox: FieldOutbox,
    private val files: EvidenceFiles,
    private val json: Json,
    private val onQueued: () -> Unit = {},
) {
    suspend fun submit(r: DailyReportRequest): FinanceResult {
        val state = db().syncStateDao().get(r.tenantId)
        if (state?.capabilities == null) return FinanceResult.Blocked(CaptureMeterReading.NEEDS_SYNC)
        if (!state.supports(SyncCapabilities.OP_DAILY_REPORT)) return FinanceResult.Blocked(CaptureMeterReading.SERVER_TOO_OLD)
        val values = when (val check = DailyReportRules.check(r.draft)) {
            is FormCheck.Invalid -> return FinanceResult.Invalid(check.messages)
            is FormCheck.Valid -> check.value
        }
        field.machine(r.machineId) ?: return FinanceResult.Blocked(CaptureMeterReading.MACHINE_MISSING)
        val evidence = r.evidenceJpegs.filter { it.isNotEmpty() }.take(DailyReportRules.MAX_PHOTOS)
        if (alreadySaved(r)) return FinanceResult.AlreadySaved
        val parents = listOf(r.draft.openingRef!!, r.draft.closingRef!!).distinct().mapNotNull { readingOp(r.tenantId, it) }
        if (parents.any { it.status == ClientOperationStatus.FAILED || it.status == ClientOperationStatus.CONFLICT }) {
            return FinanceResult.Blocked(READING_NOT_ACCEPTED)
        }
        val payload = DailyReportPayload(
            machineId = r.machineId, reportDate = r.reportDate, openingRef = r.draft.openingRef!!, closingRef = r.draft.closingRef!!,
            billableHours = values.billable?.let(AccountabilityRules::plain),
            unbillable = values.lines.map { (id, h) -> UnbillableLinePayload(id, AccountabilityRules.plain(h)) },
            note = values.note, supersedesId = r.supersedesId, clientCreatedAt = IsoTime.format(r.createdAtMs),
        )
        val stored = evidence.map { bytes -> Triple(UUID.randomUUID().toString(), files.write(bytes), bytes) }
        val database = db()
        return database.inTransaction {
            if (alreadySaved(r)) {
                stored.forEach { files.delete(it.second) }
                return@inTransaction FinanceResult.AlreadySaved
            }
            stored.forEach { (id, file, bytes) ->
                database.evidenceDao().insertAttachment(
                    AttachmentEntity(id, r.tenantId, BlobPurpose.DAILY_REPORT_EVIDENCE, file, Sha256.hex(bytes), bytes.size.toLong(),
                        "image/jpeg", AttachmentEntity.PENDING, createdAt = r.createdAtMs),
                )
            }
            val opId = outbox.enqueueOperation(
                r.tenantId, AccountabilityOps.DAILY_REPORT, FieldOps.DAILY_REPORT, r.clientId,
                json.encodeToJsonElement(DailyReportPayload.serializer(), payload).jsonObject,
                stored.map { it.first },
                parents.filter { it.status != ClientOperationStatus.ACKED }.map { it.id },
            )
            FinanceResult.Saved(r.clientId, opId)
        }.also { if (it is FinanceResult.Saved) onQueued() }
    }

    private suspend fun alreadySaved(r: DailyReportRequest) =
        db().clientOperationDao().findByEntity(r.tenantId, FieldOps.DAILY_REPORT, r.clientId) != null

    /** This phone's operation of reading [id], whatever its kind (job readings are typed by kind). */
    private suspend fun readingOp(tenantId: String, id: String) = ReadingKind.entries.firstNotNullOfOrNull { kind ->
        db().clientOperationDao().findByEntity(tenantId, FieldOps.captureEntityType(kind), id)
    }

    companion object {
        const val READING_NOT_ACCEPTED = "One of these readings was not accepted by the server. Choose another reading."
    }
}
