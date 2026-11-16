import Foundation

/// ADR-008 figures as the designs write them: compact money ("5.2M", "3.85M", "2.0M owed"), whole money
/// ("TZS 3,800,000"), hours ("300 h", "12.5 h"), percentages and "today 07:40" style times. Same rules as Android
/// `ui/common/Figures.kt` (English number format, whatever the phone's region).
public enum OwnerFigures {
    /// A period of local days (both ends included).
    public struct DayRange: Equatable, Sendable {
        public let from: Date
        public let to: Date
    }

    /// The Today / Week / Month choice of Money and Reports.
    public enum Period: String, CaseIterable, Sendable {
        case today, week, month

        public var label: String {
            switch self {
            case .today: "Today"
            case .week: "Week"
            case .month: "Month"
            }
        }

        /// The local days of this period up to `today`: the week starts on Monday, the month on the 1st.
        public func range(today: Date, calendar: Calendar = .current) -> DayRange {
            let day = calendar.startOfDay(for: today)
            switch self {
            case .today:
                return DayRange(from: day, to: day)
            case .week:
                let weekday = calendar.component(.weekday, from: day) // 1 = Sunday … 7 = Saturday
                let back = (weekday + 5) % 7 // days since Monday
                return DayRange(from: calendar.date(byAdding: .day, value: -back, to: day) ?? day, to: day)
            case .month:
                let start = calendar.date(from: calendar.dateComponents([.year, .month], from: day)) ?? day
                return DayRange(from: start, to: day)
            }
        }
    }

    private static let english = Locale(identifier: "en_US_POSIX")
    private static let million = Decimal(1_000_000)
    private static let billion = Decimal(1_000_000_000)

    /// A decimal string from the wire; blank or malformed counts as 0.
    public static func dec(_ raw: String?) -> Decimal {
        guard let text = raw?.trimmingCharacters(in: .whitespaces), !text.isEmpty,
              let value = Decimal(string: text, locale: english) else { return 0 }
        return value
    }

    /// Sum of decimal strings.
    public static func sum(_ values: [String?]) -> Decimal { values.reduce(Decimal(0)) { $0 + dec($1) } }

    /// Compact money: from a million "5.2M" / "3.85M" / "2.0M" (at most two decimals, at least one), from a billion
    /// "1.2B", below a million the grouped whole amount ("850,000").
    public static func compactMoney(_ value: Decimal) -> String {
        let magnitude = abs(value)
        let sign = value < 0 ? "-" : ""
        func scaled(_ divisor: Decimal, _ suffix: String) -> String {
            sign + format(round(magnitude / divisor, 2), minFraction: 1, maxFraction: 2) + suffix
        }
        if magnitude >= billion { return scaled(billion, "B") }
        if magnitude >= million { return scaled(million, "M") }
        return sign + format(round(magnitude, 0), minFraction: 0, maxFraction: 0)
    }

    /// "TZS 3,800,000" (whole amounts) or "TZS 3,800,000.50" (cents only when there are some). An empty currency gives
    /// the bare amount.
    public static func money(_ value: Decimal, currency: String) -> String {
        let amount = round(value, 0) == value
            ? format(value, minFraction: 0, maxFraction: 0)
            : format(round(value, 2), minFraction: 2, maxFraction: 2)
        return currency.isEmpty ? amount : "\(currency) \(amount)"
    }

    /// Hours without trailing zeros, grouped ("300", "12.5", "1,240"; at most two decimals).
    public static func hoursNumber(_ value: Decimal) -> String {
        format(value, minFraction: 0, maxFraction: 2, rounding: .halfEven)
    }

    /// "300 h", "12.5 h", "1,240 h".
    public static func hours(_ value: Decimal) -> String { "\(hoursNumber(value)) h" }

    /// Whole percent of `part` in `whole` ("73%"); nil when `whole` is 0.
    public static func percent(_ part: Decimal, of whole: Decimal) -> String? {
        guard whole > 0 else { return nil }
        return "\(format(round(part * 100 / whole, 0), minFraction: 0, maxFraction: 0))%"
    }

    /// "today 07:40", "yesterday 18:10", "2 days ago" (up to 6 days), then "12 Nov"; "—" without a time.
    public static func relative(_ date: Date?, now: Date = Date(), timeZone: TimeZone = .current) -> String {
        guard let date else { return "—" }
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = timeZone
        let days = calendar.dateComponents([.day], from: calendar.startOfDay(for: date), to: calendar.startOfDay(for: now)).day ?? 0
        switch days {
        case 0: return "today \(stamp(date, "HH:mm", timeZone))"
        case 1: return "yesterday \(stamp(date, "HH:mm", timeZone))"
        case 2...6: return "\(days) days ago"
        default: return stamp(date, "d MMM", timeZone)
        }
    }

    /// "30 Nov" from a local date (`yyyy-MM-dd`); the raw text when malformed, "—" without one.
    public static func day(_ raw: String?) -> String {
        guard let raw else { return "—" }
        let parse = DateFormatter()
        parse.locale = english
        parse.timeZone = TimeZone(identifier: "UTC")
        parse.dateFormat = "yyyy-MM-dd"
        guard let date = parse.date(from: raw) else { return raw }
        return stamp(date, "d MMM", TimeZone(identifier: "UTC") ?? .current)
    }

    /// "3 days" / "1 day".
    public static func days(_ n: Int) -> String { n == 1 ? "1 day" : "\(n) days" }

    // MARK: - Helpers

    private static func round(_ value: Decimal, _ scale: Int) -> Decimal {
        var input = value
        var result = Decimal()
        NSDecimalRound(&result, &input, scale, .plain)
        return result
    }

    private static func format(_ value: Decimal, minFraction: Int, maxFraction: Int,
                               rounding: NumberFormatter.RoundingMode = .halfUp) -> String {
        let f = NumberFormatter()
        f.locale = english
        f.numberStyle = .decimal
        f.usesGroupingSeparator = true
        f.groupingSeparator = ","
        f.decimalSeparator = "."
        f.minimumFractionDigits = minFraction
        f.maximumFractionDigits = maxFraction
        f.roundingMode = rounding
        return f.string(from: NSDecimalNumber(decimal: value)) ?? "\(value)"
    }

    private static func stamp(_ date: Date, _ pattern: String, _ timeZone: TimeZone) -> String {
        let f = DateFormatter()
        f.locale = english
        f.timeZone = timeZone
        f.dateFormat = pattern
        return f.string(from: date)
    }
}
