package com.asseta.core.model

import com.asseta.core.model.owner.MeterCaptureDto
import com.asseta.core.model.owner.OwnerHoursPurchaseDto
import com.asseta.core.model.owner.PageDto
import com.asseta.core.model.sync.AvailableHoursDto
import com.asseta.core.model.sync.CreditInvoiceDto
import com.asseta.core.model.sync.CustomerHoursSummaryDto
import com.asseta.core.model.sync.MachineReportDto
import com.asseta.core.model.sync.MachineReportStatusDto
import com.asseta.core.model.sync.ReportFindingDto
import com.asseta.core.model.sync.SyncData
import kotlinx.serialization.KSerializer
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * Real server responses (contracts/fixtures, written by backend tests/api/test_contract_fixtures.py) decoded with the
 * app's Json settings (NetworkFactory): every fixture must decode, so a DTO that disagrees with what the server really
 * sends fails here instead of on a screen ("Unexpected response from the server").
 */
class ContractFixturesTest {
    /** Same settings as `NetworkFactory.json`. */
    private val json = Json { ignoreUnknownKeys = true; explicitNulls = false; encodeDefaults = true }

    private val fixtures: File by lazy { File(System.getProperty("asseta.contracts.dir") ?: error("asseta.contracts.dir not set"), "fixtures") }

    private fun <T> decode(path: String, serializer: KSerializer<T>): T {
        val file = File(fixtures, path)
        assertTrue("$path missing", file.exists())
        return json.decodeFromString(serializer, file.readText())
    }

    private val report = MachineReportDto.serializer()
    private val reportPage = PageDto.serializer(report)

    @Test
    fun `every machine report fixture decodes`() {
        val opening = decode("machine-reports/report-opening-submitted.json", report)
        assertTrue(opening.isOpening)
        assertEquals("OPENING", opening.startSource)
        assertTrue(opening.lines.isEmpty())
        assertEquals("GPS_INACCURATE", opening.findings.single().type)
        assertEquals(MachineReportDto.SUBMITTED, opening.status)

        val submitted = decode("machine-reports/report-submitted.json", report)
        assertFalse(submitted.isOpening)
        assertEquals(2, submitted.lines.size)
        assertTrue(submitted.lines.any { it.availableHours != null })

        val rejected = decode("machine-reports/report-rejected.json", report)
        assertEquals(MachineReportDto.REJECTED, rejected.status)
        // A rejected report is final: never corrected; its reading's place is kept.
        assertTrue(rejected.correctedById == null && rejected.decisionNote != null)
        assertEquals("Mbezi Beach, Kinondoni, Dar es Salaam", rejected.visitPlace)
        assertNull(rejected.sincePreviousVisitSeconds)

        val approved = decode("machine-reports/report-approved.json", report)
        assertEquals(MachineReportDto.APPROVED, approved.status)
        assertNull(approved.correctsId)
        // The previous visit (the rejected report's reading) with its place.
        assertEquals(3600L, approved.sincePreviousVisitSeconds)
        assertEquals("Mbezi Beach, Kinondoni, Dar es Salaam", approved.previousVisitPlace)
        assertEquals(-6.8, approved.visitLat!!, 0.0)
        assertTrue(approved.lines.any { it.lots.isNotEmpty() })

        val pending = decode("machine-reports/list-pending.json", reportPage)
        assertTrue(pending.items.any { it.isOpening })
        assertTrue(pending.items.all { it.status == MachineReportDto.SUBMITTED })
        assertEquals(4, decode("machine-reports/list-all.json", reportPage).items.size)
        assertEquals(4, decode("machine-reports/list-mine.json", reportPage).items.size)
    }

    @Test
    fun `report status, available hours, the reading and the sync snapshot decode`() {
        val statuses = decode("machine-reports/status.json", ListSerializer(MachineReportStatusDto.serializer()))
        assertEquals(2, statuses.size)
        assertTrue(statuses.any { it.pendingReportId != null })
        assertTrue(statuses.all { it.lastVisitAt != null && it.lastVisitLat != null })
        assertTrue(decode("machine-reports/available-hours.json", ListSerializer(AvailableHoursDto.serializer())).isNotEmpty())
        val capture = decode("machine-reports/meter-capture-opening.json", MeterCaptureDto.serializer())
        assertEquals(900.0, capture.accuracyM!!, 0.0)
        assertNull(capture.placeName)
        val snapshot = decode("machine-reports/sync-snapshot.json", SyncData.serializer())
        assertTrue(snapshot.myMachineReports.any { it.isOpening })
        assertTrue(snapshot.machineReportStates.isNotEmpty() && snapshot.machineReportReasons.isNotEmpty())
        assertTrue(snapshot.openCreditInvoices.isNotEmpty())
    }

    @Test
    fun `credit sale, credit invoice and customer hours fixtures decode`() {
        val orders = PageDto.serializer(OwnerHoursPurchaseDto.serializer())
        val toActivate = decode("credit-sales/hours-purchases-credit-to-activate.json", orders).items.single()
        assertEquals(0, java.math.BigDecimal("450000").compareTo(java.math.BigDecimal(toActivate.creditAmount)))
        assertEquals("AWAITING_ACTIVATION", toActivate.creditStatus)
        assertEquals(listOf("CASH"), toActivate.payments.map { it.method })
        assertEquals(1, decode("credit-sales/hours-purchases-awaiting-activation.json", orders).items.size)
        val invoices = decode("credit-sales/credit-invoices.json", PageDto.serializer(CreditInvoiceDto.serializer()))
        assertEquals(CreditInvoiceDto.PART_PAID, invoices.items.single().status)
        val invoice = decode("credit-sales/credit-invoice.json", CreditInvoiceDto.serializer())
        assertEquals("MOBILE_MONEY", invoice.payments.single().method)
        assertTrue(decode("credit-sales/customer-hours.json", ListSerializer(CustomerHoursSummaryDto.serializer())).isNotEmpty())
    }

    @Test
    fun `a report's findings are the reading's findings, not inbox findings`() {
        ContractCheck.check("FindingDto", ReportFindingDto.serializer().descriptor)
    }
}
