import Foundation

// Wire DTOs of the versioned offline sync protocol (`/api/v1/sync`, protocol 1).
// Shapes follow `contracts/openapi.json` (operationIds registerDevice, syncBootstrap, syncChanges,
// syncPush, startBlobUpload, putBlobChunk, completeBlobUpload).

public struct DeviceRegisterIn: Codable, Hashable, Sendable {
    public let deviceID: String
    public let platform: String
    public let appVersion: String

    public init(deviceID: String, appVersion: String, platform: String = "IOS") {
        self.deviceID = deviceID
        self.platform = platform
        self.appVersion = appVersion
    }

    enum CodingKeys: String, CodingKey {
        case deviceID = "device_id", platform, appVersion = "app_version"
    }
}

public struct DeviceSessionDTO: Codable, Hashable, Sendable {
    public let id: UUID
    public let deviceID: String
    public let platform: String
    public let appVersion: String
    public let status: String
    public let registeredAt: Date
    public let lastSyncAt: Date?
    public let offlineGrantUntil: Date
    public let lastClockOffsetS: Double?
    public let revokedAt: Date?
    public let revokeReason: String?

    enum CodingKeys: String, CodingKey {
        case id, platform, status
        case deviceID = "device_id", appVersion = "app_version", registeredAt = "registered_at"
        case lastSyncAt = "last_sync_at", offlineGrantUntil = "offline_grant_until"
        case lastClockOffsetS = "last_clock_offset_s", revokedAt = "revoked_at", revokeReason = "revoke_reason"
    }
}

public struct PolicySnapshotDTO: Codable, Hashable, Sendable {
    public let policyType: String
    /// `"tenant"` or `"machine:<uuid>"`.
    public let scopeKey: String
    public let versionIDs: [UUID]
    public let versionStamp: String
    public let values: JSONValue
    public let validUntil: Date

    public init(policyType: String, scopeKey: String, versionIDs: [UUID], versionStamp: String,
                values: JSONValue, validUntil: Date) {
        self.policyType = policyType
        self.scopeKey = scopeKey
        self.versionIDs = versionIDs
        self.versionStamp = versionStamp
        self.values = values
        self.validUntil = validUntil
    }

    enum CodingKeys: String, CodingKey {
        case policyType = "policy_type", scopeKey = "scope_key", versionIDs = "version_ids"
        case versionStamp = "version_stamp", values, validUntil = "valid_until"
    }
}

/// Server-owned entities, kept as raw JSON objects so the local store can persist exactly what the
/// server sent. Typed views (``JobDTO`` etc.) are decoded from them on read.
public struct SyncData: Codable, Hashable, Sendable {
    public var jobs: [JSONValue]
    public var machines: [JSONValue]
    public var sites: [JSONValue]
    public var customers: [JSONValue]
    public var contracts: [JSONValue]
    public var staff: [JSONValue]
    public var expenseCategories: [JSONValue]
    /// The supervisor's current custody per currency. Not an entity (no `id`) and always complete,
    /// so it replaces the local copy instead of being merged.
    public var cashCustody: [JSONValue]
    /// Supervisor inbox lists (SUPERVISOR_INBOX_V1), raw as sent; `nil` when the server did not send
    /// the field (an older server): the stored inbox is then left untouched.
    public var inbox: [InboxList: [JSONValue]] = [:]

    public init(jobs: [JSONValue] = [], machines: [JSONValue] = [], sites: [JSONValue] = [],
                customers: [JSONValue] = [], contracts: [JSONValue] = [], staff: [JSONValue] = [],
                expenseCategories: [JSONValue] = [], cashCustody: [JSONValue] = []) {
        self.jobs = jobs
        self.machines = machines
        self.sites = sites
        self.customers = customers
        self.contracts = contracts
        self.staff = staff
        self.expenseCategories = expenseCategories
        self.cashCustody = cashCustody
    }

    enum CodingKeys: String, CodingKey {
        case jobs, machines, sites, customers, contracts, staff
        case expenseCategories = "expense_categories", cashCustody = "cash_custody"
    }

    /// The `my_*` inbox lists of `SyncData`.
    public enum InboxList: String, CodingKey, CaseIterable, Sendable {
        case meterCaptures = "my_meter_captures", meterResets = "my_meter_resets"
        case jobActivities = "my_job_activities", acknowledgements = "my_acknowledgements"
        case expenses = "my_expenses", fuelEvents = "my_fuel_events"
        case cashCollections = "my_cash_collections", cashHandovers = "my_cash_handovers"
    }

