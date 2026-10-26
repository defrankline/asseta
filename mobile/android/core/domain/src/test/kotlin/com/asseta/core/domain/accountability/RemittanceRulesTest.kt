package com.asseta.core.domain.accountability

import com.asseta.core.model.TenantAccess
import com.asseta.core.model.sync.SyncCapabilities
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class RemittanceRulesTest {
    private fun policy(extra: Map<String, Boolean> = emptyMap()) = CashCustodyPolicy.fromValues(
        buildJsonObject {
            listOf("recorders_may_record_for_others", "transfer_ack_required", "recorder_receiver_counts_as_ack", "float_ack_required",
                "remit_full_balance", "retention_allowed").forEach { put(it, false) }
            extra.forEach { (k, v) -> put(k, JsonPrimitive(v)) }
        },
    )!!

    @Test
    fun `older policies without the new keys require nothing`() {
        assertEquals(RemittanceRequirements(), policy().remittanceRequirements)
        val strict = policy(mapOf("remittance_reference_required" to true, "remittance_evidence_required" to true, "remittance_account_required" to true))
        assertEquals(RemittanceRequirements(accountRequired = true, referenceRequired = true, evidenceRequired = true), strict.remittanceRequirements)
    }

    @Test
    fun `requirements apply only with the capability and while cash custody is on`() {
        val strict = policy(mapOf("remittance_evidence_required" to true))
        val caps = setOf(SyncCapabilities.REMITTANCE_DETAILS_V1)
        assertTrue(FieldAccess(caps, emptySet(), strict).remittanceDetails)
        assertTrue(FieldAccess(caps, emptySet(), strict).remittanceRequirements.evidenceRequired)
        assertFalse(FieldAccess(caps, emptySet(), strict, disabled = setOf(TenantAccess.CASH_CUSTODY)).remittanceRequirements.evidenceRequired)
        assertFalse(FieldAccess(emptySet(), emptySet(), strict).remittanceDetails)
        assertFalse(FieldAccess(emptySet(), emptySet(), strict).remittanceRequirements.evidenceRequired)
        assertEquals(RemittanceRequirements(), FieldAccess(caps, emptySet(), null).remittanceRequirements)
    }

    @Test
    fun `method follows the account type and cash never needs a reference`() {
        assertEquals(RemittanceMethod.BANK_DEPOSIT, RemittanceMethod.ofAccountType("BANK"))
        assertEquals(RemittanceMethod.CASH_TO_OFFICE, RemittanceMethod.ofAccountType("CASH_OFFICE"))
        assertEquals(RemittanceMethod.MOBILE_MONEY, RemittanceMethod.ofWire("MOBILE_MONEY"))
        val req = RemittanceRequirements(referenceRequired = true)
        assertTrue(RemittanceRules.check(req, RemittanceMethod.CASH_TO_OFFICE, null, null, "TZS", "", 0).isEmpty())
        assertEquals(listOf(RemittanceRules.ERR_REFERENCE), RemittanceRules.check(req, RemittanceMethod.MOBILE_MONEY, null, null, "TZS", " ", 0))
        assertEquals(listOf("At most 10 photos per handover."), RemittanceRules.check(RemittanceRequirements(), RemittanceMethod.CASH_TO_OFFICE, null, null, "TZS", "", 11))
    }
}
