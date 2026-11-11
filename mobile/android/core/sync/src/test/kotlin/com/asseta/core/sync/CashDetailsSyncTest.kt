package com.asseta.core.sync

import com.asseta.core.domain.accountability.AccountabilityMessages
import com.asseta.core.domain.accountability.HoursSaleDraft
import com.asseta.core.domain.accountability.PaymentMethod
import com.asseta.core.model.ClientOperationStatus.ACKED
import com.asseta.core.model.sync.BlobPurpose
import com.asseta.core.model.sync.SyncCapabilities
import com.asseta.core.sync.data.FieldOutbox
import com.asseta.core.sync.engine.SyncReport
import com.asseta.core.sync.usecase.AccountabilityCapture
import com.asseta.core.sync.usecase.CashCollectionRequest
import com.asseta.core.sync.usecase.CashHandoverRequest
import com.asseta.core.sync.usecase.FinanceResult
import com.asseta.core.sync.usecase.HoursSaleRequest
import com.asseta.core.sync.usecase.HoursTransferRequest
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.put
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import java.util.UUID

/** DEC-032 Phase 3: the collection link, the partial remittance reason and hours transfer evidence through the real outbox. */
@RunWith(RobolectricTestRunner::class)
class CashDetailsSyncTest : SyncTestBase() {
    private lateinit var accountability: AccountabilityCapture

    @Before
    fun setUp() {
        accountability = AccountabilityCapture({ db }, repository, financeRepository, FieldOutbox({ db }, json, clock, { account }), files, json)
        fake.capabilities = listOf(
            SyncCapabilities.SUPERVISOR_INBOX_V1, SyncCapabilities.CASH_DETAILS_V2, SyncCapabilities.OP_HOURS_PURCHASE, SyncCapabilities.OP_HOURS_TRANSFER_REQUEST,
        )
    }

    private fun synced() = runBlocking { assertTrue(engine().sync(tenant) is SyncReport.Success) }

    private fun saved(r: FinanceResult): FinanceResult.Saved {
        assertTrue("expected Saved but was $r", r is FinanceResult.Saved)
        return r as FinanceResult.Saved
    }

    private fun payload(opId: String): JsonObject = json.parseToJsonElement(op(opId).payloadJson).jsonObject

    private fun collection(purchaseId: String? = null, opId: String? = null, required: Boolean = false) = CashCollectionRequest(
        tenant, UUID.randomUUID().toString(), fake.customerId, null, "50000", "TZS", "", "", clock.now,
        purchaseId = purchaseId, purchaseOperationId = opId, linkRequired = required,
    )

    private fun handover(reason: String = "", id: String? = null, required: Boolean = false) = CashHandoverRequest(
        tenant, UUID.randomUUID().toString(), "50000", "TZS", "", "", clock.now,
        partialReason = reason, partialReasonId = id, partialReasonRequired = required,
    )

    private fun transfer(evidence: List<ByteArray> = emptyList(), required: Boolean = false) = HoursTransferRequest(
        tenant, UUID.randomUUID().toString(), "p1", fake.machineId, "m2", "2", "5".toBigDecimal(), "Machine broke down", null, false, evidence, required, clock.now,
    )

    private fun invoice(id: String, balance: String = "120000", currency: String = "TZS", customer: String = fake.customerId) = buildJsonObject {
        put("id", id); put("invoice_number", "INV-$id"); put("customer_id", customer); put("customer_name", "Acacia"); put("currency", currency)
        put("total", "200000"); put("paid", "80000"); put("balance", balance); put("due_date", null as String?); put("issued_at", "2026-11-01T08:00:00Z")
    }

