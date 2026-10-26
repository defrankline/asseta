package com.asseta.core.model

import com.asseta.core.model.owner.AccountabilitySummaryDto
import com.asseta.core.model.owner.ApprovalsTileDto
import com.asseta.core.model.owner.AttemptsTileDto
import com.asseta.core.model.owner.BaselineDto
import com.asseta.core.model.owner.CashRetentionDto
import com.asseta.core.model.owner.CashTileDto
import com.asseta.core.model.owner.CashVarianceDto
import com.asseta.core.model.owner.ClassificationDto
import com.asseta.core.model.owner.CorrectionDto
import com.asseta.core.model.owner.CountAmountDto
import com.asseta.core.model.owner.CreditArrangementDto
import com.asseta.core.model.owner.CustodianCashDto
import com.asseta.core.model.owner.CustodyAdjustmentDto
import com.asseta.core.model.owner.DecisionIn
import com.asseta.core.model.owner.DiscountDto
import com.asseta.core.model.owner.DiscrepanciesTileDto
import com.asseta.core.model.owner.HoursCancellationDto
import com.asseta.core.model.owner.HoursTransferDto
import com.asseta.core.model.owner.InvestigationsTileDto
import com.asseta.core.model.owner.MeterCaptureDto
import com.asseta.core.model.owner.MeterDecisionIn
import com.asseta.core.model.owner.PaymentsTileDto
import com.asseta.core.model.sync.BaselinePayload
import com.asseta.core.model.sync.CashCollectionPayload
import com.asseta.core.model.sync.CashFloatAckPayload
import com.asseta.core.model.sync.CashHandoverPayload
import com.asseta.core.model.sync.CashReasonDto
import com.asseta.core.model.sync.CashRetentionIn
import com.asseta.core.model.sync.CashTransferAckPayload
import com.asseta.core.model.sync.CashTransferDto
import com.asseta.core.model.sync.CashTransferPayload
import com.asseta.core.model.sync.ChangesDto
import com.asseta.core.model.sync.CorrectionPayload
import com.asseta.core.model.sync.CustodianDto
import com.asseta.core.model.sync.EffectivePolicyDto
import com.asseta.core.model.sync.FieldHoursPurchaseDto
import com.asseta.core.model.sync.FloatEntryDto
import com.asseta.core.model.sync.HoursPurchasePayload
import com.asseta.core.model.sync.HoursTransferPayload
import com.asseta.core.model.sync.MachineHoursDto
import com.asseta.core.model.sync.MeterCaptureIn
import com.asseta.core.model.sync.PurchasePaymentPayload
import com.asseta.core.model.sync.PurchaseTotalsDto
import com.asseta.core.model.sync.ReasonCodeDto
import com.asseta.core.model.sync.SyncCapabilities
import com.asseta.core.model.sync.WalkInCustomerPayload
import kotlinx.serialization.KSerializer
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Accountability DTOs and sync payloads against contracts/openapi.json, and DAILY readings without a job. */
class AccountabilityContractTest {
    private val json = Json { ignoreUnknownKeys = true; explicitNulls = false; encodeDefaults = true }

    @Test
    fun `owner accountability DTOs match the contract`() {
        mapOf<String, KSerializer<*>>(
            "DecisionIn" to DecisionIn.serializer(),
            "MeterDecisionIn" to MeterDecisionIn.serializer(),
            "DiscountDto" to DiscountDto.serializer(),
            "CreditArrangementDto" to CreditArrangementDto.serializer(),
            "TransferDto" to HoursTransferDto.serializer(),
            "CancellationDto" to HoursCancellationDto.serializer(),
            "BaselineDto" to BaselineDto.serializer(),
            "ClassificationDto" to ClassificationDto.serializer(),
            "CorrectionDto" to CorrectionDto.serializer(),
            "CashVarianceDto" to CashVarianceDto.serializer(),
            "CashRetentionDto" to CashRetentionDto.serializer(),
            "CustodyAdjustmentDto" to CustodyAdjustmentDto.serializer(),
            "CountAmountDto" to CountAmountDto.serializer(),
            "ApprovalsTileDto" to ApprovalsTileDto.serializer(),
            "AttemptsTileDto" to AttemptsTileDto.serializer(),
            "CustodianCashDto" to CustodianCashDto.serializer(),
            "CashTileDto" to CashTileDto.serializer(),
            "PaymentsTileDto" to PaymentsTileDto.serializer(),
            "DiscrepanciesTileDto" to DiscrepanciesTileDto.serializer(),
            "InvestigationsTileDto" to InvestigationsTileDto.serializer(),
            "AccountabilitySummaryDto" to AccountabilitySummaryDto.serializer(),
        ).forEach { (name, serializer) -> ContractCheck.check(name, serializer.descriptor) }
    }

