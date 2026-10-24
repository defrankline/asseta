package com.asseta.core.sync

import com.asseta.core.domain.jobs.JobRequestRules
import com.asseta.core.domain.jobs.JobRequestState
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.network.NetworkFactory
import com.asseta.core.sync.data.FieldOutbox
import com.asseta.core.sync.engine.SyncReport
import com.asseta.core.sync.usecase.FinanceResult
import com.asseta.core.sync.usecase.JobRequestInput
import com.asseta.core.sync.usecase.JobRequests
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonObject
import mockwebserver3.MockResponse
import mockwebserver3.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import java.util.UUID

/** Job requests from the field: offline lookups, the queued JOB_REQUEST and how it shows until the owner decides. */
@RunWith(RobolectricTestRunner::class)
class JobRequestsTest : SyncTestBase() {
    private val office = MockWebServer()
    private var online = true
    private var queued = 0
    private lateinit var requests: JobRequests

    @Before
    fun setUp() {
        office.start()
        val client = NetworkFactory.okHttpClient({ "token" }, { tenant })
        requests = JobRequests(
            api = { NetworkFactory.tenantApi(if (online) office.url("/").toString() else "http://127.0.0.1:1/", client, allowCleartext = true) },
            db = { db }, outbox = FieldOutbox({ db }, json, clock, { account }), json = json, account = { account },
            nowMs = { clock.now }, onQueued = { queued++ },
        )
        fake.handler = { op ->
            if (op["op_type"]!!.jsonPrimitive.content == "JOB_REQUEST") {
                val payload = op["payload"]!!.jsonObject
                "ACKED" to buildJsonObject {
                    putJsonObject("entity") {
                        put("id", payload["client_id"]!!.jsonPrimitive.content); put("job_number", "J-2026-105")
                        put("status", "PENDING_APPROVAL"); put("version", 1)
                    }
                }
            } else null
        }
    }

    @After
    fun tearDown() = office.close()

    private val contracts = """[{"id":"${fake.contractId}","contract_number":"CT-01","customer_id":"${fake.customerId}",
        "customer_name":"Road Builders Ltd","job_site_id":"99999999-9999-4999-8999-999999999999","job_site_name":"Katavi quarry",
        "currency":"TZS","starts_on":"2026-01-01T00:00:00Z","ends_on":null,"reference":null}]"""
    private val machines = """[{"id":"${fake.machineId}","asset_code":"EX-01","name":"Excavator 01","meter_decimal_places":1,
        "status":"ACTIVE","version":1,"ownership":"OWNED","created_at":"2026-01-01T00:00:00Z"}]"""

    private fun input(clientId: String = UUID.randomUUID().toString(), contract: String? = fake.contractId, machine: String? = fake.machineId,
        end: Long? = null, note: String = "Dig the north trench") =
        JobRequestInput(tenant, clientId, contract, machine, null, clock.now, end, note)

    @Test
    fun lookupsComeFromTheServerAndStayOnThePhoneForOfflineUse() = runBlocking {
        office.enqueue(MockResponse(code = 200, body = contracts))
        office.enqueue(MockResponse(code = 200, body = machines))
        val fresh = requests.refreshLookups(tenant)
        assertEquals("/api/v1/tenant/field/contracts", office.takeRequest().url.encodedPath)
        assertEquals("/api/v1/tenant/field/machines", office.takeRequest().url.encodedPath)
        assertEquals("Road Builders Ltd", fresh.contracts.single().customerName)
        assertEquals("Katavi quarry", fresh.sites.single().name)
        assertEquals(clock.now, fresh.fetchedAtMs)

        online = false
        clock.advance(60_000)
        val saved = requests.refreshLookups(tenant)
        assertEquals(listOf("CT-01"), saved.contracts.map { it.contractNumber })
        assertEquals(listOf("EX-01"), saved.machines.map { it.assetCode })
        assertEquals(clock.now - 60_000, saved.fetchedAtMs)
    }

