package com.asseta.core.domain.reports

import com.asseta.core.domain.finance.FormCheck
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.math.BigDecimal

/** ADR-008 machine report rules (same cases as iOS `MachineReportRulesTests`). */
class MachineReportRulesTest {
    private val pwani = ReportLineDraft.Customer("c1", "Pwani Road Contractors", "120")
    private val msasani = ReportLineDraft.Customer("c2", "Msasani Bay Developers", "100")
    private val breakdown = ReportLineDraft.NonProductive("r1", "Breakdown / repair", "40", "Hydraulic hose replaced on site")
    private val transit = ReportLineDraft.NonProductive("r2", "Transit between sites", "25", "Kibamba to Kigamboni")
    private val idle = ReportLineDraft.NonProductive("r3", "Idle on site", "15", "Waited for the client")
    private val available = mapOf("c1" to BigDecimal("140"), "c2" to BigDecimal("100"))
    private val diff = BigDecimal("300")

    @Test
    fun `the difference is new minus previous and an opening report has none`() {
        assertEquals(BigDecimal("300.0"), MachineReportRules.difference(BigDecimal("1210.0"), BigDecimal("1510.0")))
        assertNull(MachineReportRules.difference(null, BigDecimal("1510.0")))
        assertNull(MachineReportRules.readingProblem(BigDecimal("1210"), BigDecimal("1510")))
        assertEquals(MachineReportMessages.NOTHING_TO_REPORT, MachineReportRules.readingProblem(BigDecimal("1210"), BigDecimal("1210.0")))
        assertEquals(MachineReportMessages.READING_LOWER, MachineReportRules.readingProblem(BigDecimal("1210"), BigDecimal("1200")))
        assertEquals(MachineReportMessages.READING, MachineReportRules.readingProblem(BigDecimal("1210"), null))
        // Opening report: any reading is accepted (nothing to compare with).
        assertNull(MachineReportRules.readingProblem(null, BigDecimal("5")))
    }

    @Test
    fun `review only when the lines add up to the difference exactly`() {
        val partial = listOf(pwani, msasani, breakdown, transit)
        assertEquals(BigDecimal("285"), MachineReportRules.accounted(partial))
        assertEquals(BigDecimal("15"), MachineReportRules.left(diff, partial))
        assertEquals(0.95f, MachineReportRules.progress(diff, partial), 0.001f)
        assertFalse(MachineReportRules.canReview(diff, partial, available))
        assertEquals(listOf("15 h still to account for"), (MachineReportRules.check(diff, partial, available) as FormCheck.Invalid).messages)

        val full = partial + idle
        assertTrue(MachineReportRules.canReview(diff, full, available))
        val lines = (MachineReportRules.check(diff, full, available) as FormCheck.Valid).value
        assertEquals(5, lines.size)
        assertEquals(ReportLine.NonProductive("r1", BigDecimal("40"), "Hydraulic hose replaced on site"), lines[2])

        val over = full + ReportLineDraft.NonProductive("r4", "Weather", "5", "Rain")
        assertEquals(listOf("5 h more than the meter shows"), (MachineReportRules.check(diff, over, available) as FormCheck.Invalid).messages)
    }

    @Test
    fun `a customer cannot get more than its available hours and appears once`() {
        val greedy = listOf(pwani.copy(hoursText = "150"), msasani, breakdown.copy(hoursText = "50"))
        val messages = (MachineReportRules.check(diff, greedy, available) as FormCheck.Invalid).messages
        assertEquals(listOf("Pwani Road Contractors has only 140 h available."), messages)
        assertEquals(BigDecimal("20"), MachineReportRules.afterThis(BigDecimal("140"), pwani))

        val twice = listOf(pwani, pwani.copy(hoursText = "10"), msasani, idle.copy(hoursText = "70"))
        assertTrue(MachineReportMessages.CUSTOMER_TWICE in (MachineReportRules.check(diff, twice, available) as FormCheck.Invalid).messages)

        // A customer with no available hours on this phone gets nothing.
        val unknown = listOf(ReportLineDraft.Customer("c9", "New Co", "1"), idle.copy(hoursText = "299"))
        assertEquals(listOf("New Co has only 0 h available."), (MachineReportRules.check(diff, unknown, available) as FormCheck.Invalid).messages)
    }

    @Test
    fun `non-productive lines need a note and line hours go in hundredths`() {
        val noNote = listOf(pwani, msasani, breakdown.copy(note = "  "), transit, idle)
        assertEquals(listOf("Say what happened for “Breakdown / repair”."), (MachineReportRules.check(diff, noNote, available) as FormCheck.Invalid).messages)
        assertEquals(BigDecimal("2.5"), MachineReportRules.hours("2.5"))
        assertEquals(BigDecimal("2.55"), MachineReportRules.hours("2.55"))
        assertEquals(BigDecimal("1.15"), MachineReportRules.hours("1,15"))
        assertNull(MachineReportRules.hours("2.555"))
        assertNull(MachineReportRules.hours("0"))
        assertNull(MachineReportRules.hours("0.00"))
        assertNull(MachineReportRules.hours("-1"))
        assertNull(MachineReportRules.hours("1.2.3"))
        assertEquals(BigDecimal("3"), MachineReportRules.hours("3,0"))
        assertEquals("Enter the hours (more than 0, at most 2 decimals).", MachineReportMessages.HOURS_FORMAT)
        assertEquals(listOf(MachineReportMessages.NO_LINES, "300 h still to account for"),
            (MachineReportRules.check(diff, emptyList(), available) as FormCheck.Invalid).messages)
    }

