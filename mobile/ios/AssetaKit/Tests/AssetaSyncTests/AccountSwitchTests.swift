import AssetaCapture
import AssetaModel
import AssetaStore
@testable import AssetaSync
import Foundation
import Testing

/// Several users on one phone: field data synced by one user is never shown to, bootstrapped over
/// by, or pushed under the token of the next. Unsynced work is held for its owner (not deleted)
/// and sent when that owner signs in again.
struct AccountSwitchTests {
    let userA = AccountIdentity(subject: "7f1e0c2a-aaaa-4aaa-8aaa-000000000001", label: "owner@example.com")
    let userB = AccountIdentity(subject: "7f1e0c2a-bbbb-4bbb-8bbb-000000000002", label: "supervisor@example.com")
    let otherJob = UUID(uuidString: "dddddddd-0000-4000-8000-000000000009")!

    private func paths(_ h: SyncHarness, after count: Int) -> [String] {
        h.syncRequests().dropFirst(count).map { "\($0.httpMethod!) \($0.url!.path)" }
    }

    private func pushTokens(_ h: SyncHarness) -> [String?] {
        h.syncRequests().filter { $0.url!.path == "/api/v1/sync/push" }.map { $0.value(forHTTPHeaderField: "Authorization") }
    }

    private func photo(_ h: SyncHarness) throws -> StoredEvidence {
        try h.evidence.store(Data((0..<2500).map { UInt8($0 % 251) }), fileExtension: "jpg", contentType: "image/jpeg")
    }

    @Test func anotherUserGetsAFreshBootstrapWhileThePreviousUsersWorkIsHeldUntilTheySignInAgain() async throws {
        let h = try SyncHarness()
        let tenant = SyncFixtures.tenant.lowercased
        // User A bootstraps, then records an opening reading with its photo that is not synced yet.
        #expect(try await h.engine(account: userA, token: "tkn-A").sync().outcome == .synced)
        #expect(try h.store.syncState.value("cursor", tenant: tenant) == "100")
        let capture = try h.recorder(userA).recordCapture(
            job: SyncFixtures.jobDTO, kind: .opening, mode: .automatic, reading: "1234.5",
            ocr: MeterOCRResult(value: "1234.5", confidence: 0.92, rawText: "1234.5", engine: "test", note: ""),
            photo: try photo(h), gps: .fix(latitude: -15.4, longitude: 28.3, accuracyM: 8, capturedAt: h.clock.wallNow),
            capturedAt: h.clock.wallNow, snapshot: SyncFixtures.meterSnapshot)
        #expect(capture.ownerSubject == userA.subject)
        #expect(capture.ownerLabel == userA.label)
        #expect(try h.store.attachments.attachments(tenantID: SyncFixtures.tenant, statuses: [.pending]).map(\.ownerSubject)
            == [userA.subject])

        // User B signs in on the same phone: opening the field resets A's synced data; A's work is held.
        #expect(try h.store.syncState.claim(tenantID: SyncFixtures.tenant, owner: userB.subject))
        #expect(try h.store.syncState.value("cursor", tenant: tenant) == nil)
        #expect(try h.store.syncState.value("device_registered", tenant: tenant) == nil)
        #expect(try h.store.syncState.value("offline_grant_until", tenant: tenant) == nil)
        let viewB = h.directory(userB)
        #expect(try viewB.jobs().isEmpty)
        #expect(try viewB.meterSnapshots().isEmpty)
        let overviewB = try viewB.overview()
        #expect(overviewB.unsyncedCount == 0)
        #expect(overviewB.items.isEmpty)
        #expect(overviewB.pendingUploads == 0)
        #expect(overviewB.heldAccounts == [HeldAccount(subject: userA.subject, label: userA.label, count: 1)])
        #expect(try h.recorder(userB).progress(jobID: SyncFixtures.jobID, serverStatus: .approved).openingCaptureOp == nil)

