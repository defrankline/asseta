package com.asseta.owner

import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.model.owner.ActivityDto
import com.asseta.core.model.owner.CashSupervisorSummaryDto
import com.asseta.core.model.owner.ExceptionDto
import com.asseta.core.model.owner.ExpenseDto
import com.asseta.core.model.owner.FuelEventDto
import com.asseta.core.model.owner.MeterResetDto
import com.asseta.core.model.owner.TenantOverviewDto
import com.asseta.core.network.NetworkFactory
import com.asseta.owner.ui.OwnerFeatures
import com.asseta.owner.ui.OwnerNavigation
import com.asseta.owner.ui.approvals.MeterResetText
import com.asseta.owner.ui.cash.CashLine
import com.asseta.owner.ui.cash.CashPeriod
import com.asseta.owner.ui.cash.CashText
import com.asseta.owner.ui.exceptions.ExceptionText
import com.asseta.owner.ui.home.KpiTone
import com.asseta.owner.ui.home.OverviewPresentation
import com.asseta.owner.ui.jobs.JobDetailText
import com.asseta.owner.ui.moreEntries
import com.asseta.owner.ui.spend.SpendText
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.math.BigDecimal
import java.time.LocalDate
import java.time.ZoneOffset

/**
 * Owner R1 depth pass: work log, job spend, meter exceptions, field spend, cash with supervisors and meter resets.
 * Wording must match the iOS Owner app exactly (same inputs, same strings); change both together.
 */
class DepthPresentationTest {
    private val json = NetworkFactory.json
    private val utc = ZoneOffset.UTC

    private fun activity(start: String, end: String?, billable: Boolean = true) = json.decodeFromString(
        ActivityDto.serializer(),
        """{"id":"$ID1","client_id":"$ID2","activity_type":"STANDBY","started_at":"$start","ended_at":${end?.let { "\"$it\"" } ?: "null"},
        "billable":$billable,"note":null}""",
    )

    private fun expense(status: String = "APPROVED", currency: String = "TZS", amount: String = "150000.0000", supplier: String? = "Tyre shop") =
        json.decodeFromString(ExpenseDto.serializer(), Samples.expense(ID1, status, currency, amount, supplier))

    private fun fuel(supplier: String? = "Puma") = json.decodeFromString(FuelEventDto.serializer(), Samples.fuel(ID1, supplier))

    private fun exception(status: String = "OPEN") = json.decodeFromString(
        ExceptionDto.serializer(),
        """{"id":"$ID1","job_id":"$ID2","machine_id":"$ID2","exception_type":"METER_DECREASE","severity":"CRITICAL","blocking":true,
        "evidence":{},"status":"$status","created_at":"2026-10-22T08:00:00Z"}""",
    )

    private fun cash(name: String, holding: String, pending: String = "0.0000") = json.decodeFromString(
        CashSupervisorSummaryDto.serializer(),
        """{"staff_member_id":"$ID1","staff_name":"$name","currency":"TZS","period_from":"2026-10-22","period_to":"2026-10-22",
        "opening":"10000.0000","floats_issued":"100000.0000","collections":"5000.0000","approved_spending":"20000.0000",
        "verified_handovers":"15000.0000","closing_outstanding":"$holding","claimed_unverified_handovers":"0.0000",
        "pending_spending":"$pending","unverified_collections":"0.0000"}""",
    )

    @Test
    fun `job work log lines`() {
        val now = java.time.Instant.parse("2026-10-21T08:15:59Z").toEpochMilli()
        assertEquals(
            "21 Oct 2026, 06:00 – 21 Oct 2026, 10:30 · 4.5 h",
            JobDetailText.workLogDetail(activity("2026-10-21T06:00:00Z", "2026-10-21T10:30:00Z"), utc, now),
        )
        assertEquals(
            "21 Oct 2026, 22:00 – 22 Oct 2026, 01:20 · 3.33 h",
            JobDetailText.workLogDetail(activity("2026-10-21T22:00:00Z", "2026-10-22T01:20:00Z"), utc, now),
        )
        // Ongoing: whole minutes elapsed so far.
        assertEquals("21 Oct 2026, 06:00 – ongoing · 2.25 h", JobDetailText.workLogDetail(activity("2026-10-21T06:00:00Z", null), utc, now))
        assertEquals(KpiTone.GOOD, JobDetailText.billableTone(true))
        assertEquals(KpiTone.MUTED, JobDetailText.billableTone(false))
        assertEquals("Billable", JobDetailText.BILLABLE)
        assertEquals("Not billable", JobDetailText.NOT_BILLABLE)
        assertEquals("No work logged yet.", JobDetailText.NO_WORK)
        assertEquals("2 open exception(s) need review.", JobDetailText.exceptions(2))
        assertNull(JobDetailText.exceptions(0))
    }

