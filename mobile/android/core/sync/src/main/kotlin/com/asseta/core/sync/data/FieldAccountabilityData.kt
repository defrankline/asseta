package com.asseta.core.sync.data

import com.asseta.core.database.AssetaDatabase
import com.asseta.core.database.ReadSnapshotEntity
import com.asseta.core.domain.accountability.CashCustodyPolicy
import com.asseta.core.domain.accountability.CustomerHoursPolicy
import com.asseta.core.domain.accountability.FieldAccess
import com.asseta.core.database.ClientOperationEntity
import com.asseta.core.model.DecimalAmount
import com.asseta.core.model.TenantAccess
import com.asseta.core.model.SyncAccount
import com.asseta.core.model.owner.CashRetentionDto
import com.asseta.core.model.sync.CashReasonDto
import com.asseta.core.model.sync.CashRetentionIn
import com.asseta.core.model.sync.CashTransferDto
import com.asseta.core.model.sync.CustodianDto
import com.asseta.core.model.sync.EffectivePolicyDto
import com.asseta.core.model.sync.FieldHoursPurchaseDto
import com.asseta.core.model.sync.FloatEntryDto
import com.asseta.core.model.sync.ReasonCodeDto
import com.asseta.core.model.sync.StaffDto
import com.asseta.core.network.TenantApi
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import java.math.BigDecimal

/**
 * The accountability data the field app reads online (tenant policies, cash holders, transfers and floats waiting
 * for me, open hours purchases, reason lists), saved encrypted on the phone so the forms work offline. Every part is
 * fetched on its own: a refusal or failure keeps that part's last saved copy.
 */
@Serializable
data class FieldAccountabilityCache(
    @SerialName("fetched_at_ms") val fetchedAtMs: Long = 0,
    @SerialName("cash_policy") val cashPolicy: EffectivePolicyDto? = null,
    @SerialName("hours_policy") val hoursPolicy: EffectivePolicyDto? = null,
    val custodians: List<CustodianDto> = emptyList(),
    /** Transfers I send or receive (newest first). */
    val transfers: List<CashTransferDto> = emptyList(),
    /** Floats issued to me that wait for my acknowledgement. */
    val floats: List<FloatEntryDto> = emptyList(),
    val purchases: List<FieldHoursPurchaseDto> = emptyList(),
    @SerialName("transfer_reasons") val transferReasons: List<ReasonCodeDto> = emptyList(),
    @SerialName("retention_reasons") val retentionReasons: List<CashReasonDto> = emptyList(),
) {
    val cash: CashCustodyPolicy? get() = cashPolicy?.values?.let(CashCustodyPolicy::fromValues)
    val hours: CustomerHoursPolicy? get() = hoursPolicy?.values?.let(CustomerHoursPolicy::fromValues)

    fun custodianName(staffId: String?): String? = custodians.firstOrNull { it.staffMemberId == staffId }?.fullName

    /** Transfers to [myStaffId] still waiting for the receiver. */
    fun transfersToAcknowledge(myStaffId: String?): List<CashTransferDto> =
        transfers.filter { it.toStaffId == myStaffId && it.status == CashTransferDto.PENDING }

    /** Open purchases with hours left (on any machine). */
    fun purchasesWithHours(): List<FieldHoursPurchaseDto> =
        purchases.filter { (it.totals.remaining.toBigDecimalOrNull() ?: BigDecimal.ZERO).signum() > 0 }
}

/** Outcome of the online retention request. */
sealed interface RetentionResult {
    data class Sent(val retention: CashRetentionDto) : RetentionResult
    data class Refused(val message: String) : RetentionResult
}

/** A request to keep cash as the field app shows it: this phone's outbox copy and/or the server's record. */
data class RetentionStatus(
    /** The outbox operation (null when the request was not made on this phone, e.g. opened from a notification). */
    val operation: ClientOperationEntity?,
    /** The server's request id (from the acked operation's result, or the notification). */
    val retentionId: String?,
    /** The server's record, read online; null offline or before the request reached the server. */
    val server: CashRetentionDto?,
    /** The online read failed (offline, or refused). */
    val offline: Boolean,
)

