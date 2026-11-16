import AssetaModel
@testable import AssetaStore
@testable import AssetaSync
import Foundation
import Testing

/// Supervisor side menu, Home, Sell hours, Money, credit invoice payment and Dashboard: the same rules and wording as
/// Android (`ShellModel`, `HomeTexts`, `ReportTexts`, `AccountabilityRules`, `InvoicePaymentMessages`).
@Suite("Supervisor shell parity with Android")
struct SupervisorShellParityTests {
    static let tenant = UUID()
    static let machine = UUID(uuidString: "aaaaaaaa-0000-4000-8000-0000000000c1")!
    static let pwani = UUID(uuidString: "aaaaaaaa-0000-4000-8000-0000000000a1")!

    static var utc: Calendar {
        var c = Calendar(identifier: .gregorian)
        c.timeZone = TimeZone(identifier: "UTC")!
        return c
    }

    static func date(_ text: String) -> Date { ISO8601DateFormatter().date(from: text)! }

    static func op(_ type: OperationType, _ payload: String, status: ClientOperationStatus, at: Date = Date(),
                   errorCode: String? = nil) -> ClientOperation {
        ClientOperation(id: UUID(), tenantID: tenant, opType: type.rawValue, entityType: "x", entityID: UUID(), payloadJSON: payload,
                        dependencies: [], createdAtDevice: at, status: status, attemptCount: 0, lastError: nil, errorCode: errorCode,
                        serverRevision: nil, serverResultJSON: nil, nextAttemptAt: nil)
    }

    @Test func compactMoneyAndFigures() {
        #expect(SupervisorFigures.compact(850_000) == "850,000")
        #expect(SupervisorFigures.compact(3_845_000) == "3.85M")
        #expect(SupervisorFigures.compact(2_000_000) == "2.0M")
        #expect(SupervisorFigures.compact(1_200_000_000) == "1.2B")
        #expect(SupervisorFigures.compact(950) == "950")
        #expect(SupervisorFigures.grouped(3_845_000) == "3,845,000")
        #expect(SupervisorFigures.grouped(Decimal(string: "12.5")!) == "12.5")
        #expect(SupervisorFigures.money(1_900_000, currency: "TZS") == "TZS 1,900,000")
        #expect(SupervisorFigures.money(5, currency: nil) == "5")
        #expect(SupervisorFigures.badge(0) == nil && SupervisorFigures.badge(7) == "7" && SupervisorFigures.badge(120) == "99+")
    }

    @Test func timesAreEnglishAndTwentyFourHour() {
        let now = Self.date("2026-11-17T12:00:00Z")
        let c = Self.utc
        #expect(SupervisorFigures.when(Self.date("2026-11-17T07:40:00Z"), now: now, calendar: c) == "Today 07:40")
        #expect(SupervisorFigures.when(Self.date("2026-11-16T16:05:00Z"), now: now, calendar: c) == "Yesterday 16:05")
        #expect(SupervisorFigures.when(Self.date("2026-11-12T17:30:00Z"), now: now, calendar: c) == "12 Nov 17:30")
        #expect(SupervisorFigures.ago(Self.date("2026-11-17T07:40:00Z"), now: now, calendar: c) == "today 07:40")
        #expect(SupervisorFigures.ago(Self.date("2026-11-16T07:40:00Z"), now: now, calendar: c) == "yesterday")
        #expect(SupervisorFigures.ago(Self.date("2026-11-14T07:40:00Z"), now: now, calendar: c) == "3 days ago")
    }

    @Test func weekStartsOnMonday() {
        var sunday = Self.utc
        sunday.firstWeekday = 1
        // Wednesday 18 Nov 2026: the week began on Monday 16 Nov even where weeks start on Sunday.
        let start = ActivityPeriod.week.start(now: Self.date("2026-11-18T10:00:00Z"), calendar: sunday)
        #expect(start == Self.date("2026-11-16T00:00:00Z"))
    }

    @Test func homeWording() {
        #expect(MachineReportTexts.greeting("Daudi Mollel", hour: 8) == "Good morning, Daudi")
        #expect(MachineReportTexts.greeting("daudi@example.com", hour: 14) == "Good afternoon")
        #expect(MachineReportTexts.greeting("", hour: 20) == "Good evening")
        #expect(MachineReportTexts.machinesCount(0) == "None")
        #expect(MachineReportTexts.machinesCount(1) == "1 machine")
        #expect(SupervisorShellTexts.menuSyncAllSent == "Sync · all sent")
    }