        // B's first sync is a fresh bootstrap of B's own jobs (never `changes` from A's cursor); A's
        // photo and operation are neither uploaded nor pushed under B's token.
        var job = SyncFixtures.job()
        job["id"] = otherJob.lowercased
        job["job_number"] = "J-2002"
        h.server.mutate { $0.jobs = [job] }
        let before = h.syncRequests().count
        #expect(try await h.engine(account: userB, token: "tkn-B").sync().outcome == .synced)
        let bFirst = paths(h, after: before)
        #expect(bFirst.prefix(2) == ["POST /api/v1/sync/devices", "GET /api/v1/sync/bootstrap"])
        #expect(!bFirst.contains("POST /api/v1/sync/push"))
        #expect(!bFirst.contains { $0.contains("/sync/blobs") })
        #expect(try viewB.jobs().map(\.job.jobNumber) == ["J-2002"])
        #expect(try h.status(capture.id) == .pending)
        #expect(h.server.read { $0.stored.isEmpty })

        // B's own work goes under B's token; A's stays held.
        let handover = try h.recorder(userB).recordCashHandover(amountText: "100", currency: "TZS", reference: nil,
                                                                 note: nil, handedAt: h.clock.wallNow)
        #expect(try await h.engine(account: userB, token: "tkn-B").sync(force: true).outcome == .synced)
        #expect(try h.status(handover.id) == .acked)
        #expect(try h.status(capture.id) == .pending)
        #expect(pushTokens(h) == ["Bearer tkn-B"])

        // A signs back in: a fresh bootstrap of A's data, and A's held work is sent under A's token.
        h.server.mutate { $0.jobs = [SyncFixtures.job()] }
        #expect(try h.store.syncState.claim(tenantID: SyncFixtures.tenant, owner: userA.subject))
        let beforeA = h.syncRequests().count
        let report = try await h.engine(account: userA, token: "tkn-A").sync(force: true)
        #expect(report.outcome == .synced)
        #expect(report.uploaded == 1)
        #expect(paths(h, after: beforeA).contains("GET /api/v1/sync/bootstrap"))
        #expect(try h.status(capture.id) == .acked)
        #expect(pushTokens(h).last == "Bearer tkn-A")
        #expect(try h.directory(userA).overview().heldAccounts.isEmpty) // B's only operation is synced
        #expect(try h.directory(userA).jobs().map(\.job.jobNumber) == ["J-1001"])
    }

    @Test func theSameUserSigningInAgainKeepsCursorAndCachedData() async throws {
        let h = try SyncHarness()
        let tenant = SyncFixtures.tenant.lowercased
        #expect(try await h.engine(account: userA, token: "tkn-A").sync().outcome == .synced)
        let handover = try h.recorder(userA).recordCashHandover(amountText: "100", currency: "TZS", reference: nil,
                                                                 note: nil, handedAt: h.clock.wallNow)
        // Sign out and back in as the same user: nothing is reset, the work is still theirs.
        #expect(try !h.store.syncState.claim(tenantID: SyncFixtures.tenant, owner: userA.subject))
        #expect(try h.store.syncState.value("cursor", tenant: tenant) == "100")
        #expect(try h.directory(userA).jobs().map(\.job.jobNumber) == ["J-1001"])
        #expect(try h.directory(userA).overview().unsyncedCount == 1)
        let before = h.syncRequests().count
        #expect(try await h.engine(account: userA, token: "tkn-A").sync(force: true).outcome == .synced)
        #expect(!paths(h, after: before).contains("GET /api/v1/sync/bootstrap"))
        #expect(paths(h, after: before).contains("GET /api/v1/sync/changes"))
        #expect(try h.status(handover.id) == .acked)
    }

    @Test func aRunningWorkLogEntryIsOnlyTheUsersWhoStartedIt() throws {
        let h = try SyncHarness()
        let job = SyncFixtures.jobDTO
        let entry = try h.recorder(userA).startEntry(job: job, type: .work, startedAt: h.clock.wallNow, note: nil)
        #expect(try h.recorder(userA).runningEntry(jobID: job.id) == entry)
        // B on the same (shared) job neither sees nor stops A's running entry; a claim keeps it for A.
        try h.store.syncState.claim(tenantID: SyncFixtures.tenant, owner: userB.subject)
        #expect(try h.recorder(userB).runningEntry(jobID: job.id) == nil)
        #expect(throws: FieldRecorderError.self) { try h.recorder(userB).stopEntry(job: job) }
        let stopped = try h.recorder(userA).stopEntry(job: job)
        #expect(stopped.ownerSubject == userA.subject)
    }
}
