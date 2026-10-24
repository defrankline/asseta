package com.asseta.core.sync.usecase

import com.asseta.core.database.AssetaDatabase
import com.asseta.core.database.AttachmentEntity
import com.asseta.core.database.inTransaction
import com.asseta.core.domain.accountability.AccountabilityRules
import com.asseta.core.domain.accountability.HoursSaleDraft
import com.asseta.core.domain.accountability.PaymentMethod
import com.asseta.core.domain.finance.FormCheck
import com.asseta.core.model.DecimalAmount
import com.asseta.core.model.sync.AccountabilityOps
import com.asseta.core.model.sync.CashFloatAckPayload
import com.asseta.core.model.sync.CashTransferAckPayload
import com.asseta.core.model.sync.CashTransferPayload
import com.asseta.core.model.sync.HoursPurchasePayload
import com.asseta.core.model.sync.HoursTransferPayload
import com.asseta.core.model.sync.PurchasePaymentPayload
import com.asseta.core.model.sync.SyncCapabilities
import com.asseta.core.model.sync.WalkInCustomerPayload
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

/** One hours sale from the field form; [clientId] is generated once per form visit (the purchase's idempotency key). */
data class HoursSaleRequest(
    val tenantId: String,
    val clientId: String,
    val draft: HoursSaleDraft,
    val walkInAllowed: Boolean,
    /** The cash holder when the recorder records for another custodian; null = the recorder. */
    val cashHolderId: String?,
    val receivedAtMs: Long,
    /** Original evidence JPEGs (receipt, mobile-money screenshot), at most ten. */
    val evidenceJpegs: List<ByteArray>,
)

data class HoursTransferRequest(
    val tenantId: String,
    val clientId: String,
    val purchaseId: String?,
    val fromMachineId: String?,
    val toMachineId: String?,
    val hoursText: String,
    /** Hours left on the purchase (on [fromMachineId]); null when unknown. */
    val remaining: java.math.BigDecimal?,
    val reason: String,
    val reasonCodeId: String?,
    val reasonCodeRequired: Boolean,
)

data class CashTransferRequest(
    val tenantId: String,
    val clientId: String,
    /** Null = the recorder (the server defaults to the caller's staff record). */
    val fromStaffId: String?,
    val toStaffId: String?,
    val myStaffId: String?,
    val amountText: String,
    val currency: String,
    /** The tenant counts recording a transfer you receive as its acknowledgement. */
    val selfAck: Boolean,
    val receivedText: String,
    val note: String,
    val transferredAtMs: Long,
)

/** The receiver's answer to a transfer ([isFloat] false) or a float; [targetId] is the transfer / float entry id. */
data class CashAckRequest(
    val tenantId: String,
    val targetId: String,
    val isFloat: Boolean,
    val acknowledge: Boolean,
    val receivedText: String,
    val note: String,
)

/**
 * Offline accountability field operations (customer hours and the cash custody chain). Each is checked with the
 * domain rules, then stored and queued atomically as one outbox operation keyed by the form's client id (exactly once
 * per visit; the server dedupes by client id too). An hours sale with evidence photos waits for every upload. The
 * server applies every control (rate card price, verification by someone else, acknowledgement, approvals).
 */
