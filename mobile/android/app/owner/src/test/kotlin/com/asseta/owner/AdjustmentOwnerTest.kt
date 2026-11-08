package com.asseta.owner

import com.asseta.core.domain.owner.DataSource
import com.asseta.core.domain.owner.DecisionKinds
import com.asseta.core.domain.owner.DeepLinkRouter
import com.asseta.core.domain.owner.MutationCheck
import com.asseta.core.domain.owner.OwnerAction
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.domain.owner.OwnerFormat
import com.asseta.core.model.owner.AdjustmentRequestDto
import com.asseta.core.model.owner.HoursStatementDto
import com.asseta.core.model.sync.PurchaseTotalsDto
import com.asseta.core.network.NetworkFactory
import com.asseta.owner.ui.OwnerFeatures
import com.asseta.owner.ui.OwnerSession
import com.asseta.owner.ui.moreEntries
import com.asseta.owner.ui.approvals.ApprovalsViewModel
import com.asseta.owner.ui.accountability.AdjustmentPresentation
import com.asseta.owner.ui.accountability.AdjustmentTexts
import com.asseta.owner.ui.accountability.DecisionKind
import com.asseta.owner.ui.accountability.DecisionViewModel
import com.asseta.owner.ui.accountability.HoursPresentation
import com.asseta.owner.ui.accountability.HoursPurchaseViewModel
import com.asseta.owner.ui.common.ScreenState
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.emptyFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import kotlinx.coroutines.withTimeout
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.math.BigDecimal
import java.time.ZoneOffset

/** DEC-032 Phase 2 in the Owner app: adjustment requests, reversed payments, new hours figures. */
@OptIn(ExperimentalCoroutinesApi::class)
class AdjustmentOwnerTest {
    private val h = OwnerHarness()
    private val json = NetworkFactory.json
    private val me = "99999999-9999-4999-8999-999999999999"

    @Before
    fun setUp() = Dispatchers.setMain(Dispatchers.Unconfined)

    @After
    fun tearDown() {
        Dispatchers.resetMain()
        h.close()
    }

    private fun <T> StateFlow<ScreenState<T>>.settled(): ScreenState<T> = runBlocking { withTimeout(5_000) { first { !it.loading } } }

    private fun <T> StateFlow<T>.await(predicate: (T) -> Boolean): T = runBlocking { withTimeout(5_000) { first(predicate) } }

    private fun body(type: String = "HOURS_CORRECTION", status: String = "PROPOSED", effects: String = "{}", extra: String = "") =
        """{"id":"$ID1","request_type":"$type","status":"$status","original_type":"hours_purchase","original_id":"$ID2","original_reference":"HP-7",
           "customer_id":"c1","customer_name":"Mgodi Ltd","machine_id":"m1","machine_code":"EX-01","reason":"Meter misread","params":{},
           "evidence_attachment_ids":["p1","p2"],"proposed_by":"$me","proposed_by_name":"Asha","proposed_at":"2026-10-26T08:00:00Z","effects":$effects$extra}"""

    private fun dto(type: String = "HOURS_CORRECTION", status: String = "PROPOSED", effects: String = "{}", extra: String = "") =
        json.decodeFromString(AdjustmentRequestDto.serializer(), body(type, status, effects, extra))

    private fun tzs(raw: String) = OwnerFormat.money(BigDecimal(raw), "TZS")

