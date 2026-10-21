package com.asseta.core.sync

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import com.asseta.core.database.AssetaDatabase
import com.asseta.core.database.ClientOperationEntity
import com.asseta.core.domain.capture.GpsOutcome
import com.asseta.core.domain.ocr.OcrReading
import com.asseta.core.domain.policy.CaptureMode
import com.asseta.core.domain.policy.ReadingKind
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.network.NetworkFactory
import com.asseta.core.sync.data.FieldOutbox
import com.asseta.core.sync.data.FieldRepository
import com.asseta.core.sync.data.FinanceRepository
import com.asseta.core.sync.engine.LocalDataWiper
import com.asseta.core.sync.engine.SyncEngine
import com.asseta.core.sync.evidence.EncryptedEvidenceStore
import com.asseta.core.sync.usecase.CaptureMeterReading
import com.asseta.core.sync.usecase.CaptureRequest
import com.asseta.core.sync.usecase.CaptureResult
import com.asseta.core.sync.usecase.FinanceCapture
import com.asseta.core.sync.usecase.JobWorkflow
import kotlinx.coroutines.runBlocking
import mockwebserver3.MockWebServer
import org.junit.After
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.rules.TemporaryFolder
import java.time.Instant
import java.util.UUID

class FakeClock(var now: Long, var elapsed: Long) : SyncClock {
    override fun nowMs() = now
    override fun elapsedRealtimeMs() = elapsed
    fun advance(ms: Long) { now += ms; elapsed += ms }
}

/** Real engine + Room (Robolectric SQLite) + encrypted evidence files against [FakeSyncServer] over HTTP. */
abstract class SyncTestBase {
    @get:Rule val tmp = TemporaryFolder()

    protected val tenant = "a3c1d1f2-1111-4222-8333-944455556666"
    protected val clock = FakeClock(Instant.parse("2026-10-21T08:00:00Z").toEpochMilli(), 5_000_000L)
    protected val fake = FakeSyncServer { Instant.ofEpochMilli(clock.now) }
    protected val server = MockWebServer()
    protected val json = NetworkFactory.json
    protected lateinit var db: AssetaDatabase
    protected lateinit var files: EncryptedEvidenceStore
    protected val wipes = mutableListOf<String>()
    protected lateinit var repository: FieldRepository
    protected lateinit var capture: CaptureMeterReading
    protected lateinit var workflow: JobWorkflow
    protected lateinit var financeRepository: FinanceRepository
    protected lateinit var finance: FinanceCapture
    protected val photo = ByteArray(10) { (it * 7 + 1).toByte() } // 3 chunks of 4 bytes
    private val key = ByteArray(32) { it.toByte() }

    @Before
    fun setUpBase() {
        server.dispatcher = fake
        server.start()
        val context = ApplicationProvider.getApplicationContext<Context>()
        db = Room.inMemoryDatabaseBuilder(context, AssetaDatabase::class.java).allowMainThreadQueries().build()
        files = EncryptedEvidenceStore(tmp.newFolder("evidence"), { key })
        repository = FieldRepository({ db }, json, clock)
        val outbox = FieldOutbox({ db }, json, clock)
        capture = CaptureMeterReading({ db }, repository, outbox, files, { DEVICE }, json)
        workflow = JobWorkflow({ db }, repository, outbox, files, { DEVICE }, clock, json)
        financeRepository = FinanceRepository({ db }, repository, json, clock)
        finance = FinanceCapture({ db }, repository, financeRepository, outbox, files, { DEVICE }, json)
    }

    @After
    fun tearDownBase() {
        db.close()
        server.close()
    }

    protected fun engine(online: Boolean = true): SyncEngine {
        val client = NetworkFactory.okHttpClient({ "token" }, { null }, device = { DEVICE })
        val base = if (online) server.url("/").toString() else "http://127.0.0.1:1/"
        return SyncEngine(
            api = NetworkFactory.syncApi(base, client, allowCleartext = true),
            db = { db }, files = files, deviceId = { DEVICE }, appVersion = "0.1.0-test",
            wiper = LocalDataWiper { wipes += it }, clock = clock, json = json, random = { 0.5 },
        )
    }

    protected fun captureRequest(
        kind: ReadingKind = ReadingKind.OPENING,
        mode: CaptureMode = CaptureMode.AUTOMATIC,
        reading: String = "1234.5",
        photoBytes: ByteArray? = photo,
        ocr: OcrReading? = OcrReading("1234.5", 0.95, "1234.5 HRS", "OK", emptySet()),
        gps: GpsOutcome? = GpsOutcome.Fix(-15.4, 28.3, 8.0, Instant.ofEpochMilli(clock.now), "fused"),
        attempts: Int = 1,
    ) = CaptureRequest(tenant, fake.jobId, UUID.randomUUID().toString(), kind, mode, reading, photoBytes,
        if (ocr == null) 0 else attempts, ocr, gps, clock.now)

    protected fun saved(result: CaptureResult): CaptureResult.Saved {
        assertTrue("expected Saved but was $result", result is CaptureResult.Saved)
        return result as CaptureResult.Saved
    }

    protected fun op(id: String): ClientOperationEntity = runBlocking { db.clientOperationDao().findById(id)!! }

    protected fun status(id: String): ClientOperationStatus = op(id).status

    protected companion object {
        const val DEVICE = "0f6a3b4c-5d6e-4f70-8a9b-0c1d2e3f4a5b"
    }
}
