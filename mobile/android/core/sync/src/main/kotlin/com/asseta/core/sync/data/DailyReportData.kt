package com.asseta.core.sync.data

import com.asseta.core.database.AssetaDatabase
import com.asseta.core.database.ClientOperationEntity
import com.asseta.core.database.ReadSnapshotEntity
import com.asseta.core.model.SyncAccount
import com.asseta.core.model.owner.DailyReportDto
import com.asseta.core.model.owner.DailyReportPrefillDto
import com.asseta.core.model.sync.AccountabilityOps
import com.asseta.core.model.sync.DailyReportPayload
import com.asseta.core.network.TenantApi
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import java.time.Instant
import java.time.ZoneId

@Serializable
data class DailyReportCache(val fetchedAtMs: Long = 0, val reports: List<DailyReportDto> = emptyList())

/** A daily report as the field app shows it: the server's copy and/or this phone's unsent one ([key] is the report id). */
data class DailyReportRow(val key: String, val server: DailyReportDto?, val local: DailyReportPayload?, val op: ClientOperationEntity?) {
    val machineId: String get() = server?.machineId ?: local!!.machineId
    val reportDate: String get() = server?.reportDate ?: local!!.reportDate
    val returned: Boolean get() = server?.status == DailyReportDto.RETURNED
}

/** My daily reports: read online, saved encrypted, merged with what this phone has not sent yet. */
class DailyReportData(
    private val api: () -> TenantApi,
    private val db: () -> AssetaDatabase,
    private val json: Json,
    private val account: () -> SyncAccount?,
    private val nowMs: () -> Long = System::currentTimeMillis,
) {
    private val cache = MutableStateFlow(DailyReportCache())
    private var loadedFor: String? = null

    private suspend fun load(tenantId: String) {
        val scope = "$tenantId|${ownerSubject(account)}"
        if (loadedFor == scope) return
        loadedFor = scope
        cache.value = runCatching {
            db().readSnapshotDao().get(tenantId, KEY)?.let { json.decodeFromString(DailyReportCache.serializer(), it.payloadJson) }
        }.getOrNull() ?: DailyReportCache()
    }

    private suspend fun save(tenantId: String, value: DailyReportCache) {
        cache.value = value
        runCatching {
            db().readSnapshotDao().putBounded(
                ReadSnapshotEntity(tenantId, KEY, json.encodeToString(DailyReportCache.serializer(), value), nowMs()), SupervisorOnline.MAX_SNAPSHOTS,
            )
        }
    }

    /** [userId] limits the list to the reports I sent (the server already limits it to my machines). */
    suspend fun observe(tenantId: String, userId: String?): Flow<List<DailyReportRow>> {
        load(tenantId)
        return combine(cache, db().clientOperationDao().observeByOpTypes(tenantId, ownerSubject(account), listOf(AccountabilityOps.DAILY_REPORT))) { c, ops ->
            merge(c.reports.filter { userId == null || it.submittedBy == null || it.submittedBy == userId }, ops, json)
        }
    }

    /** Refreshes the last [DAYS] days; false when the server could not be read (the saved copy stays). */
    suspend fun refresh(tenantId: String): Boolean {
        load(tenantId)
        return try {
            val from = Instant.ofEpochMilli(nowMs()).atZone(ZoneId.systemDefault()).toLocalDate().minusDays(DAYS)
            save(tenantId, DailyReportCache(nowMs(), api().dailyReports(from = from.toString(), pageSize = PAGE).items))
            true
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            false
        }
    }

    /** The saved report [id], or the server's when it is not saved yet (a notification); null offline. */
    suspend fun report(tenantId: String, id: String): DailyReportDto? {
        load(tenantId)
        cache.value.reports.firstOrNull { it.id == id }?.let { return it }
        return try {
            api().dailyReport(id).also { r -> save(tenantId, cache.value.copy(reports = cache.value.reports + r)) }
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            null
        }
    }

    suspend fun prefill(machineId: String, day: String): DailyReportPrefillDto? = try {
        api().dailyReportPrefill(machineId, day)
    } catch (e: CancellationException) {
        throw e
    } catch (e: Exception) {
        null
    }

    fun reset() {
        loadedFor = null
        cache.value = DailyReportCache()
    }

    companion object {
        const val KEY = "supervisor.daily_reports"
        const val DAYS = 60L
        private const val PAGE = 200

        /** Server copies win (the operation id is the report id); unsent operations are added; newest day first. */
        fun merge(server: List<DailyReportDto>, ops: List<ClientOperationEntity>, json: Json): List<DailyReportRow> {
            val byId = ops.associateBy { it.id }
            val known = server.map { it.id }.toSet()
            val local = ops.filter { it.id !in known }.mapNotNull { op ->
                runCatching { json.decodeFromString(DailyReportPayload.serializer(), op.payloadJson) }.getOrNull()?.let { DailyReportRow(op.id, null, it, op) }
            }
            return (server.map { DailyReportRow(it.id, it, null, byId[it.id]) } + local).sortedByDescending { it.reportDate }
        }
    }
}
