import AssetaCapture
import AssetaModel
import AssetaStore
import Foundation

/// Local progress of one job: server state overlaid with not-yet-rejected local operations, so a
/// job started offline shows as in progress while its START waits in the outbox. Server-owned data
/// itself is never overwritten locally.
public struct JobProgress: Sendable, Equatable {
    public let serverStatus: JobStatus
    public let openingCaptureOp: UUID?
    public let startOp: UUID?
    public let activityOps: [UUID]
    public let closingCaptureOp: UUID?
    public let acknowledgementOp: UUID?
    public let completeOp: UUID?

    /// Operations that still count (anything not FAILED or CONFLICT).
    static func live(_ op: ClientOperation) -> Bool { op.status != .failed && op.status != .conflict }

    public init(serverStatus: JobStatus, operations: [ClientOperation]) {
        self.serverStatus = serverStatus
        let live = operations.filter(Self.live)
        func last(_ type: OperationType, _ match: (JSONValue) -> Bool = { _ in true }) -> UUID? {
            live.last { $0.opType == type.rawValue && ((try? JSONValue.parse($0.payloadJSON)).map(match) ?? false) }?.id
        }
        openingCaptureOp = last(.meterCapture) { $0["kind"]?.stringValue == ReadingKind.opening.rawValue }
        closingCaptureOp = last(.meterCapture) { $0["kind"]?.stringValue == ReadingKind.closing.rawValue }
        startOp = last(.jobTransition) { $0["action"]?.stringValue == JobAction.start.rawValue }
        completeOp = last(.jobTransition) { $0["action"]?.stringValue == JobAction.complete.rawValue }
        acknowledgementOp = last(.jobAcknowledgement)
        activityOps = live.filter { $0.opType == OperationType.jobActivity.rawValue }.map(\.id)
    }

    public var isStarted: Bool { startOp != nil || serverStatus == .inProgress || serverStatus == .completed }
    public var isCompleted: Bool { completeOp != nil || serverStatus == .completed }
    public var isClosed: Bool { isCompleted || serverStatus == .cancelled }

    /// What the supervisor may do next, mirroring the server: OPENING needs an APPROVED job, CLOSING an
    /// IN_PROGRESS one; work may be logged on approved or running jobs; COMPLETE needs the closing
    /// reading and the customer acknowledgement (server `ACK_REQUIRED`).
    public var canCaptureOpening: Bool { serverStatus == .approved && !isStarted && openingCaptureOp == nil }
    public var canStart: Bool { serverStatus == .approved && !isStarted && openingCaptureOp != nil }
    public var canLogActivity: Bool { (serverStatus == .approved || isStarted) && !isClosed }
    public var canCaptureClosing: Bool { isStarted && !isClosed && closingCaptureOp == nil }
    public var canAcknowledge: Bool { isStarted && closingCaptureOp != nil && acknowledgementOp == nil && !isClosed }
    public var canComplete: Bool { isStarted && closingCaptureOp != nil && acknowledgementOp != nil && !isClosed }

    /// Effective status for display.
    public var displayStatus: JobStatus {
        if isCompleted { return .completed }
        if isStarted { return .inProgress }
        return serverStatus
    }
}

public enum FieldRecorderError: Error, Equatable, Sendable {
    case notAllowed(String)
    case invalid(String)
}

