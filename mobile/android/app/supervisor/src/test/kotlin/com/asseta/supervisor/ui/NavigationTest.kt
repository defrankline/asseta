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
        listOf(Route.Jobs, Route.JobDetail("1", "J-1"), Route.SyncStatus, Route.MyCash).forEach { assertFalse("$it", it.isForm) }
    }

    @Test
    fun `back label is the previous title when short`() {
        assertEquals("J-001", NavigationChrome.backLabel(Route.JobDetail("1", "J-001").title("Acme")))
        assertEquals("Back", NavigationChrome.backLabel(Route.Jobs.title("Acme Earthmoving Holdings")))
    }
}