    @Test
    fun `split lines in hundredths whatever the meter precision`() {
        val nine = BigDecimal("9.0")
        val lines = listOf(ReportLineDraft.Customer("c1", "Pwani Road Contractors", "7.85"), ReportLineDraft.NonProductive("r1", "Transit", "1.15", "Kibamba"))
        assertTrue(MachineReportRules.allAccounted(nine, lines))
        assertTrue(MachineReportRules.canReview(nine, lines, available))
        assertEquals(BigDecimal("132.15"), MachineReportRules.afterThis(BigDecimal("140"), lines[0] as ReportLineDraft.Customer))
    }

    @Test
    fun `an invalid line counts as nothing and is never all accounted for`() {
        // The reported bug: 9 h on one line and an invalid line read as "9 / 9 h · All hours accounted for".
        val nine = BigDecimal("9")
        val good = ReportLineDraft.NonProductive("r1", "Transit", "9", "Kibamba to Kigamboni")
        val invalid = ReportLineDraft.Customer("c1", "Pwani Road Contractors", "1.155")
        val lines = listOf(good, invalid)
        assertTrue(MachineReportRules.lineInvalid(invalid))
        assertFalse(MachineReportRules.lineInvalid(good))
        assertEquals(BigDecimal("9"), MachineReportRules.accounted(lines))
        assertEquals(0, MachineReportRules.left(nine, lines).signum())
        assertFalse(MachineReportRules.allAccounted(nine, lines))
        assertFalse(MachineReportRules.canReview(nine, lines, available))
        assertEquals(listOf(MachineReportMessages.HOURS_FORMAT), (MachineReportRules.check(nine, lines, available) as FormCheck.Invalid).messages)
        // The customer's "after this" ignores the invalid line.
        assertEquals(BigDecimal("140"), MachineReportRules.afterThis(BigDecimal("140"), invalid))
        // An empty line is not valid either; with no lines nothing is accounted for.
        assertFalse(MachineReportRules.allAccounted(nine, listOf(good, invalid.copy(hoursText = ""))))
        assertFalse(MachineReportRules.allAccounted(BigDecimal.ZERO, emptyList()))
        assertTrue(MachineReportRules.allAccounted(nine, listOf(good)))
    }

    @Test
    fun `machine state per server status and this phone`() {
        fun state(prev: String? = "1210", server: Boolean = false, phone: Boolean = false, rejected: Boolean = false, days: Int? = 1, remind: Int? = 3) =
            MachineReportRules.state(prev, server, phone, rejected, days, remind)
        assertEquals(ReportState.UP_TO_DATE, state())
        assertEquals(ReportState.DUE, state(days = 3))
        assertEquals(ReportState.DUE, state(days = null))
        assertEquals(ReportState.UP_TO_DATE, state(days = 30, remind = null))
        assertEquals(ReportState.AWAITING_APPROVAL, state(server = true, days = 9))
        assertEquals(ReportState.AWAITING_APPROVAL, state(phone = true, rejected = true))
        // A rejected report is final: the machine is due again, even inside the reminder days or with reminders off.
        assertEquals(ReportState.DUE, state(rejected = true))
        assertEquals(ReportState.DUE, state(rejected = true, days = 0, remind = null))
        assertEquals(ReportState.OPENING, state(prev = null, days = null))
        assertEquals(ReportState.OPENING, state(prev = null, rejected = true))
        assertTrue(ReportState.OPENING.needsReport)
        assertTrue(ReportState.DUE.needsReport)
        assertFalse(ReportState.AWAITING_APPROVAL.needsReport)
    }

    @Test
    fun `approval is by permission and never by the submitter`() {
        val approve = setOf(MachineReportApproval.APPROVE)
        assertTrue(MachineReportApproval.canDecide(approve, submittedBy = "u1", me = "u2"))
        assertFalse(MachineReportApproval.canDecide(approve, submittedBy = "U1", me = "u1"))
        assertFalse(MachineReportApproval.canDecide(setOf("tenant.machine_report.read"), submittedBy = "u1", me = "u2"))
        assertFalse(MachineReportApproval.rejectReasonValid("  "))
        assertTrue(MachineReportApproval.rejectReasonValid("Idle hours too high"))
    }

    @Test
    fun `readings and hours are formatted like the design`() {
        assertEquals("1,210.0", MachineReportRules.formatReading(BigDecimal("1210"), 1))
        assertEquals("5,016", MachineReportRules.formatReading(BigDecimal("5016"), 0))
        assertEquals("1,240", MachineReportRules.formatHours(BigDecimal("1240.0")))
        assertEquals("12.5", MachineReportRules.formatHours(BigDecimal("12.50")))
    }

    @Test
    fun `a new customer line starts with min(customer hours left, hours still to account for)`() {
        // 10 h to account for, the customer has 4 h → 4.
        assertEquals("4", MachineReportRules.startHours(BigDecimal("10"), emptyList(), BigDecimal("4.0")))
        // The customer has 20 h, 4 h already on another line → the 6 h still to account for.
        val first = ReportLineDraft.Customer("c2", "Msasani Bay Developers", "4")
        assertEquals("6", MachineReportRules.startHours(BigDecimal("10"), listOf(first), BigDecimal("20")))
        // Hundredths are kept; a non-productive line takes all that is left.
        assertEquals("1.15", MachineReportRules.startHours(BigDecimal("9"), emptyList(), BigDecimal("1.15")))
        assertEquals("6", MachineReportRules.startHours(BigDecimal("10"), listOf(first)))
        // Nothing left to account for: empty.
        assertEquals("", MachineReportRules.startHours(BigDecimal("4"), listOf(first), BigDecimal("20")))
    }
}
