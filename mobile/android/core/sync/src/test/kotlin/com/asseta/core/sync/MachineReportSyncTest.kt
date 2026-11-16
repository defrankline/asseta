package com.asseta.core.sync

import com.asseta.core.domain.accountability.PaymentMethod
import com.asseta.core.domain.capture.GpsOutcome
import com.asseta.core.domain.policy.CaptureMode
import com.asseta.core.domain.reports.MachineReportMessages
import com.asseta.core.domain.reports.ReportLineDraft
import com.asseta.core.domain.reports.ReportState
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.model.sync.MachineReportOps
import com.asseta.core.model.sync.OpTypes
import com.asseta.core.model.sync.SyncCapabilities
import com.asseta.core.sync.data.FieldOutbox
import com.asseta.core.sync.data.MachineReportData
import com.asseta.core.sync.engine.SyncReport
import com.asseta.core.sync.usecase.CaptureMeterReading
import com.asseta.core.sync.usecase.FinanceResult
import com.asseta.core.sync.usecase.InvoicePaymentRequest
import com.asseta.core.sync.usecase.MachineReportCapture
import com.asseta.core.sync.usecase.MachineReportRequest
import com.asseta.core.sync.usecase.ReportReading
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import java.math.BigDecimal
import java.time.Instant
import java.util.UUID

/** ADR-008 offline machine reports and credit-invoice payments: snapshots, checks before queueing, payloads, uploads. */
@RunWith(RobolectricTestRunner::class)
class MachineReportSyncTest : SyncTestBase() {
    private lateinit var reports: MachineReportCapture
    private lateinit var data: MachineReportData
    private val reasonId = "70000000-0000-4000-8000-000000000001"
    private val invoiceId = "71000000-0000-4000-8000-000000000001"

    @Before
    fun setUp() {
        val outbox = FieldOutbox({ db }, json, clock, { account })
        reports = MachineReportCapture({ db }, repository, outbox, files, { DEVICE }, json)
        data = MachineReportData({ db }, json, { account })
    }

    private fun snapshots(previous: String? = "1210.0", pending: String? = null) {
        fake.capabilities = fake.capabilities.orEmpty() + SyncCapabilities.OP_MACHINE_REPORT + SyncCapabilities.OP_CREDIT_INVOICE_PAYMENT
        fake.inbox = mapOf(
            "machine_report_states" to listOf(buildJsonObject {
                put("machine_id", fake.machineId); put("machine_code", "EX-01"); put("machine_name", "CAT 320D2"); put("meter_decimal_places", 1)
                put("previous_reading", previous); put("previous_at", previous?.let { "2026-10-20T14:30:00Z" })
                put("previous_source", previous?.let { "REPORT" }); put("last_approved_reading", previous); put("last_approved_at", previous?.let { "2026-10-20T14:30:00Z" })
                put("last_report_at", previous?.let { "2026-10-17T14:30:00Z" }); put("days_since_report", previous?.let { 4 })
                put("pending_report_id", pending); put("pending_report_number", pending?.let { "MR-2026-00001" }); put("rejected_report_id", null as String?)
            }),
            "machine_report_hours" to listOf(buildJsonObject {
                put("customer_id", fake.customerId); put("customer_name", "Pwani Road Contractors"); put("remaining", "160"); put("reserved", "20"); put("available", "140")
            }),
            "machine_report_reasons" to listOf(buildJsonObject {
                put("id", reasonId); put("code", "BREAKDOWN"); put("name", "Breakdown / repair"); put("description", null as String?); put("is_active", true); put("version", 1)
            }),
            "open_credit_invoices" to listOf(buildJsonObject {
                put("id", invoiceId); put("invoice_number", "CI-2026-00042"); put("purchase_id", UUID.randomUUID().toString()); put("customer_id", fake.customerId)
                put("customer_name", "Msasani Bay"); put("machine_id", fake.machineId); put("currency", "TZS"); put("hours", "40"); put("unit_price", "95000")
                put("amount", "3800000"); put("paid", "1800000"); put("paid_verified", "1800000"); put("balance", "2000000"); put("payment_terms_days", 14)
                put("issued_at", "2026-10-16T08:00:00Z"); put("due_date", "2026-10-30"); put("status", "PART_PAID"); put("overdue", false); put("days_overdue", 0)
                put("created_by", null as String?)
            }),
        )
    }

    private fun synced() = runBlocking { assertTrue(engine().sync(tenant) is SyncReport.Success) }

    private fun reading(text: String = "1510.0") = ReportReading(
        UUID.randomUUID().toString(), CaptureMode.MANUAL, text, photo, 0, null, // the test company reads DAILY meters by hand
        GpsOutcome.Fix(-6.8, 39.28, 6.0, Instant.ofEpochMilli(clock.now), "fused"), clock.now,
    )

