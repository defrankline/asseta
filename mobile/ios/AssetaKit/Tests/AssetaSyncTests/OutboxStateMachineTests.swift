import AssetaCapture
import AssetaModel
import AssetaSecurity
import AssetaStore
@testable import AssetaSync
import Foundation
import Testing

/// Every push outcome mapped onto the outbox, plus dependency/attachment gating.
struct OutboxStateMachineTests {
    let store: LocalStore
    let tenant = SyncFixtures.tenant
    let now = Date(timeIntervalSince1970: 1_792_000_000)

    init() throws {
        store = try LocalStore.open(at: try temporaryDirectory().appendingPathComponent("o.sqlite"),
                                    keyProvider: DatabaseKeyProvider(store: InMemorySecretStore()))
    }

    func sentOp(dependsOn: [UUID] = []) throws -> ClientOperation {
        let op = try store.outbox.enqueue(NewClientOperation(tenantID: tenant, opType: "JOB_ACTIVITY", entityType: "job_activity",
                                                             entityID: UUID(), payloadJSON: #"{"job_id":"x"}"#, dependsOn: dependsOn))
        try store.outbox.markSent(id: op.id)
        return op
    }

    func result(_ id: UUID, _ status: OperationOutcome, code: String? = nil, serverState: Bool = false) -> OperationResultDTO {
        var result: [String: JSONValue] = [:]
        var error: JSONValue?
        if let code {
            error = .object(["code": .string(code), "message": .string("m")])
            result["error"] = error
        }
        if serverState { result["server_state"] = .object(["job_status": .string("CANCELLED")]) }
        if status == .acked || (status == .duplicate && code == nil) { result["entity"] = .object(["version": .number(4)]) }
        return OperationResultDTO(id: id, status: status, result: .object(result), error: error)
    }

    @Test(arguments: [
        (OperationOutcome.acked, nil as String?, false, ClientOperationStatus.acked),
        (.duplicate, nil, false, .acked),
        (.duplicate, "SUBSCRIPTION_READ_ONLY", false, .quarantined),
        (.duplicate, "INVALID_JOB_TRANSITION", true, .conflict),
        (.duplicate, "VALIDATION_FAILED", false, .failed),
        (.deferred, "DEPENDENCY_PENDING", false, .pending),
        (.conflict, "MACHINE_BUSY", true, .conflict),
        (.rejected, "PERMISSION_DENIED", false, .failed),
        (.quarantined, "SUBSCRIPTION_READ_ONLY", false, .quarantined),
    ])
    func outcomeMapsToStatus(_ outcome: OperationOutcome, _ code: String?, _ state: Bool, _ expected: ClientOperationStatus) throws {
        let op = try sentOp()
        try PushOutcomeApplier(outbox: store.outbox).apply(result(op.id, outcome, code: code, serverState: state), now: now)
        let stored = try #require(try store.outbox.operation(id: op.id))
        #expect(stored.status == expected)
        if expected == .acked {
            #expect(stored.serverRevision == 4)
            #expect(stored.serverResultJSON != nil)
        }
        if expected == .failed || expected == .conflict { #expect(stored.errorCode == code) }
        if outcome == .deferred { #expect(stored.nextAttemptAt == now.addingTimeInterval(PushOutcomeApplier.deferDelay)) }
        if expected == .quarantined { #expect(stored.nextAttemptAt == now.addingTimeInterval(PushOutcomeApplier.quarantineRetry)) }
    }

    @Test func missingResultsGoBackToPendingNeverAcked() throws {
        let a = try sentOp(), b = try sentOp()
        let response = PushResultDTO(protocolVersion: 1, serverTime: now, clockOffsetS: 0, clockSkewAlert: false,
                                     results: [result(a.id, .acked)])
        let outcomes = try PushOutcomeApplier(outbox: store.outbox).apply(response, sent: [a.id, b.id], now: now)
        #expect(outcomes[b.id] == .missing)
        #expect(try store.outbox.operation(id: b.id)?.status == .pending)
    }

    @Test func illegalTransitionsAreRefused() throws {
        let op = try store.outbox.enqueue(NewClientOperation(tenantID: tenant, opType: "X", entityType: "x", entityID: UUID(),
                                                             payloadJSON: "{}"))
        #expect(throws: OutboxError.self) { try store.outbox.markConflict(id: op.id, code: nil, message: "", resultJSON: nil) }
        #expect(throws: OutboxError.self) { try store.outbox.release(id: op.id, error: nil, retryAt: nil) }
        try store.outbox.markSent(id: op.id)
        try store.outbox.markConflict(id: op.id, code: "C", message: "m", resultJSON: "{}")
        #expect(throws: OutboxError.self) { try store.outbox.requeue(id: op.id) } // conflicts are never auto-retried
        #expect(throws: OutboxError.self) { try store.outbox.markSent(id: op.id) }
    }

    @Test func quarantinedOpReleasedAfterNetworkErrorStaysQuarantined() throws {
        let op = try sentOp()
        try store.outbox.quarantine(id: op.id, reason: "held", resultJSON: nil, retryAt: now)
        #expect(try store.outbox.readyToSend(tenantID: tenant, now: now, limit: 10).map(\.id) == [op.id])
        try store.outbox.markSent(id: op.id)
        try store.outbox.release(id: op.id, error: "offline", retryAt: nil)
        #expect(try store.outbox.operation(id: op.id)?.status == .quarantined)
        try store.outbox.markSent(id: op.id)
        #expect(try store.outbox.recoverInFlight(tenantID: tenant) == 1)
        #expect(try store.outbox.operation(id: op.id)?.status == .quarantined)
    }

    @Test func allDependenciesMustBeAckedAndAttachmentsUploaded() throws {
        let parentA = try store.outbox.enqueue(NewClientOperation(tenantID: tenant, opType: "A", entityType: "a", entityID: UUID(),
                                                                  payloadJSON: "{}", createdAtDevice: now))
        let parentB = try store.outbox.enqueue(NewClientOperation(tenantID: tenant, opType: "B", entityType: "b", entityID: UUID(),
                                                                  payloadJSON: "{}", createdAtDevice: now.addingTimeInterval(1)))
        let file = try store.attachments.add(NewLocalAttachment(tenantID: tenant, purpose: "SIGNATURE", fileName: "s.png",
                                                                sha256: String(repeating: "a", count: 64), sizeBytes: 10,
                                                                contentType: "image/png"))
        let child = try store.outbox.enqueue(NewClientOperation(
            tenantID: tenant, opType: "C", entityType: "c", entityID: UUID(), payloadJSON: #"{"method":"SIGNATURE"}"#,
            dependsOn: [parentA.id, parentB.id], attachments: [(file.id, .signature)], createdAtDevice: now.addingTimeInterval(2)))
        #expect(child.dependencies.count == 2)
        func ready() throws -> [UUID] { try store.outbox.readyToSend(tenantID: tenant, now: now, limit: 10).map(\.id) }
        #expect(try ready() == [parentA.id, parentB.id])
        for parent in [parentA, parentB] {
            try store.outbox.markSent(id: parent.id)
            try store.outbox.markAcked(id: parent.id, serverRevision: 1)
        }
        #expect(try ready().isEmpty) // dependencies ACKED but the signature is not uploaded yet
        let serverID = UUID()
        try store.attachments.markComplete(id: file.id, attachmentID: serverID)
        #expect(try ready() == [child.id])
        let payload = try JSONValue.parse(try #require(try store.outbox.operation(id: child.id)).payloadJSON)
        #expect(payload["signature_attachment_id"]?.stringValue == serverID.lowercased)
    }

    @Test func enqueueRefusesUnknownAttachment() {
        #expect(throws: OutboxError.self) {
            try store.outbox.enqueue(NewClientOperation(tenantID: tenant, opType: "C", entityType: "c", entityID: UUID(),
                                                        payloadJSON: "{}", attachments: [(UUID(), .photo)]))
        }
    }
}

/// The supervisor-side chain: opening capture → START → activities/closing → acknowledgement → COMPLETE.
struct JobProgressTests {
    @Test func dependencyChainAndAllowedActions() throws {
        let h = try SyncHarness()
        let job = SyncFixtures.jobDTO
        var progress = try h.recorder.progress(jobID: job.id, serverStatus: .approved)
        #expect(progress.canCaptureOpening && !progress.canStart && !progress.canCaptureClosing)
        #expect(throws: FieldRecorderError.self) { try h.recorder.recordTransition(job: job, action: .start) }

        let (capture, start) = try h.recordOpeningAndStart()
        #expect(start.dependencies == [capture.id])
        progress = try h.recorder.progress(jobID: job.id, serverStatus: .approved)
        #expect(progress.displayStatus == .inProgress && progress.canCaptureClosing && !progress.canCaptureOpening)

        let activity = try h.recorder.recordActivity(job: job, type: .downtime, startedAt: h.clock.wallNow,
                                                     endedAt: h.clock.wallNow.addingTimeInterval(600), billable: false, note: " hose ")
        #expect(activity.dependencies == [start.id])
        #expect(try JSONValue.parse(activity.payloadJSON)["note"]?.stringValue == "hose")
        let closing = try h.recorder.recordCapture(
            job: job, kind: .closing, mode: .manual, reading: "1240.0", ocr: nil, photo: nil, gps: .failed(.disabled),
            capturedAt: h.clock.wallNow, snapshot: SyncFixtures.meterSnapshot)
        #expect(closing.dependencies == [start.id])
        #expect(throws: FieldRecorderError.self) {
            try h.recorder.recordAcknowledgement(job: job, method: .signature, signerName: "Ann", signerPhone: nil,
                                                 signature: nil, acknowledgedHours: nil)
        }
        let ack = try h.recorder.recordAcknowledgement(job: job, method: .nameConfirmation, signerName: " Ann Banda ",
                                                       signerPhone: "", signature: nil, acknowledgedHours: "5.5")
        #expect(ack.dependencies == [closing.id])
        let complete = try h.recorder.recordTransition(job: job, action: .complete)
        #expect(Set(complete.dependencies) == [closing.id, ack.id, activity.id])
        progress = try h.recorder.progress(jobID: job.id, serverStatus: .approved)
        #expect(progress.isCompleted && !progress.canLogActivity)
        let gps = try JSONValue.parse(closing.payloadJSON)["gps"]
        #expect(gps == .object(["status": .string("DISABLED"), "provider": .string("corelocation")])) // no coordinates
    }

    @Test func rejectedCaptureCanBeRetaken() throws {
        let h = try SyncHarness()
        let job = SyncFixtures.jobDTO
        let first = try h.recorder.recordCapture(job: job, kind: .opening, mode: .manual, reading: "1.0", ocr: nil, photo: nil,
                                                 gps: .failed(.timeout), capturedAt: h.clock.wallNow, snapshot: SyncFixtures.meterSnapshot)
        try h.store.outbox.markSent(id: first.id)
        try h.store.outbox.markFailed(id: first.id, code: "VALIDATION_FAILED", message: "bad", resultJSON: nil)
        #expect(try h.recorder.progress(jobID: job.id, serverStatus: .approved).canCaptureOpening)
    }
}

struct DeviceWipeTests {
    @Test func wipeRemovesDatabaseKeyTokensAndEvidence() throws {
        let dir = try temporaryDirectory()
        let secrets = InMemorySecretStore()
        let keys = DatabaseKeyProvider(store: secrets)
        let url = dir.appendingPathComponent("db.sqlite")
        let store = try LocalStore.open(at: url, keyProvider: keys)
        try store.outbox.enqueue(NewClientOperation(tenantID: UUID(), opType: "X", entityType: "x", entityID: UUID(), payloadJSON: "{}"))
        let tokens = TokenStore(store: secrets)
        try tokens.save(StoredTokens(accessToken: "a", accessTokenExpiresAt: .distantFuture, refreshToken: "r",
                                     refreshTokenExpiresAt: nil, idToken: nil))
        let deviceID = try DeviceIdentity.loadOrCreate(store: secrets)
        let evidence = EvidenceStore(directory: dir.appendingPathComponent("evidence"))
        _ = try evidence.store(Data([1, 2, 3]), fileExtension: "jpg", contentType: "image/jpeg")

        #expect(DeviceWipe.wipe(database: store.database, databaseURL: url, keyProvider: keys, tokens: tokens, evidence: evidence).isEmpty)
        #expect(!FileManager.default.fileExists(atPath: url.path))
        #expect(!FileManager.default.fileExists(atPath: url.path + "-wal"))
        #expect(try secrets.data(for: DatabaseKeyProvider.defaultAccount) == nil)
        #expect(try tokens.load() == nil)
        #expect(!FileManager.default.fileExists(atPath: evidence.directory.path))
        // The device stays the same device (so it stays revoked).
        #expect(try DeviceIdentity.loadOrCreate(store: secrets) == deviceID)
        // A fresh store opens empty with a new key.
        let reopened = try LocalStore.open(at: url, keyProvider: keys)
        #expect(try reopened.outbox.statusCounts(tenantID: UUID()).values.reduce(0, +) == 0)
    }
}
