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
    fun `job detail is one snapshot of summary readings and acknowledgements`() = runBlocking {
        h.ok("""{"job":{"id":"$ID1","job_number":"J-1001","status":"COMPLETED","machine_id":"$ID2","contract_id":"$ID2","currency":"TZS",
            "hourly_rate":"95000.0000","minimum_hours":"0.0000","mobilization_fee":"0.0000","discount_percent":"0.0000","tax_rate_percent":"15.0000",
            "rate_source":"CONTRACT","standby_treatment":"EXCLUDED","planned_start":"2026-10-21T06:00:00Z","version":3,"standby_rate":null,
            "planned_end":null,"started_at":null,"completed_at":null,"approved_at":null,"job_site_id":null,"supervisor_id":null},
            "opening_reading":"1200.00","closing_reading":"1210.00","meter_hours":"10.0000","billable_hours":"10.0000","nonbillable_hours":"0.0000",
            "billing_ready":true,"open_exceptions":0,"blocking_exceptions":0,"policy_version":"p"}""")
        h.ok("[]")
        h.ok("""[{"id":"$ID1","method":"SIGNATURE","signer_name":"Site manager","captured_at":"2026-10-21T18:00:00Z","acknowledged_hours":"10.0000",
            "signer_phone":null,"signature_attachment_id":null}]""")
        val ok = h.data.job(ID1) as Load.Ok
        assertEquals("Site manager", ok.snapshot.data.acknowledgements.single().signerName)
        assertEquals(0, java.math.BigDecimal("10").compareTo(ok.snapshot.data.summary.billableHours!!.value))
        assertTrue(h.store.rows.containsKey(TENANT to "job:$ID1"))
    }
}
