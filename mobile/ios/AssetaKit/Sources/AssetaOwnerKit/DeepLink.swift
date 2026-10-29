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
    /// One cash transfer between custodians (read-only).
    case cashTransfer(UUID)
    /// One cash float issued to a custodian (read-only).
    case cashFloat(UUID)
    /// Today's overdue remittances (custodians still holding cash past the cut-off).
    case overdueRemittances
    /// One overdue-remittance flag (read-only).
    case overdueRemittance(UUID)
    /// One revenue difference (figures, explanation, decision; DEC-031 R3).
    case revenueDifference(UUID)
    /// One machine's daily machine sheet (last 14 days, read-only).
    case dailySheet(UUID)
    /// One machine on one tenant-local day (`YYYY-MM-DD`, read-only).
    case dailySheetDay(UUID, String)
    /// Open prepaid-hours purchases with hours left or in use (DEC-031 Phase 4, read-only).
    case customerHours
    /// One prepaid-hours purchase (HOURS_LOW_BALANCE / HOURS_EXPIRING / HOURS_EXPIRED notifications).
    case hoursPurchase(UUID)
    /// The hours statement of one customer (`name` shown until the statement arrives).
    case hoursStatement(customer: UUID, name: String?)
    /// People scorecard: counts of items to look at per person (DEC-031 Phase 5, read-only).
    case scorecard
    /// One person's scorecard for the local days `from`…`to` (nil: the default period); `name` shown until it loads.
    case scorecardPerson(UUID, name: String?, from: String?, to: String?)
    /// Completed jobs not invoiced yet (read-only).
    case unbilledWork
    /// Machines idle for a while (read-only).
    case idleMachines
    /// The go-live setup checklist (`/tenant/setup`).
    case setupChecklist
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
    /// The screen of one accountability record (`kind` + `record_id`). Every kind has its own screen.
    public static func route(record: RecordRef) -> OwnerRoute {
        let id = record.id
        switch record.kind {
        case .cashTransfer: return .cashTransfer(id)
        case .cashFloat: return .cashFloat(id)
        case .cashVariance: return .decision(.writeOff, id)
        case .cashRetention: return .decision(.retention, id)
        case .custodyAdjustment: return .decision(.adjustment, id)
        case .cashRemittance: return .handover(id)
        case .remittanceOverdue: return .overdueRemittance(id)
        case .hoursDiscount: return .decision(.discount, id)
        case .hoursCredit: return .decision(.credit, id)
        case .hoursTransfer: return .decision(.hoursTransfer, id)
        case .hoursCancellation: return .decision(.cancellation, id)
        case .meterBaseline: return .decision(.baseline, id)
        case .meterCorrection: return .decision(.correction, id)
        case .engineHoursClassification: return .decision(.classification, id)
        case .revenueDifference: return .revenueDifference(id)
        case .nonRevenueApproval: return .decision(.nonRevenue, id)
        case .hoursPurchase: return .hoursPurchase(id)
        // DEC-031 Phase 5: UNBILLED_WORK names the job.
        case .job: return .job(id)
        }
    }

    /// From a notification's `target` (`entity`, `id`, console `path`).
    public static func route(entity: String, id: String?, path: String?) -> OwnerRoute? {
        let uuid = id.flatMap(UUID.init(uuidString:))
        if let record = RecordKind.resolve(kind: nil, recordID: nil, entity: entity, entityID: id) {
            return route(record: record)
        }
        switch (entity, uuid) {
        case ("cash_remittance_overdue", nil): return .overdueRemittances
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
        case ("hours_purchase", nil): return .customerHours
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
        case "REMITTANCE_OVERDUE": .overdueRemittances
        default: nil
        }
    }

    /// The exact record when the notification names one (`data.kind`/`record_id`, else its target), then the fixed
    /// screen of its type, then its target or link; anything else opens the inbox.
    public static func route(for notification: NotificationDTO) -> OwnerRoute {
        if let record = notification.dataRecord { return route(record: record) }
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
        case ("hours", _):
            // Web detail routes /tenant/hours/<purchases|discounts|credit|transfers|cancellations>/<id>.
            if parts.count >= 4, let record = UUID(uuidString: parts[3]) {
                switch parts[2] {
                case "purchases": return .hoursPurchase(record)
                case "discounts": return .decision(.discount, record)
                case "credit": return .decision(.credit, record)
                case "transfers": return .decision(.hoursTransfer, record)
                case "cancellations": return .decision(.cancellation, record)
                default: break
                }
            }
            if parts.count >= 3, parts[2] == "purchases" { return .customerHours }
            return .accountability
        case ("finance", _):
            // Web cash detail routes /tenant/finance/cash/<segment>/<id> (and their lists).
            guard parts.count >= 4, parts[2] == "cash" else { return nil }
            return cashPath(parts[3], parts.count >= 5 ? UUID(uuidString: parts[4]) : nil)
        case ("engine-hours", _):
            if parts.count >= 3, parts[2] == "daily-sheet" { return .fleet }
            if parts.count >= 4, parts[2] == "machines", let machine = UUID(uuidString: parts[3]) { return .machine(machine) }
            if parts.count >= 4, parts[2] == "classifications", let record = UUID(uuidString: parts[3]) {
                return .decision(.classification, record)
            }
            return .approvals
        case ("cash", _):
            if parts.count >= 4, parts[2] == "handovers", let handover = UUID(uuidString: parts[3]) { return .handover(handover) }
            if parts.count >= 3, parts[2] == "handovers" { return .approvals }
            guard parts.count >= 3 else { return .cash }
            return cashPath(parts[2], parts.count >= 4 ? UUID(uuidString: parts[3]) : nil)
        case ("accountability", _): return .accountability
        case let ("revenue-differences", id?): return .revenueDifference(id)
        case let ("non-revenue-approvals", id?): return .decision(.nonRevenue, id)
        case ("revenue-differences", nil), ("non-revenue-approvals", nil): return .approvals
        case ("fleet", _):
            if parts.count >= 4, parts[2] == "machines", let machine = UUID(uuidString: parts[3]) {
                return .machine(machine)
            }
            return .fleet
        case let ("machines", id?): return .machine(id)
        case ("machines", nil): return .fleet
        case ("scorecard", _): return id.map { .scorecardPerson($0, name: nil, from: nil, to: nil) } ?? .scorecard
        case ("unbilled-work", _): return .unbilledWork
        case ("idle-machines", _): return .idleMachines
        case ("setup", _): return .setupChecklist
        case let ("notifications", id?): return .notification(id)
        case ("notifications", nil): return .notifications
        default: return nil
        }
    }

    /// A cash custody segment (`transfers`, `floats`, `variances`, ...) with a record id; its list when there is none.
    static func cashPath(_ segment: String, _ id: UUID?) -> OwnerRoute {
        let kinds: [String: RecordKind] = [
            "transfers": .cashTransfer, "floats": .cashFloat, "variances": .cashVariance, "retentions": .cashRetention,
            "adjustments": .custodyAdjustment, "remittances": .cashRemittance, "remittance-overdue": .remittanceOverdue,
        ]
        let kind = kinds[segment]
        if let kind, let id { return route(record: RecordRef(kind: kind, id: id)) }
        switch kind {
        case .cashTransfer, .cashFloat, nil: return .cash
        case .remittanceOverdue: return .overdueRemittances
        default: return .approvals
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
        if let record = RecordKind.resolve(kind: string("kind"), recordID: string("record_id"), entity: nil, entityID: nil) {
            return DeepLink(tenantID: tenant, route: route(record: record), notificationID: notificationID)
        }
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
        case .machine, .alert, .approval, .investigation, .job, .meterReset, .handover, .exception, .notification, .decision,
             .cashTransfer, .cashFloat, .overdueRemittance, .revenueDifference, .dailySheetDay, .hoursPurchase, .scorecardPerson: true
        case .fleet, .jobs, .investigations, .alerts, .approvals, .exceptions, .fieldSpend, .cash, .notifications,
             .accountability, .overdueRemittances, .dailySheet, .customerHours, .hoursStatement, .scorecard, .unbilledWork,
             .idleMachines, .setupChecklist: false
        }
    }
}
