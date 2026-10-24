import AssetaModel
import Foundation

/// A screen of the Owner app that a notification can open.
public enum OwnerRoute: Hashable, Sendable {
    case fleet
    case jobs
    case investigations
    case machine(UUID)
    case alert(UUID)
    case alerts
    case approval(UUID)
    case approvals
    case investigation(UUID)
    case job(UUID)
    /// Meter exceptions, optionally only those of one job.
    case exceptions(jobID: UUID?)
    /// Expenses and fuel recorded in the field.
    case fieldSpend
    /// Cash held by supervisors.
    case cash
    case meterReset(UUID)
    /// One cash handover (confirm received / dispute).
    case handover(UUID)
    /// One meter exception (review).
    case exception(UUID)
    /// Open by notification id; the app fetches it and follows its `target`.
    case notification(UUID)
    case notifications
    /// One accountability decision (discount, credit, hours transfer/cancellation, baseline, classification,
    /// correction, write-off, retention, custody adjustment).
    case decision(DecisionKind, UUID)
    /// The accountability dashboard summary.
    case accountability
}

/// A route plus the tenant it belongs to (a push may concern another company the user belongs to).
public struct DeepLink: Hashable, Sendable {
    public let tenantID: UUID?
    public let route: OwnerRoute
    public let notificationID: UUID?

    public init(tenantID: UUID?, route: OwnerRoute, notificationID: UUID? = nil) {
        self.tenantID = tenantID
        self.route = route
        self.notificationID = notificationID
    }
}

/// Turns notification targets, console paths and APNs payloads into Owner routes. Anything not
/// recognised falls back to the inbox; nothing is executed from a payload, it only navigates.
public enum DeepLinkParser {
    /// From a notification's `target` (`entity`, `id`, console `path`).
    public static func route(entity: String, id: String?, path: String?) -> OwnerRoute? {
        let uuid = id.flatMap(UUID.init(uuidString:))
        switch (entity, uuid) {
        case let ("machine", id?): return .machine(id)
        case let ("alert", id?): return .alert(id)
        case let ("approval", id?): return .approval(id)
        case let ("case", id?): return .investigation(id)
        case let ("job", id?): return .job(id)
        case let ("meter_reset", id?): return .meterReset(id)
        case ("meter_reset", nil): return .approvals
        case ("exception", _): return .exceptions(jobID: nil)
        case let ("job_exception", id?): return .exception(id)
        case let ("cash_handover", id?): return .handover(id)
        case ("cash_transfer", _), ("supervisor_cash_custody", _): return .cash
        case ("hours_purchase", _): return .accountability
        case let (entity, id?) where DecisionKind(entity: entity) != nil: return .decision(DecisionKind(entity: entity)!, id)
        case let (entity, nil) where DecisionKind(entity: entity) != nil: return .approvals
        default: return path.flatMap(route(path:))
        }
    }

    /// Notification types whose screen is fixed whatever the record (strings doc "Notification deep links").
    public static func route(type: String?) -> OwnerRoute? {
        switch type {
        case "CASH_VARIANCE_OPENED": .approvals
        case "HOURS_EXPIRING": .accountability
        case "CASH_TRANSFER_TO_ACKNOWLEDGE", "CASH_FLOAT_TO_ACKNOWLEDGE": .cash
        default: nil
        }
    }

    public static func route(for notification: NotificationDTO) -> OwnerRoute {
        if let fixed = route(type: notification.type) { return fixed }
        guard let target = notification.target else { return .notifications }
        return route(entity: target.entity, id: target.id, path: target.path) ?? .notifications
    }

