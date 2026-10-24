package com.asseta.core.domain.accountability

import com.asseta.core.domain.finance.FormCheck
import com.asseta.core.model.sync.SyncCapabilities
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class FieldAccountabilityTest {
    private val cashValues = Json.parseToJsonElement(
        """{"recorders_may_record_for_others":true,"transfer_ack_required":true,"recorder_receiver_counts_as_ack":true,
            "float_ack_required":true,"remit_full_balance":true,"remittance_cutoff_hour":18,"variance_case_threshold":null,
            "writeoff_requires_approval":true,"retention_allowed":false}""",
    ).jsonObject
    private val hoursValues = Json.parseToJsonElement(
        """{"enabled":true,"walk_in_allowed":false,"billing_modes":["PREPAID_HOURS"],"default_billing_mode":"PREPAID_HOURS",
            "transfer_requires_approval":true,"reason_code_required":true}""",
    ).jsonObject
    private val all = setOf(
        SyncCapabilities.OP_HOURS_PURCHASE, SyncCapabilities.OP_HOURS_TRANSFER_REQUEST, SyncCapabilities.OP_CASH_TRANSFER,
        SyncCapabilities.METER_DAILY_READING, SyncCapabilities.OP_METER_BASELINE, SyncCapabilities.OP_METER_CORRECTION,
    )
    private val perms = setOf("tenant.hours.purchase", "tenant.hours.transfer", "tenant.collection.record", "tenant.meter.capture")

    @Test
    fun `policies parse strictly and fail closed`() {
        val cash = CashCustodyPolicy.fromValues(cashValues)!!
        assertTrue(cash.recordersMayRecordForOthers)
        assertFalse(cash.retentionAllowed)
        assertNull(CashCustodyPolicy.fromValues(Json.parseToJsonElement("""{"transfer_ack_required":"yes"}""").jsonObject))
        val hours = CustomerHoursPolicy.fromValues(hoursValues)!!
        assertFalse(hours.walkInAllowed)
        assertTrue(hours.reasonCodeRequired)
    }

    @Test
    fun `every entry needs capability, permission and policy`() {
        val access = FieldAccess(all, perms, CashCustodyPolicy.fromValues(cashValues), CustomerHoursPolicy.fromValues(hoursValues))
        assertTrue(access.sellHours)
        assertFalse(access.walkIn) // policy: walk-ins off
        assertTrue(access.requestHoursTransfer && access.transferCash && access.recordForOthers)
        assertFalse(access.askToKeepCash) // policy: retention not allowed
        assertTrue(access.dailyReading && access.proposeBaseline && access.proposeCorrection)
        // Unknown policy (never loaded): hidden, so today's screens are unchanged.
        val noPolicy = FieldAccess(all, perms)
        assertFalse(noPolicy.sellHours || noPolicy.recordForOthers || noPolicy.askToKeepCash)
        assertTrue(noPolicy.transferCash)
        // Older server or never synced.
        assertFalse(FieldAccess(null, perms).dailyReading)
        assertFalse(FieldAccess(emptySet(), perms, CashCustodyPolicy.fromValues(cashValues)).transferCash)
        // No permission.
        assertFalse(FieldAccess(all, setOf("tenant.meter.capture"), CashCustodyPolicy.fromValues(cashValues)).recordForOthers)
    }

    @Test
    fun `hours sale checks`() {
        val draft = HoursSaleDraft(true, null, " ", "", "m1", "1.234", true, PaymentMethod.MOBILE_MONEY, "", "", "")
        val issues = (AccountabilityRules.hoursSale(draft, walkInAllowed = false) as FormCheck.Invalid).messages
        assertTrue(AccountabilityMessages.WALK_IN_OFF in issues)
        assertTrue(AccountabilityMessages.WALK_IN_NAME in issues)
        assertTrue(AccountabilityMessages.HOURS in issues)
        assertTrue(AccountabilityMessages.AMOUNT_RECEIVED in issues)
        assertTrue(AccountabilityMessages.REFERENCE in issues)
        val ok = AccountabilityRules.hoursSale(draft.copy(walkInName = "Joe", hoursText = "10,5", amountText = "100", reference = "MP123"), true)
        val v = (ok as FormCheck.Valid).value
        assertEquals("10.5", AccountabilityRules.plain(v.hours))
        assertEquals("MP123", v.reference)
        val unpaid = AccountabilityRules.hoursSale(draft.copy(walkIn = false, customerId = "c1", hoursText = "2", paidNow = false), true)
        assertNull((unpaid as FormCheck.Valid).value.amount)
    }

    @Test
    fun `transfer, cash and acknowledgement checks`() {
        val tooMany = AccountabilityRules.hoursTransfer("p", "m1", "m2", "5", "4.5".toBigDecimal(), "Broken", null, true)
        val m = (tooMany as FormCheck.Invalid).messages
        assertTrue("Only 4.5 h are left on this purchase." in m)
        assertTrue(AccountabilityMessages.CATEGORY in m)
        assertTrue(AccountabilityRules.hoursTransfer("p", "m1", "m1", "1", null, "Broken", null, false).let { it is FormCheck.Invalid && AccountabilityMessages.SAME_MACHINE in it.messages })
        assertTrue(AccountabilityRules.cashTransfer("s1", "s1", "10", "TZS", false, false, "", "").let { it is FormCheck.Invalid && AccountabilityMessages.TRANSFER_SAME in it.messages })
        val self = AccountabilityRules.cashTransfer("s2", "s1", "10", "tzs", receiverIsMe = true, selfAck = true, receivedText = "0", note = "")
        assertEquals(0, (self as FormCheck.Valid).value.amountReceived!!.signum())
        assertTrue(AccountabilityRules.acknowledgement(false, "", " ") is FormCheck.Invalid)
        assertEquals("No cash", (AccountabilityRules.acknowledgement(false, "", "No cash") as FormCheck.Valid).value.note)
        assertTrue(AccountabilityRules.acknowledgement(true, "abc", "") is FormCheck.Invalid)
        assertTrue(AccountabilityRules.retention("0", "TZS", "Fuel float") is FormCheck.Invalid)
        assertFalse(AccountabilityRules.correctionReasonValid("too short"))
        assertTrue(AccountabilityRules.correctionReasonValid("Typed the wrong digit"))
    }
}