class AccountabilityCapture(
    private val db: () -> AssetaDatabase,
    private val field: FieldRepository,
    private val finance: FinanceRepository,
    private val outbox: FieldOutbox,
    private val files: EvidenceFiles,
    private val json: Json,
    private val onQueued: () -> Unit = {},
) {
    /** Null when the server advertises [capability], else why the action is unavailable. */
    suspend fun unavailable(tenantId: String, capability: String): String? {
        val state = db().syncStateDao().get(tenantId)
        return when {
            state?.capabilities == null -> CaptureMeterReading.NEEDS_SYNC
            !state.supports(capability) -> CaptureMeterReading.SERVER_TOO_OLD
            else -> null
        }
    }

    suspend fun hoursSale(r: HoursSaleRequest): FinanceResult {
        unavailable(r.tenantId, SyncCapabilities.OP_HOURS_PURCHASE)?.let { return FinanceResult.Blocked(it) }
        val values = when (val check = AccountabilityRules.hoursSale(r.draft, r.walkInAllowed)) {
            is FormCheck.Invalid -> return FinanceResult.Invalid(check.messages)
            is FormCheck.Valid -> check.value
        }
        val d = r.draft
        if (!d.walkIn) finance.activeCustomer(d.customerId!!) ?: return FinanceResult.Blocked(CUSTOMER_GONE)
        field.machine(d.machineId!!) ?: return FinanceResult.Blocked(CaptureMeterReading.MACHINE_MISSING)
        val evidence = r.evidenceJpegs.filter { it.isNotEmpty() }
        if (evidence.size > MAX_EVIDENCE) return FinanceResult.Invalid(listOf("At most $MAX_EVIDENCE evidence photos per sale."))
        if (alreadySaved(r.tenantId, FieldOps.HOURS_PURCHASE, r.clientId)) return FinanceResult.AlreadySaved
        val method = d.method ?: PaymentMethod.CASH
        val payment = if (!d.paidNow) {
            null
        } else {
            PurchasePaymentPayload(
                method = method.wire,
                amount = values.amount?.let(DecimalAmount::of),
                receivedAt = IsoTime.format(r.receivedAtMs),
                reference = values.reference,
                staffMemberId = r.cashHolderId.takeIf { method == PaymentMethod.CASH },
            )
        }
        val payload = HoursPurchasePayload(
            clientId = r.clientId,
            customerId = d.customerId.takeIf { !d.walkIn },
            // The walk-in's client id becomes the customer id: a replay of this sale returns the same customer.
            walkIn = if (d.walkIn) WalkInCustomerPayload(UUID.nameUUIDFromBytes("walk-in:${r.clientId}".toByteArray()).toString(), values.walkInName!!, values.walkInPhone) else null,
            machineId = d.machineId!!,
            hours = AccountabilityRules.plain(values.hours),
            note = values.note,
            payment = payment,
        )
        val stored = evidence.map { bytes -> Triple(UUID.randomUUID().toString(), files.write(bytes), bytes) }
        val database = db()
        return database.inTransaction {
            if (alreadySaved(r.tenantId, FieldOps.HOURS_PURCHASE, r.clientId)) {
                stored.forEach { files.delete(it.second) }
                return@inTransaction FinanceResult.AlreadySaved
            }
            stored.forEach { (id, file, bytes) ->
                database.evidenceDao().insertAttachment(
                    AttachmentEntity(id, r.tenantId, AccountabilityOps.PAYMENT_EVIDENCE, file, Sha256.hex(bytes), bytes.size.toLong(),
                        "image/jpeg", AttachmentEntity.PENDING, createdAt = r.receivedAtMs),
                )
            }
            val opId = enqueue(r.tenantId, AccountabilityOps.HOURS_PURCHASE, FieldOps.HOURS_PURCHASE, r.clientId,
                HoursPurchasePayload.serializer(), payload, stored.map { it.first })
            FinanceResult.Saved(r.clientId, opId)
        }.also { if (it is FinanceResult.Saved) onQueued() }
    }

    suspend fun hoursTransfer(r: HoursTransferRequest): FinanceResult {
        unavailable(r.tenantId, SyncCapabilities.OP_HOURS_TRANSFER_REQUEST)?.let { return FinanceResult.Blocked(it) }
        val values = when (
            val check = AccountabilityRules.hoursTransfer(
                r.purchaseId, r.fromMachineId, r.toMachineId, r.hoursText, r.remaining, r.reason, r.reasonCodeId, r.reasonCodeRequired,
            )
        ) {
            is FormCheck.Invalid -> return FinanceResult.Invalid(check.messages)
            is FormCheck.Valid -> check.value
        }
        val payload = HoursTransferPayload(
            clientId = r.clientId, purchaseId = r.purchaseId!!, fromMachineId = r.fromMachineId, toMachineId = r.toMachineId!!,
            hours = AccountabilityRules.plain(values.hours), reason = values.reason, reasonCodeId = r.reasonCodeId,
        )
        return queue(r.tenantId, AccountabilityOps.HOURS_TRANSFER_REQUEST, FieldOps.HOURS_TRANSFER, r.clientId, HoursTransferPayload.serializer(), payload)
    }

    suspend fun cashTransfer(r: CashTransferRequest): FinanceResult {
        unavailable(r.tenantId, SyncCapabilities.OP_CASH_TRANSFER)?.let { return FinanceResult.Blocked(it) }
        val from = r.fromStaffId ?: r.myStaffId
        val receiverIsMe = r.toStaffId != null && r.toStaffId == r.myStaffId
        val values = when (
            val check = AccountabilityRules.cashTransfer(from, r.toStaffId, r.amountText, r.currency, receiverIsMe, r.selfAck, r.receivedText, r.note)
        ) {
            is FormCheck.Invalid -> return FinanceResult.Invalid(check.messages)
            is FormCheck.Valid -> check.value
        }
        val payload = CashTransferPayload(
            clientId = r.clientId,
            fromStaffId = r.fromStaffId?.takeIf { it != r.myStaffId },
            toStaffId = r.toStaffId!!,
            amount = DecimalAmount.of(values.amount),
            amountReceived = values.amountReceived?.let(DecimalAmount::of),
            currency = values.currency,
            transferredAt = IsoTime.format(r.transferredAtMs),
            note = values.note,
        )
        return queue(r.tenantId, AccountabilityOps.CASH_TRANSFER, FieldOps.CASH_TRANSFER, r.clientId, CashTransferPayload.serializer(), payload)
    }

    /** One answer per transfer/float on this phone (the entity id is the transfer/float id). */
    suspend fun acknowledge(r: CashAckRequest): FinanceResult {
        unavailable(r.tenantId, SyncCapabilities.OP_CASH_TRANSFER)?.let { return FinanceResult.Blocked(it) }
        val values = when (val check = AccountabilityRules.acknowledgement(r.acknowledge, r.receivedText, r.note)) {
            is FormCheck.Invalid -> return FinanceResult.Invalid(check.messages)
            is FormCheck.Valid -> check.value
        }
        val received = values.amountReceived?.let(DecimalAmount::of)
        return if (r.isFloat) {
            queue(r.tenantId, AccountabilityOps.CASH_FLOAT_ACKNOWLEDGEMENT, FieldOps.CASH_FLOAT_ACK, r.targetId,
                CashFloatAckPayload.serializer(), CashFloatAckPayload(r.targetId, r.acknowledge, received, values.note))
        } else {
            queue(r.tenantId, AccountabilityOps.CASH_TRANSFER_ACKNOWLEDGEMENT, FieldOps.CASH_TRANSFER_ACK, r.targetId,
                CashTransferAckPayload.serializer(), CashTransferAckPayload(r.targetId, r.acknowledge, received, values.note))
        }
    }

    /** This phone already queued an answer to the transfer / float [targetId]. */
    suspend fun answered(tenantId: String, targetId: String, isFloat: Boolean): Boolean =
        alreadySaved(tenantId, if (isFloat) FieldOps.CASH_FLOAT_ACK else FieldOps.CASH_TRANSFER_ACK, targetId)

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
    ): String = outbox.enqueueOperation(tenantId, opType, entityType, clientId, json.encodeToJsonElement(serializer, payload).jsonObject, attachmentIds)

    companion object {
        const val MAX_EVIDENCE = 10
        const val CUSTOMER_GONE = "This customer is no longer active. Choose another one."
    }
}
