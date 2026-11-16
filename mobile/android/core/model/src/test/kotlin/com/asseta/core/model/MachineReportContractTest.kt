package com.asseta.core.model

import com.asseta.core.model.sync.AvailableHoursDto
import com.asseta.core.model.sync.CreditActivationIn
import com.asseta.core.model.sync.CreditInvoiceDto
import com.asseta.core.model.sync.CreditInvoicePaymentDto
import com.asseta.core.model.sync.CreditInvoicePaymentIn
import com.asseta.core.model.sync.CreditInvoicePaymentPayload
import com.asseta.core.model.sync.CreditInvoiceSummaryDto
import com.asseta.core.model.sync.CustomerHoursSummaryDto
import com.asseta.core.model.sync.MachineReportDecisionIn
import com.asseta.core.model.sync.MachineReportDto
import com.asseta.core.model.sync.MachineReportLineDto
import com.asseta.core.model.sync.MachineReportLinePayload
import com.asseta.core.model.sync.MachineReportPayload
import com.asseta.core.model.sync.MachineReportReasonDto
import com.asseta.core.model.sync.MachineReportRejectIn
import com.asseta.core.model.sync.MachineReportStatusDto
import com.asseta.core.model.sync.ReportLotDto
import com.asseta.core.model.sync.SyncData
import com.asseta.core.model.sync.TrackerCheckDto
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** ADR-008 DTOs against contracts/openapi.json. */
class MachineReportContractTest {
    private val json = Json { ignoreUnknownKeys = true; explicitNulls = false }

    @Test
    fun `machine report and credit invoice DTOs match the contract`() {
        ContractCheck.check("MachineReportReasonDto", MachineReportReasonDto.serializer().descriptor)
        ContractCheck.check("MachineReportStatusDto", MachineReportStatusDto.serializer().descriptor)
        ContractCheck.check("AvailableHoursDto", AvailableHoursDto.serializer().descriptor)
        ContractCheck.check("LotDto", ReportLotDto.serializer().descriptor)
        ContractCheck.check("MachineReportLineDto", MachineReportLineDto.serializer().descriptor)
        ContractCheck.check("TrackerCheckDto", TrackerCheckDto.serializer().descriptor)
        ContractCheck.check("MachineReportDto", MachineReportDto.serializer().descriptor)
        ContractCheck.check("CreditInvoicePaymentDto", CreditInvoicePaymentDto.serializer().descriptor)
        ContractCheck.check("CreditInvoiceDto", CreditInvoiceDto.serializer().descriptor)
        ContractCheck.check("CreditInvoiceSummaryDto", CreditInvoiceSummaryDto.serializer().descriptor)
        ContractCheck.check("CustomerHoursSummaryDto", CustomerHoursSummaryDto.serializer().descriptor)
        ContractCheck.check("SyncData", SyncData.serializer().descriptor)
    }

    @Test
    fun `request bodies and sync payloads match the contract inputs`() {
        ContractCheck.check("MachineReportLineIn", MachineReportLinePayload.serializer().descriptor, request = true)
        // The sync op names its reading by `capture_id` (the DAILY METER_CAPTURE queued just before it).
        ContractCheck.check("MachineReportIn", MachineReportPayload.serializer().descriptor, request = true)
        ContractCheck.check("CreditInvoicePaymentIn", CreditInvoicePaymentIn.serializer().descriptor, request = true)
        ContractCheck.check("CreditInvoicePaymentIn", CreditInvoicePaymentPayload.serializer().descriptor,
            extra = setOf("invoice_id", "evidence_upload_ids"), request = true)
        ContractCheck.check("MachineReportDecisionIn", MachineReportDecisionIn.serializer().descriptor, request = true)
        ContractCheck.check("MachineReportRejectIn", MachineReportRejectIn.serializer().descriptor, request = true)
        ContractCheck.check("CreditActivationIn", CreditActivationIn.serializer().descriptor, request = true)
    }

    @Test
    fun `a submitted report decodes with its lines`() {
        val raw = """{"id":"r1","report_number":"MR-2026-00001","machine_id":"m1","machine_code":"EX-01","capture_id":"c1",
            "start_source":"REPORT","start_ref":"r0","start_reading":"1210.0","start_at":"2026-11-12T14:30:00Z","end_reading":"1510.0",
            "end_at":"2026-11-16T04:40:00Z","hours":"300.0","customer_hours":"220.0","non_productive_hours":"80.0","status":"SUBMITTED",
            "corrects_id":null,"note":null,"source":"SYNC","submitted_by":"u1","submitted_at":"2026-11-16T04:41:00Z","client_created_at":null,
            "decided_by":null,"decided_at":null,"decision_note":null,"policy_version":"v1",
            "lines":[{"id":"l1","line_no":1,"kind":"CUSTOMER","customer_id":"c1","reason_id":null,"hours":"120.0","note":null,"available_hours":"140"},
                     {"id":"l2","line_no":2,"kind":"NON_PRODUCTIVE","customer_id":null,"reason_id":"x","reason_name":"Breakdown / repair","hours":"40.0","note":"Hose"}],
            "tracker":{"available":true,"tracker_hours":"296.0","meter_hours":"300.0","difference":"4.0"}}"""
        val r = json.decodeFromString(MachineReportDto.serializer(), raw)
        assertEquals(2, r.lines.size)
        assertEquals("140", r.lines[0].availableHours)
        assertEquals("296.0", r.tracker!!.trackerHours)
        assertNull(r.decidedAt)
    }
}
