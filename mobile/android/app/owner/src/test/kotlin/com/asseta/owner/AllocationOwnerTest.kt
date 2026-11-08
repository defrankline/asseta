package com.asseta.owner

import com.asseta.core.domain.owner.DeepLinkRouter
import com.asseta.core.domain.owner.DecisionKinds
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.model.TenantAccess
import com.asseta.core.model.owner.AllocationDayDto
import com.asseta.core.model.owner.DailyReportDto
import com.asseta.core.model.owner.SheetMoneyDto
import com.asseta.core.model.owner.WorkAllocationDto
import com.asseta.core.network.NetworkFactory
import com.asseta.owner.ui.OwnerFeatures
import com.asseta.owner.ui.accountability.AllocationPresentation
import com.asseta.owner.ui.accountability.AllocationTexts
import com.asseta.owner.ui.accountability.DailyReportPresentation
import com.asseta.owner.ui.accountability.DecisionKind
import com.asseta.owner.ui.accountability.DecisionMapper
import com.asseta.owner.ui.accountability.RevenuePresentation
import kotlinx.serialization.json.jsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.ZoneOffset

/** DEC-032 Phase 1 in the Owner app: daily report review, allocation corrections, machine-day ledger, value at risk. */
class AllocationOwnerTest {
    private val json = NetworkFactory.json
    private val me = "99999999-9999-4999-8999-999999999999"
    private val group = "44444444-4444-4444-8444-444444444444"
    private val report = "55555555-5555-4555-8555-555555555555"

    private fun dailyReport(status: String = "SUBMITTED", extra: String = "") = json.decodeFromString(
        DailyReportDto.serializer(),
        """{"id":"$report","machine_id":"m1","machine_code":"EX-01","report_date":"2026-10-26","opening_ref":"a","opening_reading":"100.00","closing_ref":"b",
           "closing_reading":"110.00","total_hours":"10.00","billable_hours":"7.00","unbillable_hours":"2.00","difference_hours":"1.00",
           "unbillable":[{"reason_id":"r1","reason_name":"Rain","hours":"2.00"}],"allocations":[],"status":"$status","submitted_by":"$me","submitted_by_name":"Asha",
           "submitted_at":"2026-10-26T18:00:00Z","client_created_at":"2026-10-26T18:00:00Z"$extra}""",
    )

    private fun allocation(kind: String, hours: String, extra: String = "") = json.decodeFromString(
        WorkAllocationDto.serializer(),
        """{"id":"a-$hours","machine_id":"m1","machine_code":"EX-01","work_date":"2026-10-26","start_reading":"100","start_at":"2026-10-26T08:00:00Z","end_reading":"105",
           "end_at":"2026-10-26T13:00:00Z","hours":"$hours","kind":"$kind","status":"PROPOSED","correction_group_id":"$group","correction_reason":"Wrong customer",
           "recorded_by":"$me","recorded_by_name":"Asha","created_at":"2026-10-27T08:00:00Z"$extra}""",
    )

    @Test
    fun `report row, figures and own report`() {
        val r = dailyReport(extra = ""","is_late":true,"is_duplicate":true""")
        val item = DecisionMapper.dailyReport(r)
        assertEquals("EX-01 · 26 Oct 2026", item.headline)
        assertEquals("10 h in total · 7 h billable · 2 h unbillable", item.reason)
        assertTrue(item.pending)
        assertTrue(item.isOwn(me))
        val figures = DailyReportPresentation.figures(r, ZoneOffset.UTC).toMap()
        assertEquals("1 h", figures[AllocationTexts.NOT_ACCOUNTED])
        assertEquals("Asha", figures[AllocationTexts.SUBMITTED_BY])
        assertEquals(listOf(AllocationTexts.FLAG_LATE, AllocationTexts.FLAG_REPEAT), DailyReportPresentation.flags(r))
        assertTrue(DailyReportPresentation.isOwn(r, me))
        assertFalse(DailyReportPresentation.isOwn(r, "someone-else"))
        assertFalse(DailyReportPresentation.canReview(dailyReport("REVIEWED")))
    }

