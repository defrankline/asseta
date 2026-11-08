package com.asseta.core.domain.accountability

import com.asseta.core.domain.finance.FormCheck
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class DailyReportRulesTest {
    private fun draft(billable: String = "", lines: List<UnbillableDraft> = emptyList(), photos: Int = 0, required: Boolean = false, opening: String? = "a", closing: String? = "b") =
        DailyReportDraft(opening, closing, "100", "110", billable, lines, " note ", photos, required)

    private fun messages(d: DailyReportDraft) = (DailyReportRules.check(d) as FormCheck.Invalid).messages

    @Test
    fun `prefill follows the server - first and last of a day with two readings`() {
        val r = listOf(ReportReading("old", "90", 50, true), ReportReading("m", "100", 110, true), ReportReading("e", "110", 150, false))
        assertEquals("m" to "e", DailyReportRules.prefill(r, 100, 200))
    }

    @Test
    fun `prefill with one reading opens from the latest before the day`() {
        val r = listOf(ReportReading("older", "80", 10, true), ReportReading("old", "90", 50, true), ReportReading("e", "110", 150, true))
        assertEquals("old" to "e", DailyReportRules.prefill(r, 100, 200))
        assertEquals(null to null, DailyReportRules.prefill(emptyList(), 100, 200))
    }

    @Test
    fun `valid report keeps billable optional and trims the note`() {
        val v = (DailyReportRules.check(draft(lines = listOf(UnbillableDraft("r1", "2.5")))) as FormCheck.Valid).value
        assertNull(v.billable)
        assertEquals(listOf("r1" to "2.5".toBigDecimal()), v.lines)
        assertEquals("note", v.note)
    }

    @Test
    fun `readings must be chosen and different`() {
        assertEquals(listOf(DailyReportMessages.OPENING, DailyReportMessages.CLOSING), messages(draft(opening = null, closing = null)))
        assertEquals(listOf(DailyReportMessages.SAME_READING), messages(draft(opening = "a", closing = "a")))
    }

    @Test
    fun `reason lines need a reason, hours and no repeats`() {
        assertEquals(listOf(DailyReportMessages.REASON_MISSING), messages(draft(lines = listOf(UnbillableDraft(null, "1")))))
        assertEquals(listOf(DailyReportMessages.REASON_HOURS), messages(draft(lines = listOf(UnbillableDraft("r", "0")))))
        assertEquals(listOf(DailyReportMessages.REASON_REPEATED), messages(draft(lines = listOf(UnbillableDraft("r", "1"), UnbillableDraft("r", "2")))))
        assertTrue(DailyReportRules.check(draft(lines = listOf(UnbillableDraft(null, "")))) is FormCheck.Valid)
    }

    @Test
    fun `hours cannot exceed the total and a required photo is enforced`() {
        assertEquals(listOf(DailyReportMessages.exceeds("10".toBigDecimal())), messages(draft(billable = "9", lines = listOf(UnbillableDraft("r", "2")))))
        assertEquals(listOf(DailyReportMessages.PHOTO), messages(draft(required = true)))
        assertTrue(DailyReportRules.check(draft(required = true, photos = 1)) is FormCheck.Valid)
    }

    @Test
    fun `a backwards meter leaves the total to the server`() {
        assertNull(DailyReportRules.total("110", "100"))
        assertTrue(DailyReportRules.check(DailyReportDraft("a", "b", "110", "100", "500", emptyList(), "", 0, false)) is FormCheck.Valid)
    }

    @Test
    fun `not accounted for is what billable and unbillable leave over`() {
        assertEquals(0, DailyReportRules.notAccounted("10".toBigDecimal(), "", listOf(UnbillableDraft("r", "2")))!!.signum())
        assertEquals("3".toBigDecimal(), DailyReportRules.notAccounted("10".toBigDecimal(), "5", listOf(UnbillableDraft("r", "2"))))
    }

    @Test
    fun `changeover needs a customer and the job only when the tenant requires it`() {
        assertEquals(DailyReportMessages.CHANGEOVER_CUSTOMER, ChangeoverRules.problem(null, null, false))
        assertNull(ChangeoverRules.problem("c", null, false))
        assertEquals(DailyReportMessages.CHANGEOVER_JOB, ChangeoverRules.problem("c", null, true))
        assertNull(ChangeoverRules.problem("c", "j", true))
    }

    @Test
    fun `a billed next job must be waiting for approval`() {
        assertTrue(ChangeoverRules.jobOffered("PENDING_APPROVAL", required = true))
        assertFalse(ChangeoverRules.jobOffered("APPROVED", required = true))
        assertTrue(ChangeoverRules.jobOffered("APPROVED", required = false))
        assertFalse(ChangeoverRules.jobOffered("IN_PROGRESS", required = false))
    }

    @Test
    fun `engine hours switches default off and access needs capability, permission and capability on`() {
        val on = EngineHoursPolicy.fromValues(buildJsonObject { put("changeover_splits_billing", JsonPrimitive(true)) })
        assertTrue(on.changeoverSplitsBilling)
        assertFalse(on.dailyReportEvidenceRequired)
        val caps = setOf("OP_DAILY_REPORT", "METER_CHANGEOVER")
        val perms = setOf(FieldAccess.METER_CAPTURE, FieldAccess.METER_READ)
        val a = FieldAccess(caps, perms, engine = on)
        assertTrue(a.dailyReport && a.readDailyReports && a.changeover && a.changeoverJobRequired)
        assertFalse(FieldAccess(caps, perms, disabled = setOf("ENGINE_HOURS")).dailyReport)
        assertFalse(FieldAccess(caps, emptySet()).changeover)
        assertFalse(FieldAccess(emptySet(), perms).dailyReport)
    }
}
