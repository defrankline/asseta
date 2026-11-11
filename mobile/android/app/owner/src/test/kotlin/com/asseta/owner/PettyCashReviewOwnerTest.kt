package com.asseta.owner

import com.asseta.core.domain.finance.ExpenseFlags
import com.asseta.core.domain.owner.DataSource
import com.asseta.core.domain.owner.DeepLinkRouter
import com.asseta.core.domain.owner.MutationCheck
import com.asseta.core.domain.owner.MutationGate
import com.asseta.core.domain.owner.OwnerAction
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.model.TenantAccess
import com.asseta.core.model.owner.ExpenseDto
import com.asseta.core.network.NetworkFactory
import com.asseta.owner.data.ActionResult
import com.asseta.owner.data.Load
import com.asseta.owner.ui.OwnerFeatures
import com.asseta.owner.ui.approvals.PettyCashRequest
import com.asseta.owner.ui.approvals.PettyCashReviewText
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.ZoneOffset

/** DEC-033 in the Owner app: petty cash fundings, top-ups and fund adjustments approved by permission, never one's own. */
class PettyCashReviewOwnerTest {
    private val h = OwnerHarness()
    private val t = PettyCashReviewText
    private val approver = setOf("tenant.pettycash.read", "tenant.pettycash.approve")

    @After fun tearDown() = h.close()

    private fun movement(status: String = "PROPOSED", kind: String = "TOP_UP", createdBy: String = ID2) =
        """{"id":"$ID1","number":"PC-0007","fund_id":"$ID2","petty_cash_fund_name":"Site box","kind":"$kind","status":"$status","client_id":null,
        "holder_staff_id":"$ID2","holder_staff_name":"Juma","amount":"45000.0000","currency":"TZS","deposit_account_id":null,"method":null,
        "reference":null,"note":"Fuel week","suggested_amount":"40000.0000","cap_amount":"40000.0000","above_cap_reason":"Two sites this week",
        "basis_from":null,"evidence_attachment_ids":[],"source":"SYNC","created_by":"$createdBy","created_by_name":"Juma","created_at":"2026-11-10T08:00:00Z",
        "client_created_at":null,"decided_by":null,"decided_at":null,"decision_note":null,"issued_by":null,"issued_at":null,"received_by":null,
        "received_at":null,"amount_received":null,"receipt_method":null,"receipt_note":null}"""

    private fun adjustment(status: String = "PENDING") =
        """{"id":"$ID2","number":"PC-0008","fund_id":"$ID1","petty_cash_fund_name":"Office box","amount":"-2500.0000","currency":"TZS","reason_id":null,
        "reason":"Torn note","evidence_attachment_ids":[],"status":"$status","created_by":"$ID1","created_by_name":"Asha","created_at":"2026-11-10T09:00:00Z",
        "decided_by":null,"decided_at":null,"decision_note":null}"""

    @Test
    fun `the queue asks for proposed movements and pending adjustments`() = runBlocking {
        h.ok("""{"items":[${movement()}],"total":1,"page":1,"page_size":100}""")
        h.ok("""{"items":[${adjustment()}],"total":1,"page":1,"page_size":100}""")
        val q = (h.data.pettyCashToApprove() as Load.Ok).snapshot.data
        val first = h.server.takeRequest().url.toString()
        val second = h.server.takeRequest().url.toString()
        assertTrue(first, first.contains("/petty-cash/movements?") && first.contains("status=PROPOSED"))
        assertTrue(second, second.contains("/petty-cash/adjustments?") && second.contains("status=PENDING"))
        assertEquals("Top-up TZS 45,000.00 · Site box", t.headline(PettyCashRequest.of(com.asseta.core.model.owner.PettyCashMovementReview(q.movements.single()))))
        assertEquals("Fund adjustment -TZS 2,500.00 · Office box", t.headline(PettyCashRequest.of(q.adjustments.single())))
    }

    @Test
    fun `a top-up opens with the spending behind it`() = runBlocking {
        h.ok(movement())
        h.ok("""[{"id":"$ID2","description":"Diesel","amount":"40000.0000","incurred_at":"2026-11-09T08:00:00Z","decided_at":null,"category_id":"$ID1","machine_id":null,"job_id":null}]""")
        val review = (h.data.pettyCashMovementReview(ID1) as Load.Ok).snapshot.data
        assertTrue(h.server.takeRequest().url.toString().endsWith("/petty-cash/movements/$ID1"))
        assertTrue(h.server.takeRequest().url.toString().endsWith("/petty-cash/movements/$ID1/expenses"))
        val r = PettyCashRequest.of(review)
        assertEquals(listOf("Diesel · TZS 40,000.00"), r.expenses)
        val fields = t.fields(r, ZoneOffset.UTC).toMap()
        assertEquals("Site box", fields["Fund"])
        assertEquals("Juma", fields["Holder"])
        assertEquals("Top-up", fields["Kind"])
        assertEquals("TZS 40,000.00", fields["Brings the fund to its limit"])
        assertEquals("Two sites this week", fields["Reason for going above the limit"])
    }

    @Test
    fun `expenses that cannot be read are not the same as none`() = runBlocking {
        h.ok(movement())
        h.error(500, "INTERNAL", "boom")
        val review = (h.data.pettyCashMovementReview(ID1) as Load.Ok).snapshot.data
        assertTrue(review.expensesFailed)
    }

