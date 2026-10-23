package com.asseta.core.sync

import com.asseta.core.database.InboxRecordEntity
import com.asseta.core.database.ReadSnapshotEntity
import com.asseta.core.domain.inbox.InboxStatus
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.sync.data.AttentionItem
import com.asseta.core.sync.data.InboxRepository
import com.asseta.core.sync.engine.AccountSwitch
import com.asseta.core.sync.engine.SyncReport
import com.asseta.core.sync.usecase.CashHandoverRequest
import com.asseta.core.sync.usecase.FinanceResult
import com.asseta.core.sync.usecase.MeterResetRequest
import com.asseta.core.sync.usecase.RequestMeterReset
import com.asseta.core.sync.data.FieldOutbox
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
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
import java.util.UUID

/** Supervisor inbox: server copies applied from bootstrap/changes, merged with this phone's records, kept per user. */
@RunWith(RobolectricTestRunner::class)
class InboxSyncTest : SyncTestBase() {
    private lateinit var inbox: InboxRepository
    private lateinit var reset: RequestMeterReset

    @Before
    fun setUp() {
        inbox = InboxRepository({ db }, json, files, { account }) { clock.now }
        reset = RequestMeterReset({ db }, repository, FieldOutbox({ db }, json, clock, { account }), files, json)
    }

    private fun success(report: SyncReport) = assertTrue("expected Success but was $report", report is SyncReport.Success)

    private fun handoverRow(id: String, clientId: String?, status: String, revision: Long, note: String? = null) = buildJsonObject {
        put("id", id); put("client_id", clientId); put("staff_member_id", fake.staffId); put("amount", "100000.0000"); put("currency", "TZS")
        put("status", status); put("decision_note", note); put("reference", "R-1"); put("note", null as String?)
        put("handed_at", "2026-10-21T07:00:00Z"); put("recorded_at", "2026-10-21T07:01:00Z"); put("recorded_by", null as String?)
        put("verified_at", null as String?); put("verified_by", null as String?); put("source", "SYNC"); put("sync_revision", revision)
    }

    private fun captureRow(id: String, revision: Long, findingStatus: String?) = buildJsonObject {
        put("id", id); put("job_id", fake.jobId); put("machine_id", fake.machineId); put("kind", "OPENING"); put("capture_mode", "AUTOMATIC")
        put("reading", "1234.5"); put("state", "PROVISIONAL"); put("gps_status", "FIX"); put("latitude", -15.4); put("longitude", 28.3)
        put("accuracy_m", 8.0); put("location_captured_at", "2026-10-21T08:00:00Z"); put("photo_attachment_id", null as String?)
        put("photo_sha256", null as String?); put("ocr_value", "1234.5"); put("ocr_confidence", 0.95); put("manually_corrected", false)
        put("policy_version", "v1"); put("supersedes_id", null as String?); put("tracker_comparison", null as String?)
        put("captured_at", "2026-10-21T08:00:00Z"); put("received_at", "2026-10-21T08:01:00Z"); put("sync_revision", revision)
        put("review_status", if (findingStatus == null) "NONE" else if (findingStatus == "OPEN") "PENDING_REVIEW" else "REVIEWED")
        put("findings", buildJsonArray {
            if (findingStatus != null) add(buildJsonObject {
                put("id", "f-$id"); put("exception_type", "METER_DECREASE"); put("severity", "HIGH"); put("blocking", true)
                put("status", findingStatus); put("machine_id", fake.machineId); put("job_id", fake.jobId); put("meter_capture_id", id)
                put("policy_version", null as String?); put("review_note", if (findingStatus == "OPEN") null else "Meter was replaced")
                put("reviewed_at", null as String?); put("created_at", "2026-10-21T08:01:00Z"); put("evidence", JsonObject(emptyMap()))
            })
        })
    }

    private fun resetRow(id: String, status: String, revision: Long) = buildJsonObject {
        put("id", id); put("machine_id", fake.machineId); put("old_reading", "9999.9"); put("new_reading", "0.0")
        put("effective_at", "2026-10-21T08:00:00Z"); put("reason", "Meter replaced by the workshop"); put("status", status)
        put("evidence_attachment_id", null as String?); put("requested_by", null as String?); put("decided_by", null as String?)
        put("decided_at", if (status == "PENDING") null else "2026-10-21T09:00:00Z"); put("created_at", "2026-10-21T08:00:00Z")
        put("sync_revision", revision)
    }

