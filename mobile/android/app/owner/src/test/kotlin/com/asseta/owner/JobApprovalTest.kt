package com.asseta.owner

import com.asseta.core.domain.owner.MutationCheck
import com.asseta.core.domain.owner.MutationGate
import com.asseta.core.domain.owner.OwnerAction
import com.asseta.core.domain.owner.OwnerErrors
import com.asseta.core.domain.owner.DataSource
import com.asseta.core.model.owner.JobDto
import com.asseta.core.network.NetworkFactory
import com.asseta.owner.ui.approvals.ApprovalsViewModel
import com.asseta.owner.ui.approvals.JobApprovalText
import com.asseta.owner.ui.common.ScreenState
import com.asseta.owner.ui.jobs.JobDetailViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.emptyFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import kotlinx.coroutines.withTimeout
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import mockwebserver3.Dispatcher
import mockwebserver3.MockResponse
import mockwebserver3.RecordedRequest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.util.Collections

/** Owner job approval: field requests show who asked; a job without a rate card is priced on approval; decline = CANCEL. */
@OptIn(ExperimentalCoroutinesApi::class)
class JobApprovalTest {
    private val h = OwnerHarness()
    private val transitions = Collections.synchronizedList(mutableListOf<String>())
    @Volatile private var status = "PENDING_APPROVAL"
    @Volatile private var refuse: String? = null

    private fun job(rateSource: String = "PENDING_PRICE") = """{"id":"$ID1","job_number":"J-2026-105","status":"$status","machine_id":"$ID2",
        "contract_id":"$ID2","currency":"TZS","hourly_rate":"0.0000","minimum_hours":"0.0000","mobilization_fee":"0.0000",
        "discount_percent":"0.0000","tax_rate_percent":"0.0000","rate_source":"$rateSource","standby_treatment":"EXCLUDED",
        "planned_start":"2026-10-24T06:00:00Z","version":1,"requested_by_staff_id":"$ID2","requested_by_name":"Juma Katavi",
        "request_note":"Dig the north trench","cancellation_reason":null}"""

    @Before
    fun setUp() {
        Dispatchers.setMain(Dispatchers.Unconfined)
        h.server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.url.encodedPath
                fun ok(body: String) = MockResponse.Builder().code(200).body(body).build()
                return when {
                    path.endsWith("/transitions") -> {
                        transitions += request.body!!.utf8()
                        refuse?.let { code ->
                            refuse = null
                            return MockResponse.Builder().code(422).body("""{"error":{"code":"$code","message":"price missing","correlation_id":"c"}}""").build()
                        }
                        status = if (request.body!!.utf8().contains("APPROVE")) "APPROVED" else "CANCELLED"
                        ok(job())
                    }
                    path == "/api/v1/tenant/jobs" -> ok(Samples.page(job()))
                    path == "/api/v1/tenant/jobs/$ID1" -> ok("""{"job":${job()},"nonbillable_hours":"0","billing_ready":false,"open_exceptions":0,
                        "blocking_exceptions":0,"policy_version":"p"}""")
                    path.startsWith("/api/v1/tenant/jobs/$ID1/") -> ok("[]")
                    path == "/api/v1/tenant/approvals" -> ok(Samples.page())
                    else -> MockResponse.Builder().code(404).body("""{"error":{"code":"NOT_FOUND","message":"no","correlation_id":"c"}}""").build()
                }
            }
        }
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
        h.close()
    }

    private fun <T> StateFlow<ScreenState<T>>.settled(): ScreenState<T> = runBlocking { withTimeout(5_000) { first { !it.loading } } }

    private fun <T> StateFlow<T>.await(predicate: (T) -> Boolean): T = runBlocking { withTimeout(5_000) { first(predicate) } }

    private fun body(i: Int) = Json.parseToJsonElement(transitions[i]).jsonObject

    @Test
    fun `waiting jobs are listed in approvals with who requested them`() {
        val vm = ApprovalsViewModel(h.data, emptyFlow(), jobs = true)
        val jobs = vm.pendingJobs!!.state.settled().data!!.items
        assertEquals("J-2026-105", jobs.single().jobNumber)
        assertEquals("Requested from the field by Juma Katavi", JobApprovalText.requestedBy(jobs.single().requestedByName))
        assertEquals("Dig the north trench", jobs.single().requestNote)
        assertTrue(jobs.single().pendingPrice)
        assertNull(ApprovalsViewModel(h.data, emptyFlow()).pendingJobs)
    }

    @Test
    fun `approving a job without a rate card sends the hourly rate and price required reads friendly`() {
        val vm = JobDetailViewModel(h.data, ID1, false, emptyFlow())
        assertEquals("PENDING_APPROVAL", vm.state.settled().data!!.summary.job.status)
        refuse = "PRICE_REQUIRED"
        vm.approve(null)
        assertEquals("Set an hourly rate before approving this job.", vm.error.await { it != null })
        vm.busy.await { !it }
        vm.approve("85000")
        assertEquals("Job approved.", vm.message.await { it != null })
        assertEquals("APPROVE", body(1)["action"]!!.jsonPrimitive.content)
        assertEquals("85000", body(1)["hourly_rate"]!!.jsonPrimitive.content)
        assertEquals("APPROVED", vm.state.await { it.data?.summary?.job?.status == "APPROVED" }.data!!.summary.job.status)
    }

    @Test
    fun `declining sends cancel with the reason and needs one`() {
        val vm = JobDetailViewModel(h.data, ID1, false, emptyFlow())
        vm.state.settled()
        vm.decline("  ")
        assertTrue(transitions.isEmpty())
        vm.decline("Customer has no budget this month")
        assertEquals("Job declined.", vm.message.await { it != null })
        assertEquals("CANCEL", body(0)["action"]!!.jsonPrimitive.content)
        assertEquals("Customer has no budget this month", body(0)["reason"]!!.jsonPrimitive.content)
        assertNull(body(0)["hourly_rate"])
    }

    @Test
    fun `approve rules, wording and the permission gate`() {
        val pending = NetworkFactory.json.decodeFromString(JobDto.serializer(), job())
        val rated = NetworkFactory.json.decodeFromString(JobDto.serializer(), job("RATE_CARD:x"))
        assertFalse(JobApprovalText.canApprove(pending, ""))
        assertFalse(JobApprovalText.canApprove(pending, "abc"))
        assertTrue(JobApprovalText.canApprove(pending, "85000.50"))
        assertTrue(JobApprovalText.canApprove(rated, ""))
        assertEquals("Hourly rate (TZS)", JobApprovalText.rateLabel("TZS"))
        assertEquals("No rate card applies — set the price to approve", JobApprovalText.PRICE_HELPER)
        assertEquals("Decline", JobApprovalText.DECLINE)
        assertEquals("Reason", JobApprovalText.REASON)
        assertEquals(OwnerErrors.PRICE_REQUIRED, OwnerErrors.message("PRICE_REQUIRED", "x"))
        assertEquals(
            MutationCheck.Blocked(MutationGate.NOT_PERMITTED),
            MutationGate.check(OwnerAction.DECIDE_JOB, true, DataSource.LIVE, setOf("tenant.job.read"), false),
        )
        assertEquals(MutationCheck.Allowed, MutationGate.check(OwnerAction.DECIDE_JOB, true, DataSource.LIVE, setOf("tenant.job.approve"), false))
    }
}
