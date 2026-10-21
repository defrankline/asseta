package com.asseta.core.sync

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import com.asseta.core.database.AssetaDatabase
import com.asseta.core.database.AttachmentEntity
import com.asseta.core.domain.capture.GpsOutcome
import com.asseta.core.domain.ocr.OcrReading
import com.asseta.core.domain.policy.CaptureMode
import com.asseta.core.domain.policy.CapturePolicyDecision
import com.asseta.core.domain.policy.ReadingKind
import com.asseta.core.model.ClientOperationStatus.ACKED
import com.asseta.core.model.ClientOperationStatus.PENDING
import com.asseta.core.model.sync.OperationIn
import com.asseta.core.model.sync.PushIn
import com.asseta.core.network.AssetaHeaders
import com.asseta.core.network.NetworkFactory
import com.asseta.core.sync.data.FieldOutbox
import com.asseta.core.sync.data.FieldRepository
import com.asseta.core.sync.data.IsoTime
import com.asseta.core.sync.engine.LocalDataWiper
import com.asseta.core.sync.engine.SyncEngine
import com.asseta.core.sync.engine.SyncReport
import com.asseta.core.sync.evidence.EncryptedEvidenceStore
import com.asseta.core.sync.usecase.CaptureMeterReading
import com.asseta.core.sync.usecase.CaptureRequest
import com.asseta.core.sync.usecase.CaptureResult
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.Request
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import java.io.File
import java.math.BigDecimal
import java.security.SecureRandom
import java.time.Instant
import java.util.UUID

/**
 * Gate 4 live E2E: the real sync engine, Retrofit/OkHttp stack, outbox, capture use case and encrypted evidence files
 * against the running backend + Keycloak (only the database is the in-memory Room variant the engine tests use).
 * Skipped unless `ASSETA_LIVE_E2E` names a fixture written by backend/scripts/field_e2e_setup.py (see
 * scripts/field-e2e.sh), so it never runs in normal builds or CI.
 */
@RunWith(RobolectricTestRunner::class)
class SyncLiveTest {
    @get:Rule val tmp = TemporaryFolder()

    private val json = NetworkFactory.json
    private lateinit var fixture: JsonObject
    private lateinit var db: AssetaDatabase

    private fun field(name: String): String = fixture[name]!!.jsonPrimitive.content

    /** Real time on both clocks (Robolectric's SystemClock is frozen). */
    private val clock = object : SyncClock {
        override fun nowMs() = System.currentTimeMillis()
        override fun elapsedRealtimeMs() = System.nanoTime() / 1_000_000
    }

    @Before
    fun setUp() {
        val path = System.getenv("ASSETA_LIVE_E2E") ?: System.getProperty("ASSETA_LIVE_E2E")
        assumeTrue("set ASSETA_LIVE_E2E to a field_e2e_setup.py fixture file", !path.isNullOrBlank())
        fixture = json.parseToJsonElement(File(path!!).readText()).jsonObject
        val expires = IsoTime.parse(field("token_expires_at"))
        assertTrue("supervisor token expired: re-run field_e2e_setup.py", expires.isAfter(Instant.now().plusSeconds(30)))
        val context = ApplicationProvider.getApplicationContext<Context>()
        db = Room.inMemoryDatabaseBuilder(context, AssetaDatabase::class.java).allowMainThreadQueries().build()
    }

    @After
    fun tearDown() {
        if (::db.isInitialized) db.close()
    }

