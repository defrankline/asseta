import Foundation

// In-app notifications, push devices, per category × severity routing and the `/api/v1/ws`
// realtime frames (`NotificationDto`, `PushDeviceIn/Dto`, `NotificationRoutingDto/In`, docs/api.md).

public struct NotificationTargetDTO: Codable, Hashable, Sendable {
    /// e.g. `alert`, `approval`, `job`, `case`, `screen`.
    public let entity: String
    public let id: String?
    /// The web console route to act on (e.g. `/tenant/cases/<id>`).
    public let path: String?

    public init(entity: String, id: String?, path: String?) {
        self.entity = entity
        self.id = id
        self.path = path
    }
}

public struct NotificationDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let type: String
    public let category: String
    public let severity: AlertSeverity
    public let priority: String
    public let title: String
    public let body: String
    public let createdAt: Date
    public let readAt: Date?
    public let target: NotificationTargetDTO?
    public let tenantID: UUID?
    public let data: JSONValue

    public var isUnread: Bool { readAt == nil }

    enum CodingKeys: String, CodingKey {
        case id, type, category, severity, priority, title, body, createdAt = "created_at", readAt = "read_at"
        case target, tenantID = "tenant_id", data
    }
}

public struct UnreadCountDTO: Codable, Hashable, Sendable {
    public let count: Int
}

public struct MarkReadIn: Codable, Hashable, Sendable {
    public let ids: [UUID]
    public init(ids: [UUID]) { self.ids = ids }
}

public struct MarkReadResultDTO: Codable, Hashable, Sendable {
    public let updated: Int
    public let unread: Int
}

// MARK: - Push devices

public struct PushDeviceIn: Codable, Hashable, Sendable {
    public let platform: String
    public let app: String
    public let token: String
    public let appVersion: String?
    public let deviceLabel: String?

    public init(platform: String, app: String, token: String, appVersion: String?, deviceLabel: String?) {
        self.platform = platform
        self.app = app
        self.token = token
        self.appVersion = appVersion
        self.deviceLabel = deviceLabel
    }

    enum CodingKeys: String, CodingKey {
        case platform, app, token, appVersion = "app_version", deviceLabel = "device_label"
    }
}

public struct PushDeviceDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let tenantID: UUID?
    public let platform: String
    public let app: String
    /// Masked token (the full token is never returned).
    public let tokenHint: String
    public let appVersion: String?
    public let deviceLabel: String?
    public let active: Bool
    public let createdAt: Date
    public let lastRegisteredAt: Date
    public let deactivatedAt: Date?
    public let deactivationReason: String?

    enum CodingKeys: String, CodingKey {
        case id, tenantID = "tenant_id", platform, app, tokenHint = "token_hint", appVersion = "app_version"
        case deviceLabel = "device_label", active, createdAt = "created_at", lastRegisteredAt = "last_registered_at"
        case deactivatedAt = "deactivated_at", deactivationReason = "deactivation_reason"
    }
}

// MARK: - Routing (push/email per category × severity)

public struct NotificationRoutingDTO: Codable, Hashable, Sendable {
    public let category: String
    public let severity: AlertSeverity
    public let push: Bool
    public let email: Bool
    public let inApp: Bool?
    /// Channels the server always uses for this cell; the app must not offer to turn them off.
    public let mandatoryChannels: [String]
    /// Where the effective value comes from (e.g. user, tenant default, system default).
    public let source: String

    public init(category: String, severity: AlertSeverity, push: Bool, email: Bool, inApp: Bool? = nil,
                mandatoryChannels: [String] = [], source: String = "SYSTEM") {
        self.category = category
        self.severity = severity
        self.push = push
        self.email = email
        self.inApp = inApp
        self.mandatoryChannels = mandatoryChannels
        self.source = source
    }

    enum CodingKeys: String, CodingKey {
        case category, severity, push, email, inApp = "in_app", mandatoryChannels = "mandatory_channels", source
    }
}

public struct NotificationRoutingChangeIn: Codable, Hashable, Sendable {
    public let category: String
    public let severity: AlertSeverity
    public let push: Bool
    public let email: Bool

    public init(category: String, severity: AlertSeverity, push: Bool, email: Bool) {
        self.category = category
        self.severity = severity
        self.push = push
        self.email = email
    }
}

public struct NotificationRoutingIn: Codable, Hashable, Sendable {
    public let changes: [NotificationRoutingChangeIn]
    public let tenantDefault: Bool

    public init(changes: [NotificationRoutingChangeIn], tenantDefault: Bool = false) {
        self.changes = changes
        self.tenantDefault = tenantDefault
    }

    enum CodingKeys: String, CodingKey { case changes, tenantDefault = "tenant_default" }
}

// MARK: - Realtime (`/api/v1/ws`, sub-protocol `asseta.v1`)

public struct EntityChangedDTO: Codable, Hashable, Sendable {
    public let entity: String
    public let id: String?
    public let action: String?

    public init(entity: String, id: String?, action: String?) {
        self.entity = entity
        self.id = id
        self.action = action
    }
}

/// A decoded server → client frame. Unknown frame types are kept as `.other` and ignored.
public enum RealtimeEvent: Hashable, Sendable {
    case authOK(unreadCount: Int?, heartbeatSeconds: Int?)
    case authError(code: String, message: String)
    case notification(NotificationDTO)
    case unreadCount(Int)
    case entityChanged(EntityChangedDTO)
    case ping
    case pong
    case reauthRequired
    case other(String)

    private struct Frame: Decodable {
        let type: String
        let payload: JSONValue?
    }

