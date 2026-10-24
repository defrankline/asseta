package com.asseta.core.model

import com.asseta.core.model.sync.BootstrapDto
import com.asseta.core.model.sync.CashReconciliationDayDto
import com.asseta.core.model.sync.CashReconciliationDto
import com.asseta.core.model.sync.ChangesDto
import com.asseta.core.model.sync.FindingDto
import com.asseta.core.model.sync.HireAllocationDto
import com.asseta.core.model.sync.SyncAcknowledgementDto
import com.asseta.core.model.sync.SyncCapabilities
import com.asseta.core.model.sync.SyncCashCollectionDto
import com.asseta.core.model.sync.SyncCashHandoverDto
import com.asseta.core.model.sync.SyncData
import com.asseta.core.model.sync.SyncExpenseDto
import com.asseta.core.model.sync.SyncFuelEventDto
import com.asseta.core.model.sync.SyncJobActivityDto
import com.asseta.core.model.sync.SyncMeterCaptureDto
import com.asseta.core.model.sync.SyncMeterResetDto
import kotlinx.serialization.KSerializer
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Sync pull DTOs (supervisor inbox) against contracts/openapi.json and contract-shaped samples. */
class SyncContractTest {
    private val json = Json { ignoreUnknownKeys = true; explicitNulls = false }

    @Test
    fun `sync inbox DTOs match the contract schemas`() {
        mapOf<String, KSerializer<*>>(
            "SyncData" to SyncData.serializer(),
            "BootstrapDto" to BootstrapDto.serializer(),
            "ChangesDto" to ChangesDto.serializer(),
            "SyncMeterCaptureDto" to SyncMeterCaptureDto.serializer(),
            "ExceptionDto" to FindingDto.serializer(),
            "SyncMeterResetDto" to SyncMeterResetDto.serializer(),
            "SyncJobActivityDto" to SyncJobActivityDto.serializer(),
            "SyncAcknowledgementDto" to SyncAcknowledgementDto.serializer(),
            "SyncExpenseDto" to SyncExpenseDto.serializer(),
            "SyncFuelEventDto" to SyncFuelEventDto.serializer(),
            "SyncCashCollectionDto" to SyncCashCollectionDto.serializer(),
            "HireAllocationDto" to HireAllocationDto.serializer(),
            "SyncCashHandoverDto" to SyncCashHandoverDto.serializer(),
            "CashReconciliationDto" to CashReconciliationDto.serializer(),
            "CashReconciliationDayDto" to CashReconciliationDayDto.serializer(),
            "FieldContractDto" to com.asseta.core.model.sync.FieldContractDto.serializer(),
            "JobRequestIn" to com.asseta.core.model.sync.JobRequestPayload.serializer(),
        ).forEach { (name, serializer) -> ContractCheck.check(name, serializer.descriptor) }
    }

    @Test
    fun `older server without inbox lists leaves them absent`() {
        val data = json.decodeFromString(SyncData.serializer(), """{"jobs":[],"machines":[]}""")
        assertNull(data.myMeterCaptures)
        assertNull(data.myExpenses)
        val changes = json.decodeFromString(
            ChangesDto.serializer(),
            """{"server_time":"2026-10-23T08:00:00Z","cursor":5,"has_more":false,"data":{},"policy_snapshots":[]}""",
        )
        assertTrue(changes.capabilities.isEmpty())
    }

