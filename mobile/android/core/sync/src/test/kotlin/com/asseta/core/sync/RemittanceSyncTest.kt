package com.asseta.core.sync

import com.asseta.core.domain.accountability.RemittanceMethod
import com.asseta.core.domain.accountability.RemittanceRequirements
import com.asseta.core.domain.accountability.RemittanceRules
import com.asseta.core.model.ClientOperationStatus.ACKED
import com.asseta.core.model.ClientOperationStatus.PENDING
import com.asseta.core.model.sync.BlobPurpose
import com.asseta.core.model.sync.SyncCapabilities
import com.asseta.core.sync.engine.SyncReport
import com.asseta.core.sync.usecase.CashHandoverRequest
import com.asseta.core.sync.usecase.FinanceResult
import com.asseta.core.sync.usecase.RemittanceDetails
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import java.util.UUID

/** DEC-031 D2: remittance details (method, deposit account, deposit slip photos) through the real engine and uploader. */
@RunWith(RobolectricTestRunner::class)
class RemittanceSyncTest : SyncTestBase() {
    private val bankId = "b0000000-0000-4000-8000-000000000001"
    private val mobileId = "b0000000-0000-4000-8000-000000000002"

    private fun account(id: String, name: String, type: String, active: Boolean = true, revision: Long = 1, currency: String = "TZS") = buildJsonObject {
        put("id", id); put("name", name); put("account_type", type); put("institution", "CRDB"); put("account_number_masked", "•••• 4821")
        put("currency", currency); put("note", null as String?); put("is_active", active); put("version", 1)
        put("created_by", null as String?); put("created_at", "2026-10-20T08:00:00Z"); put("updated_at", "2026-10-20T08:00:00Z")
        put("deactivated_at", null as String?); put("deactivated_by", null as String?); put("deactivation_reason", null as String?)
        put("sync_revision", revision)
    }

    private fun announce() {
        fake.capabilities = fake.capabilities.orEmpty() + SyncCapabilities.REMITTANCE_DETAILS_V1
        fake.inbox = mapOf("deposit_accounts" to listOf(account(bankId, "CRDB main", "BANK"), account(mobileId, "M-Pesa till", "MOBILE_MONEY")))
    }

    private fun success(report: SyncReport) = assertTrue("expected Success but was $report", report is SyncReport.Success)

    private fun saved(r: FinanceResult): FinanceResult.Saved {
        assertTrue("expected Saved but was $r", r is FinanceResult.Saved)
        return r as FinanceResult.Saved
    }

    private fun payload(opId: String): JsonObject = json.parseToJsonElement(op(opId).payloadJson).jsonObject

    private fun handover(details: RemittanceDetails?, reference: String = "") =
        CashHandoverRequest(tenant, UUID.randomUUID().toString(), "100000", "TZS", reference, "", clock.now, details = details)

    @Test
    fun depositAccountsAreKeptBySyncRevisionAndDeactivationsLeaveThePicker() = runBlocking {
        announce()
        success(engine().sync(tenant))
        assertEquals(listOf("CRDB main", "M-Pesa till"), financeRepository.observeDepositAccounts(tenant).first().map { it.name }.sorted())

        fake.cursor = 20
        fake.inbox = mapOf("deposit_accounts" to listOf(account(bankId, "CRDB main", "BANK", active = false, revision = 3)))
        success(engine().sync(tenant))
        val accounts = financeRepository.observeDepositAccounts(tenant).first()
        assertFalse(accounts.single { it.id == bankId }.isActive)
        assertTrue(RemittanceRules.accountsFor(accounts, RemittanceMethod.BANK_DEPOSIT, "TZS").isEmpty())

        fake.inbox = mapOf("deposit_accounts" to listOf(account(bankId, "CRDB main", "BANK", active = true, revision = 2))) // older replay
        success(engine().sync(tenant))
        assertFalse(financeRepository.depositAccount(bankId)!!.isActive)
    }

    @Test
    fun handoverWithSlipPhotoWaitsForTheUploadAndSendsItsUploadId() = runBlocking {
        announce()
        success(engine().sync(tenant))
        val details = RemittanceDetails(RemittanceMethod.BANK_DEPOSIT, bankId, listOf(photo), RemittanceRequirements(evidenceRequired = true))
        val saved = saved(finance.cashHandover(handover(details, reference = "DS-778")))
        val sent = payload(saved.operationId)
        assertEquals("BANK_DEPOSIT", sent["method"]!!.jsonPrimitive.content)
        assertEquals(bankId, sent["deposit_account_id"]!!.jsonPrimitive.content)
        assertTrue(sent["evidence_upload_ids"]!!.jsonArray.isEmpty())
        val attachment = db.evidenceDao().attachment(db.clientOperationDao().attachmentsOf(saved.operationId).single())!!
        assertEquals(BlobPurpose.REMITTANCE_EVIDENCE, attachment.purpose)

        fake.failChunkOnce = 1 // the photo upload is interrupted: the handover must not be sent before it completes
        assertTrue(engine().sync(tenant) is SyncReport.Retry)
        assertEquals(PENDING, status(saved.operationId))
        assertTrue(fake.pushedBatches.none { saved.operationId in it })

        success(engine().sync(tenant))
        assertEquals(ACKED, status(saved.operationId))
        val session = fake.blobs.values.single { it.attachmentId != null }
        assertEquals(listOf(session.id), payload(saved.operationId)["evidence_upload_ids"]!!.jsonArray.map { it.jsonPrimitive.content })
    }

    @Test
    fun requirementsAreEnforcedBeforeSaving() = runBlocking {
        announce()
        success(engine().sync(tenant))
        val strict = RemittanceRequirements(accountRequired = true, referenceRequired = true, evidenceRequired = true)
        val r = finance.cashHandover(handover(RemittanceDetails(RemittanceMethod.MOBILE_MONEY, null, emptyList(), strict)))
        assertEquals(
            listOf(RemittanceRules.ERR_ACCOUNT, RemittanceRules.ERR_REFERENCE, RemittanceRules.ERR_EVIDENCE),
            (r as FinanceResult.Invalid).messages,
        )
        // An account of another type than the method is refused on the phone (the server would answer REMITTANCE_ACCOUNT_MISMATCH).
        val mismatch = finance.cashHandover(handover(RemittanceDetails(RemittanceMethod.MOBILE_MONEY, bankId, emptyList(), RemittanceRequirements())))
        assertEquals(listOf(RemittanceRules.ERR_ACCOUNT_MISMATCH), (mismatch as FinanceResult.Invalid).messages)
        // Cash to the office never needs a reference.
        saved(finance.cashHandover(handover(RemittanceDetails(RemittanceMethod.CASH_TO_OFFICE, null, emptyList(), RemittanceRequirements(referenceRequired = true)))))
        Unit
    }

    @Test
    fun withoutTheCapabilityThePayloadIsUnchanged() = runBlocking {
        success(engine().sync(tenant))
        val plain = saved(finance.cashHandover(handover(null)))
        val sent = payload(plain.operationId)
        assertNull(sent["method"])
        assertNull(sent["deposit_account_id"])
        assertNull(sent["evidence_upload_ids"])
        // Details from an outdated form are refused rather than sent to a server that does not know them.
        val r = finance.cashHandover(handover(RemittanceDetails(RemittanceMethod.CASH_TO_OFFICE, null, emptyList(), RemittanceRequirements())))
        assertTrue(r is FinanceResult.Blocked)
    }
}
