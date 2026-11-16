package com.asseta.core.sync.usecase

import com.asseta.core.database.AssetaDatabase
import com.asseta.core.database.AttachmentEntity
import com.asseta.core.database.inTransaction
import com.asseta.core.domain.accountability.AccountabilityRules
import com.asseta.core.domain.capture.CaptureDraft
import com.asseta.core.domain.capture.CaptureValidator
import com.asseta.core.domain.capture.GpsOutcome
import com.asseta.core.domain.capture.ReadingInput
import com.asseta.core.domain.capture.ReadingValidator
import com.asseta.core.domain.finance.AmountParser
import com.asseta.core.domain.finance.DecimalLimit
import com.asseta.core.domain.finance.FormCheck
import com.asseta.core.domain.ocr.OcrReading
import com.asseta.core.domain.policy.CaptureMode
import com.asseta.core.domain.policy.CapturePolicyDecision
import com.asseta.core.domain.policy.ReadingKind
import com.asseta.core.domain.reports.MachineReportMessages
import com.asseta.core.domain.reports.MachineReportRules
import com.asseta.core.domain.reports.ReportLine
import com.asseta.core.domain.reports.ReportLineDraft
import com.asseta.core.model.sync.BlobPurpose
import com.asseta.core.model.sync.CreditInvoicePaymentPayload
import com.asseta.core.model.sync.MachineReportLineDto
import com.asseta.core.model.sync.MachineReportLinePayload
import com.asseta.core.model.sync.MachineReportOps
import com.asseta.core.model.sync.MachineReportPayload
import com.asseta.core.model.sync.MeterCaptureIn
import com.asseta.core.model.sync.SyncCapabilities
import com.asseta.core.sync.data.FieldOps
import com.asseta.core.sync.data.FieldOutbox
import com.asseta.core.sync.data.FieldRepository
import com.asseta.core.sync.data.IsoTime
import com.asseta.core.sync.evidence.EvidenceFiles
import com.asseta.core.sync.evidence.Sha256
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import java.math.BigDecimal
import java.util.UUID

/** The new meter reading of a report, as captured on the phone (same evidence as any reading: photo, OCR, fresh GPS). */
data class ReportReading(
    val captureId: String,
    val mode: CaptureMode,
    val readingText: String,
    /** Original JPEG bytes exactly as delivered by the camera (never re-encoded). */
    val photoJpeg: ByteArray?,
    val ocrAttempts: Int,
    val latestOcr: OcrReading?,
    val gps: GpsOutcome?,
    val capturedAtMs: Long,
)

/**
 * One machine report as the three steps produced it. [reportId] is generated once per report (the operation id = the
 * server's report id, so a replay stays exactly-once). Give [reading] (a new reading) or [existingCaptureId] (the reading
 * of the rejected report [correctsReportId], split again). [previous] null = the machine has no starting reading: an
 * opening report (the reading only, no lines).
 */
data class MachineReportRequest(
    val tenantId: String,
    val reportId: String,
    val machineId: String,
    val decimals: Int,
    val previous: BigDecimal?,
    val reading: ReportReading?,
    val existingCaptureId: String? = null,
    val existingReading: String? = null,
    val correctsReportId: String? = null,
    val lines: List<ReportLineDraft>,
    /** Hours each customer can still get (the phone's cached snapshot less its unsent reports). */
    val available: Map<String, BigDecimal>,
    val note: String,
    val createdAtMs: Long,
)

/** A payment on a customer's open credit invoice, recorded in the field. [clientId] = the operation id. */
data class InvoicePaymentRequest(
    val tenantId: String,
    val clientId: String,
    val invoiceId: String,
    /** The invoice's balance on this phone (less what this phone already queued against it). */
    val balance: BigDecimal,
    val amountText: String,
    val method: com.asseta.core.domain.accountability.PaymentMethod,
    val reference: String,
    val receivedAtMs: Long,
    val noncashAllowed: Boolean,
    val evidenceJpegs: List<ByteArray> = emptyList(),
    val note: String = "",
)

/**
 * Queues ADR-008 field operations: MACHINE_REPORT (the reading with its evidence and the split, checked on the phone:
 * lines add up to the difference, customers within their cached available hours, notes on non-productive lines) and
 * CREDIT_INVOICE_PAYMENT. The server is authoritative; its refusals come back as sync conflicts.
 */
