import AssetaCapture
import AssetaModel
import AssetaSecurity
import AssetaStore
@testable import AssetaSync
import Foundation
import Testing

/// Sync engine scenarios against a fake server behind a mock `URLProtocol`.
struct SyncEngineTests {
    @Test func firstSyncRegistersBootstrapsAndPersistsCursor() async throws {
        let h = try SyncHarness()
        let report = try await h.engine().sync()
        #expect(report.outcome == .synced)
        let requests = h.syncRequests()
        #expect(requests.map { "\($0.httpMethod!) \($0.url!.path)" }.prefix(3) == [
            "POST /api/v1/sync/devices", "GET /api/v1/sync/bootstrap", "GET /api/v1/sync/changes",
        ])
        #expect(requests.allSatisfy { $0.value(forHTTPHeaderField: "X-Device-Id") == h.deviceID })
        #expect(requests.last?.url?.query == "cursor=100")
        let registration = try #require(h.server.read { $0.registrations.first })
        #expect(registration["platform"] as? String == "IOS")
        #expect(registration["device_id"] as? String == h.deviceID)
        #expect(registration["app_version"] as? String == "0.1.0 (1)")
        #expect(try h.store.syncState.value("cursor", tenant: SyncFixtures.tenant.lowercased) == "100")
        #expect(try h.directoryView.jobs().map(\.job.jobNumber) == ["J-1001"])
        #expect(try h.directoryView.jobs().first?.machine?.assetCode == "EX-07")
        #expect(try h.directoryView.meterSnapshots().map(\.scopeKey) == ["tenant"])
        // Second cycle does not register or bootstrap again.
        _ = try await h.engine().sync()
        #expect(h.server.read { $0.registrations.count } == 1)
    }

    @Test func offlineQueuesThenReconnectUploadsPhotoAndPushesInDependencyOrder() async throws {
        let h = try SyncHarness()
        let engine = h.engine()
        _ = try await engine.sync()
        let (capture, start) = try h.recordOpeningAndStart()
        h.server.mutate { $0.offline = true }
        let offline = try await engine.sync(force: true)
        guard case .offline = offline.outcome else { Issue.record("expected offline, got \(offline.outcome)"); return }
        #expect(try h.status(capture.id) == .pending)
        #expect(try h.status(start.id) == .pending)
        // Backoff with jitter: first failure waits base(2 s) × 0.5 → the next unforced cycle is skipped.
        let skipped = try await engine.sync()
        #expect(skipped.outcome == .backingOff(until: h.clock.wallNow.addingTimeInterval(1)))

        h.server.mutate { $0.offline = false }
        let online = try await engine.sync(force: true)
        #expect(online.outcome == .synced)
        #expect(online.uploaded == 1)
        #expect(try h.status(capture.id) == .acked)
        #expect(try h.status(start.id) == .acked)
        #expect(h.server.read { $0.applyOrder } == [capture.id, start.id])
        // START waited for the capture's ACK: separate batches, never ahead of its dependency.
        #expect(h.server.read { $0.pushedBatchSizes }.suffix(2) == [1, 1])
        let payload = try JSONValue.parse(try #require(try h.store.outbox.operation(id: capture.id)).payloadJSON)
        let attachmentID = try #require(payload["photo_attachment_id"]?.stringValue)
        #expect(h.server.read { $0.blobs.values.contains { $0.attachmentID?.uuidString.lowercased() == attachmentID } })
        #expect(payload["policy_version_ids"] == .array([.string(SyncFixtures.versionID.lowercased)]))
    }

    @Test func lostResponseIsRetriedAndAnsweredDuplicateWithOneEffect() async throws {
        let h = try SyncHarness()
        let engine = h.engine()
        _ = try await engine.sync()
        let job = SyncFixtures.jobDTO
        let capture = try h.recorder.recordCapture(
            job: job, kind: .opening, mode: .manual, reading: "10.0", ocr: nil, photo: nil, gps: .failed(.timeout),
            capturedAt: h.clock.wallNow, snapshot: SyncFixtures.meterSnapshot)
        h.server.mutate { $0.dropNextPushResponse = true }
        _ = try await engine.sync(force: true)
        #expect(try h.status(capture.id) == .pending) // applied server-side, but never marked synced without ACK
        _ = try await engine.sync(force: true)
        let op = try #require(try h.store.outbox.operation(id: capture.id))
        #expect(op.status == .acked)
        #expect(op.serverResultJSON?.contains("DUPLICATE") == true)
        #expect(h.server.read { $0.applyOrder } == [capture.id])
        #expect(op.attemptCount == 2)
    }

    @Test func deferredStaysPendingThenAcks() async throws {
        let h = try SyncHarness()
        let engine = h.engine()
        _ = try await engine.sync()
        let (capture, _) = try h.recordOpeningAndStart()
        h.server.mutate { $0.script[capture.id] = ["DEFERRED"] }
        _ = try await engine.sync(force: true)
        let deferred = try #require(try h.store.outbox.operation(id: capture.id))
        #expect(deferred.status == .pending)
        #expect(deferred.nextAttemptAt == h.clock.wallNow.addingTimeInterval(PushOutcomeApplier.deferDelay))
        h.clock.advance(11)
        _ = try await engine.sync(force: true)
        #expect(try h.status(capture.id) == .acked)
    }

    @Test func conflictIsSurfacedWithServerStateAndBlocksDependents() async throws {
        let h = try SyncHarness()
        let engine = h.engine()
        _ = try await engine.sync()
        let (_, start) = try h.recordOpeningAndStart()
        let activity = try h.recorder.recordActivity(job: SyncFixtures.jobDTO, type: .work, startedAt: h.clock.wallNow,
                                                     endedAt: nil, billable: true, note: "dig")
        h.server.mutate { $0.script[start.id] = ["CONFLICT"] }
        _ = try await engine.sync(force: true)
        let op = try #require(try h.store.outbox.operation(id: start.id))
        #expect(op.status == .conflict)
        #expect(op.errorCode == "INVALID_JOB_TRANSITION")
        #expect(try h.status(activity.id) == .pending) // not sent: its parent was never ACKED
        let overview = try h.directoryView.overview()
        let item = try #require(overview.items.first { $0.id == start.id })
        #expect(item.serverState?.contains("CANCELLED") == true)
        #expect(overview.items.first { $0.id == activity.id }?.waitingFor?.contains("Blocked") == true)
        // No auto-overwrite: re-syncing leaves the conflict as it is.
        _ = try await engine.sync(force: true)
        #expect(try h.status(start.id) == .conflict)
    }

    @Test func rejectedBecomesFailedWithVisibleCode() async throws {
        let h = try SyncHarness()
        let engine = h.engine()
        _ = try await engine.sync()
        let (capture, _) = try h.recordOpeningAndStart()
        h.server.mutate { $0.script[capture.id] = ["REJECTED"] }
        _ = try await engine.sync(force: true)
        let op = try #require(try h.store.outbox.operation(id: capture.id))
        #expect(op.status == .failed)
        #expect(op.errorCode == "VALIDATION_FAILED")
        #expect(try h.store.outbox.operation(id: capture.id)?.payloadJSON.contains("1234.5") == true) // evidence kept
    }

    @Test func quarantinedWhileReadOnlyThenAckedAfterReactivation() async throws {
        let h = try SyncHarness()
        let engine = h.engine()
        _ = try await engine.sync()
        let (capture, _) = try h.recordOpeningAndStart()
        h.server.mutate { $0.readOnly = true }
        _ = try await engine.sync(force: true)
        #expect(try h.status(capture.id) == .quarantined)
        #expect(try h.directoryView.overview().counts[.quarantined] == 1)
        h.clock.advance(PushOutcomeApplier.quarantineRetry + 1)
        _ = try await engine.sync(force: true) // still read-only: DUPLICATE of the held op stays held
        #expect(try h.status(capture.id) == .quarantined)
        h.server.mutate { $0.readOnly = false }
        h.clock.advance(PushOutcomeApplier.quarantineRetry + 1)
        _ = try await engine.sync(force: true)
        #expect(try h.status(capture.id) == .acked)
        h.clock.advance(PushOutcomeApplier.deferDelay + 1)
        _ = try await engine.sync(force: true)
        #expect(try h.store.outbox.statusCounts(tenantID: SyncFixtures.tenant)[.acked] == 2)
    }

    @Test func deviceRevokedTriggersFullLocalWipe() async throws {
        let h = try SyncHarness()
        _ = try await h.engine().sync()
        try h.recordOpeningAndStart() // unsynced evidence on the phone
        h.server.mutate { $0.revoked = true }
        do {
            _ = try await h.engine().sync(force: true)
            Issue.record("expected DEVICE_REVOKED")
        } catch let SyncError.deviceRevoked(message) {
            #expect(message.contains("revoked"))
            let tokens = TokenStore(store: InMemorySecretStore())
            let errors = DeviceWipe.wipe(database: h.store.database, databaseURL: h.directory.appendingPathComponent("db.sqlite"),
                                         keyProvider: h.keys, tokens: tokens, evidence: h.evidence)
            #expect(errors.isEmpty)
            #expect(!FileManager.default.fileExists(atPath: h.directory.appendingPathComponent("db.sqlite").path))
            #expect(!FileManager.default.fileExists(atPath: h.evidence.directory.path))
            #expect(throws: (any Error).self) { try h.store.outbox.statusCounts(tenantID: SyncFixtures.tenant) } // closed
        }
        // Registration of a revoked device is refused the same way (no way around the wipe).
        let fresh = try SyncHarness()
        fresh.server.mutate { $0.revoked = true }
        await #expect(throws: SyncError.self) { _ = try await fresh.engine().sync() }
    }

    @Test func serverErrorBacksOffExponentially() async throws {
        let h = try SyncHarness()
        let engine = h.engine()
        h.server.mutate { $0.unavailable503 = 3 }
        for expected in [1.0, 2.0, 4.0] { // base 2 s · 2^(n-1) · jitter 0.5
            let report = try await engine.sync(force: true)
            guard case .serverUnavailable = report.outcome else { Issue.record("\(report.outcome)"); return }
            let next = try #require(try h.directoryView.overview().nextAttemptAt)
            #expect(abs(next.timeIntervalSince(h.clock.wallNow) - expected) < 0.01)
        }
        #expect(try await engine.sync(force: true).outcome == .synced)
        #expect(try h.directoryView.overview().consecutiveFailures == 0)
    }

    @Test func blobUploadResumesMissingChunksAfterInterruption() async throws {
        let h = try SyncHarness()
        let engine = h.engine()
        _ = try await engine.sync()
        let (capture, _) = try h.recordOpeningAndStart(photoBytes: 2500) // 3 chunks of 1000 bytes
        h.server.mutate { $0.failChunkPut = (index: 1, times: 1) }
        let first = try await engine.sync(force: true)
        guard case .offline = first.outcome else { Issue.record("\(first.outcome)"); return }
        let attachment = try #require(try h.store.attachments.attachments(tenantID: SyncFixtures.tenant, statuses: [.pending]).first)
        #expect(attachment.receivedChunks == [0])
        #expect(try h.status(capture.id) == .pending) // capture never sent without its attachment id
        #expect(h.server.read { $0.pushedBatchSizes }.isEmpty)
        _ = try await engine.sync(force: true)
        #expect(h.server.read { $0.chunkPuts.map(\.index) } == [0, 1, 2]) // chunk 0 not re-sent
        #expect(h.server.read { $0.sessionsStarted } == 1)
        #expect(try h.status(capture.id) == .acked)
    }

    @Test func checksumMismatchRestartsUpload() async throws {
        let h = try SyncHarness()
        let engine = h.engine()
        _ = try await engine.sync()
        let (capture, _) = try h.recordOpeningAndStart()
        h.server.mutate { $0.corruptNextComplete = true }
        let report = try await engine.sync(force: true)
        #expect(report.outcome == .synced)
        #expect(h.server.read { $0.sessionsStarted } == 2)
        #expect(try h.status(capture.id) == .acked)
    }

    @Test func alreadyKnownContentCompletesWithoutChunks() async throws {
        let h = try SyncHarness()
        let engine = h.engine()
        _ = try await engine.sync()
        let bytes = Data((0..<2500).map { UInt8($0 % 251) })
        let known = UUID()
        h.server.mutate { $0.knownContent[EvidenceStore.sha256Hex(bytes)] = known }
        let (capture, _) = try h.recordOpeningAndStart()
        _ = try await engine.sync(force: true)
        #expect(h.server.read { $0.chunkPuts.isEmpty })
        #expect(try h.store.outbox.operation(id: capture.id)?.payloadJSON.contains(known.lowercased) == true)
    }

    @Test func operationsSentBeforeTerminationAreResent() async throws {
        let h = try SyncHarness()
        _ = try await h.engine().sync()
        let capture = try h.recorder.recordCapture(
            job: SyncFixtures.jobDTO, kind: .opening, mode: .manual, reading: "10.0", ocr: nil, photo: nil,
            gps: .failed(.permissionDenied), capturedAt: h.clock.wallNow, snapshot: SyncFixtures.meterSnapshot)
        try h.store.outbox.markSent(id: capture.id) // app killed while the push was in flight
        _ = try await h.engine().sync(force: true)   // fresh engine = relaunch
        #expect(try h.status(capture.id) == .acked)
    }

    @Test func pushesAreBoundedBatches() async throws {
        let h = try SyncHarness(batchSize: 4)
        let engine = h.engine()
        _ = try await engine.sync()
        let (_, _) = try h.recordOpeningAndStart()
        h.clock.advance(1)
        _ = try await engine.sync(force: true)
        for i in 0..<9 {
            try h.recorder.recordActivity(job: SyncFixtures.jobDTO, type: .note, startedAt: h.clock.wallNow, endedAt: nil,
                                          billable: nil, note: "n\(i)")
        }
        _ = try await engine.sync(force: true)
        #expect(h.server.read { $0.pushedBatchSizes }.suffix(3) == [4, 4, 1])
        let body = try #require(h.server.read { $0.requests }.last { $0.url!.path == "/api/v1/sync/push" }?.httpBody)
        let json = try #require(try JSONSerialization.jsonObject(with: body) as? [String: Any])
        #expect(json["device_now"] is String)
    }

    @Test func newerRevisionWinsForServerOwnedData() async throws {
        let h = try SyncHarness()
        let engine = h.engine()
        _ = try await engine.sync()
        h.server.mutate { $0.jobs = [SyncFixtures.job(status: "IN_PROGRESS", version: 2)]; $0.cursor = 120 }
        _ = try await engine.sync(force: true)
        #expect(try h.directoryView.jobs().first?.job.status == .inProgress)
        // A replayed older page (lookback overlap) must not roll the job back.
        let stale = StoredEntity(entityType: "job", id: SyncFixtures.jobID, revision: 90, version: 1,
                                 json: String(decoding: try JSONSerialization.data(withJSONObject: SyncFixtures.job()), as: UTF8.self))
        #expect(try h.store.syncState.upsert([stale], tenantID: SyncFixtures.tenant) == 0)
        #expect(try h.directoryView.jobs().first?.job.version == 2)
    }
}
