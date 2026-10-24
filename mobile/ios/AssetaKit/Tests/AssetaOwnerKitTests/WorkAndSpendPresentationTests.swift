@testable import AssetaOwnerKit
import AssetaModel
import AssetaNetwork
import Foundation
import Testing

/// Work log, field spend, meter exceptions, cash with supervisors and meter resets. Android's
/// `WorkAndSpendPresentationTest` asserts the same strings for the same inputs; change both together.
struct WorkAndSpendPresentationTests {
    let utc = TimeZone(identifier: "UTC")!
    let decoder = AssetaJSON.decoder()
    /// Money as `<amount> <currency>` so the expectations don't depend on the test machine's locale.
    let money: (DecimalString, String) -> String = { "\($1) \($0.description)" }

    static let activity = """
    {"id":"21212121-0000-4000-8000-000000000001","client_id":"21212121-0000-4000-8000-000000000002",
     "activity_type":"WORK","started_at":"2026-10-22T08:00:00Z","ended_at":"2026-10-22T10:30:00Z","billable":true,
     "note":"Trenching"}
    """

    static func expense(status: String = "APPROVED", amount: String = "150000.0000", currency: String = "TZS",
                        supplier: String? = "Puma", note: String? = nil) -> String {
        """
        {"id":"22222222-0000-4000-8000-000000000001","client_id":null,"category_id":"22222222-0000-4000-8000-000000000002",
         "supplier":\(supplier.map { "\"\($0)\"" } ?? "null"),"description":"Diesel","amount":"\(amount)",
         "currency":"\(currency)","incurred_at":"2026-10-22T08:00:00Z","machine_id":"\(Samples.machine)",
         "job_id":"\(Samples.job)","paid_from":"CASH_CUSTODY","custodian_staff_id":null,"status":"\(status)",
         "policy_version":"v1","receipt_required":true,"gps_status":null,"latitude":null,"longitude":null,
         "gps_accuracy_m":null,"source":"MOBILE","submitted_by":null,"submitted_at":"2026-10-22T08:05:00Z",
         "decided_by":null,"decided_at":null,"decision_note":\(note.map { "\"\($0)\"" } ?? "null"),"receipt_attachment_ids":[]}
        """
    }

    static let fuel = """
    {"id":"23232323-0000-4000-8000-000000000001","client_id":null,"event_type":"PURCHASE","litres":"120.500",
     "unit_price":"3200.0000","attributed_cost":"385600.0000","currency":"TZS","machine_id":"\(Samples.machine)",
     "job_id":"\(Samples.job)","expense_id":null,"meter_reading":null,"supplier":"Puma",
     "occurred_at":"2026-10-22T09:00:00Z","note":null,"source":"MOBILE","recorded_by":null}
    """

    static func exception(status: String = "OPEN", blocking: Bool = true) -> String {
        """
        {"id":"24242424-0000-4000-8000-000000000001","job_id":"\(Samples.job)","machine_id":"\(Samples.machine)",
         "meter_capture_id":null,"exception_type":"HOURS_EXCEED_WINDOW","severity":"HIGH","blocking":\(blocking),
         "evidence":{"window_hours":"10"},"policy_version":"v2","status":"\(status)","review_note":null,
         "reviewed_at":null,"created_at":"2026-10-22T08:00:00Z"}
        """
    }

    static let reset = """
    {"id":"25252525-0000-4000-8000-000000000001","machine_id":"\(Samples.machine)","old_reading":"1250.50",
     "new_reading":"0","effective_at":"2026-10-22T08:00:00Z","reason":"Meter replaced",
     "evidence_attachment_id":null,"status":"PENDING","requested_by":null,"decided_at":null}
    """