    @Test
    fun `corrections become one row per group and show the original`() {
        val parts = listOf(
            allocation("CUSTOMER_WORK", "3.00", ""","customer_name":"Mgodi Ltd","job_number":"J-9""""),
            allocation("UNEXPLAINED", "2.00"),
        )
        val row = DecisionMapper.allocationCorrections(parts).single()
        assertEquals(group, row.id)
        assertEquals("EX-01 · 26 Oct 2026 · 5 h", row.headline)
        assertTrue(row.pending)
        assertTrue(row.isOwn(me))
        val original = allocation("UNEXPLAINED", "5.00")
        val fields = DecisionMapper.allocationCorrection(group, "PROPOSED", parts, original).fields.associate { it.label to it.value }
        assertEquals("Unexplained · 5 h", fields[AllocationTexts.ORIGINAL])
        assertEquals("3 h · Mgodi Ltd · J-9", fields[AllocationTexts.part("CUSTOMER_WORK")])
        assertEquals("2 h", fields[AllocationTexts.part("UNEXPLAINED")])
    }

    @Test
    fun `new kinds need meter read and engine hours`() {
        val read = OwnerFeatures(setOf("tenant.meter.read"))
        assertTrue(DecisionKind.DAILY_REPORT in DecisionKind.visible(read))
        assertTrue(DecisionKind.ALLOCATION_CORRECTION in DecisionKind.visible(read))
        assertFalse(DecisionKind.DAILY_REPORT in DecisionKind.visible(OwnerFeatures(emptySet())))
        assertFalse(DecisionKind.ALLOCATION_CORRECTION in DecisionKind.visible(read.copy(disabled = setOf(TenantAccess.ENGINE_HOURS))))
    }

    @Test
    fun `deep links open the exact record`() {
        val report = OwnerDestination.Decision(DecisionKinds.DAILY_REPORT, this.report)
        val correction = OwnerDestination.Decision(DecisionKinds.ALLOCATION_CORRECTION, group)
        assertEquals(report, DeepLinkRouter.fromTarget(null, null, null, kind = "DAILY_REPORT", recordId = this.report))
        assertEquals(correction, DeepLinkRouter.fromTarget(null, null, null, kind = "WORK_ALLOCATION_CORRECTION", recordId = group))
        assertEquals(report, DeepLinkRouter.fromTarget("daily_report", this.report, null))
        assertEquals(report, DeepLinkRouter.fromPath("/tenant/daily-reports/${this.report}"))
        assertEquals(correction, DeepLinkRouter.fromPath("/tenant/work-allocations/corrections/$group"))
        assertEquals(OwnerDestination.Approvals(), DeepLinkRouter.fromPath("/tenant/daily-reports"))
        assertEquals(OwnerDestination.Approvals(), DeepLinkRouter.fromPath("/tenant/work-allocations"))
    }

    @Test
    fun `machine day ledger rows and lots`() {
        val day = AllocationDayDto("m1", "2026-10-26", "10.00", "7.00", "1.50", "1.50", "10.00", "0.00", true)
        val rows = AllocationPresentation.dayRows(day).toMap()
        assertEquals("10 h", rows[AllocationTexts.DAY_TOTAL])
        assertEquals("1.5 h", rows[AllocationTexts.DAY_UNEXPLAINED])
        val a = allocation("CUSTOMER_WORK", "3.00", ""","lots":[{"purchase_id":"p1","purchase_number":"HP-7","hours":"3.00"}]""")
        assertEquals(listOf("From HP-7: 3 h"), AllocationPresentation.lots(a))
        assertNull(AllocationPresentation.who("UNEXPLAINED", "x", "y", "z", "w"))
        assertEquals("Maintenance", AllocationPresentation.who("AUTHORIZED_ACTIVITY", null, null, null, "MAINTENANCE"))
    }

    @Test
    fun `machine days open with meter read when revenue checks are off`() {
        val ledgerOnly = OwnerFeatures(setOf("tenant.meter.read"), setOf(TenantAccess.REVENUE_RECONCILIATION))
        assertFalse(ledgerOnly.revenueRead)
        assertTrue(ledgerOnly.machineDays)
        val day = OwnerDestination.SheetDay("m1", "2026-10-26")
        assertEquals(day, ledgerOnly.route(day))
        val none = OwnerFeatures(emptySet(), setOf(TenantAccess.REVENUE_RECONCILIATION))
        assertEquals(OwnerDestination.Machine("m1"), none.route(day))
        val engineOff = OwnerFeatures(setOf("tenant.meter.read"), setOf(TenantAccess.REVENUE_RECONCILIATION, TenantAccess.ENGINE_HOURS))
        assertFalse(engineOff.machineDays)
        assertTrue(OwnerFeatures(setOf("tenant.revenue.read")).machineDays)
    }

    @Test
    fun `value at risk stays apart from expected and the difference`() {
        val m = SheetMoneyDto("TZS", "500", "0", "400", "100", valueAtRisk = "75")
        val rows = RevenuePresentation.moneyRows(m)
        assertEquals(AllocationTexts.VALUE_AT_RISK, rows.last().first)
        assertTrue(RevenuePresentation.moneyRows(SheetMoneyDto("TZS", "500", "0", "400", "100")).none { it.first == AllocationTexts.VALUE_AT_RISK })
        val tile = json.parseToJsonElement("""{"value_at_risk":[{"currency":"TZS","amount":"75.00"},{"currency":"USD","amount":"3.00"}]}""").jsonObject
        assertEquals(2, AllocationPresentation.valueAtRiskRows(tile).size)
        assertTrue(AllocationPresentation.valueAtRiskRows(json.parseToJsonElement("{}").jsonObject).isEmpty())
    }
}
