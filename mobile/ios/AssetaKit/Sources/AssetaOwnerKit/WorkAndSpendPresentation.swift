import AssetaModel
import Foundation

// Screen content of the job work log, field spend (expenses and fuel), meter exceptions, cash with supervisors and
// meter reset decisions. The Android Owner app keeps the same strings and rules; `WorkAndSpendPresentationTests`
// (both platforms) pin them. Change both.

/// A coloured label on a row; the UI maps the tone to a colour (the text always says what it is).
public struct TextPill: Equatable, Sendable {
    public let text: String
    public let tone: KPITone
}

/// One list row: title, a secondary line, an optional right-aligned figure, pills and a note below.
public struct RecordRow: Equatable, Sendable {
    public let title: String
    public let detail: String
    public var trailing: String?
    public var pills: [TextPill] = []
    public var note: String?
    /// The job the record belongs to (the row opens it when the role can see jobs).
    public var jobID: UUID?
}

extension OwnerFormat {
    /// `22 Oct 2026` in `timeZone` (English month), the date half of `stamp`.
    public static func date(_ date: Date, timeZone: TimeZone = .current) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = timeZone
        f.dateFormat = "d MMM yyyy"
        return f.string(from: date)
    }

    /// A decimal with at most `fractionDigits` digits and no trailing zeros, locale-independent: `2.5`, `120`.
    public static func plain(_ value: Decimal, fractionDigits: Int = 2) -> String {
        var input = value
        var rounded = Decimal()
        NSDecimalRound(&rounded, &input, fractionDigits, .plain)
        return NSDecimalString(&rounded, Locale(identifier: "en_US_POSIX"))
    }
}

// MARK: - Job work log

public enum WorkLogText {
    public static let title = "Work log"
    public static let empty = "No work logged yet."

    /// Whole minutes between start and end (or `now` while ongoing) as hours: `2.5 h`.
    public static func duration(from start: Date, to end: Date) -> String {
        let minutes = max(0, Int(end.timeIntervalSince(start) / 60))
        return "\(OwnerFormat.plain(Decimal(minutes) / 60)) h"
    }

    /// "Work" · "22 Oct 2026, 08:00 – 22 Oct 2026, 10:30 · 2.5 h" · Billable / Not billable.
    public static func row(_ a: ActivityDTO, now: Date = Date(), timeZone: TimeZone = .current) -> RecordRow {
        let end = a.endedAt.map { OwnerFormat.stamp($0, timeZone: timeZone) } ?? "ongoing"
        return RecordRow(
            title: OwnerFormat.humanize(a.activityType),
            detail: "\(OwnerFormat.stamp(a.startedAt, timeZone: timeZone)) – \(end) · \(duration(from: a.startedAt, to: a.endedAt ?? now))",
            pills: [a.billable ? TextPill(text: "Billable", tone: .good) : TextPill(text: "Not billable", tone: .muted)],
            note: a.note
        )
    }
}

// MARK: - Field spend (expenses and fuel)

public enum SpendText {
    public static let title = "Field spend"
    public static let expensesTitle = "Expenses"
    public static let fuelTitle = "Fuel"
    /// The two halves of the Field spend screen.
    public static let kinds: [(Bool, String)] = [(false, expensesTitle), (true, fuelTitle)]
    /// Expense filter: pending only or all (the screen opens on all).
    public static let expenseFilters: [(Bool, String)] = [(true, "Pending"), (false, "All")]
    public static let defaultPendingOnly = false
    /// The server's `ExpenseStatus` value of an expense awaiting a decision.
    public static let pendingStatus = "PENDING_APPROVAL"
    public static let jobExpensesEmpty = "No expenses on this job."
    public static let jobFuelEmpty = "No fuel recorded on this job."
    public static let expensesEmpty = "No expenses yet."
    public static let fuelEmpty = "No fuel recorded yet."

    public static func expenseTone(_ status: String) -> KPITone {
        switch status {
        case "PENDING", "SUBMITTED", "PENDING_APPROVAL": .warning
        case "APPROVED": .good
        case "REJECTED": .critical
        default: .muted
        }
    }

