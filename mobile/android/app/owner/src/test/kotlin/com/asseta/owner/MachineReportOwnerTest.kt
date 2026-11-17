package com.asseta.owner

import com.asseta.core.domain.owner.OwnerDestination
import com.asseta.core.model.owner.ApprovalRequestDto
import com.asseta.core.model.owner.ExpenseDto
import com.asseta.core.model.owner.MeterCaptureDto
import com.asseta.core.model.owner.OwnerHoursPurchaseDto
import com.asseta.core.model.owner.TenantOverviewDto
import com.asseta.core.model.sync.MachineReportDto
import com.asseta.core.model.sync.MachineReportStatusDto
import com.asseta.core.network.NetworkFactory
import com.asseta.core.ui.shell.PillTone
import com.asseta.owner.data.CreditSale
import com.asseta.owner.ui.OwnerFeatures
import com.asseta.owner.ui.approvals.ApprovalCounts
import com.asseta.owner.ui.approvals.ApprovalFilter
import com.asseta.owner.ui.approvals.ApprovalKind
import com.asseta.owner.ui.approvals.ApprovalsTexts
import com.asseta.owner.ui.approvals.ApprovalsViewModel
import com.asseta.owner.ui.approvals.CreditSales
import com.asseta.owner.ui.approvals.ExpenseApprovals
import com.asseta.owner.ui.approvals.approvalChips
import com.asseta.owner.ui.common.Figures
import com.asseta.owner.ui.common.Period
import com.asseta.owner.ui.common.ScreenState
import com.asseta.owner.ui.home.HomePresentation
import com.asseta.owner.ui.reports.ReportApprovalViewModel
import com.asseta.owner.ui.reports.ReportPresentation
import com.asseta.owner.ui.reports.ReportTexts
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.emptyFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.setMain
import kotlinx.coroutines.withTimeout
import kotlinx.serialization.builtins.ListSerializer
import mockwebserver3.Dispatcher
import mockwebserver3.MockResponse
import mockwebserver3.RecordedRequest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.math.BigDecimal
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset
import java.util.Collections

/** ADR-008 Owner app: approvals (machine reports, credit sales, expenses), report decisions and Home figures. */
@OptIn(ExperimentalCoroutinesApi::class)
class MachineReportOwnerTest {
    private val json = NetworkFactory.json
    private val utc = ZoneOffset.UTC
    private val me = "33333333-3333-4333-8333-333333333333"

    @Before
    fun setUp() = Dispatchers.setMain(Dispatchers.Unconfined)

    @After
    fun tearDown() = Dispatchers.resetMain()

    private fun <T> StateFlow<ScreenState<T>>.settled(): ScreenState<T> = runBlocking { withTimeout(5_000) { first { !it.loading } } }

    private fun <T> StateFlow<T>.await(predicate: (T) -> Boolean): T = runBlocking { withTimeout(5_000) { first(predicate) } }

    // --- samples ------------------------------------------------------------------------------------------------------

    fun report(
        id: String = ID1,
        status: String = "SUBMITTED",
        submittedBy: String = ID2,
        lines: String = """
            {"id":"l1","line_no":1,"kind":"CUSTOMER","customer_id":"c1","customer_name":"Pwani Road Contractors","reason_id":null,"hours":"120","note":null,"available_hours":"140"},
            {"id":"l2","line_no":2,"kind":"CUSTOMER","customer_id":"c2","customer_name":"Msasani Bay","reason_id":null,"hours":"100","note":null,"available_hours":"100"},
            {"id":"l3","line_no":3,"kind":"NON_PRODUCTIVE","customer_id":null,"reason_id":"r1","reason_code":"BREAKDOWN","reason_name":"Breakdown / repair","hours":"40","note":"Hydraulic hose replaced on site"},
            {"id":"l4","line_no":4,"kind":"NON_PRODUCTIVE","customer_id":null,"reason_id":"r2","reason_code":"TRANSIT","reason_name":"Transit between sites","hours":"25","note":"Moved"},
            {"id":"l5","line_no":5,"kind":"NON_PRODUCTIVE","customer_id":null,"reason_id":"r3","reason_code":"IDLE_ON_SITE","reason_name":"Idle on site","hours":"15","note":"Waiting"}""",
        tracker: String = """{"available":true,"tracker_hours":"296","meter_hours":"300","difference":"4"}""",
        hours: String = "300", customerHours: String = "220", npHours: String = "80",
    ) = """{"id":"$id","report_number":"MR-2026-00001","machine_id":"$ID2","machine_code":"EX-01","machine_name":"CAT 320D2",
        "capture_id":"$ID1","start_source":"REPORT","start_ref":"x","start_reading":"1210.0","start_at":"2026-11-10T07:00:00Z",
        "end_reading":"1510.0","end_at":"2026-11-17T07:40:00Z","hours":"$hours","customer_hours":"$customerHours","non_productive_hours":"$npHours",
        "status":"$status","corrects_id":null,"note":"Busy week","source":"API","submitted_by":"$submittedBy","submitted_by_name":"Daudi Mollel",
        "submitted_at":"2026-11-17T07:40:00Z","client_created_at":null,"decided_by":null,"decided_at":null,"decision_note":null,
        "policy_version":"p","tracker":$tracker,"lines":[$lines]}"""

