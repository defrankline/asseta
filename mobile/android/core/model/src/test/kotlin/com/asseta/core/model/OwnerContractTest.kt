package com.asseta.core.model

import com.asseta.core.model.owner.ActivityDto
import com.asseta.core.model.owner.AlertDto
import com.asseta.core.model.owner.AnomalyCaseDetailDto
import com.asseta.core.model.owner.AnomalyCaseDto
import com.asseta.core.model.owner.ApprovalRequestDto
import com.asseta.core.model.owner.CashSupervisorSummaryDto
import com.asseta.core.model.owner.ExceptionDto
import com.asseta.core.model.owner.ExpenseDto
import com.asseta.core.model.owner.FuelEventDto
import com.asseta.core.model.owner.HistoryDto
import com.asseta.core.model.owner.JobDto
import com.asseta.core.model.owner.JobSummaryDto
import com.asseta.core.model.owner.MachineMapDto
import com.asseta.core.model.owner.MeterCaptureDto
import com.asseta.core.model.owner.MeterResetDecisionIn
import com.asseta.core.model.owner.MeterResetDto
import com.asseta.core.model.owner.NotificationDto
import com.asseta.core.model.owner.NotificationRoutingDto
import com.asseta.core.model.owner.PageDto
import com.asseta.core.model.owner.PushDeviceDto
import com.asseta.core.model.owner.PushDeviceIn
import com.asseta.core.model.owner.TenantOverviewDto
import kotlinx.serialization.KSerializer
import kotlinx.serialization.SerializationException
import kotlinx.serialization.descriptors.SerialDescriptor
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Test
import java.math.BigDecimal

/** Owner DTOs against contracts/openapi.json (field names + required-ness) and against contract-shaped samples. */
class OwnerContractTest {
    private val json = Json { ignoreUnknownKeys = true; explicitNulls = false }
    private fun check(schemaName: String, descriptor: SerialDescriptor) = ContractCheck.check(schemaName, descriptor)

    @Test
    fun `owner DTOs match the contract schemas`() {
        mapOf<String, KSerializer<*>>(
            "TenantOverviewDto" to TenantOverviewDto.serializer(),
            "MachineMapDto" to MachineMapDto.serializer(),
            "HistoryDto" to HistoryDto.serializer(),
            "JobDto" to JobDto.serializer(),
            "JobTransitionIn" to com.asseta.core.model.owner.JobTransitionIn.serializer(),
            "JobSummaryDto" to JobSummaryDto.serializer(),
            "MeterCaptureDto" to MeterCaptureDto.serializer(),
            "AlertDto" to AlertDto.serializer(),
            "ApprovalRequestDto" to ApprovalRequestDto.serializer(),
            "AnomalyCaseDto" to AnomalyCaseDto.serializer(),
            "AnomalyCaseDetailDto" to AnomalyCaseDetailDto.serializer(),
            "NotificationDto" to NotificationDto.serializer(),
            "NotificationRoutingDto" to NotificationRoutingDto.serializer(),
            "PushDeviceDto" to PushDeviceDto.serializer(),
            "PushDeviceIn" to PushDeviceIn.serializer(),
            "MeDto" to MeResponse.serializer(),
            "TenantAccessDto" to TenantAccess.serializer(),
            "MenuDto" to MenuEntry.serializer(),
            "MenuGroupDto" to MenuGroup.serializer(),
            "ActivityDto" to ActivityDto.serializer(),
            "FuelEventDto" to FuelEventDto.serializer(),
            "ExceptionDto" to ExceptionDto.serializer(),
            "ResetDto" to MeterResetDto.serializer(),
            "ReviewIn" to MeterResetDecisionIn.serializer(),
            "CashSupervisorSummaryDto" to CashSupervisorSummaryDto.serializer(),
            "CashHandoverDto" to com.asseta.core.model.owner.CashHandoverDto.serializer(),
            "SettlementDecisionIn" to com.asseta.core.model.owner.SettlementDecisionIn.serializer(),
            "CashFloatIn" to com.asseta.core.model.owner.CashFloatIn.serializer(),
            "CashCustodyEntryDto" to com.asseta.core.model.owner.CashCustodyEntryDto.serializer(),
        ).forEach { (name, serializer) -> check(name, serializer.descriptor) }
    }

    @Test
    fun `parses overview with partial sections and exact money`() {
        val body = """{"tenant_id":"a3c1d1f2-1111-4222-8333-944455556666","as_of":"2026-10-22T08:00:00Z","timezone":"Africa/Dar_es_Salaam",
            "fleet":{"machines":3,"connectivity":{"live":1,"offline":2},"engine_on_verified":1,"open_alerts":{"critical":1},
            "reported_work_state":{"WORKING":1},"latest_source_at":"2026-10-22T07:59:00Z"},
            "work":null,"risk":null,
            "money":{"month_start":"2026-10-01","latest_source_at":null,"currencies":[{"currency":"TZS","receivables_outstanding":"1092500.0000",
            "receivables_overdue":"0.0000","overdue_invoices":0,"verified_receipts_mtd":"500000.0000","approved_expenses_mtd":"150000.0000",
            "cash_with_supervisors":"50000.0000"}]}}"""
        val o = json.decodeFromString(TenantOverviewDto.serializer(), body)
        assertEquals(2, o.fleet!!.connectivity.offline)
        assertEquals(0, o.fleet!!.connectivity.stale)
        assertEquals(1, o.fleet!!.openAlerts.total)
        assertNull(o.work)
        assertEquals(0, BigDecimal("1092500").compareTo(o.money!!.currencies[0].receivablesOutstanding.value))
    }

