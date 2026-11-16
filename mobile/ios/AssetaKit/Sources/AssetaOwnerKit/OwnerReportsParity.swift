import AssetaModel
import Foundation

// ADR-008 Owner Reports: the same rules and wording as Android `ui/reports/OwnerReportsScreen.kt` (strings doc
// "ADR-008 apps › Owner › Reports"). Each REPORTS row opens a screen; nothing is downloaded.

private typealias F = OwnerFiguresB

public enum OwnerReportsTexts {
    public static let byReason = "Non-productive hours by reason"
    public static let reports = "REPORTS"
    public static let customers = "Customers"
    public static let hoursSold = "Hours sold"
    public static let hoursUsed = "Hours used"
    public static let nonProductive = "Non-productive"
    public static let noHours = "No machine hours reported in this period."
    public static let counted = "Approved and waiting reports; rejected ones are left out."
    public static let barAccessibility = "Machine hours by customers and reasons"
    public static let rowCustomerHours = "Customer hours: bought, used, left"
    public static let rowByMachine = "Productive vs non-productive by machine"
    public static let rowByReason = "Non-productive hours by reason"
    public static let rowSales = "Sales and collections by method"
    public static let rowCredit = "Credit invoices and payments"
    public static let rowCash = "Cash per supervisor"

    /// "Machine hours, November" (month) / "Machine hours, this week".
    public static func title(month: Bool, today: Date = Date(), calendar: Calendar = .current) -> String {
        guard month else { return "Machine hours, this week" }
        let f = DateFormatter()
        f.calendar = calendar
        f.timeZone = calendar.timeZone
        f.locale = Locale(identifier: "en_US")
        f.dateFormat = "LLLL"
        return "Machine hours, \(f.string(from: today))"
    }

    public static func stillWithCustomers(_ hours: Decimal) -> String { "\(F.hours(hours)) still with customers" }

    /// "NON-PRODUCTIVE · 80 h" (the by-reason section).
    public static func nonProductiveHeader(_ hours: Decimal) -> String { "\(nonProductive.uppercased()) · \(F.hours(hours))" }

    /// "12% of machine hours".
    public static func share(_ hours: Decimal, of total: Decimal) -> String? { F.percent(hours, of: total).map { "\($0) of machine hours" } }
}

/// Machine hours of a period: customer work and each non-productive reason (legend order: customers first).
public struct OwnerHoursSplit: Sendable, Equatable {
    public struct Reason: Sendable, Equatable {
        public let name: String
        public let hours: Decimal
    }

    public let customers: Decimal
    /// Biggest first.
    public let reasons: [Reason]
    public var nonProductive: Decimal { reasons.reduce(0) { $0 + $1.hours } }
    public var total: Decimal { customers + nonProductive }
}

/// Where a REPORTS row leads.
public enum OwnerReportLink: Sendable, Hashable { case customers, machines, hoursByReason, money, cash }

public enum OwnerReportsPresentation {
    /// Short reason names of the legend ("Breakdown", "Transit", "Idle", "Servicing"); else the tenant's name.
    public static func reasonLabel(_ l: MachineReportDTO.Line) -> String {
        switch l.reasonCode {
        case "BREAKDOWN": return "Breakdown"
        case "TRANSIT": return "Transit"
        case "IDLE_ON_SITE": return "Idle"
        case "SERVICING": return "Servicing"
        case "WAITING_CUSTOMER": return "Waiting for customer"
        case "WEATHER": return "Weather"
        default:
            if let name = l.reasonName { return name }
            if let code = l.reasonCode {
                let text = code.lowercased().replacingOccurrences(of: "_", with: " ")
                return text.prefix(1).uppercased() + text.dropFirst()
            }
            return OwnerReportsTexts.nonProductive
        }
    }

    /// Customer hours and non-productive hours by reason of the period's reports (rejected ones left out), the biggest
    /// reason first. Non-productive hours a list row carries without its lines count as "Non-productive".
    public static func split(_ reports: [MachineReportDTO]) -> OwnerHoursSplit {
        let counted = reports.filter { $0.state != .rejected }
        var order: [String] = []
        var byReason: [String: Decimal] = [:]
        func add(_ name: String, _ hours: Decimal) {
            if byReason[name] == nil { order.append(name) }
            byReason[name, default: 0] += hours
        }
        for r in counted {
            let lines = r.lines.filter { $0.lineKind == .nonProductive }
            for l in lines { add(reasonLabel(l), l.hours.value) }
            let unlisted = r.nonProductiveHours.value - lines.reduce(Decimal(0)) { $0 + $1.hours.value }
            if unlisted > 0 { add(OwnerReportsTexts.nonProductive, unlisted) }
        }
        let reasons = order.enumerated().filter { byReason[$0.element, default: 0] > 0 }
            .sorted { a, b in
                let (ha, hb) = (byReason[a.element] ?? 0, byReason[b.element] ?? 0)
                return ha != hb ? ha > hb : a.offset < b.offset
            }
            .map { OwnerHoursSplit.Reason(name: $0.element, hours: byReason[$0.element] ?? 0) }
        return OwnerHoursSplit(customers: counted.reduce(Decimal(0)) { $0 + $1.customerHours.value }, reasons: reasons)
    }

    /// Hours sold in the period (orders not cancelled) and their amount per currency ("TZS 91.2M").
    public static func sold(_ orders: [HoursPurchaseDTO]) -> (hours: Decimal, amount: String?) {
        let live = orders.filter { $0.cancelledAt == nil }
        let amounts = Dictionary(grouping: live, by: \.currency).sorted { $0.key < $1.key }.map { currency, list in
            "\(currency) \(F.compact(list.reduce(Decimal(0)) { $0 + $1.amount.value }))".trimmingCharacters(in: .whitespaces)
        }
        return (live.reduce(Decimal(0)) { $0 + $1.hours.value }, amounts.isEmpty ? nil : amounts.joined(separator: ", "))
    }

    /// The REPORTS rows the role can open (no files: each opens the matching screen).
    public static func links(_ f: OwnerFeatures) -> [(label: String, open: OwnerReportLink)] {
        typealias T = OwnerReportsTexts
        return [
            f.hoursRead ? (T.rowCustomerHours, .customers) : nil,
            f.machineReports ? (T.rowByMachine, .machines) : nil,
            f.machineReports ? (T.rowByReason, .hoursByReason) : nil,
            f.hoursRead ? (T.rowSales, .money) : nil,
            f.hoursRead ? (T.rowCredit, .money) : nil,
            f.finance ? (T.rowCash, .cash) : nil,
        ].compactMap { $0 }
    }
}
