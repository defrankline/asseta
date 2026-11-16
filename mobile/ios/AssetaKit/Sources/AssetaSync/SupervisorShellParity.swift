import AssetaModel
import AssetaStore
import Foundation

// Supervisor shell parity with Android (`ShellModel`, `HomeTexts`, `ReportTexts`, `InvoicePaymentMessages`): side menu,
// Home, Money, credit invoice payment, Dashboard and Settings wording and figures, word for word.

/// Figures of the Supervisor shell as Android writes them (Locale.US, `ShellModel` and `MachineReportRules`).
public enum SupervisorFigures {
    static let us = Locale(identifier: "en_US")

    /// "3,845,000", "12.5" (grouped, at most two decimals, no trailing zeros).
    public static func grouped(_ amount: Decimal) -> String {
        amount.formatted(.number.precision(.fractionLength(0...2)).rounded(rule: .toNearestOrEven).grouping(.automatic).locale(us))
    }

    /// "TZS 3,845,000" (no currency: the grouped amount).
    public static func money(_ amount: Decimal, currency: String?) -> String {
        [currency.flatMap { $0.isEmpty ? nil : $0 }, grouped(amount)].compactMap { $0 }.joined(separator: " ")
    }

    /// Compact money of the designs: below a million the grouped whole amount ("850,000"), from a million "3.85M" / "2.0M"
    /// (one or two decimals), from a billion "1.2B".
    public static func compact(_ amount: Decimal) -> String {
        let sign = amount < 0 ? "-" : ""
        let abs = amount < 0 ? -amount : amount
        func scaled(_ divisor: Decimal, _ suffix: String) -> String {
            let v = round(abs / divisor, 2)
            return sign + v.formatted(.number.precision(.fractionLength(1...2)).grouping(.automatic).locale(us)) + suffix
        }
        if abs >= 1_000_000_000 { return scaled(1_000_000_000, "B") }
        if abs >= 1_000_000 { return scaled(1_000_000, "M") }
        return sign + round(abs, 0).formatted(.number.precision(.fractionLength(0)).grouping(.automatic).locale(us))
    }

    /// Hours without trailing zeros, grouped ("300", "12.5", "1,240").
    public static func hours(_ value: Decimal) -> String { grouped(value) }

    static func round(_ value: Decimal, _ scale: Int) -> Decimal {
        var v = value
        var result = Decimal()
        NSDecimalRound(&result, &v, scale, .plain)
        return result
    }

    static func clock(_ date: Date, calendar: Calendar) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = calendar.timeZone
        f.dateFormat = "HH:mm"
        return f.string(from: date)
    }

    /// "Today 07:40", "Yesterday 16:05", "12 Nov 17:30" (Recent rows, my reports and sales).
    public static func when(_ date: Date, now: Date = Date(), calendar: Calendar = .current) -> String {
        let time = clock(date, calendar: calendar)
        let day = calendar.startOfDay(for: date)
        let today = calendar.startOfDay(for: now)
        if day == today { return "Today \(time)" }
        if let yesterday = calendar.date(byAdding: .day, value: -1, to: today), day == yesterday { return "Yesterday \(time)" }
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = calendar.timeZone
        f.dateFormat = "d MMM HH:mm"
        return f.string(from: date)
    }

    /// "today 07:40", "yesterday", "3 days ago" (Dashboard, my machines).
    public static func ago(_ date: Date, now: Date = Date(), calendar: Calendar = .current) -> String {
        let days = calendar.dateComponents([.day], from: calendar.startOfDay(for: date), to: calendar.startOfDay(for: now)).day ?? 0
        switch days {
        case ..<1: return "today " + clock(date, calendar: calendar)
        case 1: return "yesterday"
        default: return "\(days) days ago"
        }
    }

    /// "99+" above 99; nil for none.
    public static func badge(_ count: Int) -> String? { count > 0 ? (count > 99 ? "99+" : "\(count)") : nil }
}

/// Wording of the Supervisor shell that Android has and the older iOS texts lacked (strings doc "ADR-008 apps").
public enum SupervisorShellTexts {
    // Side menu
    public static let menuSyncAllSent = "Sync · all sent"

    // Home "Recent" pills
    public static let pillCredit = "Credit"
    public static let pillNotPaid = "Not paid"
    public static let pillWaiting = "Waiting to sync"
    public static let pillNotSynced = "Not synced"

    /// "EX-01 report · 300 h", or "EX-01 report" without hours (an opening reading).
    public static func recentReport(_ code: String, _ hours: Decimal?) -> String {
        "\(code) report" + (hours.map { " · \(SupervisorFigures.hours($0)) h" } ?? "")
    }

