import AssetaModel
import AssetaNetwork
import AssetaStore // UUID.lowercased
import Foundation

// DEC-031 Phase 4 in the Owner app (strings doc "DEC-031 Phases 2 and 4"): More → Customer hours (open prepaid-hours
// purchases with hours left or in use by running jobs), one purchase (opened from HOURS_LOW_BALANCE / HOURS_EXPIRING /
// HOURS_EXPIRED notifications, `data.kind = HOURS_PURCHASE`) and the customer's hours statement of a period with its
// PDF. Read-only; reads may come from the encrypted snapshot cache like every Owner screen.

/// Wording of the customer-hours screens, copied from the strings doc (Android `OwnerAccountabilityTexts` HOURS_* /
/// STMT_*).
public enum CustomerHoursTexts {
    public static let more = "Customer hours"
    public static let listTitle = "Customer hours"
    public static let empty = "No prepaid hours with hours left."
    public static let listFooter = "Prepaid hours with hours left or in use by running jobs. Selling and moving hours is done in the field app or on the web."
    public static func row(purchase: String, customer: String) -> String { "\(purchase) · \(customer)" }
    public static func left(_ hours: String) -> String { "\(hours) h left" }
    public static func inUse(_ hours: String) -> String { "\(hours) h in use by running jobs" }
    public static let purchaseTitle = "Hours purchase"
    public static let hours = "Hours"
    public static let customer = "Customer"
    public static let machine = "Machine"
    public static let status = "Status"
    public static let bought = "Bought"
    public static let activated = "Activated"
    public static let used = "Used"
    /// Hours held by running jobs under daily drawdown (already out of the hours left).
    public static let provisional = "In use by running jobs"
    public static let transferred = "Moved to other machines"
    public static let expired = "Expired"
    public static let remaining = "Left"
    public static let awaiting = "Awaiting activation"
    public static let machines = "Machines"
    public static let openStatement = "Hours statement"
    public static let provisionalFooter = "Hours in use by running jobs are drawn day by day and become final when the job is completed."

    public static func purchaseStatus(_ wire: String) -> String {
        switch wire {
        case "AWAITING_PAYMENT": "Awaiting payment"
        case "PARTLY_ACTIVE": "Partly active"
        case "ACTIVE": "Active"
        case "CONSUMED": "Used up"
        case "EXPIRED": "Expired"
        case "CANCELLED": "Cancelled"
        default: OwnerFormat.humanize(wire)
        }
    }

    // Statement
    public static let statementTitle = "Hours statement"
    public static func statementHeader(customer: String, period: String) -> String { "\(customer) · \(period)" }
    public static let totals = "Totals"
    public static let opening = "Opening balance"
    public static let provisionalAtClose = "Of which in use by running jobs"
    public static let transferredIn = "Moved in"
    public static let transferredOut = "Moved out"
    public static let cancelled = "Cancelled"
    public static let closing = "Closing balance"
    public static let awaitingNow = "Awaiting activation (now)"
    public static let usage = "Hours used"
    public static let usageEmpty = "No hours used in this period."
    public static func usageRow(day: String, job: String) -> String { "\(day) · \(job)" }
    public static func basis(_ wire: String) -> String {
        switch wire {
        case HoursUsageBasis.daily: "Drawn day by day"
        case HoursUsageBasis.final: "Final"
        default: OwnerFormat.humanize(wire)
        }
    }
    public static let running = "Job still running"
    public static let openPDF = "Open PDF"
    public static let pdfFailed = "Could not get the PDF. Check your connection and try again."
    public static func statementFooter(timezone: String, time: String) -> String { "Times are in \(timezone). Generated \(time)." }
}

// MARK: - Requests

extension SnapshotKey {
    public static let hoursPurchases = SnapshotKey("hours.purchases")
    public static func hoursPurchase(_ id: UUID) -> SnapshotKey { SnapshotKey("hours.purchase.\(id.lowercased)") }
    public static func hoursStatement(customerID: UUID, from: String, to: String) -> SnapshotKey {
        SnapshotKey("hours.statement.\(customerID.lowercased).\(from).\(to)")
    }
}