    @Test func recentRows() {
        let sale = #"{"customer_id":"\#(Self.pwani.uuidString.lowercased())","hours":"20","payments":[{"method":"CASH","amount":"1000000"},{"method":"CREDIT","amount":"900000"}]}"#
        let cashOnly = #"{"walk_in":{"name":"Asha"},"hours":"2","payments":[{"method":"CASH","amount":"190000"}]}"#
        let unpaid = #"{"walk_in":{"name":"Juma"},"hours":"1","payments":[]}"#
        let report = #"{"machine_id":"\#(Self.machine.uuidString.lowercased())","capture_id":"\#(UUID().uuidString.lowercased())","lines":[{"kind":"CUSTOMER","customer_id":"\#(Self.pwani.uuidString.lowercased())","hours":"120"}]}"#
        let opening = #"{"machine_id":"\#(Self.machine.uuidString.lowercased())","capture_id":"\#(UUID().uuidString.lowercased())","lines":[],"opening":true}"#
        let base = Date()
        let ops = [
            Self.op(.hoursPurchase, sale, status: .acked, at: base),
            Self.op(.hoursPurchase, cashOnly, status: .acked, at: base.addingTimeInterval(-10)),
            Self.op(.hoursPurchase, unpaid, status: .acked, at: base.addingTimeInterval(-20)),
            Self.op(.hoursPurchase, cashOnly, status: .pending, at: base.addingTimeInterval(-30)),
            Self.op(.hoursPurchase, cashOnly, status: .failed, at: base.addingTimeInterval(-40)),
            Self.op(.machineReport, report, status: .sent, at: base.addingTimeInterval(-50)),
            Self.op(.machineReport, opening, status: .conflict, at: base.addingTimeInterval(-60), errorCode: "INVOICE_PAID"),
        ]
        let sales = FieldActivity.saleRows(ops, customerName: { $0 == Self.pwani ? "Pwani Road" : nil },
                                           money: { SupervisorFigures.money($0, currency: "TZS") })
        #expect(sales.map(\.pill) == ["Credit", "Paid", "Not paid", "Waiting to sync", "Not synced"])
        #expect(sales[0].title == "Sold 20 h · Pwani Road" && sales[0].detail == "TZS 1,900,000")
        #expect(sales[2].detail == nil)
        let reports = FieldActivity.reportRows(reports: [], operations: ops, machineCode: { _ in "EX-01" })
        #expect(reports.map(\.title) == ["EX-01 report · 120 h", "EX-01 report"])
        #expect(reports.map(\.pill) == ["Waiting to sync", "Not synced"])
        #expect(reports[1].extra == "This invoice is already paid. The payment is kept for review.")
        let recent = FieldActivity.recent(reports: [], operations: ops, machineCode: { _ in "EX-01" }, customerName: { _ in nil },
                                          money: { "\($0)" })
        #expect(recent.count == 4)
    }

    @Test func serverReportRows() {
        let rejected = MachineReportDTO(id: UUID(), reportNumber: "MR-2", machineID: Self.machine, machineCode: "EX-01", startReading: 1210,
                                        startAt: Date(), endReading: 1510, endAt: Date(), status: .rejected, submittedAt: Date(),
                                        lines: [.init(lineNo: 1, kind: .customer, customerID: Self.pwani, hours: 300)])
        let rows = FieldActivity.reportRows(reports: [rejected], operations: [], machineCode: { _ in nil })
        #expect(rows.first?.pill == "Rejected" && rows.first?.title == "EX-01 report · 300 h")
        #expect(rows.first?.extra?.hasPrefix("1210 → 1510 h") == true && rows.first?.machineID == Self.machine)
        #expect(SupervisorShellTexts.reportStatus("SUBMITTED") == "Awaiting approval")
    }

