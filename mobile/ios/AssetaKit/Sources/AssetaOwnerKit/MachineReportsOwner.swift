import AssetaModel
import AssetaNetwork
import AssetaStore // UUID.lowercased
import Foundation

// ADR-008 on the Owner app: machine reports to approve (with the tracker cross-check), credit sales to approve, customers'
// hours and credit invoices, productive vs non-productive hours, money sold by method. Every request is re-authorized by
// the server; nothing here decides access.

// MARK: - Requests

extension OwnerAPI {
    /// `GET /machine-reports` (`queue=PENDING`: the approval queue).
    public static func machineReports(pending: Bool = false, status: MachineReportState? = nil, machineID: UUID? = nil,
                                      from: String? = nil, to: String? = nil, page: Int = 1,
                                      pageSize: Int = 200) -> APIRequest<Page<MachineReportDTO>> {
        .get("\(tenant)/machine-reports", query: paging(page, pageSize) + compact([
            ("queue", pending ? "PENDING" : nil), ("status", status?.rawValue), ("machine_id", machineID?.lowercased),
            ("date_from", from), ("date_to", to),
        ]))
    }

    public static func machineReport(_ id: UUID) -> APIRequest<MachineReportDTO> { .get("\(tenant)/machine-reports/\(id.lowercased)") }

    /// Every machine's report status (`GET /machine-reports/status`).
    public static func machineReportStatus() -> APIRequest<[MachineReportStatusDTO]> { .get("\(tenant)/machine-reports/status") }

    public static func approveMachineReport(_ id: UUID, note: String?, idempotencyKey: UUID) throws -> APIRequest<MachineReportDTO> {
        try .mutation(.post, "\(tenant)/machine-reports/\(id.lowercased)/approve", body: MachineReportNoteIn(note: note.nonEmpty),
                      idempotencyKey: idempotencyKey)
    }

    public static func rejectMachineReport(_ id: UUID, reason: String, idempotencyKey: UUID) throws -> APIRequest<MachineReportDTO> {
        try .mutation(.post, "\(tenant)/machine-reports/\(id.lowercased)/reject",
                      body: MachineReportRejectIn(reason: reason.trimmingCharacters(in: .whitespacesAndNewlines)),
                      idempotencyKey: idempotencyKey)
    }

    /// `GET /credit-invoices` (oldest due first is the server's order for open ones).
    public static func creditInvoices(customerID: UUID? = nil, openOnly: Bool = false, overdue: Bool? = nil,
                                      pageSize: Int = 200) -> APIRequest<Page<CreditInvoiceDTO>> {
        .get("\(tenant)/credit-invoices", query: paging(1, pageSize) + compact([
            ("customer_id", customerID?.lowercased), ("overdue", overdue.map { $0 ? "true" : "false" }),
        ]) + (openOnly ? [] : []))
    }

    public static func creditInvoice(_ id: UUID) -> APIRequest<CreditInvoiceDTO> { .get("\(tenant)/credit-invoices/\(id.lowercased)") }

    public static func recordCreditInvoicePayment(_ id: UUID, _ body: CreditInvoicePaymentIn) throws -> APIRequest<CreditInvoiceDTO> {
        try .mutation(.post, "\(tenant)/credit-invoices/\(id.lowercased)/payments", body: body, idempotencyKey: body.clientID)
    }

    /// `GET /customer-hours`: bought / activated / used / left / awaiting / credit owed per customer.
    public static func customerHoursSummary() -> APIRequest<[CustomerHoursSummaryDTO]> { .get("\(tenant)/customer-hours") }

    /// Orders whose credit part waits for activation (`queue=AWAITING_ACTIVATION`).
    public static func creditToApprove(pageSize: Int = 100) -> APIRequest<Page<HoursPurchaseDTO>> {
        .get("\(tenant)/hours-purchases", query: paging(1, pageSize) + compact([("queue", "AWAITING_ACTIVATION"), ("cancelled", "false")]))
    }

    /// Orders recorded in a period (money sold by method).
    public static func hoursPurchases(from: String, to: String, pageSize: Int = 200) -> APIRequest<Page<HoursPurchaseDTO>> {
        .get("\(tenant)/hours-purchases", query: paging(1, pageSize) + compact([("date_from", from), ("date_to", to)]))
    }

