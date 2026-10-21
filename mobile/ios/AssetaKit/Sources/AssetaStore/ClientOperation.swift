import Foundation

/// Lifecycle of an outbox operation. An operation is only "synced" once ``acked`` —
/// i.e. after a durable server ACK (`ACKED`, or `DUPLICATE` of an applied operation).
public enum ClientOperationStatus: String, CaseIterable, Sendable, Codable {
    case pending = "PENDING"
    case sent = "SENT"
    case acked = "ACKED"
    /// Rejected by the server (validation, permission). Evidence kept; error code visible.
    case failed = "FAILED"
    /// Server state conflict (e.g. job cancelled). Kept with `server_state`; never auto-overwritten.
    case conflict = "CONFLICT"
    /// Held by the server for a read-only tenant; re-sent later, never discarded.
    case quarantined = "QUARANTINED"

    /// Statuses from which a transition into `self` is legal.
    var allowedSources: Set<ClientOperationStatus> {
        switch self {
        case .pending: [.failed, .sent]
        case .sent: [.pending, .quarantined]
        case .acked: [.sent]
        case .failed: [.sent]
        case .conflict: [.sent]
        case .quarantined: [.pending, .sent, .failed]
        }
    }
}

/// Which payload field receives the server `attachment_id` once a local file is uploaded.
public enum AttachmentPayloadField: String, Sendable, CaseIterable {
    case photo = "photo_attachment_id"
    case signature = "signature_attachment_id"
    /// EXPENSE receipts: the upload session id is appended to this array (the server resolves it
    /// to the stored attachment, or answers DEFERRED `ATTACHMENT_PENDING` until it is complete).
    case receiptUploads = "receipt_upload_ids"
}

/// A durable, device-generated mutation waiting to be pushed to the server.
public struct ClientOperation: Equatable, Sendable, Identifiable {
    public let id: UUID
    public let tenantID: UUID
    public let opType: String
    public let entityType: String
    public let entityID: UUID
    public let payloadJSON: String
    /// All operations that must be ACKED first (sent as `depends_on`).
    public let dependencies: [UUID]
    public let createdAtDevice: Date
    public let status: ClientOperationStatus
    public let attemptCount: Int
    public let lastError: String?
    public let errorCode: String?
    public let serverRevision: Int64?
    /// The stored server result (`result`/`error`, including `server_state` for conflicts).
    public let serverResultJSON: String?
    public let nextAttemptAt: Date?

    /// First dependency (kept for the original single-parent API).
    public var dependsOn: UUID? { dependencies.first }
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
    public let dependsOn: [UUID]
    /// Local files whose server `attachment_id` must be known before this operation is sent.
    public let attachments: [(localID: UUID, field: AttachmentPayloadField)]
    public let createdAtDevice: Date

    public init(
        id: UUID = UUID(),
        tenantID: UUID,
        opType: String,
        entityType: String,
        entityID: UUID,
        payloadJSON: String,
        dependsOn: [UUID] = [],
        attachments: [(localID: UUID, field: AttachmentPayloadField)] = [],
        createdAtDevice: Date = Date()
    ) {
        self.id = id
        self.tenantID = tenantID
        self.opType = opType
        self.entityType = entityType
        self.entityID = entityID
        self.payloadJSON = payloadJSON
        var seen = Set<UUID>()
        self.dependsOn = dependsOn.filter { seen.insert($0).inserted }
        self.attachments = attachments
        self.createdAtDevice = createdAtDevice
    }
}

public enum OutboxError: Error, Equatable, Sendable {
    case notFound(UUID)
    case invalidTransition(id: UUID, to: ClientOperationStatus)
    case dependencyMissing(UUID)
    case crossTenantDependency(UUID)
    case attachmentMissing(UUID)
    case invalidPayload
}