    private fun dto(s: String = report()) = json.decodeFromString(MachineReportDto.serializer(), s)

    private fun purchase(createdBy: String = ID2, credit: String? = "3800000", awaiting: String = "40", creditStatus: String = "AWAITING_ACTIVATION") = """{"id":"$ID1","purchase_number":"HP-1",
        "customer_id":"$ID2","customer_name":"Msasani Bay","machine_id":"$ID2","hours":"40","status":"AWAITING_PAYMENT",
        "created_at":"2026-11-16T15:20:00Z","cancelled_at":null,"currency":"TZS","amount":"3800000","effective_rate":"95000",
        "created_by":"$createdBy","payments":[],"credit_amount":${credit?.let { "\"$it\"" } ?: "null"},
        "credit_invoice":{"id":"$ID2","invoice_number":"INV-0042","amount":"3800000","paid":"0","balance":"3800000","due_date":"2026-11-30","status":"UNPAID","overdue":false},
        "credit_status":"$creditStatus",
        "totals":{"purchased":"40","activated":"0","consumed":"0","remaining":"0","awaiting_activation":"$awaiting"}}"""

    private fun order(s: String = purchase()) = json.decodeFromString(OwnerHoursPurchaseDto.serializer(), s)

    // --- approvals: chips and counts --------------------------------------------------------------------------------

    @Test
    fun `chips show the kinds with their counts and All shows everything`() {
        val c = ApprovalCounts(reports = 2, credit = 1, expenses = 2, other = 0)
        assertEquals(listOf("All 5", "Machine reports 2", "Credit 1", "Expenses 2"), ApprovalFilter.entries.map { c.chip(it) })
        assertEquals("5 waiting", c.waiting)
        assertNull(ApprovalCounts().waiting)
        assertEquals(8, c.copy(other = 3).all)
        assertTrue(ApprovalKind.entries.all { ApprovalFilter.ALL.shows(it) })
        assertTrue(ApprovalFilter.MACHINE_REPORTS.shows(ApprovalKind.MACHINE_REPORT))
        assertFalse(ApprovalFilter.MACHINE_REPORTS.shows(ApprovalKind.CREDIT))
        assertFalse(ApprovalFilter.CREDIT.shows(ApprovalKind.OTHER))
        assertFalse(ApprovalFilter.EXPENSES.shows(ApprovalKind.OTHER))
        assertTrue(ApprovalFilter.EXPENSES.shows(ApprovalKind.EXPENSE))
    }

    @Test
    fun `the approvals list counts reports, credit sales and expenses (shared by the menu badge and Home)`() {
        val h = OwnerHarness()
        try {
            h.route(
                "/machine-reports" to Samples.page(report(ID1), report(ID2)),
                "/hours-purchases" to Samples.page(purchase()),
                "/credit-exposure" to """{"customer_id":"$ID2","currency":"TZS","arrangement_id":null,"limit_amount":"10000000","exposure":"3800000","available":"6200000"}""",
                "/approvals" to Samples.page(Samples.approval(ID1), Samples.approval(ID2)),
            )
            val vm = ApprovalsViewModel(h.data, emptyFlow(), expenseRequests = true, machineReports = true, creditSales = true)
            vm.reports!!.state.settled()
            vm.credit!!.state.settled()
            vm.expenses!!.state.settled()
            val counts = vm.counts.await { it.all == 5 }
            assertEquals(ApprovalCounts(reports = 2, credit = 1, expenses = 2), counts)
            assertEquals(listOf(ApprovalFilter.ALL, ApprovalFilter.MACHINE_REPORTS, ApprovalFilter.CREDIT, ApprovalFilter.EXPENSES), approvalChips(vm))
            assertEquals("6200000", vm.credit!!.state.value.data!!.single().limitLeft)
            // A role without these kinds gets only All, and nothing is loaded for them.
            val bare = ApprovalsViewModel(h.data, emptyFlow(), expenseRequests = false)
            assertNull(bare.reports)
            assertNull(bare.credit)
            assertEquals(listOf(ApprovalFilter.ALL), approvalChips(bare))
        } finally {
            h.close()
        }
    }

