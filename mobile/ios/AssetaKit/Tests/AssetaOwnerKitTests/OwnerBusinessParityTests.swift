import AssetaModel
import AssetaNetwork
@testable import AssetaOwnerKit
import Foundation
import Testing

/// ADR-008 Owner Customers & hours, Machines, Money, Record payment and Reports. Same inputs and expected wording as
/// Android `OwnerBusinessScreensTest`; change both together.
@Suite("ADR-008 Owner business screens (Android parity)")
struct OwnerBusinessParityTests {
    static let id1 = UUID(uuidString: "00000000-0000-4000-8000-000000000001")!
    static let id2 = UUID(uuidString: "00000000-0000-4000-8000-000000000002")!

    static func decode<T: Decodable>(_ type: T.Type, _ json: String) throws -> T {
        try AssetaJSON.decoder().decode(type, from: Data(json.utf8))
    }

    static func invoiceJSON(id: UUID = id1, number: String = "INV-0042", amount: String = "3800000", paid: String = "1800000",
                            balance: String = "2000000", status: String = "PART_PAID", overdue: Bool = false,
                            customer: UUID = id2, due: String = "2026-11-30", payments: String = "") -> String {
        """
        {"id":"\(id)","invoice_number":"\(number)","purchase_id":"\(id2)","customer_id":"\(customer)","customer_name":"Msasani Bay",
         "machine_id":"\(id2)","currency":"TZS","hours":"40","unit_price":"95000","amount":"\(amount)","paid":"\(paid)",
         "paid_verified":"0","balance":"\(balance)","payment_terms_days":14,"issued_at":"2026-11-16T15:20:00Z",
         "due_date":"\(due)","status":"\(status)","overdue":\(overdue),"days_overdue":0,"payments":[\(payments)]}
        """
    }

    static func inv(_ json: String = invoiceJSON()) throws -> CreditInvoiceDTO { try decode(CreditInvoiceDTO.self, json) }

    // MARK: Figures

    @Test func figuresFollowTheDesignRules() {
        #expect(OwnerFiguresB.compact(850_000) == "850,000")
        #expect(OwnerFiguresB.compact(3_850_000) == "3.85M")
        #expect(OwnerFiguresB.compact(2_000_000) == "2.0M")
        #expect(OwnerFiguresB.compact(91_200_000) == "91.2M")
        #expect(OwnerFiguresB.compact(1_200_000_000) == "1.2B")
        #expect(OwnerFiguresB.compact(-5_200_000) == "-5.2M")
        #expect(OwnerFiguresB.money(3_800_000, currency: "TZS") == "TZS 3,800,000")
        #expect(OwnerFiguresB.money(Decimal(string: "3800000.5")!, currency: "TZS") == "TZS 3,800,000.50")
        #expect(OwnerFiguresB.hours(Decimal(string: "3182.80")!) == "3,182.8 h")
        #expect(OwnerFiguresB.hours(1510) == "1,510 h")
        #expect(OwnerFiguresB.percent(30, of: 310) == "10%")
        #expect(OwnerFiguresB.percent(1, of: 0) == nil)
        #expect(OwnerFiguresB.day("2026-11-30") == "30 Nov")
        #expect(OwnerFiguresB.day("soon") == "soon")
        #expect(OwnerFiguresB.days(1) == "1 day" && OwnerFiguresB.days(3) == "3 days")
    }

    // MARK: Customers & hours

