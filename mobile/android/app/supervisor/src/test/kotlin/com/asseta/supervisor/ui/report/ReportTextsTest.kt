package com.asseta.supervisor.ui.report

import com.asseta.core.domain.reports.ReportState
import org.junit.Assert.assertEquals
import org.junit.Test

/** Machine report wording after ADR-008's "rejected reports are final" (same as iOS). */
class ReportTextsTest {
    @Test
    fun `a rejected report asks for a new report, never a correction`() {
        assertEquals("Rejected: Hours too high. Send a new report for this machine.", ReportTexts.rejected("Hours too high"))
        assertEquals("Rejected. Send a new report for this machine.", ReportTexts.rejected(" "))
        // After a rejection the machine is simply due.
        assertEquals("Report due", ReportTexts.state(ReportState.DUE))
    }

    @Test
    fun `server refusals of a report in plain words`() {
        assertEquals("A rejected report can't be corrected; send a new report with a new reading.", ReportTexts.conflict("CORRECTION_NOT_ALLOWED"))
        assertEquals(ReportTexts.conflict("CORRECTION_NOT_ALLOWED"), ReportTexts.conflict("CORRECTS_INVALID"))
        assertEquals("This reading was already used in another report. Take a new reading.", ReportTexts.conflict("CAPTURE_ALREADY_USED"))
        assertEquals("The hours have more than 2 decimals.", ReportTexts.conflict("HOURS_PRECISION"))
    }
}
