import Foundation

/// ADR-008 "time since last visit, and where": one wording for the Supervisor and Owner apps (same as Android and web).
public enum VisitTexts {
    /// The time between two visits from whole seconds (truncated): nil "First visit", "45 min", "5 h 20 min", "5 h",
    /// "1 day 3 h", "2 days".
    public static func duration(seconds: Int?) -> String {
        guard let seconds else { return firstVisit }
        let s = max(0, seconds)
        let minutes = s / 60, hours = s / 3600, days = s / 86400
        if hours < 1 { return "\(minutes) min" }
        if days < 1 {
            let m = minutes % 60
            return m == 0 ? "\(hours) h" : "\(hours) h \(m) min"
        }
        let h = hours % 24
        return "\(days) \(days == 1 ? "day" : "days")" + (h > 0 ? " \(h) h" : "")
    }

    /// Seconds from `from` to `to` (whole, truncated), nil without a start.
    public static func seconds(from: Date?, to: Date) -> Int? {
        from.map { Int(to.timeIntervalSince($0).rounded(.towardZero)) }
    }

    public static let firstVisit = "First visit"

    /// "17 Nov, 15:26": the phone's time zone, English month, 24-hour clock.
    public static func dayTime(_ date: Date, timeZone: TimeZone = .current) -> String {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = timeZone
        f.dateFormat = "d MMM, HH:mm"
        return f.string(from: date)
    }

    /// "Where: Mbezi Beach, Kinondoni (at Yard A) · -6.7924, 39.2083 (±5 m)"; parts that are missing are left out;
    /// nil without coordinates (no Where line at all).
    public static func whereLine(_ visit: VisitPoint?) -> String? {
        guard let visit, let point = visit.coordinate else { return nil }
        let place = visit.place?.trimmingCharacters(in: .whitespacesAndNewlines).nonEmptyValue
        let site = visit.siteName?.trimmingCharacters(in: .whitespacesAndNewlines).nonEmptyValue
        let named: String? = switch (place, site) {
        case let (place?, site?): "\(place) (at \(site))"
        case let (place?, nil): place
        case let (nil, site?): "at \(site)"
        case (nil, nil): nil
        }
        var coordinates = "\(coordinate(point.latitude)), \(coordinate(point.longitude))"
        if let accuracy = visit.accuracyM { coordinates += " (±\(Int(accuracy.rounded())) m)" }
        return "Where: " + [named, coordinates].compactMap { $0 }.joined(separator: " · ")
    }

    /// A coordinate with 4 decimals ("-6.7924").
    public static func coordinate(_ value: Double) -> String { String(format: "%.4f", locale: Locale(identifier: "en_US_POSIX"), value) }

    /// "Since last visit: 1 day 3 h" (or "First visit").
    public static func sinceLastVisit(seconds: Int?) -> String { "Since last visit: \(duration(seconds: seconds))" }

    /// "Time since last visit: 1 day 3 h (last visit 17 Nov, 15:26)", "Time since last visit: First visit".
    public static func timeSinceLastVisit(_ lastVisitAt: Date?, now: Date, timeZone: TimeZone = .current) -> String {
        guard let lastVisitAt else { return "Time since last visit: \(firstVisit)" }
        return "Time since last visit: \(duration(seconds: seconds(from: lastVisitAt, to: now))) (last visit \(dayTime(lastVisitAt, timeZone: timeZone)))"
    }

    /// "Last visit: 17 Nov, 15:26 · Where: …" (the Where part only with coordinates); nil without a previous visit.
    public static func lastVisitLine(_ visit: VisitPoint?, timeZone: TimeZone = .current) -> String? {
        guard let visit, let at = visit.at else { return nil }
        return (["Last visit: \(dayTime(at, timeZone: timeZone))", whereLine(visit)] as [String?]).compactMap { $0 }.joined(separator: " · ")
    }

    /// Apple Maps at the visit's coordinates (`http://maps.apple.com/?ll=lat,lng&q=…`), nil without coordinates.
    public static func mapsURL(_ visit: VisitPoint?) -> URL? {
        guard let visit, let point = visit.coordinate else { return nil }
        let ll = "\(coordinate(point.latitude)),\(coordinate(point.longitude))"
        let label = visit.place?.nonEmptyValue ?? visit.siteName?.nonEmptyValue ?? ll
        var components = URLComponents(string: "http://maps.apple.com/")
        components?.queryItems = [URLQueryItem(name: "ll", value: ll), URLQueryItem(name: "q", value: label)]
        return components?.url
    }

    /// The area label of a reverse-geocoded reading: neighbourhood / sub-locality, district (sub-administrative area),
    /// city / locality; missing parts skipped, equal parts once, never a street; at most 200 characters; nil when empty.
    public static func placeLabel(subLocality: String?, district: String?, locality: String?) -> String? {
        var parts: [String] = []
        for part in [subLocality, district, locality] {
            guard let text = part?.trimmingCharacters(in: .whitespacesAndNewlines), !text.isEmpty else { continue }
            if !parts.contains(where: { $0.caseInsensitiveCompare(text) == .orderedSame }) { parts.append(text) }
        }
        let label = String(parts.joined(separator: ", ").prefix(200)).trimmingCharacters(in: .whitespacesAndNewlines)
        return label.isEmpty ? nil : label
    }
}

private extension String {
    var nonEmptyValue: String? { isEmpty ? nil : self }
}
