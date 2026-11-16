import AssetaCapture
import AssetaModel
import AssetaStore
import Foundation

public enum FieldRecorderError: Error, Equatable, Sendable {
    case notAllowed(String)
    case invalid(String)
}

/// Turns supervisor actions into durable outbox operations and links evidence files so an operation is never sent
/// before its file has a server `attachment_id`. Everything is recorded with the signed-in `owner` (another user's
/// work on this phone is held for them). The operations themselves live in extensions (machine reports, readings,
/// money, petty cash, …).
public struct FieldRecorder: Sendable {
    let store: LocalStore
    let tenantID: UUID
    let deviceID: String
    let owner: AccountIdentity?

    public init(store: LocalStore, tenantID: UUID, deviceID: String, owner: AccountIdentity? = nil) {
        self.store = store
        self.tenantID = tenantID
        self.deviceID = deviceID
        self.owner = owner
    }

    // MARK: - Private

    func addAttachment(_ evidence: StoredEvidence, purpose: BlobPurpose) throws -> UUID {
        try store.attachments.add(NewLocalAttachment(
            tenantID: tenantID, purpose: purpose.rawValue, fileName: evidence.fileName, sha256: evidence.sha256,
            sizeBytes: evidence.sizeBytes, contentType: evidence.contentType, ownerSubject: owner?.subject)).id
    }

    /// `operationID` defaults to a fresh id; ops whose server key is the operation id (HOURS_PURCHASE,
    /// HOURS_TRANSFER_REQUEST, METER_BASELINE) pass the form's id so a second save of the same visit is refused.
    func enqueue(_ type: OperationType, entityType: String, entityID: UUID, payload: some Encodable,
                         dependsOn: [UUID], attachments: [(localID: UUID, field: AttachmentPayloadField)] = [],
                         createdAt: Date, operationID: UUID = UUID()) throws -> ClientOperation {
        let json = try JSONValue.encode(payload).lowercasingUUIDs().jsonString()
        return try store.outbox.enqueue(NewClientOperation(
            id: operationID, tenantID: tenantID, opType: type.rawValue, entityType: entityType, entityID: entityID, payloadJSON: json,
            dependsOn: dependsOn, attachments: attachments, createdAtDevice: createdAt, owner: owner))
    }
}
