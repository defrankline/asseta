package com.asseta.core.sync.usecase

import com.asseta.core.database.AssetaDatabase
import com.asseta.core.database.AttachmentEntity
import com.asseta.core.database.inTransaction
import com.asseta.core.domain.accountability.RemittanceMethod
import com.asseta.core.domain.accountability.RemittanceRequirements
import com.asseta.core.domain.accountability.RemittanceRules
import com.asseta.core.domain.capture.GpsOutcome
import com.asseta.core.domain.finance.CashRules
import com.asseta.core.domain.finance.ExpenseDraft
import com.asseta.core.domain.finance.ExpensePolicyDecision
import com.asseta.core.domain.finance.ExpenseRules
import com.asseta.core.domain.finance.FormCheck
import com.asseta.core.domain.finance.FuelEventType
import com.asseta.core.domain.finance.PaidFrom
import com.asseta.core.model.DecimalAmount
import com.asseta.core.model.sync.BlobPurpose
import com.asseta.core.model.sync.CashCollectionPayload
import com.asseta.core.model.sync.CashHandoverPayload
import com.asseta.core.model.sync.ExpensePayload
import com.asseta.core.model.sync.FuelEventPayload
import com.asseta.core.model.sync.OpTypes
import com.asseta.core.model.sync.SyncCapabilities
import com.asseta.core.sync.data.FieldOps
import com.asseta.core.sync.data.FieldOutbox
import com.asseta.core.sync.data.FieldRepository
import com.asseta.core.sync.data.FinanceRepository
import com.asseta.core.sync.data.IsoTime
import com.asseta.core.sync.evidence.EvidenceFiles
import com.asseta.core.sync.evidence.Sha256
import kotlinx.serialization.KSerializer
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import java.util.UUID

sealed interface FinanceResult {
    data class Saved(val clientId: String, val operationId: String) : FinanceResult
    data object AlreadySaved : FinanceResult
    data class Blocked(val message: String) : FinanceResult
    data class Invalid(val messages: List<String>) : FinanceResult
}

/** One expense as produced by the expense screen. [clientId] is generated once per form visit. */
data class ExpenseRequest(
    val tenantId: String,
    val clientId: String,
    val categoryId: String?,
    val description: String,
    val supplier: String,
    val amountText: String,
    val currency: String,
    val paidFrom: PaidFrom?,
    val machineId: String?,
    val jobId: String?,
    /** Original receipt JPEG bytes from the camera, one per photo (encrypted at rest, never re-encoded); at most ten. */
    val receiptJpegs: List<ByteArray>,
    val gps: GpsOutcome?,
    val incurredAtMs: Long,
)

data class CashCollectionRequest(
    val tenantId: String,
    val clientId: String,
    val customerId: String?,
    val jobId: String?,
    val amountText: String,
    val currency: String,
    val reference: String,
    val note: String,
    val receivedAtMs: Long,
    /** Another custodian holding the cash (recorders may record for others per tenant policy); null = me. */
    val cashHolderId: String? = null,
)

data class CashHandoverRequest(
    val tenantId: String,
    val clientId: String,
    val amountText: String,
    val currency: String,
    val reference: String,
    val note: String,
    val handedAtMs: Long,
    /** Another custodian remitting (recorders may record for others per tenant policy); null = me. */
    val cashHolderId: String? = null,
    /** DEC-031 D2 details, sent only when the server announces REMITTANCE_DETAILS_V1 (null = form without them). */
    val details: RemittanceDetails? = null,
)

/** How and where the money went, with the deposit slip photos (original JPEGs, stored encrypted on save). */
class RemittanceDetails(
    val method: RemittanceMethod,
    val depositAccountId: String?,
    val evidenceJpegs: List<ByteArray>,
    val requirements: RemittanceRequirements,
)

