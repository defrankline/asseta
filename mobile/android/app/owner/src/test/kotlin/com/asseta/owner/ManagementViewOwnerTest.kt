package com.asseta.owner

import com.asseta.core.domain.owner.DecisionKinds
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.domain.owner.RecordKinds
import com.asseta.core.model.owner.AccountabilitySummaryDto
import com.asseta.core.model.owner.ApprovalsTileDto
import com.asseta.core.model.owner.EmployeeAccountabilityDto
import com.asseta.core.model.owner.LookupMatchDto
import com.asseta.core.network.NetworkFactory
import com.asseta.owner.ui.OwnerFeatures
import com.asseta.owner.ui.OwnerNavigation
import com.asseta.owner.ui.accountability.DashboardPresentation
import com.asseta.owner.ui.accountability.EmployeePresentation
import com.asseta.owner.ui.accountability.FigureTarget
import com.asseta.owner.ui.accountability.LookupPresentation
import com.asseta.owner.ui.accountability.ManagementLinks
import com.asseta.owner.ui.accountability.ManagementPresentation
import com.asseta.owner.ui.accountability.ManagementTexts
import com.asseta.owner.ui.moreEntries
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.ZoneOffset

/** DEC-032 Phase 4 on the Owner app: the four groups, where each figure opens, the employee screen, lookup. */
class ManagementViewOwnerTest {
    private val json = NetworkFactory.json
    private val web = "https://example.test/"
    private val id = "11111111-1111-4111-8111-111111111111"
    private val all = OwnerFeatures(
        setOf(
            "tenant.finance.read", "tenant.finance.verify", "tenant.hours.read", "tenant.meter.read", "tenant.fleet.read", "tenant.job.read", "tenant.case.read",
            "tenant.accountability.read", "tenant.accountability.employee.read", "tenant.lookup.read", "tenant.approval.read", "tenant.adjustment.read",
        ),
    )

    private fun target(route: String, f: OwnerFeatures = all) = ManagementLinks.target(route, f, web)

    private fun app(route: String, f: OwnerFeatures = all) = (target(route, f) as? FigureTarget.App)?.destination

    private fun webOf(route: String, f: OwnerFeatures = all) = (target(route, f) as? FigureTarget.Web)?.url

    @Test
    fun `records open the same screen as a notification`() {
        assertEquals(OwnerDestination.HoursPurchase(id), app("/tenant/hours/purchases/$id"))
        assertEquals(OwnerDestination.Handover(id), app("/tenant/finance/cash/remittances/$id"))
        assertEquals(OwnerDestination.CashRecord(RecordKinds.CASH_TRANSFER, id), app("/tenant/finance/cash/transfers/$id"))
        assertEquals(OwnerDestination.Job(id), app("/tenant/jobs/$id"))
        assertEquals(OwnerDestination.Decision(DecisionKinds.ADJUSTMENT_REQUEST, id), app("/tenant/finance/adjustments/requests/$id"))
        assertEquals(OwnerDestination.EmployeeAccountability(id), app("/tenant/staff/$id/accountability"))
    }

    @Test
    fun `lists that the app shows open their screen`() {
        assertEquals(OwnerDestination.CustomerHours, app("/tenant/hours/balances"))
        assertEquals(OwnerDestination.HoursStatement(id), app("/tenant/hours/balances?customer_id=$id"))
        assertEquals(OwnerDestination.Cash, app("/tenant/finance/cash"))
        assertEquals(OwnerDestination.RemittanceOverdue(), app("/tenant/finance/cash/remittance-overdue?local_day=2026-11-09"))
        assertEquals(OwnerDestination.Exceptions(), app("/tenant/exceptions?status=OPEN&exception_type=METER_DECREASE"))
        assertEquals(OwnerDestination.Cases, app("/tenant/cases?closure_proposed=true"))
        assertEquals(OwnerDestination.Approvals(), app("/tenant/accountability/pending-adjustments"))
        assertEquals(OwnerDestination.Approvals(), app("/tenant/hours/transfers?status=PENDING"))
        assertEquals(OwnerDestination.Approvals(), app("/tenant/finance/cash/remittances?status=CLAIMED"))
        assertEquals(OwnerDestination.Approvals(), app("/tenant/finance/cash/remittances?partial_reason_pending=true"))
        assertEquals(OwnerDestination.Approvals(), app("/tenant/finance/cash/variances?status=CLOSURE_PROPOSED"))
        assertEquals(OwnerDestination.Approvals(), app("/tenant/daily-reports?status=SUBMITTED"))
        assertEquals(OwnerDestination.Approvals(), app("/tenant/jobs?status=PENDING_APPROVAL"))
    }

