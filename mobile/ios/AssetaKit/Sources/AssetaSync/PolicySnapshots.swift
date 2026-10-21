import AssetaModel
import AssetaStore
import Foundation

/// A `METER_CAPTURE` policy snapshot the device enforces offline.
public struct MeterPolicySnapshot: Sendable, Equatable {
    public let scopeKey: String
    public let versionIDs: [UUID]
    public let versionStamp: String
    public let policy: MeterCapturePolicy
    public let validUntil: Date

    public init(scopeKey: String, versionIDs: [UUID], versionStamp: String, policy: MeterCapturePolicy, validUntil: Date) {
        self.scopeKey = scopeKey
        self.versionIDs = versionIDs
        self.versionStamp = versionStamp
        self.policy = policy
        self.validUntil = validUntil
    }

    public static let policyType = "METER_CAPTURE"

    /// Decodes a stored snapshot; nil if its values do not form a valid policy (fails closed).
    public init?(_ stored: StoredPolicySnapshot) {
        guard stored.policyType == Self.policyType,
              let ids = try? JSONDecoder().decode([UUID].self, from: Data(stored.versionIDsJSON.utf8)),
              let policy = try? AssetaJSON.decoder().decode(MeterCapturePolicy.self, from: Data(stored.valuesJSON.utf8))
        else { return nil }
        self.init(scopeKey: stored.scopeKey, versionIDs: ids, versionStamp: stored.versionStamp, policy: policy,
                  validUntil: stored.validUntil)
    }

    static func stored(_ dto: PolicySnapshotDTO, receivedAt: Date) throws -> StoredPolicySnapshot {
        StoredPolicySnapshot(
            policyType: dto.policyType, scopeKey: dto.scopeKey,
            versionIDsJSON: String(decoding: try JSONEncoder().encode(dto.versionIDs.map(\.lowercased)), as: UTF8.self),
            versionStamp: dto.versionStamp, valuesJSON: try dto.values.jsonString(), validUntil: dto.validUntil,
            receivedAt: receivedAt)
    }
}

public enum PolicySelection {
    /// The machine-scoped snapshot if present, else the tenant snapshot.
    public static func select(_ snapshots: [MeterPolicySnapshot], machineID: UUID) -> MeterPolicySnapshot? {
        snapshots.first { $0.scopeKey == "machine:\(machineID.lowercased)" }
            ?? snapshots.first { $0.scopeKey.lowercased() == "machine:\(machineID.lowercased)" }
            ?? snapshots.first { $0.scopeKey == "tenant" }
    }
}

public enum CaptureBlockReason: Sendable, Equatable {
    case noSnapshot
    case snapshotExpired(validUntil: Date)
    case offlineGrantExpired(until: Date)

    public var message: String {
        switch self {
        case .noSnapshot: "Connect to refresh rules. No capture rules have been downloaded for this machine yet."
        case let .snapshotExpired(date): "Connect to refresh rules. The capture rules expired \(date.formatted(date: .abbreviated, time: .shortened))."
        case let .offlineGrantExpired(date): "Connect to refresh rules. Offline use of this device ended \(date.formatted(date: .abbreviated, time: .shortened))."
        }
    }
}

public enum CaptureGate: Sendable, Equatable {
    case allowed(MeterPolicySnapshot)
    case blocked(CaptureBlockReason)

    /// New captures need an unexpired snapshot and an unexpired offline grant. `now` should be the
    /// trusted time (see ``ClockMonitor/trustedNow(_:source:)``) so winding the clock back does not help.
    public static func evaluate(snapshot: MeterPolicySnapshot?, offlineGrantUntil: Date?, now: Date) -> CaptureGate {
        guard let snapshot else { return .blocked(.noSnapshot) }
        if now > snapshot.validUntil { return .blocked(.snapshotExpired(validUntil: snapshot.validUntil)) }
        if let grant = offlineGrantUntil, now > grant { return .blocked(.offlineGrantExpired(until: grant)) }
        return .allowed(snapshot)
    }
}
