package com.asseta.core.domain.forms

import com.asseta.core.domain.accountability.HoursPayments
import com.asseta.core.domain.accountability.HoursSaleDraft
import com.asseta.core.domain.accountability.PaymentMethod
import com.asseta.core.domain.reports.ReportLineDraft
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Leaving a report or a sale with entered data asks first (same cases as iOS `FormLeaveTests`). */
class FormLeaveTest {
    private val line = ReportLineDraft.Customer("c1", "Pwani Road Contractors", "120")

    @Test
    fun `back asks only when work was entered and never during a save`() {
        assertEquals(LeaveAction.LEAVE, FormLeave.decide(saving = false, saved = false, entered = false))
        assertEquals(LeaveAction.ASK, FormLeave.decide(saving = false, saved = false, entered = true))
        assertEquals(LeaveAction.STAY, FormLeave.decide(saving = true, saved = false, entered = true))
        assertEquals(LeaveAction.LEAVE, FormLeave.decide(saving = false, saved = true, entered = true))
    }

    @Test
    fun `a report with a photo, a typed reading, a line or a note holds entered data`() {
        assertFalse(FormLeave.reportEntered(false, "", emptyList(), emptyList(), ""))
        assertTrue(FormLeave.reportEntered(true, "", emptyList(), emptyList(), ""))
        assertTrue(FormLeave.reportEntered(false, "1510.5", emptyList(), emptyList(), ""))
        assertTrue(FormLeave.reportEntered(false, "", listOf(line), emptyList(), ""))
        assertTrue(FormLeave.reportEntered(false, "", emptyList(), emptyList(), "Late start"))
        // A correction opens with the rejected report's lines: not new input until they change.
        assertFalse(FormLeave.reportEntered(false, "", listOf(line), listOf(line), ""))
        assertTrue(FormLeave.reportEntered(false, "", listOf(line.copy(hoursText = "100")), listOf(line), ""))
    }

    @Test
    fun `a sale holds entered data once anything is chosen or typed`() {
        val opening = HoursSaleDraft(false, null, "", "", null, "", HoursPayments.opening(), "")
        assertFalse(FormLeave.saleEntered(opening, 0, false))
        // The opening Cash line following the total does not count, even with the total's amount filled in.
        assertFalse(FormLeave.saleEntered(opening.copy(payments = listOf(HoursPayments.opening().single().copy(amountText = "950000"))), 0, false))
        assertTrue(FormLeave.saleEntered(opening.copy(customerId = "c1"), 0, false))
        assertTrue(FormLeave.saleEntered(opening.copy(walkIn = true, walkInName = "Juma"), 0, false))
        assertTrue(FormLeave.saleEntered(opening.copy(machineId = "m1"), 0, false))
        assertTrue(FormLeave.saleEntered(opening.copy(hoursText = "20"), 0, false))
        assertTrue(FormLeave.saleEntered(opening.copy(payments = listOf(HoursPayments.opening().single().typed("5000"))), 0, false))
        assertTrue(FormLeave.saleEntered(opening.copy(payments = listOf(HoursPayments.opening().single().copy(method = PaymentMethod.BANK))), 0, false))
        assertTrue(FormLeave.saleEntered(opening.copy(payments = emptyList()), 0, false))
        assertTrue(FormLeave.saleEntered(opening, 1, false))
        assertTrue(FormLeave.saleEntered(opening, 0, true))
    }

    @Test
    fun `the wording matches the apps`() {
        assertEquals("Discard this report?", FormLeave.REPORT_TITLE)
        assertEquals("The photo and readings you entered will be lost.", FormLeave.REPORT_BODY)
        assertEquals("Discard this sale?", FormLeave.SALE_TITLE)
        assertEquals("The customer, hours and payments you entered will be lost.", FormLeave.SALE_BODY)
        assertEquals("Keep editing", FormLeave.KEEP_EDITING)
        assertEquals("Discard", FormLeave.DISCARD)
    }
}
