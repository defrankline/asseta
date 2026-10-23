package com.asseta.supervisor.ui

import com.asseta.core.database.JobEntity
import com.asseta.core.domain.capture.GpsOutcome
import com.asseta.core.domain.capture.JobStatus
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.model.sync.OpTypes
import com.asseta.core.sync.data.JobSummary
import com.asseta.core.sync.data.WaitingReason
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** The wording below is the iOS app's (AssetaField); both apps must show the same text. */
class FieldTextsTest {
    private fun payload(text: String) = Json.parseToJsonElement(text).jsonObject

    private fun job(id: String, status: String) = JobSummary(
        JobEntity(id, "t", "J-$id", "m", "c", null, status, 1, "2026-10-23T08:00:00Z", null, null), null,
    )

    @Test
    fun statusBadgeMarksLocalStateNotYetSynced() {
        assertEquals("Approved", FieldTexts.statusBadge(JobStatus.APPROVED, JobStatus.APPROVED))
        assertEquals("In progress · not synced", FieldTexts.statusBadge(JobStatus.IN_PROGRESS, JobStatus.APPROVED))
        assertEquals("Pending approval", FieldTexts.jobStatus("PENDING_APPROVAL"))
    }

    @Test
    fun jobsAreGroupedLikeTheIosHomeList() {
        val jobs = listOf(job("1", JobStatus.COMPLETED), job("2", JobStatus.APPROVED), job("3", JobStatus.APPROVED))
        val display = mapOf("1" to JobStatus.COMPLETED, "2" to JobStatus.IN_PROGRESS, "3" to JobStatus.APPROVED)
        val sections = FieldTexts.jobSections(jobs) { display.getValue(it.job.id) }
        assertEquals(listOf("In progress", "Ready to start", "Other"), sections.map { it.first })
        assertEquals(listOf("2"), sections[0].second.map { it.job.id })
        assertEquals(listOf("1"), sections[2].second.map { it.job.id })
        assertEquals(emptyList<String>(), FieldTexts.jobSections(emptyList()) { it.job.status }.map { it.first })
    }

    @Test
    fun operationTitlesMatchIos() {
        assertEquals("Opening reading 1234.5", FieldTexts.operationTitle(OpTypes.METER_CAPTURE, payload("""{"kind":"OPENING","reading":"1234.5"}""")))
        assertEquals("Work log: Downtime", FieldTexts.operationTitle(OpTypes.JOB_ACTIVITY, payload("""{"activity_type":"DOWNTIME"}""")))
        assertEquals("Acknowledged by Jane", FieldTexts.operationTitle(OpTypes.JOB_ACKNOWLEDGEMENT, payload("""{"signer_name":"Jane"}""")))
        assertEquals("Job completed", FieldTexts.operationTitle(OpTypes.JOB_TRANSITION, payload("""{"action":"COMPLETE"}""")))
        assertEquals("Fuel issue: 40 L", FieldTexts.operationTitle(OpTypes.FUEL_EVENT, payload("""{"event_type":"ISSUE","litres":"40"}""")))
        assertEquals("Complete job", FieldTexts.outboxTitle(OpTypes.JOB_TRANSITION, payload("""{"action":"COMPLETE"}""")))
        assertEquals("Start job", FieldTexts.outboxTitle(OpTypes.JOB_TRANSITION, payload("""{"action":"START"}""")))
        assertEquals("Cash handover", FieldTexts.outboxTitle(OpTypes.CASH_HANDOVER, null))
    }

    @Test
    fun syncWording() {
        assertEquals("Held", FieldTexts.syncState(ClientOperationStatus.QUARANTINED))
        assertEquals("Rejected", FieldTexts.syncState(ClientOperationStatus.FAILED))
        assertEquals("Waiting for its photo/receipt/signature upload", FieldTexts.waiting(WaitingReason.UPLOAD))
        assertEquals("You can sign in again at any time.", FieldTexts.signOutMessage(0))
        assertEquals(
            "3 item(s) are not synced yet. They stay encrypted on this phone and sync after you sign in again.",
            FieldTexts.signOutMessage(3),
        )
        assertNull(FieldTexts.lastSyncProblem(null))
        assertEquals("Sync failed: Offline or server unreachable. It will retry automatically.", FieldTexts.lastSyncProblem("NETWORK"))
        assertEquals("Server problem: BAD_SERVER_RESPONSE. It will retry automatically.", FieldTexts.lastSyncProblem("BAD_SERVER_RESPONSE"))
    }

    @Test
    fun clockSkewIsDescribedInMinutesOrHours() {
        assertEquals("10 minutes fast", FieldTexts.describeSkew(600))
        assertEquals("119 minutes slow", FieldTexts.describeSkew(-119 * 60))
        assertEquals("3 hours fast", FieldTexts.describeSkew(3 * 3_600 + 59))
        assertEquals(
            "This phone's clock is 10 minutes fast compared with Asseta's server. Set the date and time to automatic. " +
                "Readings still record the phone's own time.",
            FieldTexts.clockTamper(600),
        )
    }

    @Test
    fun meterPrecisionAndGpsFailures() {
        assertEquals("Whole hours", FieldTexts.meterPrecision(0))
        assertEquals("2 decimal place(s)", FieldTexts.meterPrecision(2))
        assertEquals("No GPS fix within 20 seconds", FieldTexts.gpsFailure(GpsOutcome.Timeout))
        assertEquals("Location services are turned off", FieldTexts.gpsFailure(GpsOutcome.Disabled))
    }
}