    @Test
    fun `revenue DTOs match the contract`() {
        mapOf<String, KSerializer<*>>(
            "RevenueDifferenceDto" to com.asseta.core.model.owner.RevenueDifferenceDto.serializer(),
            "RevenueAdjustmentDto" to com.asseta.core.model.owner.RevenueAdjustmentDto.serializer(),
            "RevenueReasonDto" to com.asseta.core.model.owner.RevenueReasonDto.serializer(),
            "NonRevenueActivityDto" to com.asseta.core.model.owner.NonRevenueActivityDto.serializer(),
            "NonRevenueApprovalDto" to com.asseta.core.model.owner.NonRevenueApprovalDto.serializer(),
            "DailyMachineSheetRowDto" to com.asseta.core.model.owner.DailyMachineSheetRowDto.serializer(),
            "DailyMachineSheetDetailDto" to com.asseta.core.model.owner.DailyMachineSheetDetailDto.serializer(),
            "SheetJobDto" to com.asseta.core.model.owner.SheetJobDto.serializer(),
            "SheetMoneyDto" to com.asseta.core.model.owner.SheetMoneyDto.serializer(),
            "SheetReadingDto" to com.asseta.core.model.owner.SheetReadingDto.serializer(),
            "SheetSegmentDto" to com.asseta.core.model.owner.SheetSegmentDto.serializer(),
            "SheetMoneySourceDto" to com.asseta.core.model.owner.SheetMoneySourceDto.serializer(),
            "SheetFlagRefDto" to com.asseta.core.model.owner.SheetFlagRefDto.serializer(),
            "SheetFuelDto" to com.asseta.core.model.owner.SheetFuelDto.serializer(),
        ).forEach { (name, serializer) -> ContractCheck.check(name, serializer.descriptor) }
        ContractCheck.check("RevenueExplanationIn", com.asseta.core.model.owner.RevenueExplanationIn.serializer().descriptor, request = true)
        ContractCheck.check("RevenueDecisionIn", com.asseta.core.model.owner.RevenueDecisionIn.serializer().descriptor, request = true)
        ContractCheck.check("NonRevenueApprovalIn", com.asseta.core.model.owner.NonRevenueApprovalIn.serializer().descriptor, request = true)
        ContractCheck.check("NonRevenueDecisionIn", com.asseta.core.model.owner.NonRevenueDecisionIn.serializer().descriptor, request = true)
    }

    @Test
    fun `field reads match the contract`() {
        mapOf<String, KSerializer<*>>(
            "CustodianDto" to CustodianDto.serializer(),
            "CashTransferDto" to CashTransferDto.serializer(),
            "CashCustodyEntryDto" to FloatEntryDto.serializer(),
        ).forEach { (name, serializer) -> ContractCheck.check(name, serializer.descriptor) }
        ContractCheck.check("CashReasonDto", CashReasonDto.serializer().descriptor, subset = true)
        ContractCheck.check("ReasonCodeDto", ReasonCodeDto.serializer().descriptor, subset = true)
        ContractCheck.check("EffectivePolicyDto", EffectivePolicyDto.serializer().descriptor)
        ContractCheck.check("HoursPurchaseDto", FieldHoursPurchaseDto.serializer().descriptor, subset = true)
        ContractCheck.check("PurchaseTotalsDto", PurchaseTotalsDto.serializer().descriptor, subset = true)
        ContractCheck.check("MachineHoursDto", MachineHoursDto.serializer().descriptor, subset = true)
        // DEC-031 P4: owner customer hours (read-only).
        ContractCheck.check("HoursPurchaseDto", com.asseta.core.model.owner.OwnerHoursPurchaseDto.serializer().descriptor, subset = true)
        ContractCheck.check("HoursStatementDto", com.asseta.core.model.owner.HoursStatementDto.serializer().descriptor, subset = true)
        ContractCheck.check("HoursStatementTotalsDto", com.asseta.core.model.owner.HoursStatementTotalsDto.serializer().descriptor)
        ContractCheck.check("HoursStatementUsageDto", com.asseta.core.model.owner.HoursStatementUsageDto.serializer().descriptor)
    }

