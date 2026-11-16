import AssetaModel
import Foundation

// ADR-008 Owner Customers & hours, Machines and Money: the same rules and wording as Android (`CustomersScreen.kt`,
// `MachinesScreen.kt`, `MoneyScreen.kt`; strings doc "ADR-008 apps › Owner").

private typealias F = OwnerFiguresB

/// The tone of a status pill, mapped to the shell pill by the views.
public enum OwnerPillTone: Sendable, Equatable { case waiting, good, bad, neutral }

/// Payment method words shared by Customers and Money (design: Cash · Bank · Mobile · Credit).
public enum OwnerMoneyWords {
    public static func method(_ m: String) -> String {
        switch m {
        case "CASH": "Cash"
        case "BANK", "BANK_TRANSFER": "Bank"
        case "MOBILE_MONEY": "Mobile"
        case "CREDIT": "Credit"
        default: m.prefix(1).uppercased() + m.dropFirst().lowercased()
        }
    }

    /// The single method of the payments that count on an invoice, else nil.
    static func singleMethod(_ i: CreditInvoiceDTO) -> String? {
        let methods = i.payments.filter { $0.counts ?? ($0.paymentStatus != "REJECTED") }.map(\.method)
        let distinct = Set(methods)
        return distinct.count == 1 ? distinct.first : nil
    }
}

// MARK: - Customers & hours

public enum OwnerCustomersParity {
    public static let empty = "No customers with hours yet."
    public static let noMatch = "No customer matches this search."

    /// Customers matching `query` (name, case-insensitive), by name.
    public static func filter(_ list: [CustomerHoursSummaryDTO], query: String) -> [CustomerHoursSummaryDTO] {
        let q = query.trimmingCharacters(in: .whitespaces).lowercased()
        return list.filter { q.isEmpty || ($0.customerName ?? "").lowercased().contains(q) }
            .sorted { ($0.customerName ?? "").lowercased() < ($1.customerName ?? "").lowercased() }
    }

    /// "Bought 160 h · used 140 h · all paid" (or "· 3.6M on credit, awaiting approval").
    public static func detail(_ c: CustomerHoursSummaryDTO) -> String {
        let owed = c.creditOwed.value, awaiting = c.awaitingActivation.value
        let tail: String? = if owed == 0 && awaiting == 0 {
            MachineReportOwnerTexts.allPaid
        } else if owed > 0 && awaiting > 0 {
            MachineReportOwnerTexts.awaitingCredit(F.compact(owed))
        } else {
            nil
        }
        return ["Bought \(F.formatHours(c.bought.value)) h", "used \(F.formatHours(c.used.value)) h", tail]
            .compactMap { $0 }.joined(separator: " · ")
    }

    /// The customer's open credit invoices (balance left, not cancelled), oldest due first.
    public static func openInvoices(_ customerID: UUID, _ invoices: [CreditInvoiceDTO]) -> [CreditInvoiceDTO] {
        invoices.filter { $0.customerID == customerID && $0.status != "CANCELLED" && $0.balance.value > 0 }
            .sorted { ($0.dueDate ?? "") < ($1.dueDate ?? "") }
    }

    /// "3,800,000 · paid 1,800,000 (bank) · due 30 Nov" (the method only when the payments are known).
    public static func invoiceLine(_ i: CreditInvoiceDTO) -> String {
        let paid = i.paid.value
        let how = OwnerMoneyWords.singleMethod(i).map { " (\(OwnerMoneyWords.method($0).lowercased()))" } ?? ""
        return [F.money(i.amount.value, currency: ""), paid > 0 ? "paid \(F.money(paid, currency: ""))\(how)" : nil,
                "due \(F.day(i.dueDate))"].compactMap { $0 }.joined(separator: " · ")
    }
}

// MARK: - Machines

/// One machine of the week (design: "300 h · 220 productive · last reading 1,510 h (pending)").
public struct OwnerMachineWeek: Sendable, Equatable, Identifiable {
    public enum Open: Sendable, Equatable { case machine(UUID), report(UUID) }
    public let id: UUID
    public let title: String
    /// The supervisor's first name (not overdue).
    public let supervisor: String?
    public let overdue: OverdueMachine?
    public let detail: String
    public let hours: Decimal
    public let productive: Decimal
    public let nonProductive: Decimal
    /// Where a tap leads: the machine (fleet) or its report waiting.
    public let open: Open?
}

