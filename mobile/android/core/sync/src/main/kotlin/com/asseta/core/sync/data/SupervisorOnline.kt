package com.asseta.core.sync.data

import com.asseta.core.database.AssetaDatabase
import com.asseta.core.database.ReadSnapshotEntity
import com.asseta.core.model.SyncAccount
import com.asseta.core.model.owner.NotificationDto
import com.asseta.core.model.owner.NotificationMarkReadIn
import com.asseta.core.model.sync.CashReconciliationDto
import com.asseta.core.network.TenantApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.Json
import java.time.Instant
import java.time.ZoneId

/** Result of an online read: fresh from the server, the cached copy (offline or failed), or nothing at all. */
sealed interface OnlineResult<out T> {
    data class Fresh<T>(val value: T) : OnlineResult<T>
    data class Cached<T>(val value: T, val fetchedAtMs: Long) : OnlineResult<T>
    data class Unavailable(val message: String) : OnlineResult<Nothing>
}

/**
 * The Supervisor's optional online reads: server notifications (EXPENSE_DECIDED, CASH_NOT_HANDED_OVER,
 * JOB_MISSING_READINGS, ...) cached in the encrypted store for offline viewing, and today's cash reconciliation. Both
 * are conveniences on top of sync: the app works fully without them.
 */
class SupervisorOnline(
    private val api: () -> TenantApi,
    private val db: () -> AssetaDatabase,
    private val json: Json,
    private val account: () -> SyncAccount?,
    private val nowMs: () -> Long = System::currentTimeMillis,
) {
    private val notifications = MutableStateFlow<List<NotificationDto>>(emptyList())
    private var loadedFor: String? = null

    /** The cached notifications of the signed-in user (newest first); [loadCached] fills it after a restart. */
    val inbox: StateFlow<List<NotificationDto>> = notifications.asStateFlow()

    private fun scope(tenantId: String) = "$tenantId|${ownerSubject(account)}"

    suspend fun loadCached(tenantId: String) {
        if (loadedFor == scope(tenantId)) return
        loadedFor = scope(tenantId)
        notifications.value = cached(tenantId)?.first.orEmpty()
    }

    private suspend fun cached(tenantId: String): Pair<List<NotificationDto>, Long>? {
        val row = db().readSnapshotDao().get(tenantId, NOTIFICATIONS_KEY) ?: return null
        val list = runCatching { json.decodeFromString(ListSerializer(NotificationDto.serializer()), row.payloadJson) }.getOrNull() ?: return null
        return list to row.fetchedAt
    }

    /** Fetches the newest notifications (falls back to the cached list when offline). */
    suspend fun refreshNotifications(tenantId: String): OnlineResult<List<NotificationDto>> = try {
        val page = api().notifications(page = 1, pageSize = PAGE).items
        store(tenantId, page)
        OnlineResult.Fresh(page)
    } catch (e: kotlinx.coroutines.CancellationException) {
        throw e
    } catch (e: Exception) {
        loadCached(tenantId)
        cached(tenantId)?.let { OnlineResult.Cached(it.first, it.second) } ?: OnlineResult.Unavailable(e.message ?: "Offline")
    }

    /** Marks notifications read on the server, and locally right away (kept read in the cache when offline). */
    suspend fun markRead(tenantId: String, ids: List<String>) {
        if (ids.isEmpty()) return
        val now = Instant.ofEpochMilli(nowMs()).toString()
        store(tenantId, notifications.value.map { if (it.id.toString() in ids && it.readAt == null) it.copy(readAt = now) else it })
        runCatching { api().markRead(NotificationMarkReadIn(ids)) }
    }

    suspend fun markAllRead(tenantId: String) {
        val now = Instant.ofEpochMilli(nowMs()).toString()
        store(tenantId, notifications.value.map { if (it.readAt == null) it.copy(readAt = now) else it })
        runCatching { api().markAllRead() }
    }

    private suspend fun store(tenantId: String, list: List<NotificationDto>) {
        loadedFor = scope(tenantId)
        notifications.value = list
        db().readSnapshotDao().putBounded(
            ReadSnapshotEntity(tenantId, NOTIFICATIONS_KEY, json.encodeToString(ListSerializer(NotificationDto.serializer()), list), nowMs()),
            MAX_SNAPSHOTS,
        )
    }

    /** Clears the in-memory list (sign-out / another user); the store is cleared by the account switch. */
    fun reset() {
        loadedFor = null
        notifications.value = emptyList()
    }

    /** Today's reconciliation per currency from the server (online only; null when offline or refused). */
    suspend fun todayReconciliation(currencies: List<String>, zone: ZoneId = ZoneId.systemDefault()): List<CashReconciliationDto>? = runCatching {
        val today = Instant.ofEpochMilli(nowMs()).atZone(zone).toLocalDate().toString()
        if (currencies.isEmpty()) api().myCashReconciliation(today, null)
        else currencies.flatMap { api().myCashReconciliation(today, it) }
    }.getOrNull()

    /** A short-lived URL of a server attachment (meter photo, signature, reset evidence), when online and allowed. */
    suspend fun attachmentUrl(attachmentId: String): String? = runCatching { api().attachmentUrl(attachmentId).url }.getOrNull()

    /** A short-lived URL of an expense receipt, when online and allowed. */
    suspend fun receiptUrl(expenseId: String, attachmentId: String): String? = runCatching { api().receiptUrl(expenseId, attachmentId).url }.getOrNull()

    companion object {
        const val NOTIFICATIONS_KEY = "supervisor.notifications"
        const val PAGE = 50
        const val MAX_SNAPSHOTS = 20
    }
}
