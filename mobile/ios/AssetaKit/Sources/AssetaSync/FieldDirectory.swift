import AssetaCapture
import AssetaModel
import AssetaSecurity
import AssetaStore
import Foundation

/// One job with the cached entities the Supervisor screens show.
public struct FieldJob: Sendable, Equatable, Identifiable {
    public let job: JobDTO
    public let machine: MachineDTO?
    public let site: JobSiteDTO?
    public let customer: CustomerDTO?
    public let contract: ContractDTO?
    /// Set for a job this supervisor requested from the field, until the owner approves it.
    public var request: JobRequestState?
    public var id: UUID { job.id }
    /// Meter display precision (machine setting; default 1 like the server).
    public var decimalPlaces: Int { machine?.meterDecimalPlaces ?? 1 }
}

/// One outbox item as shown on the sync status screen.
public struct OutboxItem: Sendable, Equatable, Identifiable {
    public let operation: ClientOperation
    public let jobID: UUID?
    /// `server_state` returned with a conflict (e.g. the job's current status), if any.
    public let serverState: String?
    /// Waiting for an earlier item, or for its photo/signature upload.
    public let waitingFor: String?
    public var id: UUID { operation.id }

    public var title: String {
        let type = OperationType(rawValue: operation.opType)
        if let type, let title = FieldAccountabilityTexts.operationTitle(type, payload: try? JSONValue.parse(operation.payloadJSON)) {
            return title
        }
        return switch type {
        case .meterCapture: "Meter reading"
        case .jobActivity: "Work log entry"
        case .jobAcknowledgement: "Customer acknowledgement"
        case .jobTransition: operation.payloadJSON.contains("COMPLETE") ? "Complete job" : "Start job"
        case .expense: "Expense"
        case .cashCollection: "Cash collection"
        case .cashHandover: "Cash handover"
        case .fuelEvent: "Fuel event"
        case .meterResetRequest: "Meter reset request"
        case .jobRequest: JobRequestText.operation
        case .hoursPurchase, .hoursTransferRequest, .cashTransfer, .cashTransferAcknowledgement, .cashFloatAcknowledgement,
             .meterBaseline, .meterCorrection, .cashRetentionRequest, nil: operation.opType
        }
    }
}

public struct SyncOverview: Sendable, Equatable {
    public let counts: [ClientOperationStatus: Int]
    public let items: [OutboxItem]
    public let pendingUploads: Int
    public let failedUploads: [LocalAttachment]
    public let lastSuccessAt: Date?
    public let nextAttemptAt: Date?
    public let consecutiveFailures: Int
    public let serverClockSkewAlert: Bool
    public let offlineGrantUntil: Date?
    public let clockStatus: ClockStatus
    /// Unsynced work other accounts left on this phone: held until that account signs in again.
    public var heldAccounts: [HeldAccount] = []

    public var unsyncedCount: Int { counts.filter { $0.key != .acked }.values.reduce(0, +) }
}

/// Read side for the UI: cached jobs and entities, policy gate, sync overview.
/// Device-owned records (operations, evidence) are the signed-in `owner`'s only.
public struct FieldDirectory: Sendable {
    let store: LocalStore
    let tenantID: UUID
    let clock: any ClockSource
    let owner: AccountIdentity?

    public init(store: LocalStore, tenantID: UUID, clock: any ClockSource = SystemClockSource(),
                owner: AccountIdentity? = nil) {
        self.store = store
        self.tenantID = tenantID
        self.clock = clock
        self.owner = owner
    }

    private var tenantKey: String { tenantID.uuidString.lowercased() }

    private func decode<T: Decodable>(_ type: String, _ id: UUID?) -> T? {
        guard let id, let entity = try? store.syncState.entity(type: type, id: id, tenantID: tenantID) else { return nil }
        return try? AssetaJSON.decoder().decode(T.self, from: Data(entity.json.utf8))
    }

    /// Synced jobs plus this user's job requests the server has not delivered yet (shown right away).
    public func jobs() throws -> [FieldJob] {
        let requests = try requestOperations()
        let byID = Dictionary(requests.map { ($0.entityID, $0) }, uniquingKeysWith: { first, _ in first })
        let server = try store.syncState.entities(type: "job", tenantID: tenantID)
            .compactMap { try? AssetaJSON.decoder().decode(JobDTO.self, from: Data($0.json.utf8)) }
        let serverIDs = Set(server.map(\.id))
        let local = pendingRequests(requests, serverIDs: serverIDs).compactMap(localRequestJob)
        return (server.map { fieldJob($0, requestOp: byID[$0.id]) } + local)
            .sorted { ($0.job.plannedStart, $0.job.jobNumber) < ($1.job.plannedStart, $1.job.jobNumber) }
    }

    public func job(id: UUID) -> FieldJob? {
        let op = try? requestOperations().first { $0.entityID == id }
        if let job = decode("job", id) as JobDTO? { return fieldJob(job, requestOp: op) }
        return op.flatMap(localRequestJob)
    }

