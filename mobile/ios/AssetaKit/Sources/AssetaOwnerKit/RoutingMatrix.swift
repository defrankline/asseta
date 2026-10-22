import AssetaModel
import Foundation

/// The user's push priority matrix: push on/off per notification category × severity, as returned
/// by `GET /tenant/notification-routing`. Cells whose PUSH channel is mandatory cannot be turned
/// off. ``changes(from:)`` yields only the cells the user actually changed.
public struct RoutingMatrix: Equatable, Sendable {
    public struct Cell: Hashable, Sendable {
        public let category: String
        public let severity: AlertSeverity
    }

    /// Server category order (unknown future categories are appended alphabetically).
    public static let knownCategories = ["ACTION", "REMINDER", "ANOMALY", "BILLING", "INFO"]
    public static let severities: [AlertSeverity] = [.critical, .warning, .info]

    public private(set) var rows: [Cell: NotificationRoutingDTO]

    public init(_ routing: [NotificationRoutingDTO]) {
        var rows: [Cell: NotificationRoutingDTO] = [:]
        for row in routing { rows[Cell(category: row.category, severity: row.severity)] = row }
        self.rows = rows
    }

    public var categories: [String] {
        let present = Set(rows.keys.map(\.category))
        return Self.knownCategories.filter(present.contains) + present.subtracting(Self.knownCategories).sorted()
    }

    public func row(_ category: String, _ severity: AlertSeverity) -> NotificationRoutingDTO? {
        rows[Cell(category: category, severity: severity)]
    }

    public func isPushOn(_ category: String, _ severity: AlertSeverity) -> Bool {
        row(category, severity)?.push ?? false
    }

    public func isPushLocked(_ category: String, _ severity: AlertSeverity) -> Bool {
        row(category, severity)?.mandatoryChannels.contains("PUSH") ?? true
    }

    /// Sets push for one cell. Returns false (and changes nothing) for a missing or locked cell.
    @discardableResult
    public mutating func setPush(_ on: Bool, category: String, severity: AlertSeverity) -> Bool {
        let cell = Cell(category: category, severity: severity)
        guard let row = rows[cell], !isPushLocked(category, severity) else { return false }
        rows[cell] = NotificationRoutingDTO(category: row.category, severity: row.severity, push: on, email: row.email,
                                            inApp: row.inApp, mandatoryChannels: row.mandatoryChannels,
                                            source: row.source)
        return true
    }

    /// Cells that differ from `original`, in a stable order (email is sent unchanged).
    public func changes(from original: RoutingMatrix) -> [NotificationRoutingChangeIn] {
        rows.compactMap { cell, row -> NotificationRoutingChangeIn? in
            guard let before = original.rows[cell], before.push != row.push else { return nil }
            return NotificationRoutingChangeIn(category: cell.category, severity: cell.severity, push: row.push,
                                               email: row.email)
        }
        .sorted { ($0.category, -$0.severity.rank) < ($1.category, -$1.severity.rank) }
    }

    /// Human label for a category.
    public static func label(_ category: String) -> String {
        switch category {
        case "ACTION": "Needs your action"
        case "REMINDER": "Reminders"
        case "ANOMALY": "Anomalies & alerts"
        case "BILLING": "Billing"
        case "INFO": "Information"
        default: category.capitalized
        }
    }
}