    private fun request(lines: List<ReportLineDraft>, previous: BigDecimal? = BigDecimal("1210.0"), available: Map<String, BigDecimal>? = null) = runBlocking {
        MachineReportRequest(
            tenant, UUID.randomUUID().toString(), fake.machineId, 1, previous, reading(), lines = lines,
            available = available ?: data.observe(tenant).first().available(fake.machineId), note = " Hose failure on Thursday ", createdAtMs = clock.now,
        )
    }

    private val customer = ReportLineDraft.Customer(fake.customerId, "Pwani Road Contractors", "120")
    private val breakdown = ReportLineDraft.NonProductive(reasonId, "Breakdown / repair", "180", "Hydraulic hose replaced on site")

    private fun payload(opId: String): JsonObject = json.parseToJsonElement(op(opId).payloadJson).jsonObject

    @Test
    fun snapshotsGiveMachinesTheirStateAndCustomersTheirHours() = runBlocking {
        snapshots()
        synced()
        val view = data.observe(tenant).first()
        val machine = view.machines(reminderDays = 3).single()
        assertEquals(ReportState.DUE, machine.state)
        assertEquals("EX-01 · CAT 320D2", machine.label)
        assertEquals(BigDecimal("1210.0"), machine.previous)
        assertEquals(mapOf(fake.customerId to BigDecimal("140")), view.available(fake.machineId))
        assertEquals("Breakdown / repair", view.reasons.single().name)
        assertEquals(BigDecimal("2000000"), view.openInvoices().single().second)
        // Without the capability (switched off, or an older server) nothing of it is kept.
        fake.capabilities = fake.capabilities.orEmpty() - SyncCapabilities.OP_MACHINE_REPORT
        synced()
        assertTrue(data.observe(tenant).first().states.isEmpty())
    }

    @Test
    fun aReportIsQueuedOfflineAsADailyReadingThenTheReportThatNamesIt() = runBlocking {
        snapshots()
        synced()
        val r = request(listOf(customer, breakdown))
        val saved = reports.submit(r) as FinanceResult.Saved
        // The operation id is the report id; its type is MACHINE_REPORT.
        assertEquals(r.reportId, saved.operationId)
        assertEquals(MachineReportOps.MACHINE_REPORT, op(r.reportId).opType)
        // The reading goes first as a normal DAILY METER_CAPTURE carrying the photo gate; the report depends on it.
        val captureOpId = db.clientOperationDao().dependenciesOf(r.reportId).single()
        val captureOp = op(captureOpId)
        assertEquals(OpTypes.METER_CAPTURE, captureOp.opType)
        assertEquals(r.reading!!.captureId, captureOp.entityId)
        assertEquals(1, db.clientOperationDao().attachmentsOf(captureOpId).size)
        assertTrue(db.clientOperationDao().attachmentsOf(r.reportId).isEmpty())
        val capture = payload(captureOpId)
        assertEquals(r.reading!!.captureId, capture["id"]!!.jsonPrimitive.content)
        assertEquals("1510.0", capture["reading"]!!.jsonPrimitive.content)
        assertEquals("DAILY", capture["kind"]!!.jsonPrimitive.content)
        assertEquals(fake.machineId, capture["machine_id"]!!.jsonPrimitive.content)
        assertNull(capture["job_id"])
        val p = payload(r.reportId)
        assertEquals(fake.machineId, p["machine_id"]!!.jsonPrimitive.content)
        assertEquals(r.reading!!.captureId, p["capture_id"]!!.jsonPrimitive.content)
        assertNull(p["capture"])
        assertNull(p["corrects_report_id"])
        val lines = p["lines"]!!.jsonArray.map { it.jsonObject }
        assertEquals(listOf("CUSTOMER", "NON_PRODUCTIVE"), lines.map { it["kind"]!!.jsonPrimitive.content })
        assertEquals("120", lines[0]["hours"]!!.jsonPrimitive.content)
        assertEquals("Hydraulic hose replaced on site", lines[1]["note"]!!.jsonPrimitive.content)
        assertEquals("Hose failure on Thursday", p["note"]!!.jsonPrimitive.content)
        assertNull(p["opening"])
        assertNull(p["photo_upload_id"])
        // While the report waits, the phone counts its customer hours as taken.
        val view = data.observe(tenant).first()
        assertEquals(BigDecimal("20"), view.available(fake.machineId)[fake.customerId])
        assertEquals(ReportState.AWAITING_APPROVAL, view.machines(3).single().state)
        // Offline nothing is sent; online the photo uploads first, then the reading goes with it, then the report.
        assertTrue(engine(online = false).sync(tenant) is SyncReport.Retry)
        assertEquals(ClientOperationStatus.PENDING, status(captureOpId))
        assertEquals(ClientOperationStatus.PENDING, status(r.reportId))
        synced()
        assertEquals(ClientOperationStatus.ACKED, status(captureOpId))
        assertEquals(ClientOperationStatus.ACKED, status(r.reportId))
        assertNotNull(fake.stored[captureOpId]!!.payload["photo_attachment_id"])
        assertNull(fake.stored[r.reportId]!!.payload["photo_upload_id"])
        // A second tap never queues it twice.
        assertEquals(FinanceResult.AlreadySaved, reports.submit(r))
    }

