package com.asseta.owner

import com.asseta.core.domain.owner.DataSource
import com.asseta.core.domain.owner.FailureKind
import com.asseta.owner.data.ActionResult
import com.asseta.owner.data.Load
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** Server-first reads with the bounded offline fallback, and the online-only mutations. */
class OwnerRepositoryTest {
    private val h = OwnerHarness()

    @After
    fun tearDown() = h.close()

    @Test
    fun `live read is cached and served stale when offline`() = runBlocking {
        h.ok(Samples.OVERVIEW)
        val live = h.data.overview() as Load.Ok
        assertEquals(DataSource.LIVE, live.snapshot.source)
        val fetchedAt = h.now
        h.goOffline()
        h.now += 3_600_000
        val cached = h.data.overview() as Load.Ok
        assertEquals(DataSource.CACHE, cached.snapshot.source)
        assertTrue(cached.snapshot.stale)
        assertEquals(fetchedAt, cached.snapshot.fetchedAtMs)
        assertEquals(1, cached.snapshot.data.work!!.pendingApprovals)
    }

    @Test
    fun `cache older than seven days is never shown`() = runBlocking {
        h.ok(Samples.OVERVIEW)
        h.data.overview()
        h.goOffline()
        h.now += 8L * 86_400_000
        val failed = h.data.overview() as Load.Failed
        assertEquals(FailureKind.NETWORK, failed.kind)
        assertTrue(failed.error.message.startsWith("Cannot reach Asseta"))
    }

    @Test
    fun `server errors are not masked by cached data`() = runBlocking {
        h.ok(Samples.OVERVIEW)
        h.data.overview()
        h.error(500, "INTERNAL", "boom")
        val failed = h.data.overview() as Load.Failed
        assertEquals(FailureKind.SERVER, failed.kind)
        assertEquals("cid-500", failed.error.reference)
    }

    @Test
    fun `tenant revocation wipes that tenant's snapshots`() = runBlocking {
        h.ok(Samples.OVERVIEW)
        h.data.overview()
        h.store.rows[("other-tenant" to "overview")] = h.store.rows.values.first()
        h.error(403, "TENANT_ACCESS_DENIED")
        assertTrue(h.data.overview() is Load.Failed)
        assertEquals(listOf(TENANT), h.events.revoked)
        assertTrue(h.store.rows.keys.none { it.first == TENANT })
        assertEquals(1, h.store.rows.size)
    }

    @Test
    fun `unauthenticated ends the session`() = runBlocking {
        h.error(401, "NOT_AUTHENTICATED")
        assertTrue(h.data.fleet() is Load.Failed)
        assertEquals(1, h.events.ended)
    }

    @Test
    fun `segregation of duties refusal keeps its code and explanation`() = runBlocking {
        h.error(422, "SEGREGATION_OF_DUTIES", "Submitters cannot approve their own expenses")
        val r = h.data.decideApproval(ID1, true, null) as ActionResult.Refused
        assertEquals("SEGREGATION_OF_DUTIES", r.code)
        assertTrue(r.error.message.startsWith("Segregation of duties"))
        assertEquals(false, r.reload)
        val body = h.server.takeRequest().body!!.utf8()
        assertEquals("""{"approve":true}""", body)
    }

    @Test
    fun `mutations never fall back offline`() = runBlocking {
        h.goOffline()
        val r = h.data.acknowledgeAlert(ID1) as ActionResult.Refused
        assertEquals(null, r.code)
        assertTrue(h.store.rows.isEmpty())
    }

    @Test
    fun `exceptions, field spend and cash are cached per filter`() = runBlocking {
        h.ok(Samples.page())
        h.data.exceptions("OPEN")
        h.ok(Samples.page())
        h.data.exceptions(null)
        h.ok(Samples.page())
        h.data.expenses("PENDING_APPROVAL")
        h.ok(Samples.page())
        h.data.fuel()
        h.ok("[]")
        h.data.cash("WEEK", java.time.LocalDate.parse("2026-10-16"), java.time.LocalDate.parse("2026-10-22"))
        h.ok("[]")
        h.data.meterResets("PENDING")
        assertEquals(
            setOf("exceptions:OPEN", "exceptions:ALL", "expenses:PENDING", "fuel:ALL", "cash:WEEK", "meter_resets:PENDING"),
            h.store.rows.keys.map { it.second }.toSet(),
        )
        val first = h.server.takeRequest().url
        assertEquals("OPEN", first.queryParameter("status"))
        assertEquals(null, first.queryParameter("job_id"))
        assertEquals(null, h.server.takeRequest().url.queryParameter("status"))
        assertEquals("PENDING_APPROVAL", h.server.takeRequest().url.queryParameter("status"))
        h.server.takeRequest()
        assertEquals("2026-10-16", h.server.takeRequest().url.queryParameter("from"))
        assertEquals("PENDING", h.server.takeRequest().url.queryParameter("status"))
    }

    @Test
    fun `meter reset decision sends the outcome and note`() = runBlocking {
        h.ok(Samples.reset(ID1, "APPROVED"))
        val r = h.data.decideMeterReset(ID1, approve = true, note = "  Meter replaced  ") as ActionResult.Done
        assertEquals("APPROVED", r.value.status)
        assertEquals("""{"outcome":"EXPLAINED","note":"Meter replaced"}""", h.server.takeRequest().body!!.utf8())
        h.error(422, "SEGREGATION_OF_DUTIES", "Requester cannot approve their own reset")
        val refused = h.data.decideMeterReset(ID1, approve = false, note = "Wrong reading") as ActionResult.Refused
        assertEquals("SEGREGATION_OF_DUTIES", refused.code)
        assertEquals("""{"outcome":"CONFIRMED","note":"Wrong reading"}""", h.server.takeRequest().body!!.utf8())
        h.error(409, "RESET_DECIDED", "Reset already decided")
        val decided = h.data.decideMeterReset(ID1, approve = true, note = "Meter replaced") as ActionResult.Refused
        assertEquals("This reset was already decided.", decided.error.message)
        assertTrue(decided.reload)
    }
}