    public func encode(to encoder: any Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(jobs, forKey: .jobs)
        try c.encode(machines, forKey: .machines)
        try c.encode(sites, forKey: .sites)
        try c.encode(customers, forKey: .customers)
        try c.encode(contracts, forKey: .contracts)
        try c.encode(staff, forKey: .staff)
        try c.encode(expenseCategories, forKey: .expenseCategories)
        try c.encode(cashCustody, forKey: .cashCustody)
        var lists = encoder.container(keyedBy: InboxList.self)
        for (key, rows) in inbox { try lists.encode(rows, forKey: key) }
    }

    /// Whether the server sent any inbox list.
    public var hasInbox: Bool { !inbox.isEmpty }

    public init(from decoder: any Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        jobs = try c.decodeIfPresent([JSONValue].self, forKey: .jobs) ?? []
        machines = try c.decodeIfPresent([JSONValue].self, forKey: .machines) ?? []
        sites = try c.decodeIfPresent([JSONValue].self, forKey: .sites) ?? []
        customers = try c.decodeIfPresent([JSONValue].self, forKey: .customers) ?? []
        contracts = try c.decodeIfPresent([JSONValue].self, forKey: .contracts) ?? []
        staff = try c.decodeIfPresent([JSONValue].self, forKey: .staff) ?? []
        expenseCategories = try c.decodeIfPresent([JSONValue].self, forKey: .expenseCategories) ?? []
        cashCustody = try c.decodeIfPresent([JSONValue].self, forKey: .cashCustody) ?? []
        let lists = try decoder.container(keyedBy: InboxList.self)
        for key in InboxList.allCases {
            if let rows = try lists.decodeIfPresent([JSONValue].self, forKey: key) { inbox[key] = rows }
        }
    }

    /// Entity type name → objects, in a stable order.
    public var byType: [(String, [JSONValue])] {
        [("job", jobs), ("machine", machines), ("site", sites), ("customer", customers),
         ("contract", contracts), ("staff", staff), ("expense_category", expenseCategories)]
    }
}

public struct BootstrapDTO: Codable, Hashable, Sendable {
    public let protocolVersion: Int?
    /// Optional protocol features the server supports (``SyncCapability``); nil from older servers.
    public let capabilities: [String]?
    public let serverTime: Date
    public let cursor: Int64
    public let deviceSession: DeviceSessionDTO
    public let data: SyncData
    public let policySnapshots: [PolicySnapshotDTO]

    enum CodingKeys: String, CodingKey {
        case protocolVersion = "protocol_version", capabilities, serverTime = "server_time", cursor
        case deviceSession = "device_session", data, policySnapshots = "policy_snapshots"
    }
}

public struct ChangesDTO: Codable, Hashable, Sendable {
    public let protocolVersion: Int?
    public let capabilities: [String]?
    public let serverTime: Date
    public let cursor: Int64
    public let hasMore: Bool
    public let data: SyncData
    public let policySnapshots: [PolicySnapshotDTO]

    enum CodingKeys: String, CodingKey {
        case protocolVersion = "protocol_version", capabilities, serverTime = "server_time", cursor, hasMore = "has_more"
        case data, policySnapshots = "policy_snapshots"
    }
}

/// One outbox operation on the wire (`OperationIn`).
public struct OperationIn: Codable, Hashable, Sendable {
    public let id: UUID
    public let opType: String
    public let createdAtDevice: Date
    public let dependsOn: [UUID]
    public let payload: JSONValue

    public init(id: UUID, opType: String, createdAtDevice: Date, dependsOn: [UUID], payload: JSONValue) {
        self.id = id
        self.opType = opType
        self.createdAtDevice = createdAtDevice
        self.dependsOn = dependsOn
        self.payload = payload
    }

    enum CodingKeys: String, CodingKey {
        case id, opType = "op_type", createdAtDevice = "created_at_device", dependsOn = "depends_on", payload
    }

    public func encode(to encoder: any Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(id.uuidString.lowercased(), forKey: .id)
        try c.encode(opType, forKey: .opType)
        try c.encode(createdAtDevice, forKey: .createdAtDevice)
        try c.encode(dependsOn.map { $0.uuidString.lowercased() }, forKey: .dependsOn)
        try c.encode(payload, forKey: .payload)
    }
}

