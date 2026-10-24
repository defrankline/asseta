package com.asseta.core.sync.data

import com.asseta.core.database.AssetaDatabase
import com.asseta.core.database.ReadSnapshotEntity
import com.asseta.core.domain.accountability.CashCustodyPolicy
import com.asseta.core.domain.accountability.CustomerHoursPolicy
import com.asseta.core.domain.accountability.FieldAccess
import com.asseta.core.model.DecimalAmount
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

class FieldAccountabilityData(
    private val api: () -> TenantApi,
    private val db: () -> AssetaDatabase,
    private val json: Json,
    private val account: () -> SyncAccount?,
    private val nowMs: () -> Long = System::currentTimeMillis,
) {
    private val _cache = MutableStateFlow(FieldAccountabilityCache())
    private var loadedFor: String? = null

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
        return FieldAccess(capabilities, permissions, c.cash, c.hours)
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
        val record = FieldAccess.COLLECTION_RECORD in permissions
        val hoursRead = FieldAccess.HOURS_READ in permissions
        val next = FieldAccountabilityCache(
            fetchedAtMs = old.fetchedAtMs,
            cashPolicy = part(record, old.cashPolicy, null) { effectivePolicy(CashCustodyPolicy.TYPE) },
            hoursPolicy = part(FieldAccess.HOURS_PURCHASE in permissions, old.hoursPolicy, null) { effectivePolicy(CustomerHoursPolicy.TYPE) },
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

    /** Clears the in-memory copy (sign-out / another user); the store is cleared by the account switch. */
    fun reset() {
        loadedFor = null
        _cache.value = FieldAccountabilityCache()
    }

    companion object {
        const val KEY = "supervisor.accountability"
        private const val PAGE = 100
    }
}
