import AssetaModel
import AssetaNetwork
import Foundation

/// Where a snapshot came from.
public enum SnapshotSource: Equatable, Sendable {
    /// Just fetched from the server.
    case server
    /// Served from the encrypted cache because the server could not be reached.
    case cache(reason: String)
}

/// A screen's data and where it came from.
public struct Snapshot<Value: Sendable>: Sendable {
    public let value: Value
    public let fetchedAt: Date
    public let source: SnapshotSource

    public init(value: Value, fetchedAt: Date, source: SnapshotSource) {
        self.value = value
        self.fetchedAt = fetchedAt
        self.source = source
    }

    public var isFromCache: Bool { source != .server }

    public func map<T: Sendable>(_ transform: (Value) -> T) -> Snapshot<T> {
        Snapshot<T>(value: transform(value), fetchedAt: fetchedAt, source: source)
    }
}

/// Network-first reads with an offline fallback to the last cached snapshot.
///
/// - Success: the response is cached (`fetchedAt` = now) and returned as `.server`.
/// - Network failure / 5xx / 429: the cached snapshot (if still within the 7-day bound) is
///   returned as `.cache`; otherwise the error is thrown.
/// - Lost tenant access (403 tenant/mandate codes): the tenant's whole cache is wiped, then the
///   error is thrown. Missing permission or a vanished record (403/404): that entry is dropped.
public struct OwnerRepository: Sendable {
    public let client: APIClient
    public let cache: SnapshotCache?
    public let tenantID: UUID
    private let now: @Sendable () -> Date

    /// Error codes meaning this user may no longer see the tenant at all.
    public static let accessLostCodes: Set<String> = [
        "TENANT_ACCESS_DENIED", "TENANT_ACCESS_BLOCKED", "MANDATE_REQUIRED", "MANDATE_ENDED", "USER_INACTIVE",
    ]

    public init(client: APIClient, cache: SnapshotCache?, tenantID: UUID, now: @escaping @Sendable () -> Date = { Date() }) {
        self.client = client
        self.cache = cache
        self.tenantID = tenantID
        self.now = now
    }

    public func load<Value: Codable & Sendable>(_ key: SnapshotKey, _ request: APIRequest<Value>) async throws
        -> Snapshot<Value> {
        do {
            let value = try await client.send(request)
            let fetchedAt = now()
            try? cache?.put(value, key: key, tenantID: tenantID, fetchedAt: fetchedAt)
            return Snapshot(value: value, fetchedAt: fetchedAt, source: .server)
        } catch let error as APIError {
            switch Self.disposition(of: error) {
            case .fallBackToCache:
                if let cached = try? cache?.get(Value.self, key: key, tenantID: tenantID, now: now()) {
                    return Snapshot(value: cached.value, fetchedAt: cached.fetchedAt,
                                    source: .cache(reason: error.localizedDescription))
                }
            case .wipeTenant:
                try? cache?.removeTenant(tenantID)
            case .dropEntry:
                try? cache?.remove(key: key, tenantID: tenantID)
            case .none:
                break
            }
            throw error
        }
    }

    /// The cached snapshot only (used to paint a screen instantly before the network answers).
    public func cached<Value: Codable & Sendable>(_ key: SnapshotKey, as type: Value.Type = Value.self)
        -> Snapshot<Value>? {
        guard let hit = try? cache?.get(Value.self, key: key, tenantID: tenantID, now: now()) else { return nil }
        return Snapshot(value: hit.value, fetchedAt: hit.fetchedAt, source: .cache(reason: "Cached"))
    }

    /// Sends a mutation (never cached, never queued: the Owner app has no offline writes).
    public func send<Value: Decodable & Sendable>(_ request: APIRequest<Value>) async throws -> Value {
        do {
            return try await client.send(request)
        } catch let error as APIError {
            if Self.disposition(of: error) == .wipeTenant { try? cache?.removeTenant(tenantID) }
            throw error
        }
    }

    public enum ErrorDisposition: Equatable, Sendable { case fallBackToCache, wipeTenant, dropEntry, none }

    public static func disposition(of error: APIError) -> ErrorDisposition {
        if error.isRetryable { return .fallBackToCache }
        switch error {
        case let .server(status, body):
            if accessLostCodes.contains(body.code) { return .wipeTenant }
            return status == 403 || status == 404 ? .dropEntry : .none
        case let .unexpectedStatus(status, _):
            return status == 403 || status == 404 ? .dropEntry : .none
        default:
            return .none
        }
    }
}
