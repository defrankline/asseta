package com.asseta.owner

import com.asseta.core.domain.owner.DataSource
import com.asseta.core.domain.owner.DeepLinkRouter
import com.asseta.core.domain.owner.MutationCheck
import com.asseta.core.domain.owner.MutationGate
import com.asseta.core.domain.owner.OwnerAction
import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.domain.owner.OwnerErrors
import com.asseta.core.model.owner.CustomerPaymentDto
import com.asseta.core.model.owner.PaymentReview
import com.asseta.core.network.NetworkFactory
import com.asseta.owner.data.ActionResult
import com.asseta.owner.data.Load
import com.asseta.owner.ui.OwnerFeatures
import com.asseta.owner.ui.accountability.FigureTarget
import com.asseta.owner.ui.accountability.ManagementLinks
import com.asseta.owner.ui.approvals.PaymentReviewText
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.ZoneOffset

/** Go-live fix: the boss confirms or rejects customer payments from the phone. Strings doc "payments to confirm". */
class PaymentReviewOwnerTest {
    private val h = OwnerHarness()
    private val t = PaymentReviewText
    private val inv = "33333333-3333-4333-8333-333333333333"
    private val att = "44444444-4444-4444-8444-444444444444"

    @After fun tearDown() = h.close()

    private fun json(
        status: String = "CLAIMED",
        recordedBy: String? = ID2,
        recordedByName: String? = "Asha Mwita",
        customerName: String? = "Kilimo Ltd",
        allocations: String = """[{"id":"$att","invoice_id":"$inv","amount":"30000.00","created_at":"2026-11-01T08:00:00Z","released_at":null,"release_reason":null}]""",
    ) = """{"id":"$ID1","customer_id":"$ID2","customer_name":${customerName?.let { "\"$it\"" } ?: "null"},"client_id":null,"amount":"50000.00","currency":"TZS",
        "method":"MOBILE_MONEY","reference":"MP-77","received_at":"2026-11-01T07:00:00Z","received_by_staff_id":"$ID2","received_by_staff_name":"Juma",
        "status":"$status","note":"Paid at site","source":"FIELD","recorded_by":${recordedBy?.let { "\"$it\"" } ?: "null"},"recorded_by_name":${recordedByName?.let { "\"$it\"" } ?: "null"},
        "recorded_at":"2026-11-01T08:00:00Z","verified_by":null,"verified_at":null,"decision_note":null,"collection_number":"COL-12",
        "allocations":$allocations,"purchase_links":[{"purchase_id":"$inv","purchase_number":"HP-9","amount":"20000.00"}],"future_field":1}"""

    private fun payment(body: String = json()): CustomerPaymentDto = NetworkFactory.json.decodeFromString(CustomerPaymentDto.serializer(), body)

    private val readAndVerify = setOf("tenant.finance.read", "tenant.finance.verify")

    @Test
    fun `the list asks only for claimed payments`() = runBlocking {
        h.ok("""{"items":[${json()}],"total":1,"page":1,"page_size":100}""")
        val page = (h.data.paymentsToConfirm() as Load.Ok).snapshot.data
        val url = h.server.takeRequest().url.toString()
        assertTrue(url, url.contains("/customer-payments?") && url.contains("status=CLAIMED") && url.contains("page_size=100"))
        assertEquals("Kilimo Ltd paid TZS 50,000.00", t.headline(page.items.single()))
        assertEquals("Mobile money · COL-12", t.summary(page.items.single()))
        assertEquals("Recorded by Asha Mwita", t.recordedBy(page.items.single()))
    }

    @Test
    fun `a payment opens by id with evidence and invoice numbers`() = runBlocking {
        h.ok(json())
        h.ok("""[{"id":"$att","payment_id":"$ID1","attachment_id":"$att","created_by":null,"created_at":"2026-11-01T08:00:00Z"}]""")
        h.ok("""{"id":"$inv","invoice_number":"INV-4"}""")
        val review = (h.data.paymentReview(ID1) as Load.Ok).snapshot.data
        assertTrue(h.server.takeRequest().url.toString().endsWith("/customer-payments/$ID1"))
        assertTrue(h.server.takeRequest().url.toString().endsWith("/customer-payments/$ID1/evidence"))
        assertTrue(h.server.takeRequest().url.toString().endsWith("/hire-invoices/$inv"))
        assertEquals(listOf(att), review.evidenceIds)
        assertFalse(review.evidenceFailed)
        assertEquals(listOf("INV-4 · TZS 30,000.00"), t.invoices(review))
    }

