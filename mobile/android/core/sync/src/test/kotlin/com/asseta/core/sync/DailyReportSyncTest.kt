package com.asseta.core.sync

import com.asseta.core.domain.accountability.DailyReportDraft
import com.asseta.core.domain.accountability.DailyReportMessages
import com.asseta.core.domain.accountability.UnbillableDraft
import com.asseta.core.domain.policy.CaptureMode
import com.asseta.core.domain.policy.ReadingKind
import com.asseta.core.model.ClientOperationStatus.ACKED
import com.asseta.core.model.ClientOperationStatus.CONFLICT
import com.asseta.core.model.ClientOperationStatus.PENDING
import com.asseta.core.model.owner.DailyReportDto
import com.asseta.core.model.sync.AccountabilityOps
import com.asseta.core.model.sync.BlobPurpose
import com.asseta.core.model.sync.DailyReportPayload
import com.asseta.core.model.sync.SyncCapabilities
import com.asseta.core.sync.data.DailyReportData
import com.asseta.core.sync.data.FieldOps
import com.asseta.core.sync.data.FieldOutbox
import com.asseta.core.sync.engine.SyncReport
import com.asseta.core.sync.usecase.CaptureMeterReading
import com.asseta.core.sync.usecase.CaptureResult
import com.asseta.core.sync.usecase.CaptureTarget
import com.asseta.core.sync.usecase.DailyReportCapture
import com.asseta.core.sync.usecase.DailyReportRequest
import com.asseta.core.sync.usecase.FinanceResult
import com.asseta.core.sync.usecase.JobWorkflow
import com.asseta.core.sync.usecase.WorkflowResult
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import java.util.UUID

/** DEC-032 Phase 1 on the phone: the DAILY_REPORT operation and the changeover reading, through the real engine. */
@RunWith(RobolectricTestRunner::class)
class DailyReportSyncTest : SyncTestBase() {
    private lateinit var reports: DailyReportCapture
    private val opening = UUID.randomUUID().toString()
    private val closing = UUID.randomUUID().toString()
    private val reason = UUID.randomUUID().toString()
    private val nextCustomer = "99999999-9999-4999-8999-999999999999"

    @Before
    fun setUp() {
        reports = DailyReportCapture({ db }, repository, FieldOutbox({ db }, json, clock, { account }), files, json)
        fake.capabilities = listOf(SyncCapabilities.SUPERVISOR_INBOX_V1, SyncCapabilities.OP_DAILY_REPORT, SyncCapabilities.METER_CHANGEOVER)
    }

    private fun success(report: SyncReport) = assertTrue("expected Success but was $report", report is SyncReport.Success)

    private fun request(clientId: String = UUID.randomUUID().toString(), openingRef: String = opening, photos: List<ByteArray> = emptyList(), supersedes: String? = null) =
        DailyReportRequest(
            tenant, clientId, fake.machineId, "2026-10-21",
            DailyReportDraft(openingRef, closing, "100", "110", "7.50", listOf(UnbillableDraft(reason, "2")), " Rain ", photos.size, false),
            photos, supersedes, clock.now,
        )

    private fun saved(r: FinanceResult) = (r as? FinanceResult.Saved) ?: throw AssertionError("expected Saved but was $r")

    private fun payload(id: String): JsonObject = json.parseToJsonElement(op(id).payloadJson).jsonObject

    @Test
    fun reportIsQueuedOncePerVisitAndTheOperationIdIsTheReportId() = runBlocking {
        success(engine().sync(tenant))
        val client = UUID.randomUUID().toString()
        val first = saved(reports.submit(request(client)))
        assertEquals(FinanceResult.AlreadySaved, reports.submit(request(client)))
        val o = op(first.operationId)
        assertEquals(AccountabilityOps.DAILY_REPORT, o.opType)
        assertEquals(FieldOps.DAILY_REPORT, o.entityType)
        val p = payload(first.operationId)
        assertFalse(p.containsKey("id"))
        assertEquals("2026-10-21", p["report_date"]!!.jsonPrimitive.content)
        assertEquals("7.5", p["billable_hours"]!!.jsonPrimitive.content)
        assertEquals(reason, p["unbillable"]!!.jsonArray.single().jsonObject["reason_id"]!!.jsonPrimitive.content)
        assertEquals("Rain", p["note"]!!.jsonPrimitive.content)
        assertTrue(p["client_created_at"]!!.jsonPrimitive.content.startsWith("2026-10-21T08:00"))
        success(engine().sync(tenant))
        assertEquals(ACKED, status(first.operationId))
    }