data class FuelEventRequest(
    val tenantId: String,
    val clientId: String,
    val eventType: FuelEventType?,
    val litresText: String,
    val unitPriceText: String,
    val currency: String,
    val machineId: String?,
    val jobId: String?,
    val meterReadingText: String,
    val supplier: String,
    val note: String,
    val occurredAtMs: Long,
)

/**
 * Offline field finance: expenses (receipt + GPS under the synced EXPENSE_CAPTURE snapshot), cash collections, cash
 * handovers and fuel events. Each is validated with the domain rules, then stored and queued atomically as one outbox
 * operation whose entity id is the form's client id (exactly once per visit; the server dedupes by client id too). An
 * expense with receipts (up to [ExpenseRules.MAX_RECEIPTS]) waits for every receipt upload (attachment gate) and is sent
 * with all their completed upload ids.
 */
class FinanceCapture(
    private val db: () -> AssetaDatabase,
    private val field: FieldRepository,
    private val finance: FinanceRepository,
    private val outbox: FieldOutbox,
    private val files: EvidenceFiles,
    private val deviceId: () -> String,
    private val json: Json,
    private val onQueued: () -> Unit = {},
) {
    suspend fun expense(r: ExpenseRequest): FinanceResult {
        val decision = finance.expensePolicy(r.tenantId)
        if (decision is ExpensePolicyDecision.Blocked) return FinanceResult.Blocked(decision.message)
        decision as ExpensePolicyDecision.Allowed
        val receipts = r.receiptJpegs.filter { it.isNotEmpty() }
        if (receipts.size > ExpenseRules.MAX_RECEIPTS) {
            return FinanceResult.Invalid(listOf("At most ${ExpenseRules.MAX_RECEIPTS} receipt photos per expense."))
        }
        if (r.categoryId != null && finance.category(r.categoryId)?.isActive != true) {
            return FinanceResult.Blocked("This category is no longer available. Choose another one.")
        }
        val job = r.jobId?.let { field.job(it) ?: return FinanceResult.Blocked("This job is no longer assigned to you.") }
        val machineId = r.machineId ?: job?.machineId
        if (machineId != null && field.machine(machineId) == null) return FinanceResult.Blocked("This machine is not on this device.")
        val draft = ExpenseDraft(
            r.categoryId, r.description, r.supplier, r.amountText, r.currency, r.paidFrom, machineId, r.jobId, job?.machineId,
            receipts.isNotEmpty(), r.gps,
        )
        val assessment = ExpenseRules.assess(draft, decision.policy, finance.baseCurrency(r.tenantId))
        if (!assessment.isValid) return FinanceResult.Invalid(assessment.issues.map { it.message })
        if (alreadySaved(r.tenantId, FieldOps.EXPENSE, r.clientId)) return FinanceResult.AlreadySaved // cheap pre-check

        val stored = receipts.map { bytes -> StoredReceipt(UUID.randomUUID().toString(), files.write(bytes), bytes) }
        val payload = ExpensePayload(
            clientId = r.clientId,
            categoryId = r.categoryId!!,
            supplier = r.supplier.trim().takeIf { it.isNotEmpty() },
            description = r.description.trim(),
            amount = DecimalAmount.of(assessment.amount!!),
            currency = assessment.currency!!,
            incurredAt = IsoTime.format(r.incurredAtMs),
            machineId = machineId,
            jobId = r.jobId,
            paidFrom = r.paidFrom!!.name,
            receiptUploadIds = emptyList(), // filled in as each receipt upload completes, before the op is ever sent
            gps = r.gps!!.toWire(),
            deviceId = deviceId(),
        )
        val database = db()
        return database.inTransaction {
            if (alreadySaved(r.tenantId, FieldOps.EXPENSE, r.clientId)) { // authoritative check, serialized with writes
                stored.forEach { files.delete(it.fileName) }
                return@inTransaction FinanceResult.AlreadySaved
            }
            stored.forEach { receipt ->
                database.evidenceDao().insertAttachment(
                    AttachmentEntity(receipt.id, r.tenantId, BlobPurpose.EXPENSE_RECEIPT, receipt.fileName, Sha256.hex(receipt.bytes),
                        receipt.bytes.size.toLong(), "image/jpeg", AttachmentEntity.PENDING, createdAt = r.incurredAtMs),
                )
            }
            val opId = enqueue(
                r.tenantId, OpTypes.EXPENSE, FieldOps.EXPENSE, r.clientId, ExpensePayload.serializer(), payload, stored.map { it.id },
            )
            FinanceResult.Saved(r.clientId, opId)
        }.also { if (it is FinanceResult.Saved) onQueued() }
    }

    suspend fun cashCollection(r: CashCollectionRequest): FinanceResult {
        val values = when (val check = CashRules.collection(r.customerId, r.amountText, r.currency, r.reference, r.note)) {
            is FormCheck.Invalid -> return FinanceResult.Invalid(check.messages)
            is FormCheck.Valid -> check.value
        }
        finance.activeCustomer(r.customerId!!) ?: return FinanceResult.Blocked("This customer is no longer active. Choose another one.")
        val job = r.jobId?.let { field.job(it) ?: return FinanceResult.Blocked("This job is no longer assigned to you.") }
        if (job != null) {
            val jobCustomer = finance.customerOfContract(job.contractId)
            if (jobCustomer != null && jobCustomer != r.customerId) return FinanceResult.Invalid(listOf("Job ${job.jobNumber} belongs to another customer."))
        }
        // The collection contract has no job field: the job is recorded in the note so the office can see it.
        val note = listOfNotNull(job?.let { "Job ${it.jobNumber}" }, values.note).joinToString(" · ").takeIf { it.isNotEmpty() }?.take(CashRules.MAX_NOTE)
        val payload = CashCollectionPayload(
            r.clientId, r.customerId, DecimalAmount.of(values.amount), values.currency, IsoTime.format(r.receivedAtMs), values.reference, note,
            r.cashHolderId,
        )
        return queue(r.tenantId, OpTypes.CASH_COLLECTION, FieldOps.CASH_COLLECTION, r.clientId, CashCollectionPayload.serializer(), payload)
    }

    suspend fun cashHandover(r: CashHandoverRequest): FinanceResult {
        val values = when (val check = CashRules.handover(r.amountText, r.currency, r.reference, r.note)) {
            is FormCheck.Invalid -> return FinanceResult.Invalid(check.messages)
            is FormCheck.Valid -> check.value
        }
        val d = r.details
        if (d != null && !supports(r.tenantId, SyncCapabilities.REMITTANCE_DETAILS_V1)) {
            return FinanceResult.Blocked(CaptureMeterReading.SERVER_TOO_OLD)
        }
        val evidence = d?.evidenceJpegs.orEmpty().filter { it.isNotEmpty() }
        if (d != null) {
            val account = d.depositAccountId?.let { finance.depositAccount(it) }
            val issues = RemittanceRules.check(d.requirements, d.method, d.depositAccountId, account, values.currency, values.reference.orEmpty(), evidence.size)
            if (issues.isNotEmpty()) return FinanceResult.Invalid(issues)
        }
        val payload = CashHandoverPayload(
            r.clientId, DecimalAmount.of(values.amount), values.currency, IsoTime.format(r.handedAtMs), values.reference, values.note,
            r.cashHolderId,
            method = d?.method?.wire,
            depositAccountId = d?.depositAccountId,
            evidenceUploadIds = d?.let { emptyList() }, // filled in as each photo upload completes, before the op is sent
        )
        if (evidence.isEmpty()) {
            return queue(r.tenantId, OpTypes.CASH_HANDOVER, FieldOps.CASH_HANDOVER, r.clientId, CashHandoverPayload.serializer(), payload)
        }
        if (alreadySaved(r.tenantId, FieldOps.CASH_HANDOVER, r.clientId)) return FinanceResult.AlreadySaved
        val stored = evidence.map { bytes -> StoredReceipt(UUID.randomUUID().toString(), files.write(bytes), bytes) }
        val database = db()
        return database.inTransaction {
            if (alreadySaved(r.tenantId, FieldOps.CASH_HANDOVER, r.clientId)) {
                stored.forEach { files.delete(it.fileName) }
                return@inTransaction FinanceResult.AlreadySaved
            }
            stored.forEach { photo ->
                database.evidenceDao().insertAttachment(
                    AttachmentEntity(photo.id, r.tenantId, BlobPurpose.REMITTANCE_EVIDENCE, photo.fileName, Sha256.hex(photo.bytes),
                        photo.bytes.size.toLong(), "image/jpeg", AttachmentEntity.PENDING, createdAt = r.handedAtMs),
                )
            }
            val opId = enqueue(
                r.tenantId, OpTypes.CASH_HANDOVER, FieldOps.CASH_HANDOVER, r.clientId, CashHandoverPayload.serializer(), payload, stored.map { it.id },
            )
            FinanceResult.Saved(r.clientId, opId)
        }.also { if (it is FinanceResult.Saved) onQueued() }
    }

    private suspend fun supports(tenantId: String, capability: String): Boolean =
        db().syncStateDao().get(tenantId)?.supports(capability) == true

    suspend fun fuelEvent(r: FuelEventRequest): FinanceResult {
        val job = r.jobId?.let { field.job(it) ?: return FinanceResult.Blocked("This job is no longer assigned to you.") }
        val machineId = r.machineId ?: job?.machineId
        val values = when (
            val check = CashRules.fuel(r.eventType, r.litresText, r.unitPriceText, r.currency, machineId, r.meterReadingText, r.supplier, r.note)
        ) {
            is FormCheck.Invalid -> return FinanceResult.Invalid(check.messages)
            is FormCheck.Valid -> check.value
        }
        if (job != null && machineId != job.machineId) return FinanceResult.Invalid(listOf("The selected machine is not the machine of job ${job.jobNumber}."))
        if (machineId != null && field.machine(machineId) == null) return FinanceResult.Blocked("This machine is not on this device.")
        val payload = FuelEventPayload(
            clientId = r.clientId,
            eventType = r.eventType!!.name,
            litres = DecimalAmount.of(values.litres),
            unitPrice = values.unitPrice?.let(DecimalAmount::of),
            currency = values.currency,
            machineId = machineId,
            jobId = r.jobId,
            meterReading = values.meterReading?.let(DecimalAmount::of),
            supplier = values.supplier,
            occurredAt = IsoTime.format(r.occurredAtMs),
            note = values.note,
        )
        return queue(r.tenantId, OpTypes.FUEL_EVENT, FieldOps.FUEL_EVENT, r.clientId, FuelEventPayload.serializer(), payload)
    }

    private suspend fun alreadySaved(tenantId: String, entityType: String, clientId: String): Boolean =
        db().clientOperationDao().findByEntity(tenantId, entityType, clientId) != null

    private suspend fun <T> queue(
        tenantId: String,
        opType: String,
        entityType: String,
        clientId: String,
        serializer: KSerializer<T>,
        payload: T,
    ): FinanceResult {
        val database = db()
        return database.inTransaction {
            if (alreadySaved(tenantId, entityType, clientId)) return@inTransaction FinanceResult.AlreadySaved
            FinanceResult.Saved(clientId, enqueue(tenantId, opType, entityType, clientId, serializer, payload, emptyList()))
        }.also { if (it is FinanceResult.Saved) onQueued() }
    }

    private suspend fun <T> enqueue(
        tenantId: String,
        opType: String,
        entityType: String,
        clientId: String,
        serializer: KSerializer<T>,
        payload: T,
        attachmentIds: List<String>,
    ): String = outbox.enqueueOperation(
        tenantId, opType, entityType, clientId, json.encodeToJsonElement(serializer, payload).jsonObject, attachmentIds,
    )

    private class StoredReceipt(val id: String, val fileName: String, val bytes: ByteArray)
}
