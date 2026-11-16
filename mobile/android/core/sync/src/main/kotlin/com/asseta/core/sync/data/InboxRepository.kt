package com.asseta.core.sync.data

import com.asseta.core.database.AssetaDatabase
import com.asseta.core.database.AttachmentEntity
import com.asseta.core.database.ClientOperationEntity
import com.asseta.core.database.InboxRecordEntity
import com.asseta.core.database.MachineEntity
import com.asseta.core.domain.inbox.InboxMerge
import com.asseta.core.domain.inbox.InboxStatus
import com.asseta.core.domain.inbox.InboxStatusRules
import com.asseta.core.domain.inbox.LocalKey
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.model.SyncAccount
import com.asseta.core.model.sync.AccountabilityOps
import com.asseta.core.model.sync.CashCollectionPayload
import com.asseta.core.model.sync.CashHandoverPayload
import com.asseta.core.model.sync.ExpensePayload
import com.asseta.core.model.sync.FindingDto
import com.asseta.core.model.sync.FuelEventPayload
import com.asseta.core.model.sync.MeterCaptureIn
import com.asseta.core.model.sync.MeterResetPayload
import com.asseta.core.model.sync.OpTypes
import com.asseta.core.model.sync.SyncCashCollectionDto
import com.asseta.core.model.sync.SyncCashHandoverDto
import com.asseta.core.model.sync.SyncExpenseDto
import com.asseta.core.model.sync.SyncFuelEventDto
import com.asseta.core.model.sync.SyncMeterCaptureDto
import com.asseta.core.model.sync.SyncMeterResetDto
import com.asseta.core.sync.evidence.EvidenceFiles
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.combine
import kotlinx.serialization.KSerializer
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive

/** A reading of mine: the server's copy (state, findings, review) and/or this phone's queued capture. */
data class ReadingItem(
    val id: String,
    val machineId: String?,
    val kind: String,
    val reading: String,
    val captureMode: String,
    val atMs: Long,
    val status: InboxStatus,
    val server: SyncMeterCaptureDto?,
    val op: ClientOperationEntity?,
) {
    val findings: List<FindingDto> get() = server?.findings.orEmpty()
    val openFindings: Int get() = findings.count { it.status == "OPEN" }
    val blockingFindings: Int get() = findings.count { it.blocking && it.status == "OPEN" }

    /** Counts as the machine's reading (not refused by the server or replaced). */
    val counts: Boolean get() = status != InboxStatus.REJECTED && status != InboxStatus.SUPERSEDED && status != InboxStatus.NOT_SYNCED
}

data class ResetItem(
    val key: String,
    val machineId: String,
    val oldReading: String,
    val newReading: String,
    val effectiveAtMs: Long,
    val reason: String,
    val atMs: Long,
    val status: InboxStatus,
    val decidedAtMs: Long?,
    val hasEvidence: Boolean,
    val server: SyncMeterResetDto?,
    val op: ClientOperationEntity?,
)

data class ExpenseItem(
    val key: String,
    val serverId: String?,
    val description: String,
    val supplier: String?,
    val amount: String,
    val currency: String,
    val paidFrom: String,
    val categoryId: String?,
    val machineId: String?,
    val atMs: Long,
    val status: InboxStatus,
    val decisionNote: String?,
    val decidedAtMs: Long?,
    val receiptAttachmentIds: List<String>,
    val server: SyncExpenseDto?,
    val op: ClientOperationEntity?,
    /** DEC-033: the fund that paid, and why the office must look at it (server copy only). */
    val pettyCashFundId: String? = null,
    val controlFlags: List<String> = emptyList(),
)

data class FuelItem(
    val key: String,
    val eventType: String,
    val litres: String,
    val unitPrice: String?,
    val attributedCost: String?,
    val currency: String?,
    val machineId: String?,
    val expenseId: String?,
    val meterReading: String?,
    val supplier: String?,
    val note: String?,
    val atMs: Long,
    val status: InboxStatus,
    val server: SyncFuelEventDto?,
    val op: ClientOperationEntity?,
)

/** A cash collection or handover ([customerId] null for a handover). */
data class CashItem(
    val key: String,
    val isCollection: Boolean,
    val customerId: String?,
    val amount: String,
    val currency: String,
    val reference: String?,
    val note: String?,
    val atMs: Long,
    val status: InboxStatus,
    val decisionNote: String?,
    val verifiedAtMs: Long?,
    val op: ClientOperationEntity?,
    /** The human number the server gave it (collection or remittance number); null until synced. */
    val number: String? = null,
)

