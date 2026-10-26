package com.asseta.owner

import com.asseta.core.model.owner.CashHandoverDto
import com.asseta.core.model.owner.CashVarianceDto
import com.asseta.core.model.owner.RemittanceOverdueDto
import com.asseta.core.network.NetworkFactory
import com.asseta.owner.ui.accountability.CashRecords
import com.asseta.owner.ui.accountability.DecisionMapper
import com.asseta.owner.ui.accountability.OwnerAccountabilityTexts
import com.asseta.owner.ui.cash.HandoverText
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.ZoneOffset

/** DEC-031 Phase 3 in the Owner app: remittance details beside "Amount received", surplus wording, held-too-long flags. */
class RemittanceDetailsOwnerTest {
    private val json = NetworkFactory.json

    private fun handover(extra: String) = json.decodeFromString(
        CashHandoverDto.serializer(),
        """{"id":"11111111-1111-4111-8111-111111111111","staff_member_id":"22222222-2222-4222-8222-222222222222","amount":"50000",
           "currency":"TZS","handed_at":"2026-10-26T06:00:00Z","status":"CLAIMED","source":"MOBILE","recorded_at":"2026-10-26T06:01:00Z"$extra}""",
    )

    @Test
    fun `remittance confirm shows method, account and reference`() {
        val h = handover(""","method":"BANK_DEPOSIT","deposit_account_id":"33333333-3333-4333-8333-333333333333",
            "deposit_account_name":"CRDB main","reference":"DS-778","evidence_attachment_ids":["44444444-4444-4444-8444-444444444444"]""")
        assertEquals(listOf("Method" to "Bank deposit", "Paid into" to "CRDB main", "Reference" to "DS-778"), HandoverText.details(h))
        assertEquals(1, h.evidenceAttachmentIds.size)
        assertFalse(HandoverText.noPhoto(h))
        assertEquals("deposit slip photo 1", OwnerAccountabilityTexts.remitPhoto(1))

        val noName = handover(""","method":"MOBILE_MONEY","deposit_account_id":"33333333-3333-4333-8333-333333333333"""")
        assertEquals(listOf("Method" to "Mobile money", "Paid into" to "33333333"), HandoverText.details(noName))
        assertTrue(HandoverText.noPhoto(noName))
    }

    @Test
    fun `older remittances show only their reference`() {
        val old = handover(""","reference":"R-1"""")
        assertEquals(listOf("Reference" to "R-1"), HandoverText.details(old))
        assertFalse(HandoverText.noPhoto(old))
        assertTrue(HandoverText.details(handover("")).isEmpty())
        assertNull(OwnerAccountabilityTexts.remitMethod(null))
        assertEquals("Cash to the office", OwnerAccountabilityTexts.remitMethod("CASH_TO_OFFICE"))
    }

    private fun variance(amount: String, kind: String?) = json.decodeFromString(
        CashVarianceDto.serializer(),
        """{"id":"v1","source_type":"REMITTANCE","source_id":"h1","staff_member_id":"s1","staff_member_name":"Juma","currency":"TZS",
           "declared_amount":"50000","received_amount":"${if (amount.startsWith("-")) "52000" else "48000"}","amount":"$amount",
           "status":"WRITE_OFF_PROPOSED","opened_at":"2026-10-26T07:00:00Z"${kind?.let { ""","kind":"$it"""" } ?: ""}}""",
    )

    @Test
    fun `a surplus reads Surplus to explain`() {
        val surplus = DecisionMapper.writeOff(variance("-2000", "SURPLUS"))
        assertTrue(surplus.headline, surplus.headline.startsWith("Surplus to explain: TZS 2,000"))
        val fields = surplus.fields.associate { it.label to it.value }
        assertTrue(fields["Surplus to explain"]!!.startsWith("TZS 2,000"))
        assertNull(fields["Difference"])

        val shortfall = DecisionMapper.writeOff(variance("2000", "SHORTFALL"))
        assertTrue(shortfall.headline.startsWith("Write off TZS 2,000"))
        assertTrue(shortfall.fields.any { it.label == "Difference" })
        // An older server sends no kind: a negative difference is still a surplus.
        assertTrue(DecisionMapper.writeOff(variance("-2000", null)).headline.startsWith("Surplus to explain"))
    }

    private fun overdue(extra: String) = json.decodeFromString(
        RemittanceOverdueDto.serializer(),
        """{"id":"o1","staff_member_id":"s1","staff_member_name":"Juma","local_day":"2026-10-26","cutoff_hour":9,
           "amounts":[{"currency":"TZS","amount":"80000"}],"flagged_at":"2026-10-26T09:00:00Z","policy_version":"v2"$extra}""",
    )

    @Test
    fun `overdue remittance shows the reason`() {
        val cutoff = overdue("")
        val c = CashRecords.overdueFields(cutoff, ZoneOffset.UTC).associate { it.label to it.value }
        assertEquals("Not remitted by the daily cut-off", c["Reason"])
        assertEquals("09:00", c["Cut-off"])
        assertEquals("Still held after the 09:00 cut-off on 2026-10-26.", CashRecords.overdueLine(cutoff, ZoneOffset.UTC))

        val held = overdue(""","reason":"HELD_TOO_LONG","held_since":"2026-10-22T10:15:00Z","max_holding_days":3""")
        val fields = CashRecords.overdueFields(held, ZoneOffset.UTC)
        val h = fields.associate { it.label to it.value }
        assertEquals("Held longer than allowed", h["Reason"])
        assertNull(h["Cut-off"])
        assertEquals("3 days", h["Allowed"])
        assertEquals(listOf("Cash held by", "Not remitted", "Reason", "Day", "Held since", "Allowed", "Flagged"), fields.map { it.label })
        assertEquals("Held since ${h["Held since"]}, longer than the allowed 3 days.", CashRecords.overdueLine(held, ZoneOffset.UTC))
        assertEquals("Held longer than allowed.", CashRecords.overdueLine(overdue(""","reason":"HELD_TOO_LONG""""), ZoneOffset.UTC))
    }
}
