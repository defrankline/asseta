package com.asseta.supervisor

import android.content.Context
import com.asseta.core.network.NetworkFactory
import com.asseta.core.sync.SystemSyncClock
import com.asseta.core.sync.data.FieldOutbox
import com.asseta.core.sync.data.FieldRepository
import com.asseta.core.sync.engine.DeviceWipe
import com.asseta.core.sync.engine.SyncEngine
import com.asseta.core.sync.evidence.EncryptedEvidenceStore
import com.asseta.core.sync.usecase.CaptureMeterReading
import com.asseta.core.sync.usecase.JobWorkflow
import com.asseta.core.sync.work.SyncScheduler
import com.asseta.core.ui.AssetaAppContainer
import com.asseta.supervisor.capture.GpsLocator
import com.asseta.supervisor.capture.MeterOcr
import java.io.File

/**
 * Supervisor field-app graph on top of the shared container (manual DI). Every database access goes through
 * `container.database` lazily so the revocation wipe can close and delete the database safely.
 */
class FieldGraph(context: Context, val container: AssetaAppContainer) {
    private val appContext = context.applicationContext
    private val json = NetworkFactory.json
    private val db = { container.database }
    val clock = SystemSyncClock

    val deviceId: String by lazy { container.security.deviceIdStore.getOrCreate() }

    val evidence = EncryptedEvidenceStore(
        directory = File(appContext.noBackupFilesDir, "evidence"),
        key = { container.security.evidenceKey.getOrCreate() },
    )

    val scheduler = SyncScheduler(appContext)

    private val syncApi by lazy {
        val client = NetworkFactory.okHttpClient(container.authManager, container.tenantStore, device = { deviceId })
        NetworkFactory.defaultSyncApi(client)
    }

    private val wiper = DeviceWipe(
        listOf(
            { _ -> scheduler.cancelAll() },
            { _ -> container.databaseHolder.closeAndDelete() },
            { _ -> evidence.wipeAll() },
            { _ -> appContext.cacheDir.listFiles()?.forEach { it.deleteRecursively() } },
            { _ -> container.security.wipeLocalSecrets() },
            { _ -> container.authManager.logout() },
            { _ -> container.tenantStore.clear() },
            { reason -> container.sessionNotice.post(reason) },
        ),
    )

    val engine: SyncEngine by lazy {
        SyncEngine(syncApi, db, evidence, { deviceId }, BuildConfig.VERSION_NAME, wiper, clock, json)
    }

    val repository = FieldRepository(db, json, clock)
    private val outbox = FieldOutbox(db, json, clock)

    val captureReading = CaptureMeterReading(db, repository, outbox, evidence, { deviceId }, json) { scheduler.syncNow() }
    val workflow = JobWorkflow(db, repository, outbox, evidence, { deviceId }, clock, json) { scheduler.syncNow() }

    val ocr by lazy { MeterOcr(appContext) }
    val gps by lazy { GpsLocator(appContext) }
}
