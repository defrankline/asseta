package com.asseta.owner

import com.asseta.core.domain.owner.Connectivity
import com.asseta.core.domain.owner.DataSource
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.network.NetworkFactory
import com.asseta.core.model.owner.MachineMapDto
import com.asseta.owner.ui.OwnerNavigation
import com.asseta.owner.ui.OwnerSession
import com.asseta.owner.ui.OwnerTab
import com.asseta.owner.ui.fleet.FleetRows
import com.asseta.core.domain.owner.MutationCheck
import com.asseta.core.domain.owner.OwnerAction
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class NavigationAndFleetTest {
    @Test
    fun `tabs reset the stack and details push`() {
        var stack = listOf<OwnerDestination>(OwnerDestination.Home)
        stack = OwnerNavigation.navigate(stack, OwnerDestination.Fleet)
        stack = OwnerNavigation.navigate(stack, OwnerDestination.Machine(ID1))
        stack = OwnerNavigation.navigate(stack, OwnerDestination.Job(ID2))
        assertEquals(3, stack.size)
        assertEquals(OwnerTab.FLEET, OwnerNavigation.currentTab(stack))
        assertEquals(listOf(OwnerDestination.Fleet, OwnerDestination.Machine(ID1)), OwnerNavigation.back(stack))
        assertEquals(listOf<OwnerDestination>(OwnerDestination.Alerts()), OwnerNavigation.navigate(stack, OwnerDestination.Alerts()))
        // A deep link to one alert is pushed (keeps context), not treated as the tab.
        assertEquals(4, OwnerNavigation.navigate(stack, OwnerDestination.Alerts(ID1)).size)
        assertEquals(stack, OwnerNavigation.navigate(stack, OwnerDestination.Job(ID2)))
    }

    private fun machine(connectivity: String, live: Boolean) =
        NetworkFactory.json.decodeFromString(MachineMapDto.serializer(), Samples.machine(connectivity, live))

    @Test
    fun `fleet never shows live from cache and ages last seen by the snapshot age`() {
        val now = 1_000_000_000L
        val cached = FleetRows.build(listOf(machine("LIVE", true)), DataSource.CACHE, now - 3_600_000, now).single()
        assertEquals(Connectivity.RECENT, cached.connectivity)
        assertEquals("1 h ago", cached.lastSeen)
        val live = FleetRows.build(listOf(machine("LIVE", true)), DataSource.LIVE, now, now).single()
        assertEquals(Connectivity.LIVE, live.connectivity)
        assertEquals("just now", live.lastSeen)
    }

    @Test
    fun `fleet filter by text and connectivity`() {
        val rows = FleetRows.build(listOf(machine("OFFLINE", false)), DataSource.LIVE, 0, 0)
        assertEquals(1, FleetRows.filter(rows, "excav", null).size)
        assertEquals(0, FleetRows.filter(rows, "dozer", null).size)
        assertEquals(0, FleetRows.filter(rows, "", Connectivity.LIVE).size)
        assertEquals(1, FleetRows.filter(rows, "EX-01", Connectivity.OFFLINE).size)
    }

    @Test
    fun `owner session gates mutations by permission and data source`() {
        val s = OwnerSession(TENANT, "Acme", setOf("tenant.approval.expense"), readOnly = false)
        assertEquals(MutationCheck.Allowed, s.can(OwnerAction.DECIDE_APPROVAL, true, DataSource.LIVE))
        assertTrue(s.can(OwnerAction.DECIDE_APPROVAL, true, null) is MutationCheck.Blocked)
        assertTrue(s.can(OwnerAction.ACKNOWLEDGE_ALERT, true, DataSource.LIVE) is MutationCheck.Blocked)
    }
}