    /// A report's server status: Awaiting approval, Approved, Rejected.
    public static func reportStatus(_ status: String) -> String {
        switch status {
        case "SUBMITTED": "Awaiting approval"
        case "APPROVED": "Approved"
        case "REJECTED": "Rejected"
        default: status.prefix(1).uppercased() + status.dropFirst().lowercased()
        }
    }

    // Money
    public static let noCash = "No cash balance yet. It appears after a sync."
    public static let recordInvoicePayment = "Record a credit invoice payment"
    public static let moneyRecords = "Cash records, transfers and more"
    public static let moneyFooter = "Sales and payments recorded on this phone, and your cash records."

    // Credit invoice payment
    public static let noInvoices = "No open credit invoices on this phone. They appear after a sync."
    public static func invoiceOption(_ number: String, _ customer: String?) -> String {
        [number, customer].compactMap { $0 }.joined(separator: " · ")
    }
    public static func invoiceOwes(_ balance: String, _ due: String?) -> String { "owes \(balance)" + (due.map { " · due \($0)" } ?? "") }

    // Dashboard
    public static let noBalances = "Customers with usable hours appear here after a sync."
    public static func hoursUsable(_ hours: String) -> String { "\(hours) h usable" }
    public static let balancesFooter = "Hours each customer can still use in a machine report (bought, activated, not yet used or reserved)."
    /// "Last reading 1,510 h · today 07:40", "No reading yet".
    public static func lastReading(_ reading: String?, _ ago: String?) -> String {
        [reading.map { "Last reading \($0) h" } ?? MachineReportTexts.dashNoReading, ago].compactMap { $0 }.joined(separator: " · ")
    }
    public static func productive(_ hours: String, _ percent: Int?) -> String {
        "Productive \(hours) h" + (percent.map { " (\($0)%)" } ?? "")
    }

    // Settings
    public static func version(_ version: String) -> String { "Asseta Supervisor \(version)" }

    /// Server refusals of an hours sale or a credit-invoice payment kept for review (sync status, Inbox); nil for others.
    public static func conflict(_ code: String?) -> String? {
        switch code {
        case "CREDIT_SALES_NOT_ALLOWED": "Your company records credit sales at the office. The sale is kept for review."
        case "CREDIT_NOT_ALLOWED": "Your company does not sell on credit now. The sale is kept for review."
        case "WALK_IN_NO_CREDIT": "A walk-in customer cannot buy on credit. The sale is kept for review."
        case "PAYMENTS_EXCEED_TOTAL": "The payments add up to more than the sale. The sale is kept for review."
        case "INVOICE_PAID": "This invoice is already paid. The payment is kept for review."
        case "INVOICE_OVERPAYMENT": "The payment is more than the invoice still owes. It is kept for review."
        case "INVOICE_CANCELLED": "This invoice was cancelled. The payment is kept for review."
        case "INVOICE_NOT_FOUND": "This invoice is no longer on record. The payment is kept for review."
        case "PAYMENT_NOT_PERMITTED": "Bank and mobile-money payments are recorded by the office."
        default: nil
        }
    }
}

extension FieldAccess {
    /// The Fuel menu entry: FUEL on and the user records expenses (`tenant.expense.write`).
    public var fuelMenu: Bool { fuelOn && can(Self.expenseWrite) }

    public static let expenseWrite = "tenant.expense.write"
}

/// One customer's usable hours (Dashboard "Customer balances", offline from the machine report snapshot).
public struct CustomerBalance: Sendable, Equatable, Identifiable {
    public let id: UUID
    public let name: String
    public let hours: Decimal
}

extension FieldActivity {
    /// Customers with their usable hours (all machines), by name.
    public static func customerBalances(_ rows: [AvailableHoursDTO]) -> [CustomerBalance] {
        Dictionary(grouping: rows, by: \.customerID).map { id, list in
            CustomerBalance(id: id, name: list.lazy.compactMap(\.customerName).first ?? String(id.uuidString.lowercased().prefix(8)),
                            hours: list.reduce(Decimal(0)) { $0 + $1.available.value })
        }
        .sorted { $0.name.lowercased() < $1.name.lowercased() }
    }