    @Test func customersShowHoursLeftAndOpenInvoices() throws {
        let c1 = UUID(), c3 = UUID()
        let list = [
            CustomerHoursSummaryDTO(customerID: c1, customerName: "Pwani Road Contractors", bought: 160, activated: 160, used: 140, left: 20),
            CustomerHoursSummaryDTO(customerID: Self.id2, customerName: "Msasani Bay Developers", bought: 140, activated: 140, used: 140,
                                    left: 0, creditOwed: 2_000_000),
            CustomerHoursSummaryDTO(customerID: c3, customerName: "Mji Mpya Housing", bought: 100, activated: 62, used: 38, left: 62,
                                    awaitingActivation: 38, creditOwed: 3_600_000),
        ]
        #expect(OwnerCustomersParity.detail(list[0]) == "Bought 160 h · used 140 h · all paid")
        #expect(OwnerCustomersParity.detail(list[1]) == "Bought 140 h · used 140 h")
        #expect(OwnerCustomersParity.detail(list[2]) == "Bought 100 h · used 38 h · 3.6M on credit, awaiting approval")
        #expect(OwnerCustomersParity.filter(list, query: "mji").map(\.customerName) == ["Mji Mpya Housing"])
        #expect(OwnerCustomersParity.filter(list, query: "  ").count == 3)
        let invoices = try [Self.inv(), Self.inv(Self.invoiceJSON(id: UUID(), balance: "0", status: "PAID")),
                            Self.inv(Self.invoiceJSON(id: UUID(), customer: c1))]
        #expect(OwnerCustomersParity.openInvoices(Self.id2, invoices).map(\.id) == [Self.id1])
        #expect(OwnerCustomersParity.invoiceLine(try Self.inv()) == "3,800,000 · paid 1,800,000 · due 30 Nov")
        let bank = try Self.inv(Self.invoiceJSON(payments: """
        {"id":"\(UUID())","amount":"1800000","method":"BANK","reference":"TX1","payment_status":"VERIFIED","counts":true}
        """))
        #expect(OwnerCustomersParity.invoiceLine(bank) == "3,800,000 · paid 1,800,000 (bank) · due 30 Nov")
        #expect(OwnerCustomersParity.invoiceLine(try Self.inv(Self.invoiceJSON(paid: "0", status: "UNPAID"))) == "3,800,000 · due 30 Nov")
    }

    // MARK: Machines

    @Test func machinesListEveryMachineAndFlagOverdueOnes() throws {
        let m2 = UUID()
        let at = Date(timeIntervalSince1970: 1_792_000_000)
        let report = MachineReportDTO(id: Self.id1, reportNumber: "MR-1", machineID: Self.id2, machineCode: "EX-01", machineName: "CAT 320D2",
                                      startReading: 1210, startAt: at, endReading: 1510, endAt: at, status: .submitted, submittedAt: at,
                                      lines: [.init(lineNo: 1, kind: .customer, hours: 220), .init(lineNo: 2, kind: .nonProductive, hours: 80)])
        let rejected = MachineReportDTO(id: UUID(), reportNumber: "MR-2", machineID: Self.id2, startReading: 1510, startAt: at,
                                        endReading: 1560, endAt: at, status: .rejected, submittedAt: at,
                                        lines: [.init(lineNo: 1, kind: .customer, hours: 50)])
        let statuses = [
            MachineReportStatusDTO(machineID: Self.id2, machineCode: "EX-01", machineName: "CAT 320D2", previousReading: 1510,
                                   daysSinceReport: 0, pendingReportID: Self.id1),
            MachineReportStatusDTO(machineID: m2, machineCode: "EX-02", machineName: "Komatsu PC210", previousReading: 812.5,
                                   lastApprovedReading: Decimal(string: "812.5"), daysSinceReport: 3),
        ]
        let fleetJSON = Samples.machineJSON().replacingOccurrences(of: Samples.machine, with: Self.id2.uuidString.lowercased())
            .replacingOccurrences(of: "\"Sam\"", with: "\"Daudi Mollel\"")
        let fleet = [try Self.decode(MachineMapDTO.self, fleetJSON)]
        let rows = OwnerMachinesParity.rows(statuses: statuses, reports: [report, rejected], fleet: fleet, fleetOn: true,
                                            tracking: true, machineReports: true, reminderDays: 3)
        #expect(rows.map(\.title) == ["EX-02 · Komatsu PC210", "EX-01 · CAT 320D2"])
        #expect(rows[1].detail == "300 h · 220 productive · last reading 1,510 h (pending)")
        #expect(rows[1].supervisor == "Daudi" && rows[1].overdue == nil && rows[1].hours == 300)
        #expect(rows[1].open == .machine(Self.id2))
        #expect(rows[0].overdue?.pill == "No report 3 days")
        #expect(rows[0].detail == "last reading 812.5 h")
        // Without the fleet: a tap opens the report waiting, if any.
        let noFleet = OwnerMachinesParity.rows(statuses: statuses, reports: [report], fleet: [], fleetOn: false, tracking: true,
                                               machineReports: true, reminderDays: 3)
        #expect(noFleet.first { $0.id == Self.id2 }?.open == .report(Self.id1))
        #expect(noFleet.first { $0.id == m2 }?.open == nil)
        // An overdue machine with a tracker shows the tracker line; never reported shows that there is no reading.
        let tracked = OwnerMachinesParity.rows(statuses: [statuses[1]], reports: [], fleet: [try Self.decode(MachineMapDTO.self,
            Samples.machineJSON().replacingOccurrences(of: Samples.machine, with: m2.uuidString.lowercased()))],
                                               fleetOn: true, tracking: true, machineReports: true, reminderDays: 3)
        #expect(tracked[0].detail == "Tracker: engine on · stationary")
        let never = OwnerMachinesParity.rows(statuses: [MachineReportStatusDTO(machineID: m2, machineCode: "EX-03", previousReading: nil)],
                                             reports: [], fleet: [], fleetOn: false, tracking: true, machineReports: true, reminderDays: 3)
        #expect(never[0].overdue?.pill == "No report yet" && never[0].detail == "No approved reading yet")
        #expect(OwnerMachinesParity.mapAccessibility(4) == "Map with 4 machines. Use the List for details.")
    }