    @Test
    fun `row names the type, quantity and who it is about`() {
        val correction = AdjustmentPresentation.item(dto(extra = ""","hours":"2.00""""))
        assertEquals("Hours correction · +2 h", correction.headline)
        assertEquals("Mgodi Ltd · EX-01", correction.subline)
        assertEquals("Meter misread", correction.reason)
        assertEquals("Asha", correction.proposedByName)
        assertEquals(listOf("p1", "p2"), correction.photoAttachmentIds)
        assertTrue(correction.pending)
        assertEquals("Hours correction · -1.5 h", AdjustmentPresentation.headline(dto(extra = ""","hours":"-1.50"""")))
        assertEquals("Hours refund · 3 h", AdjustmentPresentation.headline(dto("HOURS_REFUND", extra = ""","hours":"3.00"""")))
        assertEquals("Payment reversal · ${tzs("150000")}", AdjustmentPresentation.headline(dto("PAYMENT_REVERSAL", extra = ""","amount":"150000.0000","currency":"TZS"""")))
        assertEquals("Invoice void", AdjustmentPresentation.headline(dto("INVOICE_VOID", extra = ""","amount":"5.00","currency":"TZS"""")))
    }

    @Test
    fun `forecast and actual effects read differently`() {
        val forecast = AdjustmentPresentation.item(dto(effects = """{"lot_hours_before":"10.00","lot_hours_after":"12.00"}"""))
        assertEquals(AdjustmentTexts.EFFECTS_FORECAST, forecast.effectsTitle)
        assertEquals(mapOf(AdjustmentTexts.LOT_BEFORE_FORECAST to "10 h", AdjustmentTexts.LOT_AFTER to "12 h"), forecast.effects.associate { it.label to it.value })
        val actual = AdjustmentPresentation.item(dto(status = "APPROVED", effects = """{"lot_hours_before":"0","lot_hours_after":"2","purchase_remaining":"7"}"""))
        assertEquals(AdjustmentTexts.EFFECTS_ACTUAL, actual.effectsTitle)
        assertFalse(actual.pending)
        // The lot rows stay even at zero.
        assertEquals(listOf(AdjustmentTexts.LOT_BEFORE_ACTUAL to "0 h", AdjustmentTexts.LOT_AFTER to "2 h", AdjustmentTexts.PURCHASE_REMAINING to "7 h"), actual.effects.map { it.label to it.value })
    }

    @Test
    fun `reversal forecast shows money, treatment and each purchase, ignoring unknown keys`() {
        val rows = AdjustmentPresentation.effectRows(
            dto(
                "PAYMENT_REVERSAL", extra = ""","amount":"100","currency":"TZS"""",
                effects = """{"unused_hours_removed":"4","used_hours":"1.5","money_owed":"30000","hire_allocations_released":"0","treatment":"CASE","custody_balance_after":"500",
                    "custody_staff_id":"s1","something_new":"9","purchases":[{"purchase_number":"HP-7","unused_hours":"4","used_hours":"1.5","money_owed":"30000"}]}""",
            ),
        ).map { it.label to it.value }
        assertEquals(
            listOf(
                AdjustmentTexts.UNUSED_REMOVED to "4 h", AdjustmentTexts.USED_HOURS to "1.5 h", AdjustmentTexts.MONEY_OWED to tzs("30000"),
                AdjustmentTexts.TREATMENT to "Open an investigation case", AdjustmentTexts.CUSTODY_AFTER to tzs("500"),
                "HP-7" to AdjustmentTexts.purchaseLine("4", "1.5", tzs("30000")),
            ),
            rows,
        )
    }

    @Test
    fun `treatment is left out when no used hours are touched`() {
        val rows = AdjustmentPresentation.effectRows(dto("PAYMENT_REVERSAL", effects = """{"unused_hours_removed":"4","used_hours":"0","money_owed":"0","treatment":"RECEIVABLE"}"""))
        assertEquals(listOf(AdjustmentTexts.UNUSED_REMOVED), rows.map { it.label })
    }

    @Test
    fun `a refused forecast warns in plain words`() {
        val item = AdjustmentPresentation.item(dto(effects = """{"refused":"PURCHASE_CANCELLED"}"""))
        assertEquals(AdjustmentTexts.refused("This purchase is cancelled."), item.effectsWarning)
        assertTrue(item.effects.isEmpty())
        assertEquals(AdjustmentTexts.refused(AdjustmentTexts.REFUSED_UNKNOWN), AdjustmentPresentation.refusal(dto(effects = """{"refused":"BRAND_NEW"}""")))
        assertNull(AdjustmentPresentation.refusal(dto(status = "APPROVED", effects = """{"refused":"PURCHASE_CANCELLED"}""")))
    }

    @Test
    fun `a withdrawn request labels its reason`() {
        val fields = AdjustmentPresentation.item(dto(status = "WITHDRAWN", extra = ""","decision_note":"Entered by mistake"""")).fields.associate { it.label to it.value }
        assertEquals("Entered by mistake", fields[AdjustmentTexts.WITHDRAWN_REASON])
        assertEquals("HP-7", fields[AdjustmentTexts.REFERENCE])
    }

    @Test
    fun `own request blocks deciding and offers withdraw only while it waits`() {
        val item = AdjustmentPresentation.item(dto())
        assertTrue(item.isOwn(me))
        assertTrue(AdjustmentPresentation.canWithdraw(item, me))
        assertFalse(AdjustmentPresentation.canWithdraw(item, "someone-else"))
        assertFalse(AdjustmentPresentation.canWithdraw(AdjustmentPresentation.item(dto(status = "APPROVED")), me))
        assertFalse(AdjustmentPresentation.withdrawReasonValid(" ab "))
        assertTrue(AdjustmentPresentation.withdrawReasonValid("abc"))
    }

    @Test
    fun `section and actions follow the adjustment permissions`() {
        assertTrue(DecisionKind.ADJUSTMENT_REQUEST in DecisionKind.visible(OwnerFeatures(setOf("tenant.adjustment.read"))))
        assertFalse(DecisionKind.ADJUSTMENT_REQUEST in DecisionKind.visible(OwnerFeatures(setOf("tenant.finance.read"))))
        val session = OwnerSession(TENANT, "Acme", setOf("tenant.adjustment.read"), readOnly = false, userId = me)
        assertTrue(session.can(OwnerAction.DECIDE_ADJUSTMENT_REQUEST, true, DataSource.LIVE) is MutationCheck.Blocked)
        assertTrue(session.can(OwnerAction.WITHDRAW_ADJUSTMENT_REQUEST, true, DataSource.LIVE) is MutationCheck.Blocked)
        val decider = session.copy(permissions = setOf("tenant.adjustment.read", "tenant.adjustment.decide", "tenant.adjustment.propose"))
        assertEquals(MutationCheck.Allowed, decider.can(OwnerAction.DECIDE_ADJUSTMENT_REQUEST, true, DataSource.LIVE))
        assertEquals(MutationCheck.Allowed, decider.can(OwnerAction.WITHDRAW_ADJUSTMENT_REQUEST, true, DataSource.LIVE))
    }

    @Test
    fun `an adjustment holder without expense approvals still gets Approvals`() {
        val holder = OwnerFeatures(setOf("tenant.finance.read", "tenant.adjustment.read", "tenant.adjustment.decide"))
        assertTrue(moreEntries(holder).any { it.second == OwnerDestination.Approvals() })
        // A role with a decision to see gets Approvals (finance.read sees write-offs); one with nothing does not.
        assertTrue(moreEntries(OwnerFeatures(setOf("tenant.finance.read", "tenant.finance.writeoff"))).any { it.second == OwnerDestination.Approvals() })
        assertFalse(moreEntries(OwnerFeatures(setOf("tenant.expense.read"))).any { it.second == OwnerDestination.Approvals() })
        h.route("/adjustment-requests" to Samples.page(body()))
        val vm = ApprovalsViewModel(h.data, emptyFlow(), decisions = DecisionKind.visible(OwnerFeatures(setOf("tenant.adjustment.read"))), expenseRequests = holder.approvals)
        assertEquals(0, vm.state.settled().data!!.items.size)
        assertNull(vm.state.value.error)
        val section = vm.decisionSections.single().second.state.settled().data!!
        assertEquals("Hours correction", section.single().headline)
        assertEquals(1, h.server.requestCount)
        assertEquals("/api/v1/tenant/adjustment-requests", h.server.takeRequest().url.encodedPath)
    }

    @Test
    fun `deep links open the request or Approvals`() {
        val target = OwnerDestination.Decision(DecisionKinds.ADJUSTMENT_REQUEST, ID1)
        assertEquals(target, DeepLinkRouter.fromTarget(null, null, null, kind = "ADJUSTMENT_REQUEST", recordId = ID1))
        assertEquals(target, DeepLinkRouter.fromTarget("adjustment_request", ID1, null))
        assertEquals(target, DeepLinkRouter.fromPath("/tenant/finance/adjustments/requests/$ID1"))
        assertEquals(OwnerDestination.Approvals(), DeepLinkRouter.fromPath("/tenant/finance/adjustments"))
        assertEquals(OwnerDestination.Approvals(), DeepLinkRouter.fromPath("/tenant/finance/adjustments/$ID1"))
        assertEquals(null, DeepLinkRouter.fromPath("/tenant/finance/invoices"))
    }

    @Test
    fun `approving reloads so the screen shows what happened`() {
        h.ok(body(effects = """{"lot_hours_before":"10","lot_hours_after":"12"}"""))
        val vm = DecisionViewModel(h.data, DecisionKind.ADJUSTMENT_REQUEST, ID1, emptyFlow())
        vm.state.settled()
        h.ok(body(status = "APPROVED"))
        h.ok(body(status = "APPROVED", effects = """{"lot_hours_before":"10","lot_hours_after":"12","purchase_remaining":"12"}"""))
        vm.decide(true, "")
        val item = vm.state.await { s -> s.data?.first()?.effects?.size == 3 }.data!!.first()
        assertEquals(AdjustmentTexts.EFFECTS_ACTUAL, item.effectsTitle)
        h.server.takeRequest()
        val post = h.server.takeRequest()
        assertEquals("/api/v1/tenant/adjustment-requests/$ID1/decision", post.url.encodedPath)
        assertTrue(post.body!!.utf8().contains("\"decision\":\"APPROVE\""))
    }

    @Test
    fun `a refused decision uses plain words`() {
        h.ok(body())
        val vm = DecisionViewModel(h.data, DecisionKind.ADJUSTMENT_REQUEST, ID1, emptyFlow())
        vm.state.settled()
        h.error(422, "SEGREGATION_OF_DUTIES")
        vm.decide(true, "")
        val e = vm.error.await { it != null }!!
        assertTrue(e.segregationOfDuties)
        assertEquals("You proposed this request, so someone else must decide it.", e.error.message)
    }

    @Test
    fun `rejecting needs a note`() {
        h.ok(body())
        val vm = DecisionViewModel(h.data, DecisionKind.ADJUSTMENT_REQUEST, ID1, emptyFlow())
        vm.state.settled()
        vm.decide(false, " ")
        assertEquals(1, h.server.requestCount)
    }

    @Test
    fun `withdrawing posts the reason and closes the request`() {
        h.ok(body())
        val vm = DecisionViewModel(h.data, DecisionKind.ADJUSTMENT_REQUEST, ID1, emptyFlow())
        vm.state.settled()
        vm.withdraw("ab")
        assertEquals(1, h.server.requestCount)
        val closed = body(status = "WITHDRAWN", extra = ""","decision_note":"Entered by mistake"""")
        h.ok(closed)
        h.ok(closed)
        vm.withdraw(" Entered by mistake ")
        assertEquals(AdjustmentTexts.WITHDRAWN, vm.message.await { it != null })
        assertEquals("WITHDRAWN", vm.state.await { it.data?.first()?.status == "WITHDRAWN" }.data!!.first().status)
        h.server.takeRequest()
        val post = h.server.takeRequest()
        assertEquals("/api/v1/tenant/adjustment-requests/$ID1/withdraw", post.url.encodedPath)
        assertEquals("""{"reason":"Entered by mistake"}""", post.body!!.utf8())
    }

    @Test
    fun `a refused withdrawal stays on the request`() {
        h.ok(body())
        val vm = DecisionViewModel(h.data, DecisionKind.ADJUSTMENT_REQUEST, ID1, emptyFlow())
        vm.state.settled()
        h.error(403, "NOT_PROPOSER")
        h.ok(body())
        vm.withdraw("Entered by mistake")
        assertEquals("Only the person who proposed this request can withdraw it.", vm.withdrawError.await { it != null })
        assertNull(vm.message.value)
    }

    private val purchase = """{"id":"$ID1","purchase_number":"HP-7","customer_id":"c1","machine_id":"m1","hours":"20","status":"ACTIVE","created_at":"2026-10-01T08:00:00Z",
        "currency":"TZS","totals":{"purchased":"20","activated":"20","consumed":"5","remaining":"10","awaiting_activation":"0","refunded":"3","corrected":"-2","reversed":"4"},
        "allocations":[{"id":"a1","payment_id":"$ID2","amount":"100000","released_at":"2026-10-26T22:30:00Z","payment_status":"VERIFIED"},
        {"id":"a2","payment_id":"p-kept","amount":"50000","released_at":null,"payment_status":"VERIFIED"},
        {"id":"a3","payment_id":"p-released","amount":"25000","released_at":"2026-10-26T10:00:00Z","payment_status":"VERIFIED"}]}"""

    @Test
    fun `a reversed payment is marked on the purchase`() {
        h.route(
            "/hours-purchases/$ID1" to purchase,
            "/customer-payments/$ID2" to """{"id":"$ID2","reversed_at":"2026-10-26T22:30:00Z","reversal_id":"r1"}""",
            "/customer-payments/p-released" to """{"id":"p-released","reversed_at":null}""",
        )
        val vm = HoursPurchaseViewModel(h.data, ID1, emptyFlow(), payments = true)
        val d = vm.state.settled().data!!
        val lines = HoursPresentation.payments(d, ZoneOffset.ofHours(3))
        assertEquals(tzs("100000"), lines[0].amount)
        assertEquals("Reversed 27 Oct 2026", lines[0].status)
        assertTrue(lines[0].reversed)
        assertEquals("Verified", lines[1].status)
        assertFalse(lines[1].reversed)
        assertEquals("No longer counted", lines[2].status)
        assertFalse(lines[2].reversed)
        assertTrue(lines[2].released)
    }

    @Test
    fun `without permission the payments are not read and nothing is claimed reversed`() {
        h.route("/hours-purchases/$ID1" to purchase)
        val d = HoursPurchaseViewModel(h.data, ID1, emptyFlow()).state.settled().data!!
        assertEquals(1, h.server.requestCount)
        assertEquals(listOf("No longer counted", "Verified", "No longer counted"), HoursPresentation.payments(d, ZoneOffset.UTC).map { it.status })
    }

    @Test
    fun `purchase shows refunded, corrected and reversed only when set`() {
        h.route("/hours-purchases/$ID1" to purchase)
        val p = HoursPurchaseViewModel(h.data, ID1, emptyFlow()).state.settled().data!!.purchase
        val rows = HoursPresentation.purchaseRows(p).toMap()
        assertEquals("3 h", rows["Refunded"])
        assertEquals("-2 h", rows["Corrected"])
        assertEquals("4 h", rows["Reversed"])
        val older = p.copy(totals = json.decodeFromString(PurchaseTotalsDto.serializer(), """{"purchased":"1","activated":"1","consumed":"0","remaining":"1","awaiting_activation":"0"}"""))
        val plain = HoursPresentation.purchaseRows(older).toMap()
        assertFalse(listOf("Refunded", "Corrected", "Reversed").any { it in plain })
    }

    @Test
    fun `statement lists the new ledger kinds newest first`() {
        val s = json.decodeFromString(
            HoursStatementDto.serializer(),
            """{"customer_id":"c1","date_from":"2026-10-01","date_to":"2026-10-31","timezone":"Africa/Dar_es_Salaam","generated_at":"2026-10-31T08:00:00Z","pdf_path":"/x",
               "totals":{"opening_balance":"0","bought":"0","activated":"0","used":"0","transferred_in":"0","transferred_out":"0","expired":"0","cancelled":"0","closing_balance":"0",
               "provisional_at_close":"0","awaiting_activation":"0","refunded":"3","corrected":"2"},
               "lines":[{"entry_id":"1","day":"2026-10-02","occurred_at":"2026-10-02T08:00:00Z","entry_type":"CONSUMED","purchase_id":"p","machine_id":"m","hours":"-1","balance_after":"1"},
               {"entry_id":"2","day":"2026-10-03","occurred_at":"2026-10-03T08:00:00Z","entry_type":"CORRECTION_ADD","purchase_id":"p","purchase_number":"HP-7","machine_id":"m","hours":"2","balance_after":"3","reason":"Meter misread"},
               {"entry_id":"3","day":"2026-10-04","occurred_at":"2026-10-04T08:00:00Z","entry_type":"REFUNDED","purchase_id":"p","machine_id":"m","hours":"-3","balance_after":"0","reason":null}]}""",
        )
        val totals = HoursPresentation.totals(s).toMap()
        assertEquals("3 h", totals["Refunded"])
        assertEquals("+2 h", totals["Corrected"])
        val lines = HoursPresentation.adjustmentLines(s)
        assertEquals(listOf("4 Oct 2026 · Hours refunded", "3 Oct 2026 · Hours added by correction"), lines.map { it.label })
        assertEquals(listOf("-3 h", "+2 h"), lines.map { it.value })
        assertEquals(listOf("", "HP-7 · Meter misread"), lines.map { it.caption })
    }
}
