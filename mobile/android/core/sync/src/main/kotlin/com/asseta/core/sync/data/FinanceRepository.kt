package com.asseta.core.sync.data

import com.asseta.core.database.AssetaDatabase
import com.asseta.core.database.CashCustodyBalanceEntity
import com.asseta.core.database.ClientOperationEntity
import com.asseta.core.database.ExpenseCategoryEntity
import com.asseta.core.database.MachineEntity
import com.asseta.core.domain.finance.CustodyBalance
import com.asseta.core.domain.finance.CustodyLine
import com.asseta.core.domain.finance.CustodySummary
import com.asseta.core.domain.finance.ExpensePolicyDecision
import com.asseta.core.domain.finance.ExpensePolicySelector
import com.asseta.core.domain.finance.PaidFrom
import com.asseta.core.domain.finance.PendingCashItem
import com.asseta.core.domain.finance.PendingCashKind
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.model.sync.ContractDto
import com.asseta.core.model.sync.CustomerDto
import com.asseta.core.model.sync.OpTypes
import com.asseta.core.sync.SyncClock
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.map
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import java.math.BigDecimal
import java.time.Instant

/** A synced customer usable in pickers (active only). */
data class CustomerOption(val id: String, val code: String, val name: String, val contactName: String?)

/** One field-finance record of this device, derived from its outbox operation (the device's own copy). */
data class FinanceRecord(
    val operationId: String,
    val opType: String,
    val title: String,
    val amount: BigDecimal?,
    val currency: String?,
    val status: ClientOperationStatus,
    val errorCode: String?,
    val lastError: String?,
    val createdAtMs: Long,
) {
    /** Not yet acknowledged, but still expected to apply (pending, in flight or held while read-only). */
    val isPending: Boolean get() = status in PENDING_STATES

    /** The server refused it (rejected or conflicting): kept for the user, never counted. */
    val isRefused: Boolean get() = status == ClientOperationStatus.FAILED || status == ClientOperationStatus.CONFLICT

    companion object {
        val PENDING_STATES = setOf(ClientOperationStatus.PENDING, ClientOperationStatus.SENT, ClientOperationStatus.QUARANTINED)
    }
}

/** "My cash": the server's custody per currency next to this device's unsynced cash movements. */
data class CashView(val lines: List<CustodyLine>, val records: List<FinanceRecord>, val asOfMs: Long?)