    // MARK: Money

    @Test func moneyLinesPillsAndCash() throws {
        var sold = SoldByMethod()
        sold.cash = 5_400_000
        sold.bank = 2_000_000
        sold.credit = 3_800_000
        #expect(OwnerMoneyParity.methods(sold) == "Cash 5.4M · Bank 2.0M · Credit 3.8M")
        #expect(OwnerMoneyParity.pill(try Self.inv()) == ("Part paid", .waiting))
        #expect(OwnerMoneyParity.pill(try Self.inv(Self.invoiceJSON(paid: "0", status: "UNPAID"))) == ("Unpaid", .waiting))
        #expect(OwnerMoneyParity.pill(try Self.inv(Self.invoiceJSON(balance: "0", status: "PAID"))) == ("Paid", .good))
        #expect(OwnerMoneyParity.pill(try Self.inv(Self.invoiceJSON(overdue: true))) == ("Overdue", .bad))
        #expect(OwnerMoneyParity.pill(try Self.inv(Self.invoiceJSON(status: "CANCELLED"))) == ("Cancelled", .neutral))
        #expect(OwnerMoneyParity.invoiceTitle(try Self.inv()) == "INV-0042 · Msasani Bay")
        #expect(OwnerMoneyParity.invoiceDetail(try Self.inv()) == "3.8M · paid 1.8M · due 30 Nov")
        let bank = try Self.inv(Self.invoiceJSON(payments: """
        {"id":"\(UUID())","amount":"1800000","method":"BANK","reference":"TX1","payment_status":"VERIFIED","counts":true}
        """))
        #expect(OwnerMoneyParity.invoiceDetail(bank) == "3.8M · paid 1.8M by bank · due 30 Nov")
        let ordered = OwnerMoneyParity.invoices(try [Self.inv(Self.invoiceJSON(id: Self.id2, balance: "0", status: "PAID")),
                                                     Self.inv(Self.invoiceJSON(id: UUID(), status: "CANCELLED")),
                                                     Self.inv(Self.invoiceJSON(id: Self.id1, overdue: true)), Self.inv(Self.invoiceJSON(id: UUID()))])
        #expect(ordered.count == 3 && ordered.first?.id == Self.id1 && ordered.last?.id == Self.id2)
        #expect(OwnerMoneyParity.expenses(nil) == "Expenses" && OwnerMoneyParity.expenses(3) == "Expenses (3)")

        let s = try Self.decode(CashSupervisorSummaryDTO.self, """
        {"staff_member_id":"\(Self.id1)","staff_name":"Daudi Mollel","currency":"TZS","period_from":"2026-11-17","period_to":"2026-11-17",
         "opening":"0","floats_issued":"0","collections":"0","approved_spending":"0","verified_handovers":"0",
         "closing_outstanding":"3850000","claimed_unverified_handovers":"1200000","pending_spending":"0","unverified_collections":"0"}
        """)
        var utc = Calendar(identifier: .gregorian)
        utc.timeZone = TimeZone(identifier: "UTC")!
        let today = AssetaJSON.parseInstant("2026-11-17T09:00:00Z")!
        #expect(OwnerMoneyParity.cashDetail(s, overdue: nil, today: today, calendar: utc) == "Handed over 1.2M · awaiting your check")
        let flag = try Self.decode(RemittanceOverdueDTO.self, """
        {"id":"\(UUID())","staff_member_id":"\(Self.id1)","local_day":"2026-11-17","cutoff_hour":18,"amounts":[],
         "flagged_at":"2026-11-17T15:00:00Z","policy_version":"p","held_since":"2026-11-15T10:00:00Z"}
        """)
        #expect(OwnerMoneyParity.cashDetail(s, overdue: flag, today: today, calendar: utc) == "Overdue to hand over · 2 days")
        #expect(OwnerMoneyParity.cashRows([s]).count == 1)
    }