    @Test
    fun photosGoByUploadAndTheOperationWaitsForThem() = runBlocking {
        success(engine().sync(tenant))
        val s = saved(reports.submit(request(photos = listOf(photo))))
        val attachment = db.evidenceDao().attachment(db.clientOperationDao().attachmentsOf(s.operationId).single())!!
        assertEquals(BlobPurpose.DAILY_REPORT_EVIDENCE, attachment.purpose)
        fake.failChunkOnce = 1
        assertTrue(engine().sync(tenant) is SyncReport.Retry)
        assertEquals(PENDING, status(s.operationId))
        assertTrue(fake.pushedBatches.none { s.operationId in it })
        success(engine().sync(tenant))
        assertEquals(ACKED, status(s.operationId))
        val session = fake.blobs.values.single { it.attachmentId != null }
        assertEquals(listOf(session.id), payload(s.operationId)["evidence_upload_ids"]!!.jsonArray.map { it.jsonPrimitive.content })
    }

    @Test
    fun reportWaitsForAReadingTheServerDoesNotHaveYet() = runBlocking {
        success(engine().sync(tenant))
        val request = captureRequest(ReadingKind.OPENING)
        val reading = saved(capture(request))
        val s = saved(reports.submit(request(openingRef = request.captureId)))
        assertEquals(listOf(reading.operationId), db.clientOperationDao().dependenciesOf(s.operationId))
        success(engine().sync(tenant))
        assertEquals(ACKED, status(reading.operationId))
        assertEquals(ACKED, status(s.operationId))
    }

    @Test
    fun aReadingTheServerRefusedCannotBeNamed() = runBlocking {
        success(engine().sync(tenant))
        val request = captureRequest(ReadingKind.OPENING)
        saved(capture(request))
        fake.handler = { "CONFLICT" to buildJsonObject { put("error", fake.err("CAPTURE_ID_CONFLICT")) } }
        engine().sync(tenant)
        val r = reports.submit(request(openingRef = request.captureId))
        assertEquals(FinanceResult.Blocked(DailyReportCapture.READING_NOT_ACCEPTED), r)
    }

    @Test
    fun conflictKeepsTheCodeForPlainWords() = runBlocking {
        success(engine().sync(tenant))
        val s = saved(reports.submit(request()))
        fake.handler = { "CONFLICT" to buildJsonObject { put("error", fake.err("REPORT_READINGS_INVALID")) } }
        engine().sync(tenant)
        assertEquals(CONFLICT, op(s.operationId).status)
        assertEquals("REPORT_READINGS_INVALID", op(s.operationId).errorCode)
    }

    @Test
    fun serverWithoutTheCapabilityBlocksTheForm() = runBlocking {
        fake.capabilities = listOf(SyncCapabilities.SUPERVISOR_INBOX_V1)
        success(engine().sync(tenant))
        assertEquals(FinanceResult.Blocked(CaptureMeterReading.SERVER_TOO_OLD), reports.submit(request()))
    }

    @Test
    fun mergeShowsTheServerCopyOverTheUnsentOne() = runBlocking {
        success(engine().sync(tenant))
        val s = saved(reports.submit(request()))
        val unsent = DailyReportData.merge(emptyList(), listOf(op(s.operationId)), json).single()
        assertEquals(s.operationId, unsent.key)
        assertEquals("2026-10-21", unsent.reportDate)
        val server = json.decodeFromString(DailyReportDto.serializer(), serverReport(s.operationId))
        val merged = DailyReportData.merge(listOf(server), listOf(op(s.operationId)), json).single()
        assertEquals("RETURNED", merged.server!!.status)
        assertTrue(merged.returned)
    }

    private fun serverReport(id: String) = """{"id":"$id","machine_id":"${fake.machineId}","report_date":"2026-10-21","opening_ref":"$opening","opening_reading":"100",
        "closing_ref":"$closing","closing_reading":"110","total_hours":"10","billable_hours":"8","unbillable_hours":"2","difference_hours":"0","status":"RETURNED",
        "submitted_at":"2026-10-21T08:00:00Z","client_created_at":"2026-10-21T08:00:00Z","review_note":"Wrong day"}"""

    private fun changeoverRequest(customer: String?, job: String?, jobRequired: Boolean) =
        captureRequest(ReadingKind.DAILY, mode = CaptureMode.MANUAL, ocr = null).copy(target = CaptureTarget.Changeover(customer, job, jobRequired))


    @Test
    fun changeoverNeedsARunningJob() = runBlocking {
        success(engine().sync(tenant))
        val r = capture(changeoverRequest(nextCustomer, null, false))
        assertEquals(CaptureResult.Blocked(CaptureMeterReading.CHANGEOVER_NOT_RUNNING), r)
    }

