import AssetaModel
import Foundation

/// The last successful "Today" reconciliation (every currency), saved in the encrypted store so the
/// Money tab can show the office's figures offline. Cleared with the tenant's state on account switch.
public struct CashTodaySnapshot: Codable, Hashable, Sendable {
    public let rows: [CashReconciliationDTO]
    public let fetchedAt: Date
    /// Local date (`yyyy-MM-dd`) the figures are for.
    public let day: String

    public init(rows: [CashReconciliationDTO], fetchedAt: Date, day: String) {
        self.rows = rows
        self.fetchedAt = fetchedAt
        self.day = day
    }

    enum CodingKeys: String, CodingKey { case rows, day, fetchedAt = "fetched_at" }

    /// The latest day of `currency` in the snapshot.
    public func day(currency: String) -> CashReconciliationDayDTO? {
        rows.first { $0.currency == currency }?.days.last
    }
}

/// Which "Today" figures the Money tab shows for one currency. Same rules and wording as Android
/// `CashToday`.
public enum CashToday: Equatable, Sendable {
    /// Fresh from the office (online).
    case live(CashReconciliationDayDTO)
    /// Offline, saved earlier today: the full figures, labelled with the fetch time.
    case savedToday(CashReconciliationDayDTO, asOf: Date)
    /// Offline, saved on an earlier day: that day's outstanding next to the estimate.
    case savedEarlier(CashReconciliationDayDTO, day: String)
    /// Nothing from the office: the estimate only.
    case estimate

    public static let savedTodayFooter = "Office figures from the last time this phone was online. Not updated while offline."
    public static let unsyncedHeader = "Recorded on this phone, not yet synced"

    /// `live` is the per-currency result of the last fetch, or nil when it failed (offline / error); only
    /// then is the saved snapshot used. `today` is the local `yyyy-MM-dd`.
    public static func select(live: [String: CashReconciliationDayDTO]?, snapshot: CashTodaySnapshot?, currency: String,
                              today: String) -> CashToday {
        if let live { return live[currency].map(CashToday.live) ?? .estimate }
        guard let snapshot, let day = snapshot.day(currency: currency) else { return .estimate }
        return snapshot.day == today ? .savedToday(day, asOf: snapshot.fetchedAt) : .savedEarlier(day, day: snapshot.day)
    }

    public func header(timeZone: TimeZone = .current) -> String {
        switch self {
        case .live: "Today"
        case let .savedToday(_, asOf): "Today (as of \(Self.format(asOf, "HH:mm", timeZone)))"
        case let .savedEarlier(_, day): "Last office figures (\(Self.displayDay(day)))"
        case .estimate: "Today (estimate)"
        }
    }

    public var footer: String {
        switch self {
        case .live: InboxTexts.reconciliationFooter
        case .savedToday: Self.savedTodayFooter
        case .savedEarlier, .estimate: InboxTexts.estimateFooter
        }
    }

    /// Local `yyyy-MM-dd` of `date` (the reconciliation's `date` parameter).
    public static func localDay(_ date: Date, timeZone: TimeZone = .current) -> String {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = timeZone
        let parts = calendar.dateComponents([.year, .month, .day], from: date)
        return String(format: "%04d-%02d-%02d", parts.year ?? 0, parts.month ?? 0, parts.day ?? 0)
    }

    /// `2026-10-22` → `22 Oct 2026` (the text itself when it is not a date).
    static func displayDay(_ day: String) -> String {
        let utc = TimeZone(identifier: "UTC")!
        let parser = formatter("yyyy-MM-dd", utc)
        guard let date = parser.date(from: day) else { return day }
        return formatter("d MMM yyyy", utc).string(from: date)
    }

    private static func format(_ date: Date, _ pattern: String, _ timeZone: TimeZone) -> String {
        formatter(pattern, timeZone).string(from: date)
    }

    private static func formatter(_ pattern: String, _ timeZone: TimeZone) -> DateFormatter {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.calendar = Calendar(identifier: .gregorian)
        f.timeZone = timeZone
        f.dateFormat = pattern
        return f
    }
}

extension CashLine {
    /// This phone has cash records of this currency the server has not confirmed yet.
    public var hasUnsyncedCash: Bool { pendingCollections > 0 || pendingHandovers > 0 || pendingCashExpenses > 0 }
}
