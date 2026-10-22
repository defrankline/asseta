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

    /// `14:05` today, `Mon 14:05` within the week, `3 Oct 14:05` otherwise.
    public static func timestamp(_ date: Date, now: Date = Date(), calendar: Calendar = .current,
                                 locale: Locale = .current) -> String {
        var cal = calendar
        cal.locale = locale
        let time = date.formatted(Date.FormatStyle(locale: locale, calendar: cal, timeZone: cal.timeZone)
            .hour(.twoDigits(amPM: .abbreviated)).minute(.twoDigits))
        if cal.isDate(date, inSameDayAs: now) { return time }
        let days = cal.dateComponents([.day], from: cal.startOfDay(for: date), to: cal.startOfDay(for: now)).day ?? 99
        let style = Date.FormatStyle(locale: locale, calendar: cal, timeZone: cal.timeZone)
        if days > 0 && days < 7 { return "\(date.formatted(style.weekday(.abbreviated))) \(time)" }
        return "\(date.formatted(style.day().month(.abbreviated))) \(time)"
    }

    /// The offline banner: `Offline — data from 14:05 (stale)`.
    public static func staleBanner(fetchedAt: Date, isOnline: Bool, now: Date = Date(), calendar: Calendar = .current,
                                   locale: Locale = .current) -> String {
        let when = timestamp(fetchedAt, now: now, calendar: calendar, locale: locale)
        return isOnline ? "Can't reach Asseta — data from \(when) (stale)" : "Offline — data from \(when) (stale)"
    }

    /// Freshness caption for a KPI section: `Updated 3 min ago` or `No data yet`.
    public static func sourceFreshness(_ latestSourceAt: Date?, now: Date = Date()) -> String {
        guard let latestSourceAt else { return "No data yet" }
        return "Latest data \(age(since: latestSourceAt, now: now))"
    }
}
