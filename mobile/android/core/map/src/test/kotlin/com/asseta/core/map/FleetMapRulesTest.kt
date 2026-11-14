package com.asseta.core.map

import com.asseta.core.domain.owner.Connectivity
import com.asseta.core.model.owner.MachineMapDto
import kotlinx.coroutines.test.runTest
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import retrofit2.HttpException
import retrofit2.Response
import java.util.UUID

/** Same cases as iOS `FleetMapRulesTests`. */
class FleetMapRulesTest {
    private fun machine(code: String, lat: Double? = -6.8, lon: Double? = 39.2, connectivity: String = "RECENT", isLive: Boolean = false) =
        MachineMapDto(
            machineId = UUID.randomUUID(), assetCode = code, name = "Excavator $code", machineStatus = "ACTIVE",
            connectivity = connectivity, isLive = isLive, observedEngine = "OFF", observedMotion = "STOPPED",
            reportedWorkStatus = "WORKING", locationCompliance = "UNKNOWN", openAlerts = 0, policyVersion = "1",
            latitude = lat, longitude = lon, lastSeenAgeSeconds = 300,
        )

    private fun http(code: Int) = HttpException(Response.error<Any>(code, "{}".toResponseBody(null)))

    @Test
    fun `switch shows only with tenant fleet read`() {
        assertTrue(FleetMapRules.canShowMap(setOf("tenant.meter.write", "tenant.fleet.read")))
        assertFalse(FleetMapRules.canShowMap(setOf("tenant.meter.write", "tenant.job.request")))
        assertFalse(FleetMapRules.canShowMap(emptySet()))
    }

    @Test
    fun `offline never calls the server`() = runTest {
        var calls = 0
        val state = FleetMapRules.load(online = false, nowMs = { 0L }) { calls++; listOf(machine("EX-1")) }
        assertEquals(FleetMapRules.State.Offline, state)
        assertEquals(0, calls)
    }

    @Test
    fun `online loads every machine the server returns`() = runTest {
        // Scope ALL: machines that are not in the phone's "My machines" list are shown too (no client-side filter).
        val server = listOf(machine("EX-1"), machine("EX-2"), machine("TR-9"))
        val state = FleetMapRules.load(online = true, nowMs = { 42L }) { server }
        assertEquals(FleetMapRules.State.Loaded(server, 42L), state)
    }

    @Test
    fun `forbidden and not found become plain messages`() = runTest {
        assertEquals(FleetMapRules.State.Failed(FleetMapRules.FORBIDDEN), FleetMapRules.load(true, { 0L }) { throw http(403) })
        assertEquals(FleetMapRules.State.Failed(FleetMapRules.NOT_FOUND), FleetMapRules.load(true, { 0L }) { throw http(404) })
        assertEquals(FleetMapRules.State.Failed(FleetMapRules.FAILED), FleetMapRules.load(true, { 0L }) { throw http(500) })
        assertEquals(FleetMapRules.State.Failed(FleetMapRules.NO_CONNECTION), FleetMapRules.load(true, { 0L }) { throw java.io.IOException("down") })
    }

    @Test
    fun `machines without a position are counted, not placed`() {
        val placed = machine("EX-1")
        val noFix = machine("EX-2", lat = null, lon = null)
        val half = machine("EX-3", lat = -6.8, lon = null)
        val split = FleetMapRules.split(listOf(placed, noFix, half))
        assertEquals(listOf(placed), split.placed)
        assertEquals(listOf(noFix, half), split.unplaced)
        assertEquals("2 machines have no known position (see List).", FleetMapRules.unplacedNote(split.unplaced.size))
        assertEquals("1 machine has no known position (see List).", FleetMapRules.unplacedNote(1))
        assertNull(FleetMapRules.unplacedNote(0))
    }

    @Test
    fun `status card lines`() {
        val now = 1_000_000L
        val s = FleetMapRules.status(machine("EX-1", connectivity = "LIVE", isLive = true), fetchedAtMs = now, nowMs = now)
        assertEquals("EX-1 · Excavator EX-1", s.title)
        assertEquals(Connectivity.LIVE, s.connectivity)
        assertEquals("Last seen 5 min ago", s.lastSeen)
        assertEquals("Reported: Working", s.reported)
        // An old response is never shown as live.
        assertEquals(Connectivity.RECENT, FleetMapRules.status(machine("EX-1", connectivity = "LIVE", isLive = true), 0L, 10 * 60_000L).connectivity)
        assertEquals("Never seen", FleetMapRules.status(machine("EX-1").copy(lastSeenAgeSeconds = null), 0L, 0L).lastSeen)
    }
}
