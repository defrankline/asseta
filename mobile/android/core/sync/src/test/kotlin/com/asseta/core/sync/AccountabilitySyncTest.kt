package com.asseta.core.sync

import com.asseta.core.domain.accountability.HoursSaleDraft
import com.asseta.core.domain.accountability.AccountabilityMessages
import com.asseta.core.domain.accountability.PaymentLine
import com.asseta.core.domain.accountability.PaymentMethod
import com.asseta.core.domain.capture.GpsOutcome
import com.asseta.core.domain.policy.CaptureMode
import com.asseta.core.domain.policy.ReadingKind
import com.asseta.core.model.ClientOperationStatus.ACKED
import com.asseta.core.model.sync.AccountabilityOps
import com.asseta.core.model.sync.SyncCapabilities
import com.asseta.core.sync.data.FieldOutbox
import com.asseta.core.sync.data.InboxRepository
import com.asseta.core.sync.engine.SyncReport
import com.asseta.core.sync.usecase.AccountabilityCapture
import com.asseta.core.sync.usecase.CaptureRequest
import com.asseta.core.sync.usecase.CaptureResult
import com.asseta.core.sync.usecase.CaptureTarget
import com.asseta.core.sync.usecase.CashAckRequest
import com.asseta.core.sync.usecase.CashTransferRequest
import com.asseta.core.sync.usecase.FinanceResult
import com.asseta.core.sync.usecase.HoursSaleRequest
import com.asseta.core.sync.usecase.HoursTransferRequest
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import java.time.Instant
import java.util.UUID

/** Accountability field operations through the real outbox, blob uploader and engine against [FakeSyncServer]. */
@RunWith(RobolectricTestRunner::class)
class AccountabilitySyncTest : SyncTestBase() {
    private lateinit var accountability: AccountabilityCapture
    private lateinit var inbox: InboxRepository

    @Before
    fun setUp() {
        val outbox = FieldOutbox({ db }, json, clock, { account })
        accountability = AccountabilityCapture({ db }, repository, financeRepository, outbox, files, json)
        inbox = InboxRepository({ db }, json, files, { account })
        fake.capabilities = listOf(
            SyncCapabilities.SUPERVISOR_INBOX_V1, SyncCapabilities.OP_HOURS_PURCHASE, SyncCapabilities.OP_HOURS_TRANSFER_REQUEST,
            SyncCapabilities.OP_CASH_TRANSFER, SyncCapabilities.METER_DAILY_READING, SyncCapabilities.OP_METER_BASELINE,
            SyncCapabilities.OP_METER_CORRECTION,
        )
    }

    private fun synced() = runBlocking { assertTrue(engine().sync(tenant) is SyncReport.Success) }

    private fun saved(r: FinanceResult): FinanceResult.Saved {
        assertTrue("expected Saved but was $r", r is FinanceResult.Saved)
        return r as FinanceResult.Saved
    }

    private fun payload(opId: String): JsonObject = json.parseToJsonElement(op(opId).payloadJson).jsonObject

    private fun sale(walkIn: Boolean = true, evidence: List<ByteArray> = listOf(photo), method: PaymentMethod = PaymentMethod.CASH, reference: String = "") =
        HoursSaleRequest(
            tenant, UUID.randomUUID().toString(),
            HoursSaleDraft(walkIn, if (walkIn) null else fake.customerId, "Walk-in Joe", "0712", fake.machineId, "12.50",
                listOf(PaymentLine(method, "300000", reference)), ""),
            walkInAllowed = true, cashHolderId = null, receivedAtMs = clock.now, paymentEvidence = listOf(evidence),
        )

    @Test
    fun hoursSaleWithEvidenceWaitsForTheUploadAndSendsItsUploadId() = runBlocking {
        synced()
        val opId = saved(accountability.hoursSale(sale())).operationId
        val before = payload(opId)
        assertEquals("12.5", before["hours"]!!.jsonPrimitive.content)
        assertEquals("Walk-in Joe", before["walk_in"]!!.jsonObject["name"]!!.jsonPrimitive.content)
        assertEquals("CASH", before["payment"]!!.jsonObject["method"]!!.jsonPrimitive.content)
        assertTrue(before["evidence_upload_ids"]!!.jsonArray.isEmpty())
        synced()
        assertEquals(ACKED, status(opId))
        val sent = fake.stored[opId]!!.payload
        assertEquals(1, sent["evidence_upload_ids"]!!.jsonArray.size)
        val attachment = db.clientOperationDao().attachmentsOf(opId).single()
        assertEquals(AccountabilityOps.PAYMENT_EVIDENCE, db.evidenceDao().attachment(attachment)!!.purpose)
    }