    @Test
    fun `sync payloads match the contract input schemas`() {
        ContractCheck.check("HoursPurchaseIn", HoursPurchasePayload.serializer().descriptor, extra = setOf("evidence_upload_ids"), request = true)
        ContractCheck.check("PurchasePaymentIn", PurchasePaymentPayload.serializer().descriptor, request = true)
        ContractCheck.check("WalkInCustomerIn", WalkInCustomerPayload.serializer().descriptor, request = true)
        ContractCheck.check("TransferIn", HoursTransferPayload.serializer().descriptor, request = true)
        ContractCheck.check("CashTransferIn", CashTransferPayload.serializer().descriptor, request = true)
        ContractCheck.check("CashAcknowledgementIn", CashTransferAckPayload.serializer().descriptor, extra = setOf("transfer_id"), request = true)
        ContractCheck.check("CashAcknowledgementIn", CashFloatAckPayload.serializer().descriptor, extra = setOf("entry_id"), request = true)
        ContractCheck.check("BaselineIn", BaselinePayload.serializer().descriptor, request = true)
        ContractCheck.check("CorrectionIn", CorrectionPayload.serializer().descriptor, request = true)
        ContractCheck.check("MeterCaptureIn", MeterCaptureIn.serializer().descriptor, request = true)
        ContractCheck.check("CashCollectionIn", CashCollectionPayload.serializer().descriptor, extra = setOf("client_id"), request = true)
        ContractCheck.check("CashHandoverIn", CashHandoverPayload.serializer().descriptor, extra = setOf("client_id", "evidence_upload_ids"), request = true)
        ContractCheck.check("CashRetentionIn", CashRetentionIn.serializer().descriptor, request = true)
        ContractCheck.check("SiteCheckinIn", com.asseta.core.model.sync.SiteCheckinPayload.serializer().descriptor, request = true)
    }

    @Test
    fun `oversight DTOs match the contract`() {
        mapOf<String, KSerializer<*>>(
            "AmountByCurrencyDto" to com.asseta.core.model.owner.AmountByCurrencyDto.serializer(),
            "CashHeldDto" to com.asseta.core.model.owner.CashHeldDto.serializer(),
            "ScorecardRowDto" to com.asseta.core.model.owner.ScorecardRowDto.serializer(),
            "ScorecardRecordDto" to com.asseta.core.model.owner.ScorecardRecordDto.serializer(),
            "ScorecardDetailDto" to com.asseta.core.model.owner.ScorecardDetailDto.serializer(),
            "UnbilledJobDto" to com.asseta.core.model.owner.UnbilledJobDto.serializer(),
            "IdleMachineDto" to com.asseta.core.model.owner.IdleMachineDto.serializer(),
            "SiteCheckinDto" to com.asseta.core.model.owner.SiteCheckinDto.serializer(),
            "CheckinSlotDto" to com.asseta.core.model.owner.CheckinSlotDto.serializer(),
            "MySiteCheckinsDto" to com.asseta.core.model.owner.MySiteCheckinsDto.serializer(),
        ).forEach { (name, serializer) -> ContractCheck.check(name, serializer.descriptor) }
    }

    @Test
    fun `site check-in payload keeps a failed GPS attempt without coordinates`() {
        val payload = com.asseta.core.model.sync.SiteCheckinPayload("c1", "2026-10-26T07:00:00Z", com.asseta.core.model.sync.GpsIn("TIMEOUT"))
        val wire = json.encodeToJsonElement(com.asseta.core.model.sync.SiteCheckinPayload.serializer(), payload).jsonObject
        assertEquals("c1", wire["client_id"].toString().trim('"'))
        assertFalse("latitude" in wire["gps"]!!.jsonObject)
        assertFalse("job_site_id" in wire)
    }