    @Test
    fun `expense and fuel rows`() {
        assertEquals("Tyre shop · 21 Oct 2026", SpendText.expenseDetail(expense(), utc))
        assertEquals("21 Oct 2026", SpendText.expenseDetail(expense(supplier = null), utc))
        assertEquals(KpiTone.WARNING, SpendText.expenseTone("PENDING_APPROVAL"))
        assertEquals(KpiTone.WARNING, SpendText.expenseTone("PENDING"))
        assertEquals(KpiTone.GOOD, SpendText.expenseTone("APPROVED"))
        assertEquals(KpiTone.CRITICAL, SpendText.expenseTone("REJECTED"))
        assertEquals(KpiTone.MUTED, SpendText.expenseTone("DRAFT"))
        assertEquals("Purchase · 40.5 L", SpendText.fuelTitle(fuel()))
        assertEquals("Puma · 21 Oct 2026", SpendText.fuelDetail(fuel(), utc))
        assertEquals("21 Oct 2026", SpendText.fuelDetail(fuel(supplier = null), utc))
        assertEquals("No expenses on this job.", SpendText.NO_JOB_EXPENSES)
        assertEquals("No fuel recorded on this job.", SpendText.NO_JOB_FUEL)
        assertEquals("No expenses yet.", SpendText.NO_EXPENSES)
        assertEquals("No fuel recorded yet.", SpendText.NO_FUEL)
    }

    @Test
    fun `approved total per currency, rejected and pending excluded`() {
        val items = listOf(
            expense("APPROVED", amount = "100000.0000"), expense("APPROVED", amount = "50000.5000"), expense("REJECTED", amount = "999.0000"),
            expense("PENDING_APPROVAL", amount = "1.0000"), expense("APPROVED", currency = "USD", amount = "20.0000"),
        )
        assertEquals(listOf("Total approved: TZS 150,000.50", "Total approved: USD 20.00"), SpendText.totalApproved(items))
        assertEquals(emptyList<String>(), SpendText.totalApproved(listOf(expense("REJECTED"))))
        assertEquals(emptyList<String>(), SpendText.totalApproved(emptyList()))
    }

    @Test
    fun `field spend filters`() {
        assertEquals(listOf("Expenses", "Fuel"), SpendText.SEGMENTS.map { it.second })
        assertEquals(listOf("Pending", "All"), SpendText.EXPENSE_FILTERS.map { it.second })
        assertEquals("PENDING_APPROVAL", SpendText.EXPENSE_FILTERS.first().first)
        assertNull(SpendText.DEFAULT_EXPENSE_FILTER)
    }

    @Test
    fun `meter exception rows`() {
        val open = exception()
        assertEquals("Meter decrease", ExceptionText.title(open))
        assertEquals("Critical · 22 Oct 2026, 08:00", ExceptionText.detail(open, utc))
        assertNull(ExceptionText.statusTone("OPEN"))
        assertEquals(KpiTone.GOOD, ExceptionText.statusTone("EXPLAINED"))
        assertEquals(KpiTone.CRITICAL, ExceptionText.statusTone("CONFIRMED"))
        assertEquals("No open exceptions.", ExceptionText.empty("OPEN"))
        assertEquals("No exceptions.", ExceptionText.empty(null))
        assertEquals(listOf("Open", "All"), ExceptionText.FILTERS.map { it.second })
        assertEquals("OPEN", ExceptionText.DEFAULT_FILTER)
        assertEquals("Blocking", ExceptionText.BLOCKING)
    }