    @Test func dashboardFigures() {
        let sale = #"{"hours":"20","payments":[{"method":"CASH","amount":"1000000"},{"method":"CREDIT","amount":"900000"}]}"#
        let payment = #"{"invoice_id":"\#(UUID().uuidString.lowercased())","amount":"500000","method":"CASH"}"#
        let ops = [Self.op(.hoursPurchase, sale, status: .acked), Self.op(.creditInvoicePayment, payment, status: .pending),
                   Self.op(.hoursPurchase, sale, status: .failed)]
        let sold = FieldActivity.hoursSold(ops, since: .distantPast)
        #expect(sold.hours == 20 && sold.amount == 1_900_000)
        let byMethod = FieldActivity.salesByMethod(ops, since: .distantPast)
        #expect(byMethod.cash == 1_500_000 && byMethod.credit == 900_000 && byMethod.total - byMethod.credit == 1_500_000)
        #expect(FieldActivity.productivePercent(customers: 0, nonProductive: 0) == nil)
        #expect(SupervisorShellTexts.productive("0", nil) == "Productive 0 h")
        #expect(SupervisorShellTexts.productive("220", 73) == "Productive 220 h (73%)")
        #expect(SupervisorShellTexts.lastReading("1,510", "yesterday") == "Last reading 1,510 h · yesterday")
        #expect(SupervisorShellTexts.lastReading(nil, nil) == "No reading yet")
        let balances = FieldActivity.customerBalances([
            AvailableHoursDTO(customerID: Self.pwani, customerName: "pwani Road", machineID: Self.machine, remaining: 10, available: 10),
            AvailableHoursDTO(customerID: Self.pwani, customerName: nil, machineID: UUID(), remaining: 5, available: Decimal(string: "2.5")!),
            AvailableHoursDTO(customerID: UUID(), customerName: "Msasani", remaining: 4, available: 4),
        ])
        #expect(balances.map(\.name) == ["Msasani", "pwani Road"] && balances[1].hours == Decimal(string: "12.5")!)
        #expect(SupervisorShellTexts.hoursUsable("12.5") == "12.5 h usable")
    }

    @Test func sellHoursWording() {
        var d = HoursSaleDraft()
        d.customerID = Self.pwani
        d.machineID = UUID()
        d.hoursText = "20"
        d.payments = [PaymentLine(method: "CASH", amountText: "1000000"), PaymentLine(method: "CREDIT", amountText: "900000")]
        #expect(AccountabilityRules.hoursSaleBlockers(d, walkInAllowed: true, creditAllowed: false) == "To save: change payment 2 to cash.")
        d.payments.append(PaymentLine(method: "CREDIT", amountText: "1"))
        #expect(AccountabilityRules.hoursSaleBlockers(d, walkInAllowed: true, creditAllowed: true)?.contains("keep one credit part") == true)
        #expect(MachineReportTexts.saleRate("20", "95,000") == "20 h × 95,000 · rate card")
        #expect(MachineReportTexts.saleRate("20", "95,000", discount: "10") == "20 h × 95,000 · rate card less 10%")
        #expect(MachineReportTexts.saleLineTitle("BANK") == "Paid by bank")
        #expect(MachineReportTexts.saleLineTitle("MOBILE_MONEY") == "Paid by mobile money")
        #expect(MachineReportTexts.saleBalance("270,000") == "Part paid · balance 270,000")
        #expect(MachineReportTexts.saleErrCreditOff == "Credit sales are recorded by the office.")
        #expect(FieldAccountabilityTexts.conflictText("CREDIT_SALES_NOT_ALLOWED")
            == "Your company records credit sales at the office. The sale is kept for review.")
        #expect(FieldAccountabilityTexts.conflictText("PAYMENTS_EXCEED_TOTAL")
            == "The payments add up to more than the sale. The sale is kept for review.")
    }

    @Test func invoicePaymentWording() {
        #expect(SupervisorShellTexts.invoiceOption("CI-2026-00042", "Msasani") == "CI-2026-00042 · Msasani")
        #expect(SupervisorShellTexts.invoiceOwes("2,000,000", "2026-11-30") == "owes 2,000,000 · due 2026-11-30")
        #expect(SupervisorShellTexts.invoiceOwes("5", nil) == "owes 5")
        guard case let .failure(none) = CreditPaymentRules.check(amountText: "0", balance: 100, method: "CASH", reference: "",
                                                                 noncashAllowed: false) else { Issue.record("0 accepted"); return }
        #expect(none.messages == ["Enter the amount received (more than 0)."])
        guard case let .failure(over) = CreditPaymentRules.check(amountText: "150.5", balance: Decimal(string: "100.50")!,
                                                                 method: "CASH", reference: "", noncashAllowed: false)
        else { Issue.record("over accepted"); return }
        #expect(over.messages == ["The invoice still owes only 100.5."])
        #expect(FieldAccountabilityTexts.conflictText("PAYMENT_NOT_PERMITTED") == "Bank and mobile-money payments are recorded by the office.")
        #expect(MachineReportTexts.payTitle == "Credit invoice payment")
    }

    @Test func fuelMenuNeedsExpenseRights() {
        #expect(FieldAccess(capabilities: [], permissions: ["tenant.expense.write"]).fuelMenu)
        #expect(!FieldAccess(capabilities: [], permissions: []).fuelMenu)
        #expect(!FieldAccess(capabilities: [], permissions: ["tenant.expense.write"], disabledCapabilities: ["FUEL"]).fuelMenu)
    }
}
