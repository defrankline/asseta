import AssetaModel
import Foundation

/// Display formatting for the Owner app. Money is formatted from `Decimal` (never `Double`) with
/// the currency's own minor units; times are shown in the device's time zone.
public enum OwnerFormat {
    public static func money(_ amount: DecimalString, currency: String, locale: Locale = .current) -> String {
        money(amount.value, currency: currency, locale: locale)
    }

    public static func money(_ amount: Decimal, currency: String, locale: Locale = .current) -> String {
        guard currency.count == 3, currency.allSatisfy({ $0.isASCII && $0.isLetter }) else {
            return "\(amount.formatted(.number.locale(locale))) \(currency)"
        }
        return amount.formatted(.currency(code: currency.uppercased()).locale(locale))
    }

    /// Hours from a decimal string, e.g. `12.5 h`; `—` when absent.
    public static func hours(_ value: DecimalString?, locale: Locale = .current) -> String {
        guard let value else { return "—" }
        return "\(value.value.formatted(.number.precision(.fractionLength(0...2)).locale(locale))) h"
    }

    public static func kilometres(_ value: Double, locale: Locale = .current) -> String {
        "\(value.formatted(.number.precision(.fractionLength(0...1)).locale(locale))) km"
    }

    /// Compact relative age: `just now`, `4 min ago`, `3 h ago`, `2 d ago`.
    public static func age(seconds: Int) -> String {
        let s = max(0, seconds)
        switch s {
        case ..<60: return "just now"
        case ..<3600: return "\(s / 60) min ago"
        case ..<86_400: return "\(s / 3600) h ago"
        default: return "\(s / 86_400) d ago"
        }
    }

    public static func age(since date: Date, now: Date) -> String {
        age(seconds: Int(now.timeIntervalSince(date)))
    }

    /// `22 Oct 2026, 14:05` in `calendar`'s time zone: the same absolute stamp the Android Owner app shows, so a
    /// figure reads identically on both phones. (`now` and `locale` are kept for call-site compatibility.)
    public static func timestamp(_ date: Date, now: Date = Date(), calendar: Calendar = .current,
                                 locale: Locale = .current) -> String {
        stamp(date, timeZone: calendar.timeZone)
    }

    /// `22 Oct 2026, 14:05` in `timeZone` (English month, 24 h clock), as `OwnerFormat.dateTime` on Android.
    public static func stamp(_ date: Date, timeZone: TimeZone = .current) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = timeZone
        f.dateFormat = "d MMM yyyy, HH:mm"
        return f.string(from: date)
    }

    /// Server enum values (`TRACKER_OFFLINE`) as words (`Tracker offline`), as `OwnerFormat.humanize` on Android.
    public static func humanize(_ raw: String) -> String {
        let text = raw.lowercased().replacingOccurrences(of: "_", with: " ")
        return text.prefix(1).uppercased() + text.dropFirst()
    }

    /// The offline banner: `Offline — data from 14:05 (stale)`.
    public static func staleBanner(fetchedAt: Date, isOnline: Bool, now: Date = Date(), calendar: Calendar = .current,
                                   locale: Locale = .current) -> String {
        let when = timestamp(fetchedAt, now: now, calendar: calendar, locale: locale)
        return isOnline ? "Can't reach Asseta — data from \(when) (stale)" : "Offline — data from \(when) (stale)"
    }

    /// Freshness caption for a KPI section: `Source data updated 3 min ago` or `No source data yet` (Android wording).
    public static func sourceFreshness(_ latestSourceAt: Date?, now: Date = Date()) -> String {
        guard let latestSourceAt else { return "No source data yet" }
        return "Source data updated \(age(since: latestSourceAt, now: now))"
    }
}