    private suspend fun started(): String {
        success(engine().sync(tenant))
        saved(capture(captureRequest(ReadingKind.OPENING)))
        assertTrue(workflow.transition(tenant, fake.jobId, JobWorkflow.START) is WorkflowResult.Done)
        return db.clientOperationDao().forJob(tenant, USER_A.subject, fake.jobId).single { it.entityType == FieldOps.transitionEntityType("START") }.id
    }

    @Test
    fun changeoverCarriesTheNextCustomerAndWaitsForTheStart() = runBlocking {
        val start = started()
        val r = saved(capture(changeoverRequest(nextCustomer, null, false)))
        assertEquals(listOf(start), db.clientOperationDao().dependenciesOf(r.operationId))
        val p = payload(r.operationId)
        assertEquals("DAILY", p["kind"]!!.jsonPrimitive.content)
        assertEquals(fake.jobId, p["job_id"]!!.jsonPrimitive.content)
        assertEquals(nextCustomer, p["changeover_to_customer_id"]!!.jsonPrimitive.content)
        success(engine().sync(tenant))
        assertEquals(ACKED, status(r.operationId))
    }

    @Test
    fun changeoverRequiresTheCustomerAndTheJobWhenTheTenantSaysSo() = runBlocking {
        started()
        assertEquals(CaptureResult.Blocked(DailyReportMessages.CHANGEOVER_CUSTOMER), capture(changeoverRequest(null, null, false)))
        assertEquals(CaptureResult.Blocked(DailyReportMessages.CHANGEOVER_JOB), capture(changeoverRequest(nextCustomer, null, true)))
        val job = UUID.randomUUID().toString()
        val r = saved(capture(changeoverRequest(nextCustomer, job, true)))
        assertEquals(job, payload(r.operationId)["changeover_to_job_id"]!!.jsonPrimitive.content)
    }

    private fun changeoverJob(id: String, status: String, revision: Long) = buildJsonObject {
        put("id", id); put("job_number", "J-$revision"); put("machine_id", fake.machineId); put("customer_id", nextCustomer)
        put("customer_name", "Next Ltd"); put("status", status); put("sync_revision", revision)
    }

    private fun reasonRow(id: String, active: Boolean, revision: Long) = buildJsonObject {
        put("id", id); put("code", "R"); put("name", "Rain"); put("description", null as String?); put("is_active", active); put("sync_revision", revision)
    }

    @Test
    fun tenantZoneFromSyncIsKeptAcrossPullsThatDoNotSendIt() = runBlocking {
        fake.tenantTimezone = "Africa/Dar_es_Salaam"
        success(engine().sync(tenant))
        assertEquals("Africa/Dar_es_Salaam", repository.tenantTimezone(tenant))
        fake.tenantTimezone = null
        success(engine().sync(tenant))
        assertEquals("Africa/Dar_es_Salaam", repository.tenantTimezone(tenant))
    }

    @Test
    fun syncedListsFollowRevisionsAndDeactivations() = runBlocking {
        fake.capabilities = fake.capabilities.orEmpty() + listOf(SyncCapabilities.SYNC_CHANGEOVER_JOBS, SyncCapabilities.SYNC_UNBILLABLE_REASONS)
        val job = UUID.randomUUID().toString()
        fake.inbox = mapOf("changeover_jobs" to listOf(changeoverJob(job, "PENDING_APPROVAL", 5)), "unbillable_reasons" to listOf(reasonRow(reason, true, 5)))
        success(engine().sync(tenant))
        assertEquals("PENDING_APPROVAL", financeRepository.changeoverJobs(tenant)!!.single().status)
        assertEquals(listOf(reason), financeRepository.unbillableReasons(tenant)!!.map { it.id })

        fake.cursor = 20
        fake.inbox = mapOf("changeover_jobs" to listOf(changeoverJob(job, "CANCELLED", 3))) // older replay
        success(engine().sync(tenant))
        assertEquals("PENDING_APPROVAL", financeRepository.changeoverJobs(tenant)!!.single().status)

        fake.cursor = 30
        fake.inbox = mapOf("changeover_jobs" to listOf(changeoverJob(job, "APPROVED", 9)), "unbillable_reasons" to listOf(reasonRow(reason, false, 9)))
        success(engine().sync(tenant))
        assertEquals("APPROVED", financeRepository.changeoverJobs(tenant)!!.single().status)
        assertTrue(financeRepository.unbillableReasons(tenant)!!.isEmpty())
    }

    @Test
    fun listsAreNullWhileTheServerDoesNotAnnounceThem() = runBlocking {
        success(engine().sync(tenant))
        assertEquals(null, financeRepository.changeoverJobs(tenant))
        assertEquals(null, financeRepository.unbillableReasons(tenant))
    }
}