    /// Approve the credit part of an order (`tenant.hours.credit_activate`, never the order's recorder).
    public static func activateCredit(_ purchaseID: UUID, hours: Decimal, reason: String,
                                      idempotencyKey: UUID) throws -> APIRequest<HoursPurchaseDTO> {
        try .mutation(.post, "\(tenant)/hours-purchases/\(purchaseID.lowercased)/credit-activations",
                      body: CreditActivationIn(hours: DecimalString(hours), reason: reason), idempotencyKey: idempotencyKey)
    }

    /// A report export (`GET /reports/{code}.pdf`).
    public static func reportPDF(_ code: String, from: String?, to: String?) -> APIRequest<RawData> {
        .get("\(tenant)/reports/\(code).pdf", query: compact([("from", from), ("to", to)]))
    }
}

struct MachineReportNoteIn: Codable, Sendable { let note: String? }
struct MachineReportRejectIn: Codable, Sendable { let reason: String }
struct CreditActivationIn: Codable, Sendable { let hours: DecimalString; let reason: String }

extension SnapshotKey {
    public static let machineReportQueue = SnapshotKey("machine-reports:PENDING")
    public static func machineReport(_ id: UUID) -> SnapshotKey { SnapshotKey("machine-report.\(id.lowercased)") }
    public static let machineReportStatus = SnapshotKey("machine-reports:status")
    public static func machineReports(from: String, to: String) -> SnapshotKey { SnapshotKey("machine-reports:\(from):\(to)") }
    public static let creditInvoices = SnapshotKey("credit-invoices")
    public static let customerHoursSummary = SnapshotKey("customer-hours")
    public static let creditToApprove = SnapshotKey("hours-purchases:AWAITING_ACTIVATION")
    public static func hoursPurchases(from: String, to: String) -> SnapshotKey { SnapshotKey("hours-purchases:\(from):\(to)") }
}

// MARK: - Rules

/// Who may decide a machine report: the approve permission, never the person who submitted it (segregation of duties),
/// and only while it is SUBMITTED.
public enum MachineReportApproval {
    public static let reasonMin = 3

    public enum Decision: Equatable, Sendable { case allowed, ownReport, notPermitted, decided }

    public static func decision(_ report: MachineReportDTO, me: UUID, permissions: Set<String>) -> Decision {
        guard report.state == .submitted else { return .decided }
        guard permissions.contains(MachineReportPermission.approve) else { return .notPermitted }
        if report.submittedBy == me { return .ownReport }
        return .allowed
    }

    /// A rejection needs a reason (3+ characters, as the server).
    public static func rejectReasonValid(_ text: String) -> Bool {
        text.trimmingCharacters(in: .whitespacesAndNewlines).count >= reasonMin
    }

    /// A customer line's hours before and after this report ("140 → 20 h left").
    public static func beforeAfter(_ line: MachineReportDTO.Line) -> (before: Decimal, after: Decimal)? {
        guard line.lineKind == .customer, let available = line.availableHours?.value else { return nil }
        return (available, available - line.hours.value)
    }
}

/// Approved (and waiting) report hours per machine and per reason over a period.
public struct MachineHoursSummary: Sendable, Equatable {
    public struct Machine: Sendable, Equatable, Identifiable {
        public let id: UUID
        public let code: String
        public let name: String
        public var productive: Decimal
        public var nonProductive: Decimal
        public var lastReading: Decimal?
        public var lastPending: Bool
        public var submittedBy: String?
        public var total: Decimal { productive + nonProductive }
    }

    public var machines: [Machine]
    /// Customers first, then each reason, largest first.
    public var byReason: [(name: String, hours: Decimal)]
    public var productive: Decimal
    public var nonProductive: Decimal

    public static func == (a: MachineHoursSummary, b: MachineHoursSummary) -> Bool {
        a.machines == b.machines && a.productive == b.productive && a.nonProductive == b.nonProductive
            && a.byReason.map(\.name) == b.byReason.map(\.name) && a.byReason.map(\.hours) == b.byReason.map(\.hours)
    }

