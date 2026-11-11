package com.asseta.core.sync.data

import com.asseta.core.database.AssetaDatabase
import com.asseta.core.database.ClientOperationEntity
import com.asseta.core.domain.accountability.DepositAccountOption
import com.asseta.core.domain.finance.AdvanceChoice
import com.asseta.core.domain.finance.FundChoice
import com.asseta.core.domain.finance.PettyCashPolicy
import com.asseta.core.domain.policy.PolicySnapshot
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.model.sync.PettyCashAdvanceDto
import com.asseta.core.model.sync.PettyCashFundDto
import com.asseta.core.model.sync.PettyCashHolderChangeDto
import com.asseta.core.model.sync.PettyCashMovementDto
import com.asseta.core.model.sync.PettyCashOps
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.map
import kotlinx.serialization.KSerializer
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonObject

/** One petty cash operation recorded on this phone, with its sync state (the device's own copy). */
data class PettyCashRecord(
    val operationId: String,
    val opType: String,
    /** The movement / holder change / advance answered, or the form's client id. */
    val entityId: String,
    val fundId: String?,
    /** Amount sent, as decimal text (null for a dispute or a holder change). */
    val amount: String?,
    val status: ClientOperationStatus,
    val errorCode: String?,
    val lastError: String?,
    val createdAtMs: Long,
    /** A synced count the server recorded as a self-count (no witness while the tenant asks for one). */
    val selfCount: Boolean = false,
    /** A synced count whose chosen witness the server dropped (the witness lost the permission before the phone synced). */
    val witnessDropped: Boolean = false,
) {
    val isRefused: Boolean get() = status == ClientOperationStatus.FAILED || status == ClientOperationStatus.CONFLICT
}

/** Everything "My petty cash" shows, from the last pull and this phone's outbox. */
data class PettyCashView(
    val funds: List<PettyCashFundDto> = emptyList(),
    /** Fundings / top-ups waiting for my acknowledgement and not answered on this phone. */
    val awaiting: List<PettyCashMovementDto> = emptyList(),
    /** Funds being handed to me, not answered on this phone. */
    val holderChanges: List<PettyCashHolderChangeDto> = emptyList(),
    /** Outstanding advances (given to me, or out of a fund I hold and not cleared on this phone). */
    val advances: List<PettyCashAdvanceDto> = emptyList(),
    val records: List<PettyCashRecord> = emptyList(),
    val loaded: Boolean = false,
) {
    /** How many items wait for my answer. */
    val waitingCount: Int get() = awaiting.size + holderChanges.size

    fun fund(id: String?): PettyCashFundDto? = funds.firstOrNull { it.id == id }
}

/**
 * Read side of the field petty cash (DEC-033): the server's snapshot (funds, money waiting, holder changes, advances)
 * saved encrypted on the phone, minus what this phone already answered (an answer leaves the list until the server
 * refuses it), and this phone's petty cash operations with their sync state.
 */
