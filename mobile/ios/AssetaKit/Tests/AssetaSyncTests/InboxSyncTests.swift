import AssetaCapture
import AssetaModel
import AssetaStore
@testable import AssetaSync
import Foundation
import Testing

/// Supervisor inbox: server copies applied from bootstrap/changes, merged with this phone's records,
/// kept per user (same scenarios as Android `InboxSyncTest`).
struct InboxSyncTests {
    let staff = UUID()

    private func handoverRow(_ id: UUID, clientID: UUID?, status: String, revision: Int, note: String? = nil) -> [String: Any] {
        ["id": id.uuidString.lowercased(), "client_id": clientID?.uuidString.lowercased() ?? NSNull(),
         "staff_member_id": staff.uuidString.lowercased(), "amount": "100000.0000", "currency": "ZMW", "status": status,
         "decision_note": note ?? NSNull(), "reference": "R-1", "note": NSNull(), "handed_at": "2026-10-21T07:00:00Z",
         "recorded_at": "2026-10-21T07:01:00Z", "recorded_by": NSNull(), "verified_at": NSNull(), "verified_by": NSNull(),
         "source": "SYNC", "sync_revision": revision]
    }

    private func captureRow(_ id: UUID, revision: Int, finding: String?) -> [String: Any] {
        var findings: [[String: Any]] = []
        if let finding {
            findings.append(["id": UUID().uuidString.lowercased(), "exception_type": "METER_DECREASE", "severity": "HIGH",
                             "blocking": true, "status": finding, "machine_id": SyncFixtures.machineID.uuidString.lowercased(),
                             "job_id": SyncFixtures.jobID.uuidString.lowercased(), "meter_capture_id": id.uuidString.lowercased(),
                             "policy_version": NSNull(), "review_note": finding == "OPEN" ? NSNull() : "Meter was replaced",
                             "reviewed_at": NSNull(), "created_at": "2026-10-21T08:01:00Z", "evidence": [String: Any]()])
        }
        return ["id": id.uuidString.lowercased(), "job_id": SyncFixtures.jobID.uuidString.lowercased(),
                "machine_id": SyncFixtures.machineID.uuidString.lowercased(), "kind": "OPENING", "capture_mode": "AUTOMATIC",
                "reading": "1234.5", "state": "PROVISIONAL", "gps_status": "FIX", "latitude": -15.4, "longitude": 28.3,
                "accuracy_m": 8.0, "location_captured_at": "2026-10-21T08:00:00Z", "photo_attachment_id": NSNull(),
                "photo_sha256": NSNull(), "ocr_value": "1234.5", "ocr_confidence": 0.92, "manually_corrected": false,
                "policy_version": "v1", "supersedes_id": NSNull(), "tracker_comparison": NSNull(),
                "captured_at": "2026-10-21T08:00:00Z", "received_at": "2026-10-21T08:01:00Z", "sync_revision": revision,
                "review_status": finding == nil ? "NONE" : finding == "OPEN" ? "PENDING_REVIEW" : "REVIEWED", "findings": findings]
    }

    private func resetRow(_ id: UUID, status: String, revision: Int) -> [String: Any] {
        ["id": id.uuidString.lowercased(), "machine_id": SyncFixtures.machineID.uuidString.lowercased(), "old_reading": "9999.9",
         "new_reading": "0.0", "effective_at": "2026-10-21T08:00:00Z", "reason": "Meter replaced by the workshop",
         "status": status, "evidence_attachment_id": NSNull(), "requested_by": NSNull(), "decided_by": NSNull(),
         "decided_at": status == "PENDING" ? NSNull() : "2026-10-21T09:00:00Z", "created_at": "2026-10-21T08:00:00Z",
         "sync_revision": revision]
    }

    private func inbox(_ h: SyncHarness) throws -> InboxSnapshot {
        try InboxDirectory(store: h.store, tenantID: SyncFixtures.tenant).snapshot()
    }

