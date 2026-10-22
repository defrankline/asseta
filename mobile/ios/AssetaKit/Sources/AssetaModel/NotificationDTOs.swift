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