class FieldAccountabilityData(
    private val api: () -> TenantApi,
    private val db: () -> AssetaDatabase,
    private val json: Json,
    private val account: () -> SyncAccount?,
    private val nowMs: () -> Long = System::currentTimeMillis,
) {
    private val _cache = MutableStateFlow(FieldAccountabilityCache())
    private var loadedFor: String? = null

    /** Tenant capabilities switched off (`/me` `disabled_capabilities`), per tenant; set when the tenant is opened. */
    private val disabled = java.util.concurrent.ConcurrentHashMap<String, Set<String>>()

    /** Records the tenant's switched-off capabilities from `/me` (their entry points are hidden, their data not read). */
    fun setDisabledCapabilities(tenantId: String, capabilities: Collection<String>) {
        disabled[tenantId] = capabilities.toSet()
    }

    private fun disabledFor(tenantId: String): Set<String> = disabled[tenantId].orEmpty()

    /** The saved data of the signed-in user (empty until [load] or [refresh]). */
    val cache: StateFlow<FieldAccountabilityCache> = _cache.asStateFlow()

    private fun scope(tenantId: String) = "$tenantId|${ownerSubject(account)}"

    suspend fun load(tenantId: String) {
        if (loadedFor == scope(tenantId)) return
        loadedFor = scope(tenantId)
        _cache.value = saved(tenantId) ?: FieldAccountabilityCache()
    }

    private suspend fun saved(tenantId: String): FieldAccountabilityCache? = runCatching {
        db().readSnapshotDao().get(tenantId, KEY)?.let { json.decodeFromString(FieldAccountabilityCache.serializer(), it.payloadJson) }
    }.getOrNull()

    /** My staff id (the only staff record sync delivers is the signed-in user's own). */
    suspend fun myStaffId(tenantId: String): String? =
        db().fieldDataDao().observeReferences(tenantId, ServerDataWriter.KIND_STAFF).first()
            .mapNotNull { runCatching { json.decodeFromString(StaffDto.serializer(), it.json) }.getOrNull() }
            .firstOrNull()?.id

    /** What the field app offers now: server capabilities (last pull), [permissions] and the saved tenant policies. */
    suspend fun access(tenantId: String, permissions: Set<String>): FieldAccess {
        load(tenantId)
        val capabilities = db().syncStateDao().get(tenantId)?.capabilities?.split(',')?.filter { it.isNotBlank() }?.toSet()
        val c = _cache.value
        return FieldAccess(capabilities, permissions, c.cash, c.hours, disabledFor(tenantId))
    }

    /**
     * Refreshes every part the user may read; returns true when at least one part came from the server. Parts the
     * role cannot read are not asked for (and keep nothing).
     */
    suspend fun refresh(tenantId: String, permissions: Set<String>): Boolean {
        load(tenantId)
        val me = myStaffId(tenantId)
        val old = _cache.value
        var fresh = false
        suspend fun <T> part(allowed: Boolean, keep: T, empty: T, fetch: suspend TenantApi.() -> T): T {
            if (!allowed) return empty
            return try {
                api().fetch().also { fresh = true }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                keep
            }
        }
        // CASH_CUSTODY off: the DEC-030 cash additions (policy, holders, transfers, floats to acknowledge, reasons) are not read.
        val record = FieldAccess.COLLECTION_RECORD in permissions && TenantAccess.CASH_CUSTODY !in disabledFor(tenantId)
        // A capability the tenant switched off is not read at all (its entry points are hidden).
        val hoursOn = TenantAccess.CUSTOMER_HOURS !in disabledFor(tenantId)
        val hoursRead = hoursOn && FieldAccess.HOURS_READ in permissions
        val next = FieldAccountabilityCache(
            fetchedAtMs = old.fetchedAtMs,
            cashPolicy = part(record, old.cashPolicy, null) { effectivePolicy(CashCustodyPolicy.TYPE) },
            hoursPolicy = part(hoursOn && FieldAccess.HOURS_PURCHASE in permissions, old.hoursPolicy, null) { effectivePolicy(CustomerHoursPolicy.TYPE) },
            custodians = part(record, old.custodians, emptyList()) { cashCustodians(pageSize = PAGE).items.filter { it.isActive } },
            transfers = part(record && me != null, old.transfers, emptyList()) { cashTransfers(staffMemberId = me, pageSize = PAGE).items },
            floats = part(record && me != null, old.floats, emptyList()) {
                cashFloats(staffMemberId = me, awaitingAcknowledgement = true, pageSize = PAGE).items
            },
            purchases = part(hoursRead && FieldAccess.HOURS_TRANSFER in permissions, old.purchases, emptyList()) { hoursPurchases(pageSize = PAGE).items },
            transferReasons = part(hoursRead, old.transferReasons, emptyList()) { hoursReasonCodes(kind = "TRANSFER").items.filter { it.isActive } },
            retentionReasons = part(record, old.retentionReasons, emptyList()) { cashReasons(kind = "RETENTION").items.filter { it.isActive } },
        ).let { if (fresh) it.copy(fetchedAtMs = nowMs()) else it }
        _cache.value = next
        runCatching {
            db().readSnapshotDao().putBounded(
                ReadSnapshotEntity(tenantId, KEY, json.encodeToString(FieldAccountabilityCache.serializer(), next), nowMs()),
                SupervisorOnline.MAX_SNAPSHOTS,
            )
        }
        return fresh
    }

    /** Ask to keep cash (online only; [key] is stable per form visit so a retry never asks twice). */
    suspend fun requestRetention(
        amount: BigDecimal,
        currency: String,
        reason: String,
        reasonId: String?,
        staffMemberId: String?,
        key: String,
    ): RetentionResult = try {
        RetentionResult.Sent(api().requestCashRetention(CashRetentionIn(DecimalAmount.of(amount), currency, reason, reasonId, staffMemberId), key))
    } catch (e: CancellationException) {
        throw e
    } catch (e: Exception) {
        RetentionResult.Refused(e.message ?: "The request could not be sent.")
    }

    /**
     * Status of a request to keep cash: [key] is this phone's form id (the outbox entity id) or the server's request
     * id (a notification). Once the operation is acked, the server's record is read online (GET /cash/retentions/{id}).
     */
    suspend fun retentionStatus(tenantId: String, key: String): RetentionStatus {
        val op = db().clientOperationDao().findByEntity(tenantId, FieldOps.CASH_RETENTION, key)
        val id = if (op == null) key else retentionIdOf(op)
        if (id == null) return RetentionStatus(op, null, null, offline = false)
        return try {
            RetentionStatus(op, id, api().cashRetention(id), offline = false)
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            RetentionStatus(op, id, null, offline = true)
        }
    }

    /** Overdue remittance flags read this session (by id), so a reopened screen shows at once. */
    private val overdue = java.util.concurrent.ConcurrentHashMap<String, com.asseta.core.model.owner.RemittanceOverdueDto>()

    /** The last read of overdue flag [id] (memory only), or null. */
    fun savedOverdue(id: String): com.asseta.core.model.owner.RemittanceOverdueDto? = overdue[id]

    /**
     * My overdue remittance flag (`GET /cash/remittance-overdue/{id}`, online only: the custodian or the recorder of
     * that custodian's collections that day). Null on 404, offline or any error (the caller opens the Money tab).
     */
    suspend fun remittanceOverdue(id: String): com.asseta.core.model.owner.RemittanceOverdueDto? = try {
        api().remittanceOverdueFlag(id).also { overdue[id] = it }
    } catch (e: CancellationException) {
        throw e
    } catch (e: Exception) {
        null
    }

    /** The server request id from an acked `CASH_RETENTION_REQUEST` result (`{"entity": CashRetentionDto}`). */
    fun retentionIdOf(op: ClientOperationEntity): String? = op.resultJson?.let { raw ->
        runCatching {
            val entity = json.parseToJsonElement(raw).jsonObject["entity"]?.jsonObject
            entity?.get("id")?.jsonPrimitive?.contentOrNull
        }.getOrNull()
    }

    /** Clears the in-memory copy (sign-out / another user); the store is cleared by the account switch. */
    fun reset() {
        loadedFor = null
        overdue.clear()
        _cache.value = FieldAccountabilityCache()
    }

    companion object {
        const val KEY = "supervisor.accountability"
        private const val PAGE = 100
    }
}