    public var total: Decimal { productive + nonProductive }
    public var productivePercent: Int {
        total > 0 ? Int((NSDecimalNumber(decimal: productive / total * 100).doubleValue).rounded()) : 0
    }

    /// Rejected reports are left out; waiting ones count (they show as "pending").
    public static func of(_ reports: [MachineReportDTO]) -> MachineHoursSummary {
        var machines: [UUID: Machine] = [:]
        var reasons: [String: Decimal] = [:]
        var productive = Decimal(0), other = Decimal(0)
        for report in reports.sorted(by: { $0.submittedAt < $1.submittedAt }) where report.state != .rejected {
            var m = machines[report.machineID] ?? Machine(id: report.machineID, code: report.machineCode ?? "", name: report.machineName ?? "",
                                                          productive: 0, nonProductive: 0, lastReading: nil, lastPending: false,
                                                          submittedBy: nil)
            m.productive += report.customerHours.value
            m.nonProductive += report.nonProductiveHours.value
            m.lastReading = report.endReading.value
            m.lastPending = report.state == .submitted
            m.submittedBy = report.submittedByName
            machines[report.machineID] = m
            productive += report.customerHours.value
            other += report.nonProductiveHours.value
            for line in report.lines where line.lineKind == .nonProductive {
                reasons[line.reasonName ?? line.reasonCode ?? "Other", default: 0] += line.hours.value
            }
        }
        let byReason = [(MachineReportOwnerTexts.customers, productive)] + reasons.sorted { $0.value > $1.value }.map { ($0.key, $0.value) }
        return MachineHoursSummary(machines: machines.values.sorted { $0.code < $1.code }, byReason: byReason,
                                   productive: productive, nonProductive: other)
    }
}

/// Money sold in a period by payment line (CREDIT included) from the orders.
public struct SoldByMethod: Sendable, Equatable {
    public var cash: Decimal = 0
    public var bank: Decimal = 0
    public var mobileMoney: Decimal = 0
    public var credit: Decimal = 0
    public var hours: Decimal = 0
    public var total: Decimal { cash + bank + mobileMoney + credit }

    public init() {}

    public static func of(_ orders: [HoursPurchaseDTO]) -> SoldByMethod {
        var s = SoldByMethod()
        for order in orders where order.cancelledAt == nil {
            s.hours += order.hours.value
            s.credit += order.creditAmount?.value ?? 0
            for payment in order.payments ?? [] where payment.method != "CREDIT" {
                switch payment.method {
                case "BANK": s.bank += payment.amount.value
                case "MOBILE_MONEY": s.mobileMoney += payment.amount.value
                default: s.cash += payment.amount.value
                }
            }
        }
        return s
    }
}

/// A machine the owner should chase for a report: the shared ``MachineReportStanding`` (as the Supervisor app judges it)
/// is due, needs its first reading, or was rejected and not redone. A machine with a report waiting is never overdue.
public enum OverdueMachine: Sendable, Equatable {
    /// No report for this many days (more than 0).
    case noReportFor(days: Int)
    /// Never reported (no report day known) or its first reading is still missing.
    case noReportYet
    /// The last report was rejected and not yet redone.
    case rejected

    /// The machine's overdue state under the tenant's reminder days (nil = reminders off), else nil.
    public static func of(_ state: MachineReportStatusDTO, reminderDays: Int?) -> OverdueMachine? {
        switch MachineReportStanding.of(state, unsentReport: false, reminderDays: reminderDays) {
        case .due:
            if let days = state.daysSinceReport, days > 0 { return .noReportFor(days: days) }
            return .noReportYet
        case .opening: return .noReportYet
        case .rejected: return .rejected
        case .awaitingApproval, .upToDate: return nil
        }
    }

    /// The overdue machines, longest without a report first (never reported last).
    public static func list(_ states: [MachineReportStatusDTO], reminderDays: Int?) -> [(state: MachineReportStatusDTO, overdue: OverdueMachine)] {
        let rows = states.compactMap { s in of(s, reminderDays: reminderDays).map { (state: s, overdue: $0) } }
        return rows.enumerated().sorted { a, b in
            let (da, db) = (a.element.state.daysSinceReport ?? -1, b.element.state.daysSinceReport ?? -1)
            return da != db ? da > db : a.offset < b.offset
        }.map(\.element)
    }