    /// From a console route such as `/tenant/cases/<id>` or `/tenant/alerts`.
    public static func route(path: String) -> OwnerRoute? {
        let parts = path.split(separator: "?").first.map { $0.split(separator: "/").map(String.init) } ?? []
        guard parts.first == "tenant", parts.count >= 2 else { return nil }
        let id = parts.count >= 3 ? UUID(uuidString: parts[2]) : nil
        switch (parts[1], id) {
        case let ("cases", id?): return .investigation(id)
        case ("cases", nil): return .investigations
        case let ("jobs", id?): return .job(id)
        case ("jobs", nil): return .jobs
        case let ("alerts", id?): return .alert(id)
        case ("alerts", nil): return .alerts
        case let ("approvals", id?): return .approval(id)
        case ("approvals", nil): return .approvals
        case let ("meter-resets", id?): return .meterReset(id)
        case ("meter-resets", nil): return .approvals
        case ("exceptions", _): return .exceptions(jobID: nil)
        case let ("customer-discounts", id?): return .decision(.discount, id)
        case let ("credit-arrangements", id?): return .decision(.credit, id)
        case let ("hours-transfers", id?): return .decision(.hoursTransfer, id)
        case let ("hours-cancellations", id?): return .decision(.cancellation, id)
        case let ("meter-baselines", id?): return .decision(.baseline, id)
        case let ("meter-corrections", id?): return .decision(.correction, id)
        case ("customer-discounts", nil), ("credit-arrangements", nil), ("hours-transfers", nil), ("hours-cancellations", nil),
             ("meter-baselines", nil), ("meter-corrections", nil):
            return .approvals
        case ("hours", _): return .accountability
        case ("engine-hours", _):
            if parts.count >= 4, parts[2] == "machines", let machine = UUID(uuidString: parts[3]) { return .machine(machine) }
            if parts.count >= 4, parts[2] == "classifications", let record = UUID(uuidString: parts[3]) {
                return .decision(.classification, record)
            }
            return .approvals
        case ("cash", _):
            if parts.count >= 4, parts[2] == "handovers", let handover = UUID(uuidString: parts[3]) { return .handover(handover) }
            if parts.count >= 3, parts[2] == "variances" { return .approvals }
            return .cash
        case ("accountability", _): return .accountability
        case ("fleet", _):
            if parts.count >= 4, parts[2] == "machines", let machine = UUID(uuidString: parts[3]) {
                return .machine(machine)
            }
            return .fleet
        case let ("machines", id?): return .machine(id)
        case ("machines", nil): return .fleet
        case let ("notifications", id?): return .notification(id)
        case ("notifications", nil): return .notifications
        default: return nil
        }
    }

    /// From an APNs `userInfo` dictionary. The server's push `data` carries `notification_id`,
    /// `type`, `severity`, `tenant_id` and `link` (a console path, often without an id); when the
    /// link names no record, the notification itself is opened and resolved via its `target`.
    public static func parse(pushPayload userInfo: [AnyHashable: Any]) -> DeepLink? {
        func string(_ key: String) -> String? {
            let value = userInfo[key] as? String
            return value?.isEmpty == false ? value : nil
        }
        let tenant = string("tenant_id").flatMap(UUID.init(uuidString:))
        let notificationID = string("notification_id").flatMap(UUID.init(uuidString:))
        if let fixed = route(type: string("type")) {
            return DeepLink(tenantID: tenant, route: fixed, notificationID: notificationID)
        }
        if let entity = string("entity"), let route = route(entity: entity, id: string("entity_id"), path: nil) {
            return DeepLink(tenantID: tenant, route: route, notificationID: notificationID)
        }
        if let link = string("link"), let route = route(path: link), route.identifiesRecord {
            return DeepLink(tenantID: tenant, route: route, notificationID: notificationID)
        }
        if let notificationID {
            return DeepLink(tenantID: tenant, route: .notification(notificationID), notificationID: notificationID)
        }
        if let link = string("link"), let route = route(path: link) {
            return DeepLink(tenantID: tenant, route: route)
        }
        return tenant == nil ? nil : DeepLink(tenantID: tenant, route: .notifications)
    }
}

extension OwnerRoute {
    /// Whether the route opens one specific record (as opposed to a list).
    public var identifiesRecord: Bool {
        switch self {
        case .machine, .alert, .approval, .investigation, .job, .meterReset, .handover, .exception, .notification, .decision: true
        case .fleet, .jobs, .investigations, .alerts, .approvals, .exceptions, .fieldSpend, .cash, .notifications,
             .accountability: false
        }
    }
}
