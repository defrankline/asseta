package com.asseta.core.model

import com.asseta.core.model.owner.AccountabilitySummaryDto
import com.asseta.core.model.owner.CashRetentionDto
import com.asseta.core.model.owner.HoursTransferDto
import com.asseta.core.model.owner.NotificationDto
import com.asseta.core.model.owner.OverdueAmountDto
import com.asseta.core.model.owner.RemittanceOverdueDto
import com.asseta.core.model.sync.CashTransferDto
import com.asseta.core.model.sync.FloatEntryDto
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** DEC-030 gap pass: new DTOs match the contract; names decode and stay optional (older servers send none). */
class GapPassContractTest {
    private val json = Json { ignoreUnknownKeys = true; explicitNulls = false }

    @Test
    fun `new and named DTOs match the contract`() {
        ContractCheck.check("RemittanceOverdueDto", RemittanceOverdueDto.serializer().descriptor)
        ContractCheck.check("OverdueAmountDto", OverdueAmountDto.serializer().descriptor)
        ContractCheck.check("CashCustodyEntryDto", com.asseta.core.model.owner.CashCustodyEntryDto.serializer().descriptor)
        ContractCheck.check("TenantAccessDto", TenantAccess.serializer().descriptor, subset = true)
    }

    @Test
    fun `names decode when sent and are null when not`() {
        val named = json.decodeFromString(
            HoursTransferDto.serializer(),
            """{"id":"t","client_id":null,"purchase_id":"p","purchase_number":"HP-1","customer_name":"Kilimo","from_machine_id":"m1",
            "from_machine_code":"EX-01","from_machine_name":"Excavator","to_machine_id":"m2","to_machine_code":"EX-02","to_machine_name":null,
            "hours":"2.00","reason":"r","reason_code_id":null,"status":"PENDING","requested_by":"u","requested_by_name":"Asha",
            "requested_at":"2026-10-25T08:00:00Z","decided_by":null,"decided_at":null,"decision_note":null,"brand_new":[1,2]}""",
        )
        assertEquals("HP-1", named.purchaseNumber)
        assertEquals("Asha", named.requestedByName)
        assertNull(named.toMachineName)
        val old = json.decodeFromString(
            CashRetentionDto.serializer(),
            """{"id":"r","staff_member_id":"s","amount":"10","currency":"TZS","reason":"x","status":"PENDING","created_at":"2026-10-25T08:00:00Z"}""",
        )
        assertNull(old.staffMemberName)
        assertNull(old.clientId)
        val t = json.decodeFromString(
            CashTransferDto.serializer(),
            """{"id":"t","from_staff_id":"a","from_staff_name":"Juma","to_staff_id":"b","amount_declared":"5","currency":"TZS",
            "status":"PENDING_ACKNOWLEDGEMENT","transferred_at":"2026-10-25T08:00:00Z","recorded_at":"2026-10-25T08:00:00Z","source":"SYNC"}""",
        )
        assertEquals("Juma", t.fromStaffName)
        assertNull(t.toStaffName)
        val f = json.decodeFromString(
            FloatEntryDto.serializer(),
            """{"id":"f","staff_member_id":"s","staff_member_name":"Neema","entry_type":"FLOAT_ISSUED","amount":"1","currency":"TZS",
            "occurred_at":"2026-10-25T08:00:00Z","created_by_name":"Office"}""",
        )
        assertEquals("Neema", f.staffMemberName)
    }

    @Test
    fun `cash tile carries the remittance cut-off and notifications their record`() {
        val s = json.decodeFromString(
            AccountabilitySummaryDto.serializer(),
            """{"as_of":"x","policy_version":"v","cash":{"custodians":[],"remittance_cutoff_hour":18,"remittances_overdue_today":3}}""",
        )
        assertEquals(18, s.cash!!.remittanceCutoffHour)
        assertEquals(3, s.cash!!.remittancesOverdueToday)
        val off = json.decodeFromString(AccountabilitySummaryDto.serializer(), """{"as_of":"x","policy_version":"v","cash":{"custodians":[]}}""")
        assertNull(off.cash!!.remittancesOverdueToday)
        val n = json.decodeFromString(
            NotificationDto.serializer(),
            """{"id":"11111111-1111-4111-8111-111111111111","type":"REMITTANCE_OVERDUE","category":"c","severity":"WARNING","priority":"NORMAL",
            "title":"t","body":"b","created_at":"x","data":{"kind":"REMITTANCE_OVERDUE","record_id":"22222222-2222-4222-8222-222222222222","amounts":[]}}""",
        )
        assertEquals("REMITTANCE_OVERDUE", n.recordKind)
        assertEquals("22222222-2222-4222-8222-222222222222", n.recordId)
    }
}
