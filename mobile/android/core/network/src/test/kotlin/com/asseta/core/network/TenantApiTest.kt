package com.asseta.core.network

import com.asseta.core.model.owner.ApprovalDecisionIn
import com.asseta.core.model.owner.MeterResetDecisionIn
import kotlinx.coroutines.test.runTest
import mockwebserver3.MockResponse
import mockwebserver3.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test

/** Owner endpoints: paths, tenant header, idempotency on decisions, SoD error envelope, WebSocket protocol frames. */
class TenantApiTest {
    private val server = MockWebServer()
    private val tenant = "a3c1d1f2-1111-4222-8333-944455556666"
    private lateinit var api: TenantApi

    @Before
    fun setUp() {
        server.start()
        api = NetworkFactory.tenantApi(server.url("/").toString(), NetworkFactory.okHttpClient({ "t" }, { tenant }), allowCleartext = true)
    }

    @After
    fun tearDown() = server.close()

    @Test
    fun `decision is sent with tenant and idempotency key and SoD becomes a typed error`() = runTest {
        server.enqueue(
            MockResponse.Builder().code(422).body(
                """{"error":{"code":"SEGREGATION_OF_DUTIES","message":"Submitters cannot approve their own expenses","correlation_id":"cid-1"}}""",
            ).build(),
        )
        try {
            api.decideApproval("a3c1d1f2-1111-4222-8333-944455556667", ApprovalDecisionIn(true, "ok"))
            fail("expected ApiException")
        } catch (e: ApiException) {
            assertEquals("SEGREGATION_OF_DUTIES", e.code)
            assertEquals("cid-1", e.correlationId)
        }
        val request = server.takeRequest()
        assertEquals("/api/v1/tenant/approvals/a3c1d1f2-1111-4222-8333-944455556667/decision", request.url.encodedPath)
        assertEquals(tenant, request.headers[AssetaHeaders.TENANT_ID])
        assertNotNull(request.headers[AssetaHeaders.IDEMPOTENCY_KEY])
        assertTrue(request.body!!.utf8().contains("\"approve\":true"))
    }

    @Test
    fun `history query uses from and to`() = runTest {
        server.enqueue(MockResponse.Builder().body("""{"machine_id":"$tenant","points":[],"stops":[],"site_visits":[],"distance_km":0.0,"truncated":false,"policy_version":"p"}""").build())
        api.machineHistory(tenant, "2026-10-21T08:00:00Z", "2026-10-22T08:00:00Z")
        val url = server.takeRequest().url
        assertEquals("2026-10-21T08:00:00Z", url.queryParameter("from"))
        assertEquals("2026-10-22T08:00:00Z", url.queryParameter("to"))
    }

    @Test
    fun `meter reset decision, filtered lists and cash period queries`() = runTest {
        server.enqueue(MockResponse.Builder().code(409).body("""{"error":{"code":"RESET_DECIDED","message":"Reset already decided","correlation_id":"c"}}""").build())
        try {
            api.decideMeterReset(tenant, MeterResetDecisionIn(MeterResetDecisionIn.APPROVE, "Meter replaced"))
            fail("expected ApiException")
        } catch (e: ApiException) {
            assertEquals("RESET_DECIDED", e.code)
        }
        val decision = server.takeRequest()
        assertEquals("/api/v1/tenant/meter-resets/$tenant/decision", decision.url.encodedPath)
        assertEquals("""{"outcome":"EXPLAINED","note":"Meter replaced"}""", decision.body!!.utf8())
        server.enqueue(MockResponse.Builder().body("[]").build())
        api.cashSupervisorSummary("2026-10-01", "2026-10-22")
        val cash = server.takeRequest().url
        assertEquals("/api/v1/tenant/cash/supervisor-summary", cash.encodedPath)
        assertEquals("2026-10-01", cash.queryParameter("from"))
        assertEquals("2026-10-22", cash.queryParameter("to"))
        server.enqueue(MockResponse.Builder().body("""{"items":[],"total":0,"page":1,"page_size":100}""").build())
        api.fuelEvents(jobId = tenant, pageSize = 100)
        val fuel = server.takeRequest().url
        assertEquals(tenant, fuel.queryParameter("job_id"))
        assertEquals("100", fuel.queryParameter("page_size"))
    }

    @Test
    fun `realtime frames`() {
        val json = NetworkFactory.json
        assertEquals("asseta.v1, bearer.abc", RealtimeProtocol.protocolHeader("abc"))
        assertTrue(RealtimeProtocol.subscribe(tenant).contains("\"tenantId\":\"$tenant\""))
        assertEquals(RealtimeEvent.Connected(4), RealtimeProtocol.parse("""{"type":"auth_ok","payload":{"unread_count":4}}""", json))
        assertEquals(RealtimeEvent.UnreadCount(2), RealtimeProtocol.parse("""{"type":"unread_count","payload":{"count":2}}""", json))
        assertEquals(
            RealtimeEvent.EntityChanged("alert", tenant, "created"),
            RealtimeProtocol.parse("""{"type":"entity.changed","payload":{"entity":"alert","id":"$tenant","action":"created"}}""", json),
        )
        assertEquals(RealtimeEvent.Ping, RealtimeProtocol.parse("""{"type":"ping"}""", json))
        assertEquals(null, RealtimeProtocol.parse("""{"type":"future_thing"}""", json))
        assertEquals(null, RealtimeProtocol.parse("not json", json))
        assertTrue(RealtimeProtocol.isFatalClose(4403))
        val n = RealtimeProtocol.parse(
            """{"type":"notification","payload":{"id":"$tenant","type":"TRACKING_ALERT","category":"ANOMALY","severity":"CRITICAL",
               "priority":"HIGH","title":"t","body":"b","created_at":"2026-10-22T08:00:00Z","read_at":null,"target":null,"tenant_id":"$tenant","data":{}}}""",
            json,
        ) as RealtimeEvent.Notification
        assertEquals("CRITICAL", n.notification.severity)
    }
}