    static func cash(name: String, closing: String, pending: String = "0.0000") -> String {
        """
        {"staff_member_id":"26262626-0000-4000-8000-00000000000\(name.count % 10)","staff_name":"\(name)",
         "currency":"TZS","period_from":"2026-10-22","period_to":"2026-10-22","opening":"10000.0000",
         "floats_issued":"50000.0000","collections":"0.0000","approved_spending":"20000.0000",
         "verified_handovers":"0.0000","closing_outstanding":"\(closing)","claimed_unverified_handovers":"0.0000",
         "pending_spending":"\(pending)","unverified_collections":"0.0000"}
        """
    }

    func decode<T: Decodable>(_ type: T.Type, _ json: String) throws -> T { try decoder.decode(T.self, from: Data(json.utf8)) }

    @Test(arguments: [
        ("ActivityDto", activity), ("ExpenseDto", expense()), ("FuelEventDto", fuel), ("ExceptionDto", exception()),
        ("ResetDto", reset), ("CashSupervisorSummaryDto", cash(name: "Neema", closing: "40000.0000")),
    ])
    func samplesMatchTheContract(_ sample: (String, String)) throws {
        #expect(try Contract.missingRequired(schema: sample.0, json: sample.1) == [])
    }

    @Test func workLogRows() throws {
        let done = try decode(ActivityDTO.self, Self.activity)
        let row = WorkLogText.row(done, timeZone: utc)
        #expect(row.title == "Work")
        #expect(row.detail == "22 Oct 2026, 08:00 – 22 Oct 2026, 10:30 · 2.5 h")
        #expect(row.pills == [TextPill(text: "Billable", tone: .good)] && row.note == "Trenching")
        let ongoing = try decode(ActivityDTO.self, Self.activity
            .replacingOccurrences(of: #""ended_at":"2026-10-22T10:30:00Z""#, with: #""ended_at":null"#)
            .replacingOccurrences(of: #""billable":true"#, with: #""billable":false"#)
            .replacingOccurrences(of: #""activity_type":"WORK""#, with: #""activity_type":"STANDBY""#))
        let now = AssetaJSON.parseInstant("2026-10-22T09:20:00Z")!
        let open = WorkLogText.row(ongoing, now: now, timeZone: utc)
        #expect(open.title == "Standby" && open.detail == "22 Oct 2026, 08:00 – ongoing · 1.33 h")
        #expect(open.pills == [TextPill(text: "Not billable", tone: .muted)])
        #expect(WorkLogText.empty == "No work logged yet.")
        #expect(WorkLogText.duration(from: now, to: now.addingTimeInterval(3600)) == "1 h")
    }

    @Test func expenseRowsTonesAndTotals() throws {
        let approved = try decode(ExpenseDTO.self, Self.expense(note: "OK"))
        let row = SpendText.expenseRow(approved, timeZone: utc, money: money)
        #expect(row.title == "Diesel" && row.detail == "Puma · 22 Oct 2026" && row.trailing == "TZS 150000")
        #expect(row.pills == [TextPill(text: "Approved", tone: .good)] && row.note == "OK")
        #expect(row.jobID == UUID(uuidString: Samples.job) && approved.receiptRequired)
        let pending = try decode(ExpenseDTO.self, Self.expense(status: "PENDING_APPROVAL", supplier: nil))
        #expect(SpendText.expenseRow(pending, timeZone: utc, money: money).detail == "22 Oct 2026")
        #expect(SpendText.expenseRow(pending, timeZone: utc, money: money).pills == [TextPill(text: "Pending approval", tone: .warning)])
        #expect(SpendText.expenseTone("REJECTED") == .critical && SpendText.expenseTone("DRAFT") == .muted)
        #expect(SpendText.expenseTone("PENDING") == .warning && SpendText.expenseTone("SUBMITTED") == .warning)
        let usd = try decode(ExpenseDTO.self, Self.expense(amount: "20.5000", currency: "USD"))
        let money: (Decimal, String) -> String = { "\($1) \($0)" }
        #expect(SpendText.totalApproved([approved, approved, pending, usd], money: money)
            == ["Total approved: TZS 300000", "Total approved: USD 20.5"])
        #expect(SpendText.totalApproved([pending], money: money).isEmpty)
        #expect(SpendText.pendingStatus == "PENDING_APPROVAL")
        #expect(SpendText.expenseFilters.map(\.1) == ["Pending", "All"] && !SpendText.defaultPendingOnly)
        #expect(SpendText.kinds.map(\.1) == ["Expenses", "Fuel"])
        #expect([SpendText.jobExpensesEmpty, SpendText.jobFuelEmpty, SpendText.expensesEmpty, SpendText.fuelEmpty]
            == ["No expenses on this job.", "No fuel recorded on this job.", "No expenses yet.", "No fuel recorded yet."])
    }

    @Test func fuelRows() throws {
        let row = SpendText.fuelRow(try decode(FuelEventDTO.self, Self.fuel), timeZone: utc, money: money)
        #expect(row.title == "Purchase · 120.5 L" && row.detail == "Puma · 22 Oct 2026" && row.trailing == "TZS 385600")
        #expect(row.pills.isEmpty && row.jobID == UUID(uuidString: Samples.job))
    }

    @Test func exceptionRowsFiltersAndEmptyText() throws {
        let open = ExceptionText.row(try decode(MeterExceptionDTO.self, Self.exception()), timeZone: utc)
        #expect(open.title == "Hours exceed window" && open.detail == "High · 22 Oct 2026, 08:00")
        #expect(open.pills == [TextPill(text: "Blocking", tone: .critical)])
        let explained = ExceptionText.row(try decode(MeterExceptionDTO.self, Self.exception(status: "EXPLAINED", blocking: false)),
                                          timeZone: utc)
        #expect(explained.pills == [TextPill(text: "Explained", tone: .good)])
        let confirmed = ExceptionText.row(try decode(MeterExceptionDTO.self, Self.exception(status: "CONFIRMED")), timeZone: utc)
        #expect(confirmed.pills == [TextPill(text: "Blocking", tone: .critical), TextPill(text: "Confirmed", tone: .critical)])
        #expect(ExceptionText.filters.map(\.1) == ["Open", "All"] && ExceptionText.defaultOpenOnly)
        #expect(ExceptionText.empty(openOnly: true) == "No open exceptions." && ExceptionText.empty(openOnly: false) == "No exceptions.")
        #expect(SnapshotKey.exceptions(openOnly: true, jobID: nil).rawValue == "exceptions:OPEN:ALL")
        #expect(JobDetailText.exceptions(2) == "2 open exception(s) need review." && JobDetailText.exceptions(0) == nil)
    }

    @Test func cashPeriodsCardsAndOrder() throws {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(identifier: "Africa/Dar_es_Salaam")!
        let now = AssetaJSON.parseInstant("2026-10-22T22:30:00Z")! // 23 Oct 01:30 in Dar es Salaam
        #expect(CashText.range(.today, now: now, calendar: calendar) == ("2026-10-23", "2026-10-23"))
        #expect(CashText.range(.week, now: now, calendar: calendar) == ("2026-10-17", "2026-10-23"))
        #expect(CashText.range(.month, now: now, calendar: calendar) == ("2026-10-01", "2026-10-23"))
        #expect(CashPeriod.allCases.map(\.label) == ["Today", "7 days", "This month"] && CashText.defaultPeriod == .today)
        let small = try decode(CashSupervisorSummaryDTO.self, Self.cash(name: "Ali", closing: "5000.0000"))
        let big = try decode(CashSupervisorSummaryDTO.self, Self.cash(name: "Neema", closing: "40000.0000", pending: "3000.0000"))
        let cards = CashText.cards([small, big], money: money)
        #expect(cards.map(\.title) == ["Neema", "Ali"] && cards[0].holding == "TZS 40000")
        #expect(cards[1].lines.map(\.label) == ["Opening", "Floats issued", "Collections", "Approved spending", "Handed over (verified)"])
        #expect(cards[0].lines.last == CashLine(label: "Spending awaiting approval", value: "TZS 3000", tone: .warning))
        #expect(CashText.empty == "No supervisor cash in this period." && CashText.holdingLabel == "Holding")
        #expect(CashText.footer == "Holding = opening + floats + collections − approved spending − verified handovers.")
    }

    @Test func meterResetTextAndDecisionRules() throws {
        let reset = try decode(MeterResetDTO.self, Self.reset)
        #expect(MeterResetText.detail(reset, timeZone: utc) == "1250.5 → 0 · effective 22 Oct 2026, 08:00")
        #expect(MeterResetText.title == "Meter reset" && MeterResetText.empty == "No meter resets waiting.")
        #expect(!MeterResetText.canDecide(note: " ok  ") && MeterResetText.canDecide(note: "Meter swapped"))
        #expect(MeterResetText.done(approve: true) == "Reset approved." && MeterResetText.done(approve: false) == "Reset rejected.")
        #expect(MeterResetText.statusTone("PENDING") == .warning && MeterResetText.statusTone("REJECTED") == .critical)
        let decided = APIError.server(status: 409, body: ErrorBody(code: "RESET_DECIDED", message: "x", correlationID: "c"))
        let own = APIError.server(status: 422, body: ErrorBody(code: "SEGREGATION_OF_DUTIES", message: "x", correlationID: "c"))
        #expect(DecisionErrorText.resetMessage(for: decided) == "This reset was already decided.")
        #expect(DecisionErrorText.resetMessage(for: own) == "You requested this reset, so someone else must decide it.")
        #expect(DecisionErrorText.needsReload(decided))
        let body = String(decoding: try AssetaJSON.encoder().encode(MeterResetDecisionIn(outcome: "EXPLAINED", note: "Swapped")),
                          as: UTF8.self)
        #expect(body.contains(#""outcome":"EXPLAINED""#) && body.contains(#""note":"Swapped""#))
    }

    @Test func routesFeaturesAndMoreOrder() {
        let all = OwnerFeatures(permissions: ["tenant.approval.read", "tenant.meter.read", "tenant.expense.read",
                                              "tenant.finance.read", "tenant.case.read", "tenant.notification.read",
                                              "tenant.meter.approve"])
        #expect(all.moreEntries == ["Approvals", "Meter exceptions", "Field spend", "Cash with supervisors", "Investigations",
                                    "Notifications", "Settings"])
        #expect(all.expenses && all.meterApprove && all.allows(.exceptions(jobID: nil)) && all.allows(.fieldSpend))
        let none = OwnerFeatures(permissions: [])
        #expect(!none.allows(.cash) && !none.allows(.meterReset(UUID())) && !none.allows(.fieldSpend))
        let id = UUID()
        #expect(DeepLinkParser.route(entity: "meter_reset", id: id.uuidString, path: nil) == .meterReset(id))
        #expect(DeepLinkParser.route(entity: "meter_reset", id: nil, path: nil) == .approvals)
        #expect(DeepLinkParser.route(entity: "exception", id: nil, path: nil) == .exceptions(jobID: nil))
        #expect(DeepLinkParser.route(path: "/tenant/meter-resets/\(id.uuidString)") == .meterReset(id))
        #expect(DeepLinkParser.route(path: "/tenant/exceptions") == .exceptions(jobID: nil))
        #expect(OwnerRoute.meterReset(id).identifiesRecord && !OwnerRoute.cash.identifiesRecord)
    }

    @Test func openExceptionsTileOpensTheExceptionsList() throws {
        let o = try decoder.decode(TenantOverviewDTO.self, from: Data(Samples.overview.utf8))
        let rows = OverviewPresentation.sections(o, cached: false).flatMap { $0.groups.flatMap(\.rows) }
        #expect(rows.first { $0.label == "Open meter exceptions" }?.route == .exceptions(jobID: nil))
    }
}
