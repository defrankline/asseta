package com.asseta.supervisor

import android.content.Context
import com.asseta.core.network.NetworkFactory
import com.asseta.core.sync.SystemSyncClock
import com.asseta.core.sync.data.FieldOutbox
import com.asseta.core.sync.data.FieldRepository
import com.asseta.core.sync.data.FinanceRepository
import com.asseta.core.sync.data.InboxRepository
import com.asseta.core.sync.data.SupervisorOnline
import com.asseta.core.sync.engine.AccountSwitch
import com.asseta.core.sync.engine.DeviceWipe
import com.asseta.core.sync.engine.SyncEngine
import com.asseta.core.sync.evidence.EncryptedEvidenceStore
import com.asseta.core.sync.usecase.CaptureMeterReading
import com.asseta.core.sync.usecase.FinanceCapture
import com.asseta.core.sync.usecase.JobWorkflow
import com.asseta.core.sync.usecase.RequestMeterReset
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

    /** The signed-in user: owner of the field data this phone records and syncs (null when signed out). */
    private val account = { container.authManager.account() }

    /** Resets field data another user synced on this phone when a different user signs in (see [AccountSwitch]). */
    val accounts = AccountSwitch(db)

    private val syncApi by lazy {
        val client = NetworkFactory.okHttpClient(container.authManager, container.tenantStore, device = { deviceId })
        NetworkFactory.defaultSyncApi(client)
    }

    /** Online-only tenant reads (notifications, reconciliation, evidence URLs); the selected tenant's header. */
    private val tenantApi by lazy {
        NetworkFactory.defaultTenantApi(NetworkFactory.okHttpClient(container.authManager, container.tenantStore))
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
        SyncEngine(syncApi, db, evidence, { deviceId }, BuildConfig.VERSION_NAME, wiper, clock, json, account)
    }

    val repository = FieldRepository(db, json, clock, account)
    private val outbox = FieldOutbox(db, json, clock, account)

    val captureReading = CaptureMeterReading(db, repository, outbox, evidence, { deviceId }, json) { scheduler.syncNow() }
    val workflow = JobWorkflow(db, repository, outbox, evidence, { deviceId }, clock, json) { scheduler.syncNow() }
    val financeRepository = FinanceRepository(db, repository, json, clock)
    val finance = FinanceCapture(db, repository, financeRepository, outbox, evidence, { deviceId }, json) { scheduler.syncNow() }

    /** The supervisor's own records (server copies merged with this phone's) behind every tab. */
    val inbox = InboxRepository(db, json, evidence, account)
    val online = SupervisorOnline({ tenantApi }, db, json, account)
    val meterReset = RequestMeterReset(db, repository, outbox, evidence, json) { scheduler.syncNow() }

    val ocr by lazy { MeterOcr(appContext) }
    val gps by lazy { GpsLocator(appContext) }
}