    @Test
    fun `decisions are sent with a trimmed note and refusals keep the server's words`() = runBlocking {
        h.ok(movement(status = "APPROVED"))
        assertTrue(h.data.decidePettyCashMovement(ID1, true, "  ") is ActionResult.Done)
        val req = h.server.takeRequest()
        assertTrue(req.url.toString().endsWith("/petty-cash/movements/$ID1/decision"))
        assertEquals("""{"approve":true}""", req.body!!.utf8())

        h.ok(adjustment(status = "REJECTED"))
        h.data.decidePettyCashAdjustment(ID2, false, " No evidence ")
        val adj = h.server.takeRequest()
        assertTrue(adj.url.toString().endsWith("/petty-cash/adjustments/$ID2/decision"))
        assertEquals("""{"approve":false,"note":"No evidence"}""", adj.body!!.utf8())

        h.error(422, "SEGREGATION_OF_DUTIES", "The holder cannot approve their own fund")
        val own = h.data.decidePettyCashMovement(ID1, true, null) as ActionResult.Refused
        assertEquals("The holder cannot approve their own fund", t.refusal(own.code, own.serverMessage ?: own.error.message))

        h.error(409, "PETTY_CASH_ALREADY_DECIDED", "Already APPROVED")
        val decided = h.data.decidePettyCashMovement(ID1, true, null) as ActionResult.Refused
        assertTrue(decided.reload)
        assertEquals("Someone already decided this. Reload to see it.", t.refusal(decided.code, decided.error.message))
    }

    @Test
    fun `the proposer never sees the buttons and a reason is needed to reject`() {
        val r = PettyCashRequest.of(com.asseta.core.model.owner.PettyCashMovementReview(
            NetworkFactory.json.decodeFromString(com.asseta.core.model.owner.PettyCashMovementReviewDto.serializer(), movement(createdBy = ID2))))
        assertTrue(t.isOwn(r, ID2))
        assertTrue(t.isOwn(r, ID2.uppercase()))
        assertFalse(t.isOwn(r, ID1))
        assertFalse(t.isOwn(r, null))
        assertTrue(t.decidable(r))
        assertFalse(t.decidable(r.copy(status = "APPROVED")))
        assertTrue(t.canDecide(true, ""))
        assertFalse(t.canDecide(false, "no"))
        assertTrue(t.canDecide(false, "Not needed"))
    }

    @Test
    fun `approving is by permission, online, and the section follows the switch`() {
        assertEquals("tenant.pettycash.approve", OwnerAction.DECIDE_PETTY_CASH.permission)
        assertEquals(MutationCheck.Allowed, MutationGate.check(OwnerAction.DECIDE_PETTY_CASH, true, DataSource.LIVE, approver, false))
        assertEquals(MutationCheck.Blocked(MutationGate.OFFLINE), MutationGate.check(OwnerAction.DECIDE_PETTY_CASH, false, DataSource.LIVE, approver, false))
        assertTrue(OwnerFeatures(approver).pettyCashApprove)
        assertTrue(OwnerFeatures(approver).approvalsScreen)
        assertFalse(OwnerFeatures(setOf("tenant.pettycash.read")).pettyCashApprove)
        assertFalse(OwnerFeatures(approver, setOf(TenantAccess.PETTY_CASH)).pettyCashApprove)
    }

    @Test
    fun `petty cash links open the record or Approvals`() {
        assertEquals(OwnerDestination.PettyCashMovement(ID1), DeepLinkRouter.fromTarget("petty_cash_movement", ID1, "/tenant/finance/petty-cash/movements/$ID1"))
        assertEquals(OwnerDestination.PettyCashAdjustment(ID1), DeepLinkRouter.fromTarget("petty_cash_adjustment", ID1, null))
        assertEquals(OwnerDestination.PettyCashMovement(ID1), DeepLinkRouter.fromPath("/tenant/finance/petty-cash/movements/$ID1"))
        assertEquals(OwnerDestination.Approvals(), DeepLinkRouter.fromPath("/tenant/finance/petty-cash/counts/$ID1"))
        val push = DeepLinkRouter.fromPush(mapOf("notification_id" to ID2, "entity" to "petty_cash_adjustment", "entity_id" to ID1, "link" to "/tenant/finance/petty-cash/adjustments"))!!
        assertEquals(OwnerDestination.PettyCashAdjustment(ID1), push.destination)
        val movement = OwnerDestination.PettyCashMovement(ID1)
        assertEquals(movement, OwnerFeatures(approver).route(movement))
        assertEquals(OwnerDestination.Notifications(), OwnerFeatures(setOf("tenant.finance.read")).route(movement))
    }

    @Test
    fun `expense flags are read and worded neutrally`() {
        val e = NetworkFactory.json.decodeFromString(ExpenseDto.serializer(),
            """{"id":"$ID1","amount":"5000","currency":"TZS","description":"Rope","status":"PENDING_APPROVAL","incurred_at":"2026-11-10T08:00:00Z",
            "submitted_at":"2026-11-10T08:00:00Z","paid_from":"PETTY_CASH","control_flags":["OVERSPEND"],"petty_cash_fund_id":"$ID2"}""")
        assertEquals(listOf("Recorded above what the fund had available"), ExpenseFlags.labels(e.controlFlags))
    }
}