    /// "Diesel" · "Puma · 22 Oct 2026" · amount · status pill · decision note.
    public static func expenseRow(_ e: ExpenseDTO, timeZone: TimeZone = .current,
                                  money: (DecimalString, String) -> String = { OwnerFormat.money($0, currency: $1) })
        -> RecordRow {
        RecordRow(title: e.description, detail: prefixed(e.supplier, OwnerFormat.date(e.incurredAt, timeZone: timeZone)),
                  trailing: money(e.amount, e.currency),
                  pills: [TextPill(text: OwnerFormat.humanize(e.status), tone: expenseTone(e.status))],
                  note: e.decisionNote, jobID: e.jobID)
    }

    /// "Total approved: TZS 150,000.00", one line per currency (sorted); none when nothing is approved.
    public static func totalApproved(_ items: [ExpenseDTO],
                                     money: (Decimal, String) -> String = { OwnerFormat.money($0, currency: $1) }) -> [String] {
        var sums: [String: Decimal] = [:]
        for e in items where e.status == "APPROVED" { sums[e.currency, default: 0] += e.amount.value }
        return sums.keys.sorted().map { "Total approved: \(money(sums[$0] ?? 0, $0))" }
    }

    /// "Purchase · 120.5 L" · "Puma · 22 Oct 2026" · attributed cost.
    public static func fuelRow(_ f: FuelEventDTO, timeZone: TimeZone = .current,
                               money: (DecimalString, String) -> String = { OwnerFormat.money($0, currency: $1) })
        -> RecordRow {
        RecordRow(title: "\(OwnerFormat.humanize(f.eventType)) · \(f.litres.description) L",
                  detail: prefixed(f.supplier, OwnerFormat.date(f.occurredAt, timeZone: timeZone)),
                  trailing: money(f.attributedCost, f.currency), jobID: f.jobID)
    }

    static func prefixed(_ head: String?, _ text: String) -> String {
        guard let head, !head.isEmpty else { return text }
        return "\(head) · \(text)"
    }
}

// MARK: - Meter exceptions

public enum ExceptionText {
    public static let title = "Meter exceptions"
    /// Open only (the default) or all.
    public static let filters: [(Bool, String)] = [(true, "Open"), (false, "All")]
    public static let defaultOpenOnly = true

    public static func empty(openOnly: Bool) -> String { openOnly ? "No open exceptions." : "No exceptions." }

    /// "Hours exceed window" · "High · 22 Oct 2026, 08:00" · Blocking · Explained/Confirmed · review note.
    public static func row(_ x: MeterExceptionDTO, timeZone: TimeZone = .current) -> RecordRow {
        var pills: [TextPill] = []
        if x.blocking { pills.append(TextPill(text: "Blocking", tone: .critical)) }
        if x.status != "OPEN" {
            let tone: KPITone = switch x.status {
            case "EXPLAINED": .good
            case "CONFIRMED": .critical
            default: .muted
            }
            pills.append(TextPill(text: OwnerFormat.humanize(x.status), tone: tone))
        }
        return RecordRow(title: OwnerFormat.humanize(x.exceptionType),
                         detail: "\(OwnerFormat.humanize(x.severity)) · \(OwnerFormat.stamp(x.createdAt, timeZone: timeZone))",
                         pills: pills, note: x.reviewNote, jobID: x.jobID)
    }
}

// MARK: - Cash with supervisors

/// Period of the cash summary, in local days ending today.
public enum CashPeriod: String, CaseIterable, Sendable {
    case today = "TODAY", week = "WEEK", month = "MONTH"

    public var label: String {
        switch self {
        case .today: "Today"
        case .week: "7 days"
        case .month: "This month"
        }
    }
}

public struct CashLine: Equatable, Sendable {
    public let label: String
    public let value: String
    public var tone: KPITone = .normal
}

/// One supervisor x currency: who, what they hold, and how it adds up.
public struct CashCard: Equatable, Sendable, Identifiable {
    public let id: String
    public let title: String
    public let holding: String
    public let lines: [CashLine]
    /// Whose cash it is and in which currency (where "Issue float" sends the float).
    public var staffMemberID: UUID?
    public var currency: String?
}