extension OwnerAPI {
    /// `GET /hours-purchases?cancelled=false` (the list keeps those with hours left or in use).
    public static func hoursPurchases(pageSize: Int = 100) -> APIRequest<Page<HoursPurchaseDTO>> {
        .get("\(tenant)/hours-purchases", query: compact([("cancelled", "false")]) + paging(1, pageSize))
    }

    /// `GET /hours-purchases/{id}` (`tenant.hours.read`).
    public static func hoursPurchase(_ id: UUID) -> APIRequest<HoursPurchaseDTO> {
        .get("\(tenant)/hours-purchases/\(id.lowercased)")
    }

    /// `GET /customers/{id}/hours-statement?date_from=&date_to=` (local days, at most 366).
    public static func hoursStatement(customerID: UUID, from: String, to: String) -> APIRequest<HoursStatementDTO> {
        .get("\(tenant)/customers/\(customerID.lowercased)/hours-statement", query: compact([("date_from", from), ("date_to", to)]))
    }

    /// The same statement as a PDF (online only, never cached).
    public static func hoursStatementPDF(customerID: UUID, from: String, to: String) -> APIRequest<RawData> {
        .get("\(tenant)/customers/\(customerID.lowercased)/hours-statement.pdf", query: compact([("date_from", from), ("date_to", to)]))
    }
}

// MARK: - Presentation

/// Statement period chips (owner.stmt.period.*): local days, always ending today except Last month.
public enum StatementPeriod: String, CaseIterable, Sendable, Hashable {
    case thisMonth, lastMonth, last3Months, thisYear

    public var label: String {
        switch self {
        case .thisMonth: "This month"
        case .lastMonth: "Last month"
        case .last3Months: "Last 3 months"
        case .thisYear: "This year"
        }
    }

    /// (date_from, date_to) as local `YYYY-MM-DD`.
    public func range(now: Date = Date(), timeZone: TimeZone = .current) -> (from: String, to: String) {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = timeZone
        let day = { (d: Date) in CashRecordPresentation.localDay(d, timeZone: timeZone) }
        let monthStart = calendar.date(from: calendar.dateComponents([.year, .month], from: now)) ?? now
        switch self {
        case .thisMonth:
            return (day(monthStart), day(now))
        case .lastMonth:
            let start = calendar.date(byAdding: .month, value: -1, to: monthStart) ?? monthStart
            let end = calendar.date(byAdding: .day, value: -1, to: monthStart) ?? monthStart
            return (day(start), day(end))
        case .last3Months:
            return (day(calendar.date(byAdding: .month, value: -2, to: monthStart) ?? monthStart), day(now))
        case .thisYear:
            return (day(calendar.date(from: calendar.dateComponents([.year], from: now)) ?? now), day(now))
        }
    }
}

/// One usage line of the statement: label, value, caption.
public struct UsageLine: Hashable, Sendable {
    public let label: String
    public let value: String
    public let caption: String
}

/// Pure presentation of customer hours, purchases and the statement (as Android `HoursPresentation`).
public enum CustomerHoursPresentation {
    typealias T = CustomerHoursTexts

    static func num(_ value: DecimalString) -> String { OwnerFormat.hoursNumber(value) }
    static func h(_ value: DecimalString) -> String { OwnerFormat.hours(value) }
    static func positive(_ value: DecimalString) -> Bool { value.value > 0 }

    /// Open (not cancelled) purchases with hours left or in use by running jobs, newest first.
    public static func open(_ items: [HoursPurchaseDTO]) -> [HoursPurchaseDTO] {
        items.filter { $0.cancelledAt == nil && (positive($0.totals.remaining) || positive($0.totals.provisional)) }
            .sorted { $0.createdAt > $1.createdAt }
    }

    /// "{left} h left[ · {n} h in use by running jobs]" (provisional is already out of remaining: never subtracted again).
    public static func leftLine(remaining: DecimalString, provisional: DecimalString) -> String {
        T.left(num(remaining)) + (positive(provisional) ? " · " + T.inUse(num(provisional)) : "")
    }

    public static func machine(_ p: HoursPurchaseDTO) -> String {
        DisplayName.machine(code: p.machineCode, name: p.machineName, id: p.machineID)
    }