    @Test
    fun `money as float is rejected`() {
        val body = """{"id":"a3c1d1f2-1111-4222-8333-944455556666","subject_type":"EXPENSE","subject_id":"a3c1d1f2-1111-4222-8333-944455556667",
            "amount":1250.5,"currency":"TZS","reason":"r","status":"PENDING","requested_at":"2026-10-22T08:00:00Z","policy_version":"v1"}"""
        assertThrows(SerializationException::class.java) { json.decodeFromString(ApprovalRequestDto.serializer(), body) }
    }

    @Test
    fun `parses fleet rows with unknown enum values and missing position`() {
        val body = """[{"machine_id":"a3c1d1f2-1111-4222-8333-944455556666","asset_code":"EX-01","name":"Excavator","machine_status":"ACTIVE",
            "connectivity":"SOMETHING_NEW","is_live":false,"observed_engine":"UNKNOWN","observed_motion":"UNKNOWN","reported_work_status":"IDLE",
            "location_compliance":"UNKNOWN","open_alerts":0,"policy_version":"p","latitude":null,"longitude":null,"tracker_id":null}]"""
        val rows = json.decodeFromString(kotlinx.serialization.builtins.ListSerializer(MachineMapDto.serializer()), body)
        assertEquals("SOMETHING_NEW", rows[0].connectivity)
        assertFalse(rows[0].hasPosition)
    }

    @Test
    fun `parses alert page and notification with target`() {
        val page = """{"items":[{"id":"a3c1d1f2-1111-4222-8333-944455556666","alert_type":"TRACKER_OFFLINE","severity":"WARNING","status":"OPEN",
            "title":"Tracker offline","event_time":"2026-10-22T08:00:00Z","created_at":"2026-10-22T08:00:01Z","evidence":{"minutes":42,"site":"A"},
            "machine_id":null,"tracker_id":null,"acknowledged_at":null,"resolved_at":null,"resolution_note":null,"policy_version":null}],
            "total":1,"page":1,"page_size":50}"""
        val alerts = json.decodeFromString(PageDto.serializer(AlertDto.serializer()), page)
        assertEquals("42", alerts.items[0].evidence["minutes"].toString())
        val n = json.decodeFromString(NotificationDto.serializer(), """{"id":"a3c1d1f2-1111-4222-8333-944455556666","type":"APPROVAL_REQUESTED",
            "category":"ACTION","severity":"INFO","priority":"NORMAL","title":"t","body":"b","created_at":"2026-10-22T08:00:00Z","read_at":null,
            "target":{"entity":"approval","id":"a3c1d1f2-1111-4222-8333-944455556667","path":"/tenant/approvals"},"tenant_id":null,"data":{}}""")
        assertEquals("approval", n.target!!.entity)
    }

    @Test
    fun `parses field spend, meter evidence and cash rows with exact decimals`() {
        val id = "a3c1d1f2-1111-4222-8333-944455556666"
        val fuel = json.decodeFromString(FuelEventDto.serializer(), """{"id":"$id","client_id":null,"event_type":"PURCHASE","litres":"40.000",
            "unit_price":"3200.0000","attributed_cost":"128000.0000","currency":"TZS","machine_id":null,"job_id":"$id","expense_id":null,
            "meter_reading":null,"supplier":"Puma","occurred_at":"2026-10-22T08:00:00Z","note":null,"source":"MOBILE","recorded_by":null}""")
        assertEquals(0, BigDecimal("40").compareTo(fuel.litres.value))
        assertEquals(id, fuel.jobId.toString())
        val e = json.decodeFromString(ExceptionDto.serializer(), """{"id":"$id","job_id":null,"machine_id":"$id","meter_capture_id":null,
            "exception_type":"METER_DECREASE","severity":"CRITICAL","blocking":true,"evidence":{"delta":"-3"},"policy_version":null,
            "status":"OPEN","review_note":null,"reviewed_at":null,"created_at":"2026-10-22T08:00:00Z"}""")
        assertEquals(true, e.blocking)
        val r = json.decodeFromString(MeterResetDto.serializer(), """{"id":"$id","machine_id":"$id","old_reading":"1200.00","new_reading":"0.00",
            "effective_at":"2026-10-22T08:00:00Z","reason":"Meter replaced","evidence_attachment_id":null,"status":"PENDING","requested_by":null,"decided_at":null}""")
        assertEquals("1200.00", r.oldReading.toPlainString())
        val a = json.decodeFromString(ActivityDto.serializer(), """{"id":"$id","client_id":"$id","activity_type":"STANDBY","started_at":"2026-10-22T08:00:00Z",
            "ended_at":null,"billable":false,"note":null}""")
        assertNull(a.endedAt)
        val c = json.decodeFromString(CashSupervisorSummaryDto.serializer(), """{"staff_member_id":"$id","staff_name":"Neema","currency":"TZS",
            "period_from":"2026-10-22","period_to":"2026-10-22","opening":"0.0000","floats_issued":"100000.0000","collections":"0.0000",
            "approved_spending":"20000.0000","verified_handovers":"0.0000","closing_outstanding":"80000.0000","claimed_unverified_handovers":"0.0000",
            "pending_spending":"5000.0000","unverified_collections":"0.0000"}""")
        assertEquals(0, BigDecimal("80000").compareTo(c.closingOutstanding.value))
        val x = json.decodeFromString(ExpenseDto.serializer(), """{"id":"$id","amount":"150000.0000","currency":"TZS","description":"Tyre",
            "status":"REJECTED","incurred_at":"2026-10-22T08:00:00Z","submitted_at":"2026-10-22T08:00:00Z","paid_from":"COMPANY","decision_note":"Duplicate"}""")
        assertEquals("Duplicate", x.decisionNote)
    }
}
