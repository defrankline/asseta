package com.asseta.owner

import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.owner.ui.OwnerFeatures
import com.asseta.owner.ui.common.ScreenState
import com.asseta.owner.ui.settings.ClosurePresentation
import com.asseta.owner.ui.settings.ClosureTexts
import com.asseta.owner.ui.settings.CompanyClosureViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import kotlinx.coroutines.withTimeout
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/** Owner app: the closure request behind the home banner (read-only) and "Cancel closure" with a reason. */
@OptIn(ExperimentalCoroutinesApi::class)
class CompanyClosureOwnerTest {
    private val h = OwnerHarness()

    @Before fun setUp() = Dispatchers.setMain(Dispatchers.Unconfined)

    @After fun tearDown() {
        Dispatchers.resetMain()
        h.close()
    }

    private fun <T> StateFlow<ScreenState<T>>.settled(): ScreenState<T> = runBlocking { withTimeout(5_000) { first { !it.loading } } }
    private fun <T> StateFlow<T>.await(predicate: (T) -> Boolean): T = runBlocking { withTimeout(5_000) { first(predicate) } }

    private fun request(status: String = "REQUESTED", cancel: String = "") = """{"id":"$ID1","tenant_id":"$TENANT","tenant_name":"Acme Hire",
        "status":"$status","reason":"Selling the business","requested_by":"$ID2","requested_by_name":"Asha Owner",
        "requested_at":"2026-11-12T08:00:00Z","waiting_days":30,"scheduled_for":"2026-12-12T08:00:00Z","policy_version":"1",
        "attempts":0,"steps_done":[]$cancel}"""

    private fun status(req: String? = request()) = """{"tenant_id":"$TENANT","company_name":"Acme Hire","waiting_days":30,"request":${req ?: "null"}}"""

    @Test
    fun `shows the request read-only and only a requested closure can be cancelled`() {
        h.ok(status())
        val vm = CompanyClosureViewModel(h.data)
        val r = vm.state.settled().data!!.request!!
        assertEquals("Asha Owner", r.requestedByName)
        assertEquals("2026-12-12T08:00:00Z", r.scheduledFor)
        assertEquals("Requested", ClosureTexts.status(r.status))
        assertTrue(ClosurePresentation.canCancel(r))
        assertFalse(ClosurePresentation.canCancel(r.copy(status = "IN_PROGRESS")))
        assertFalse(ClosurePresentation.canCancel(null))
        assertEquals("Deletion in progress", ClosureTexts.status("IN_PROGRESS"))
        assertEquals("/api/v1/tenant/company/deletion-request", h.server.takeRequest().url.encodedPath)
    }

    @Test
    fun `no request reads as none`() {
        h.ok(status(null))
        assertNull(CompanyClosureViewModel(h.data).state.settled().data!!.request)
    }

    @Test
    fun `cancel needs a reason and a connection, then refreshes the profile`() {
        h.ok(status())
        val vm = CompanyClosureViewModel(h.data)
        vm.state.settled()
        h.server.takeRequest()
        var refreshed = 0
        vm.cancel("  ", online = true) { refreshed++ }
        assertEquals(ClosureTexts.REASON_TOO_SHORT, vm.error.value)
        vm.cancel("Changed our mind", online = false) { refreshed++ }
        assertEquals(ClosureTexts.OFFLINE, vm.error.value)
        assertEquals(0, h.server.requestCount - 1)

        h.ok(request("CANCELLED", ""","cancelled_by_name":"Asha Owner","cancel_reason":"Changed our mind""""))
        vm.cancel("  Changed our mind ", online = true) { refreshed++ }
        vm.message.await { it == ClosureTexts.CANCELLED }
        val sent = h.server.takeRequest()
        assertEquals("/api/v1/tenant/company/deletion-request/cancel", sent.url.encodedPath)
        assertEquals("""{"reason":"Changed our mind"}""", sent.body!!.utf8())
        assertEquals(TENANT, sent.headers["X-Tenant-ID"])
        assertEquals(1, refreshed)
        assertEquals("CANCELLED", vm.state.value.data!!.request!!.status)
        assertNull(vm.error.value)
    }

    @Test
    fun `a refusal shows the server message`() {
        h.ok(status())
        val vm = CompanyClosureViewModel(h.data)
        vm.state.settled()
        h.error(409, "DELETION_STARTED", "The deletion has already started")
        vm.cancel("Changed our mind", online = true)
        assertEquals("The deletion has already started", vm.error.await { it != null })
    }

    @Test
    fun `the closure screen is reachable only with the close permission`() {
        val owner = OwnerFeatures(setOf("tenant.company.close"))
        assertTrue(owner.closeCompany)
        assertEquals(OwnerDestination.CompanyClosure, owner.route(OwnerDestination.CompanyClosure))
        assertEquals(OwnerDestination.Home, OwnerFeatures(setOf("tenant.fleet.read")).route(OwnerDestination.CompanyClosure))
    }
}