    @Test
    fun `parses capture with findings and an unknown enum value`() {
        val body = """{"capabilities":["SUPERVISOR_INBOX_V1","OP_METER_RESET_REQUEST"],"server_time":"2026-10-23T08:00:00Z","cursor":9,
            "has_more":true,"policy_snapshots":[],"data":{"my_meter_captures":[{"id":"c1","job_id":"j1","machine_id":"m1","kind":"OPENING",
            "capture_mode":"AUTOMATIC","reading":"1234.5","state":"PROVISIONAL","gps_status":"FIX","latitude":-6.8,"longitude":39.2,
            "accuracy_m":12.0,"location_captured_at":"2026-10-23T07:59:00Z","photo_attachment_id":"a1","photo_sha256":"ab","ocr_value":"1234.5",
            "ocr_confidence":0.91,"manually_corrected":false,"policy_version":"p1","supersedes_id":null,"tracker_comparison":null,
            "captured_at":"2026-10-23T07:59:30Z","received_at":"2026-10-23T08:00:00Z","sync_revision":42,"review_status":"PENDING_REVIEW",
            "findings":[{"id":"f1","exception_type":"SOMETHING_NEW","severity":"HIGH","blocking":true,"status":"OPEN","machine_id":"m1",
            "job_id":"j1","meter_capture_id":"c1","policy_version":null,"review_note":null,"reviewed_at":null,"created_at":"2026-10-23T08:00:00Z",
            "evidence":{"delta":"12"}}]}],
            "my_expenses":[{"id":"e1","client_id":"x1","category_id":"k1","description":"Diesel","supplier":null,"amount":"25000.00",
            "currency":"TZS","paid_from":"CASH_CUSTODY","status":"REJECTED","decision_note":"No receipt","decided_at":"2026-10-23T09:00:00Z",
            "decided_by":null,"incurred_at":"2026-10-23T07:00:00Z","submitted_at":"2026-10-23T07:10:00Z","submitted_by":null,
            "custodian_staff_id":null,"job_id":null,"machine_id":null,"gps_status":"FIX","gps_accuracy_m":5.0,"latitude":1.0,"longitude":2.0,
            "policy_version":"p","receipt_required":true,"source":"SYNC","receipt_attachment_ids":["r1","r2"],"approval_request_id":"ap1",
            "sync_revision":7}],
            "my_cash_collections":[{"id":"p1","client_id":"x2","customer_id":"cu1","amount":"10","currency":"TZS","method":"CASH",
            "status":"VERIFIED","decision_note":null,"reference":null,"note":null,"received_at":"2026-10-23T07:00:00Z","received_by_staff_id":"s1",
            "recorded_at":"2026-10-23T07:00:00Z","recorded_by":null,"verified_at":"2026-10-23T10:00:00Z","verified_by":null,"source":"SYNC",
            "allocations":[{"id":"al","invoice_id":"i1","amount":"10","created_at":"2026-10-23T10:00:00Z","released_at":null,"release_reason":null}],
            "sync_revision":3}]}}"""
        val dto = json.decodeFromString(ChangesDto.serializer(), body)
        assertTrue(SyncCapabilities.SUPERVISOR_INBOX_V1 in dto.capabilities)
        val capture = dto.data.myMeterCaptures!!.single()
        assertEquals("PENDING_REVIEW", capture.reviewStatus)
        assertEquals("SOMETHING_NEW", capture.findings.single().exceptionType)
        assertTrue(capture.findings.single().blocking)
        assertEquals(42L, capture.syncRevision)
        val expense = dto.data.myExpenses!!.single()
        assertEquals("No receipt", expense.decisionNote)
        assertEquals(listOf("r1", "r2"), expense.receiptAttachmentIds)
        assertEquals("10", dto.data.myCashCollections!!.single().allocations.single().amount)
        assertNull(dto.data.myFuelEvents)
    }

    @Test
    fun `parses reconciliation days`() {
        val body = """[{"staff_member_id":"s1","currency":"TZS","timezone":"Africa/Dar_es_Salaam","days":[{"day":"2026-10-23","opening":"0",
            "floats_issued":"100000","collections":"50000","approved_spending":"20000","verified_handovers":"30000","outstanding":"100000",
            "claimed_unverified_handovers":"10000","pending_spending":"5000","unverified_collections":"0","outstanding_if_claims_verified":"90000"}]}]"""
        val rows = json.decodeFromString(ListSerializer(CashReconciliationDto.serializer()), body)
        assertEquals("100000", rows.single().days.single().outstanding)
    }
}