    private func fieldJob(_ job: JobDTO, requestOp: ClientOperation? = nil) -> FieldJob {
        let contract: ContractDTO? = decode("contract", job.contractID)
        return FieldJob(job: job, machine: decode("machine", job.machineID), site: decode("site", job.jobSiteID),
                        customer: decode("customer", contract?.customerID), contract: contract,
                        request: JobRequestState.of(job: job, requestOp: requestOp))
    }

    public func meterSnapshots() throws -> [MeterPolicySnapshot] {
        try store.syncState.policySnapshots(policyType: MeterPolicySnapshot.policyType, tenantID: tenantID)
            .compactMap(MeterPolicySnapshot.init)
    }

    public func clockReference() -> ClockReference? {
        guard let text = try? store.syncState.value(SyncKey.clockReference, tenant: SyncStateStore.deviceScope) else {
            return nil
        }
        return try? JSONDecoder().decode(ClockReference.self, from: Data(text.utf8))
    }

    public func offlineGrantUntil() -> Date? {
        (try? store.syncState.value(SyncKey.grantUntil, tenant: tenantKey))?
            .flatMap(Int64.init).map(Date.init(millisecondsSince1970:))
    }

    /// Whether a new capture for `machineID` may start, and under which policy snapshot.
    public func captureGate(machineID: UUID) throws -> CaptureGate {
        let snapshot = PolicySelection.select(try meterSnapshots(), machineID: machineID)
        let now = ClockMonitor.enforcementNow(clockReference(), source: clock)
        return CaptureGate.evaluate(snapshot: snapshot, offlineGrantUntil: offlineGrantUntil(), now: now)
    }

    public func clockStatus() -> ClockStatus { ClockMonitor.status(clockReference(), source: clock) }

    public func overview() throws -> SyncOverview {
        let mine = owner?.subject
        let all = try store.outbox.operations(tenantID: tenantID, owner: mine, statuses: Set(ClientOperationStatus.allCases))
        let byID = Dictionary(uniqueKeysWithValues: all.map { ($0.id, $0) })
        let pendingFiles = try store.attachments.attachments(tenantID: tenantID, statuses: [.pending], owner: mine)
        let unsynced = all.filter { $0.status != .acked }
        let awaitingUpload = try store.attachments.operationsAwaitingUpload(tenantID: tenantID)
        let items = unsynced.map { op -> OutboxItem in
            let payload = try? JSONValue.parse(op.payloadJSON)
            let result = op.serverResultJSON.flatMap { try? JSONValue.parse($0) }
            let state = result?["result"]?["server_state"].flatMap { try? $0.jsonString() }
            var waiting: String?
            if let parent = op.dependencies.compactMap({ byID[$0] }).first(where: { $0.status != .acked }) {
                waiting = parent.status == .failed || parent.status == .conflict
                    ? "Blocked by an earlier item that needs attention" : "Waiting for an earlier item"
            } else if awaitingUpload.contains(op.id) {
                waiting = "Waiting for its photo/receipt/signature upload"
            }
            return OutboxItem(operation: op, jobID: payload?["job_id"]?.stringValue.flatMap(UUID.init(uuidString:)),
                              serverState: state, waitingFor: waiting)
        }
        func int(_ key: String) -> Int { Int((try? store.syncState.value(key, tenant: tenantKey)) ?? nil ?? "0") ?? 0 }
        func date(_ key: String) -> Date? {
            ((try? store.syncState.value(key, tenant: tenantKey)) ?? nil).flatMap(Int64.init).map(Date.init(millisecondsSince1970:))
        }
        return SyncOverview(
            counts: try store.outbox.statusCounts(tenantID: tenantID, owner: mine), items: items,
            pendingUploads: pendingFiles.count,
            failedUploads: try store.attachments.attachments(tenantID: tenantID, statuses: [.failed], owner: mine),
            lastSuccessAt: date(SyncKey.lastSuccessAt), nextAttemptAt: date(SyncKey.nextSyncAt),
            consecutiveFailures: int(SyncKey.failures), serverClockSkewAlert: int(SyncKey.clockSkewAlert) == 1,
            offlineGrantUntil: offlineGrantUntil(), clockStatus: clockStatus(),
            heldAccounts: try mine.map { try store.outbox.heldAccounts(tenantID: tenantID, excluding: $0) } ?? [])
    }
}

/// Wipe after `DEVICE_REVOKED` (details `WIPE_LOCAL_DATA`): the encrypted database and its
/// Keychain key, the OAuth tokens and every cached evidence file. The device id is kept so the
/// device stays revoked. Every step runs even if another fails; failures are returned.
public enum DeviceWipe {
    @discardableResult
    public static func wipe(database: EncryptedDatabase?, databaseURL: URL, keyProvider: DatabaseKeyProvider,
                            tokens: TokenStore, evidence: EvidenceStore) -> [any Error] {
        var errors: [any Error] = []
        do { try LocalStore.destroy(at: databaseURL, keyProvider: keyProvider, closing: database) } catch { errors.append(error) }
        do { try tokens.clear() } catch { errors.append(error) }
        do { try evidence.wipeAll() } catch { errors.append(error) }
        return errors
    }
}
