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
        let op = try store.outbox.enqueue(NewClientOperation(tenantID: tenant, opType: "EXPENSE", entityType: "expense",
                                                             entityID: UUID(), payloadJSON: #"{"amount":"1"}"#, dependsOn: dependsOn))
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
        if serverState { result["server_state"] = .object(["pending_report_number": .string("MR-2026-00009")]) }
        if status == .acked || (status == .duplicate && code == nil) { result["entity"] = .object(["version": .number(4)]) }
        return OperationResultDTO(id: id, status: status, result: .object(result), error: error)
    }

    @Test(arguments: [
        (OperationOutcome.acked, nil as String?, false, ClientOperationStatus.acked),
        (.duplicate, nil, false, .acked),
        (.duplicate, "SUBSCRIPTION_READ_ONLY", false, .quarantined),
        (.duplicate, "REPORT_PENDING", true, .conflict),
        (.duplicate, "CAPTURE_ID_CONFLICT", false, .conflict),
        (.duplicate, "VALIDATION_FAILED", false, .failed),
        (.deferred, "DEPENDENCY_PENDING", false, .pending),
        (.conflict, "HOURS_NOT_AVAILABLE", true, .conflict),
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
        let file = try store.attachments.add(NewLocalAttachment(tenantID: tenant, purpose: "METER_PHOTO", fileName: "s.png",
                                                                sha256: String(repeating: "a", count: 64), sizeBytes: 10,
                                                                contentType: "image/png"))
        let child = try store.outbox.enqueue(NewClientOperation(
            tenantID: tenant, opType: "C", entityType: "c", entityID: UUID(), payloadJSON: #"{"kind":"DAILY"}"#,
            dependsOn: [parentA.id, parentB.id], attachments: [(file.id, .photo)], createdAtDevice: now.addingTimeInterval(2)))
        #expect(child.dependencies.count == 2)
        func ready() throws -> [UUID] { try store.outbox.readyToSend(tenantID: tenant, now: now, limit: 10).map(\.id) }
        #expect(try ready() == [parentA.id, parentB.id])
        for parent in [parentA, parentB] {
            try store.outbox.markSent(id: parent.id)
            try store.outbox.markAcked(id: parent.id, serverRevision: 1)
        }
        #expect(try ready().isEmpty) // dependencies ACKED but the photo is not uploaded yet
        let serverID = UUID()
        try store.attachments.markComplete(id: file.id, attachmentID: serverID)
        #expect(try ready() == [child.id])
        let payload = try JSONValue.parse(try #require(try store.outbox.operation(id: child.id)).payloadJSON)
        #expect(payload["photo_attachment_id"]?.stringValue == serverID.lowercased)
    }

    @Test func enqueueRefusesUnknownAttachment() {
        #expect(throws: OutboxError.self) {
            try store.outbox.enqueue(NewClientOperation(tenantID: tenant, opType: "C", entityType: "c", entityID: UUID(),
                                                        payloadJSON: "{}", attachments: [(UUID(), .photo)]))
        }
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