public struct PushIn: Codable, Hashable, Sendable {
    public let deviceNow: Date
    public let operations: [OperationIn]

    public init(deviceNow: Date, operations: [OperationIn]) {
        self.deviceNow = deviceNow
        self.operations = operations
    }

    enum CodingKeys: String, CodingKey { case deviceNow = "device_now", operations }
}

public enum OperationOutcome: String, Codable, Sendable, CaseIterable {
    case acked = "ACKED", duplicate = "DUPLICATE", rejected = "REJECTED"
    case conflict = "CONFLICT", deferred = "DEFERRED", quarantined = "QUARANTINED"
}

public struct OperationResultDTO: Codable, Hashable, Sendable {
    public let id: UUID
    public let status: OperationOutcome
    public let result: JSONValue
    public let error: JSONValue?

    public init(id: UUID, status: OperationOutcome, result: JSONValue = .object([:]), error: JSONValue? = nil) {
        self.id = id
        self.status = status
        self.result = result
        self.error = error
    }

    public init(from decoder: any Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(UUID.self, forKey: .id)
        status = try c.decode(OperationOutcome.self, forKey: .status)
        result = try c.decodeIfPresent(JSONValue.self, forKey: .result) ?? .object([:])
        let error = try c.decodeIfPresent(JSONValue.self, forKey: .error)
        self.error = error == .null ? nil : error
    }

    enum CodingKeys: String, CodingKey { case id, status, result, error }

    /// Error code from `error.code`, falling back to `result.error.code`.
    public var errorCode: String? {
        error?["code"]?.stringValue ?? result["error"]?["code"]?.stringValue
    }

    public var errorMessage: String? {
        error?["message"]?.stringValue ?? result["error"]?["message"]?.stringValue
    }
}

public struct PushResultDTO: Codable, Hashable, Sendable {
    public let protocolVersion: Int?
    public let serverTime: Date
    public let clockOffsetS: Double
    public let clockSkewAlert: Bool
    public let results: [OperationResultDTO]

    public init(protocolVersion: Int?, serverTime: Date, clockOffsetS: Double, clockSkewAlert: Bool,
                results: [OperationResultDTO]) {
        self.protocolVersion = protocolVersion
        self.serverTime = serverTime
        self.clockOffsetS = clockOffsetS
        self.clockSkewAlert = clockSkewAlert
        self.results = results
    }

    enum CodingKeys: String, CodingKey {
        case protocolVersion = "protocol_version", serverTime = "server_time", clockOffsetS = "clock_offset_s"
        case clockSkewAlert = "clock_skew_alert", results
    }
}

public enum BlobPurpose: String, Codable, Sendable, CaseIterable {
    case meterPhoto = "METER_PHOTO", signature = "SIGNATURE", resetEvidence = "RESET_EVIDENCE"
    case expenseReceipt = "EXPENSE_RECEIPT"
}

public struct BlobStartIn: Codable, Hashable, Sendable {
    public let sha256: String
    public let sizeBytes: Int64
    public let purpose: BlobPurpose

    public init(sha256: String, sizeBytes: Int64, purpose: BlobPurpose) {
        self.sha256 = sha256
        self.sizeBytes = sizeBytes
        self.purpose = purpose
    }

    enum CodingKeys: String, CodingKey { case sha256, sizeBytes = "size_bytes", purpose }
}

public struct BlobSessionDTO: Codable, Hashable, Sendable {
    public let id: UUID
    public let chunkSize: Int
    public let totalChunks: Int
    public let receivedChunks: [Int]
    public let status: String
    public let attachmentID: UUID?
    public let expiresAt: Date

    public init(id: UUID, chunkSize: Int, totalChunks: Int, receivedChunks: [Int], status: String,
                attachmentID: UUID?, expiresAt: Date) {
        self.id = id
        self.chunkSize = chunkSize
        self.totalChunks = totalChunks
        self.receivedChunks = receivedChunks
        self.status = status
        self.attachmentID = attachmentID
        self.expiresAt = expiresAt
    }

    public var isComplete: Bool { status == "COMPLETE" && attachmentID != nil }

    enum CodingKeys: String, CodingKey {
        case id, status, chunkSize = "chunk_size", totalChunks = "total_chunks"
        case receivedChunks = "received_chunks", attachmentID = "attachment_id", expiresAt = "expires_at"
    }
}