    // MARK: Record payment

    @Test func paymentFormRules() throws {
        let i = try Self.inv()
        func draft(_ amount: String, _ method: OwnerPayMethod = .cash, reference: String = "") -> OwnerPaymentDraft {
            var d = OwnerPaymentDraft(invoiceID: Self.id1)
            d.amount = amount
            d.method = method
            d.reference = reference
            return d
        }
        #expect(OwnerPaymentRules.problem(OwnerPaymentDraft(), invoice: nil) == "Choose the invoice being paid.")
        #expect(OwnerPaymentRules.problem(draft("0"), invoice: i) == "Enter the amount received (more than 0).")
        #expect(OwnerPaymentRules.problem(draft("12.345"), invoice: i) == OwnerPaymentTexts.amountNeeded)
        #expect(OwnerPaymentRules.problem(draft("abc"), invoice: i) == OwnerPaymentTexts.amountNeeded)
        #expect(OwnerPaymentRules.problem(draft("2000001"), invoice: i) == "At most the balance, 2,000,000.")
        #expect(OwnerPaymentRules.problem(draft("2,000,000"), invoice: i) == nil)
        #expect(OwnerPaymentRules.problem(draft("170000", .bank), invoice: i)
            == "Enter the transaction reference for a bank or mobile money payment.")
        #expect(OwnerPaymentRules.problem(draft("170000", .mobileMoney, reference: " "), invoice: i) == OwnerPaymentTexts.referenceNeeded)
        #expect(OwnerPaymentRules.problem(draft("170000", .mobileMoney, reference: "QK12AB34"), invoice: i) == nil)
        #expect(OwnerPayMethod.allCases.map(\.label) == ["Cash", "Bank", "Mobile money"])

        let open = OwnerPaymentRules.open(try [Self.inv(Self.invoiceJSON(id: UUID(), balance: "0", status: "PAID")),
                                               Self.inv(Self.invoiceJSON(id: UUID(), status: "CANCELLED")), i,
                                               Self.inv(Self.invoiceJSON(id: Self.id2, overdue: true))])
        #expect(open.map(\.id) == [Self.id2, Self.id1])

        var utc = Calendar(identifier: .gregorian)
        utc.timeZone = TimeZone(identifier: "UTC")!
        let now = AssetaJSON.parseInstant("2026-11-17T09:00:00Z")!
        var cash = draft("170000.00", reference: "ignored")
        let cashBody = OwnerPaymentRules.body(cash, now: now, calendar: utc)
        #expect(cashBody.amount.value == 170_000 && cashBody.method == "CASH" && cashBody.reference == nil)
        #expect(cashBody.clientID == cash.key && cashBody.receivedAt == now)
        cash = draft("5", .bank, reference: " TX1 ")
        cash.yesterday = true
        let bankBody = OwnerPaymentRules.body(cash, now: now, calendar: utc)
        #expect(bankBody.reference == "TX1" && bankBody.receivedAt == AssetaJSON.parseInstant("2026-11-16T12:00:00Z"))