public enum OwnerMachinesParity {
    public static let noMachines = "No machines to show."
    public static let mapEmpty = "No machine has a known position."

    public static func mapAccessibility(_ n: Int) -> String { "Map with \(n) machines. Use the List for details." }
    public static func tracker(engine: String, motion: String) -> String {
        "Tracker: engine \(engine.lowercased()) · \(motion.lowercased())"
    }

    /// "Last approved reading 1,510 h" or that there is none yet.
    public static func overdueDetail(_ s: MachineReportStatusDTO) -> String {
        s.lastApprovedReading.map { "Last approved reading \(F.formatHours($0.value)) h" } ?? "No approved reading yet"
    }

    /// Every machine with a report status or a report this week (rejected reports left out); overdue ones first, then
    /// by hours. Overdue follows ``OverdueMachine`` on the tenant's reminder days.
    public static func rows(statuses: [MachineReportStatusDTO], reports: [MachineReportDTO], fleet: [MachineMapDTO],
                            fleetOn: Bool, tracking: Bool, machineReports: Bool, reminderDays: Int?) -> [OwnerMachineWeek] {
        let counted = reports.filter { $0.state != .rejected }
        let byMachine = Dictionary(grouping: counted, by: \.machineID)
        let fleetByID = Dictionary(fleet.map { ($0.machineID, $0) }, uniquingKeysWith: { a, _ in a })
        var ids: [UUID] = []
        for id in statuses.map(\.machineID) + counted.map(\.machineID) where !ids.contains(id) { ids.append(id) }
        let rows = ids.map { id -> OwnerMachineWeek in
            let status = statuses.first { $0.machineID == id }
            let week = byMachine[id] ?? []
            let map = fleetByID[id]
            let hours = week.reduce(Decimal(0)) { $0 + $1.hours.value }
            let productive = week.reduce(Decimal(0)) { $0 + $1.customerHours.value }
            let nonProductive = week.reduce(Decimal(0)) { $0 + $1.nonProductiveHours.value }
            let code = status?.machineCode ?? week.first?.machineCode ?? map?.assetCode ?? String(id.uuidString.prefix(8))
            let name = status?.machineName ?? week.first?.machineName ?? map?.name
            let overdue = status.flatMap { OverdueMachine.of($0, reminderDays: reminderDays) }
            let latest = week.max { $0.submittedAt < $1.submittedAt }
            let reading: String? = if let latest {
                "last reading \(F.formatHours(latest.endReading.value)) h" + (latest.state == .submitted ? " (pending)" : "")
            } else if let last = status?.lastApprovedReading {
                "last reading \(F.formatHours(last.value)) h"
            } else {
                nil
            }
            let detail: String
            if let status, overdue != nil, week.isEmpty {
                detail = map.flatMap { m in
                    tracking ? tracker(engine: OwnerFormat.humanize(m.observedEngine.rawValue),
                                       motion: OwnerFormat.humanize(m.observedMotion.rawValue)) : nil
                } ?? reading ?? overdueDetail(status)
            } else {
                detail = [F.hours(hours), "\(F.formatHours(productive)) productive", reading].compactMap { $0 }.joined(separator: " · ")
            }
            let open: OwnerMachineWeek.Open? = if fleetOn {
                .machine(id)
            } else if let pending = status?.pendingReportID, machineReports {
                .report(pending)
            } else {
                nil
            }
            let supervisor = map?.supervisor?.split(separator: " ").first.map(String.init)
            return OwnerMachineWeek(id: id, title: [code, name].compactMap { $0 }.joined(separator: " · "),
                                    supervisor: supervisor, overdue: overdue, detail: detail, hours: hours,
                                    productive: productive, nonProductive: nonProductive, open: open)
        }
        return rows.sorted { a, b in
            if (a.overdue != nil) != (b.overdue != nil) { return a.overdue != nil }
            if a.hours != b.hours { return a.hours > b.hours }
            return a.title < b.title
        }
    }
}

// MARK: - Money

public enum OwnerMoneyParity {
    public static let noSales = "No sales in this period."
    public static let noCash = "No supervisor holds cash."
    public static let noInvoices = "No open credit invoices."
    public static let overdueHandover = "Overdue to hand over"