    @Test func localRecordWaitsThenMergesWithTheServerRecordAndItsDecision() async throws {
        let h = try SyncHarness()
        _ = try await h.engine().sync(force: true)
        let clientID = UUID()
        let op = try h.recorder.recordCashHandover(amountText: "100000", currency: "ZMW", reference: "R-1", note: nil,
                                                   handedAt: h.clock.wallNow, clientID: clientID)
        #expect(try inbox(h).handovers.map(\.status) == [.waiting])

        _ = try await h.engine().sync(force: true)
        #expect(try h.status(op.id) == .acked)
        #expect(try inbox(h).handovers.map(\.status) == [.synced]) // acked, server copy not pulled yet

        let serverID = UUID()
        h.server.mutate { $0.inbox = ["my_cash_handovers": [handoverRow(serverID, clientID: clientID, status: "CLAIMED", revision: 20)]] }
        _ = try await h.engine().sync(force: true)
        var item = try #require(try inbox(h).handovers.first)
        #expect(try inbox(h).handovers.count == 1)
        #expect(item.id == serverID && item.status == .claimed && item.op?.id == op.id)

        h.server.mutate {
            $0.inbox = ["my_cash_handovers": [handoverRow(serverID, clientID: clientID, status: "REJECTED", revision: 21,
                                                          note: "Amount does not match")]]
        }
        _ = try await h.engine().sync(force: true)
        item = try #require(try inbox(h).handovers.first)
        #expect(item.status == .rejected && item.decisionNote == "Amount does not match")
        #expect(try inbox(h).attention.map(\.kind) == [.handover])

        // A replayed older revision never overwrites the newer decision.
        h.server.mutate { $0.inbox = ["my_cash_handovers": [handoverRow(serverID, clientID: clientID, status: "CLAIMED", revision: 20)]] }
        _ = try await h.engine().sync(force: true)
        #expect(try inbox(h).handovers.first?.status == .rejected)
    }

    @Test func capturesShowFindingsAndReviewAndMergeWithTheLocalCapture() async throws {
        let h = try SyncHarness()
        _ = try await h.engine().sync(force: true)
        let (capture, _) = try h.recordOpeningAndStart()
        _ = try await h.engine().sync(force: true)
        h.server.mutate { $0.inbox = ["my_meter_captures": [captureRow(capture.entityID, revision: 30, finding: "OPEN")]] }
        _ = try await h.engine().sync(force: true)
        var reading = try #require(try inbox(h).readings.first)
        #expect(try inbox(h).readings.count == 1)
        #expect(reading.status == .flagged && reading.op?.id == capture.id && reading.blockingFindings == 1)

        h.server.mutate { $0.inbox = ["my_meter_captures": [captureRow(capture.entityID, revision: 31, finding: "EXPLAINED")]] }
        _ = try await h.engine().sync(force: true)
        reading = try #require(try inbox(h).readings.first)
        #expect(reading.status == .reviewed)
        #expect(reading.findings.first?.reviewNote == "Meter was replaced")
        #expect(try inbox(h).jobReading(SyncFixtures.jobID, kind: "OPENING")?.reading == "1234.5")
    }