    private fun split(lines: List<PaymentLine>, clientId: String = UUID.randomUUID().toString(), noncash: Boolean = true, holder: String? = null) =
        HoursSaleRequest(
            tenant, clientId, HoursSaleDraft(false, fake.customerId, "", "", fake.machineId, "6", lines, ""),
            walkInAllowed = false, cashHolderId = holder, receivedAtMs = clock.now, paymentEvidence = emptyList(), noncashAllowed = noncash,
        )

    private fun priced(rate: String = "95000.0000", minorUnits: Int? = 2) {
        fake.capabilities = fake.capabilities.orEmpty() + SyncCapabilities.SYNC_HOURS_PRICES
        fake.inbox = mapOf(
            "hours_prices" to listOf(buildJsonObject {
                put("machine_id", fake.machineId); put("rate_card_id", "e0000000-0000-4000-8000-000000000001"); put("hourly_rate", rate)
                put("minimum_hours", "0"); put("currency", "TZS"); minorUnits?.let { put("minor_units", it) }; put("effective_from", "2026-01-01T00:00:00Z")
            }),
        )
    }

    @Test
    fun splitSaleIsQueuedWithItsPartsInOrderAndRetriesStayExactlyOnce() = runBlocking {
        priced()
        synced()
        val holder = "5f000000-0000-4000-8000-000000000009"
        val clientId = UUID.randomUUID().toString()
        val lines = listOf(
            PaymentLine(PaymentMethod.CASH, "300000", "ignored for cash"),
            PaymentLine(PaymentMethod.BANK, "200000", " CRDB-77 "),
            PaymentLine(PaymentMethod.MOBILE_MONEY, "70000", "MP-1"),
        )
        val opId = saved(accountability.hoursSale(split(lines, clientId, holder = holder))).operationId
        val p = payload(opId)
        assertEquals(clientId, p["client_id"]!!.jsonPrimitive.content)
        assertNull(p["payment"])
        val parts = p["payments"]!!.jsonArray.map { it.jsonObject }
        assertEquals(listOf("CASH", "BANK", "MOBILE_MONEY"), parts.map { it["method"]!!.jsonPrimitive.content })
        assertEquals(listOf("300000", "200000", "70000"), parts.map { it["amount"]!!.jsonPrimitive.content })
        assertEquals(listOf(null, "CRDB-77", "MP-1"), parts.map { it["reference"]?.jsonPrimitive?.content })
        // Cash goes to the named holder's custody; bank and mobile money name no holder.
        assertEquals(listOf(holder, null, null), parts.map { it["staff_member_id"]?.jsonPrimitive?.content })
        assertTrue(parts.all { it["received_at"]!!.jsonPrimitive.content == com.asseta.core.sync.data.IsoTime.format(clock.now) })
        // The same form saved again is the same sale (the server keys the parts uuid5(client_id, "payment"/"payment-n")).
        assertEquals(FinanceResult.AlreadySaved, accountability.hoursSale(split(lines, clientId, holder = holder)))
        synced()
        assertEquals(ACKED, status(opId))
        assertEquals(3, fake.stored[opId]!!.payload["payments"]!!.jsonArray.size)
    }

    @Test
    fun onePaymentTravelsAsPaymentAndNoneAsNotPaid() = runBlocking {
        synced()
        val one = payload(saved(accountability.hoursSale(split(listOf(PaymentLine(PaymentMethod.CASH, "570000", ""))))).operationId)
        assertEquals("570000", one["payment"]!!.jsonObject["amount"]!!.jsonPrimitive.content)
        assertNull(one["payments"])
        val none = payload(saved(accountability.hoursSale(split(emptyList()))).operationId)
        assertNull(none["payment"])
        assertNull(none["payments"])
    }