    @Test
    fun `approvals screen opens for machine report readers and credit approvers`() {
        assertTrue(OwnerFeatures(setOf("tenant.machine_report.read")).approvalsScreen)
        // Reading machine reports: read OR approve (same as iOS).
        assertTrue(OwnerFeatures(setOf("tenant.machine_report.approve")).machineReports)
        assertTrue(OwnerFeatures(setOf("tenant.machine_report.approve")).approvalsScreen)
        assertFalse(OwnerFeatures(setOf("tenant.hours.read")).machineReports)
        assertTrue(OwnerFeatures(setOf("tenant.hours.read", "tenant.hours.credit_activate")).approvalsScreen)
        assertFalse(OwnerFeatures(setOf("tenant.hours.credit_activate")).creditSales)
        assertFalse(OwnerFeatures(setOf("tenant.hours.read", "tenant.hours.credit_activate"), setOf(com.asseta.core.model.TenantAccess.CUSTOMER_HOURS)).creditSales)
    }

    // --- rows -------------------------------------------------------------------------------------------------------

    @Test
    fun `machine report rows read as the design`() {
        val r = dto()
        assertEquals("EX-01 · 300 h · Daudi Mollel", ReportPresentation.rowTitle(r))
        assertEquals("220 h to 2 customers · 80 h non-productive", ReportPresentation.split(r))
        val single = dto(
            report(
                hours = "42", customerHours = "38", npHours = "4",
                lines = """{"id":"a","line_no":1,"kind":"CUSTOMER","customer_id":"c","customer_name":"Mji Mpya Housing","reason_id":null,"hours":"38","note":null},
                    {"id":"b","line_no":2,"kind":"NON_PRODUCTIVE","customer_id":null,"reason_id":"r","reason_code":"TRANSIT","hours":"4","note":"x"}""",
            ),
        )
        assertEquals("38 h Mji Mpya Housing · 4 h transit", ReportPresentation.split(single))
        // A list row without lines falls back to the totals.
        assertEquals("220 h to customers · 80 h non-productive", ReportPresentation.split(r.copy(lines = emptyList())))
        assertEquals("1,210 → 1,510 h", ReportPresentation.readings(r))
        assertEquals("· 140 → 20 h left", ReportPresentation.beforeAfter(r.lines[0]))
        assertEquals("· 100 → 0 h left", ReportPresentation.beforeAfter(r.lines[1]))
        assertEquals("“Hydraulic hose replaced on site”", ReportPresentation.quoted(r.lines[2].note))
        assertEquals("Tracker engine hours for the same period: 296 h (meter 300 h).", ReportPresentation.tracker(r.tracker, r))
        assertEquals(ReportTexts.NO_TRACKER, ReportPresentation.tracker(null, r))
        assertEquals(ReportTexts.NO_TRACKER, ReportPresentation.tracker(r.tracker!!.copy(available = false), r))
    }

    @Test
    fun `reading line shows the phone's OCR and the GPS fix`() {
        val r = dto()
        val capture = json.decodeFromString(
            MeterCaptureDto.serializer(),
            """{"id":"$ID1","machine_id":"$ID2","kind":"DAILY","reading":"1510.0","capture_mode":"AUTOMATIC","captured_at":"2026-11-17T07:40:00Z",
            "received_at":"2026-11-17T07:41:00Z","gps_status":"FIX","state":"ACCEPTED","manually_corrected":false,"policy_version":"p",
            "ocr_value":"1510.0","latitude":-6.8,"longitude":39.28,"accuracy_m":6.2}""",
        )
        assertEquals("300 h · read by phone 1510.0 ✓", ReportPresentation.readLine(r, capture))
        assertEquals("GPS: ±6 m", ReportPresentation.gpsLine(capture))
        assertEquals("300 h", ReportPresentation.readLine(r, null))
        assertNull(ReportPresentation.gpsLine(null))
        assertEquals("GPS: no fix", ReportPresentation.gpsLine(capture.copy(latitude = null, gpsStatus = "NO_FIX")))
    }