    public static func decode(_ data: Data) throws -> RealtimeEvent {
        let frame = try AssetaJSON.decoder().decode(Frame.self, from: data)
        let payload = frame.payload ?? .null
        switch frame.type {
        case "auth_ok":
            return .authOK(unreadCount: payload["unread_count"]?.intValue,
                           heartbeatSeconds: payload["heartbeat_seconds"]?.intValue)
        case "auth_error":
            return .authError(code: payload["code"]?.stringValue ?? "NOT_AUTHENTICATED",
                              message: payload["message"]?.stringValue ?? "")
        case "notification": return .notification(try payload.decode())
        case "unread_count": return .unreadCount(payload["count"]?.intValue ?? 0)
        case "entity.changed": return .entityChanged(try payload.decode())
        case "ping": return .ping
        case "pong": return .pong
        case "reauth_required": return .reauthRequired
        default: return .other(frame.type)
        }
    }
}

// MARK: - Exact-record links (DEC-030 G5)

/// The accountability record a notification is about. The server puts `kind` + `record_id` in the notification
/// `data` and in the push payload; older notifications only have `target.entity` + `target.id`, mapped here the same
/// way as the server's `RECORDS` table. Unknown kinds are nil, so the apps fall back to the list.
public enum RecordKind: String, CaseIterable, Sendable, Hashable {
    case cashTransfer = "CASH_TRANSFER"
    case cashFloat = "CASH_FLOAT"
    case cashVariance = "CASH_VARIANCE"
    case cashRetention = "CASH_RETENTION"
    case custodyAdjustment = "CUSTODY_ADJUSTMENT"
    case cashRemittance = "CASH_REMITTANCE"
    case remittanceOverdue = "REMITTANCE_OVERDUE"
    case hoursDiscount = "HOURS_DISCOUNT"
    case hoursCredit = "HOURS_CREDIT"
    case hoursTransfer = "HOURS_TRANSFER"
    case hoursCancellation = "HOURS_CANCELLATION"
    case meterBaseline = "METER_BASELINE"
    case meterCorrection = "METER_CORRECTION"
    case engineHoursClassification = "ENGINE_HOURS_CLASSIFICATION"
    /// DEC-031 R3: a revenue difference to explain or decide.
    case revenueDifference = "REVENUE_DIFFERENCE"
    /// DEC-031: non-revenue time explained by one person, awaiting another's approval.
    case nonRevenueApproval = "NON_REVENUE_APPROVAL"

    /// From a notification target entity (`cash_transfer`, `supervisor_cash_custody`, `baseline`, ...).
    public init?(entity: String?) {
        switch entity {
        case "cash_transfer": self = .cashTransfer
        case "supervisor_cash_custody", "cash_float": self = .cashFloat
        case "cash_variance": self = .cashVariance
        case "cash_retention": self = .cashRetention
        case "custody_adjustment": self = .custodyAdjustment
        case "cash_handover": self = .cashRemittance
        case "cash_remittance_overdue": self = .remittanceOverdue
        case "customer_discount": self = .hoursDiscount
        case "credit_arrangement": self = .hoursCredit
        case "hours_transfer": self = .hoursTransfer
        case "hours_cancellation": self = .hoursCancellation
        case "baseline", "meter_baseline": self = .meterBaseline
        case "correction", "meter_correction": self = .meterCorrection
        case "classification", "engine_hours_classification": self = .engineHoursClassification
        case "revenue_difference": self = .revenueDifference
        case "non_revenue_approval": self = .nonRevenueApproval
        default: return nil
        }
    }

    /// `kind` + `record_id` (else `entity` + `entity_id`) as strings, e.g. from a push payload or notification data.
    public static func resolve(kind: String?, recordID: String?, entity: String?, entityID: String?) -> RecordRef? {
        if let kind = kind.flatMap(RecordKind.init(rawValue:)), let id = recordID.flatMap(UUID.init(uuidString:)) {
            return RecordRef(kind: kind, id: id)
        }
        if let kind = RecordKind(entity: entity), let id = entityID.flatMap(UUID.init(uuidString:)) {
            return RecordRef(kind: kind, id: id)
        }
        return nil
    }
}

/// One accountability record: its kind and id.
public struct RecordRef: Hashable, Sendable {
    public let kind: RecordKind
    public let id: UUID

    public init(kind: RecordKind, id: UUID) {
        self.kind = kind
        self.id = id
    }
}

extension NotificationDTO {
    /// The record named by `data.kind` + `data.record_id` only (DEC-030 G5 notifications).
    public var dataRecord: RecordRef? {
        RecordKind.resolve(kind: data["kind"]?.stringValue, recordID: data["record_id"]?.stringValue, entity: nil, entityID: nil)
    }

    /// The exact record this notification is about (`data.kind`/`data.record_id`, else its target), when known.
    public var record: RecordRef? {
        RecordKind.resolve(kind: data["kind"]?.stringValue, recordID: data["record_id"]?.stringValue,
                           entity: target?.entity, entityID: target?.id)
    }
}

extension RecordRef {
    /// From an APNs payload: `kind` + `record_id`, else `entity` + `entity_id` (strings).
    public init?(pushPayload info: [AnyHashable: Any]) {
        func string(_ key: String) -> String? { (info[key] as? String).flatMap { $0.isEmpty ? nil : $0 } }
        guard let ref = RecordKind.resolve(kind: string("kind"), recordID: string("record_id"), entity: string("entity"),
                                           entityID: string("entity_id")) else { return nil }
        self = ref
    }
}
