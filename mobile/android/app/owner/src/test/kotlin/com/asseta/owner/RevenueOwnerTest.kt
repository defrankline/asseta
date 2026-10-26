package com.asseta.owner

import com.asseta.core.domain.owner.DeepLinkRouter
import com.asseta.core.domain.owner.DecisionKinds
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.model.TenantAccess
import com.asseta.core.model.owner.AccountabilitySummaryDto
import com.asseta.core.model.owner.DailyMachineSheetDetailDto
import com.asseta.core.model.owner.NonRevenueApprovalDto
import com.asseta.core.model.owner.RevenueDifferenceDto
import com.asseta.core.network.NetworkFactory
import com.asseta.owner.ui.OwnerFeatures
import com.asseta.owner.ui.accountability.DashboardPresentation
import com.asseta.owner.ui.accountability.DecisionKind
import com.asseta.owner.ui.accountability.DecisionMapper
import com.asseta.owner.ui.accountability.RevenuePresentation
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate
import java.time.ZoneOffset

/** DEC-031 Phase 1 in the Owner app: revenue differences, non-revenue hours, dashboard tile, daily machine sheet. */
class RevenueOwnerTest {
    private val json = NetworkFactory.json
    private val zone = ZoneOffset.UTC
    private val diffId = "11111111-1111-4111-8111-111111111111"
    private val me = "99999999-9999-4999-8999-999999999999"
    private val all = setOf("tenant.revenue.read", "tenant.revenue.explain", "tenant.revenue.decide")

    private fun difference(status: String, extra: String = "") = json.decodeFromString(
        RevenueDifferenceDto.serializer(),
        """{"id":"$diffId","machine_id":"22222222-2222-4222-8222-222222222222","machine_code":"EX-01","period_kind":"WEEK",
           "period_key":"2026-W43","period_start":"2026-10-19T00:00:00Z","period_end":"2026-10-26T00:00:00Z","local_from":"2026-10-19",
           "local_to":"2026-10-25","job_id":null,"currency":"TZS","expected_amount":"500000.00","in_progress_amount":"0.00",
           "attributed_amount":"350000.00","difference":"150000.00","customer_work_hours":"10.00","non_revenue_hours":"1.50",
           "unexplained_hours":"0.00","unexplained_expected_amount":"0.00",
           "detail":{"jobs":[{"job_id":"33333333-3333-4333-8333-333333333333","job_number":"J-7","currency":"TZS","expected":"500000.0000",
             "in_progress":"0.0000","attributed":"350000.0000","completed":true},{"job_id":"x","currency":"USD","expected":"1","in_progress":"0","attributed":"0"}]},
           "status":"$status","case_id":null,"policy_version":"v1","opened_at":"2026-10-26T01:00:00Z","computed_at":"2026-10-26T01:00:00Z",
           "reason_id":null,"explanation_note":null,"explained_by":null,"explained_at":null,"decided_by":null,"decided_at":null,
           "decision_note":null,"adjustments":[]$extra}""",
    )

    @Test
    fun `revenue difference row and figures`() {
        val d = difference("OPEN")
        val item = DecisionMapper.revenueDifference(d, zone)
        assertEquals(DecisionKinds.REVENUE_DIFFERENCE, item.kind)
        assertEquals("TZS 150,000.00 to explain · EX-01", item.headline)
        assertEquals("19 Oct 2026 – 25 Oct 2026 · To explain", item.reason)
        assertTrue(item.pending)
        assertFalse(DecisionMapper.revenueDifference(difference("EXPLAINED"), zone).pending)

        val figures = RevenuePresentation.figures(d)
        assertEquals("Machine" to "EX-01", figures.first())
        assertTrue("Work still in progress" !in figures.map { it.first })
        assertTrue("Unexplained hours" !in figures.map { it.first })
        assertTrue(("Difference" to "TZS 150,000.00") in figures)
        assertEquals(listOf("J-7" to "Expected TZS 500,000.00 · Attributed TZS 350,000.00"), RevenuePresentation.jobs(d))
    }

    @Test
    fun `adjusted difference and explanation are shown`() {
        val d = difference(
            "EXPLAINED",
            ""","adjusted_difference":"90000.00","reason_name":"Machine moved","explanation_note":"Moved to site B","explained_by":"$me",
               "explained_by_name":"Asha","explained_at":"2026-10-26T08:00:00Z","decided_by_name":"Juma","decided_by":"88888888-8888-4888-8888-888888888888",
               "decision_note":"Agreed","adjustments":[{"id":"a1","previous_difference":"150000.00","new_difference":"90000.00","amount":"-60000.00",
               "cause_type":"non_revenue_approval","cause_id":"c1","created_by":null,"created_at":"2026-10-27T08:00:00Z"}]""",
        )
        assertEquals("TZS 90,000.00 to explain · EX-01", DecisionMapper.revenueDifference(d, zone).headline)
        assertTrue(("Difference after adjustments" to "TZS 90,000.00") in RevenuePresentation.figures(d))
        assertEquals(listOf("Reason" to "Machine moved", "Note" to "Moved to site B", "Explained by" to "Asha", "Explained" to "26 Oct 2026, 08:00"),
            RevenuePresentation.explanation(d, zone))
        assertEquals(listOf("Decided by" to "Juma", "Decision note" to "Agreed"), RevenuePresentation.decided(d))
        assertEquals(listOf("27 Oct 2026: TZS 150,000.00 → TZS 90,000.00"), RevenuePresentation.adjustments(d, zone))
    }

