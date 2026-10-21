package com.asseta.core.sync.work

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.asseta.core.sync.engine.SyncReport
import java.util.concurrent.TimeUnit

/** Implemented by the Application: gives background work access to the process-wide sync graph. */
interface SyncHost {
    /** Tenant to sync, or null when signed out / no tenant selected (then the worker does nothing). */
    fun syncTenantId(): String?
    suspend fun runSync(tenantId: String): SyncReport
}

/**
 * Background sync (WorkManager survives process death and reboots; requires a network connection). Retryable failures
 * schedule a follow-up run with exponential backoff + jitter computed from the persisted failure streak.
 */
class SyncWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {
    override suspend fun doWork(): Result {
        val host = applicationContext as? SyncHost ?: return Result.failure()
        val tenantId = host.syncTenantId() ?: return Result.success()
        when (val report = host.runSync(tenantId)) {
            is SyncReport.Retry -> SyncScheduler(applicationContext).scheduleRetry(report.retryAfterMs)
            is SyncReport.Failed -> SyncScheduler(applicationContext).scheduleRetry(report.retryAfterMs)
            is SyncReport.Revoked -> SyncScheduler(applicationContext).cancelAll()
            is SyncReport.Success, SyncReport.AuthRequired -> Unit
        }
        return Result.success()
    }
}

class SyncScheduler(context: Context) {
    private val work = WorkManager.getInstance(context.applicationContext)
    private val online = Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()

    /** Sync as soon as a network is available (after a capture, on app start, or "Sync now"). */
    fun syncNow() {
        val request = OneTimeWorkRequestBuilder<SyncWorker>()
            .setConstraints(online)
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, MIN_BACKOFF_S, TimeUnit.SECONDS)
            .build()
        work.enqueueUniqueWork(NOW, ExistingWorkPolicy.APPEND_OR_REPLACE, request)
    }

    fun scheduleRetry(delayMs: Long) {
        val request = OneTimeWorkRequestBuilder<SyncWorker>()
            .setConstraints(online)
            .setInitialDelay(delayMs.coerceAtLeast(0), TimeUnit.MILLISECONDS)
            .build()
        work.enqueueUniqueWork(RETRY, ExistingWorkPolicy.REPLACE, request)
    }

    /** Periodic delta pull + push while the app is installed (15 min is the OS minimum). */
    fun ensurePeriodic() {
        val request = PeriodicWorkRequestBuilder<SyncWorker>(PERIOD_MIN, TimeUnit.MINUTES).setConstraints(online).build()
        work.enqueueUniquePeriodicWork(PERIODIC, ExistingPeriodicWorkPolicy.KEEP, request)
    }

    fun cancelAll() {
        listOf(NOW, RETRY, PERIODIC).forEach(work::cancelUniqueWork)
    }

    private companion object {
        const val NOW = "asseta-sync-now"
        const val RETRY = "asseta-sync-retry"
        const val PERIODIC = "asseta-sync-periodic"
        const val PERIOD_MIN = 15L
        const val MIN_BACKOFF_S = 30L
    }
}
