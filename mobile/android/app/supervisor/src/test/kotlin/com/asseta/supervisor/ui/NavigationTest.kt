package com.asseta.supervisor.ui

import com.asseta.core.domain.policy.ReadingKind
import com.asseta.core.ui.components.NavigationChrome
import com.asseta.supervisor.ui.finance.CashFormViewModel
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Navigation bar of the Supervisor app, as on iOS (`FieldRootView` and its sheets). */
class NavigationTest {
    @Test
    fun `home is titled with the company and pushed screens with their own title`() {
        assertEquals("Acme", Route.Jobs.title("Acme"))
        assertEquals("J-001", Route.JobDetail("1", "J-001").title("Acme"))
        assertEquals("Sync status", Route.SyncStatus.title("Acme"))
        assertEquals("Opening reading", Route.Capture("1", ReadingKind.OPENING).title("Acme"))
    }

    @Test
    fun `forms are the iOS sheets with Cancel and Save, other screens push with back`() {
        listOf(
            Route.Capture("1", ReadingKind.CLOSING), Route.Acknowledge("1"), Route.WorkLogEntry("1"), Route.RecordExpense,
            Route.CashForm(CashFormViewModel.COLLECTION), Route.CashForm(CashFormViewModel.HANDOVER), Route.CashForm(CashFormViewModel.FUEL),
        ).forEach { assertTrue("$it", it.isForm) }
        assertTrue(Route.ResetRequest("m", null).isForm)
        listOf(Route.Jobs, Route.JobDetail("1", "J-1"), Route.SyncStatus, Route.Money, Route.ReadingDetail("r"), Route.ExpenseDetail("e"))
            .forEach { assertFalse("$it", it.isForm) }
    }

    @Test
    fun `five tabs with their own titles and stacks`() {
        assertEquals(listOf("Jobs", "Readings", "Fuel", "Money", "Inbox"), SupervisorTab.entries.map { it.label })
        assertEquals("Readings", Route.Readings.title("Acme"))
        assertEquals("Inbox", SupervisorTab.INBOX.root.title("Acme"))
        var nav = TabStacks()
        nav = nav.push(Route.JobDetail("1", "J-1"))
        nav = nav.select(SupervisorTab.MONEY).push(Route.ExpenseDetail("e"))
        assertEquals(Route.ExpenseDetail("e"), nav.route)
        nav = nav.select(SupervisorTab.JOBS)
        assertEquals(Route.JobDetail("1", "J-1"), nav.route) // each tab keeps its stack
        nav = nav.select(SupervisorTab.JOBS)
        assertEquals(Route.Jobs, nav.route) // selecting the current tab again returns to its first screen
        assertEquals(Route.Jobs, nav.pop().route)
    }

    @Test
    fun `a notification tap opens the Inbox list and keeps the other tabs`() {
        var nav = TabStacks().push(Route.JobDetail("1", "J-1")).select(SupervisorTab.INBOX).push(Route.NotificationDetail("n0"))
        nav = nav.select(SupervisorTab.JOBS).showRoot(SupervisorTab.INBOX)
        assertEquals(SupervisorTab.INBOX, nav.tab)
        assertEquals(listOf<Route>(Route.Inbox), nav.stack)
        assertEquals(Route.NotificationDetail("n1"), nav.push(Route.NotificationDetail("n1")).route)
        assertEquals(Route.JobDetail("1", "J-1"), nav.select(SupervisorTab.JOBS).route)
    }

    @Test
    fun `back label is the previous title when short`() {
        assertEquals("J-001", NavigationChrome.backLabel(Route.JobDetail("1", "J-001").title("Acme")))
        assertEquals("Back", NavigationChrome.backLabel(Route.Jobs.title("Acme Earthmoving Holdings")))
    }
}