    @Test
    fun `lists the app does not show open the web, as relative tenant links only`() {
        assertEquals("https://example.test/tenant/hours/ledger?entry_type=ACTIVATED", webOf("/tenant/hours/ledger?entry_type=ACTIVATED"))
        assertEquals("https://example.test/tenant/hours/purchases?queue=UNPAID", webOf("/tenant/hours/purchases?queue=UNPAID"))
        assertEquals("https://example.test/tenant/customer-payments?method=CASH", webOf("/tenant/customer-payments?method=CASH"))
        assertEquals("https://example.test/tenant/work-allocations?kind=UNEXPLAINED", webOf("/tenant/work-allocations?kind=UNEXPLAINED"))
        assertEquals("https://example.test/tenant/finance/cash/variances?direction=SHORTAGE", webOf("/tenant/finance/cash/variances?direction=SHORTAGE"))
        assertEquals("https://example.test/tenant/daily-reports?status=RETURNED", webOf("/tenant/daily-reports?status=RETURNED"))
        assertEquals("https://example.test/tenant/finance/adjustments/$id", webOf("/tenant/finance/adjustments/$id"))
        assertEquals("https://example.test/tenant/work-allocations/$id", webOf("/tenant/work-allocations/$id"))
        assertNull(target("https://evil.test/x"))
        assertNull(target("//evil.test/x"))
        assertNull(target(""))
        assertNull(ManagementLinks.target(null, all, web))
    }

    @Test
    fun `a role that may not open the screen gets the web`() {
        val none = OwnerFeatures(setOf("tenant.accountability.read"))
        assertEquals("https://example.test/tenant/finance/cash", webOf("/tenant/finance/cash", none))
        assertEquals("https://example.test/tenant/staff/$id/accountability", webOf("/tenant/staff/$id/accountability", none))
    }

    @Test
    fun `excavator rows open the daily sheet, else the machine`() {
        val r = ManagementLinks.excavatorTarget(id, "/tenant/work-allocations?machine_id=$id", all, web)
        assertEquals(FigureTarget.App(OwnerDestination.DailySheet(id)), r)
        val fleet = OwnerFeatures(setOf("tenant.fleet.read"))
        assertEquals(FigureTarget.App(OwnerDestination.Machine(id)), ManagementLinks.excavatorTarget(id, "/tenant/x", fleet, web))
    }

    private val money = """{"lines":[{"currency":"TZS","count":2,"amount":"150000"}],"count":2,"route":"/tenant/customer-payments?method=CASH"}"""
    private val none = """{"lines":[],"count":0,"route":"/tenant/x"}"""
    private val hours = """{"hours":"12.5","count":3,"route":"/tenant/hours/ledger"}"""
    private val queue = """{"count":1,"hours":"8","amounts":[{"currency":"TZS","count":1,"amount":"40000"}],"items":[],"route":"/tenant/hours/purchases?queue=UNPAID"}"""
    private val count = """{"count":4,"route":"/tenant/daily-reports?status=SUBMITTED"}"""