    @Test
    fun `credit sale rows, hours and who may approve`() {
        val p = order()
        assertTrue(CreditSales.waiting(p))
        assertFalse(CreditSales.waiting(order(purchase(credit = null))))
        assertFalse(CreditSales.waiting(order(purchase(awaiting = "0"))))
        assertEquals(0, BigDecimal("40").compareTo(CreditSales.creditHours(p)))
        // Never more than the hours still waiting.
        assertEquals(0, BigDecimal("12").compareTo(CreditSales.creditHours(order(purchase(awaiting = "12")))))
        assertEquals("Msasani Bay · 40 h on credit", CreditSales.title(p))
        assertEquals("Invoice INV-0042 · TZS 3,800,000 · limit left 6.2M", CreditSales.detail(CreditSale(p, "6200000")))
        assertEquals("Invoice INV-0042 · TZS 3,800,000", CreditSales.detail(CreditSale(p, null)))
        assertTrue(CreditSales.recordedBy(order(purchase(createdBy = me)), me))
        assertFalse(CreditSales.recordedBy(p, me))
        // Approve credit makes every waiting hour usable, with the fixed reason (as iOS).
        assertEquals(0, BigDecimal("12").compareTo(CreditSales.awaitingHours(order(purchase(awaiting = "12")))))
        assertEquals("Credit approved in the Owner app", ApprovalsTexts.CREDIT_APPROVED_REASON)
        // A rejected credit no longer waits.
        assertFalse(CreditSales.waiting(order(purchase(creditStatus = "REJECTED"))))
    }