    /// "Cash 5.4M · Bank 2.0M · Mobile 1.4M · Credit 3.8M" (methods with nothing left out).
    public static func methods(_ s: SoldByMethod) -> String {
        [("CASH", s.cash), ("BANK", s.bank), ("MOBILE_MONEY", s.mobileMoney), ("CREDIT", s.credit)]
            .filter { $0.1 > 0 }.map { "\(OwnerMoneyWords.method($0.0)) \(F.compact($0.1))" }.joined(separator: " · ")
    }

    /// Whether the period has any sale (orders not cancelled).
    public static func hasSales(_ orders: [HoursPurchaseDTO]) -> Bool { orders.contains { $0.cancelledAt == nil } }

    /// "Expenses" until the count is known, then "Expenses (3)".
    public static func expenses(_ n: Int?) -> String { "Expenses" + (n.map { " (\($0))" } ?? "") }

    /// The pill of an invoice (design: Part paid / Unpaid / Paid / Overdue / Cancelled).
    public static func pill(_ i: CreditInvoiceDTO) -> (label: String, tone: OwnerPillTone) {
        if i.status == "CANCELLED" { return ("Cancelled", .neutral) }
        if i.status == "PAID" { return ("Paid", .good) }
        if i.overdue { return ("Overdue", .bad) }
        if i.status == "PART_PAID" { return ("Part paid", .waiting) }
        return ("Unpaid", .waiting)
    }

    /// "INV-0042 · Msasani Bay".
    public static func invoiceTitle(_ i: CreditInvoiceDTO) -> String {
        [i.invoiceNumber, i.customerName].compactMap { $0 }.joined(separator: " · ")
    }

    /// "3.8M · paid 1.8M by bank · due 30 Nov" (the method only when the payments are known).
    public static func invoiceDetail(_ i: CreditInvoiceDTO) -> String {
        let paid = i.paid.value
        let method = OwnerMoneyWords.singleMethod(i).map { " by \(OwnerMoneyWords.method($0).lowercased())" } ?? ""
        return [F.compact(i.amount.value), paid > 0 ? "paid \(F.compact(paid))\(method)" : nil, "due \(F.day(i.dueDate))"]
            .compactMap { $0 }.joined(separator: " · ")
    }

    /// Invoices to show: open ones first (overdue, then by due date), then the paid ones; at most `max`.
    public static func invoices(_ all: [CreditInvoiceDTO], max: Int = 20) -> [CreditInvoiceDTO] {
        Array(all.filter { $0.status != "CANCELLED" }.sorted { a, b in
            let (pa, pb) = (a.status == "PAID", b.status == "PAID")
            if pa != pb { return !pa }
            if a.overdue != b.overdue { return a.overdue }
            return (a.dueDate ?? "") < (b.dueDate ?? "")
        }.prefix(max))
    }

    /// Whether a tap on an invoice row opens Record payment for it.
    public static func payable(_ i: CreditInvoiceDTO) -> Bool { i.balance.value > 0 && i.status != "CANCELLED" }

    /// Supervisors holding cash or with a hand-over awaiting the check, most held first.
    public static func cashRows(_ list: [CashSupervisorSummaryDTO]) -> [CashSupervisorSummaryDTO] {
        list.filter { $0.closingOutstanding.value != 0 || $0.claimedUnverifiedHandovers.value > 0 }
            .sorted { $0.closingOutstanding.value > $1.closingOutstanding.value }
    }

    /// "Overdue to hand over · 3 days" (or without days).
    public static func overdue(days: Int?) -> String {
        overdueHandover + (days.flatMap { $0 > 0 ? " · \(F.days($0))" : nil } ?? "")
    }

    /// A supervisor's cash line: overdue to hand over, else handed over and waiting for the office.
    public static func cashDetail(_ s: CashSupervisorSummaryDTO, overdue flag: RemittanceOverdueDTO?, today: Date = Date(),
                                  calendar: Calendar = .current) -> String? {
        if let flag {
            let days = flag.heldSince.flatMap {
                calendar.dateComponents([.day], from: calendar.startOfDay(for: $0), to: calendar.startOfDay(for: today)).day
            }
            return overdue(days: days)
        }
        let claimed = s.claimedUnverifiedHandovers.value
        return claimed > 0 ? MachineReportOwnerTexts.handedAwaiting(F.compact(claimed)) : nil
    }
}