    @Test
    fun localRecordWaitsThenMergesWithTheServerRecordAndItsDecision() = runBlocking {
        success(engine().sync(tenant))
        val clientId = UUID.randomUUID().toString()
        val saved = finance.cashHandover(CashHandoverRequest(tenant, clientId, "100000", "TZS", "R-1", "", clock.now)) as FinanceResult.Saved
        // Not synced yet: listed once, "Waiting to sync".
        var snap = inbox.observe(tenant).first()
        assertEquals(InboxStatus.WAITING, snap.handovers.single().status)

        success(engine().sync(tenant))
        assertEquals(ClientOperationStatus.ACKED, status(saved.operationId))
        snap = inbox.observe(tenant).first()
        assertEquals(InboxStatus.SYNCED, snap.handovers.single().status) // acked, server copy not pulled yet

        // The server's copy arrives (matched by client id): one row with the office's status, then its decision.
        val serverId = UUID.randomUUID().toString()
        fake.inbox = mapOf("my_cash_handovers" to listOf(handoverRow(serverId, clientId, "CLAIMED", 20)))
        success(engine().sync(tenant))
        snap = inbox.observe(tenant).first()
        assertEquals(serverId, snap.handovers.single().key)
        assertEquals(InboxStatus.CLAIMED, snap.handovers.single().status)
        assertNotNull(snap.handovers.single().op)

        fake.inbox = mapOf("my_cash_handovers" to listOf(handoverRow(serverId, clientId, "REJECTED", 21, "Amount does not match")))
        success(engine().sync(tenant))
        snap = inbox.observe(tenant).first()
        assertEquals(InboxStatus.REJECTED, snap.handovers.single().status)
        assertEquals("Amount does not match", snap.handovers.single().decisionNote)
        assertEquals(listOf(AttentionItem.Kind.HANDOVER), snap.attention.map { it.kind })

        // A replayed older revision (lookback) never overwrites the newer decision.
        fake.inbox = mapOf("my_cash_handovers" to listOf(handoverRow(serverId, clientId, "CLAIMED", 20)))
        success(engine().sync(tenant))
        assertEquals(InboxStatus.REJECTED, inbox.observe(tenant).first().handovers.single().status)
    }

    @Test
    fun capturesShowFindingsAndReviewAndMergeWithTheLocalCapture() = runBlocking {
        success(engine().sync(tenant))
        val local = saved(capture(captureRequest()))
        success(engine().sync(tenant))
        fake.inbox = mapOf("my_meter_captures" to listOf(captureRow(local.captureId, 30, "OPEN")))
        success(engine().sync(tenant))
        var reading = inbox.observe(tenant).first().readings.single()
        assertEquals(InboxStatus.FLAGGED, reading.status)
        assertNotNull(reading.local) // local evidence (photo) stays attached to the server's copy
        assertEquals(1, reading.blockingFindings)

        fake.inbox = mapOf("my_meter_captures" to listOf(captureRow(local.captureId, 31, "EXPLAINED")))
        success(engine().sync(tenant))
        reading = inbox.observe(tenant).first().readings.single()
        assertEquals(InboxStatus.REVIEWED, reading.status)
        assertEquals("Meter was replaced", reading.findings.single().reviewNote)
        assertEquals("1234.5", inbox.observe(tenant).first().jobReading(fake.jobId, "OPENING")?.reading)
    }

    @Test
    fun serverWithoutTheCapabilityKeepsCurrentBehaviour() = runBlocking {
        fake.capabilities = null
        success(engine().sync(tenant))
        assertEquals("", db.syncStateDao().get(tenant)!!.capabilities)
        assertEquals(0, db.inboxDao().count(tenant))
        // Reset requests need the capability.
        assertNotNull(reset.unavailable(tenant))
        val r = reset(MeterResetRequest(tenant, "c", fake.machineId, "10", "0", "Meter replaced by workshop", photo, clock.now))
        assertTrue(r is FinanceResult.Blocked)
    }