/** Read side for the field-finance screens (Flows over the encrypted DB). Rules come from `core:domain`. */
class FinanceRepository(
    private val db: () -> AssetaDatabase,
    private val field: FieldRepository,
    private val json: Json,
    private val clock: SyncClock,
) {
    fun observeCategories(tenantId: String): Flow<List<ExpenseCategoryEntity>> =
        db().financeDataDao().observeActiveCategories(tenantId)

    suspend fun category(id: String): ExpenseCategoryEntity? = db().financeDataDao().category(id)

    /** Customers delivered by sync; deactivated ones (delta `is_active=false`) are excluded. */
    fun observeCustomers(tenantId: String): Flow<List<CustomerOption>> =
        db().fieldDataDao().observeReferences(tenantId, ServerDataWriter.KIND_CUSTOMER).map { rows ->
            rows.mapNotNull { runCatching { json.decodeFromString(CustomerDto.serializer(), it.json) }.getOrNull() }
                .filter { it.isActive }
                .map { CustomerOption(it.id, it.code, it.name, it.contactName) }
                .sortedBy { it.name.lowercase() }
        }

    suspend fun activeCustomer(id: String): CustomerDto? =
        db().fieldDataDao().reference(ServerDataWriter.KIND_CUSTOMER, id)
            ?.let { runCatching { json.decodeFromString(CustomerDto.serializer(), it.json) }.getOrNull() }
            ?.takeIf { it.isActive }

    /** The customer of a job's contract, when the contract was synced. */
    suspend fun customerOfContract(contractId: String): String? =
        db().fieldDataDao().reference(ServerDataWriter.KIND_CONTRACT, contractId)
            ?.let { runCatching { json.decodeFromString(ContractDto.serializer(), it.json) }.getOrNull() }
            ?.customerId

    fun observeMachines(tenantId: String): Flow<List<MachineEntity>> =
        db().fieldDataDao().observeMachines(tenantId).map { list -> list.sortedBy { it.assetCode } }

    fun observeJobs(tenantId: String): Flow<List<JobSummary>> = field.observeJobs(tenantId)

    /** Tenant `EXPENSE_CAPTURE` snapshot; blocked when missing, expired or past the offline grant. */
    suspend fun expensePolicy(tenantId: String): ExpensePolicyDecision =
        ExpensePolicySelector.select(field.policySnapshots(tenantId), Instant.ofEpochMilli(clock.nowMs()), field.offlineGrant(tenantId))

    /** Best local knowledge of the tenant currency (custody currency, else the jobs' currency); null when unknown. */
    suspend fun baseCurrency(tenantId: String): String? = CustodySummary.baseCurrencyHint(
        db().financeDataDao().custody(tenantId).map { it.currency },
        db().fieldDataDao().jobCurrencies(tenantId),
    )

    fun observeRecords(tenantId: String): Flow<List<FinanceRecord>> =
        combine(
            db().clientOperationDao().observeByOpTypes(tenantId, FieldOps.FINANCE_OP_TYPES),
            observeCustomers(tenantId),
        ) { ops, customers ->
            val names = customers.associate { it.id to it.name }
            ops.map { record(it, names) }
        }

    fun observeCashView(tenantId: String): Flow<CashView> =
        combine(db().financeDataDao().observeCustody(tenantId), db().clientOperationDao().observeByOpTypes(tenantId, FieldOps.FINANCE_OP_TYPES)) { custody, ops ->
            val records = ops.map { record(it, emptyMap()) }
            val pending = ops.filter { it.status in FinanceRecord.PENDING_STATES }.mapNotNull(::pendingCash)
            CashView(CustodySummary.lines(custody.map(::balance), pending), records, custody.maxOfOrNull { it.asOf })
        }

    private fun balance(row: CashCustodyBalanceEntity) = CustodyBalance(
        row.currency, BigDecimal(row.outstanding), BigDecimal(row.claimedUnverifiedHandovers), BigDecimal(row.pendingSpending),
        Instant.ofEpochMilli(row.asOf),
    )

    /** Unsynced cash movements: collections (+), handovers (-) and expenses paid from custody (-). */
    private fun pendingCash(op: ClientOperationEntity): PendingCashItem? {
        val payload = payload(op) ?: return null
        val kind = when (op.opType) {
            OpTypes.CASH_COLLECTION -> PendingCashKind.COLLECTION
            OpTypes.CASH_HANDOVER -> PendingCashKind.HANDOVER
            OpTypes.EXPENSE -> PendingCashKind.CASH_EXPENSE.takeIf { payload.text("paid_from") == PaidFrom.CASH_CUSTODY.name }
            else -> null
        } ?: return null
        val amount = payload.text("amount")?.toBigDecimalOrNull() ?: return null
        val currency = payload.text("currency") ?: return null
        return PendingCashItem(kind, amount, currency)
    }

    private fun record(op: ClientOperationEntity, customerNames: Map<String, String>): FinanceRecord {
        val p = payload(op)
        val title = when (op.opType) {
            OpTypes.EXPENSE -> "Expense · " + (p?.text("description") ?: "") +
                (if (p?.text("paid_from") == PaidFrom.CASH_CUSTODY.name) " (paid from my cash)" else " (company paid)")
            OpTypes.CASH_COLLECTION -> "Cash collected · " + (p?.text("customer_id")?.let { customerNames[it] ?: "customer" } ?: "customer")
            OpTypes.CASH_HANDOVER -> "Cash handed to office" + (p?.text("note")?.let { " · $it" } ?: "")
            OpTypes.FUEL_EVENT -> "Fuel ${p?.text("event_type")?.lowercase() ?: ""} · ${p?.text("litres") ?: "?"} L"
            else -> op.opType
        }
        val amount = when (op.opType) {
            OpTypes.FUEL_EVENT -> null
            else -> p?.text("amount")?.toBigDecimalOrNull()
        }
        return FinanceRecord(op.id, op.opType, title, amount, p?.text("currency"), op.status, op.errorCode, op.lastError, op.createdAtDevice)
    }

    private fun payload(op: ClientOperationEntity): JsonObject? =
        runCatching { json.parseToJsonElement(op.payloadJson).jsonObject }.getOrNull()

    private fun JsonObject.text(key: String): String? = (this[key] as? kotlinx.serialization.json.JsonPrimitive)?.contentOrNull
}