    public static func customer(_ p: HoursPurchaseDTO) -> String { DisplayName.or(p.customerName, id: p.customerID) }

    /// The list row: "{purchase} · {customer}", machine, hours left line.
    public static func row(_ p: HoursPurchaseDTO) -> (title: String, machine: String, left: String) {
        (T.row(purchase: p.purchaseNumber, customer: customer(p)), machine(p), leftLine(remaining: p.totals.remaining, provisional: p.totals.provisional))
    }

    /// Hours card rows in the documented order (zero-only optional rows left out).
    public static func purchaseRows(_ p: HoursPurchaseDTO) -> [DecisionField] {
        let t = p.totals
        var rows: [(String, String)] = [(T.customer, customer(p)), (T.machine, machine(p)), (T.status, T.purchaseStatus(p.status)),
                                        (T.bought, h(t.purchased)), (T.activated, h(t.activated)), (T.used, h(t.consumed))]
        if positive(t.provisional) { rows.append((T.provisional, h(t.provisional))) }
        if positive(t.transferred) { rows.append((T.transferred, h(t.transferred))) }
        if positive(t.expired) { rows.append((T.expired, h(t.expired))) }
        rows.append((T.remaining, h(t.remaining)))
        if positive(t.awaitingActivation) { rows.append((T.awaiting, h(t.awaitingActivation))) }
        return rows.map { DecisionField(label: $0.0, value: $0.1) }
    }

    /// Per-machine rows, only when the hours are on more than one machine.
    public static func machineRows(_ p: HoursPurchaseDTO) -> [DecisionField] {
        guard let machines = p.machines, machines.count >= 2 else { return [] }
        return machines.map {
            DecisionField(label: DisplayName.machine(code: $0.machineCode, name: $0.machineName, id: $0.machineID),
                          value: leftLine(remaining: $0.remaining, provisional: $0.provisional))
        }
    }

    // Statement

    /// "{customer} · {period}".
    public static func header(_ s: HoursStatementDTO, fallbackName: String?) -> String {
        T.statementHeader(customer: s.customerName ?? fallbackName ?? DisplayName.shortID(s.customerID),
                          period: RevenuePresentation.period(from: s.dateFrom, to: s.dateTo))
    }

    /// Totals rows in the documented order (optional rows only when > 0).
    public static func totals(_ s: HoursStatementDTO) -> [DecisionField] {
        let t = s.totals
        var rows: [(String, String)] = [(T.opening, h(t.openingBalance)), (T.bought, h(t.bought)), (T.activated, h(t.activated)),
                                        (T.used, h(t.used))]
        if positive(t.provisionalAtClose) { rows.append((T.provisionalAtClose, h(t.provisionalAtClose))) }
        if positive(t.transferredIn) { rows.append((T.transferredIn, h(t.transferredIn))) }
        if positive(t.transferredOut) { rows.append((T.transferredOut, h(t.transferredOut))) }
        if positive(t.expired) { rows.append((T.expired, h(t.expired))) }
        if positive(t.cancelled) { rows.append((T.cancelled, h(t.cancelled))) }
        rows.append((T.closing, h(t.closingBalance)))
        if positive(t.awaitingActivation) { rows.append((T.awaitingNow, h(t.awaitingActivation))) }
        return rows.map { DecisionField(label: $0.0, value: $0.1) }
    }

    /// Usage lines, newest day first.
    public static func usage(_ s: HoursStatementDTO) -> [UsageLine] {
        s.usage.sorted { $0.day > $1.day }.map { u in
            let caption = [DisplayName.machine(code: u.machineCode, name: u.machineName, id: u.machineID), T.basis(u.basis)]
                + (u.jobRunning ? [T.running] : [])
            return UsageLine(label: T.usageRow(day: RevenuePresentation.day(u.day), job: u.jobNumber ?? "—"),
                             value: h(u.hours), caption: caption.joined(separator: " · "))
        }
    }

    public static func footer(_ s: HoursStatementDTO, timeZone: TimeZone = .current) -> String {
        T.statementFooter(timezone: s.timezone, time: OwnerFormat.stamp(s.generatedAt, timeZone: timeZone))
    }
}