    @Test
    fun openInvoicesAreReplacedByEveryPull() = runBlocking {
        fake.capabilities = fake.capabilities.orEmpty() + SyncCapabilities.SYNC_OPEN_INVOICES
        fake.inbox = mapOf("open_invoices" to listOf(invoice("i1"), invoice("i2")))
        synced()
        assertEquals(setOf("i1", "i2"), financeRepository.observeOpenInvoices(tenant).first().map { it.id }.toSet())

        fake.inbox = mapOf("open_invoices" to listOf(invoice("i2", balance = "5000")))
        synced()
        assertEquals("5000", financeRepository.observeOpenInvoices(tenant).first().single().balance)

        fake.inbox = emptyMap()
        synced()
        assertTrue(financeRepository.observeOpenInvoices(tenant).first().isEmpty())
    }

    @Test
    fun aServerWithoutTheCapabilityLeavesInvoicesAlone() = runBlocking {
        fake.inbox = mapOf("open_invoices" to listOf(invoice("i1")))
        synced()
        assertTrue(financeRepository.observeOpenInvoices(tenant).first().isEmpty())
    }

    @Test
    fun aCollectionPaysAnInvoiceUpToWhatItOwes() = runBlocking {
        fake.capabilities = fake.capabilities.orEmpty() + SyncCapabilities.SYNC_OPEN_INVOICES
        synced()
        val base = CashCollectionRequest(tenant, UUID.randomUUID().toString(), fake.customerId, null, "50000", "TZS", "", "", clock.now, invoiceId = "i1", linkRequired = true)
        val opId = saved(finance.cashCollection(base.copy(invoiceBalance = "20000".toBigDecimal()))).operationId
        val line = payload(opId)["allocations"]!!.jsonArray.single().jsonObject
        assertEquals("i1", line["invoice_id"]!!.jsonPrimitive.content)
        assertEquals("20000", line["amount"]!!.jsonPrimitive.content)
        assertNull(payload(opId)["purchase_id"])

        // Cash below what it owes: all the cash is allocated.
        val second = base.copy(clientId = UUID.randomUUID().toString(), invoiceBalance = "90000".toBigDecimal())
        assertEquals("50000", payload(saved(finance.cashCollection(second)).operationId)["allocations"]!!.jsonArray.single().jsonObject["amount"]!!.jsonPrimitive.content)
    }

    @Test
    fun aServerThatDoesNotAnnounceInvoicesRefusesTheLink() = runBlocking {
        synced()
        val request = CashCollectionRequest(tenant, UUID.randomUUID().toString(), fake.customerId, null, "50000", "TZS", "", "", clock.now, invoiceId = "i1", invoiceBalance = "20000".toBigDecimal())
        assertEquals(FinanceResult.Blocked(com.asseta.core.sync.usecase.CaptureMeterReading.SERVER_TOO_OLD), finance.cashCollection(request))
    }

    @Test
    fun collectionLinksThePurchaseAndRespectsTheCompanyRule() = runBlocking {
        synced()
        val opId = saved(finance.cashCollection(collection(purchaseId = "p1"))).operationId
        assertEquals("p1", payload(opId)["purchase_id"]!!.jsonPrimitive.content)

        val refused = finance.cashCollection(collection(required = true))
        assertEquals(listOf(AccountabilityMessages.COLLECTION_LINK_REQUIRED), (refused as FinanceResult.Invalid).messages)
        // Not required: no link at all.
        assertNull(payload(saved(finance.cashCollection(collection())).operationId)["purchase_id"])
    }

    @Test
    fun aCollectionOnAnUnsyncedPurchaseWaitsForIt() = runBlocking {
        synced()
        val sale = HoursSaleRequest(
            tenant, UUID.randomUUID().toString(),
            HoursSaleDraft(false, fake.customerId, "", "", fake.machineId, "12.50", emptyList(), ""),
            walkInAllowed = false, cashHolderId = null, receivedAtMs = clock.now, paymentEvidence = emptyList(),
        )
        val saleOp = saved(accountability.hoursSale(sale)).operationId
        val unsynced = financeRepository.observeUnsyncedPurchases(tenant).first().single()
        assertEquals(sale.clientId, unsynced.clientId)
        assertEquals(saleOp, unsynced.operationId)

        val opId = saved(finance.cashCollection(collection(purchaseId = unsynced.clientId, opId = unsynced.operationId))).operationId
        assertEquals(listOf(saleOp), db.clientOperationDao().dependenciesOf(opId))
        assertEquals(sale.clientId, payload(opId)["purchase_id"]!!.jsonPrimitive.content)
    }

