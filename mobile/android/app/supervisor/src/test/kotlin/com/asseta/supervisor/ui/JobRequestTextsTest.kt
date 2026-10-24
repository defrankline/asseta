package com.asseta.supervisor.ui

import com.asseta.core.database.JobEntity
import com.asseta.core.domain.capture.JobStatus
import com.asseta.core.domain.jobs.JobRequestRules
import com.asseta.core.domain.jobs.JobRequestState
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.model.sync.FieldContractDto
import com.asseta.core.model.sync.JobRequestPayload
import com.asseta.core.model.sync.MachineDto
import com.asseta.core.model.sync.OpTypes
import com.asseta.core.sync.usecase.JobRequestItem
import com.asseta.core.sync.usecase.JobRequestLookups
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.concurrent.TimeUnit

/** Job requests from the field: the wording is the iOS app's (`JobRequestTexts`); both apps must show the same text. */
class JobRequestTextsTest {
    private val now = 1_800_000_000_000L

    private fun request(id: String, status: ClientOperationStatus, ageDays: Long = 0, number: String? = null) = JobRequestItem(
        id, status, number, JobRequestPayload(id, "c1", "m1", null, "2026-10-24T08:00:00Z"), now - TimeUnit.DAYS.toMillis(ageDays), null,
    )

    private fun job(status: String, requestedBy: String? = null, reason: String? = null) =
        JobEntity("j", "t", "J-2026-105", "m1", "c1", null, status, 2, "2026-10-24T08:00:00Z", null, null, "TZS", reason, requestedBy)

    @Test
    fun theFormAndListUseTheSharedWording() {
        assertEquals("Request job", JobRequestTexts.BUTTON)
        assertEquals("Request a job", Route.RequestJob.title("Acme"))
        assertTrue(Route.RequestJob.isForm)
        assertEquals(
            listOf("Customer contract", "Machine", "Site (optional)", "Planned start", "Planned end (optional)", "What the customer asked for", "Send for approval"),
            listOf(JobRequestTexts.CONTRACT, JobRequestTexts.MACHINE, JobRequestTexts.SITE, JobRequestTexts.PLANNED_START,
                JobRequestTexts.PLANNED_END, JobRequestTexts.NOTE, JobRequestTexts.SUBMIT),
        )
        assertEquals("Job request", FieldTexts.outboxTitle(OpTypes.JOB_REQUEST, null))
    }

    @Test
    fun aRequestIsNotSentThenWaitingThenDeclined() {
        fun chip(op: ClientOperationStatus?, job: String?) = JobRequestTexts.chip(JobRequestRules.state(op, job), op)
        assertEquals("Waiting for approval (not yet sent)", chip(ClientOperationStatus.PENDING, null))
        assertEquals("Waiting for approval (not yet sent)", chip(ClientOperationStatus.SENT, null))
        assertEquals("Waiting for approval", chip(ClientOperationStatus.ACKED, null))
        assertEquals("Waiting for approval", chip(ClientOperationStatus.ACKED, "PENDING_APPROVAL"))
        assertEquals("Declined", chip(ClientOperationStatus.ACKED, JobStatus.CANCELLED))
        assertEquals("Rejected", chip(ClientOperationStatus.FAILED, null))
        assertNull(chip(ClientOperationStatus.ACKED, JobStatus.APPROVED))
        assertEquals(JobRequestState.DECIDED, JobRequestRules.state(null, JobStatus.IN_PROGRESS))
    }

    @Test
    fun jobsOnThePhoneCarryTheRequestChip() {
        assertEquals("Waiting for approval", JobRequestTexts.jobChip(job("PENDING_APPROVAL"), requestedHere = false))
        assertEquals("Declined", JobRequestTexts.jobChip(job(JobStatus.CANCELLED, requestedBy = "s1"), requestedHere = false))
        assertEquals("Declined", JobRequestTexts.jobChip(job(JobStatus.CANCELLED), requestedHere = true))
        // An office job the office cancelled is just "Cancelled".
        assertNull(JobRequestTexts.jobChip(job(JobStatus.CANCELLED), requestedHere = false))
        assertNull(JobRequestTexts.jobChip(job(JobStatus.APPROVED, requestedBy = "s1"), requestedHere = true))
    }

    @Test
    fun requestsAreListedUntilTheirJobIsOnThePhone() {
        val list = listOf(
            request("a", ClientOperationStatus.PENDING, ageDays = 30),
            request("b", ClientOperationStatus.ACKED, ageDays = 2, number = "J-2026-105"),
            request("c", ClientOperationStatus.ACKED, ageDays = 20),
            request("d", ClientOperationStatus.ACKED),
        )
        assertEquals(listOf("a", "b"), JobRequestTexts.pending(list, setOf("d"), now).map { it.clientId })
    }

    @Test
    fun pickersAndRowsNameTheCustomerAndMachine() {
        val contract = FieldContractDto("c1", "CT-01", "cu1", "Road Builders Ltd", "s1", "Katavi quarry", "TZS")
        val machine = MachineDto("m1", "EX-01", "Excavator 01", 1, "ACTIVE", 1)
        val option = JobRequestTexts.contractOption(contract)
        assertEquals("Road Builders Ltd", option.title)
        assertEquals("CT-01 · Katavi quarry", option.subtitle)
        assertEquals("EX-01 · Excavator 01", JobRequestTexts.machineOption(machine).title)
        assertEquals(
            "EX-01 · Excavator 01\nRoad Builders Ltd",
            JobRequestTexts.requestLine(request("a", ClientOperationStatus.PENDING), JobRequestLookups(listOf(contract), listOf(machine))),
        )
    }

    @Test
    fun theFormNeedsContractMachineAndOrderedDates() {
        assertEquals(emptyList<String>(), JobRequestRules.validate("c", "m", 10, null, ""))
        assertEquals(listOf("The planned end is before the planned start."), JobRequestRules.validate("c", "m", 10, 9, ""))
    }
}