class PettyCashRepository(
    private val db: () -> AssetaDatabase,
    private val field: FieldRepository,
    private val json: Json,
) {
    private fun <T> refs(tenantId: String, kind: String, serializer: KSerializer<T>): Flow<List<T>> =
        db().fieldDataDao().observeReferences(tenantId, kind).map { rows ->
            rows.mapNotNull { runCatching { json.decodeFromString(serializer, it.json) }.getOrNull() }
        }

    fun observe(tenantId: String, myStaffId: String? = null): Flow<PettyCashView> = combine(
        refs(tenantId, ServerDataWriter.KIND_PETTY_FUND, PettyCashFundDto.serializer()),
        refs(tenantId, ServerDataWriter.KIND_PETTY_AWAITING, PettyCashMovementDto.serializer()),
        refs(tenantId, ServerDataWriter.KIND_PETTY_HOLDER_CHANGE, PettyCashHolderChangeDto.serializer()),
        refs(tenantId, ServerDataWriter.KIND_PETTY_ADVANCE, PettyCashAdvanceDto.serializer()),
        db().clientOperationDao().observeByOpTypes(tenantId, field.ownerSubject(), PettyCashOps.ALL),
    ) { funds, awaiting, changes, advances, ops ->
        build(funds, awaiting, changes, advances, ops.map(::record), myStaffId)
    }

    /** The `PETTY_CASH` policy snapshot as last synced (lenient: missing = off). */
    suspend fun policy(tenantId: String): PettyCashPolicy = policyOf(field.policySnapshots(tenantId))

    /** Colleagues who may witness a count, by name, as the last pull delivered them (offline picker). */
    fun observeWitnesses(tenantId: String): Flow<List<com.asseta.core.model.sync.PettyCashWitnessDto>> =
        refs(tenantId, ServerDataWriter.KIND_PETTY_WITNESS, com.asseta.core.model.sync.PettyCashWitnessDto.serializer())
            .map { list -> list.sortedWith(compareBy({ it.name.lowercase() }, { it.userId })) }

    /** The server sends the witness list (SYNC_PETTY_CASH_WITNESSES): the count form picks offline, else searches online. */
    suspend fun witnessesOffline(tenantId: String): Boolean =
        db().syncStateDao().get(tenantId)?.supports(com.asseta.core.model.sync.SyncCapabilities.SYNC_PETTY_CASH_WITNESSES) == true

    /** Active deposit accounts in [currency] for the return form. */
    fun depositAccounts(accounts: List<DepositAccountOption>, currency: String): List<DepositAccountOption> =
        accounts.filter { it.isActive && it.currency == currency }

    private fun record(op: ClientOperationEntity): PettyCashRecord {
        val p = runCatching { json.parseToJsonElement(op.payloadJson).jsonObject }.getOrNull()
        val amount = when (op.opType) {
            PettyCashOps.ACKNOWLEDGEMENT -> p.text("amount_received")
            PettyCashOps.COUNT -> p.text("counted_amount")
            PettyCashOps.ADVANCE_CLEARANCE -> p.text("change_returned")
            PettyCashOps.HOLDER_CHANGE_ACKNOWLEDGEMENT -> null
            else -> p.text("amount")
        }
        val counted = if (op.opType == PettyCashOps.COUNT && op.status == ClientOperationStatus.ACKED) countOutcome(p, op.resultJson) else null
        return PettyCashRecord(
            op.id, op.opType, op.entityId, p.text("fund_id"), amount, op.status, op.errorCode, op.lastError, op.createdAtDevice,
            selfCount = counted?.first == true, witnessDropped = counted?.second == true,
        )
    }

    /** (self-count, witness dropped) of a synced count, from the server's copy in the push result. */
    private fun countOutcome(payload: JsonObject?, resultJson: String?): Pair<Boolean, Boolean>? {
        val entity = resultJson?.let { runCatching { json.parseToJsonElement(it).jsonObject["entity"] as? JsonObject }.getOrNull() } ?: return null
        return countOutcome(payload.text("witness_user_id"), entity.text("witness_user_id"), (entity["self_count"] as? JsonPrimitive)?.contentOrNull == "true")
    }

    private fun JsonObject?.text(key: String): String? = (this?.get(key) as? JsonPrimitive)?.contentOrNull

    companion object {
        /** (self-count, witness dropped): a witness was chosen but the server recorded none, or the server marked a self-count. */
        fun countOutcome(sentWitness: String?, recordedWitness: String?, selfCount: Boolean): Pair<Boolean, Boolean> {
            val dropped = sentWitness != null && recordedWitness == null
            return Pair(selfCount && !dropped, dropped)
        }

        fun policyOf(snapshots: List<PolicySnapshot>): PettyCashPolicy = PettyCashPolicy.fromValues(
            snapshots.firstOrNull { it.policyType == PettyCashPolicy.TYPE && it.scopeKey == PolicySnapshot.TENANT_SCOPE }?.values,
        )

        /** Pure assembly (unit-tested): answered items leave the waiting lists unless the server refused the answer. */
        fun build(
            funds: List<PettyCashFundDto>,
            awaiting: List<PettyCashMovementDto>,
            changes: List<PettyCashHolderChangeDto>,
            advances: List<PettyCashAdvanceDto>,
            records: List<PettyCashRecord>,
            myStaffId: String? = null,
        ): PettyCashView {
            fun answered(opType: String) = records.filter { it.opType == opType && !it.isRefused }.map { it.entityId }.toSet()
            val acked = answered(PettyCashOps.ACKNOWLEDGEMENT)
            val taken = answered(PettyCashOps.HOLDER_CHANGE_ACKNOWLEDGEMENT)
            val cleared = answered(PettyCashOps.ADVANCE_CLEARANCE)
            return PettyCashView(
                funds = funds.filter { it.isActive }.sortedBy { it.code },
                awaiting = awaiting.filter { it.id !in acked },
                holderChanges = changes.filter { it.id !in taken && (myStaffId == null || it.toStaffId == myStaffId) },
                advances = advances.filter { it.id !in cleared && it.status == "OUTSTANDING" },
                records = records.sortedByDescending { it.createdAtMs },
                loaded = true,
            )
        }

        /** Funds an expense can be paid from: the ones I hold, plus the funds of advances given to me. */
        fun fundChoices(view: PettyCashView, myStaffId: String?): List<FundChoice> {
            val held = view.funds.map { FundChoice(it.id, it.currency, it.balance?.availableToSpend?.toBigDecimalOrNull(), held = true) }
            val viaAdvance = advanceChoicesOf(view, myStaffId).mapNotNull { a ->
                if (held.any { it.id == a.fundId }) null
                else view.advances.firstOrNull { it.id == a.id }?.let { FundChoice(it.fundId, it.currency, null, held = false) }
            }.distinctBy { it.id }
            return held + viaAdvance
        }

        /** Advances given to me (spendable); with [myStaffId] unknown, every outstanding advance not of a fund I hold. */
        fun advanceChoicesOf(view: PettyCashView, myStaffId: String?): List<AdvanceChoice> = view.advances
            .filter { a -> if (myStaffId != null) a.recipientStaffId == myStaffId else view.funds.none { it.id == a.fundId } }
            .map { AdvanceChoice(it.id, it.fundId, it.remaining.toBigDecimalOrNull() ?: java.math.BigDecimal.ZERO) }

        /** Advances out of a fund I hold, given to someone else: the holder clears them (takes the change back). */
        fun clearable(view: PettyCashView, myStaffId: String?): List<PettyCashAdvanceDto> = view.advances
            .filter { a -> view.funds.any { it.id == a.fundId } && a.recipientStaffId != myStaffId }
    }
}
