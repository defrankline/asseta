package com.asseta.core.sync

import com.asseta.core.network.NetworkFactory
import com.asseta.core.sync.data.CashToday
import com.asseta.core.sync.data.OnlineResult
import com.asseta.core.sync.data.SupervisorOnline
import com.asseta.core.sync.engine.AccountSwitch
import com.asseta.core.sync.engine.SyncReport
import kotlinx.coroutines.runBlocking
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
import java.time.ZoneOffset

/** Today's cash figures: every successful fetch is saved per tenant and shown again when the server is unreachable. */
@RunWith(RobolectricTestRunner::class)
class SupervisorOnlineTest : SyncTestBase() {
    private val office = MockWebServer()
    private var online = true
    private lateinit var supervisor: SupervisorOnline

    @Before
    fun setUp() {
        office.start()
        val client = NetworkFactory.okHttpClient({ "token" }, { tenant })
        supervisor = SupervisorOnline(
            api = { NetworkFactory.tenantApi(if (online) office.url("/").toString() else "http://127.0.0.1:1/", client, allowCleartext = true) },
            db = { db }, json = json, account = { account }, nowMs = { clock.now },
        )
    }

    @After
    fun tearDown() = office.close()

    private fun reconciliation(currency: String, outstanding: String) = """{"staff_member_id":"${fake.staffId}","currency":"$currency",
        "timezone":"Africa/Lusaka","days":[{"day":"2026-10-21","opening":"0","floats_issued":"0","collections":"$outstanding",
        "approved_spending":"0","verified_handovers":"0","outstanding":"$outstanding","claimed_unverified_handovers":"0",
        "pending_spending":"0","unverified_collections":"0","outstanding_if_claims_verified":"$outstanding"}]}"""

    @Test
    fun aSuccessfulFetchIsSavedAndShownOfflineWithItsTimeAndDay() = runBlocking {
        office.enqueue(MockResponse(code = 200, body = "[${reconciliation("TZS", "1500.0000")}]"))
        office.enqueue(MockResponse(code = 200, body = "[${reconciliation("USD", "20.0000")}]"))
        val fresh = supervisor.todayCash(tenant, listOf("TZS", "USD"), ZoneOffset.UTC)
        assertTrue(fresh is OnlineResult.Fresh)
        assertEquals("date=2026-10-21&currency=TZS", office.takeRequest().url.query)

        online = false
        clock.advance(3_600_000)
        val cached = supervisor.todayCash(tenant, listOf("TZS", "USD"), ZoneOffset.UTC) as OnlineResult.Cached<CashToday>
        assertEquals("2026-10-21", cached.value.date)
        assertEquals(clock.now - 3_600_000, cached.fetchedAtMs)
        assertEquals(listOf("TZS", "USD"), cached.value.reconciliations.map { it.currency })
        assertEquals("20.0000", cached.value.reconciliations[1].days.single().outstanding)
    }

    @Test
    fun nothingSavedMeansUnavailableAndAnotherUserNeverSeesTheFigures() = runBlocking {
        online = false
        assertTrue(supervisor.todayCash(tenant, listOf("TZS"), ZoneOffset.UTC) is OnlineResult.Unavailable)

        online = true
        office.enqueue(MockResponse(code = 200, body = "[${reconciliation("TZS", "1500.0000")}]"))
        assertTrue(supervisor.todayCash(tenant, listOf("TZS"), ZoneOffset.UTC) is OnlineResult.Fresh)
        assertTrue(engine().sync(tenant) is SyncReport.Success) // the tenant's field data now belongs to user A
        account = USER_B
        AccountSwitch { db }.claimAll(USER_B)
        assertNull(db.readSnapshotDao().get(tenant, SupervisorOnline.CASH_TODAY_KEY))
    }
}