class MachineReportCapture(
    private val db: () -> AssetaDatabase,
    private val repository: FieldRepository,
    private val outbox: FieldOutbox,
    private val files: EvidenceFiles,
    private val deviceId: () -> String,
    private val json: Json,
    private val onQueued: () -> Unit = {},
) {
    suspend fun submit(r: MachineReportRequest): FinanceResult {
        unavailable(r.tenantId, SyncCapabilities.OP_MACHINE_REPORT)?.let { return FinanceResult.Blocked(it) }
        if (r.reading == null && r.existingCaptureId == null) return FinanceResult.Invalid(listOf(MachineReportMessages.READING))
        // The reading: a new capture (validated like any reading) or the rejected report's reading.
        val readingValue: BigDecimal
        var capture: MeterCaptureIn? = null
        val reading = r.reading
        if (reading != null) {
            val decision = repository.capturePolicy(r.tenantId, r.machineId)
            if (decision is CapturePolicyDecision.Blocked) return FinanceResult.Blocked(decision.message)
            decision as CapturePolicyDecision.Allowed
            val draft = CaptureDraft(ReadingKind.DAILY, reading.mode, reading.readingText, reading.photoJpeg != null, reading.ocrAttempts, reading.latestOcr, reading.gps != null)
            val violations = CaptureValidator.validate(draft, decision.policy, r.decimals)
            if (violations.isNotEmpty()) return FinanceResult.Invalid(violations.map { it.message })
            val normalized = (ReadingValidator.validate(reading.readingText, r.decimals) as ReadingInput.Valid).normalized
            readingValue = BigDecimal(normalized)
            val ocr = reading.latestOcr.takeIf { reading.mode == CaptureMode.AUTOMATIC }
            capture = MeterCaptureIn(
                id = reading.captureId, kind = ReadingKind.DAILY.name, captureMode = reading.mode.name, reading = normalized,
                ocrRawText = ocr?.rawText?.take(500), ocrValue = ocr?.value, ocrConfidence = ocr?.confidence, ocrEngine = ocr?.let { CaptureMeterReading.OCR_ENGINE },
                photoAttachmentId = null, gps = reading.gps!!.toWire(), deviceId = deviceId(), capturedAt = IsoTime.format(reading.capturedAtMs),
                policyVersionIds = decision.snapshot.versionIds, machineId = r.machineId,
            )
        } else {
            readingValue = r.existingReading?.toBigDecimalOrNull() ?: return FinanceResult.Invalid(listOf(MachineReportMessages.READING))
        }
        val opening = r.previous == null && r.correctsReportId == null
        val lines: List<ReportLine> = if (opening) {
            emptyList()
        } else {
            MachineReportRules.readingProblem(r.previous, readingValue)?.let { return FinanceResult.Invalid(listOf(it)) }
            val difference = MachineReportRules.difference(r.previous, readingValue)!!
            when (val check = MachineReportRules.check(difference, r.lines, r.available, r.decimals)) {
                is FormCheck.Invalid -> return FinanceResult.Invalid(check.messages)
                is FormCheck.Valid -> check.value
            }
        }
        if (alreadySaved(r.tenantId, r.reportId)) return FinanceResult.AlreadySaved
        val payload = MachineReportPayload(
            machineId = r.machineId,
            capture = capture,
            captureId = r.existingCaptureId.takeIf { capture == null },
            correctsReportId = r.correctsReportId,
            lines = lines.map {
                when (it) {
                    is ReportLine.Customer -> MachineReportLinePayload(MachineReportLineDto.CUSTOMER, customerId = it.customerId, hours = AccountabilityRules.plain(it.hours))
                    is ReportLine.NonProductive -> MachineReportLinePayload(MachineReportLineDto.NON_PRODUCTIVE, reasonId = it.reasonId, hours = AccountabilityRules.plain(it.hours), note = it.note)
                }
            },
            note = r.note.trim().take(MachineReportRules.MAX_NOTE).ifEmpty { null },
            clientCreatedAt = IsoTime.format(r.createdAtMs),
            opening = true.takeIf { opening },
        )
        val photo = reading?.photoJpeg
        val photoFile = photo?.let { files.write(it) }
        val attachmentId = photoFile?.let { UUID.randomUUID().toString() }
        val database = db()
        return database.inTransaction {
            if (alreadySaved(r.tenantId, r.reportId)) {
                photoFile?.let { files.delete(it) }
                return@inTransaction FinanceResult.AlreadySaved
            }
            if (photo != null && photoFile != null && attachmentId != null) {
                database.evidenceDao().insertAttachment(
                    AttachmentEntity(attachmentId, r.tenantId, BlobPurpose.METER_PHOTO, photoFile, Sha256.hex(photo), photo.size.toLong(),
                        "image/jpeg", AttachmentEntity.PENDING, createdAt = reading.capturedAtMs),
                )
            }
            // The operation id is the report id; it waits for its meter photo, whose upload id is written in when complete.
            val opId = outbox.enqueueOperation(
                r.tenantId, MachineReportOps.MACHINE_REPORT, FieldOps.MACHINE_REPORT, r.reportId,
                json.encodeToJsonElement(MachineReportPayload.serializer(), payload).jsonObject,
                listOfNotNull(attachmentId), operationId = r.reportId,
            )
            FinanceResult.Saved(r.reportId, opId)
        }.also { if (it is FinanceResult.Saved) onQueued() }
    }

    suspend fun recordInvoicePayment(r: InvoicePaymentRequest): FinanceResult {
        unavailable(r.tenantId, SyncCapabilities.OP_CREDIT_INVOICE_PAYMENT)?.let { return FinanceResult.Blocked(it) }
        val m = mutableListOf<String>()
        val amount = AmountParser.valueOrNull(r.amountText, DecimalLimit.MONEY)
        if (amount == null) m += InvoicePaymentMessages.AMOUNT
        else if (amount > r.balance) m += InvoicePaymentMessages.overBalance(AccountabilityRules.plain(r.balance))
        val reference = r.reference.trim().take(AccountabilityRules.MAX_REFERENCE).ifEmpty { null }
        when (r.method) {
            com.asseta.core.domain.accountability.PaymentMethod.CREDIT -> m += InvoicePaymentMessages.METHOD
            com.asseta.core.domain.accountability.PaymentMethod.CASH -> Unit
            else -> {
                if (!r.noncashAllowed) m += com.asseta.core.domain.accountability.AccountabilityMessages.NONCASH_OFF
                if (reference == null) m += com.asseta.core.domain.accountability.AccountabilityMessages.REFERENCE
            }
        }
        if (m.isNotEmpty()) return FinanceResult.Invalid(m)
        if (alreadySavedPayment(r.tenantId, r.clientId)) return FinanceResult.AlreadySaved
        val evidence = r.evidenceJpegs.filter { it.isNotEmpty() }.take(MAX_EVIDENCE)
        val stored = evidence.map { bytes -> Triple(UUID.randomUUID().toString(), files.write(bytes), bytes) }
        val payload = CreditInvoicePaymentPayload(
            invoiceId = r.invoiceId, amount = AccountabilityRules.plain(amount!!), method = r.method.wire,
            reference = reference.takeIf { r.method.needsReference }, receivedAt = IsoTime.format(r.receivedAtMs),
            note = r.note.trim().take(AccountabilityRules.MAX_NOTE).ifEmpty { null },
        )
        val database = db()
        return database.inTransaction {
            if (alreadySavedPayment(r.tenantId, r.clientId)) {
                stored.forEach { files.delete(it.second) }
                return@inTransaction FinanceResult.AlreadySaved
            }
            stored.forEach { (id, file, bytes) ->
                database.evidenceDao().insertAttachment(
                    AttachmentEntity(id, r.tenantId, BlobPurpose.PAYMENT_EVIDENCE, file, Sha256.hex(bytes), bytes.size.toLong(),
                        "image/jpeg", AttachmentEntity.PENDING, createdAt = r.receivedAtMs),
                )
            }
            val opId = outbox.enqueueOperation(
                r.tenantId, MachineReportOps.CREDIT_INVOICE_PAYMENT, FieldOps.CREDIT_INVOICE_PAYMENT, r.clientId,
                json.encodeToJsonElement(CreditInvoicePaymentPayload.serializer(), payload).jsonObject,
                stored.map { it.first }, operationId = r.clientId,
            )
            FinanceResult.Saved(r.clientId, opId)
        }.also { if (it is FinanceResult.Saved) onQueued() }
    }

    private suspend fun unavailable(tenantId: String, capability: String): String? {
        val state = db().syncStateDao().get(tenantId)
        return when {
            state?.capabilities == null -> CaptureMeterReading.NEEDS_SYNC
            !state.supports(capability) -> CaptureMeterReading.SERVER_TOO_OLD
            else -> null
        }
    }

    private suspend fun alreadySaved(tenantId: String, reportId: String) =
        db().clientOperationDao().findByEntity(tenantId, FieldOps.MACHINE_REPORT, reportId) != null

    private suspend fun alreadySavedPayment(tenantId: String, clientId: String) =
        db().clientOperationDao().findByEntity(tenantId, FieldOps.CREDIT_INVOICE_PAYMENT, clientId) != null

    companion object {
        const val MAX_EVIDENCE = 10
    }
}

/** Wording of the credit-invoice payment form (shared with iOS). */
object InvoicePaymentMessages {
    const val AMOUNT = "Enter the amount received (more than 0)."
    const val METHOD = "Choose Cash, Bank or Mobile money."
    fun overBalance(balance: String) = "The invoice still owes only $balance."
}