    @Test
    fun openingCaptureWithPhotoSyncsExactlyOnceAgainstTheLiveBackend() = runBlocking {
        val tenant = field("tenant_id")
        val jobId = field("job_id")
        val machineId = field("machine_id")
        val token = field("access_token")
        val device = UUID.randomUUID().toString()
        val key = ByteArray(32).also { SecureRandom().nextBytes(it) }
        val files = EncryptedEvidenceStore(tmp.newFolder("evidence"), { key })
        val client = NetworkFactory.okHttpClient({ token }, { tenant }, device = { device })
        val api = NetworkFactory.syncApi(field("api_base"), client, allowCleartext = true)
        val wipes = mutableListOf<String>()
        val engine = SyncEngine(
            api = api, db = { db }, files = files, deviceId = { device }, appVersion = "live-e2e (android)",
            wiper = LocalDataWiper { wipes += it }, clock = clock, json = json,
        )
        val repository = FieldRepository({ db }, json, clock)
        val capture = CaptureMeterReading({ db }, repository, FieldOutbox({ db }, json, clock), files, { device }, json)

        // 1. First sync: registers the device and bootstraps the supervisor's jobs + capture policy.
        success(engine.sync(tenant))
        val job = db.fieldDataDao().job(jobId)
        assertNotNull("assigned job missing from bootstrap", job)
        assertEquals("APPROVED", job!!.status)
        assertEquals(machineId, job.machineId)

        // 2. Opening capture as the capture screen records it: policy-decided mode, photo, fresh GPS fix.
        val decision = repository.capturePolicy(tenant, machineId)
        assertTrue("capture blocked by the synced policy gate: $decision", decision is CapturePolicyDecision.Allowed)
        val mode = (decision as CapturePolicyDecision.Allowed).policy.requiredMode(ReadingKind.OPENING)
        val ocr = if (mode == CaptureMode.AUTOMATIC) OcrReading("1234.5", 0.99, "1234.5", "OK", emptySet()) else null
        val now = clock.nowMs()
        val captureId = UUID.randomUUID().toString()
        val result = capture(
            CaptureRequest(
                tenant, jobId, captureId, ReadingKind.OPENING, mode, "1234.5", jpeg(300_000), if (ocr == null) 0 else 1,
                ocr, GpsOutcome.Fix(-6.8, 39.28, 8.0, Instant.ofEpochMilli(now - 2_000), "fused"), now,
            ),
        )
        assertTrue("expected Saved but was $result", result is CaptureResult.Saved)
        val opId = (result as CaptureResult.Saved).operationId
        assertEquals(PENDING, db.clientOperationDao().findById(opId)!!.status)

        // 3. Sync: the photo uploads (resumable blob API) before the capture is pushed and ACKED.
        val second = success(engine.sync(tenant))
        assertEquals(1, second.uploaded)
        assertEquals(1, second.push.acked)
        val acked = db.clientOperationDao().findById(opId)!!
        assertEquals("operation ${acked.errorCode} ${acked.lastError}", ACKED, acked.status)
        val attachment = db.evidenceDao().attachment(acked.attachmentLocalId!!)!!
        assertEquals(AttachmentEntity.COMPLETE, attachment.status)
        val serverAttachment = attachment.serverAttachmentId!!
        val payload = json.parseToJsonElement(acked.payloadJson).jsonObject
        assertEquals(serverAttachment, payload["photo_attachment_id"]!!.jsonPrimitive.content)

        // 4. Replay of the same client operation id (lost response): DUPLICATE, no second effect.
        val replay = api.push(
            tenant,
            PushIn(IsoTime.format(clock.nowMs()), listOf(OperationIn(acked.id, acked.opType, IsoTime.format(acked.createdAtDevice), emptyList(), payload))),
        )
        assertEquals(listOf(acked.id to "DUPLICATE"), replay.results.map { it.id to it.status })
        assertEquals(0, success(engine.sync(tenant)).push.sent) // nothing left to send
        assertTrue(wipes.isEmpty())

        // 5. Server side: exactly one opening reading, with the uploaded photo.
        val request = Request.Builder().url("${field("api_base").trimEnd('/')}/api/v1/tenant/jobs/$jobId/meter-captures")
            .header(AssetaHeaders.TENANT_ID, tenant).get().build()
        val body = client.newCall(request).execute().use { it.body.string() }
        val rows = json.parseToJsonElement(body).jsonArray
        assertEquals(1, rows.size)
        val row = rows.single().jsonObject
        fun text(name: String) = row[name]!!.jsonPrimitive.content
        assertEquals(captureId, text("id"))
        assertEquals("OPENING", text("kind"))
        assertEquals(0, BigDecimal("1234.5").compareTo(BigDecimal(text("reading"))))
        assertEquals(mode.name, text("capture_mode"))
        assertEquals(serverAttachment, text("photo_attachment_id"))
        assertEquals("FIX", text("gps_status"))
    }

    private fun success(report: SyncReport): SyncReport.Success {
        assertTrue("expected Success but was $report", report is SyncReport.Success)
        return report as SyncReport.Success
    }

    /** JPEG-framed random bytes (unique per run so the server's content dedupe does not short-circuit the upload). */
    private fun jpeg(size: Int): ByteArray =
        byteArrayOf(0xFF.toByte(), 0xD8.toByte(), 0xFF.toByte(), 0xE0.toByte()) +
            ByteArray(size).also { SecureRandom().nextBytes(it) } + byteArrayOf(0xFF.toByte(), 0xD9.toByte())
}
