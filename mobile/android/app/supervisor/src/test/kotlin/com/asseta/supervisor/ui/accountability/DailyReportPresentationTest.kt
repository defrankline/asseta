package com.asseta.supervisor.ui.accountability

import com.asseta.core.domain.inbox.InboxLink
import com.asseta.core.domain.inbox.InboxLinks
import com.asseta.core.domain.inbox.Tone
import com.asseta.core.model.owner.DailyReportDto
import com.asseta.core.network.NetworkFactory
import com.asseta.core.sync.data.DailyReportRow
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

class DailyReportPresentationTest {
    private fun report(status: String) = NetworkFactory.json.decodeFromString(
        DailyReportDto.serializer(),
        """{"id":"r","machine_id":"m","report_date":"2026-10-26","opening_ref":"a","opening_reading":"100.00","closing_ref":"b","closing_reading":"110.50",
           "total_hours":"10.50","billable_hours":"8.00","unbillable_hours":"2.50","difference_hours":"0","status":"$status",
           "submitted_at":"2026-10-26T18:00:00Z","client_created_at":"2026-10-26T18:00:00Z"}""",
    )

    @Test
    fun `statuses in plain words`() {
        assertEquals("Sent back" to Tone.WARNING, DailyReportTexts.status(DailyReportRow("r", report("RETURNED"), null, null)))
        assertEquals("Replaced" to Tone.NEUTRAL, DailyReportTexts.status(DailyReportRow("r", report("SUPERSEDED"), null, null)))
        assertEquals("Waiting to sync" to Tone.NEUTRAL, DailyReportTexts.status(DailyReportRow("r", null, null, null)))
    }

    @Test
    fun `figures and dates`() {
        assertEquals("10.5 h in total · 8 h billable", DailyReportTexts.rowLine("10.50", "8.00"))
        assertEquals("26 Oct 2026", DailyReportTexts.date("2026-10-26"))
        assertEquals("120 · today · not synced yet", DailyReportTexts.readingOption("120", "today", synced = false))
        assertEquals("Authorized activity", DailyReportTexts.kind("AUTHORIZED_ACTIVITY"))
    }

    @Test
    fun `every new conflict code has plain words`() {
        listOf(
            "REPORT_READINGS_INVALID", "REPORT_HOURS_EXCEED_TOTAL", "REPORT_ID_CONFLICT", "REPORT_NOT_SUPERSEDABLE", "REPORT_EVIDENCE_REQUIRED",
            "REASON_NOT_ALLOWED", "CHANGEOVER_NOT_ALLOWED", "CHANGEOVER_SAME_CUSTOMER", "CHANGEOVER_JOB_REQUIRED", "CHANGEOVER_JOB_INVALID",
        ).forEach { assertNotNull(it, FieldAccountabilityTexts.conflict(it)) }
        assertNull(FieldAccountabilityTexts.conflict("SOMETHING_ELSE"))
    }

    @Test
    fun `a returned report notification opens the report`() {
        assertEquals(InboxLink.DailyReport("r1"), InboxLinks.from(null, null, "DAILY_REPORT", "r1"))
        assertEquals(InboxLink.DailyReport("r2"), InboxLinks.from("daily_report", "r2"))
    }
}