        #expect(OwnerPaymentTexts.left(i) == "TZS 2,000,000 left · due 30 Nov")
        #expect(OwnerPaymentTexts.amountLabel("TZS") == "Amount (TZS)" && OwnerPaymentTexts.amountLabel(nil) == "Amount")
        let after = try Self.inv(Self.invoiceJSON(paid: "1970000", balance: "1830000"))
        #expect(OwnerPaymentTexts.done(after) == "Payment recorded. INV-0042: TZS 1,830,000 left.")
        #expect(OwnerPaymentTexts.refusal("INVOICE_OVERPAYMENT", fallback: "x")
            == "That is more than the invoice still owes. The invoice has been refreshed.")
        #expect(OwnerPaymentTexts.refusal("INVOICE_PAID", fallback: "x").contains("already paid"))
        #expect(OwnerPaymentTexts.refusal("INVOICE_CANCELLED", fallback: "x").contains("cancelled"))
        #expect(OwnerPaymentTexts.refusal("PAYMENT_NOT_PERMITTED", fallback: "x").contains("bank or mobile money"))
        #expect(OwnerPaymentTexts.refusal("SOMETHING_ELSE", fallback: "x") == "x")
    }

    // MARK: Reports

    static func reportJSON(id: UUID = UUID(), status: String = "SUBMITTED", hours: String = "300", customer: String = "220",
                           np: String = "80", lines: String? = nil) -> String {
        let defaultLines = """
        {"id":"\(UUID())","line_no":1,"kind":"CUSTOMER","customer_id":"\(id2)","hours":"220"},
        {"id":"\(UUID())","line_no":2,"kind":"NON_PRODUCTIVE","reason_code":"BREAKDOWN","reason_name":"Breakdown / repair","hours":"40"},
        {"id":"\(UUID())","line_no":3,"kind":"NON_PRODUCTIVE","reason_code":"TRANSIT","reason_name":"Moving between sites","hours":"30"},
        {"id":"\(UUID())","line_no":4,"kind":"NON_PRODUCTIVE","reason_code":"IDLE_ON_SITE","reason_name":"Idle on site","hours":"10"}
        """
        return """
        {"id":"\(id)","report_number":"MR-1","machine_id":"\(id2)","capture_id":"\(UUID())","start_reading":"1210",
         "start_at":"2026-11-16T07:00:00Z","end_reading":"1510","end_at":"2026-11-17T07:00:00Z","hours":"\(hours)",
         "customer_hours":"\(customer)","non_productive_hours":"\(np)","status":"\(status)","submitted_at":"2026-11-17T07:40:00Z",
         "lines":[\(lines ?? defaultLines)]}
        """
    }

    @Test func reportsSplitHoursAndLinkToScreens() throws {
        let r = try Self.decode(MachineReportDTO.self, Self.reportJSON())
        let noLines = try Self.decode(MachineReportDTO.self, Self.reportJSON(hours: "10", customer: "6", np: "4", lines: ""))
        let rejected = try Self.decode(MachineReportDTO.self, Self.reportJSON(status: "REJECTED"))
        let split = OwnerReportsPresentation.split([r, noLines, rejected])
        #expect(split.customers == 226)
        #expect(split.reasons.map(\.name) == ["Breakdown", "Transit", "Idle", "Non-productive"])
        #expect(split.total == 310)
        var utc = Calendar(identifier: .gregorian)
        utc.timeZone = TimeZone(identifier: "UTC")!
        #expect(OwnerReportsTexts.title(month: true, today: AssetaJSON.parseInstant("2026-11-17T09:00:00Z")!, calendar: utc)
            == "Machine hours, November")
        #expect(OwnerReportsTexts.title(month: false) == "Machine hours, this week")
        #expect(OwnerReportsTexts.stillWithCustomers(80) == "80 h still with customers")
        #expect(OwnerReportsTexts.nonProductiveHeader(84) == "NON-PRODUCTIVE · 84 h")
        #expect(OwnerReportsTexts.share(40, of: 310) == "13% of machine hours")

        let all = OwnerFeatures(permissions: ["tenant.machine_report.read", "tenant.hours.read", "tenant.finance.read"])
        let links = OwnerReportsPresentation.links(all)
        #expect(links.map(\.label) == [OwnerReportsTexts.rowCustomerHours, OwnerReportsTexts.rowByMachine, OwnerReportsTexts.rowByReason,
                                       OwnerReportsTexts.rowSales, OwnerReportsTexts.rowCredit, OwnerReportsTexts.rowCash])
        #expect(links.map(\.open) == [.customers, .machines, .hoursByReason, .money, .money, .cash])
        #expect(OwnerReportsPresentation.links(OwnerFeatures(permissions: ["tenant.finance.read"])).map(\.label) == [OwnerReportsTexts.rowCash])

        let orders = try Self.decode([HoursPurchaseDTO].self, """
        [{"id":"\(UUID())","purchase_number":"HP-1","client_id":null,"customer_id":"\(UUID())","machine_id":"\(UUID())",
          "hours":"960","currency":"TZS","amount":"91200000","status":"ACTIVE","created_at":"2026-11-16T08:00:00Z",
          "totals":{"purchased":"960","activated":"960","consumed":"0","remaining":"960","awaiting_activation":"0"}}]
        """)
        let sold = OwnerReportsPresentation.sold(orders)
        #expect(sold.hours == 960 && sold.amount == "TZS 91.2M")
        #expect(OwnerReportsPresentation.sold([]).amount == nil)
    }
}