    private fun summary(sections: String) = json.decodeFromString(
        AccountabilitySummaryDto.serializer(),
        """{"as_of":"2026-11-09T08:00:00Z","policy_version":"v1","hidden_tiles":[],"unavailable_tiles":[],
           "cash":{"custodians":[],"transfers_awaiting_acknowledgement":[],"floats_awaiting_acknowledgement":[],"remittances_awaiting_confirmation":[],"partial_remittances_in_window":0},
           "payments":{"awaiting_confirmation":[]},
           "outstanding_approvals":{"approval_requests":1,"payments_to_verify":0,"remittances_to_verify":0,"cash_retentions":0,"custody_adjustments":0,"write_offs":0,"total":3,"adjustment_requests":2,"meter_resets":0}
           $sections}""",
    )

    private val hoursSection = """,
        "hours_section":{"purchased":$hours,"purchased_value":$money,"activated":$hours,"consumed":$hours,"remaining":{"hours":"4","count":1,"route":"/tenant/hours/balances"},
          "remaining_by_customer":[{"customer_id":"$id","customer_name":"Acacia","activated":"8","consumed":"4","remaining":"4","route":"/tenant/hours/balances?customer_id=$id"}],
          "remaining_customers_total":3,"unpaid_purchases":$queue,"unconfirmed_purchases":$queue,"awaiting_activation":$queue}"""

    private val cashSection = """,
        "cash_section":{"collected":$money,"held_by_employee":[{"staff_member_id":"$id","staff_member_name":"Asha","currency":"TZS","outstanding":"90000","in_transit_out":"10000","claimed_unverified_handovers":"0","pending_floats":"0","approved_retention":"0","route":"/tenant/staff/$id/accountability"}],
          "transferred":$none,"in_transit":$money,"declared_for_remittance":$money,"confirmed_by_company":$money,"outstanding":$money,"unconfirmed_remittances":$money,"disputed_remittances":$none,"disputed_transfers":$none}"""

    private val exceptionsSection = """,
        "exceptions_section":{"unexplained_engine_hours":$hours,"shortages":$money,"overages":$none,"shortages_opened_in_period":$money,"overages_opened_in_period":$none,
          "pending_adjustments":{"total":2,"by_kind":[{"kind":"adjustment_requests","count":2,"oldest_at":"2026-11-08T08:00:00Z","route":"/tenant/finance/adjustments/requests?status=PROPOSED"}],"oldest":[],"route":"/tenant/accountability/pending-adjustments"},
          "unauthorized_attempts":{"permission_denied":2,"segregation_of_duties":1,"since":"2026-11-01T00:00:00Z","route":"/tenant/security-events"},
          "unconfirmed_payments":$money,
          "outstanding_approvals":{"total":3,"by_kind":[{"kind":"hours_transfers","count":3,"oldest_at":null,"route":"/tenant/hours/transfers?status=PENDING"}]},
          "overdue_reports":{"total":0,"missing_daily_reports":{"count":0,"route":"/tenant/daily-reports"},"remittances_overdue_today":{"count":0,"route":"/tenant/finance/cash/remittance-overdue"}},
          "unresolved_variances":{"total":1,"by_source":[{"source":"CUSTOMER_HOUR","unit":"HOURS","count":1,"amounts":[],"route":"/tenant/finance/cash/variances?source_type=CUSTOMER_HOUR"}]},
          "changeover_jobs_awaiting_approval":{"count":1,"oldest_days":5,"items":[{"job_id":"$id","job_number":"J-9","machine_id":"$id","machine_code":"EX-1","customer_id":"$id","customer_name":"Acacia","changed_over_at":"2026-11-04T08:00:00Z","days_waiting":5,"route":"/tenant/jobs/$id"}]}}"""

    private fun presentation() = ManagementPresentation(all, web, ZoneOffset.UTC)

    private fun row(groupKey: String, key: String, s: AccountabilitySummaryDto) =
        presentation().groups(s).first { it.key == groupKey }.rows.first { it.key == key }

    @Test
    fun `the four groups come in guideline order and only when present`() {
        val s = summary(hoursSection + cashSection + exceptionsSection)
        assertEquals(listOf("hours_section", "cash_section", "exceptions_section"), presentation().groups(s).map { it.key })
        assertTrue(presentation().groups(summary("")).isEmpty())
    }

