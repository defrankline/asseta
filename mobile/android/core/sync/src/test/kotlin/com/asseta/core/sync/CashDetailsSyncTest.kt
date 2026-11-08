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
import kotlinx.serialization.json.jsonArray
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
            HoursSaleDraft(false, fake.customerId, "", "", fake.machineId, "12.50", false, PaymentMethod.CASH, "", "", ""),
            walkInAllowed = false, cashHolderId = null, receivedAtMs = clock.now, evidenceJpegs = emptyList(),
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
