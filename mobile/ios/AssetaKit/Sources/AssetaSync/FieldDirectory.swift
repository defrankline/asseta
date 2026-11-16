import AssetaCapture
import AssetaModel
import AssetaSecurity
import AssetaStore
import Foundation

/// One outbox item as shown on the sync status screen.
public struct OutboxItem: Sendable, Equatable, Identifiable {
    public let operation: ClientOperation
    /// `server_state` returned with a conflict, if any.
    public let serverState: String?
    /// Waiting for an earlier item, or for its photo upload.
    public let waitingFor: String?
    public var id: UUID { operation.id }

    public var title: String {
        let type = OperationType(rawValue: operation.opType)
        if let type, let title = FieldAccountabilityTexts.operationTitle(type, payload: try? JSONValue.parse(operation.payloadJSON)) {
            return title
        }
        return switch type {
        case .meterCapture: "Meter reading"
        case .expense: "Expense"
        case .cashCollection: "Cash collection"
        case .cashHandover: "Cash handover"
        case .fuelEvent: "Fuel event"
        case .meterResetRequest: "Meter reset request"
        case .machineReport: "Machine report"
        case .creditInvoicePayment: "Credit invoice payment"
        case .hoursPurchase, .hoursTransferRequest, .cashTransfer, .cashTransferAcknowledgement, .cashFloatAcknowledgement,
             .meterBaseline, .meterCorrection, .cashRetentionRequest,
             .pettyCashAcknowledgement, .pettyCashTopUpRequest, .pettyCashReturn, .pettyCashCount,
             .pettyCashHolderChangeAcknowledgement, .pettyCashAdvanceClearance, .pettyCashAdvance, nil: operation.opType
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

/// Read side for the UI: cached entities, policy gate, sync overview.
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
            let result = op.serverResultJSON.flatMap { try? JSONValue.parse($0) }
            let state = result?["result"]?["server_state"].flatMap { try? $0.jsonString() }
            var waiting: String?
            if let parent = op.dependencies.compactMap({ byID[$0] }).first(where: { $0.status != .acked }) {
                waiting = parent.status == .failed || parent.status == .conflict
                    ? "Blocked by an earlier item that needs attention" : "Waiting for an earlier item"
            } else if awaitingUpload.contains(op.id) {
                waiting = op.opType == OperationType.cashHandover.rawValue || op.opType == OperationType.hoursTransferRequest.rawValue
                    ? FieldAccountabilityTexts.outboxWaitingPhotos : "Waiting for its photo/receipt upload"
            }
            return OutboxItem(operation: op, serverState: state, waitingFor: waiting)
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
