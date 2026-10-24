package com.asseta.owner

import com.asseta.core.model.owner.ContractDto
import com.asseta.core.model.owner.JobDto
import com.asseta.core.model.owner.MachineDto
import com.asseta.core.model.owner.StaffDto
import com.asseta.owner.data.ActionResult
import com.asseta.owner.ui.OwnerFeatures
import com.asseta.owner.ui.jobs.JobCreateModel
import com.asseta.owner.ui.jobs.JobCreateOutcome
import com.asseta.owner.ui.jobs.JobCreateText
import com.asseta.owner.ui.jobs.JobField
import com.asseta.owner.ui.jobs.JobForm
import com.asseta.owner.ui.jobs.RateMode
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
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
import java.time.Instant
import java.util.Collections
import java.util.UUID

/** Owner "New job": validation, the createJob body, the create -> SUBMIT -> APPROVE sequence and its keys, gating. */
class JobCreateTest {
    private val h = OwnerHarness()
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)

    /** Mutation requests seen by the server: path, body, Idempotency-Key. */
    private val posts = Collections.synchronizedList(mutableListOf<Triple<String, String, String?>>())
    private val gets = Collections.synchronizedList(mutableListOf<String>())

    /** Refusal for the next POST whose path ends with the key ("jobs" or "transitions"), as (http status, code). */
    private val refuse = Collections.synchronizedMap(mutableMapOf<String, Pair<Int, String>>())
    @Volatile private var jobStatus = "DRAFT"

    /** Refuse the n-th POST (1-based) with (http status, code). */
    @Volatile private var refuseOnCall: Pair<Int, Pair<Int, String>>? = null

    private fun job() = """{"id":"$ID1","job_number":"J-7","status":"$jobStatus","machine_id":"$ID2","contract_id":"$ID2","currency":"TZS",
        "hourly_rate":"95000.0000","minimum_hours":"0.0000","mobilization_fee":"0.0000","discount_percent":"0.0000","tax_rate_percent":"0.0000",
        "rate_source":"NEGOTIATED","standby_treatment":"EXCLUDED","planned_start":"2026-10-24T06:00:00Z","version":1}"""

    @Before
    fun setUp() {
        h.server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.url.encodedPath
                fun ok(body: String, code: Int = 200) = MockResponse.Builder().code(code).body(body).build()
                if (request.method != "POST") {
                    gets += "$path?${request.url.query}"
                    return when (path) {
                        "/api/v1/tenant/contracts" -> ok(Samples.page("""{"id":"$ID2","customer_id":"$ID1","contract_number":"C-1","job_site_id":null,
                            "currency":"TZS","status":"ACTIVE","starts_on":"2026-01-01","ends_on":null,"reference":"Katavi road"}"""))
                        "/api/v1/tenant/staff" -> ok(Samples.page("""{"id":"$ID2","full_name":"Juma Katavi","kind":"SUPERVISOR","employee_code":null,
                            "phone":null,"keycloak_subject":null,"is_active":true,"deactivated_at":null,"deactivation_reason":null,"version":1}"""))
                        "/api/v1/tenant/job-sites" -> ok("[]")
                        else -> ok("""{"error":{"code":"NOT_FOUND","message":"no","correlation_id":"c"}}""", 404)
                    }
                }
                val body = request.body!!.utf8()
                posts += Triple(path, body, request.headers["Idempotency-Key"])
                refuseOnCall?.takeIf { it.first == posts.size }?.let { (_, r) ->
                    refuseOnCall = null
                    return ok("""{"error":{"code":"${r.second}","message":"refused","correlation_id":"c"}}""", r.first)
                }
                refuse.keys.firstOrNull { path.endsWith(it) }?.let { key ->
                    val (code, error) = refuse.remove(key)!!
                    return ok("""{"error":{"code":"$error","message":"refused","correlation_id":"c"}}""", code)
                }
                return when {
                    path == "/api/v1/tenant/jobs" -> { jobStatus = "DRAFT"; ok(job(), 201) }
                    path == "/api/v1/tenant/jobs/$ID1/transitions" -> {
                        val action = Json.parseToJsonElement(body).jsonObject["action"]!!.jsonPrimitive.content
                        jobStatus = if (action == "SUBMIT") "PENDING_APPROVAL" else "APPROVED"
                        ok(job())
                    }
                    else -> ok("""{"error":{"code":"NOT_FOUND","message":"no","correlation_id":"c"}}""", 404)
                }
            }
        }
    }

    @After
    fun tearDown() {
        scope.cancel()
        h.close()
    }

    private val start: Instant = Instant.parse("2026-10-24T06:00:00Z")
    private val contract = ContractDto(UUID.fromString(ID2), "C-1", UUID.fromString(ID1), "TZS", "ACTIVE", "2026-01-01", reference = "Katavi road")
    private val machine = MachineDto(UUID.fromString(ID2), "EX-01", "Excavator", "ACTIVE", "OWNED", 2, 1, "2026-01-01T00:00:00Z")
    private val supervisor = StaffDto(UUID.fromString(ID2), "Juma Katavi", "SUPERVISOR", true, 1)

    private fun valid(rateMode: RateMode = RateMode.RATE_CARD, rate: String = "") = JobForm(
        plannedStart = start, contract = contract, jobNumber = " J-7 ", machine = machine, supervisor = supervisor,
        rateMode = rateMode, hourlyRate = rate,
    )

    private var keys = 0
    private val outcomes = mutableListOf<JobCreateOutcome>()
    private val finished get() = outcomes.filterIsInstance<JobCreateOutcome.Done>().map { it.job to it.message }

    private fun model(canApprove: Boolean, form: JobForm = valid()) =
        JobCreateModel(h.data, scope, canApprove, start, onOutcome = { outcomes += it }, newKey = { "key-${++keys}" }).also { m ->
            m.update { form.copy(approveNow = it.approveNow) }
        }

    private fun JobCreateModel.settle() = runBlocking { withTimeout(5_000) { status.first { !it.busy } } }

    private fun body(i: Int): JsonObject = Json.parseToJsonElement(posts[i].second).jsonObject

    @Test
    fun `validation uses the spec wording`() {
        val empty = JobCreateText.errors(JobForm(plannedStart = start, rateMode = RateMode.NEGOTIATED, plannedEnd = start.minusSeconds(60)))
        assertEquals("Choose the customer contract.", empty[JobField.CONTRACT])
        assertEquals("Choose the machine.", empty[JobField.MACHINE])
        assertEquals("Choose the supervisor.", empty[JobField.SUPERVISOR])
        assertEquals("Enter the hourly rate.", empty[JobField.HOURLY_RATE])
        assertEquals("The planned end is before the planned start.", empty[JobField.PLANNED_END])
        assertEquals("Enter the job number.", empty[JobField.JOB_NUMBER])
        assertTrue(JobCreateText.errors(valid()).isEmpty())
        assertEquals("Enter the hourly rate.", JobCreateText.errors(valid(RateMode.NEGOTIATED, "0"))[JobField.HOURLY_RATE])
        assertTrue(JobCreateText.errors(valid(RateMode.NEGOTIATED, "120000")).isEmpty())
        assertEquals("Hourly rate (TZS)", JobCreateText.rateLabel(contract.currency))
        assertEquals("C-1 · Katavi road", JobCreateText.contractLabel(contract))
        assertEquals("EX-01 · Excavator", JobCreateText.machineLabel(machine))
        assertEquals("The job number is at most 32 characters.", JobCreateText.errors(valid().copy(jobNumber = "J".repeat(33)))[JobField.JOB_NUMBER])
        assertTrue(JobCreateText.errors(valid().copy(jobNumber = " ${"J".repeat(32)} ")).isEmpty())
        assertEquals("Enter the minimum hours as a number.", JobCreateText.errors(valid().copy(minimumHours = "1.2.3"))[JobField.MINIMUM_HOURS])
        assertTrue(JobCreateText.errors(valid().copy(minimumHours = "0")).isEmpty())
        assertEquals("The planned end is before the planned start.", JobCreateText.errors(valid().copy(plannedEnd = start))[JobField.PLANNED_END])
        assertEquals("Choose an active contract.", JobCreateText.message("CONTRACT_NOT_ACTIVE", "x"))
        assertEquals("The chosen supervisor is inactive; choose an active staff member.", JobCreateText.message("STAFF_INACTIVE", "x"))
        assertEquals("server words", JobCreateText.message("SOMETHING", "server words"))
    }

    @Test
    fun `an invalid form sends nothing`() {
        val m = model(canApprove = true, form = valid().copy(machine = null))
        m.submit()
        assertTrue(m.status.value.showErrors)
        assertTrue(posts.isEmpty())
    }

    @Test
    fun `approve now creates, submits and approves with one key per step and tells who was assigned`() {
        val m = model(canApprove = true, form = valid(RateMode.NEGOTIATED, "120000.50").copy(minimumHours = "4", plannedEnd = start.plusSeconds(3600)))
        assertTrue(m.form.value.approveNow)
        m.submit()
        m.settle()
        assertEquals(listOf("/api/v1/tenant/jobs", "/api/v1/tenant/jobs/$ID1/transitions", "/api/v1/tenant/jobs/$ID1/transitions"), posts.map { it.first })
        val create = body(0)
        assertEquals(ID2, create["contract_id"]!!.jsonPrimitive.content)
        assertEquals("J-7", create["job_number"]!!.jsonPrimitive.content)
        assertEquals(ID2, create["machine_id"]!!.jsonPrimitive.content)
        assertEquals(ID2, create["supervisor_id"]!!.jsonPrimitive.content)
        assertEquals("2026-10-24T06:00:00Z", create["planned_start"]!!.jsonPrimitive.content)
        assertEquals("2026-10-24T07:00:00Z", create["planned_end"]!!.jsonPrimitive.content)
        assertEquals("120000.5", create["hourly_rate"]!!.jsonPrimitive.content)
        assertEquals("4", create["minimum_hours"]!!.jsonPrimitive.content)
        assertEquals(JsonPrimitive("EXCLUDED"), create["standby_treatment"])
        assertEquals(JsonPrimitive("0"), create["mobilization_fee"])
        assertFalse("no site chosen: the contract's default", "job_site_id" in create)
        assertEquals("SUBMIT", body(1)["action"]!!.jsonPrimitive.content)
        assertEquals("APPROVE", body(2)["action"]!!.jsonPrimitive.content)
        assertFalse("hourly_rate" in body(2))
        assertEquals(listOf("key-1", "key-2", "key-3"), posts.map { it.third })
        val (job, message) = finished.single()
        assertEquals("APPROVED", job.status)
        assertEquals("Job J-7 created and assigned to Juma Katavi.", message)
    }

    @Test
    fun `rate card sends no hourly rate and approve off only sends for approval`() {
        val m = model(canApprove = true)
        m.setPlannedEnd(true)
        assertEquals(start.plusSeconds(8 * 3600), m.form.value.plannedEnd)
        m.setPlannedEnd(false)
        assertNull(m.form.value.plannedEnd)
        m.update { it.copy(approveNow = false) }
        assertEquals("Create", JobCreateText.primary(m.form.value.approveNow))
        m.submit()
        m.settle()
        assertEquals(2, posts.size)
        assertFalse("hourly_rate" in body(0))
        assertFalse("minimum_hours" in body(0))
        assertEquals("SUBMIT", body(1)["action"]!!.jsonPrimitive.content)
        assertEquals("Job J-7 created and sent for approval.", finished.single().second)
    }

    @Test
    fun `without tenant job approve there is no approve now`() {
        val m = model(canApprove = false)
        assertFalse(m.form.value.approveNow)
        m.update { it.copy(approveNow = true) } // ignored: the toggle is not offered
        m.submit()
        m.settle()
        assertEquals(listOf("SUBMIT"), (1 until posts.size).map { body(it)["action"]!!.jsonPrimitive.content })
        assertEquals("PENDING_APPROVAL", finished.single().first.status)
        assertEquals("Create and approve", JobCreateText.primary(true))
    }

    @Test
    fun `create refusals are worded and nothing else is sent`() {
        refuse["jobs"] = 422 to "NO_RATE"
        val m = model(canApprove = true)
        m.submit()
        val s = m.settle()
        assertEquals("No rate card applies to this machine; choose Negotiated rate and enter a price.", s.error)
        assertNull(s.created)
        assertEquals(1, posts.size)
        refuse["jobs"] = 409 to "DUPLICATE_JOB"
        m.submit()
        assertEquals("That job number is already used.", m.settle().error)
        // A refused create made nothing, so the corrected retry is a new request with a new key.
        assertEquals(listOf("key-1", "key-4"), posts.map { it.third })
    }

    @Test
    fun `a refused submit or approve ends with the created job and its notice, never a second create`() {
        refuse["transitions"] = 409 to "MACHINE_BUSY"
        val m = model(canApprove = true)
        m.submit()
        m.settle()
        val partly = outcomes.single() as JobCreateOutcome.Partly
        assertEquals("DRAFT", partly.job.status)
        assertEquals(
            "Job J-7 was created but not sent for approval: " +
                "This machine already has an approved or running job; complete or cancel that job first.",
            partly.message,
        )
        assertEquals(2, posts.size)

    }

    @Test
    fun `a refused approve says the job was sent for approval but not approved`() {
        val m = model(canApprove = true)
        // Let create and SUBMIT through, refuse the APPROVE (the third POST).
        refuseOnCall = 3 to (409 to "MACHINE_BUSY")
        m.submit()
        m.settle()
        val partly = outcomes.single() as JobCreateOutcome.Partly
        assertEquals("PENDING_APPROVAL", partly.job.status)
        assertTrue(partly.message.startsWith("Job J-7 was created and sent for approval, but not approved: This machine"))
        assertEquals(listOf("key-1", "key-2", "key-3"), posts.map { it.third })
    }

    @Test
    fun `lookups use the web form endpoints`() = runBlocking {
        val m = model(canApprove = false)
        val contracts = m.searchContracts(" katavi ") as ActionResult.Done
        assertEquals("C-1 · Katavi road", JobCreateText.contractLabel(contracts.value.single()))
        val staff = m.searchSupervisors("") as ActionResult.Done
        assertEquals("Juma Katavi", staff.value.single().fullName)
        assertTrue(m.searchSites("") is ActionResult.Done)
        assertEquals("/api/v1/tenant/contracts?q=katavi&page=1&page_size=20", gets[0])
        assertEquals("/api/v1/tenant/staff?kind=SUPERVISOR&page=1&page_size=20", gets[1])
        assertEquals("/api/v1/tenant/job-sites?null", gets[2])
    }

    @Test
    fun `new job is shown with tenant job write, approve now with tenant job approve`() {
        assertTrue(OwnerFeatures(setOf("tenant.job.write")).createJobs)
        assertFalse(OwnerFeatures(setOf("tenant.job.write")).approveJobs)
        assertFalse(OwnerFeatures(setOf("tenant.job.read", "tenant.job.approve")).createJobs)
        assertTrue(OwnerFeatures(setOf("tenant.geofence.read")).jobSites)
    }
}