    /// Hours and money of this phone's hours sales since `since` (refused ones left out): Dashboard "Hours sold".
    public static func hoursSold(_ operations: [ClientOperation], since: Date) -> (hours: Decimal, amount: Decimal) {
        var hours = Decimal(0), amount = Decimal(0)
        for op in operations where op.opType == OperationType.hoursPurchase.rawValue && op.createdAtDevice >= since
            && op.status != .failed {
            guard let payload = try? JSONValue.parse(op.payloadJSON) else { continue }
            hours += decimal(payload["hours"]) ?? 0
            amount += parts(payload).compactMap { decimal($0["amount"]) }.reduce(0, +)
        }
        return (hours, amount)
    }

    /// My machine reports: the server's (last 30 days) and those still on this phone, newest first. `extra`: the readings
    /// ("1210 → 1510 h") and a rejection note, or why the server refused one sent from this phone.
    public static func reportRows(reports: [MachineReportDTO], operations: [ClientOperation], machineCode: (UUID) -> String?,
                                  now: Date = Date()) -> [RecentActivity] {
        typealias S = SupervisorShellTexts
        var rows: [RecentActivity] = reports.map { r in
            let tone: RecentActivity.Pill = switch r.state {
            case .approved: .good
            case .rejected: .bad
            default: .waiting
            }
            let extra = [ "\(r.startReading) → \(r.endReading) h", r.state == .rejected ? r.decisionNote : nil ]
                .compactMap { $0 }.joined(separator: " · ")
            return RecentActivity(id: r.id, title: S.recentReport(r.machineCode ?? r.machineName ?? "Machine", r.hours.value),
                                  at: r.submittedAt, detail: nil, pill: S.reportStatus(r.status), tone: tone,
                                  machineID: r.machineID, extra: extra)
        }
        let server = Set(reports.map(\.id))
        for op in operations where op.opType == OperationType.machineReport.rawValue && !server.contains(op.id) {
            guard let p = try? AssetaJSON.decoder().decode(MachineReportPayload.self, from: Data(op.payloadJSON.utf8)) else { continue }
            let hours = p.lines.reduce(Decimal(0)) { $0 + $1.hours.value }
            let refused = op.status == .failed || op.status == .conflict
            let waiting = [.pending, .sent, .quarantined].contains(op.status)
            let code = machineCode(p.machineID).flatMap { $0.isEmpty ? nil : $0 } ?? "Machine"
            rows.append(RecentActivity(id: op.id, title: S.recentReport(code, hours > 0 ? hours : nil), at: op.createdAtDevice,
                                       detail: nil, pill: refused ? S.pillNotSynced : waiting ? S.pillWaiting : MachineReportTexts.awaitingApproval,
                                       tone: refused ? .bad : .waiting, machineID: p.machineID,
                                       extra: refused ? (FieldAccountabilityTexts.conflictText(op.errorCode) ?? op.lastError) : nil))
        }
        return rows.sorted { $0.at > $1.at }
    }

    /// My hours sales on this phone, newest first: "Sold 20 h · Pwani Road", detail the amount; pill Paid / Credit / Not
    /// paid, "Waiting to sync" until the server has it, "Not synced" when it refused it.
    public static func saleRows(_ operations: [ClientOperation], customerName: (UUID) -> String?,
                                money: (Decimal) -> String) -> [RecentActivity] {
        typealias S = SupervisorShellTexts
        var rows: [RecentActivity] = []
        for op in operations where op.opType == OperationType.hoursPurchase.rawValue {
            guard let payload = try? JSONValue.parse(op.payloadJSON) else { continue }
            let hours = decimal(payload["hours"]) ?? 0
            let customer = payload["customer_id"]?.stringValue.flatMap(UUID.init(uuidString:)).flatMap(customerName)
                ?? payload["walk_in"]?["name"]?.stringValue ?? "Walk-in"
            let lines = parts(payload)
            let total = lines.compactMap { decimal($0["amount"]) }.reduce(Decimal(0), +)
            let credit = lines.filter { $0["method"]?.stringValue == "CREDIT" }.compactMap { decimal($0["amount"]) }.reduce(Decimal(0), +)
            let (pill, tone): (String, RecentActivity.Pill) =
                if op.status == .failed || op.status == .conflict { (S.pillNotSynced, .bad) }
                else if op.status != .acked { (S.pillWaiting, .neutral) }
                else if lines.isEmpty { (S.pillNotPaid, .waiting) }
                else if credit > 0 { (S.pillCredit, .waiting) }
                else { (MachineReportTexts.pillPaid, .good) }
            rows.append(RecentActivity(id: op.id, title: MachineReportTexts.recentSale(SupervisorFigures.hours(hours), customer),
                                       at: op.createdAtDevice, detail: total > 0 ? money(total) : nil, pill: pill, tone: tone,
                                       machineID: nil))
        }
        return rows.sorted { $0.at > $1.at }
    }
}
