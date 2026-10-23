import AssetaCapture
import AssetaModel
import AssetaStore
import Foundation

/// Offline meter reset request (`METER_RESET_REQUEST`, server capability OP_METER_RESET_REQUEST):
/// checked with ``ResetRules``, the evidence photo linked as a resumable upload (purpose
/// RESET_EVIDENCE) and the operation queued atomically; it waits for the photo upload and is sent
/// with the completed upload id. The office's decision comes back in the inbox (`my_meter_resets`).
/// Same rules and wording as Android `RequestMeterReset`.
extension FieldRecorder {
    /// Nil when reset requests can be recorded, else why not.
    public func meterResetUnavailable() -> String? {
        let tenant = tenantID.uuidString.lowercased()
        guard let capabilities = try? store.syncState.value(SyncKey.capabilities, tenant: tenant) else {
            return "Sync once while online before requesting a meter reset."
        }
        guard capabilities.split(separator: ",").contains(Substring(SyncCapability.meterResetRequest)) else {
            return "Your company's server does not accept meter reset requests yet."
        }
        return nil
    }

    /// Records a reset request for `machineID`. `photo` must already be in the evidence store.
    /// `clientID` is generated once per form visit (a second save of the same visit is refused).
    @discardableResult
    public func requestMeterReset(machineID: UUID, oldReading: String, newReading: String, reason: String,
                                  photo: StoredEvidence?, effectiveAt: Date, clientID: UUID = UUID()) throws -> ClientOperation {
        if let blocked = meterResetUnavailable() { throw FieldRecorderError.notAllowed(blocked) }
        guard try store.syncState.entity(type: "machine", id: machineID, tenantID: tenantID) != nil else {
            throw FieldRecorderError.notAllowed("This machine is not on this device.")
        }
        let issues = ResetRules.validate(oldReading: oldReading, newReading: newReading, reason: reason, hasPhoto: photo != nil)
        if !issues.isEmpty { throw FieldRecorderError.invalid(issues.joined(separator: "\n")) }
        guard let photo, let old = ResetRules.parse(oldReading), let new = ResetRules.parse(newReading) else {
            throw FieldRecorderError.invalid("The request is incomplete")
        }
        let existing = try store.outbox.operations(tenantID: tenantID, owner: owner?.subject,
                                                   statuses: Set(ClientOperationStatus.allCases))
        if existing.contains(where: { $0.opType == OperationType.meterResetRequest.rawValue && $0.entityID == clientID }) {
            throw FieldRecorderError.notAllowed("This request is already saved.")
        }
        return try store.database.transaction {
            let local = try addAttachment(photo, purpose: .resetEvidence)
            let payload = MeterResetPayload(machineID: machineID, oldReading: old, newReading: new, effectiveAt: effectiveAt,
                                            reason: reason.trimmingCharacters(in: .whitespacesAndNewlines))
            return try enqueue(.meterResetRequest, entityType: "meter_reset", entityID: clientID, payload: payload,
                               dependsOn: [], attachments: [(local, .evidenceUpload)], createdAt: effectiveAt)
        }
    }
}