public enum CashText {
    public static let title = "Cash with supervisors"
    public static let holdingLabel = "Holding"
    public static let defaultPeriod = CashPeriod.today
    public static let empty = "No supervisor cash in this period."
    public static let footer = "Holding = opening + floats + collections − approved spending − verified handovers."

    /// `from`/`to` as `YYYY-MM-DD` local days: today; today and the 6 days before; the 1st of the month to today.
    public static func range(_ period: CashPeriod, now: Date = Date(), calendar: Calendar = .current) -> (from: String, to: String) {
        let today = calendar.startOfDay(for: now)
        let start: Date = switch period {
        case .today: today
        case .week: calendar.date(byAdding: .day, value: -6, to: today) ?? today
        case .month: calendar.date(from: calendar.dateComponents([.year, .month], from: today)) ?? today
        }
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.calendar = Calendar(identifier: .gregorian)
        f.timeZone = calendar.timeZone
        f.dateFormat = "yyyy-MM-dd"
        return (f.string(from: start), f.string(from: today))
    }

    /// Cards, largest holding first; the "awaiting" lines appear only when above zero.
    public static func cards(_ items: [CashSupervisorSummaryDTO],
                             money: (DecimalString, String) -> String = { OwnerFormat.money($0, currency: $1) }) -> [CashCard] {
        items.sorted { $0.closingOutstanding.value > $1.closingOutstanding.value }.map { s in
            var lines = [
                CashLine(label: "Opening", value: money(s.opening, s.currency)),
                CashLine(label: "Floats issued", value: money(s.floatsIssued, s.currency)),
                CashLine(label: "Collections", value: money(s.collections, s.currency)),
                CashLine(label: "Approved spending", value: money(s.approvedSpending, s.currency)),
                CashLine(label: "Handed over (verified)", value: money(s.verifiedHandovers, s.currency)),
            ]
            let awaiting = [
                ("Spending awaiting approval", s.pendingSpending),
                ("Handovers awaiting verification", s.claimedUnverifiedHandovers),
                ("Collections awaiting verification", s.unverifiedCollections),
            ]
            lines += awaiting.filter { $0.1.value > 0 }.map {
                CashLine(label: $0.0, value: money($0.1, s.currency), tone: .warning)
            }
            return CashCard(id: s.id, title: s.staffName, holding: money(s.closingOutstanding, s.currency), lines: lines,
                            staffMemberID: s.staffMemberID, currency: s.currency)
        }
    }
}

// MARK: - Meter resets

public enum MeterResetText {
    public static let sectionTitle = "Meter resets"
    public static let title = "Meter reset"
    public static let empty = "No meter resets waiting."
    public static let notFound = "Meter reset not found"
    public static let noteLabel = "Note (required)"
    public static let approve = "Approve reset"
    public static let reject = "Reject reset"
    public static let approved = "Reset approved."
    public static let rejected = "Reset rejected."
    public static let alreadyDecided = "This reset was already decided."
    public static let ownRequest = "You requested this reset, so someone else must decide it."
    public static let pendingStatus = "PENDING"
    /// The server accepts notes of 5 to 2000 characters.
    public static let minNoteLength = 5

    public static func canDecide(note: String) -> Bool {
        note.trimmingCharacters(in: .whitespacesAndNewlines).count >= minNoteLength
    }

    /// "1250.5 → 0 · effective 22 Oct 2026, 08:00"
    public static func detail(_ r: MeterResetDTO, timeZone: TimeZone = .current) -> String {
        "\(r.oldReading.description) → \(r.newReading.description) · effective \(OwnerFormat.stamp(r.effectiveAt, timeZone: timeZone))"
    }

    public static func statusTone(_ status: String) -> KPITone {
        switch status {
        case "PENDING": .warning
        case "APPROVED": .good
        case "REJECTED": .critical
        default: .muted
        }
    }

    public static func done(approve: Bool) -> String { approve ? approved : rejected }
}
