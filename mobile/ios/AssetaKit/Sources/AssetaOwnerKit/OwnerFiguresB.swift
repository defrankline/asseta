import Foundation

/// ADR-008 figures as the designs write them (Android `ui/common/Figures.kt`): compact money ("5.2M", "3.85M", "850,000"),
/// whole money ("TZS 3,800,000"), hours ("300 h", "12.5 h"), percentages and "30 Nov" days. en-US digits always.
public enum OwnerFiguresB {
    private static let posix = Locale(identifier: "en_US_POSIX")
    private static let million = Decimal(1_000_000)
    private static let billion = Decimal(1_000_000_000)

    private static func format(_ value: Decimal, min: Int, max: Int, grouping: Bool = true) -> String {
        let f = NumberFormatter()
        f.locale = posix
        f.numberStyle = .decimal
        f.usesGroupingSeparator = grouping
        f.groupingSeparator = ","
        f.groupingSize = 3
        f.decimalSeparator = "."
        f.minimumFractionDigits = min
        f.maximumFractionDigits = max
        f.roundingMode = .halfUp
        return f.string(from: NSDecimalNumber(decimal: value)) ?? "\(value)"
    }

    private static func rounded(_ value: Decimal, _ scale: Int) -> Decimal {
        var v = value, out = Decimal()
        NSDecimalRound(&out, &v, scale, .plain)
        return out
    }

    /// A decimal string from the wire; blank or malformed counts as 0.
    public static func dec(_ raw: String?) -> Decimal {
        guard let raw = raw?.trimmingCharacters(in: .whitespaces), !raw.isEmpty else { return 0 }
        return Decimal(string: raw, locale: posix) ?? 0
    }

    /// Compact money: from a million "5.2M" / "3.85M" / "2.0M" (one or two decimals), from a billion "1.2B", below a
    /// million the grouped whole amount ("850,000").
    public static func compact(_ value: Decimal) -> String {
        let a = abs(value)
        let sign = value < 0 ? "-" : ""
        if a >= billion { return sign + format(rounded(a / billion, 2), min: 1, max: 2) + "B" }
        if a >= million { return sign + format(rounded(a / million, 2), min: 1, max: 2) + "M" }
        return sign + format(rounded(a, 0), min: 0, max: 0)
    }

    /// "TZS 3,800,000" (whole amounts) or "TZS 3,800,000.50" (cents only when there are some). An empty currency gives
    /// the bare amount.
    public static func money(_ value: Decimal, currency: String) -> String {
        let whole = rounded(value, 0) == value
        let amount = whole ? format(value, min: 0, max: 0) : format(rounded(value, 2), min: 2, max: 2)
        return currency.isEmpty ? amount : "\(currency) \(amount)"
    }

    /// Hours without trailing zeros, at most two decimals ("1,510", "3,182.8").
    public static func formatHours(_ value: Decimal) -> String { format(value, min: 0, max: 2) }

    /// "300 h", "12.5 h", "1,240 h".
    public static func hours(_ value: Decimal) -> String { "\(formatHours(value)) h" }

    /// Whole percent of `part` in `whole` ("73%"); nil when `whole` is 0.
    public static func percent(_ part: Decimal, of whole: Decimal) -> String? {
        guard whole > 0 else { return nil }
        return "\(format(rounded(part * 100 / whole, 0), min: 0, max: 0, grouping: false))%"
    }

    /// "30 Nov" from a local date (`yyyy-MM-dd`); the raw text when malformed; "—" without one.
    public static func day(_ raw: String?) -> String {
        guard let raw else { return "—" }
        let parse = DateFormatter()
        parse.calendar = Calendar(identifier: .gregorian)
        parse.locale = posix
        parse.timeZone = TimeZone(identifier: "UTC")
        parse.dateFormat = "yyyy-MM-dd"
        guard let date = parse.date(from: raw) else { return raw }
        let out = DateFormatter()
        out.calendar = Calendar(identifier: .gregorian)
        out.locale = Locale(identifier: "en_US")
        out.timeZone = TimeZone(identifier: "UTC")
        out.dateFormat = "d MMM"
        return out.string(from: date)
    }

    /// "3 days" / "1 day".
    public static func days(_ n: Int) -> String { n == 1 ? "1 day" : "\(n) days" }
}
