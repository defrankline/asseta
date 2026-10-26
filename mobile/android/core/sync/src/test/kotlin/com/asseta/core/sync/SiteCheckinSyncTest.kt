package com.asseta.core.sync

import com.asseta.core.domain.accountability.FieldAccess
import com.asseta.core.domain.capture.GpsOutcome
import com.asseta.core.model.ClientOperationStatus.ACKED
import com.asseta.core.model.ClientOperationStatus.CONFLICT
import com.asseta.core.model.TenantAccess
import com.asseta.core.model.sync.AccountabilityOps
import com.asseta.core.model.sync.SyncCapabilities
import com.asseta.core.network.NetworkFactory
import com.asseta.core.sync.data.FieldAccountabilityData
import com.asseta.core.sync.data.FieldOps
import com.asseta.core.sync.data.FieldOutbox
import com.asseta.core.sync.engine.SyncReport
import com.asseta.core.sync.usecase.AccountabilityCapture
import com.asseta.core.sync.usecase.FinanceResult
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonObject
import mockwebserver3.MockResponse
import mockwebserver3.MockWebServer
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

/** Site check-ins through the outbox (SITE_CHECKIN, DEC-031 M3) and the saved schedule (GET /site-checkins/mine). */
@RunWith(RobolectricTestRunner::class)
class SiteCheckinSyncTest : SyncTestBase() {
    private lateinit var accountability: AccountabilityCapture
    private val perms = setOf(FieldAccess.SITE_CHECKIN_RECORD)
    private val fix = GpsOutcome.Fix(-6.8, 39.28, 8.0, Instant.parse("2026-10-21T08:00:05Z"), "fused")

    @Before
    fun setUp() {
        val outbox = FieldOutbox({ db }, json, clock, { account })
        accountability = AccountabilityCapture({ db }, repository, financeRepository, outbox, files, json)
        fake.capabilities = listOf(SyncCapabilities.SUPERVISOR_INBOX_V1, SyncCapabilities.OP_SITE_CHECKIN)
    }

    private fun synced() = runBlocking { assertTrue(engine().sync(tenant) is SyncReport.Success) }

    private fun data(base: String) = FieldAccountabilityData(
        api = { NetworkFactory.tenantApi(base, NetworkFactory.okHttpClient({ "token" }, { null }, device = { DEVICE }), allowCleartext = true) },
        db = { db }, json = json, account = { account },
    )

    @Test
    fun checkinIsQueuedOnceWithItsGpsAndAcked() = runBlocking {
        synced()
        val clientId = UUID.randomUUID().toString()
        val first = accountability.siteCheckin(tenant, clientId, clock.now, fix)
        assertTrue("expected Saved but was $first", first is FinanceResult.Saved)
        assertEquals(FinanceResult.AlreadySaved, accountability.siteCheckin(tenant, clientId, clock.now, fix))
        val opId = (first as FinanceResult.Saved).operationId
        val op = op(opId)
        assertEquals(AccountabilityOps.SITE_CHECKIN, op.opType)
        assertEquals(FieldOps.SITE_CHECKIN, op.entityType)
        val payload = json.parseToJsonElement(op.payloadJson).jsonObject
        assertEquals(clientId, payload["client_id"]!!.jsonPrimitive.content)
        assertEquals("FIX", payload["gps"]!!.jsonObject["status"]!!.jsonPrimitive.content)
        assertFalse(payload.containsKey("job_site_id") && payload["job_site_id"].toString() != "null")

        fake.handler = { o ->
            if (o["op_type"]!!.jsonPrimitive.content == AccountabilityOps.SITE_CHECKIN) {
                "ACKED" to buildJsonObject { putJsonObject("entity") { put("id", UUID.randomUUID().toString()) } }
            } else {
                null
            }
        }
        synced()
        assertEquals(ACKED, status(opId))
    }

    @Test
    fun failedGpsIsSentWithoutCoordinatesAndConflictKeepsTheCode() = runBlocking {
        synced()
        val saved = accountability.siteCheckin(tenant, UUID.randomUUID().toString(), clock.now, GpsOutcome.Timeout) as FinanceResult.Saved
        val gps = json.parseToJsonElement(op(saved.operationId).payloadJson).jsonObject["gps"]!!.jsonObject
        assertEquals("TIMEOUT", gps["status"]!!.jsonPrimitive.content)
        assertTrue(gps["latitude"] == null || gps["latitude"].toString() == "null")
        fake.handler = { o ->
            if (o["op_type"]!!.jsonPrimitive.content == AccountabilityOps.SITE_CHECKIN) {
                "CONFLICT" to buildJsonObject { put("error", fake.err("SITE_CHECKIN_DISABLED")) }
            } else {
                null
            }
        }
        engine().sync(tenant)
        val op = op(saved.operationId)
        assertEquals(CONFLICT, op.status)
        assertEquals("SITE_CHECKIN_DISABLED", op.errorCode)
    }

    @Test
    fun withoutTheCapabilityTheCheckinIsBlocked() = runBlocking {
        fake.capabilities = listOf(SyncCapabilities.SUPERVISOR_INBOX_V1)
        synced()
        assertTrue(accountability.siteCheckin(tenant, UUID.randomUUID().toString(), clock.now, fix) is FinanceResult.Blocked)
        assertFalse(data("http://127.0.0.1:1/").access(tenant, perms).siteCheckin)
    }

    @Test
    fun scheduleIsSavedForOfflineAndKeptWhenTheReadFails() = runBlocking {
        synced()
        val api = MockWebServer()
        api.start()
        try {
            api.enqueue(
                MockResponse(
                    code = 200,
                    body = """{"required":true,"times":["08:00","14:00"],"window_minutes":60,"max_distance_m":300,"timezone":"Africa/Dar_es_Salaam",
                        "day_from":"2026-10-15","day_to":"2026-10-21","slots":[{"scheduled_at":"2026-10-21T05:00:00Z","window_minutes":60,"status":"MADE"}],
                        "checkins":[]}""",
                ),
            )
            val online = data(api.url("/").toString())
            assertTrue(online.access(tenant, perms).siteCheckin)
            assertTrue(online.refreshSiteCheckins(tenant, perms))
            assertEquals("/api/v1/tenant/site-checkins/mine", api.takeRequest().url.encodedPath)
            assertEquals(300, online.cache.value.siteCheckins!!.maxDistanceM)

            // A new process offline: the saved copy is read back, and a failed read keeps it.
            val offline = data("http://127.0.0.1:1/")
            assertFalse(offline.refreshSiteCheckins(tenant, perms))
            assertEquals(1, offline.cache.value.siteCheckins!!.slots.size)
            assertTrue(offline.cache.value.siteCheckinsAtMs > 0)

            // Switched off: nothing is read or kept.
            offline.setDisabledCapabilities(tenant, listOf(TenantAccess.SITE_CHECKIN))
            assertFalse(offline.refreshSiteCheckins(tenant, perms))
            assertNull(offline.cache.value.siteCheckins)
        } finally {
            api.close()
        }
    }
}