    @Test
    fun `daily reading without a job decodes in the pull and in the owner list`() {
        val body = """{"capabilities":["SUPERVISOR_INBOX_V1","METER_DAILY_READING"],"server_time":"2026-10-25T08:00:00Z","cursor":3,"has_more":false,
            "policy_snapshots":[],"data":{"my_meter_captures":[{"id":"c9","job_id":null,"machine_id":"m1","kind":"DAILY","capture_mode":"MANUAL",
            "reading":"1500.0","state":"ACCEPTED","gps_status":"FIX","latitude":null,"longitude":null,"accuracy_m":null,"location_captured_at":null,
            "photo_attachment_id":null,"photo_sha256":null,"ocr_value":null,"ocr_confidence":null,"manually_corrected":false,"policy_version":"p",
            "supersedes_id":null,"tracker_comparison":null,"captured_at":"2026-10-25T07:00:00Z","received_at":"2026-10-25T07:01:00Z","sync_revision":5}]}}"""
        val dto = json.decodeFromString(ChangesDto.serializer(), body)
        assertTrue(SyncCapabilities.METER_DAILY_READING in dto.capabilities)
        val capture = dto.data.myMeterCaptures!!.single()
        assertNull(capture.jobId)
        assertEquals("m1", capture.machineId)
        // Also when the server leaves job_id out altogether.
        val owner = json.decodeFromString(MeterCaptureDto.serializer(), """{"id":"a3c1d1f2-1111-4222-8333-944455556666",
            "machine_id":"a3c1d1f2-1111-4222-8333-944455556667","kind":"DAILY","reading":"10.5","capture_mode":"MANUAL",
            "captured_at":"2026-10-25T07:00:00Z","received_at":"2026-10-25T07:01:00Z","gps_status":"FIX","state":"ACCEPTED",
            "manually_corrected":false,"policy_version":"p"}""")
        assertNull(owner.jobId)
    }

    @Test
    fun `daily capture payload sends the machine and no job`() {
        val payload = MeterCaptureIn(
            id = "c1", kind = "DAILY", captureMode = "MANUAL", reading = "12", gps = com.asseta.core.model.sync.GpsIn("NO_FIX"),
            deviceId = "dev-1", capturedAt = "2026-10-25T07:00:00Z", machineId = "m1",
        )
        val wire = json.encodeToJsonElement(MeterCaptureIn.serializer(), payload).jsonObject
        assertFalse("job_id" in wire)
        assertEquals("m1", wire["machine_id"].toString().trim('"'))
    }

    @Test
    fun `parses a summary with hidden and object tiles`() {
        val body = """{"as_of":"2026-10-25T08:00:00Z","policy_version":"v3","hidden_tiles":["payments"],"unavailable_tiles":[],
            "outstanding_approvals":{"approval_requests":1,"payments_to_verify":2,"remittances_to_verify":3,"cash_retentions":0,
            "custody_adjustments":0,"write_offs":1,"total":7},"cash":{"custodians":[{"staff_member_id":"s1","staff_name":"Juma","currency":"TZS",
            "outstanding":"50000","in_transit_out":"0","pending_floats":"0","claimed_unverified_handovers":"0"}],
            "transfers_awaiting_acknowledgement":[{"count":1,"amount":"10000","currency":"TZS"}],"floats_awaiting_acknowledgement":[],
            "remittances_awaiting_confirmation":[],"partial_remittances_in_window":0},"payments":null,"discrepancies":null,"investigations":null,
            "unauthorized_attempts":{"permission_denied":4,"segregation_of_duties":1,"window_days":30},
            "customer_hours":{"customers":2,"remaining":"12.5","purchases_by_status":{"ACTIVE":1}},"engine_hours":null,"unexplained_hours":null,
            "hours_awaiting_activation":null,"missing_daily_reports":{"count":0,"items":[]}}"""
        val s = json.decodeFromString(AccountabilitySummaryDto.serializer(), body)
        assertEquals(7, s.outstandingApprovals!!.total)
        assertEquals("Juma", s.cash!!.custodians.single().staffName)
        assertNull(s.payments)
        assertEquals(listOf("payments"), s.hiddenTiles)
        assertTrue(s.customerHours!!.containsKey("remaining"))
    }
}