    @Test
    fun meterResetRequestUploadsEvidenceAndMergesWithTheDecision() = runBlocking {
        success(engine().sync(tenant))
        assertNull(reset.unavailable(tenant))
        val invalid = reset(MeterResetRequest(tenant, "c0", fake.machineId, "x", "0", "short", null, clock.now))
        assertEquals(3, (invalid as FinanceResult.Invalid).messages.size)
        val clientId = UUID.randomUUID().toString()
        val saved = reset(MeterResetRequest(tenant, clientId, fake.machineId, "9999.9", "0", "Meter replaced by the workshop", photo, clock.now))
        assertTrue(saved is FinanceResult.Saved)
        assertEquals(FinanceResult.AlreadySaved, reset(MeterResetRequest(tenant, clientId, fake.machineId, "9999.9", "0", "Meter replaced by the workshop", photo, clock.now)))
        assertEquals(InboxStatus.WAITING, inbox.observe(tenant).first().resets.single().status)

        success(engine().sync(tenant))
        val opId = (saved as FinanceResult.Saved).operationId
        assertEquals(ClientOperationStatus.ACKED, status(opId))
        val (serverId, payload) = fake.resets.entries.single()
        assertEquals("Meter replaced by the workshop", payload["reason"]!!.jsonPrimitive.content)
        assertTrue(fake.blobs.containsKey(payload["evidence_upload_id"]!!.jsonPrimitive.content))
        assertNull(payload["evidence_attachment_id"])

        // The server's reset (no client id) merges with the request by the acknowledged server id.
        fake.inbox = mapOf("my_meter_resets" to listOf(resetRow(serverId, "PENDING", 40)))
        success(engine().sync(tenant))
        var item = inbox.observe(tenant).first().resets.single()
        assertEquals(InboxStatus.PENDING, item.status)
        assertEquals(opId, item.op?.id)
        fake.inbox = mapOf("my_meter_resets" to listOf(resetRow(serverId, "APPROVED", 41)))
        success(engine().sync(tenant))
        item = inbox.observe(tenant).first().resets.single()
        assertEquals(InboxStatus.APPROVED, item.status)
        assertNotNull(item.decidedAtMs)
    }

    @Test
    fun anotherUserSignInClearsTheInboxAndCachedNotifications() = runBlocking {
        fake.inbox = mapOf("my_cash_handovers" to listOf(handoverRow(UUID.randomUUID().toString(), null, "VERIFIED", 5)))
        success(engine().sync(tenant))
        assertEquals(1, db.inboxDao().count(tenant))
        db.readSnapshotDao().putBounded(ReadSnapshotEntity(tenant, "supervisor.notifications", "[]", clock.now), 10)
        account = USER_B
        AccountSwitch { db }.claimAll(USER_B)
        assertEquals(0, db.inboxDao().count(tenant))
        assertNull(db.readSnapshotDao().get(tenant, "supervisor.notifications"))
        assertTrue(inbox.observe(tenant).first().handovers.isEmpty())
    }

    @Test
    fun bootstrapStartsTheInboxAfreshAndOldFinishedRecordsArePruned() = runBlocking {
        db.inboxDao().upsert(listOf(InboxRecordEntity(InboxRecordEntity.EXPENSE, "gone", tenant, null, null, null, "APPROVED", 1, 1, "{}")))
        success(engine().sync(tenant)) // bootstrap with SUPERVISOR_INBOX_V1
        assertEquals(0, db.inboxDao().count(tenant))
        val old = clock.now - 40L * 24 * 3600 * 1000
        db.inboxDao().upsert(
            listOf(
                InboxRecordEntity(InboxRecordEntity.EXPENSE, "old-done", tenant, null, null, null, "APPROVED", old, 1, "{}"),
                InboxRecordEntity(InboxRecordEntity.EXPENSE, "old-open", tenant, null, null, null, "PENDING_APPROVAL", old, 1, "{}"),
            ),
        )
        fake.inbox = mapOf("my_expenses" to emptyList())
        success(engine().sync(tenant))
        assertEquals(listOf("old-open"), db.inboxDao().kind(tenant, InboxRecordEntity.EXPENSE).map { it.id })
    }
}