/** Something that needs the supervisor's attention (Inbox "Needs attention"). */
data class AttentionItem(val key: String, val kind: Kind, val refId: String, val atMs: Long, val status: InboxStatus) {
    enum class Kind { READING, RESET, EXPENSE, FUEL, COLLECTION, HANDOVER, OPERATION, UPLOAD }
}

/** Everything the supervisor tabs show, merged once per change of the encrypted store. */
data class InboxSnapshot(
    val readings: List<ReadingItem> = emptyList(),
    val resets: List<ResetItem> = emptyList(),
    val expenses: List<ExpenseItem> = emptyList(),
    val fuel: List<FuelItem> = emptyList(),
    val collections: List<CashItem> = emptyList(),
    val handovers: List<CashItem> = emptyList(),
    /** Refused operations that are not one of the records above, and evidence that failed for good. */
    val problemOperations: List<ClientOperationEntity> = emptyList(),
    val failedUploads: List<AttachmentEntity> = emptyList(),
    val machines: Map<String, MachineEntity> = emptyMap(),
    /** This phone's accountability operations (hours sales/transfers, cash transfers and answers, baselines, corrections). */
    val accountabilityOps: List<ClientOperationEntity> = emptyList(),
    val loaded: Boolean = false,
) {
    /** Newest first: rejected expenses, flagged/rejected readings, rejected cash, refused sync items, failed uploads. */
    val attention: List<AttentionItem>
        get() = buildList {
            readings.filter { it.status.needsAttention }.forEach { add(AttentionItem("r-${it.id}", AttentionItem.Kind.READING, it.id, it.atMs, it.status)) }
            resets.filter { it.status.needsAttention }.forEach { add(AttentionItem("m-${it.key}", AttentionItem.Kind.RESET, it.key, it.atMs, it.status)) }
            expenses.filter { it.status.needsAttention }.forEach { add(AttentionItem("e-${it.key}", AttentionItem.Kind.EXPENSE, it.key, it.atMs, it.status)) }
            fuel.filter { it.status.needsAttention }.forEach { add(AttentionItem("f-${it.key}", AttentionItem.Kind.FUEL, it.key, it.atMs, it.status)) }
            collections.filter { it.status.needsAttention }.forEach { add(AttentionItem("c-${it.key}", AttentionItem.Kind.COLLECTION, it.key, it.atMs, it.status)) }
            handovers.filter { it.status.needsAttention }.forEach { add(AttentionItem("h-${it.key}", AttentionItem.Kind.HANDOVER, it.key, it.atMs, it.status)) }
            problemOperations.forEach { add(AttentionItem("o-${it.id}", AttentionItem.Kind.OPERATION, it.id, it.createdAtDevice, InboxStatus.NOT_SYNCED)) }
            failedUploads.forEach { add(AttentionItem("u-${it.id}", AttentionItem.Kind.UPLOAD, it.id, it.createdAt, InboxStatus.NOT_SYNCED)) }
        }.sortedByDescending { it.atMs }

    fun machineOf(reading: ReadingItem): String? = reading.machineId

    /** Latest counted reading per machine (my captures). */
    fun latestReadingByMachine(): Map<String, ReadingItem> =
        readings.filter { it.counts }.mapNotNull { r -> machineOf(r)?.let { it to r } }
            .groupBy({ it.first }, { it.second }).mapValues { (_, list) -> list.maxBy { it.atMs } }
}

/**
 * Read side of the supervisor tabs: the server's copies of my records (`inbox_record`) merged with this phone's own
 * records (outbox operations) of the signed-in [account]. Local records show "Waiting to
 * sync" until acknowledged, then merge with the server record (matched by client id or the acknowledged server id).
 */
