import Foundation

/// Response of `GET /api/v1/me`.
///
/// Permissions and menus are **display hints** computed by the server from Keycloak identity and
/// Asseta tenant RBAC. The app may hide UI with them but must never treat them as authorization:
/// every request is re-authorized server-side.
public struct MeResponse: Codable, Hashable, Sendable {
    public let userID: UUID
    public let email: String
    public let displayName: String
    public let platformPermissions: [String]
    public let platformMenus: [MenuEntry]
    public let tenants: [TenantMembership]

    public init(
        userID: UUID,
        email: String,
        displayName: String,
        platformPermissions: [String],
        platformMenus: [MenuEntry],
        tenants: [TenantMembership]
    ) {
        self.userID = userID
        self.email = email
        self.displayName = displayName
        self.platformPermissions = platformPermissions
        self.platformMenus = platformMenus
        self.tenants = tenants
    }

    enum CodingKeys: String, CodingKey {
        case userID = "user_id"
        case email
        case displayName = "display_name"
        case platformPermissions = "platform_permissions"
        case platformMenus = "platform_menus"
        case tenants
    }
}

public struct TenantMembership: Codable, Hashable, Sendable, Identifiable {
    public let tenantID: UUID
    public let name: String
    public let status: TenantStatus
    public let accessState: TenantAccessState
    public let permissions: [String]
    public let menus: [MenuEntry]
    /// Tenant capabilities switched off by policy (e.g. `CUSTOMER_HOURS`); their entry points are hidden.
    /// Missing on older servers = nothing switched off.
    public let disabledCapabilities: [String]

    public var id: UUID { tenantID }

    public init(
        tenantID: UUID,
        name: String,
        status: TenantStatus,
        accessState: TenantAccessState,
        permissions: [String],
        menus: [MenuEntry],
        disabledCapabilities: [String] = []
    ) {
        self.tenantID = tenantID
        self.name = name
        self.status = status
        self.accessState = accessState
        self.permissions = permissions
        self.menus = menus
        self.disabledCapabilities = disabledCapabilities
    }

    /// Menus in server-defined order (ties broken by key for determinism).
    public var orderedMenus: [MenuEntry] { menus.inServerOrder }

    /// Whether the tenant's policy switched `capability` off (`TenantCapability`).
    public func isDisabled(_ capability: String) -> Bool { disabledCapabilities.contains(capability) }

    enum CodingKeys: String, CodingKey {
        case tenantID = "tenant_id"
        case accessState = "access_state"
        case disabledCapabilities = "disabled_capabilities"
        case name, status, permissions, menus
    }

    public init(from decoder: any Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        tenantID = try c.decode(UUID.self, forKey: .tenantID)
        name = try c.decode(String.self, forKey: .name)
        status = try c.decode(TenantStatus.self, forKey: .status)
        accessState = try c.decode(TenantAccessState.self, forKey: .accessState)
        permissions = try c.decode([String].self, forKey: .permissions)
        menus = try c.decode([MenuEntry].self, forKey: .menus)
        disabledCapabilities = (try? c.decodeIfPresent([String].self, forKey: .disabledCapabilities)) ?? []
    }
}

/// Tenant capabilities a policy can switch off (`TenantAccessDto.disabled_capabilities`).
public enum TenantCapability {
    public static let customerHours = "CUSTOMER_HOURS"
}

/// Server-computed access level for a tenant membership (subscription/entitlement driven).
/// Unknown future values are preserved and treated by the UI like ``blocked`` (fail closed).
public struct TenantAccessState: RawRepresentable, Codable, Hashable, Sendable {
    public let rawValue: String
    public init(rawValue: String) { self.rawValue = rawValue }

    public static let full = TenantAccessState(rawValue: "FULL")
    public static let readOnly = TenantAccessState(rawValue: "READ_ONLY")
    public static let blocked = TenantAccessState(rawValue: "BLOCKED")

    /// Whether the tenant may be opened at all in the app (display decision only).
    public var allowsEntry: Bool { self == .full || self == .readOnly }

    public init(from decoder: any Decoder) throws {
        rawValue = try decoder.singleValueContainer().decode(String.self)
    }

    public func encode(to encoder: any Encoder) throws {
        var container = encoder.singleValueContainer()
        try container.encode(rawValue)
    }
}

/// Tenant lifecycle status as reported by the server. Open-ended so new server states
/// decode without crashing older app builds; the server decides what each state allows.
public struct TenantStatus: RawRepresentable, Codable, Hashable, Sendable {
    public let rawValue: String
    public init(rawValue: String) { self.rawValue = rawValue }

    public static let active = TenantStatus(rawValue: "ACTIVE")
    public static let suspended = TenantStatus(rawValue: "SUSPENDED")

    public init(from decoder: any Decoder) throws {
        rawValue = try decoder.singleValueContainer().decode(String.self)
    }

    public func encode(to encoder: any Encoder) throws {
        var container = encoder.singleValueContainer()
        try container.encode(rawValue)
    }
}

public struct MenuEntry: Codable, Hashable, Sendable, Identifiable {
    public let key: String
    public let label: String
    public let path: String
    public let order: Int

    public var id: String { key }

    public init(key: String, label: String, path: String, order: Int) {
        self.key = key
        self.label = label
        self.path = path
        self.order = order
    }
}

extension Array where Element == MenuEntry {
    /// Server-defined order, ties broken by key for determinism.
    public var inServerOrder: [MenuEntry] {
        sorted { ($0.order, $0.key) < ($1.order, $1.key) }
    }
}