    @Test
    fun `evidence that cannot be read is not the same as no evidence`() = runBlocking {
        h.ok(json(allocations = "[]"))
        h.error(403, "PERMISSION_DENIED")
        val review = (h.data.paymentReview(ID1) as Load.Ok).snapshot.data
        assertTrue(review.evidenceFailed)
        assertTrue(review.evidenceIds.isEmpty())
    }

    @Test
    fun `an invoice without a known number shows its short id and released ones are left out`() {
        val released = """[{"id":"$att","invoice_id":"$ID2","amount":"1.00","created_at":"2026-11-01T08:00:00Z","released_at":"2026-11-02T08:00:00Z","release_reason":"Payment rejected"},
            {"id":"$att","invoice_id":"$inv","amount":"30000.00","created_at":"2026-11-01T08:00:00Z","released_at":null,"release_reason":null}]"""
        assertEquals(listOf("33333333 · TZS 30,000.00"), t.invoices(PaymentReview(payment(json(allocations = released)))))
    }

    @Test
    fun `facts are named in screen order`() {
        val fields = t.fields(payment(), ZoneOffset.UTC)
        assertEquals(listOf("Customer", "Amount", "Method", "Reference", "Collection number", "Received", "Received by", "Recorded by", "Recorded", "Note"), fields.map { it.first })
        assertEquals("Asha Mwita", fields.first { it.first == "Recorded by" }.second)
        assertEquals(ID2.take(8), t.fields(payment(json(customerName = null)), ZoneOffset.UTC).first().second)
        assertEquals("A customer paid TZS 50,000.00", t.headline(payment(json(customerName = null))))
    }

    @Test
    fun `methods and statuses are in plain words`() {
        assertEquals("Cash", t.method("CASH"))
        assertEquals("Bank transfer", t.method("BANK"))
        assertEquals("Waiting to be confirmed", t.status("CLAIMED"))
        assertEquals("Confirmed", t.status("VERIFIED"))
        assertEquals("Rejected", t.status("REJECTED"))
    }

    @Test
    fun `a rejection needs a reason of at least 3 characters`() {
        assertTrue(t.canDecide(true, ""))
        assertFalse(t.canDecide(false, ""))
        assertFalse(t.canDecide(false, " ab "))
        assertTrue(t.canDecide(false, "abc"))
        assertFalse(t.canDecide(true, "x".repeat(1001)))
    }

    @Test
    fun `the decision is sent without amount and with a trimmed note`() = runBlocking {
        h.ok(json(status = "VERIFIED"))
        assertTrue(h.data.decidePayment(ID1, true, "  ") is ActionResult.Done)
        val confirm = h.server.takeRequest()
        assertTrue(confirm.url.toString().endsWith("/customer-payments/$ID1/decision"))
        assertEquals("""{"verified":true}""", confirm.body!!.utf8())

        h.ok(json(status = "REJECTED"))
        h.data.decidePayment(ID1, false, "  Not received ")
        assertEquals("""{"verified":false,"note":"Not received"}""", h.server.takeRequest().body!!.utf8())
    }

    @Test
    fun `refusals are in plain words and an already decided payment reloads`() = runBlocking {
        h.error(422, "SEGREGATION_OF_DUTIES", "The person who recorded a payment cannot verify it")
        val own = h.data.decidePayment(ID1, true, null) as ActionResult.Refused
        assertEquals("You recorded this payment, so someone else must confirm or reject it.", OwnerErrors.paymentMessage(own.code, own.error.message))

        h.error(409, "PAYMENT_ALREADY_DECIDED", "Payment already VERIFIED")
        val decided = h.data.decidePayment(ID1, true, null) as ActionResult.Refused
        assertTrue(decided.reload)
        assertEquals("Someone already decided this payment. Reload to see it.", OwnerErrors.paymentMessage(decided.code, decided.error.message))
    }

    @Test
    fun `the recorder cannot decide and only a waiting payment is decidable`() {
        val p = payment(json(recordedBy = ID2))
        assertTrue(t.isOwn(p, ID2))
        assertTrue(t.isOwn(p, ID2.uppercase()))
        assertFalse(t.isOwn(p, ID1))
        assertFalse(t.isOwn(p, null))
        assertFalse(t.isOwn(payment(json(recordedBy = null)), ID1))
        assertTrue(t.decidable(p))
        assertFalse(t.decidable(payment(json(status = "VERIFIED"))))
    }

