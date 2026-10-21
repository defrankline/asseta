package com.asseta.core.sync.engine

import com.asseta.core.database.AssetaDatabase
import com.asseta.core.database.SyncStateEntity
import com.asseta.core.domain.sync.Backoff
import com.asseta.core.model.sync.DeviceRegisterIn
import com.asseta.core.model.sync.SyncErrorCodes
import com.asseta.core.network.ApiException
import com.asseta.core.network.SyncApi
import com.asseta.core.sync.SyncClock
import com.asseta.core.sync.data.ServerDataWriter
import com.asseta.core.sync.evidence.EvidenceFiles
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.serialization.SerializationException
import kotlinx.serialization.json.Json
import java.io.IOException
import kotlin.random.Random

sealed interface SyncReport {
    data class Success(val pulledPages: Int, val uploaded: Int, val push: PushSummary) : SyncReport

    /** Network down or server 5xx/408/429: nothing lost, retry after [retryAfterMs] (exponential backoff + jitter). */
    data class Retry(val reason: String, val retryAfterMs: Long) : SyncReport

    /** Non-retryable request error (kept in sync state for the status screen); retried on the normal schedule. */
    data class Failed(val code: String, val message: String, val retryAfterMs: Long) : SyncReport

    /** 401: the user must sign in again; local data is kept. */
    data object AuthRequired : SyncReport

    /** DEVICE_REVOKED: local data was wiped. */
    data class Revoked(val message: String) : SyncReport
}

/**
 * One sync run for a tenant: register device (refreshes the offline grant) -> bootstrap (first time) or delta pull by
 * persisted cursor -> evidence upload -> outbox push -> delta pull (server state after our operations).
 * Runs are serialized per process. SENT rows left by a killed process are first returned to PENDING.
 */
class SyncEngine(
    private val api: SyncApi,
    private val db: () -> AssetaDatabase,
    private val files: EvidenceFiles,
    private val deviceId: () -> String,
    private val appVersion: String,
    private val wiper: LocalDataWiper,
    private val clock: SyncClock,
    private val json: Json,
    private val backoff: Backoff = Backoff(),
    private val random: () -> Double = { Random.nextDouble() },
) {
    private val mutex = Mutex()
    private val writer = ServerDataWriter(db, json)
    private val uploader = BlobUploader(api, db, files, json)
    private val pusher = OutboxPusher(api, db, clock, json)

    suspend fun sync(tenantId: String): SyncReport = mutex.withLock {
        try {
            db().clientOperationDao().recoverInFlight()
            register(tenantId)
            var pages = pull(tenantId)
            val uploaded = uploader.uploadPending(tenantId)
            val push = pusher.pushAll(tenantId, state(tenantId).maxBatch ?: DEFAULT_BATCH)
            if (push.sent > 0) pages += pull(tenantId)
            updateState(tenantId) { it.copy(failureStreak = 0, lastError = null, lastSyncAt = clock.nowMs()) }
            SyncReport.Success(pages, uploaded, push)
        } catch (e: ApiException) {
            handleApiError(tenantId, e)
        } catch (e: IOException) {
            retry(tenantId, "NETWORK", "Offline or server unreachable")
        } catch (e: SerializationException) {
            // Unexpected server payload: keep everything local and retry on the normal schedule.
            val streak = recordFailure(tenantId, "BAD_SERVER_RESPONSE")
            SyncReport.Failed("BAD_SERVER_RESPONSE", e.message ?: "Unreadable server response", backoff.delayFor(streak, random()))
        }
    }

    private suspend fun handleApiError(tenantId: String, e: ApiException): SyncReport = when {
        e.code == SyncErrorCodes.DEVICE_REVOKED -> {
            val message = "This device was revoked by your administrator, so its local data was erased. " +
                "Contact your administrator before signing in again."
            wiper.wipe(message)
            SyncReport.Revoked(message)
        }
        e.isUnauthenticated -> SyncReport.AuthRequired
        e.isRetryable -> retry(tenantId, e.code, e.message)
        else -> {
            when (e.code) {
                SyncErrorCodes.DEVICE_NOT_REGISTERED -> updateState(tenantId) { it.copy(deviceSessionId = null) }
                SyncErrorCodes.BATCH_TOO_LARGE ->
                    updateState(tenantId) { it.copy(maxBatch = ((it.maxBatch ?: DEFAULT_BATCH) / 2).coerceAtLeast(1)) }
            }
            val streak = recordFailure(tenantId, e.code)
            SyncReport.Failed(e.code, e.message, backoff.delayFor(streak, random()))
        }
    }

    private suspend fun retry(tenantId: String, code: String, message: String): SyncReport {
        val streak = recordFailure(tenantId, code)
        return SyncReport.Retry("$code: $message", backoff.delayFor(streak, random()))
    }

    private suspend fun recordFailure(tenantId: String, code: String): Int {
        var streak = 0
        updateState(tenantId) { s -> s.copy(failureStreak = s.failureStreak + 1, lastError = code).also { streak = it.failureStreak } }
        return streak
    }

    private suspend fun register(tenantId: String) {
        val session = api.registerDevice(tenantId, DeviceRegisterIn(deviceId(), "ANDROID", appVersion.take(32)))
        writer.applyRegistration(tenantId, session)
    }

    /** Bootstrap when no cursor is stored yet, else page through `/sync/changes` (bounded). Returns pages applied. */
    private suspend fun pull(tenantId: String): Int {
        val cursor = state(tenantId).cursor
        if (cursor == null) {
            val dto = api.bootstrap(tenantId)
            writer.applyBootstrap(tenantId, dto, clock.elapsedRealtimeMs())
            return 1
        }
        var next: Long = cursor
        var pages = 0
        while (pages < MAX_PAGES) {
            val page = api.changes(tenantId, next)
            writer.applyChanges(tenantId, page, clock.elapsedRealtimeMs())
            pages++
            if (!page.hasMore || page.cursor <= next) break
            next = page.cursor
        }
        return pages
    }

    private suspend fun state(tenantId: String): SyncStateEntity =
        db().syncStateDao().get(tenantId) ?: SyncStateEntity(tenantId)

    private suspend fun updateState(tenantId: String, change: (SyncStateEntity) -> SyncStateEntity) {
        val dao = db().syncStateDao()
        dao.put(change(dao.get(tenantId) ?: SyncStateEntity(tenantId)))
    }

    private companion object {
        const val DEFAULT_BATCH = 25
        const val MAX_PAGES = 50
    }
}