    @Test
    fun `reject credit needs a reason, posts it and explains refusals`() {
        val h = OwnerHarness()
        val posts = Collections.synchronizedList(mutableListOf<Pair<String, String>>())
        val refusal = java.util.concurrent.atomic.AtomicReference<String?>(null)
        h.server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.url.encodedPath
                if (request.method == "POST") {
                    posts += path to request.body!!.utf8()
                    refusal.get()?.let { code ->
                        return MockResponse.Builder().code(422).body("""{"error":{"code":"$code","message":"refused","correlation_id":"c"}}""").build()
                    }
                    return MockResponse.Builder().code(200).body(purchase(creditStatus = "REJECTED")).build()
                }
                return when {
                    path.endsWith("/hours-purchases") -> MockResponse.Builder().code(200).body(Samples.page(purchase())).build()
                    path.endsWith("/credit-exposure") -> MockResponse.Builder().code(404).build()
                    else -> MockResponse.Builder().code(404).build()
                }
            }
        }
        try {
            val vm = ApprovalsViewModel(h.data, emptyFlow(), expenseRequests = false, creditSales = true)
            val sale = vm.credit!!.state.settled().data!!.single()
            assertFalse(ApprovalsTexts.rejectReasonValid("  no "))
            assertTrue(ApprovalsTexts.rejectReasonValid(" Owes "))
            vm.rejectCredit(sale, "  ")
            assertTrue(posts.isEmpty())
            refusal.set("CREDIT_INVOICE_HAS_PAYMENTS")
            vm.rejectCredit(sale, "Customer already owes too much")
            assertEquals(ApprovalsTexts.creditRejectRefusal("CREDIT_INVOICE_HAS_PAYMENTS", "x"), vm.creditError.await { it != null }!!.message)
            assertEquals("/api/v1/tenant/hours-purchases/$ID1/credit/reject", posts[0].first)
            vm.creditBusy.await { it == null }
            refusal.set(null)
            vm.rejectCredit(sale, "Customer already owes too much")
            assertEquals(ApprovalsTexts.CREDIT_REJECTED, vm.message.await { it != null })
            assertTrue(posts[1].second.contains("\"reason\":\"Customer already owes too much\""))
        } finally {
            h.close()
        }
        assertTrue(ApprovalsTexts.creditRejectRefusal("SEGREGATION_OF_DUTIES", "x").startsWith("You recorded this sale"))
        assertTrue(ApprovalsTexts.creditRejectRefusal("CREDIT_NOT_AWAITING", "x").startsWith("This credit is no longer waiting"))
        assertTrue(ApprovalsTexts.creditRejectReloads("CREDIT_NOT_AWAITING"))
        assertEquals("server words", ApprovalsTexts.creditRejectRefusal("SOMETHING_ELSE", "server words"))
    }

    @Test
    fun `expense rows say what was bought and whether a receipt is attached`() {
        val a = json.decodeFromString(ApprovalRequestDto.serializer(), Samples.approval())
        val e = json.decodeFromString(ExpenseDto.serializer(), Samples.expense(ID2, supplier = "Tabata Hydraulics").replace("Tyre repair", "Hydraulic hose"))
            .copy(receiptAttachmentIds = listOf(java.util.UUID.fromString(ID1)))
        assertEquals("Hydraulic hose · TZS 150,000", ExpenseApprovals.title(a, e))
        assertEquals("receipt photo · Tabata Hydraulics · Fuel above limit", ExpenseApprovals.detail(a, e))
        assertEquals("Fuel above limit · TZS 150,000", ExpenseApprovals.title(a, null))
    }

    // --- report decisions: by permission, never your own, a reason to reject ------------------------------------------

    @Test
    fun `only an approver who did not submit the report may decide it`() {
        val r = dto()
        val approver = setOf("tenant.machine_report.approve", "tenant.machine_report.read")
        assertNull(ReportPresentation.cannotDecide(approver, r, me))
        assertEquals(ReportTexts.OWN_REPORT, ReportPresentation.cannotDecide(approver, r, ID2))
        assertEquals(ReportTexts.NO_PERMISSION, ReportPresentation.cannotDecide(setOf("tenant.machine_report.read"), r, me))
    }

    /** A real OPENING report from the server (contracts/fixtures, backend test_contract_fixtures.py). */
    private fun fixture(name: String): String =
        java.io.File(System.getProperty("asseta.contracts.dir") ?: error("asseta.contracts.dir not set"), "fixtures/machine-reports/$name").readText()

    @Test
    fun `an opening report from the server opens, reads as the first reading and is approved`() {
        val opening = fixture("report-opening-submitted.json")
        val capture = fixture("meter-capture-opening.json")
        val h = OwnerHarness()
        h.server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.url.encodedPath
                return when {
                    request.method == "POST" && path.endsWith("/approve") ->
                        MockResponse.Builder().code(200).body(opening.replace("\"status\": \"SUBMITTED\"", "\"status\": \"APPROVED\"")).build()
                    path.contains("/machine-reports/") -> MockResponse.Builder().code(200).body(opening).build()
                    path.contains("/meter-captures/") -> MockResponse.Builder().code(200).body(capture).build()
                    else -> MockResponse.Builder().code(404).build()
                }
            }
        }
        try {
            val id = json.decodeFromString(MachineReportDto.serializer(), opening).id
            val vm = ReportApprovalViewModel(h.data, id, reading = true, refreshOn = emptyFlow())
            val state = vm.state.settled()
            assertNull(state.error)
            val detail = state.data!!
            val r = detail.report
            assertTrue(r.isOpening)
            assertEquals("GPS_INACCURATE", r.findings.single().type)
            assertEquals("1,520.4 h", ReportPresentation.readings(r))
            assertEquals("First reading — starting point · typed by hand", ReportPresentation.readLine(r, detail.capture))
            assertEquals("GPS: ±900 m", ReportPresentation.gpsLine(detail.capture))
            assertEquals(ReportTexts.OPENING_NOTE, ReportPresentation.tracker(r.tracker, r))
            assertEquals(ReportTexts.FIRST_READING, ReportPresentation.split(r))
            assertEquals("OPEN-000 · sup-FIX-1", ReportPresentation.rowTitle(r))
            assertEquals("OPEN-000 first reading · 1,520.4 h", ReportPresentation.attentionTitle(r))
            vm.decide(approve = true, reason = "")
            assertEquals(ReportTexts.OPENING_APPROVED, vm.message.await { it != null })
            assertEquals("APPROVED", vm.state.value.data!!.report.status)
        } finally {
            h.close()
        }
    }

    @Test
    fun `reject needs a reason, approve posts, refusals read as plain sentences`() {
        val h = OwnerHarness()
        val posts = Collections.synchronizedList(mutableListOf<Pair<String, String>>())
        val refusal = java.util.concurrent.atomic.AtomicReference<String?>(null)
        h.server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                val path = request.url.encodedPath
                if (request.method == "POST") {
                    posts += path to request.body!!.utf8()
                    refusal.get()?.let { code ->
                        return MockResponse.Builder().code(422).body("""{"error":{"code":"$code","message":"refused","correlation_id":"c"}}""").build()
                    }
                    return MockResponse.Builder().code(200).body(report(status = if (path.endsWith("/approve")) "APPROVED" else "REJECTED")).build()
                }
                return if (path.endsWith("/machine-reports/$ID1")) MockResponse.Builder().code(200).body(report()).build() else MockResponse.Builder().code(404).build()
            }
        }
        try {
            val vm = ReportApprovalViewModel(h.data, ID1, reading = false, refreshOn = emptyFlow())
            assertEquals("SUBMITTED", vm.state.settled().data!!.report.status)
            vm.decide(approve = false, reason = "   ")
            assertTrue(posts.isEmpty())
            refusal.set("SEGREGATION_OF_DUTIES")
            vm.decide(approve = true, reason = "")
            assertEquals(ReportTexts.refusal("SEGREGATION_OF_DUTIES", "x"), vm.error.await { it != null })
            assertEquals("/api/v1/tenant/machine-reports/$ID1/approve", posts[0].first)
            vm.busy.await { !it }
            refusal.set(null)
            vm.decide(approve = false, reason = "Idle hours too high, explain")
            assertEquals(ReportTexts.REJECTED, vm.message.await { it != null })
            assertEquals("/api/v1/tenant/machine-reports/$ID1/reject", posts[1].first)
            assertTrue(posts[1].second.contains("\"reason\":\"Idle hours too high, explain\""))
            assertEquals("REJECTED", vm.state.value.data!!.report.status)
        } finally {
            h.close()
        }
        assertTrue(ReportTexts.refusal("REPORT_READINGS_CHANGED", "x").startsWith("The machine's previous reading changed"))
        assertTrue(ReportTexts.refusal("HOURS_NOT_AVAILABLE", "x").startsWith("A customer no longer has these hours"))
        assertTrue(ReportTexts.refusal("REPORT_NOT_PENDING", "x").startsWith("This report was already decided"))
        assertEquals("server words", ReportTexts.refusal("SOMETHING_ELSE", "server words"))
    }

    // --- Home ---------------------------------------------------------------------------------------------------------

    @Test
    fun `home figures and attention rows`() {
        val reports = listOf(dto(), dto(report(ID2, status = "REJECTED", hours = "100", customerHours = "0", npHours = "100")))
        assertEquals("73%", HomePresentation.productive(reports))
        assertEquals("—", HomePresentation.productive(null))
        assertEquals("—", HomePresentation.productive(emptyList()))
        assertEquals("92 h", HomePresentation.hoursSold(listOf(order(purchase()).copy(hours = "52"), order(purchase()))))
        val overview = json.decodeFromString(
            TenantOverviewDto.serializer(),
            """{"tenant_id":"$TENANT","as_of":"2026-11-17T08:00:00Z","timezone":"UTC","money":{"month_start":"2026-11-01","currencies":[{"currency":"TZS",
            "receivables_outstanding":"0","receivables_overdue":"0","overdue_invoices":0,"verified_receipts_mtd":"0","approved_expenses_mtd":"0",
            "cash_with_supervisors":"5200000"}]}}""",
        )
        assertEquals("5.2M", HomePresentation.cash(overview))
        val all = OwnerFeatures(setOf("tenant.finance.read", "tenant.hours.read", "tenant.machine_report.read"))
        assertEquals(listOf("Cash with supervisors", "Hours sold this week", "Productive"), HomePresentation.figures(overview, null, null, all).map { it.label })
        assertEquals(listOf("Productive"), HomePresentation.figures(null, null, null, OwnerFeatures(setOf("tenant.machine_report.read"))).map { it.label })

        val statuses = json.decodeFromString(
            ListSerializer(MachineReportStatusDto.serializer()),
            """[{"machine_id":"m2","machine_code":"EX-02","previous_reading":"812.5","days_since_report":3,"last_approved_reading":"812.5"},
                {"machine_id":"m3","machine_code":"WL-01","previous_reading":"40","days_since_report":1},
                {"machine_id":"m4","machine_code":"TP-01","previous_reading":"7","days_since_report":9,"pending_report_id":"x"}]""",
        )
        val now = Instant.parse("2026-11-17T12:00:00Z").toEpochMilli()
        val items = HomePresentation.attention(listOf(dto()), statuses, 3, now, utc)
        assertEquals(listOf("EX-01 report · 80 h non-productive", "EX-02 · no report for 3 days"), items.map { it.title })
        assertEquals("Daudi Mollel · today 07:40", items[0].detail)
        assertEquals(ReportTexts.REVIEW to PillTone.WAITING, items[0].pill to items[0].tone)
        assertEquals(OwnerDestination.MachineReport(ID1), items[0].open)
        assertEquals(ReportTexts.OVERDUE to PillTone.BAD, items[1].pill to items[1].tone)
        assertEquals("Last approved reading 812.5 h", items[1].detail)
        assertEquals(OwnerDestination.Machine("m2"), items[1].open)
        // The company's reminder days (null = off); never reported, no starting reading and rejected always show.
        assertEquals(listOf("EX-01 report · 80 h non-productive"), HomePresentation.attention(listOf(dto()), statuses, null, now, utc).map { it.title })
        assertEquals(listOf("EX-02 · no report for 3 days", "WL-01 · no report for 1 day"), HomePresentation.attention(null, statuses, 1, now, utc).map { it.title })
        val more = json.decodeFromString(
            ListSerializer(MachineReportStatusDto.serializer()),
            """[{"machine_id":"n1","machine_code":"NV-01","previous_reading":"10"},
                {"machine_id":"n2","machine_code":"OP-01"},
                {"machine_id":"n3","machine_code":"RJ-01","previous_reading":"10","days_since_report":1,"rejected_report_id":"r9"},
                {"machine_id":"n4","machine_code":"PD-01","previous_reading":"10","rejected_report_id":"r8","pending_report_id":"r10"}]""",
        )
        assertEquals(
            setOf("NV-01 · no report yet", "OP-01 · no report yet", "RJ-01 · report rejected, not yet redone"),
            HomePresentation.attention(null, more, null, now, utc).map { it.title }.toSet(),
        )
        assertEquals(3, ReportPresentation.reminderDays(null))
        assertNull(ReportPresentation.reminderDays(com.asseta.owner.data.ReportReminder(null)))
        assertEquals(5, ReportPresentation.reminderDays(com.asseta.owner.data.ReportReminder(5)))
    }

    @Test
    fun `figures read as the designs`() {
        assertEquals("5.2M", Figures.compact(BigDecimal("5200000")))
        assertEquals("3.85M", Figures.compact(BigDecimal("3850000")))
        assertEquals("2.0M", Figures.compact(BigDecimal("2000000")))
        assertEquals("850,000", Figures.compact(BigDecimal("850000")))
        assertEquals("1.2B", Figures.compact(BigDecimal("1200000000")))
        assertEquals("TZS 12,600,000", Figures.money(BigDecimal("12600000.0000"), "TZS"))
        assertEquals("300 h", Figures.hours(BigDecimal("300.0")))
        assertEquals("73%", Figures.percent(BigDecimal("220"), BigDecimal("300")))
        assertNull(Figures.percent(BigDecimal.ONE, BigDecimal.ZERO))
        val now = Instant.parse("2026-11-17T12:00:00Z").toEpochMilli()
        assertEquals("today 07:40", Figures.relative("2026-11-17T07:40:00Z", now, utc))
        assertEquals("yesterday 18:10", Figures.relative("2026-11-16T18:10:00Z", now, utc))
        assertEquals("2 days ago", Figures.relative("2026-11-15T09:00:00Z", now, utc))
        assertEquals("1 Nov", Figures.relative("2026-11-01T09:00:00Z", now, utc))
        assertEquals("30 Nov", Figures.day("2026-11-30"))
        val tuesday = LocalDate.parse("2026-11-17")
        assertEquals(LocalDate.parse("2026-11-16"), Period.WEEK.range(tuesday).from)
        assertEquals(LocalDate.parse("2026-11-01"), Period.MONTH.range(tuesday).from)
        assertEquals(tuesday, Period.TODAY.range(tuesday).from)
    }

    @Test
    fun `fuel follows the switch in me`() {
        assertTrue(OwnerFeatures(emptySet()).fuel)
        assertFalse(OwnerFeatures(emptySet(), setOf(com.asseta.core.model.TenantAccess.FUEL)).fuel)
    }
}