class InboxRepository(
    private val db: () -> AssetaDatabase,
    private val json: Json,
    private val files: EvidenceFiles,
    private val account: () -> SyncAccount?,
    private val nowMs: () -> Long = System::currentTimeMillis,
) {
    private fun owner() = ownerSubject(account)

    fun observe(tenantId: String): Flow<InboxSnapshot> {
        val database = db()
        val owner = owner()
        val ops = database.clientOperationDao().observeByOpTypes(tenantId, owner, ALL_OP_TYPES)
        return combine(
            database.inboxDao().observeAll(tenantId),
            ops,
            database.evidenceDao().observeFailedAttachments(tenantId, owner),
            database.fieldDataDao().observeMachines(tenantId),
        ) { records, operations, failed, machines -> build(records, operations, failed, machines) }
    }

    /** Pure merge of one state of the store (unit-tested). */
    fun build(
        records: List<InboxRecordEntity>,
        operations: List<ClientOperationEntity>,
        failedUploads: List<AttachmentEntity>,
        machines: List<MachineEntity>,
    ): InboxSnapshot {
        val byKind = records.groupBy { it.kind }
        fun <T> parse(kind: String, serializer: KSerializer<T>): List<T> =
            byKind[kind].orEmpty().mapNotNull { runCatching { json.decodeFromString(serializer, it.json) }.getOrNull() }
        val opsByType = operations.groupBy { it.opType }
        fun ops(type: String) = opsByType[type].orEmpty()

        // A reading on this phone is its DAILY METER_CAPTURE operation, until the server's copy replaces it.
        val dailyType = FieldOps.captureEntityType(com.asseta.core.domain.policy.ReadingKind.DAILY)
        val readings = merge(
            parse(InboxRecordEntity.METER_CAPTURE, SyncMeterCaptureDto.serializer()), ops(OpTypes.METER_CAPTURE).filter { it.entityType == dailyType },
            { setOf(it.id) },
        ) { s, op ->
            val p = op?.let { payload(it, MeterCaptureIn.serializer()) }
            ReadingItem(
                id = s?.id ?: op!!.entityId, machineId = s?.machineId ?: p?.machineId, kind = s?.kind ?: p?.kind ?: DAILY,
                reading = s?.reading ?: p?.reading.orEmpty(), captureMode = s?.captureMode ?: p?.captureMode.orEmpty(),
                atMs = (s?.capturedAt ?: p?.capturedAt)?.let(::ms) ?: op?.createdAtDevice ?: 0,
                status = InboxStatusRules.combined(op?.status, s?.let { InboxStatusRules.reading(it.state, it.reviewStatus, it.findings.map { f -> f.status }) }),
                server = s, op = op,
            )
        }

        val resets = merge(parse(InboxRecordEntity.METER_RESET, SyncMeterResetDto.serializer()), ops(OpTypes.METER_RESET_REQUEST), { setOf(it.id) }) { s, op ->
            val p = op?.let { payload(it, MeterResetPayload.serializer()) }
            ResetItem(
                key = s?.id ?: op!!.id, machineId = s?.machineId ?: p?.machineId.orEmpty(),
                oldReading = s?.oldReading ?: p?.oldReading.orEmpty(), newReading = s?.newReading ?: p?.newReading.orEmpty(),
                effectiveAtMs = (s?.effectiveAt ?: p?.effectiveAt)?.let(::ms) ?: op?.createdAtDevice ?: 0,
                reason = s?.reason ?: p?.reason.orEmpty(), atMs = op?.createdAtDevice ?: ms(s!!.createdAt),
                status = InboxStatusRules.combined(op?.status, s?.let { InboxStatusRules.reset(it.status) }),
                decidedAtMs = s?.decidedAt?.let(::ms), hasEvidence = s?.evidenceAttachmentId != null || op != null, server = s, op = op,
            )
        }

        val expenses = merge(parse(InboxRecordEntity.EXPENSE, SyncExpenseDto.serializer()), ops(OpTypes.EXPENSE), { setOfNotNull(it.id, it.clientId) }) { s, op ->
            val p = op?.let { payload(it, ExpensePayload.serializer()) }
            ExpenseItem(
                key = s?.id ?: op!!.id, serverId = s?.id, description = s?.description ?: p?.description.orEmpty(),
                supplier = s?.supplier ?: p?.supplier, amount = s?.amount ?: p?.amount?.toPlainString().orEmpty(),
                currency = s?.currency ?: p?.currency.orEmpty(), paidFrom = s?.paidFrom ?: p?.paidFrom.orEmpty(),
                categoryId = s?.categoryId ?: p?.categoryId, machineId = s?.machineId ?: p?.machineId,
                atMs = (s?.incurredAt ?: p?.incurredAt)?.let(::ms) ?: op?.createdAtDevice ?: 0,
                status = InboxStatusRules.combined(op?.status, s?.let { InboxStatusRules.expense(it.status) }),
                decisionNote = s?.decisionNote, decidedAtMs = s?.decidedAt?.let(::ms),
                receiptAttachmentIds = s?.receiptAttachmentIds.orEmpty(), server = s, op = op,
                pettyCashFundId = s?.pettyCashFundId ?: p?.pettyCashFundId, controlFlags = s?.controlFlags.orEmpty(),
            )
        }

        val fuel = merge(parse(InboxRecordEntity.FUEL_EVENT, SyncFuelEventDto.serializer()), ops(OpTypes.FUEL_EVENT), { setOfNotNull(it.id, it.clientId) }) { s, op ->
            val p = op?.let { payload(it, FuelEventPayload.serializer()) }
            FuelItem(
                key = s?.id ?: op!!.id, eventType = s?.eventType ?: p?.eventType.orEmpty(),
                litres = s?.litres ?: p?.litres?.toPlainString().orEmpty(), unitPrice = s?.unitPrice ?: p?.unitPrice?.toPlainString(),
                attributedCost = s?.attributedCost, currency = s?.currency ?: p?.currency, machineId = s?.machineId ?: p?.machineId,
                expenseId = s?.expenseId, meterReading = s?.meterReading ?: p?.meterReading?.toPlainString(),
                supplier = s?.supplier ?: p?.supplier, note = s?.note ?: p?.note,
                atMs = (s?.occurredAt ?: p?.occurredAt)?.let(::ms) ?: op?.createdAtDevice ?: 0,
                status = InboxStatusRules.combined(op?.status, s?.let { InboxStatus.RECORDED }), server = s, op = op,
            )
        }

        val collections = merge(parse(InboxRecordEntity.CASH_COLLECTION, SyncCashCollectionDto.serializer()), ops(OpTypes.CASH_COLLECTION), { setOfNotNull(it.id, it.clientId) }) { s, op ->
            val p = op?.let { payload(it, CashCollectionPayload.serializer()) }
            CashItem(
                key = s?.id ?: op!!.id, isCollection = true, customerId = s?.customerId ?: p?.customerId,
                amount = s?.amount ?: p?.amount?.toPlainString().orEmpty(), currency = s?.currency ?: p?.currency.orEmpty(),
                reference = s?.reference ?: p?.reference, note = s?.note ?: p?.note,
                atMs = (s?.receivedAt ?: p?.receivedAt)?.let(::ms) ?: op?.createdAtDevice ?: 0,
                status = InboxStatusRules.combined(op?.status, s?.let { InboxStatusRules.settlement(it.status) }),
                decisionNote = s?.decisionNote, verifiedAtMs = s?.verifiedAt?.let(::ms), op = op,
                number = s?.collectionNumber,
            )
        }

        val handovers = merge(parse(InboxRecordEntity.CASH_HANDOVER, SyncCashHandoverDto.serializer()), ops(OpTypes.CASH_HANDOVER), { setOfNotNull(it.id, it.clientId) }) { s, op ->
            val p = op?.let { payload(it, CashHandoverPayload.serializer()) }
            CashItem(
                key = s?.id ?: op!!.id, isCollection = false, customerId = null,
                amount = s?.amount ?: p?.amount?.toPlainString().orEmpty(), currency = s?.currency ?: p?.currency.orEmpty(),
                reference = s?.reference ?: p?.reference, note = s?.note ?: p?.note,
                atMs = (s?.handedAt ?: p?.handedAt)?.let(::ms) ?: op?.createdAtDevice ?: 0,
                status = InboxStatusRules.combined(op?.status, s?.let { InboxStatusRules.settlement(it.status) }),
                decisionNote = s?.decisionNote, verifiedAtMs = s?.verifiedAt?.let(::ms), op = op,
                number = s?.remittanceNumber,
            )
        }

        // Refused operations without a list of their own are listed under "Needs attention" as sync items.
        val problems = operations.filter { it.opType in ACCOUNTABILITY_OP_TYPES && it.status.isRefused() }
        return InboxSnapshot(
            readings = readings.sortedByDescending { it.atMs },
            resets = resets.sortedByDescending { it.atMs },
            expenses = expenses.sortedByDescending { it.atMs },
            fuel = fuel.sortedByDescending { it.atMs },
            collections = collections.sortedByDescending { it.atMs },
            handovers = handovers.sortedByDescending { it.atMs },
            problemOperations = problems,
            failedUploads = failedUploads,
            machines = machines.associateBy { it.id },
            accountabilityOps = operations.filter { it.opType in ACCOUNTABILITY_OP_TYPES }.sortedByDescending { it.createdAtDevice },
            loaded = true,
        )
    }

    /** An operation's top-level payload values as text (for list rows of operations without a typed copy). */
    fun payloadText(op: ClientOperationEntity): Map<String, String?> = runCatching {
        json.parseToJsonElement(op.payloadJson).jsonObject.mapValues { (_, v) -> (v as? kotlinx.serialization.json.JsonPrimitive)?.contentOrNull }
    }.getOrDefault(emptyMap())

    /** The GPS attempt a queued reading carries (its METER_CAPTURE payload), or null. */
    fun payloadGps(op: ClientOperationEntity): com.asseta.core.model.sync.GpsIn? = payload(op, MeterCaptureIn.serializer())?.gps

    /** The reading value of one of my readings as the server has it (shown on the correction form), or null. */
    suspend fun readingValue(tenantId: String, id: String): String? =
        db().inboxDao().kind(tenantId, InboxRecordEntity.METER_CAPTURE).firstOrNull { it.id == id }
            ?.let { runCatching { json.decodeFromString(SyncMeterCaptureDto.serializer(), it.json).reading }.getOrNull() }

    /** Decrypted local evidence (meter photo, reset evidence, receipts) of an attachment, or null. */
    suspend fun localEvidence(attachmentLocalId: String): ByteArray? {
        val row = db().evidenceDao().attachment(attachmentLocalId) ?: return null
        return runCatching { files.read(row.fileName) }.getOrNull()
    }

    /** The local evidence files an operation carries (meter photo, reset photo, receipts). */
    suspend fun attachmentsOf(operationId: String): List<String> = db().clientOperationDao().attachmentsOf(operationId)

    private fun <S, R> merge(
        server: List<S>,
        local: List<ClientOperationEntity>,
        serverKeys: (S) -> Set<String>,
        item: (S?, ClientOperationEntity?) -> R,
    ): List<R> = InboxMerge.merge(server, local, serverKeys) { LocalKey(it.entityId, serverIdOf(it)) }.map { item(it.server, it.local) }

    /** The server id an acknowledged operation returned (`result.entity.id`), if any. */
    private fun serverIdOf(op: ClientOperationEntity): String? = op.resultJson?.let { text ->
        runCatching { json.parseToJsonElement(text).jsonObject["entity"]?.jsonObject?.get("id")?.jsonPrimitive?.contentOrNull }.getOrNull()
    }

    private fun <T> payload(op: ClientOperationEntity, serializer: KSerializer<T>): T? =
        runCatching { json.decodeFromString(serializer, op.payloadJson) }.getOrNull()

    private fun ms(iso: String): Long = runCatching { IsoTime.parse(iso).toEpochMilli() }.getOrDefault(0L)

    private fun ClientOperationStatus.isRefused() = this == ClientOperationStatus.FAILED || this == ClientOperationStatus.CONFLICT

    companion object {
        private const val DAILY = "DAILY"
        val ACCOUNTABILITY_OP_TYPES = setOf(
            AccountabilityOps.CASH_TRANSFER, AccountabilityOps.CASH_TRANSFER_ACKNOWLEDGEMENT, AccountabilityOps.CASH_FLOAT_ACKNOWLEDGEMENT,
            AccountabilityOps.HOURS_PURCHASE, AccountabilityOps.HOURS_TRANSFER_REQUEST, AccountabilityOps.METER_BASELINE,
            AccountabilityOps.METER_CORRECTION, AccountabilityOps.CASH_RETENTION_REQUEST,
            com.asseta.core.model.sync.MachineReportOps.MACHINE_REPORT, com.asseta.core.model.sync.MachineReportOps.CREDIT_INVOICE_PAYMENT,
        )
        val ALL_OP_TYPES = listOf(
            OpTypes.METER_CAPTURE, OpTypes.EXPENSE,
            OpTypes.CASH_COLLECTION, OpTypes.CASH_HANDOVER, OpTypes.FUEL_EVENT, OpTypes.METER_RESET_REQUEST,
            AccountabilityOps.CASH_TRANSFER, AccountabilityOps.CASH_TRANSFER_ACKNOWLEDGEMENT, AccountabilityOps.CASH_FLOAT_ACKNOWLEDGEMENT,
            AccountabilityOps.HOURS_PURCHASE, AccountabilityOps.HOURS_TRANSFER_REQUEST, AccountabilityOps.METER_BASELINE,
            AccountabilityOps.METER_CORRECTION, AccountabilityOps.CASH_RETENTION_REQUEST,
            com.asseta.core.model.sync.MachineReportOps.MACHINE_REPORT, com.asseta.core.model.sync.MachineReportOps.CREDIT_INVOICE_PAYMENT,
        )
    }
}