/// Turns supervisor actions into durable outbox operations with the dependency chain
/// opening capture → START → activities / closing capture → acknowledgement → COMPLETE, and links
/// evidence files so an operation is never sent before its file has a server `attachment_id`.
/// Everything is recorded with the signed-in `owner`, and only that user's operations shape a job's
/// progress (another user's work on this phone is held for them).
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

    public func progress(jobID: UUID, serverStatus: JobStatus) throws -> JobProgress {
        JobProgress(serverStatus: serverStatus,
                    operations: try store.outbox.operations(tenantID: tenantID, owner: owner?.subject, jobID: jobID))
    }

    /// Records a meter reading. `photo` must already be in the evidence store. `snapshot` is the
    /// policy snapshot the UI enforced; its version ids travel with the capture.
    @discardableResult
    public func recordCapture(job: JobDTO, kind: ReadingKind, mode: CaptureMode, reading: String,
                              ocr: MeterOCRResult?, photo: StoredEvidence?, gps: GpsPayload, capturedAt: Date,
                              snapshot: MeterPolicySnapshot, captureID: UUID = UUID()) throws -> ClientOperation {
        let progress = try progress(jobID: job.id, serverStatus: job.status)
        switch kind {
        case .opening where !progress.canCaptureOpening: throw FieldRecorderError.notAllowed("Opening reading is not allowed now.")
        case .closing where !progress.canCaptureClosing: throw FieldRecorderError.notAllowed("Closing reading is not allowed now.")
        default: break
        }
        return try store.database.transaction {
            let photoLocal = try photo.map { try addAttachment($0, purpose: .meterPhoto) }
            let payload = MeterCapturePayload(
                id: captureID, jobID: job.id, kind: kind, captureMode: mode, reading: reading,
                ocrRawText: ocr.map { String($0.rawText.prefix(500)) }, ocrValue: ocr?.value,
                ocrConfidence: ocr.map { ($0.confidence * 1000).rounded() / 1000 }, ocrEngine: ocr?.engine,
                photoAttachmentID: nil, gps: gps, deviceID: deviceID, capturedAt: capturedAt,
                policyVersionIDs: snapshot.versionIDs)
            let dependencies = kind == .closing ? [progress.startOp].compactMap { $0 } : []
            return try enqueue(.meterCapture, entityType: "meter_capture", entityID: captureID, payload: payload,
                               dependsOn: dependencies, attachments: photoLocal.map { [($0, .photo)] } ?? [],
                               createdAt: capturedAt)
        }
    }

    @discardableResult
    public func recordTransition(job: JobDTO, action: JobAction, at date: Date = Date()) throws -> ClientOperation {
        let progress = try progress(jobID: job.id, serverStatus: job.status)
        let dependencies: [UUID]
        switch action {
        case .start:
            guard progress.canStart else { throw FieldRecorderError.notAllowed("Capture the opening reading first.") }
            dependencies = [progress.openingCaptureOp].compactMap { $0 }
        case .complete:
            guard progress.closingCaptureOp != nil, progress.isStarted, !progress.isClosed else {
                throw FieldRecorderError.notAllowed("Capture the closing reading first.")
            }
            guard progress.acknowledgementOp != nil else {
                throw FieldRecorderError.notAllowed("Get the customer acknowledgement first.")
            }
            if try runningEntry(jobID: job.id) != nil {
                throw FieldRecorderError.notAllowed("Stop the running work-log entry first.")
            }
            dependencies = [progress.closingCaptureOp, progress.acknowledgementOp].compactMap { $0 } + progress.activityOps
        }
        return try enqueue(.jobTransition, entityType: "job", entityID: job.id,
                           payload: JobTransitionPayload(jobID: job.id, action: action), dependsOn: dependencies,
                           createdAt: date)
    }

    @discardableResult
    public func recordActivity(job: JobDTO, type: ActivityType, startedAt: Date, endedAt: Date?, billable: Bool?,
                               note: String?, at date: Date = Date(), clientID: UUID = UUID()) throws -> ClientOperation {
        let progress = try progress(jobID: job.id, serverStatus: job.status)
        guard progress.canLogActivity else {
            throw FieldRecorderError.notAllowed("Work can only be logged on approved or running jobs.")
        }
        if let endedAt, endedAt < startedAt { throw FieldRecorderError.invalid("The end time is before the start time.") }
        if type == .note && (note?.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ?? true) {
            throw FieldRecorderError.invalid("Write a note first.")
        }
        let trimmed = note?.trimmingCharacters(in: .whitespacesAndNewlines)
        let payload = ActivityPayload(jobID: job.id, clientID: clientID, activityType: type, startedAt: startedAt, endedAt: endedAt,
                                      billable: billable, note: (trimmed?.isEmpty ?? true) ? nil : String(trimmed!.prefix(2000)),
                                      deviceID: deviceID)
        return try enqueue(.jobActivity, entityType: "job_activity", entityID: payload.clientID, payload: payload,
                           dependsOn: [progress.startOp].compactMap { $0 }, createdAt: date)
    }

    @discardableResult
    public func recordAcknowledgement(job: JobDTO, method: AcknowledgementMethod, signerName: String,
                                      signerPhone: String?, signature: StoredEvidence?, acknowledgedHours: String?,
                                      at date: Date = Date()) throws -> ClientOperation {
        let progress = try progress(jobID: job.id, serverStatus: job.status)
        guard progress.canAcknowledge else { throw FieldRecorderError.notAllowed("Capture the closing reading first.") }
        let name = signerName.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !name.isEmpty, name.count <= 200 else { throw FieldRecorderError.invalid("Enter the customer's name.") }
        if method == .signature && signature == nil { throw FieldRecorderError.invalid("The customer must sign.") }
        return try store.database.transaction {
            let signatureLocal = try signature.map { try addAttachment($0, purpose: .signature) }
            let phone = signerPhone?.trimmingCharacters(in: .whitespaces)
            let payload = AcknowledgementPayload(
                jobID: job.id, method: method, signerName: name, signerPhone: (phone?.isEmpty ?? true) ? nil : phone,
                signatureAttachmentID: nil, acknowledgedHours: acknowledgedHours, capturedAt: date)
            return try enqueue(.jobAcknowledgement, entityType: "job_acknowledgement", entityID: payload.clientID,
                               payload: payload, dependsOn: [progress.closingCaptureOp].compactMap { $0 },
                               attachments: signatureLocal.map { [($0, .signature)] } ?? [], createdAt: date)
        }
    }

    // MARK: - Private

    func addAttachment(_ evidence: StoredEvidence, purpose: BlobPurpose) throws -> UUID {
        try store.attachments.add(NewLocalAttachment(
            tenantID: tenantID, purpose: purpose.rawValue, fileName: evidence.fileName, sha256: evidence.sha256,
            sizeBytes: evidence.sizeBytes, contentType: evidence.contentType, ownerSubject: owner?.subject)).id
    }

    func enqueue(_ type: OperationType, entityType: String, entityID: UUID, payload: some Encodable,
                         dependsOn: [UUID], attachments: [(localID: UUID, field: AttachmentPayloadField)] = [],
                         createdAt: Date) throws -> ClientOperation {
        let json = try JSONValue.encode(payload).lowercasingUUIDs().jsonString()
        return try store.outbox.enqueue(NewClientOperation(
            tenantID: tenantID, opType: type.rawValue, entityType: entityType, entityID: entityID, payloadJSON: json,
            dependsOn: dependsOn, attachments: attachments, createdAtDevice: createdAt, owner: owner))
    }
}
