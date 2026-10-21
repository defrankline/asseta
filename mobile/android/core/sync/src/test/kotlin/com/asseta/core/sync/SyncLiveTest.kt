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
import com.asseta.core.domain.finance.ApprovalOutlook
import com.asseta.core.domain.finance.ExpenseDraft
import com.asseta.core.domain.finance.ExpensePolicyDecision
import com.asseta.core.domain.finance.ExpenseRules
import com.asseta.core.domain.finance.PaidFrom
import com.asseta.core.sync.data.FinanceRepository
import com.asseta.core.sync.usecase.CashCollectionRequest
import com.asseta.core.sync.usecase.CashHandoverRequest
import com.asseta.core.sync.usecase.ExpenseRequest
import com.asseta.core.sync.usecase.FinanceCapture
import com.asseta.core.sync.usecase.FinanceResult
import kotlinx.coroutines.flow.first
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
 * Gate 4/5 live E2E: the real sync engine, Retrofit/OkHttp stack, outbox, capture and finance use cases and encrypted
 * evidence files against the running backend + Keycloak (only the database is the in-memory Room variant the engine tests use).
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

    /**
     * Gate 5: an expense with a receipt (paid from custody), a cash collection and a handover recorded offline, synced
     * to ACKED in one run (receipt uploaded first), then verified server-side through the API (expense with the
     * uploaded receipt, custody deltas) and against the custody the device pulled afterwards.
     */
    @Test
    fun offlineExpenseCollectionAndHandoverReachAckedAgainstTheLiveBackend() = runBlocking {
        val tenant = field("tenant_id")
        val token = field("access_token")
        val device = UUID.randomUUID().toString()
        val key = ByteArray(32).also { SecureRandom().nextBytes(it) }
        val files = EncryptedEvidenceStore(tmp.newFolder("evidence-finance"), { key })
        val client = NetworkFactory.okHttpClient({ token }, { tenant }, device = { device })
        val api = NetworkFactory.syncApi(field("api_base"), client, allowCleartext = true)
        val engine = SyncEngine(api, { db }, files, { device }, "live-e2e (android)", LocalDataWiper { }, clock, json)
        val repository = FieldRepository({ db }, json, clock)
        val financeRepo = FinanceRepository({ db }, repository, json, clock)
        val outbox = FieldOutbox({ db }, json, clock)
        val finance = FinanceCapture({ db }, repository, financeRepo, outbox, files, { device }, json)
        fun get(path: String): String {
            val request = Request.Builder().url("${field("api_base").trimEnd('/')}/api/v1/tenant/$path")
                .header(AssetaHeaders.TENANT_ID, tenant).get().build()
            return client.newCall(request).execute().use { r -> r.body.string().also { assertEquals(it, 200, r.code) } }
        }
        fun custody(): JsonObject? = json.parseToJsonElement(get("cash/custody/me")).jsonArray.map { it.jsonObject }
            .firstOrNull { it["currency"]!!.jsonPrimitive.content == financeCurrency }
        fun JsonObject?.money(name: String) = this?.get(name)?.jsonPrimitive?.content?.let(::BigDecimal) ?: BigDecimal.ZERO

        // 1. Bootstrap delivers the category, the job's customer, the custody balance and the EXPENSE_CAPTURE rules.
        success(engine.sync(tenant))
        val categoryId = field("expense_category_id")
        assertTrue("category missing", financeRepo.observeCategories(tenant).first().any { it.id == categoryId })
        assertTrue("customer missing", financeRepo.observeCustomers(tenant).first().any { it.id == field("customer_id") })
        financeCurrency = financeRepo.baseCurrency(tenant) ?: error("custody currency missing from bootstrap")
        val decision = financeRepo.expensePolicy(tenant)
        assertTrue("expense rules not synced: $decision", decision is ExpensePolicyDecision.Allowed)
        val before = custody()

        // 2. Offline: expense with receipt (cash custody), cash collection for the job's customer, handover.
        val now = clock.nowMs()
        val gps = GpsOutcome.Fix(-6.8, 39.28, 8.0, Instant.ofEpochMilli(now - 1_000), "fused")
        val expenseClient = UUID.randomUUID().toString()
        val expenseRequest = ExpenseRequest(
            tenant, expenseClient, categoryId, "Hydraulic hose (live E2E)", "Field Spares", "1500.50", financeCurrency,
            PaidFrom.CASH_CUSTODY, field("machine_id"), null, jpeg(120_000), gps, now,
        )
        val outlook = ExpenseRules.assess(
            ExpenseDraft(categoryId, expenseRequest.description, expenseRequest.supplier, expenseRequest.amountText, financeCurrency,
                PaidFrom.CASH_CUSTODY, field("machine_id"), null, null, true, gps),
            (decision as ExpensePolicyDecision.Allowed).policy, financeCurrency,
        ).approval
        val expense = finance.expense(expenseRequest) as FinanceResult.Saved
        val collection = finance.cashCollection(
            CashCollectionRequest(tenant, UUID.randomUUID().toString(), field("customer_id"), field("job_id"), "250000", financeCurrency,
                "LIVE-${expenseClient.take(8)}", "", now),
        ) as FinanceResult.Saved
        val handover = finance.cashHandover(
            CashHandoverRequest(tenant, UUID.randomUUID().toString(), "100000", financeCurrency, "", "Live E2E handover", now),
        ) as FinanceResult.Saved
        val pendingLine = financeRepo.observeCashView(tenant).first().lines.single { it.currency == financeCurrency }
        assertEquals(0, pendingLine.pendingCollections.compareTo(BigDecimal("250000")))
        assertEquals(0, pendingLine.pendingCashExpenses.compareTo(BigDecimal("1500.50")))

        // 3. One sync: receipt upload completes first, then all three operations are ACKED.
        val report = success(engine.sync(tenant))
        assertEquals(1, report.uploaded)
        listOf(expense, collection, handover).forEach {
            val op = db.clientOperationDao().findById(it.operationId)!!
            assertEquals("${op.opType} ${op.errorCode} ${op.lastError}", ACKED, op.status)
        }
        val expenseOp = db.clientOperationDao().findById(expense.operationId)!!
        val serverAttachment = db.evidenceDao().attachment(expenseOp.attachmentLocalId!!)!!.serverAttachmentId!!
        val expensePayload = json.parseToJsonElement(expenseOp.payloadJson).jsonObject
        assertEquals(1, expensePayload["receipt_upload_ids"]!!.jsonArray.size)
        val replay = api.push(
            tenant,
            PushIn(IsoTime.format(clock.nowMs()), listOf(OperationIn(expenseOp.id, expenseOp.opType, IsoTime.format(expenseOp.createdAtDevice), emptyList(), expensePayload))),
        )
        assertEquals(listOf(expenseOp.id to "DUPLICATE"), replay.results.map { it.id to it.status })

        // 4. Server side: exactly one expense for the client id, with the uploaded receipt and the policy outcome.
        val expenses = json.parseToJsonElement(get("expenses?custodian_staff_id=${field("staff_member_id")}&page_size=100"))
            .jsonObject["items"]!!.jsonArray.map { it.jsonObject }.filter { it["client_id"]?.jsonPrimitive?.content == expenseClient }
        assertEquals(1, expenses.size)
        val row = expenses.single()
        assertEquals(0, BigDecimal("1500.50").compareTo(row["amount"]!!.jsonPrimitive.content.toBigDecimal()))
        assertEquals("CASH_CUSTODY", row["paid_from"]!!.jsonPrimitive.content)
        assertEquals(listOf(serverAttachment), row["receipt_attachment_ids"]!!.jsonArray.map { it.jsonPrimitive.content })
        val approved = outlook == ApprovalOutlook.AutoApproved
        assertEquals(if (approved) "APPROVED" else "PENDING_APPROVAL", row["status"]!!.jsonPrimitive.content)

        // 5. Custody moved by exactly these records: +collection, claimed handover, expense (approved or pending).
        val after = custody()
        val spent = if (approved) BigDecimal("1500.50") else BigDecimal.ZERO
        assertEquals(0, (after.money("outstanding") - before.money("outstanding")).compareTo(BigDecimal("250000") - spent))
        assertEquals(0, (after.money("claimed_unverified_handovers") - before.money("claimed_unverified_handovers")).compareTo(BigDecimal("100000")))
        assertEquals(0, (after.money("pending_spending") - before.money("pending_spending")).compareTo(BigDecimal("1500.50") - spent))
        val local = financeRepo.observeCashView(tenant).first().lines.single { it.currency == financeCurrency }
        assertEquals(0, local.synced!!.outstanding.compareTo(after.money("outstanding"))) // pulled right after the push
        assertTrue(!local.hasPending)
    }

    private var financeCurrency = ""

    private fun success(report: SyncReport): SyncReport.Success {
        assertTrue("expected Success but was $report", report is SyncReport.Success)
        return report as SyncReport.Success
    }

    /** JPEG-framed random bytes (unique per run so the server's content dedupe does not short-circuit the upload). */
    private fun jpeg(size: Int): ByteArray =
        byteArrayOf(0xFF.toByte(), 0xD8.toByte(), 0xFF.toByte(), 0xE0.toByte()) +
            ByteArray(size).also { SecureRandom().nextBytes(it) } + byteArrayOf(0xFF.toByte(), 0xD9.toByte())
}
