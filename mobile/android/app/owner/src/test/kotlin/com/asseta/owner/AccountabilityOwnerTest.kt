package com.asseta.owner

import com.asseta.core.domain.owner.DataSource
import com.asseta.core.domain.owner.DeepLinkRouter
import com.asseta.core.domain.owner.DecisionKinds
import com.asseta.core.domain.owner.RecordKinds
import com.asseta.core.domain.owner.MutationCheck
import com.asseta.core.domain.owner.OwnerAction
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.model.owner.AccountabilitySummaryDto
import com.asseta.core.network.NetworkFactory
import com.asseta.owner.data.ActionResult
import com.asseta.owner.data.Load
import com.asseta.owner.ui.OwnerFeatures
import com.asseta.owner.ui.OwnerNavigation
import com.asseta.owner.ui.OwnerSession
import com.asseta.owner.ui.accountability.DashboardPresentation
import com.asseta.owner.ui.accountability.DecisionKind
import com.asseta.owner.ui.accountability.DecisionMapper
import com.asseta.owner.ui.cash.HandoverText
import com.asseta.owner.ui.moreEntries
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Owner accountability: approvals sections, decisions (segregation of duties), dashboard, remittance and deep links. */
class AccountabilityOwnerTest {
    private val h = OwnerHarness()

    @After fun tearDown() = h.close()

    private val discount = """{"id":"$ID1","customer_id":"$ID2","percent":"10.00","effective_from":"2026-10-25T00:00:00Z","effective_to":null,
        "reason":"Loyal customer","reason_code_id":null,"status":"PROPOSED","proposed_by":"u-1","proposed_at":"2026-10-25T08:00:00Z",
        "decided_by":null,"decided_at":null,"decision_note":null,"revoked_by":null,"revoked_at":null,"revoke_reason":null,"version":1}"""

    private val baseline = """{"id":"$ID1","machine_id":"$ID2","machine_code":"EX-01","machine_name":"Excavator","reading":"1234.50",
        "source":"PROPOSAL","source_capture_id":null,"photo_attachment_id":"$ID2","captured_at":"2026-10-25T07:00:00Z","latitude":null,
        "longitude":null,"accuracy_m":null,"note":"New machine","status":"PROPOSED","proposed_by":"u-2","proposed_by_name":"Asha",
        "proposed_at":"2026-10-25T08:00:00Z","decided_by":null,"decided_at":null,"decision_note":null}"""

    @Test
    fun `decisions load, map and decide with the right body`() = runBlocking {
        h.ok(Samples.page(discount))
        val loaded = h.data.decisions(DecisionKind.DISCOUNT) as Load.Ok
        val item = loaded.snapshot.data.single()
        assertEquals("10% discount", item.headline)
        assertTrue(item.pending)
        assertTrue(item.isOwn("u-1"))
        assertFalse(item.isOwn("u-9"))
        assertTrue(h.server.takeRequest().url.toString().contains("customer-discounts?status=PROPOSED"))
        h.ok(discount.replace("PROPOSED", "APPROVED"))
        assertTrue(h.data.decide(DecisionKind.DISCOUNT, ID1, approve = true, note = " ") is ActionResult.Done)
        val decided = h.server.takeRequest()
        assertTrue(decided.url.toString().endsWith("/customer-discounts/$ID1/decision"))
        assertEquals("""{"approve":true}""", decided.body!!.utf8())
    }

    @Test
    fun `meter decisions send APPROVE or REJECT with the note`() = runBlocking {
        h.ok(Samples.page(baseline))
        val item = (h.data.decisions(DecisionKind.BASELINE) as Load.Ok).snapshot.data.single()
        assertEquals("Baseline 1234.5 h · EX-01", item.headline)
        assertEquals(ID2, item.photoAttachmentId)
        h.server.takeRequest()
        h.ok(baseline.replace("\"PROPOSED\"", "\"REJECTED\""))
        h.data.decide(DecisionKind.BASELINE, ID1, approve = false, note = "Photo unreadable")
        assertEquals("""{"decision":"REJECT","note":"Photo unreadable"}""", h.server.takeRequest().body!!.utf8())
        assertFalse(DecisionMapper.canDecide(DecisionKind.BASELINE, true, "ok"))
        assertTrue(DecisionMapper.canDecide(DecisionKind.BASELINE, true, "Looks right"))
        assertTrue(DecisionMapper.canDecide(DecisionKind.RETENTION, true, ""))
        assertFalse(DecisionMapper.canDecide(DecisionKind.RETENTION, false, " "))
    }