    @Test
    fun eachSplitPartCarriesItsOwnEvidenceAndTheOpWaitsForEveryUpload() = runBlocking {
        synced()
        val lines = listOf(PaymentLine(PaymentMethod.CASH, "300000", ""), PaymentLine(PaymentMethod.BANK, "200000", "CRDB-77"),
            PaymentLine(PaymentMethod.MOBILE_MONEY, "70000", "MP-1"))
        val request = split(lines).copy(paymentEvidence = listOf(emptyList(), listOf(photo, photo.reversedArray()), listOf(photo + byteArrayOf(9))))
        val opId = saved(accountability.hoursSale(request)).operationId
        // Queued: each part names its photos by local id; the op-level list stays empty; three uploads to wait for.
        val before = payload(opId)["payments"]!!.jsonArray.map { it.jsonObject }
        val local = db.clientOperationDao().attachmentsOf(opId)
        assertEquals(3, local.size)
        assertNull(before[0]["evidence_upload_ids"])
        assertEquals(2, before[1]["evidence_upload_ids"]!!.jsonArray.size)
        assertEquals(1, before[2]["evidence_upload_ids"]!!.jsonArray.size)
        assertEquals(local.toSet(), (before[1]["evidence_upload_ids"]!!.jsonArray + before[2]["evidence_upload_ids"]!!.jsonArray).map { it.jsonPrimitive.content }.toSet())
        assertTrue(payload(opId)["evidence_upload_ids"]!!.jsonArray.isEmpty())
        // Offline nothing is sent; once online every photo uploads first, then the sale goes with the upload ids.
        assertTrue(engine(online = false).sync(tenant) is SyncReport.Retry)
        synced()
        assertEquals(ACKED, status(opId))
        val sent = fake.stored[opId]!!.payload
        val parts = sent["payments"]!!.jsonArray.map { it.jsonObject }
        val uploads = fake.blobs.values.map { it.id }.toSet()
        assertEquals(3, uploads.size)
        assertNull(parts[0]["evidence_upload_ids"])
        val named = (parts[1]["evidence_upload_ids"]!!.jsonArray + parts[2]["evidence_upload_ids"]!!.jsonArray).map { it.jsonPrimitive.content }
        assertEquals(uploads, named.toSet())
        assertTrue(sent["evidence_upload_ids"]!!.jsonArray.isEmpty())
    }

    @Test
    fun partsAboveTheTotalAndNonCashWithoutThePolicyAreRefused() = runBlocking {
        priced()
        synced()
        // 6 h x 95,000 = 570,000.
        val over = accountability.hoursSale(split(listOf(PaymentLine(PaymentMethod.CASH, "300000", ""), PaymentLine(PaymentMethod.CASH, "270000.01", ""))))
        assertEquals(listOf(AccountabilityMessages.paymentsExceed("TZS 570,000")), (over as FinanceResult.Invalid).messages)
        saved(accountability.hoursSale(split(listOf(PaymentLine(PaymentMethod.CASH, "300000", ""), PaymentLine(PaymentMethod.CASH, "270000", "")))))
        val bank = accountability.hoursSale(split(listOf(PaymentLine(PaymentMethod.BANK, "100", "REF")), noncash = false))
        assertEquals(listOf(AccountabilityMessages.NONCASH_OFF), (bank as FinanceResult.Invalid).messages)
    }

    @Test
    fun hoursSaleRulesAndCapability() = runBlocking {
        synced()
        val bank = accountability.hoursSale(sale(walkIn = false, method = PaymentMethod.BANK))
        assertTrue(bank is FinanceResult.Invalid)
        fake.capabilities = listOf(SyncCapabilities.SUPERVISOR_INBOX_V1)
        synced()
        assertTrue(accountability.hoursSale(sale()) is FinanceResult.Blocked)
    }

    @Test
    fun hoursTransferChecksRemainingHours() = runBlocking {
        synced()
        val request = HoursTransferRequest(tenant, UUID.randomUUID().toString(), "p1", fake.machineId, "m2", "5", "3".toBigDecimal(),
            "Machine broke down", null, false)
        assertTrue(accountability.hoursTransfer(request) is FinanceResult.Invalid)
        val opId = saved(accountability.hoursTransfer(request.copy(hoursText = "2.5"))).operationId
        assertEquals("2.5", payload(opId)["hours"]!!.jsonPrimitive.content)
        assertEquals("p1", payload(opId)["purchase_id"]!!.jsonPrimitive.content)
    }

    @Test
    fun cashTransferAndOneAnswerPerTransfer() = runBlocking {
        synced()
        val transfer = CashTransferRequest(tenant, UUID.randomUUID().toString(), null, "s2", "s1", "50000", "tzs", selfAck = false,
            receivedText = "", note = "", transferredAtMs = clock.now)
        val opId = saved(accountability.cashTransfer(transfer)).operationId
        val p = payload(opId)
        assertEquals("TZS", p["currency"]!!.jsonPrimitive.content)
        assertNull(p["from_staff_id"]) // the recorder: the server uses the caller's staff record
        assertNull(p["amount_received"])
        val ack = CashAckRequest(tenant, "t1", isFloat = false, acknowledge = true, receivedText = "45000", note = "")
        val ackOp = saved(accountability.acknowledge(ack)).operationId
        assertEquals("45000", payload(ackOp)["amount_received"]!!.jsonPrimitive.content)
        assertEquals(FinanceResult.AlreadySaved, accountability.acknowledge(ack.copy(acknowledge = false, note = "Nothing came")))
        assertTrue(accountability.answered(tenant, "t1", isFloat = false))
        assertTrue(accountability.acknowledge(CashAckRequest(tenant, "f1", true, false, "", "")) is FinanceResult.Invalid) // dispute needs a reason
        synced()
        assertEquals(ACKED, status(opId))
        assertEquals(ACKED, status(ackOp))
    }