    /// Owner Home row title ("EX-02 · no report for 3 days").
    public func title(_ machine: String) -> String {
        switch self {
        case let .noReportFor(days): MachineReportOwnerTexts.attentionMissing(machine, days)
        case .noReportYet: MachineReportOwnerTexts.attentionNoReportYet(machine)
        case .rejected: MachineReportOwnerTexts.attentionRejected(machine)
        }
    }

    /// Machines screen pill ("No report 3 days").
    public var pill: String {
        switch self {
        case let .noReportFor(days): MachineReportOwnerTexts.noReportDays(days)
        case .noReportYet: MachineReportOwnerTexts.noReportYet
        case .rejected: MachineReportOwnerTexts.pillRejected
        }
    }
}

extension OwnerAPI {
    /// The tenant's CUSTOMER_HOURS policy (`machine_report_reminder_days` for overdue machines).
    public static func customerHoursPolicy() -> APIRequest<EffectivePolicyDTO<CustomerHoursPolicyValues>> {
        .get("\(tenant)/policies/CUSTOMER_HOURS/effective")
    }
}

extension SnapshotKey {
    public static let customerHoursPolicy = SnapshotKey("policy.CUSTOMER_HOURS")
}

/// Owner Home "Needs your attention": waiting machine reports and overdue machines (``OverdueMachine``).
public struct AttentionRow: Sendable, Equatable, Identifiable {
    public enum Kind: Sendable, Equatable { case report(UUID), missing(UUID) }
    public let id: String
    public let title: String
    public let detail: String
    public let pill: String
    public let kind: Kind

    /// `reminderDays`: the tenant's `machine_report_reminder_days` (``MachineReportStanding/reminderDays(_:)``).
    public static func rows(pending: [MachineReportDTO], states: [MachineReportStatusDTO], reminderDays: Int?,
                            now: Date = Date()) -> [AttentionRow] {
        typealias T = MachineReportOwnerTexts
        var rows = pending.sorted { $0.submittedAt > $1.submittedAt }.map { r in
            AttentionRow(id: "r-\(r.id)",
                         title: r.nonProductiveHours.value > 0
                             ? T.attentionReportIdle(r.machineCode ?? "", T.h(r.nonProductiveHours.value))
                             : T.attentionReport(r.machineCode ?? "", T.h(r.hours.value)),
                         detail: [r.submittedByName, T.when(r.submittedAt, now: now)].compactMap { $0 }.joined(separator: " · "),
                         pill: T.review, kind: .report(r.id))
        }
        rows += OverdueMachine.list(states, reminderDays: reminderDays).map { s, overdue in
            AttentionRow(id: "m-\(s.machineID)", title: overdue.title(s.machineCode ?? s.machineName ?? ""),
                         detail: s.machineName ?? "", pill: T.overdue, kind: .missing(s.machineID))
        }
        return rows
    }
}

/// Wording of the ADR-008 Owner app (approved designs owner/*). Same text as Android.
public enum MachineReportOwnerTexts {
    /// Hours for display: grouping, 0–1 decimals ("300", "5,016.8").
    public static func h(_ value: Decimal, locale: Locale = .current) -> String {
        value.formatted(.number.precision(.fractionLength(0...1)).locale(locale))
    }

    /// Short money ("3.85M", "355K", "900").
    public static func short(_ value: Decimal) -> String {
        let n = NSDecimalNumber(decimal: value).doubleValue
        switch abs(n) {
        case 1_000_000...: return (n / 1_000_000).formatted(.number.precision(.fractionLength(0...2))) + "M"
        case 10_000...: return (n / 1000).formatted(.number.precision(.fractionLength(0...1))) + "K"
        default: return n.formatted(.number.precision(.fractionLength(0)))
        }
    }