    @Test
    fun `deciding is online only and needs tenant finance verify`() {
        assertEquals("tenant.finance.verify", OwnerAction.DECIDE_PAYMENT.permission)
        fun check(online: Boolean, source: DataSource, perms: Set<String>) = MutationGate.check(OwnerAction.DECIDE_PAYMENT, online, source, perms, false)
        assertEquals(MutationCheck.Allowed, check(true, DataSource.LIVE, readAndVerify))
        assertEquals(MutationCheck.Blocked(MutationGate.OFFLINE), check(false, DataSource.LIVE, readAndVerify))
        assertEquals(MutationCheck.Blocked(MutationGate.SHOWING_SAVED_DATA), check(true, DataSource.CACHE, readAndVerify))
        assertEquals(MutationCheck.Blocked(MutationGate.NOT_PERMITTED), check(true, DataSource.LIVE, setOf("tenant.finance.read")))
    }

    @Test
    fun `the section needs read and verify and opens the Approvals screen`() {
        assertTrue(OwnerFeatures(readAndVerify).confirmPayments)
        assertTrue(OwnerFeatures(readAndVerify).approvalsScreen)
        assertFalse(OwnerFeatures(setOf("tenant.finance.read")).confirmPayments)
        assertFalse(OwnerFeatures(setOf("tenant.finance.verify")).confirmPayments)
    }

    @Test
    fun `the payment notification opens the payment`() {
        val payment = OwnerDestination.CustomerPayment(ID1)
        assertEquals(payment, DeepLinkRouter.fromTarget("customer_payment", ID1, "/tenant/customer-payments", ID2, "CUSTOMER_PAYMENT_TO_VERIFY"))
        assertEquals(OwnerDestination.Approvals(), DeepLinkRouter.fromTarget("customer_payment", null, "/tenant/customer-payments"))
        assertEquals(payment, DeepLinkRouter.fromPath("/tenant/customer-payments/$ID1"))
        assertEquals(OwnerDestination.Approvals(), DeepLinkRouter.fromPath("/tenant/customer-payments?status=CLAIMED"))
        val push = DeepLinkRouter.fromPush(mapOf("notification_id" to ID2, "type" to "CUSTOMER_PAYMENT_TO_VERIFY", "tenant_id" to TENANT, "link" to "/tenant/customer-payments", "entity" to "customer_payment", "entity_id" to ID1))!!
        assertEquals(payment, push.destination)
        assertEquals(TENANT, push.tenantId)
        assertEquals(ID2, push.notificationId)
        // An id in the wrong form falls back to the link, not to a broken screen.
        assertEquals(OwnerDestination.Approvals(), DeepLinkRouter.fromPush(mapOf("link" to "/tenant/customer-payments", "entity" to "customer_payment", "entity_id" to "../x"))!!.destination)
    }

    @Test
    fun `a link for a role that cannot read payments opens the inbox`() {
        val payment = OwnerDestination.CustomerPayment(ID1)
        assertEquals(payment, OwnerFeatures(readAndVerify).route(payment))
        assertEquals(OwnerDestination.Notifications(), OwnerFeatures(setOf("tenant.finance.verify")).route(payment))
    }

    @Test
    fun `dashboard routes open the phone screens and other lists stay on the web`() {
        val f = OwnerFeatures(readAndVerify)
        assertEquals(FigureTarget.App(OwnerDestination.CustomerPayment(ID1)), ManagementLinks.target("/tenant/customer-payments/$ID1", f, "https://example.test"))
        assertEquals(FigureTarget.App(OwnerDestination.Approvals()), ManagementLinks.target("/tenant/customer-payments?status=CLAIMED", f, "https://example.test"))
        assertTrue(ManagementLinks.target("/tenant/customer-payments?method=CASH", f, "https://example.test") is FigureTarget.Web)
        assertTrue(ManagementLinks.target("/tenant/customer-payments?status=CLAIMED", OwnerFeatures(setOf("tenant.finance.read")), "https://example.test") is FigureTarget.Web)
        assertNull(ManagementLinks.target("", f, "https://example.test"))
    }
}