    @Test
    fun withoutSavedListsTheSyncedContractsAndMachinesAreOffered() = runBlocking {
        assertTrue(engine().sync(tenant) is SyncReport.Success)
        online = false
        val lookups = requests.refreshLookups(tenant)
        assertEquals("Road Builders Ltd", lookups.contracts.single().customerName)
        assertEquals("EX-01", lookups.machines.single().assetCode)
        assertNull(lookups.fetchedAtMs)
    }

    @Test
    fun requestsNeedOneSyncWithAServerThatAcceptsThem() = runBlocking {
        assertEquals(FinanceResult.Blocked("Sync once while online before requesting a job."), requests.request(input()))
        fake.capabilities = listOf("SUPERVISOR_INBOX_V1")
        assertTrue(engine().sync(tenant) is SyncReport.Success)
        assertEquals(FinanceResult.Blocked("Your company's server does not accept job requests yet."), requests.request(input()))
        assertEquals(0, queued)
    }

    @Test
    fun anIncompleteFormIsRefused() = runBlocking {
        assertTrue(engine().sync(tenant) is SyncReport.Success)
        val r = requests.request(input(contract = null, machine = null, end = clock.now - 1, note = "x".repeat(1001)))
        assertEquals(
            listOf("Choose the customer contract.", "Choose the machine.", "The planned end is before the planned start.",
                "What the customer asked for: at most 1000 characters."),
            (r as FinanceResult.Invalid).messages,
        )
        assertEquals(0, queued)
    }

    @Test
    fun aRequestIsQueuedOfflineOnceAndShowsTheServerJobNumberAfterSync() = runBlocking {
        assertTrue(engine().sync(tenant) is SyncReport.Success)
        val clientId = UUID.randomUUID().toString()
        val saved = requests.request(input(clientId)) as FinanceResult.Saved
        assertEquals(FinanceResult.AlreadySaved, requests.request(input(clientId)))
        assertEquals(1, queued)
        val pending = requests.observe(tenant).first().single()
        assertEquals(clientId, pending.clientId)
        assertEquals(ClientOperationStatus.PENDING, pending.operationStatus)
        assertEquals(JobRequestState.NOT_SENT, JobRequestRules.state(pending.operationStatus, null))
        assertNull(pending.jobNumber)

        assertTrue(engine().sync(tenant) is SyncReport.Success)
        val sent = fake.stored.getValue(saved.operationId).payload
        assertEquals(clientId, sent["client_id"]!!.jsonPrimitive.content)
        assertEquals(fake.contractId, sent["contract_id"]!!.jsonPrimitive.content)
        assertEquals("2026-10-21T08:00:00Z", sent["planned_start"]!!.jsonPrimitive.content)
        assertEquals("Dig the north trench", sent["note"]!!.jsonPrimitive.content)
        assertNull(sent["planned_end"])
        val accepted = requests.observe(tenant).first().single()
        assertEquals("J-2026-105", accepted.jobNumber)
        assertEquals(JobRequestState.WAITING, JobRequestRules.state(accepted.operationStatus, null))
    }

    @Test
    fun aDeclinedRequestKeepsTheOwnersReason() = runBlocking {
        assertTrue(engine().sync(tenant) is SyncReport.Success)
        val clientId = UUID.randomUUID().toString()
        requests.request(input(clientId))
        assertTrue(engine().sync(tenant) is SyncReport.Success)
        fake.changesJobs = listOf(
            buildJsonObject {
                fake.job("CANCELLED", 2, clientId).forEach { (k, v) -> put(k, v) }
                put("cancellation_reason", "Customer has no budget this month")
                put("requested_by_staff_id", fake.staffId); put("request_note", "Dig the north trench")
            },
        )
        assertTrue(engine().sync(tenant) is SyncReport.Success)
        val job = repository.job(clientId)!!
        assertEquals("Customer has no budget this month", job.cancellationReason)
        assertEquals("Dig the north trench", job.requestNote)
        assertEquals(JobRequestState.DECLINED, JobRequestRules.state(ClientOperationStatus.ACKED, job.status))
    }
}