    @Test
    fun `remittance confirm sends the amount counted`() = runBlocking {
        h.ok("""{"id":"$ID1","staff_member_id":"$ID2","amount":"50000","currency":"TZS","handed_at":"2026-10-25T08:00:00Z","status":"VERIFIED",
            "source":"SYNC","recorded_at":"2026-10-25T08:00:00Z","amount_received":"45000","expected_balance":"60000","partial_shortfall":"10000"}""")
        val r = h.data.decideHandover(ID1, verified = true, note = null, amountReceived = HandoverText.receivedAmount("45000,00"))
        assertEquals("45000", ((r as ActionResult.Done).value.amountReceived!!.value.stripTrailingZeros().toPlainString()))
        assertEquals("""{"verified":true,"amount_received":"45000.00"}""", h.server.takeRequest().body!!.utf8())
        assertTrue(HandoverText.canDecide(true, "", "0"))
        assertFalse(HandoverText.canDecide(true, "", "abc"))
        assertFalse(HandoverText.canDecide(false, " ", null))
    }

    @Test
    fun `sections and decisions follow permissions`() {
        val none = OwnerFeatures(setOf("tenant.approval.read"))
        assertTrue(DecisionKind.visible(none).isEmpty())
        val hours = OwnerFeatures(setOf("tenant.hours.read", "tenant.meter.read"))
        assertEquals(
            listOf(DecisionKind.DISCOUNT, DecisionKind.CREDIT, DecisionKind.HOURS_TRANSFER, DecisionKind.CANCELLATION, DecisionKind.BASELINE,
                DecisionKind.CLASSIFICATION, DecisionKind.CORRECTION),
            DecisionKind.visible(hours),
        )
        val session = OwnerSession(TENANT, "Acme", setOf("tenant.hours.read"), readOnly = false, userId = "u-1")
        val blocked = session.can(DecisionKind.DISCOUNT.action, online = true, DataSource.LIVE)
        assertTrue(blocked is MutationCheck.Blocked)
        val approver = session.copy(permissions = setOf("tenant.hours.read", "tenant.hours.discount_approve"))
        assertEquals(MutationCheck.Allowed, approver.can(OwnerAction.DECIDE_DISCOUNT, online = true, DataSource.LIVE))
        assertTrue(moreEntries(OwnerFeatures(setOf("tenant.accountability.read"))).any { it.second == OwnerDestination.Accountability })
        assertFalse(moreEntries(OwnerFeatures(emptySet())).any { it.second == OwnerDestination.Accountability })
        assertEquals("Meter baseline", OwnerNavigation.title(OwnerDestination.Decision(DecisionKinds.BASELINE, ID1)))
        assertEquals("Accountability", OwnerNavigation.title(OwnerDestination.Accountability))
    }