    @Test
    fun `actions follow permissions, status and segregation of duties`() {
        val owner = OwnerFeatures(all)
        val open = RevenuePresentation.actions(difference("OPEN"), owner, me)
        assertTrue(open.explain); assertTrue(open.confirm); assertFalse(open.approveReject); assertFalse(open.own)

        val proposedByMe = difference("EXPLANATION_PROPOSED", ""","explained_by":"$me"""")
        val mine = RevenuePresentation.actions(proposedByMe, owner, me)
        assertFalse(mine.explain); assertTrue(mine.approveReject); assertTrue(mine.own)

        val accountant = RevenuePresentation.actions(difference("OPEN"), OwnerFeatures(setOf("tenant.revenue.read", "tenant.revenue.explain")), me)
        assertTrue(accountant.explain); assertFalse(accountant.decide)

        val off = RevenuePresentation.actions(difference("OPEN"), OwnerFeatures(all, setOf(TenantAccess.REVENUE_RECONCILIATION)), me)
        assertFalse(off.explain); assertFalse(off.decide)

        val closed = RevenuePresentation.actions(difference("CONFIRMED"), owner, me)
        assertFalse(closed.explain); assertFalse(closed.decide)

        assertFalse(RevenuePresentation.noteValid(" ok  "))
        assertTrue(RevenuePresentation.noteValid("moved"))
    }

    @Test
    fun `non-revenue approval decision item`() {
        val a = json.decodeFromString(
            NonRevenueApprovalDto.serializer(),
            """{"id":"44444444-4444-4444-8444-444444444444","activity_id":"a","job_id":"j","job_number":"J-7","machine_id":"m","machine_code":"EX-01",
               "activity_type":"MOBILIZATION","started_at":"2026-10-26T06:00:00Z","ended_at":"2026-10-26T08:30:00Z","hours":"2.50",
               "reason_id":"r","reason_name":"Site move","note":"Moved to the new site","status":"PROPOSED","proposed_by":"$me",
               "proposed_by_name":"Asha","proposed_at":"2026-10-26T09:00:00Z","decided_by":null,"decided_at":null,"decision_note":null,"policy_version":"v1"}""",
        )
        val item = DecisionMapper.nonRevenue(a, zone)
        assertEquals("2.5 h Mobilization · EX-01", item.headline)
        assertTrue(item.pending)
        assertTrue(item.isOwn(me))
        assertTrue(item.fields.any { it.label == "Type" && it.value == "Mobilization" })
        assertTrue(item.fields.any { it.label == "Time" && it.value == "26 Oct 2026, 06:00 – 26 Oct 2026, 08:30" })
        // Note of at least 5 characters for both Approve and Reject (server Note).
        assertFalse(DecisionMapper.canDecide(DecisionKind.NON_REVENUE, true, "ok"))
        assertTrue(DecisionMapper.canDecide(DecisionKind.NON_REVENUE, false, "not moved"))
    }

    @Test
    fun `revenue kinds are hidden while the capability is off or without the permission`() {
        val on = OwnerFeatures(all)
        assertTrue(DecisionKind.REVENUE_DIFFERENCE in DecisionKind.visible(on))
        assertTrue(DecisionKind.NON_REVENUE in DecisionKind.visible(on))
        assertFalse(DecisionKind.REVENUE_DIFFERENCE in DecisionKind.visible(OwnerFeatures(setOf("tenant.approval.read"))))
        val off = OwnerFeatures(all, setOf(TenantAccess.REVENUE_RECONCILIATION))
        assertFalse(DecisionKind.NON_REVENUE in DecisionKind.visible(off))
        assertEquals(OwnerDestination.Approvals(), off.route(OwnerDestination.Decision(DecisionKinds.REVENUE_DIFFERENCE, diffId)))
        assertEquals(OwnerDestination.Machine("m"), off.route(OwnerDestination.DailySheet("m")))
        assertEquals(OwnerDestination.DailySheet("m"), on.route(OwnerDestination.DailySheet("m")))
    }

    @Test
    fun `deep links of revenue records`() {
        val diff = OwnerDestination.Decision(DecisionKinds.REVENUE_DIFFERENCE, diffId)
        assertEquals(diff, DeepLinkRouter.fromTarget(null, null, null, kind = "REVENUE_DIFFERENCE", recordId = diffId))
        assertEquals(diff, DeepLinkRouter.fromTarget("revenue_difference", diffId, null))
        assertEquals(diff, DeepLinkRouter.fromPath("/tenant/revenue-differences/$diffId"))
        val nonRev = OwnerDestination.Decision(DecisionKinds.NON_REVENUE, diffId)
        assertEquals(nonRev, DeepLinkRouter.fromPush(mapOf("kind" to "NON_REVENUE_APPROVAL", "record_id" to diffId))?.destination)
        assertEquals(nonRev, DeepLinkRouter.fromTarget("non_revenue_approval", diffId, null))
        assertEquals(nonRev, DeepLinkRouter.fromPath("/tenant/non-revenue-approvals/$diffId"))
        assertEquals(OwnerDestination.Approvals(), DeepLinkRouter.fromPath("/tenant/revenue-differences"))
        assertEquals(OwnerDestination.Fleet, DeepLinkRouter.fromPath("/tenant/engine-hours/daily-sheet"))
    }

    @Test
    fun `dashboard tile`() {
        val body = """{"as_of":"2026-10-26T08:00:00Z","policy_version":"v3","hidden_tiles":[],"unavailable_tiles":[],
            "revenue_differences":{"open":2,"awaiting_decision":1,"amounts":[{"currency":"TZS","count":3,"amount":"250000.00"}],
            "oldest_open_days":4,"window_days":30,"explained_in_window":5,"confirmed_in_window":1,"cleared_in_window":0,
            "items":[{"id":"x","machine_id":"m","machine_code":"EX-01","period_key":"2026-10-25","local_from":"2026-10-25","local_to":"2026-10-25",
            "currency":"TZS","difference":"100000.00","status":"OPEN"}]}}"""
        val s = json.decodeFromString(AccountabilitySummaryDto.serializer(), body)
        val tile = DashboardPresentation.tiles(s, OwnerFeatures(all)).single { it.key == "revenue_differences" }
        assertEquals(
            listOf("To explain" to "2", "Awaiting a decision" to "1", "Amount" to "3 · TZS 250,000.00", "Oldest open" to "4 days",
                "Explained" to "5", "Confirmed" to "1", "Cleared" to "0", "EX-01 · 25 Oct 2026" to "TZS 100,000.00"),
            tile.rows,
        )
        assertEquals(OwnerDestination.Approvals(), tile.link)
        assertEquals("Last 30 days", tile.footer)
        // Switched off (by /me or by the summary) or no permission: no tile.
        assertTrue(DashboardPresentation.tiles(s.copy(disabledCapabilities = listOf(TenantAccess.REVENUE_RECONCILIATION)), OwnerFeatures(all)).none { it.key == "revenue_differences" })
        assertTrue(DashboardPresentation.tiles(s, OwnerFeatures(setOf("tenant.accountability.read"))).none { it.key == "revenue_differences" })
        assertNull(RevenuePresentation.tile(null))
    }

    @Test
    fun `daily machine sheet day`() {
        val d = json.decodeFromString(
            DailyMachineSheetDetailDto.serializer(),
            """{"machine_id":"m","machine_code":"EX-01","day":"2026-10-25","first_reading":"1200.0","last_reading":"1210.5","reading_count":2,
               "engine_hours":"10.50","customer_work_hours":"8.00","non_revenue_hours":"1.50","non_revenue_by_type":{"MOBILIZATION":"1.50"},
               "non_revenue_pending_hours":"0.00","revenue_hours":"8.00","approved_non_customer_hours":"0.00","identified_variance_hours":"0.00",
               "unexplained_hours":"1.00","pending_review_hours":"0.00","fuel_litres":"40.0",
               "jobs":[{"job_id":"j","job_number":"J-7","billing_mode":"INVOICE","status":"COMPLETED","customer_name":"Acme","customer_work_hours":"8.00","revenue_hours":"8.00"}],
               "money":[{"currency":"TZS","expected":"400000","in_progress":"0","attributed":"300000","difference":"100000","unexplained_hours":"1.00","unexplained_expected":"50000"}],
               "flags":["UNEXPLAINED_HOURS","REVENUE_DIFFERENCE"],"readings":[{"id":"r1","kind":"OPENING","captured_at":"2026-10-25T06:00:00Z","reading":"1200.0","state":"ACCEPTED","job_id":"j"}],
               "segments":[],"money_sources":[],"flag_records":[],"fuel_events":[]}""",
        )
        assertEquals(
            listOf("Engine hours" to "10.5 h", "Customer work" to "8 h", "Non-revenue" to "1.5 h", "Non-revenue · Mobilization" to "1.5 h",
                "Revenue hours" to "8 h", "Unexplained" to "1 h"),
            RevenuePresentation.hoursRows(d),
        )
        assertEquals(
            listOf("Expected revenue" to "TZS 400,000.00", "Money attributed" to "TZS 300,000.00", "Difference" to "TZS 100,000.00",
                "Unexplained hours expected as revenue" to "TZS 50,000.00"),
            RevenuePresentation.moneyRows(d.money.single()),
        )
        assertEquals(listOf("J-7 · Acme" to "8 h"), RevenuePresentation.jobRows(d))
        assertEquals("Unexplained hours · Revenue difference", RevenuePresentation.flags(d.flags))
        assertEquals("25 Oct 2026", RevenuePresentation.day(d.day))
        assertEquals(LocalDate.of(2026, 10, 13) to LocalDate.of(2026, 10, 26), RevenuePresentation.window(LocalDate.of(2026, 10, 26)))
    }
}