    @Test
    fun anAcceptedSaleIsNoLongerListedAsUnsynced() = runBlocking {
        synced()
        val sale = HoursSaleRequest(
            tenant, UUID.randomUUID().toString(),
            HoursSaleDraft(false, fake.customerId, "", "", fake.machineId, "12.50", emptyList(), ""),
            walkInAllowed = false, cashHolderId = null, receivedAtMs = clock.now, paymentEvidence = emptyList(),
        )
        val saleOp = saved(accountability.hoursSale(sale)).operationId
        assertEquals(1, financeRepository.observeUnsyncedPurchases(tenant).first().size)
        synced()
        assertEquals(ACKED, status(saleOp))
        assertTrue(financeRepository.observeUnsyncedPurchases(tenant).first().isEmpty())
    }

    @Test
    fun withoutTheCapabilityALinkOrReasonIsNotSent() = runBlocking {
        fake.capabilities = listOf(SyncCapabilities.SUPERVISOR_INBOX_V1)
        synced()
        assertTrue(finance.cashCollection(collection(purchaseId = "p1")) is FinanceResult.Blocked)
        assertTrue(finance.cashHandover(handover("Kept for fuel")) is FinanceResult.Blocked)
        // Nothing asked for: unchanged payloads.
        val sent = payload(saved(finance.cashCollection(collection())).operationId)
        assertNull(sent["purchase_id"])
        val h = payload(saved(finance.cashHandover(handover())).operationId)
        assertNull(h["partial_reason"])
        assertNull(h["partial_reason_id"])
    }

    @Test
    fun handoverCarriesThePartialReason() = runBlocking {
        synced()
        val missing = finance.cashHandover(handover("", required = true))
        assertEquals(listOf(AccountabilityMessages.PARTIAL_REASON), (missing as FinanceResult.Invalid).messages)
        assertTrue(finance.cashHandover(handover("ab")) is FinanceResult.Invalid)
        val p = payload(saved(finance.cashHandover(handover("  Kept for fuel  ", "r1", required = true))).operationId)
        assertEquals("Kept for fuel", p["partial_reason"]!!.jsonPrimitive.content)
        assertEquals("r1", p["partial_reason_id"]!!.jsonPrimitive.content)
    }

    @Test
    fun transferEvidenceIsRequiredPerPolicyAndWaitsForTheUpload() = runBlocking {
        synced()
        assertEquals(listOf(AccountabilityMessages.TRANSFER_EVIDENCE_REQUIRED), (accountability.hoursTransfer(transfer(required = true)) as FinanceResult.Invalid).messages)
        assertNull(payload(saved(accountability.hoursTransfer(transfer())).operationId)["evidence_upload_ids"])

        val saved = saved(accountability.hoursTransfer(transfer(listOf(photo), required = true)))
        val attachment = db.evidenceDao().attachment(db.clientOperationDao().attachmentsOf(saved.operationId).single())!!
        assertEquals(BlobPurpose.ADJUSTMENT_EVIDENCE, attachment.purpose)
        assertTrue(payload(saved.operationId)["evidence_upload_ids"]!!.jsonArray.isEmpty())

        assertTrue(engine().sync(tenant) is SyncReport.Success)
        assertEquals(ACKED, status(saved.operationId))
        val session = fake.blobs.values.single { it.attachmentId != null }
        assertEquals(listOf(session.id), payload(saved.operationId)["evidence_upload_ids"]!!.jsonArray.map { it.jsonPrimitive.content })
    }
}