    @Test
    fun `cash periods, order and lines`() {
        val today = LocalDate.parse("2026-10-22")
        assertEquals(today to today, CashText.range(CashPeriod.TODAY, today))
        assertEquals(LocalDate.parse("2026-10-16") to today, CashText.range(CashPeriod.WEEK, today))
        assertEquals(LocalDate.parse("2026-10-01") to today, CashText.range(CashPeriod.MONTH, today))
        assertEquals(LocalDate.parse("2026-10-01") to LocalDate.parse("2026-10-01"), CashText.range(CashPeriod.MONTH, LocalDate.parse("2026-10-01")))
        assertEquals(listOf("Today", "7 days", "This month"), CashText.PERIODS.map { it.second })
        assertEquals(CashPeriod.TODAY, CashText.DEFAULT_PERIOD)
        assertEquals(listOf("Ali", "Neema"), CashText.sorted(listOf(cash("Neema", "5000.0000"), cash("Ali", "80000.0000"))).map { it.staffName })
        assertEquals(
            listOf("Opening", "Floats issued", "Collections", "Approved spending", "Handed over (verified)"),
            CashText.lines(cash("Ali", "80000.0000")).map { it.label },
        )
        val withPending = CashText.lines(cash("Ali", "80000.0000", pending = "2500.0000"))
        assertEquals(CashLine("Spending awaiting approval", BigDecimal("2500.0000"), warning = true), withPending.last())
        assertEquals(6, withPending.size)
        assertEquals("Holding", CashText.HOLDING)
        assertEquals("No supervisor cash in this period.", CashText.EMPTY)
        assertEquals("Holding = opening + floats + collections − approved spending − verified handovers.", CashText.FOOTER)
    }

    @Test
    fun `meter reset rows and decision rules`() {
        val r = json.decodeFromString(MeterResetDto.serializer(), Samples.reset())
        assertEquals("1200 → 0 · effective 21 Oct 2026, 07:00", MeterResetText.detail(r, utc))
        assertEquals("Meter reset not found", MeterResetText.NOT_FOUND)
        assertEquals("Meter reset", MeterResetText.ROW_TITLE)
        assertEquals("Meter resets", MeterResetText.SECTION)
        assertEquals("No meter resets waiting.", MeterResetText.EMPTY)
        assertEquals("Note (required)", MeterResetText.NOTE_LABEL)
        assertEquals("Approve reset", MeterResetText.APPROVE)
        assertEquals("Reject reset", MeterResetText.REJECT)
        assertFalse(MeterResetText.canDecide("ok"))
        assertTrue(MeterResetText.canDecide("Meter replaced"))
        assertEquals("Reset approved.", MeterResetText.done(true))
        assertEquals("Reset rejected.", MeterResetText.done(false))
        assertEquals(KpiTone.WARNING, MeterResetText.statusTone("PENDING"))
        assertEquals(KpiTone.GOOD, MeterResetText.statusTone("APPROVED"))
        assertEquals(KpiTone.CRITICAL, MeterResetText.statusTone("REJECTED"))
    }

    @Test
    fun `More order, gating and titles of the new screens`() {
        val all = OwnerFeatures(
            setOf(
                "tenant.approval.read", "tenant.meter.read", "tenant.expense.read", "tenant.finance.read", "tenant.case.read",
                "tenant.notification.read",
            ),
        )
        assertEquals(
            listOf("Approvals", "Meter exceptions", "Field spend", "Cash with supervisors", "Investigations", "Notifications", "Settings"),
            moreEntries(all).map { it.first },
        )
        assertEquals(
            listOf(OwnerDestination.Exceptions(), OwnerDestination.FieldSpend, OwnerDestination.Cash),
            moreEntries(all).map { it.second }.subList(1, 4),
        )
        assertEquals(listOf("Field spend", "Settings"), moreEntries(OwnerFeatures(setOf("tenant.expense.read"))).map { it.first })
        assertTrue(OwnerFeatures(setOf("tenant.meter.approve")).meterApprove)
        assertFalse(OwnerFeatures(setOf("tenant.meter.read")).meterApprove)
        assertEquals("Meter exceptions", OwnerNavigation.title(OwnerDestination.Exceptions(ID1)))
        assertEquals("Field spend", OwnerNavigation.title(OwnerDestination.FieldSpend))
        assertEquals("Cash with supervisors", OwnerNavigation.title(OwnerDestination.Cash))
        assertEquals("Meter reset", OwnerNavigation.title(OwnerDestination.MeterReset(ID1)))
        assertNull(OwnerNavigation.tabOf(OwnerDestination.Exceptions()))
    }

    @Test
    fun `open meter exceptions tile opens the exceptions list`() {
        val o = json.decodeFromString(
            TenantOverviewDto.serializer(),
            """{"tenant_id":"$TENANT","as_of":"2026-10-22T08:00:00Z","timezone":"UTC","fleet":null,"money":null,"risk":null,
            "work":{"jobs_by_status":{},"open_exceptions":3}}""",
        )
        val row = OverviewPresentation.sections(o, cached = false, nowMs = 0).single().groups.single().rows.single { it.label == "Open meter exceptions" }
        assertEquals(OwnerDestination.Exceptions(), row.target)
        assertEquals(KpiTone.WARNING, row.tone)
    }
}