    private fun fix() = GpsOutcome.Fix(-6.8, 39.28, 8.0, Instant.ofEpochMilli(clock.now), "fused")

    private fun manual(target: CaptureTarget, reading: String = "1500.0") = CaptureRequest(
        tenant, null, UUID.randomUUID().toString(), ReadingKind.DAILY, CaptureMode.MANUAL, reading, photo, 0, null, fix(), clock.now, target,
    )

    @Test
    fun dailyReadingOutsideAJobNamesTheMachineAndShowsInReadings() = runBlocking {
        synced()
        val result = capture(manual(CaptureTarget.Daily(fake.machineId)))
        assertTrue("$result", result is CaptureResult.Saved)
        val opId = (result as CaptureResult.Saved).operationId
        val p = payload(opId)
        assertFalse("job_id" in p)
        assertEquals(fake.machineId, p["machine_id"]!!.jsonPrimitive.content)
        assertEquals("DAILY", p["kind"]!!.jsonPrimitive.content)
        val reading = inbox.observe(tenant).first().readings.single()
        assertNull(reading.jobId)
        assertEquals(fake.machineId, reading.machineId)
        synced()
        assertEquals(ACKED, status(opId))
        assertTrue(fake.stored[opId]!!.payload["photo_attachment_id"] != null)
    }

    @Test
    fun baselineSendsItsPhotoAttachment() = runBlocking {
        synced()
        val result = capture(manual(CaptureTarget.Baseline(fake.machineId, "New machine")))
        val opId = (result as CaptureResult.Saved).operationId
        assertEquals(AccountabilityOps.METER_BASELINE, op(opId).opType)
        synced()
        val sent = fake.stored[opId]!!.payload
        assertTrue(sent["photo_attachment_id"] != null)
        assertEquals("New machine", sent["note"]!!.jsonPrimitive.content)
    }

    private fun serverDaily(id: String, state: String = "ACCEPTED") = buildJsonObject {
        put("id", id); put("job_id", JsonNull); put("machine_id", fake.machineId); put("kind", "DAILY"); put("capture_mode", "MANUAL")
        put("reading", "1400.0"); put("state", state); put("gps_status", "FIX"); put("manually_corrected", false); put("policy_version", "p")
        put("captured_at", "2026-10-21T07:00:00Z"); put("received_at", "2026-10-21T07:01:00Z"); put("sync_revision", 3)
    }

    @Test
    fun pulledDailyReadingWithNullJobAndItsCorrection() = runBlocking {
        val readingId = UUID.randomUUID().toString()
        fake.inbox = mapOf("my_meter_captures" to listOf(serverDaily(readingId)))
        synced()
        val pulled = inbox.observe(tenant).first().readings.single()
        assertNull(pulled.jobId)
        assertEquals("1400.0", inbox.readingValue(tenant, readingId))
        val short = capture(manual(CaptureTarget.Correction(readingId, "typo")))
        assertTrue(short is CaptureResult.Blocked) // reason of at least 10 characters
        val result = capture(manual(CaptureTarget.Correction(readingId, "Typed 1400 instead of 1450"), reading = "1450.0"))
        val opId = (result as CaptureResult.Saved).operationId
        synced()
        val sent = fake.stored[opId]!!.payload
        assertEquals(readingId, sent["superseded_capture_id"]!!.jsonPrimitive.content)
        val replacement = sent["replacement"]!!.jsonObject
        assertEquals("1450.0", replacement["reading"]!!.jsonPrimitive.content)
        assertEquals("DAILY", replacement["kind"]!!.jsonPrimitive.content)
        assertTrue(replacement["photo_attachment_id"] != null)
    }

    @Test
    fun withoutTheCapabilityDailyReadingsAreRefused() = runBlocking {
        fake.capabilities = listOf(SyncCapabilities.SUPERVISOR_INBOX_V1)
        synced()
        val result = capture(manual(CaptureTarget.Daily(fake.machineId)))
        assertTrue(result is CaptureResult.Blocked)
    }
}