    @Test
    fun `dashboard tiles skip hidden ones and link where the role may go`() {
        val s = NetworkFactory.json.decodeFromString(
            AccountabilitySummaryDto.serializer(),
            """{"as_of":"2026-10-25T08:00:00Z","policy_version":"v3","hidden_tiles":["payments"],"unavailable_tiles":[],
            "outstanding_approvals":{"approval_requests":1,"payments_to_verify":2,"remittances_to_verify":3,"cash_retentions":0,
            "custody_adjustments":0,"write_offs":1,"total":7},
            "cash":{"custodians":[{"staff_member_id":"s1","staff_name":"Juma","currency":"TZS","outstanding":"50000","in_transit_out":"10000",
            "pending_floats":"0","claimed_unverified_handovers":"0"}],"transfers_awaiting_acknowledgement":[{"count":1,"amount":"10000","currency":"TZS"}],
            "floats_awaiting_acknowledgement":[],"remittances_awaiting_confirmation":[],"partial_remittances_in_window":2},
            "unauthorized_attempts":{"permission_denied":4,"segregation_of_duties":1,"window_days":30},
            "customer_hours":{"customers":2,"activated":"20.00","consumed":"7.5","remaining":"12.5","awaiting_activation":"0","expired":"0","open_overruns":1},
            "unexplained_hours":{"machines":1,"hours":"3.5","items":[{"machine_id":"m1","machine_code":"EX-01","unexplained_hours":"3.5","oldest_open_item_days":4}]},
            "missing_daily_reports":{"count":0,"items":[]}}""",
        )
        val tiles = DashboardPresentation.tiles(s, OwnerFeatures(setOf("tenant.finance.read", "tenant.approval.read")))
        assertEquals(listOf("approvals", "cash", "attempts", "customer_hours", "unexplained_hours", "missing_daily_reports"), tiles.map { it.key })
        val cash = tiles.first { it.key == "cash" }
        assertEquals(OwnerDestination.Cash, cash.link)
        assertTrue(cash.rows.any { it.first == "Juma" && it.second.contains("outstanding") && it.second.contains("in transit") })
        assertEquals("Last 30 days", tiles.first { it.key == "attempts" }.footer)
        assertEquals("12.5", tiles.first { it.key == "customer_hours" }.rows.first { it.first == "Remaining" }.second)
        assertEquals("3.5 h · oldest 4 days", tiles.first { it.key == "unexplained_hours" }.rows.last().second)
        assertNull(tiles.first { it.key == "unexplained_hours" }.link) // no meter read permission
    }

    @Test
    fun `new notification types open the right screen`() {
        assertEquals(OwnerDestination.Decision(DecisionKinds.DISCOUNT, ID1), DeepLinkRouter.fromTarget("customer_discount", ID1, "/tenant/hours/discounts"))
        assertEquals(OwnerDestination.Decision(DecisionKinds.BASELINE, ID1), DeepLinkRouter.fromTarget("baseline", ID1, "/tenant/meter-baselines"))
        assertEquals(OwnerDestination.Decision(DecisionKinds.RETENTION, ID1), DeepLinkRouter.fromTarget("cash_retention", ID1, "/tenant/cash"))
        assertEquals(OwnerDestination.Decision(DecisionKinds.WRITE_OFF, ID1), DeepLinkRouter.fromTarget("cash_variance", ID1, "/tenant/cash"))
        assertEquals(OwnerDestination.Approvals(), DeepLinkRouter.fromTarget("cash_variance", ID1, "/tenant/cash/variances", type = "CASH_VARIANCE_OPENED"))
        assertEquals(OwnerDestination.MeterException(ID1), DeepLinkRouter.fromTarget("job_exception", ID1, "/tenant/exceptions"))
        assertEquals(OwnerDestination.Handover(ID1), DeepLinkRouter.fromTarget("cash_handover", ID1, "/tenant/cash/handovers"))
        assertEquals(OwnerDestination.CashRecord(RecordKinds.CASH_TRANSFER, ID1), DeepLinkRouter.fromTarget("cash_transfer", ID1, "/tenant/cash/transfers"))
        assertEquals(OwnerDestination.HoursPurchase(ID1), DeepLinkRouter.fromTarget("hours_purchase", ID1, "/tenant/hours/purchases/$ID1"))
        assertEquals(OwnerDestination.Machine(ID1), DeepLinkRouter.fromTarget("machine", ID1, "/tenant/engine-hours/machines/$ID1"))
        // Push taps carry only the link.
        assertEquals(OwnerDestination.Machine(ID1), DeepLinkRouter.fromPath("/tenant/engine-hours/machines/$ID1"))
        assertEquals(OwnerDestination.Approvals(), DeepLinkRouter.fromPath("/tenant/meter-corrections"))
        assertEquals(OwnerDestination.Approvals(), DeepLinkRouter.fromPath("/tenant/hours/transfers"))
        assertEquals(OwnerDestination.HoursPurchase(ID1), DeepLinkRouter.fromPath("/tenant/hours/purchases/$ID1"))
        assertEquals(OwnerDestination.Cash, DeepLinkRouter.fromPath("/tenant/cash/floats"))
        assertEquals(OwnerDestination.Approvals(), DeepLinkRouter.fromPath("/tenant/cash/variances"))
    }
}
