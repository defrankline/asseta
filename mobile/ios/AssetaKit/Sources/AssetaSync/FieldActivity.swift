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

    /// The period's first instant (local calendar).
    public func start(now: Date = Date(), calendar: Calendar = .current) -> Date {
        switch self {
        case .today: calendar.startOfDay(for: now)
        case .week: calendar.dateInterval(of: .weekOfYear, for: now)?.start ?? calendar.startOfDay(for: now)
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
}

public enum FieldActivity {
    /// Sales and credit-invoice payments this phone recorded since `since` (refused ones left out), by method. Sales
    /// count their payment lines (CREDIT included); invoice payments add money received.
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
            case OperationType.cashCollection.rawValue:
                if let amount = decimal(payload["amount"]) { result.add(method: "CASH", amount: amount) }
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

    /// Productive share in whole percent (0 when nothing was reported).
    public static func productivePercent(customers: Decimal, nonProductive: Decimal) -> Int {
        let total = customers + nonProductive
        guard total > 0 else { return 0 }
        return Int((NSDecimalNumber(decimal: customers / total * 100).doubleValue).rounded())
    }

    /// Home "Recent": my reports (synced and unsent) and my sales, newest first.
    public static func recent(reports: [MachineReportDTO], operations: [ClientOperation], machineCode: (UUID) -> String,
                              customerName: (UUID) -> String?, money: (Decimal) -> String, limit: Int = 6) -> [RecentActivity] {
        typealias T = MachineReportTexts
        var rows: [RecentActivity] = []
        let syncedIDs = Set(reports.map(\.id))
        for report in reports {
            let (pill, tone): (String, RecentActivity.Pill) = switch report.state {
            case .approved: (T.pillApproved, .good)
            case .rejected: (T.pillRejected, .bad)
            default: (T.pillAwaiting, .waiting)
            }
            rows.append(RecentActivity(id: report.id,
                                       title: T.recentReport(report.machineCode ?? machineCode(report.machineID),
                                                             MachineReportRules.hoursText(report.hours.value)),
                                       at: report.submittedAt, detail: nil, pill: pill, tone: tone, machineID: report.machineID))
        }
        for op in operations where op.status != .failed && !syncedIDs.contains(op.id) {
            guard let payload = try? JSONValue.parse(op.payloadJSON) else { continue }
            let unsent = op.status != .acked
            switch op.opType {
            case OperationType.machineReport.rawValue where unsent:
                guard let report = try? AssetaJSON.decoder().decode(MachineReportPayload.self, from: Data(op.payloadJSON.utf8))
                else { continue }
                let hours = report.lines.reduce(Decimal(0)) { $0 + $1.hours.value }
                let code = machineCode(report.machineID)
                rows.append(RecentActivity(id: op.id,
                                           title: report.opening == true ? T.recentOpening(code)
                                               : T.recentReport(code, MachineReportRules.hoursText(hours)),
                                           at: op.createdAtDevice, detail: nil, pill: T.pillNotSent, tone: .neutral,
                                           machineID: report.machineID))
            case OperationType.hoursPurchase.rawValue:
                let hours = decimal(payload["hours"]) ?? 0
                let customer = payload["customer_id"]?.stringValue.flatMap(UUID.init(uuidString:)).flatMap(customerName)
                    ?? payload["walk_in"]?["name"]?.stringValue ?? ""
                let lines = parts(payload)
                let paid = lines.filter { $0["method"]?.stringValue != "CREDIT" }.compactMap { decimal($0["amount"]) }
                    .reduce(Decimal(0), +)
                let credit = lines.contains { $0["method"]?.stringValue == "CREDIT" }
                let (pill, tone): (String, RecentActivity.Pill)
                if unsent {
                    (pill, tone) = (T.pillNotSent, .neutral)
                } else if credit {
                    (pill, tone) = (T.pillCredit, .waiting)
                } else if let amount = decimal(op.serverResultJSON.flatMap { try? JSONValue.parse($0) }?["entity"]?["amount"]),
                          paid < amount {
                    (pill, tone) = (T.pillPartPaid, .waiting)
                } else if paid > 0 {
                    (pill, tone) = (T.pillPaid, .good)
                } else {
                    (pill, tone) = (T.pillSent, .neutral)
                }
                let total = lines.compactMap { decimal($0["amount"]) }.reduce(Decimal(0), +)
                rows.append(RecentActivity(id: op.id, title: T.recentSale(MachineReportRules.hoursText(hours), customer),
                                           at: op.createdAtDevice, detail: total > 0 ? money(total) : nil, pill: pill, tone: tone,
                                           machineID: nil))
            default: continue
            }
        }
        return Array(rows.sorted { $0.at > $1.at }.prefix(limit))
    }
}
