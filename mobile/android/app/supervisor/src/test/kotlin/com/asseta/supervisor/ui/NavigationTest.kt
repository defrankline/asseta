package com.asseta.supervisor.ui

import com.asseta.core.domain.accountability.CustomerHoursPolicy
import com.asseta.core.domain.accountability.FieldAccess
import com.asseta.core.model.sync.SyncCapabilities
import com.asseta.core.ui.components.NavigationChrome
import com.asseta.supervisor.ui.finance.CashFormViewModel
import com.asseta.supervisor.ui.home.MenuItem
import com.asseta.supervisor.ui.home.ShellModel
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** ADR-008 shell of the Supervisor app: side menu, one back stack from Home, titles and forms (same as iOS). */
class NavigationTest {
    private val hours = CustomerHoursPolicy(enabled = true, walkInAllowed = true, transferRequiresApproval = true, reasonCodeRequired = false)
    private val all = FieldAccess(
        setOf(SyncCapabilities.OP_HOURS_PURCHASE, SyncCapabilities.OP_MACHINE_REPORT),
        setOf(FieldAccess.HOURS_PURCHASE, FieldAccess.MACHINE_REPORT_SUBMIT, ShellModel.EXPENSE_WRITE), hours = hours,
    )

    @Test
    fun `home is titled with the company and pushed screens with their own title`() {
        assertEquals("Acme", Route.Home.title("Acme"))
        assertEquals("Machine report", Route.MachineReport().title("Acme"))
        assertEquals("Sell hours", Route.HoursSale.title("Acme"))
        assertEquals("Sync status", Route.SyncStatus.title("Acme"))
        assertEquals("Credit invoice payment", Route.InvoicePayment().title("Acme"))
    }

    @Test
    fun `forms are the iOS sheets with Cancel and Save, the redesigned flows keep their own buttons`() {
        listOf(Route.RecordExpense, Route.CashForm(CashFormViewModel.COLLECTION), Route.CashForm(CashFormViewModel.HANDOVER), Route.ResetRequest("m", null))
            .forEach { assertTrue("$it", it.isForm) }
        listOf(Route.Home, Route.HoursSale, Route.MachineReport(), Route.Money, Route.Dashboard, Route.InvoicePayment(), Route.SyncStatus)
            .forEach { assertFalse("$it", it.isForm) }
    }

    @Test
    fun `side menu entries per design, gated by access and the fuel switch`() {
        assertEquals(
            listOf("Home", "Sell hours", "Machine report", "Money", "Fuel", "Dashboard", "Inbox", "Customers"),
            ShellModel.menu(all, all.permissions, fuelOn = true).map { it.label },
        )
        // FUEL off: no Fuel entry at all; no sale / report entries without their access.
        assertEquals(listOf("Home", "Money", "Dashboard", "Inbox", "Customers"), ShellModel.menu(null, emptySet(), fuelOn = false).map { it.label })
        assertFalse(MenuItem.FUEL in ShellModel.menu(all, all.permissions, fuelOn = false))
        assertEquals(listOf(MenuItem.SELL_HOURS, MenuItem.MACHINE_REPORT, MenuItem.MONEY, MenuItem.DASHBOARD), ShellModel.tiles(all))
        assertEquals(listOf(MenuItem.MONEY, MenuItem.DASHBOARD), ShellModel.tiles(null))
    }

    @Test
    fun `one back stack from Home, a menu entry opens on top of Home`() {
        var nav = NavStack()
        assertEquals(Route.Home, nav.route)
        nav = nav.open(MenuItem.MONEY).push(Route.ExpenseDetail("e"))
        assertEquals(listOf(Route.Home, Route.Money, Route.ExpenseDetail("e")), nav.stack)
        assertEquals(MenuItem.MONEY, nav.menu)
        nav = nav.pop().pop()
        assertEquals(Route.Home, nav.route)
        assertEquals(Route.Home, nav.pop().route) // Home is never popped
        nav = nav.open(MenuItem.DASHBOARD).push(Route.MachineReport("m1"))
        assertEquals(MenuItem.DASHBOARD, nav.menu)
        assertEquals(listOf(Route.Home), nav.open(MenuItem.HOME).stack)
    }

    @Test
    fun `a notification tap opens the Inbox on top of Home`() {
        val nav = NavStack().open(MenuItem.MONEY).push(Route.ExpenseDetail("e")).showInbox()
        assertEquals(listOf(Route.Home, Route.Inbox), nav.stack)
        assertEquals(Route.NotificationDetail("n1"), nav.push(Route.NotificationDetail("n1")).route)
    }

    @Test
    fun `back label is the previous title when short`() {
        assertEquals("Money", NavigationChrome.backLabel(Route.Money.title("Acme")))
        assertEquals("Back", NavigationChrome.backLabel(Route.Home.title("Acme Earthmoving Holdings")))
    }
}