    @Test
    fun theSplitMustMatchTheMeterAndStayWithinCustomersHours() = runBlocking {
        snapshots()
        synced()
        val short = reports.submit(request(listOf(customer, breakdown.copy(hoursText = "170"))))
        assertEquals(listOf("10 h still to account for"), (short as FinanceResult.Invalid).messages)
        val greedy = reports.submit(request(listOf(customer.copy(hoursText = "150"), breakdown.copy(hoursText = "150"))))
        assertEquals(listOf("Pwani Road Contractors has only 140 h available."), (greedy as FinanceResult.Invalid).messages)
        val same = reports.submit(request(listOf(breakdown)).copy(reading = reading("1210.0")))
        assertEquals(listOf(MachineReportMessages.NOTHING_TO_REPORT), (same as FinanceResult.Invalid).messages)
        assertTrue(db.clientOperationDao().observeUnsynced(tenant, USER_A.subject).first().isEmpty())
    }

    @Test
    fun anOpeningReportSendsTheReadingOnly() = runBlocking {
        snapshots(previous = null)
        synced()
        assertEquals(ReportState.OPENING, data.observe(tenant).first().machines(3).single().state)
        val r = request(emptyList(), previous = null)
        reports.submit(r) as FinanceResult.Saved
        val p = payload(r.reportId)
        assertEquals(true, p["opening"]!!.jsonPrimitive.content.toBoolean())
        assertTrue(p["lines"]!!.jsonArray.isEmpty())
        assertNull(p["capture"])
        assertEquals(r.reading!!.captureId, p["capture_id"]!!.jsonPrimitive.content)
        val captureOpId = db.clientOperationDao().dependenciesOf(r.reportId).single()
        assertEquals(OpTypes.METER_CAPTURE, op(captureOpId).opType)
        assertEquals("DAILY", payload(captureOpId)["kind"]!!.jsonPrimitive.content)
    }

    @Test
    fun aRejectedReportIsRedoneOnTheSameReadingWithoutANewCapture() = runBlocking {
        snapshots()
        synced()
        val rejectedId = UUID.randomUUID().toString()
        val oldCapture = UUID.randomUUID().toString()
        val r = request(listOf(customer, breakdown)).copy(
            reading = null, existingCaptureId = oldCapture, existingReading = "1510.0", correctsReportId = rejectedId,
        )
        reports.submit(r) as FinanceResult.Saved
        assertTrue(db.clientOperationDao().dependenciesOf(r.reportId).isEmpty())
        val p = payload(r.reportId)
        assertEquals(oldCapture, p["capture_id"]!!.jsonPrimitive.content)
        assertEquals(rejectedId, p["corrects_report_id"]!!.jsonPrimitive.content)
        assertNull(p["opening"])
        assertEquals(2, p["lines"]!!.jsonArray.size)
        // Only the report was queued: no new reading.
        assertEquals(listOf(MachineReportOps.MACHINE_REPORT), db.clientOperationDao().observeUnsynced(tenant, USER_A.subject).first().map { it.opType })
    }

    @Test
    fun aReportNeedsTheServerCapability() = runBlocking {
        synced()
        assertEquals(FinanceResult.Blocked(CaptureMeterReading.SERVER_TOO_OLD), reports.submit(request(listOf(breakdown.copy(hoursText = "300")), available = emptyMap())))
    }

    @Test
    fun anInvoicePaymentIsQueuedWithItsClientIdAndNeverAboveTheBalance() = runBlocking {
        snapshots()
        synced()
        val view = data.observe(tenant).first()
        val (invoice, balance) = view.openInvoices().single()
        fun pay(amount: String, method: PaymentMethod = PaymentMethod.CASH, reference: String = "", noncash: Boolean = false) =
            InvoicePaymentRequest(tenant, UUID.randomUUID().toString(), invoice.id, balance, amount, method, reference, clock.now, noncash)
        assertEquals(listOf("The invoice still owes only 2000000."), (reports.recordInvoicePayment(pay("2000001")) as FinanceResult.Invalid).messages)
        assertTrue(reports.recordInvoicePayment(pay("500", PaymentMethod.BANK, "REF", noncash = false)) is FinanceResult.Invalid)
        val request = pay("850000")
        val saved = reports.recordInvoicePayment(request) as FinanceResult.Saved
        assertEquals(request.clientId, saved.operationId)
        val p = payload(request.clientId)
        assertEquals(invoiceId, p["invoice_id"]!!.jsonPrimitive.content)
        assertEquals("850000", p["amount"]!!.jsonPrimitive.content)
        assertEquals("CASH", p["method"]!!.jsonPrimitive.content)
        assertNull(p["reference"])
        // The balance on this phone already counts the queued payment.
        assertEquals(BigDecimal("1150000"), data.observe(tenant).first().openInvoices().single().second)
        synced()
        assertEquals(ClientOperationStatus.ACKED, status(request.clientId))
    }
}
