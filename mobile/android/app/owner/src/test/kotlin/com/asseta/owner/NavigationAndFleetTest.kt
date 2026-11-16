package com.asseta.owner

import com.asseta.core.domain.owner.Connectivity
import com.asseta.core.domain.owner.DataSource
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.network.NetworkFactory
import com.asseta.core.model.owner.MachineMapDto
import com.asseta.owner.ui.OwnerFeatures
import com.asseta.owner.ui.OwnerNavigation
import com.asseta.owner.ui.OwnerSession
import com.asseta.owner.ui.fleet.FleetRows
import com.asseta.core.domain.owner.MutationCheck
import com.asseta.core.domain.owner.OwnerAction
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class NavigationAndFleetTest {
    @Test
    fun `side menu destinations reset the stack to Home and details push`() {
        var stack = listOf<OwnerDestination>(OwnerDestination.Home)
        stack = OwnerNavigation.navigate(stack, OwnerDestination.Machines)
        assertEquals(listOf(OwnerDestination.Home, OwnerDestination.Machines), stack)
        stack = OwnerNavigation.navigate(stack, OwnerDestination.Machine(ID1))
        stack = OwnerNavigation.navigate(stack, OwnerDestination.MachineReport(ID2))
        assertEquals(4, stack.size)
        assertEquals(OwnerDestination.Machines, OwnerNavigation.menuRoot(stack))
        assertEquals(listOf(OwnerDestination.Home, OwnerDestination.Machines, OwnerDestination.Machine(ID1)), OwnerNavigation.back(stack))
        // Another menu destination starts again from Home; Home itself is the whole stack.
        assertEquals(listOf(OwnerDestination.Home, OwnerDestination.Alerts()), OwnerNavigation.navigate(stack, OwnerDestination.Alerts()))
        assertEquals(listOf<OwnerDestination>(OwnerDestination.Home), OwnerNavigation.navigate(stack, OwnerDestination.Home))
        // A deep link to one alert is pushed (keeps context), not treated as the menu destination.
        assertEquals(5, OwnerNavigation.navigate(stack, OwnerDestination.Alerts(ID1)).size)
        assertEquals(stack, OwnerNavigation.navigate(stack, OwnerDestination.MachineReport(ID2)))
        assertEquals(listOf<OwnerDestination>(OwnerDestination.Home), OwnerNavigation.back(listOf(OwnerDestination.Home)))
        assertEquals(OwnerDestination.Home, OwnerNavigation.menuRoot(listOf(OwnerDestination.Home)))
    }

    @Test
    fun `the old More tab opens Home`() {
        val f = OwnerFeatures(setOf("tenant.fleet.read"))
        assertEquals(OwnerDestination.Home, f.route(OwnerDestination.More))
    }

    @Test
    fun `side menu is grouped, gated and badged`() {
        val owner = OwnerFeatures(
            setOf(
                "tenant.approval.read", "tenant.machine_report.read", "tenant.machine_report.approve", "tenant.hours.read",
                "tenant.hours.credit_activate", "tenant.fleet.read", "tenant.finance.read", "tenant.notification.read", "tenant.setup.read",
            ),
        )
        val groups = com.asseta.owner.ui.OwnerMenu.groups(owner, waiting = 5, unread = 6)
        assertEquals(listOf(null, "More"), groups.map { it.header })
        assertEquals(
            listOf("Home", "Approvals", "Customers & hours", "Machines", "Money", "Reports", "Notifications"),
            groups[0].entries.map { it.label },
        )
        assertEquals("5", groups[0].entries.single { it.key == "approvals" }.badge)
        assertEquals("6", groups[0].entries.single { it.key == "notifications" }.badge)
        assertEquals(listOf("Go-live checklist", "Dashboard", "Fleet map", "Alerts", "Cash with supervisors"), groups[1].entries.map { it.label })
        assertEquals(listOf("Settings", "Sign out"), com.asseta.owner.ui.OwnerMenu.footer(false).map { it.label })
        assertEquals(listOf("Switch company", "Settings", "Sign out"), com.asseta.owner.ui.OwnerMenu.footer(true).map { it.label })
        assertEquals("approvals", com.asseta.owner.ui.OwnerMenu.selectedKey(OwnerDestination.Approvals(), groups))
        // Nothing waiting: no badge. Customers & hours switched off: no entry.
        assertNull(com.asseta.owner.ui.OwnerMenu.groups(owner, 0, 0)[0].entries.single { it.key == "approvals" }.badge)
        val hoursOff = owner.copy(disabled = setOf(com.asseta.core.model.TenantAccess.CUSTOMER_HOURS))
        assertTrue(com.asseta.owner.ui.OwnerMenu.groups(hoursOff, null, null)[0].entries.none { it.key == "customers" })
        assertEquals(OwnerDestination.Home, hoursOff.route(OwnerDestination.Customers))
        // A role with nothing but the inbox: Home, Notifications; never an empty More group.
        val inbox = com.asseta.owner.ui.OwnerMenu.groups(OwnerFeatures(setOf("tenant.notification.read")), null, null)
        assertEquals(1, inbox.size)
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