    /// "today 07:40", "yesterday 18:10", "2 days ago".
    public static func when(_ date: Date, now: Date = Date(), calendar: Calendar = .current) -> String {
        let days = calendar.dateComponents([.day], from: calendar.startOfDay(for: date), to: calendar.startOfDay(for: now)).day ?? 0
        let time = date.formatted(date: .omitted, time: .shortened)
        switch days {
        case ..<1: return "today \(time)"
        case 1: return "yesterday \(time)"
        default: return "\(days) days ago"
        }
    }

    public static let customers = "Customers"
    public static let review = "Review"
    public static let overdue = "Overdue"
    public static func attentionReport(_ code: String, _ hours: String) -> String { "\(code) report · \(hours) h" }
    public static func attentionReportIdle(_ code: String, _ hours: String) -> String { "\(code) report · \(hours) h non-productive" }
    public static func attentionMissing(_ code: String, _ days: Int) -> String { "\(code) · no report for \(days) days" }
    public static func attentionNoReportYet(_ code: String) -> String { "\(code) · no report yet" }
    public static func attentionRejected(_ code: String) -> String { "\(code) · report rejected, not yet redone" }

    // Home
    public static let cashWithSupervisors = "Cash with supervisors"
    public static let hoursSoldWeek = "Hours sold this week"
    public static let productive = "Productive"
    public static let yourBusiness = "YOUR BUSINESS"
    public static let needsAttention = "NEEDS YOUR ATTENTION"
    public static let nothingNeedsYou = "Nothing needs you right now."
    public static let tileApprovals = "Approvals"
    public static let tileApprovalsSub = "Reports, credit, expenses"
    public static func waiting(_ n: Int) -> String { "\(n) waiting" }
    public static let tileCustomers = "Customers"
    public static let tileCustomersSub = "Hours bought, used, left"
    public static let tileMachines = "Machines"
    public static let tileMachinesSub = "Map, readings, hours"
    public static let tileMoney = "Money"
    public static let tileMoneySub = "Collections, cash, expenses"
    // Menu
    public static let menuHome = "Home"
    public static let menuCustomers = "Customers & hours"
    public static let menuReports = "Reports"
    public static let menuNotifications = "Notifications"
    public static let menuSwitchCompany = "Switch company"
    public static let menuSettings = "Settings"
    public static let menuSignOut = "Sign out"
    public static let menuMore = "More"
    public static let roleOwner = "Owner"
    // Approvals
    public static func filterAll(_ n: Int) -> String { "All \(n)" }
    public static func filterReports(_ n: Int) -> String { "Machine reports \(n)" }
    public static func filterCredit(_ n: Int) -> String { "Credit \(n)" }
    public static func filterExpenses(_ n: Int) -> String { "Expenses \(n)" }
    public static let kindReport = "MACHINE REPORT"
    public static let kindCredit = "CREDIT SALE"
    public static let kindExpense = "EXPENSE"
    public static func reportCard(_ code: String, _ hours: String, _ name: String) -> String { "\(code) · \(hours) h · \(name)" }
    public static func reportSplit(customerHours: String, customers: Int, idle: String) -> String {
        "\(customerHours) h to \(customers) \(customers == 1 ? "customer" : "customers") · \(idle) h non-productive"
    }
    public static func creditCard(_ customer: String, _ hours: String) -> String { "\(customer) · \(hours) h on credit" }
    public static func creditDetail(_ invoice: String?, _ amount: String) -> String {
        [invoice.map { "Invoice \($0)" }, amount].compactMap { $0 }.joined(separator: " · ")
    }
    public static let approveCredit = "Approve credit"
    public static let reject = "Reject"
    public static let approve = "Approve"
    public static let creditApprovedReason = "Credit approved in the Owner app"
    public static let otherApprovals = "Other approvals"
    public static let otherApprovalsSub = "Hand-overs, petty cash, discounts and more"
    public static let nothingWaiting = "Nothing is waiting for you."
    // Report approval
    public static func reportTitle(_ code: String) -> String { "\(code) machine report" }
    public static func readings(_ from: String, _ to: String) -> String { "\(from) → \(to) h" }
    public static func readByPhone(_ hours: String, _ ocr: String?) -> String {
        ocr.map { "\(hours) h · read by phone \($0) ✓" } ?? "\(hours) h"
    }
    public static func customersHeader(_ hours: String) -> String { "CUSTOMERS · \(hours) h" }
    public static func nonProductiveHeader(_ hours: String) -> String { "NON-PRODUCTIVE · \(hours) h" }
    public static func leftAfter(_ before: String, _ after: String) -> String { "· \(before) → \(after) h left" }
    public static func tracker(_ tracker: String, _ meter: String) -> String {
        "Tracker engine hours for the same period: \(tracker) h (meter \(meter) h)."
    }
    public static let noTracker = "No tracker engine hours for this period."
    public static let rejectReason = "Reason (needed to reject)"
    public static let rejectPlaceholder = "e.g. Idle hours too high, explain"
    public static let ownReport = "You submitted this report, so someone else decides it."
    public static let notPermitted = "You can read this report but not decide it."
    public static let decidedApproved = "Approved"
    public static let decidedRejected = "Rejected"
    // Customers
    public static let customersTitle = "Customers & hours"
    public static let searchCustomers = "Search customers"
    public static let bought = "Bought"
    public static let used = "Used"
    public static let creditOwed = "Credit owed"
    public static func hoursLeft(_ h: String) -> String { "\(h) h left" }
    public static func boughtUsed(_ bought: String, _ used: String) -> String { "Bought \(bought) h · used \(used) h" }
    public static let allPaid = "all paid"
    public static func awaitingCredit(_ money: String) -> String { "\(money) on credit, awaiting approval" }
    public static func invoiceRow(_ number: String) -> String { "Invoice \(number) · credit" }
    public static func owed(_ money: String) -> String { "\(money) owed" }
    // Machines
    public static let machinesTitle = "Machines"
    public static let map = "Map"
    public static let list = "List"
    public static let thisWeek = "THIS WEEK"
    public static func machineWeek(_ total: String, _ productive: String, _ last: String?, pending: Bool) -> String {
        "\(total) h · \(productive) productive" + (last.map { " · last reading \($0) h" + (pending ? " (pending)" : "") } ?? "")
    }
    public static func noReportDays(_ n: Int) -> String { "No report \(n) days" }
    public static let noReportYet = "No report yet"
    public static let pillRejected = "Rejected"
    public static let noReports = "No machine reports this week."
    // Money
    public static func soldIn(_ period: String) -> String { "SOLD \(period.uppercased())" }
    public static func soldLine(cash: String, bank: String, mobile: String, credit: String) -> String {
        "Cash \(cash) · Bank \(bank) · Mobile \(mobile) · Credit \(credit)"
    }
    public static let cashSupervisors = "CASH WITH SUPERVISORS"
    public static func handedAwaiting(_ money: String) -> String { "Handed over \(money) · awaiting your check" }
    public static let creditInvoices = "CREDIT INVOICES"
    public static func invoiceLine(_ amount: String, _ paid: String, _ due: String?) -> String {
        [amount, "paid \(paid)", due.map { "due \($0)" }].compactMap { $0 }.joined(separator: " · ")
    }
    public static func expenses(_ n: Int) -> String { "Expenses (\(n))" }
    public static let recordPayment = "Record payment"
    public static let noInvoices = "No open credit invoices."
    public static let paymentSaved = "Payment recorded."
    // Reports
    public static let reportsTitle = "Reports"
    public static func machineHoursIn(_ period: String) -> String { "Machine hours, \(period)" }
    public static let hoursSold = "Hours sold"
    public static let hoursUsed = "Hours used"
    public static func stillWithCustomers(_ h: String) -> String { "\(h) h still with customers" }
    public static let reportsHeader = "REPORTS"
    public static let reportCodes: [(code: String, title: String)] = [
        ("customer_hours", "Customer hours: bought, used, left"),
        ("machine_hours", "Productive vs non-productive by machine"),
        ("machine_hours", "Non-productive hours by reason"),
        ("sales_collections", "Sales and collections by method"),
        ("credit_invoices", "Credit invoices and payments"),
        ("cash", "Cash per supervisor"),
    ]
}