    @Test
    fun `figures read with their unit and carry their link`() {
        val s = summary(hoursSection + cashSection + exceptionsSection)
        assertEquals("12.5 h", row("hours_section", "purchased", s).value)
        assertEquals("TZS 150,000.00", row("hours_section", "purchased_value", s).value)
        val queueRow = row("hours_section", "unpaid", s)
        assertEquals("1 · 8 h", queueRow.value)
        assertEquals("TZS 40,000.00", queueRow.caption)
        assertEquals("https://example.test/tenant/hours/purchases?queue=UNPAID", (queueRow.target as FigureTarget.Web).url)
        assertEquals(FigureTarget.App(OwnerDestination.HoursStatement(id)), row("hours_section", "customer-$id", s).target)
        assertEquals(ManagementTexts.NONE, row("exceptions_section", "overages", s).value)
        val held = row("cash_section", "held-$id-TZS", s)
        assertEquals("In transit TZS 10,000.00", held.caption)
        assertEquals(FigureTarget.App(OwnerDestination.EmployeeAccountability(id)), held.target)
        val attempts = row("exceptions_section", "attempts", s)
        assertEquals("3", attempts.value)
        assertEquals("Denied 2 · Second person required 1", attempts.caption)
    }

    @Test
    fun `changeover rows and approval kinds open their records`() {
        val s = summary(exceptionsSection)
        assertEquals(FigureTarget.App(OwnerDestination.Job(id)), row("exceptions_section", "changeover-$id", s).target)
        assertEquals("Oldest 5 days", row("exceptions_section", "changeover", s).caption)
        val kind = row("exceptions_section", "approval-hours_transfers", s)
        assertEquals("Hours transfers", kind.label)
        assertEquals(FigureTarget.App(OwnerDestination.Approvals()), kind.target)
        assertTrue(row("exceptions_section", "pending", s).heading)
    }

    @Test
    fun `a footer says when not every customer is shown`() {
        assertEquals("Showing 1 of 3 customers.", presentation().groups(summary(hoursSection)).first().footer)
    }

    @Test
    fun `old tiles stay until their section replaces them`() {
        val without = DashboardPresentation.tiles(summary(""), all).map { it.key }
        assertTrue("approvals" in without && "cash" in without && "payments" in without)
        val withAll = DashboardPresentation.tiles(summary(hoursSection + cashSection + exceptionsSection), all).map { it.key }
        assertFalse("approvals" in withAll || "cash" in withAll || "payments" in withAll)
    }

    @Test
    fun `the approvals tile shows the new counts that are present and not zero`() {
        val a = summary("").outstandingApprovals!!
        assertEquals(listOf("Adjustment requests" to "2"), ManagementPresentation.newApprovalCounts(a))
        assertEquals(emptyList<Pair<String, String>>(), ManagementPresentation.newApprovalCounts(ApprovalsTileDto(0, 0, 0, 0, 0, 0, 0)))
        assertTrue(DashboardPresentation.tiles(summary(""), all).first { it.key == "approvals" }.rows.contains("Adjustment requests" to "2"))
    }

    private val employee = json.decodeFromString(
        EmployeeAccountabilityDto.serializer(),
        """{"identity":{"staff_member_id":"$id","full_name":"Asha","employee_code":"E-1","kind":"STAFF","is_active":true,"phone":null,"login_email":null,"user_id":null,"roles":["Supervisor"]},
           "date_from":"2026-11-01","date_to":"2026-11-09",
           "cash_held":[{"as_of":"2026-11-09T08:00:00Z","staff_member_id":"$id","currency":"TZS","outstanding":"90000","claimed_unverified_handovers":"5000","pending_spending":"0"}],
           "collections":[{"record_type":"customer_payment","id":"$id","reference":"COL-1","status":"CLAIMED","occurred_at":"2026-11-02T08:00:00Z","amount":"1000","currency":"TZS","route":"/tenant/customer-payments/$id"},
                          {"record_type":"customer_payment","id":"$id","reference":"COL-2","status":"VERIFIED","occurred_at":"2026-11-03T08:00:00Z","amount":"500","currency":"TZS","route":"/tenant/customer-payments/$id"}],
           "remittances":[{"record_type":"cash_handover","id":"$id","reference":"RMT-1","status":"CLAIMED","occurred_at":"2026-11-04T08:00:00Z","amount":"200","currency":"TZS","route":"/tenant/finance/cash/remittances/$id"}],
           "reports_submitted":[],"scorecard_items":[{"record_type":"job_exception","id":null,"occurred_at":"2026-11-04T08:00:00Z"}],"scorecard_visible":false,"truncated":["collections"]}""",
    )

