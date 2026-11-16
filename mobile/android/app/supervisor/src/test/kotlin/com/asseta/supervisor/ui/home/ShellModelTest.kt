package com.asseta.supervisor.ui.home

import com.asseta.core.domain.accountability.PaymentMethod
import com.asseta.core.domain.reports.MachineReportRules
import com.asseta.core.domain.reports.ReportState
import com.asseta.core.model.ClientOperationStatus
import com.asseta.core.model.DecimalAmount
import com.asseta.core.model.sync.CreditInvoicePaymentPayload
import com.asseta.core.model.sync.HoursPurchasePayload
import com.asseta.core.model.sync.MachineReportLinePayload
import com.asseta.core.model.sync.MachineReportPayload
import com.asseta.core.model.sync.PurchasePaymentPayload
import com.asseta.core.sync.data.LocalInvoicePayment
import com.asseta.core.sync.data.LocalReport
import com.asseta.supervisor.ui.report.ReportTexts
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.math.BigDecimal
import java.time.LocalDateTime
import java.time.ZoneId

/** Figures and wording of Home, Money and Dashboard (approved designs; same as iOS `ShellModelTests`). */
class ShellModelTest {
    private val zone = ZoneId.of("Africa/Dar_es_Salaam")
    private val now = LocalDateTime.of(2026, 11, 16, 9, 0).atZone(zone).toInstant().toEpochMilli()
    private val hour = 3_600_000L

    private fun sale(at: Long, vararg parts: Pair<String, String>, status: ClientOperationStatus = ClientOperationStatus.ACKED) = ShellModel.sale(
        "s$at", at, status,
        HoursPurchasePayload("c", customerId = "c1", machineId = "m1", hours = "20",
            payments = parts.map { (m, a) -> PurchasePaymentPayload(m, DecimalAmount.of(BigDecimal(a)), if (m == "CREDIT") null else "x") }),
    ) { "Pwani Road" }

    @Test
    fun `money by method for the period, with handovers and expenses`() {
        val sales = listOf(
            sale(now - hour, "CASH" to "1000000", "MOBILE_MONEY" to "900000"),
            sale(now - 2 * hour, "CREDIT" to "500000"),
            sale(now - 30 * 24 * hour, "CASH" to "999"), // last month
            sale(now - hour, "CASH" to "7", status = ClientOperationStatus.FAILED), // refused: not counted
        )
        val payments = listOf(LocalInvoicePayment("p1", ClientOperationStatus.PENDING, now - hour, CreditInvoicePaymentPayload("i1", "85000", "BANK", "REF", "t")))
        val f = ShellModel.money(Period.TODAY.range(now, zone), sales, payments,
            handovers = listOf(Movement(now - hour, BigDecimal("1200000"), pending = true)),
            expenses = listOf(Movement(now - hour, BigDecimal("185000"), pending = true), Movement(now - hour, BigDecimal("170000"), pending = false)))
        assertEquals(BigDecimal("1000000"), f.byMethod[PaymentMethod.CASH])
        assertEquals(BigDecimal("85000"), f.byMethod[PaymentMethod.BANK])
        assertEquals(BigDecimal("900000"), f.byMethod[PaymentMethod.MOBILE_MONEY])
        assertEquals(BigDecimal("500000"), f.byMethod[PaymentMethod.CREDIT])
        assertEquals(BigDecimal("2485000"), f.totalSold)
        assertEquals(BigDecimal("1985000"), f.collected)
        assertEquals(BigDecimal("1200000"), f.handedOver)
        assertEquals(1, f.handedOverAwaiting)
        assertEquals(BigDecimal("355000"), f.expenses)
        assertEquals("2 receipts · 1 pending", HomeTexts.receipts(f.expenseCount, f.expensePending))
        assertEquals("Collected 1,985,000 − handed over 1,200,000 − expenses 355,000",
            HomeTexts.cashFormula(ShellModel.grouped(f.collected), ShellModel.grouped(f.handedOver), ShellModel.grouped(f.expenses)))
    }