    @Test func serverWithoutTheCapabilityKeepsCurrentBehaviour() async throws {
        let h = try SyncHarness()
        h.server.mutate { $0.capabilities = nil }
        _ = try await h.engine().sync(force: true)
        #expect(try h.store.inbox.count(tenantID: SyncFixtures.tenant) == 0)
        #expect(h.recorder.meterResetUnavailable() != nil)
        let photo = try h.evidence.store(Data(repeating: 7, count: 50), fileExtension: "jpg", contentType: "image/jpeg")
        #expect(throws: FieldRecorderError.self) {
            try h.recorder.requestMeterReset(machineID: SyncFixtures.machineID, oldReading: "10", newReading: "0",
                                             reason: "Meter replaced by workshop", photo: photo, effectiveAt: h.clock.wallNow)
        }
    }

    @Test func meterResetRequestUploadsEvidenceAndMergesWithTheDecision() async throws {
        let h = try SyncHarness()
        _ = try await h.engine().sync(force: true)
        #expect(h.recorder.meterResetUnavailable() == nil)
        #expect(throws: FieldRecorderError.self) {
            try h.recorder.requestMeterReset(machineID: SyncFixtures.machineID, oldReading: "x", newReading: "0", reason: "short",
                                             photo: nil, effectiveAt: h.clock.wallNow)
        }
        let photo = try h.evidence.store(Data((0..<1500).map { UInt8($0 % 251) }), fileExtension: "jpg", contentType: "image/jpeg")
        let clientID = UUID()
        let op = try h.recorder.requestMeterReset(machineID: SyncFixtures.machineID, oldReading: "9999.9", newReading: "0",
                                                  reason: "Meter replaced by the workshop", photo: photo,
                                                  effectiveAt: h.clock.wallNow, clientID: clientID)
        #expect(throws: FieldRecorderError.self) {
            try h.recorder.requestMeterReset(machineID: SyncFixtures.machineID, oldReading: "9999.9", newReading: "0",
                                             reason: "Meter replaced by the workshop", photo: photo,
                                             effectiveAt: h.clock.wallNow, clientID: clientID)
        }
        #expect(try inbox(h).resets.map(\.status) == [.waiting])

        _ = try await h.engine().sync(force: true)
        #expect(try h.status(op.id) == .acked)
        let (serverID, payload) = try #require(h.server.read { $0.resets.first })
        #expect(payload["reason"] as? String == "Meter replaced by the workshop")
        #expect(payload["evidence_attachment_id"] == nil)

        // The server's reset (no client id) merges with the request by the acknowledged server id.
        h.server.mutate { $0.inbox = ["my_meter_resets": [resetRow(serverID, status: "PENDING", revision: 40)]] }
        _ = try await h.engine().sync(force: true)
        var item = try #require(try inbox(h).resets.first)
        #expect(try inbox(h).resets.count == 1)
        #expect(item.status == .pending && item.op?.id == op.id)
        h.server.mutate { $0.inbox = ["my_meter_resets": [resetRow(serverID, status: "APPROVED", revision: 41)]] }
        _ = try await h.engine().sync(force: true)
        item = try #require(try inbox(h).resets.first)
        #expect(item.status == .approved && item.decidedAt != nil)
    }

    @Test func anotherUserSignInClearsTheInboxAndCachedNotifications() async throws {
        let h = try SyncHarness()
        h.server.mutate { $0.inbox = ["my_cash_handovers": [handoverRow(UUID(), clientID: nil, status: "VERIFIED", revision: 5)]] }
        let a = AccountIdentity(subject: "user-a"), b = AccountIdentity(subject: "user-b")
        _ = try await h.engine(account: a, token: "a").sync(force: true)
        #expect(try h.store.inbox.count(tenantID: SyncFixtures.tenant) == 1)
        try h.store.syncState.setValue("{}", for: SyncKey.notifications, tenant: SyncFixtures.tenant.uuidString.lowercased())
        try h.store.syncState.claim(tenantID: SyncFixtures.tenant, owner: b.subject)
        #expect(try h.store.inbox.count(tenantID: SyncFixtures.tenant) == 0)
        #expect(try h.store.syncState.value(SyncKey.notifications, tenant: SyncFixtures.tenant.uuidString.lowercased()) == nil)
    }

    @Test func bootstrapStartsTheInboxAfreshAndOldFinishedRecordsArePruned() async throws {
        let h = try SyncHarness()
        func row(_ id: UUID, _ status: String, _ at: Date) -> InboxRecord {
            InboxRecord(kind: .expense, id: id, clientID: nil, jobID: nil, machineID: nil, status: status, occurredAt: at,
                        syncRevision: 1, json: "{}")
        }
        try h.store.inbox.upsert([row(UUID(), "APPROVED", Date(timeIntervalSince1970: 1))], tenantID: SyncFixtures.tenant)
        _ = try await h.engine().sync(force: true) // bootstrap with SUPERVISOR_INBOX_V1
        #expect(try h.store.inbox.count(tenantID: SyncFixtures.tenant) == 0)
        let old = h.clock.wallNow.addingTimeInterval(-40 * 86400)
        let open = UUID()
        try h.store.inbox.upsert([row(UUID(), "APPROVED", old), row(open, "PENDING_APPROVAL", old)], tenantID: SyncFixtures.tenant)
        h.server.mutate { $0.inbox = ["my_expenses": []] }
        _ = try await h.engine().sync(force: true)
        #expect(try h.store.inbox.records(tenantID: SyncFixtures.tenant).map(\.id) == [open])
    }
}