    @Test
    fun `the employee screen counts its lists and opens records`() {
        val p = EmployeePresentation(all, web, ZoneOffset.UTC)
        val figures = p.figures(employee).toMap()
        assertEquals("2 · TZS 1,500.00", figures[ManagementTexts.LIST_COLLECTIONS])
        assertEquals("1 · TZS 200.00", figures[ManagementTexts.LIST_REMITTANCES])
        assertEquals("0", figures[ManagementTexts.LIST_FLOATS])
        assertFalse(ManagementTexts.LIST_SCORECARD in figures)
        val lists = p.lists(employee)
        assertEquals(listOf(ManagementTexts.LIST_COLLECTIONS, ManagementTexts.LIST_REMITTANCES), lists.map { it.title })
        assertEquals(FigureTarget.App(OwnerDestination.Handover(id)), lists[1].rows.single().target)
        assertEquals("https://example.test/tenant/customer-payments/$id", (lists[0].rows[0].target as FigureTarget.Web).url)
        val cash = p.cash(employee.cashHeld.single())
        assertEquals("TZS 90,000.00", cash.value)
        assertEquals("Claimed TZS 5,000.00", cash.caption)
    }

    @Test
    fun `lookup shows what when who and balance`() {
        val p = LookupPresentation(all, web, ZoneOffset.UTC)
        val m = json.decodeFromString(
            LookupMatchDto.serializer(),
            """{"record_type":"hours_purchase","id":"$id","reference":"HP-1","route":"/tenant/hours/purchases/$id","status":"ACTIVE","recorded_by_name":"Asha","recorded_at":"2026-11-02T08:00:00Z","customer_name":"Acacia","amount":"1000","currency":"TZS","balance_outstanding":"4","balance_unit":"HOURS","hours_remaining":"4"}""",
        )
        assertEquals("Hours purchase", p.title(m))
        assertEquals("HP-1 · Active", p.subtitle(m))
        val rows = p.rows(m).toMap()
        assertTrue(rows[ManagementTexts.LOOKUP_RECORDED_BY]!!.startsWith("Asha · "))
        assertEquals("4 h", rows[ManagementTexts.LOOKUP_BALANCE])
        assertEquals("TZS 1,000.00", rows[ManagementTexts.LOOKUP_AMOUNT])
        assertFalse(ManagementTexts.LOOKUP_DECIDED_BY in rows)
        assertEquals(FigureTarget.App(OwnerDestination.HoursPurchase(id)), p.target(m))
    }

    @Test
    fun `find a reference and employee links follow their permissions`() {
        val entries = moreEntries(all).map { it.second }
        assertTrue(OwnerDestination.Lookup in entries)
        assertFalse(OwnerDestination.Lookup in moreEntries(OwnerFeatures(setOf("tenant.accountability.read"))).map { it.second })
        assertEquals(OwnerDestination.More, OwnerFeatures(emptySet()).route(OwnerDestination.Lookup))
        assertEquals(OwnerDestination.Accountability, OwnerFeatures(emptySet()).route(OwnerDestination.EmployeeAccountability(id)))
        assertEquals(ManagementTexts.LOOKUP_TITLE, OwnerNavigation.title(OwnerDestination.Lookup))
        assertEquals("Asha", OwnerNavigation.title(OwnerDestination.EmployeeAccountability(id, "Asha")))
    }
}
