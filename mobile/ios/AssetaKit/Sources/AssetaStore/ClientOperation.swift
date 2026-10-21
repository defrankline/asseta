import Foundation

/// Lifecycle of an outbox operation. An operation is only "synced" once ``acked`` —
/// i.e. after a durable server ACK carrying a server revision.
public enum ClientOperationStatus: String, CaseIterable, Sendable, Codable {
    case pending = "PENDING"
    case sent = "SENT"
    case acked = "ACKED"
    case failed = "FAILED"
    case quarantined = "QUARANTINED"

    /// Statuses from which a transition into `self` is legal.
    var allowedSources: Set<ClientOperationStatus> {
        switch self {
        case .pending: [.failed]
        case .sent: [.pending]
        case .acked: [.sent]
        case .failed: [.sent]
        case .quarantined: [.pending, .sent, .failed]
        }
    }
}

/// A durable, device-generated mutation waiting to be pushed to the server.
public struct ClientOperation: Equatable, Sendable, Identifiable {
    public let id: UUID
    public let tenantID: UUID
    public let opType: String
    public let entityType: String
    public let entityID: UUID
    public let payloadJSON: String
    public let dependsOn: UUID?
    public let createdAtDevice: Date
    public let status: ClientOperationStatus
    public let attemptCount: Int
    public let lastError: String?
    public let serverRevision: Int64?
}

/// Input for ``ClientOperationRepository/enqueue(_:)``. The `id` doubles as the
/// server-side idempotency key, so it is generated once on device and never regenerated.
public struct NewClientOperation: Sendable {
    public let id: UUID
    public let tenantID: UUID
    public let opType: String
    public let entityType: String
    public let entityID: UUID
    public let payloadJSON: String
    public let dependsOn: UUID?
    public let createdAtDevice: Date

    public init(
        id: UUID = UUID(),
        tenantID: UUID,
        opType: String,
        entityType: String,
        entityID: UUID,
        payloadJSON: String,
        dependsOn: UUID? = nil,
        createdAtDevice: Date = Date()
    ) {
        self.id = id
        self.tenantID = tenantID
        self.opType = opType
        self.entityType = entityType
        self.entityID = entityID
        self.payloadJSON = payloadJSON
        self.dependsOn = dependsOn
        self.createdAtDevice = createdAtDevice
    }
}

public enum OutboxError: Error, Equatable, Sendable {
    case notFound(UUID)
    case invalidTransition(id: UUID, to: ClientOperationStatus)
    case dependencyMissing(UUID)
    case crossTenantDependency(UUID)
    case invalidPayload
}
