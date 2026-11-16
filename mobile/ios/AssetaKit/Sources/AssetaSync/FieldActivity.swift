import AssetaModel
import AssetaStore
import Foundation

// ADR-008 Supervisor Home, Money and Dashboard figures, from what this phone recorded (sales, invoice payments, machine
// reports) and the synced reports. Pure functions so the same numbers show offline and in tests.

/// Today / Week / Month (Money and Dashboard headers).
public enum ActivityPeriod: String, CaseIterable, Sendable, Hashable {
    case today, week, month

    public var label: String {
        switch self {
        case .today: MachineReportTexts.moneyToday
        case .week: MachineReportTexts.moneyWeek
        case .month: MachineReportTexts.moneyMonth
        }
    }

    /// "today", "this week", "this month" (Dashboard "Machine hours this week").
    public var phrase: String {
        switch self {
        case .today: MachineReportTexts.dashPeriodToday
        case .week: MachineReportTexts.dashPeriodWeek
        case .month: MachineReportTexts.dashPeriodMonth
        }
    }

    /// The period's first instant (local day, the week from Monday, the month).
    public func start(now: Date = Date(), calendar: Calendar = .current) -> Date {
        var monday = calendar
        monday.firstWeekday = 2
        return switch self {
        case .today: calendar.startOfDay(for: now)
        case .week: monday.dateInterval(of: .weekOfYear, for: now)?.start ?? calendar.startOfDay(for: now)
        case .month: calendar.dateInterval(of: .month, for: now)?.start ?? calendar.startOfDay(for: now)
        }
    }
}

/// Money sold by payment method (Money "Collections by method").
public struct SalesByMethod: Sendable, Equatable {
    public var cash: Decimal = 0
    public var bank: Decimal = 0
    public var mobileMoney: Decimal = 0
    public var credit: Decimal = 0
    public var hours: Decimal = 0

    public init() {}

    public var total: Decimal { cash + bank + mobileMoney + credit }

    mutating func add(method: String, amount: Decimal) {
        switch method {
        case "BANK": bank += amount
        case "MOBILE_MONEY": mobileMoney += amount
        case "CREDIT": credit += amount
        default: cash += amount
        }
    }
}

/// One Home "Recent" row.
public struct RecentActivity: Sendable, Equatable, Identifiable {
    public enum Pill: Sendable, Equatable { case waiting, good, warning, bad, neutral }
    public let id: UUID
    public let title: String
    public let at: Date
    public let detail: String?
    public let pill: String
    public let tone: Pill
    /// The machine a report row is about (opens its report).
    public let machineID: UUID?
    /// A second line (my machine reports: the readings, a rejection note or why the server refused it).
    public var extra: String? = nil
}

public enum FieldActivity {
    /// Sales and credit-invoice payments this phone recorded since `since` (refused ones left out), by method. Sales
    /// count their payment lines (CREDIT included); invoice payments add money received (as Android `ShellModel.money`).
    public static func salesByMethod(_ operations: [ClientOperation], since: Date) -> SalesByMethod {
        var result = SalesByMethod()
        for op in operations where op.createdAtDevice >= since && op.status != .failed {
            guard let payload = try? JSONValue.parse(op.payloadJSON) else { continue }
            switch op.opType {
            case OperationType.hoursPurchase.rawValue:
                result.hours += decimal(payload["hours"]) ?? 0
                for part in parts(payload) {
                    if let amount = decimal(part["amount"]) { result.add(method: part["method"]?.stringValue ?? "CASH", amount: amount) }
                }
            case OperationType.creditInvoicePayment.rawValue:
                if let amount = decimal(payload["amount"]) { result.add(method: payload["method"]?.stringValue ?? "CASH", amount: amount) }
            default: break
            }
        }
        return result
    }

    static func parts(_ payload: JSONValue) -> [JSONValue] {
        if case let .array(list)? = payload["payments"] { return list }
        if let one = payload["payment"], one != .null { return [one] }
        return []
    }

    static func decimal(_ value: JSONValue?) -> Decimal? { value?.stringValue.flatMap { DecimalString(string: $0)?.value } }

    /// Customer hours and non-productive hours of my reports since `since` (rejected ones left out; unsent ones counted).
    public static func reportHours(_ reports: [MachineReportDTO], unsent: [ClientOperation],
                                   since: Date) -> (customers: Decimal, nonProductive: Decimal) {
        var customers = Decimal(0), other = Decimal(0)
        for report in reports where report.submittedAt >= since && report.state != .rejected {
            customers += report.customerHours.value
            other += report.nonProductiveHours.value
        }
        for op in unsent where op.opType == OperationType.machineReport.rawValue && op.createdAtDevice >= since {
            guard let payload = try? AssetaJSON.decoder().decode(MachineReportPayload.self, from: Data(op.payloadJSON.utf8)) else { continue }
            for line in payload.lines {
                if line.kind == .customer { customers += line.hours.value } else { other += line.hours.value }
            }
        }
        return (customers, other)
    }

    /// Productive share in whole percent; nil when nothing was reported.
    public static func productivePercent(customers: Decimal, nonProductive: Decimal) -> Int? {
        let total = customers + nonProductive
        guard total > 0 else { return nil }
        return Int((NSDecimalNumber(decimal: customers / total * 100).doubleValue).rounded())
    }

    /// Home "Recent": my reports (the server's and those still on this phone) and my sales, newest first; at most four.
    public static func recent(reports: [MachineReportDTO], operations: [ClientOperation], machineCode: (UUID) -> String,
                              customerName: (UUID) -> String?, money: (Decimal) -> String, limit: Int = 4) -> [RecentActivity] {
        let rows = reportRows(reports: reports, operations: operations, machineCode: machineCode)
            + saleRows(operations, customerName: customerName, money: money)
        return Array(rows.sorted { $0.at > $1.at }.prefix(limit))
    }
}