    @Test
    fun `dashboard counts hours sold, hours used and productive share`() {
        val local = LocalReport("r9", "m2", ClientOperationStatus.PENDING, now - hour,
            MachineReportPayload("m2", lines = listOf(MachineReportLinePayload("CUSTOMER", "c1", hours = "20"), MachineReportLinePayload("NON_PRODUCTIVE", reasonId = "x", hours = "10", note = "n"))), null, null)
        val d = ShellModel.dashboard(Period.WEEK.range(now, zone), listOf(sale(now - hour, "CASH" to "1900000")), emptyList(), listOf(local)) { null }
        assertEquals(BigDecimal("20"), d.hoursSold)
        assertEquals(BigDecimal("1900000"), d.soldAmount)
        assertEquals(BigDecimal("30"), d.machineHours)
        assertEquals(BigDecimal("20"), d.productive)
        assertEquals(BigDecimal("10"), d.nonProductive)
        assertEquals(67, d.productivePercent)
        assertEquals("Productive 20 h (67%)", HomeTexts.productive("20", d.productivePercent))
        assertNull(DashboardFigures(BigDecimal.ZERO, BigDecimal.ZERO, BigDecimal.ZERO, BigDecimal.ZERO, BigDecimal.ZERO, BigDecimal.ZERO).productivePercent)
    }

    @Test
    fun `summary strip and recent wording follow the design`() {
        assertEquals("3.85M", ShellModel.compact(BigDecimal("3845000")))
        assertEquals("950,000", ShellModel.compact(BigDecimal("950000")))
        assertEquals("2.0M", ShellModel.compact(BigDecimal("2000000")))
        assertEquals("1,200", ShellModel.compact(BigDecimal("1200")))
        assertEquals("Asseta Supervisor 0.5.7", HomeTexts.settingsVersion("0.5.7"))
        // My machines rows: the last reading without trailing zeros (design "1,510 h", "3,182.8 h").
        assertEquals("Last reading 1,510 h · today 07:40", HomeTexts.lastReading(MachineReportRules.formatHours(BigDecimal("1510.00")), "today 07:40"))
        assertEquals("Last reading 3,182.8 h · 2 days ago", HomeTexts.lastReading(MachineReportRules.formatHours(BigDecimal("3182.80")), "2 days ago"))
        assertEquals("2 machines", ReportTexts.machines(2))
        assertEquals("2 due", ReportTexts.dueBadge(2))
        assertNull(ReportTexts.dueBadge(0))
        val row = ShellModel.recentSale(sale(now - 17 * hour, "CASH" to "1900000"), "TZS", now)
        assertEquals("Sold 20 h · Pwani Road", row.title)
        assertEquals("Paid", row.pill)
        assertEquals("Credit", ShellModel.recentSale(sale(now, "CASH" to "1", "CREDIT" to "2"), "TZS", now).pill)
        assertEquals("Waiting to sync", ShellModel.recentSale(sale(now, "CASH" to "1", status = ClientOperationStatus.PENDING), "TZS", now).pill)
        assertEquals("Today 08:00", ShellModel.when_(now - hour, now, zone))
        assertEquals("Yesterday 16:00", ShellModel.when_(now - 17 * hour, now, zone))
        assertEquals("3 days ago", ShellModel.ago(now - 72 * hour, now, zone))
    }

    @Test
    fun `machine states read as in the design`() {
        assertEquals("Report due", ReportTexts.state(ReportState.DUE))
        assertEquals("Awaiting approval", ReportTexts.state(ReportState.AWAITING_APPROVAL))
        assertEquals("Up to date", ReportTexts.state(ReportState.UP_TO_DATE))
        assertEquals("Next: account for 300 h", ReportTexts.nextAccount(BigDecimal("300.0")))
        assertEquals("Review — 15 h left to account for", ReportTexts.reviewButton(BigDecimal("15")))
        assertEquals("Review", ReportTexts.reviewButton(BigDecimal.ZERO))
        assertEquals("Available 140 h · after this 20 h", ReportTexts.available(BigDecimal("140"), BigDecimal("20")))
        assertEquals("EX-01 · 1,210 → 1,510", ReportTexts.splitHeader("EX-01", BigDecimal("1210.0"), BigDecimal("1510.0")))
        // Titles per step (designs) with the step line under the progress bars.
        assertEquals("Machine report", ReportTexts.title(com.asseta.supervisor.ui.report.ReportStep.READING, "EX-01 · 1,210 → 1,510"))
        assertEquals("EX-01 · 1,210 → 1,510", ReportTexts.title(com.asseta.supervisor.ui.report.ReportStep.SPLIT, "EX-01 · 1,210 → 1,510"))
        assertEquals("Machine report", ReportTexts.title(com.asseta.supervisor.ui.report.ReportStep.SPLIT, null))
        assertEquals("Review & submit", ReportTexts.title(com.asseta.supervisor.ui.report.ReportStep.REVIEW, null))
        assertEquals("Step 2 of 3 · Account for hours", ReportTexts.STEP_SPLIT)
        assertEquals("Meter photo · read by the phone · GPS ±6 m", ReportTexts.photoCaption(true, ReportTexts.gpsAccuracy(6.2)))
    }
}
