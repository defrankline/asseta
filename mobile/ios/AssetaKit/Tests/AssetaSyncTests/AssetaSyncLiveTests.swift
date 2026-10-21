import AssetaCapture
import AssetaModel
import AssetaNetwork
import AssetaSecurity
import AssetaStore
import AssetaSync
import AssetaTestSupport
import Foundation
import Testing

/// Fixture written by `backend/scripts/field_e2e_setup.py` (mode 600). Only its path is in the environment.
struct LiveFixture: Decodable {
    let apiBase: URL
    let tenantID: UUID
    let jobID: UUID
    let machineID: UUID
    let accessToken: String
    let tokenExpiresAt: String

    enum CodingKeys: String, CodingKey {
        case apiBase = "api_base", tenantID = "tenant_id", jobID = "job_id", machineID = "machine_id"
        case accessToken = "access_token", tokenExpiresAt = "token_expires_at"
    }

    static var path: String? { ProcessInfo.processInfo.environment["ASSETA_LIVE_E2E"].flatMap { $0.isEmpty ? nil : $0 } }

    static func load() throws -> LiveFixture {
        try JSONDecoder().decode(LiveFixture.self, from: Data(contentsOf: URL(fileURLWithPath: try #require(path))))
    }
}

/// Gate 4 live E2E: the real AssetaKit sync stack (SyncEngine, SyncAPI, URLSessionTransport, SQLCipher outbox and
/// store, evidence files, FieldRecorder) against the running backend + Keycloak. Skipped unless `ASSETA_LIVE_E2E`
/// names a fixture file (see scripts/field-e2e.sh); never runs in normal `swift test` or CI.
@Suite(.enabled(if: LiveFixture.path != nil, "set ASSETA_LIVE_E2E to a field_e2e_setup.py fixture file"))
struct AssetaSyncLiveTests {
    @Test func openingCaptureWithPhotoSyncsExactlyOnceAgainstTheLiveBackend() async throws {
        let fixture = try LiveFixture.load()
        let expiry = try #require(ISO8601DateFormatter.lenient(fixture.tokenExpiresAt))
        try #require(expiry.timeIntervalSinceNow > 30, "supervisor token expired: re-run field_e2e_setup.py")

        let directory = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let store = try LocalStore.open(at: directory.appendingPathComponent("db.sqlite"),
                                        keyProvider: DatabaseKeyProvider(store: InMemorySecretStore()))
        let evidence = EvidenceStore(directory: directory.appendingPathComponent("evidence"))
        let deviceID = try DeviceIdentity.loadOrCreate(store: InMemorySecretStore())
        let client = APIClient(baseURL: fixture.apiBase, transport: URLSessionTransport(),
                               tokens: StaticTokenProvider(token: fixture.accessToken), tenantID: fixture.tenantID)
        let api = SyncAPI(client: client, deviceID: deviceID)
        let engine = SyncEngine(store: store, evidence: evidence, api: api, tenantID: fixture.tenantID,
                                configuration: SyncConfiguration(appVersion: "live-e2e (ios)"))
        let fieldDirectory = FieldDirectory(store: store, tenantID: fixture.tenantID)
        let recorder = FieldRecorder(store: store, tenantID: fixture.tenantID, deviceID: deviceID)

        // 1. First sync: registers the device and bootstraps the supervisor's jobs + capture policy.
        let first = try await engine.sync(force: true)
        #expect(first.outcome == .synced, "first sync: \(first.outcome)")
        let job = try #require(fieldDirectory.job(id: fixture.jobID), "assigned job missing from bootstrap")
        #expect(job.job.machineID == fixture.machineID)
        #expect(job.job.status == .approved)

        // 2. Opening capture exactly as the capture screen records it: policy-decided mode, photo, fresh GPS fix.
        guard case let .allowed(snapshot) = try fieldDirectory.captureGate(machineID: fixture.machineID) else {
            Issue.record("capture blocked by the synced policy gate")
            return
        }
        let requirements = CaptureRequirements(policy: snapshot.policy, kind: .opening, decimalPlaces: job.decimalPlaces)
        let ocr = requirements.requiredMode == .automatic
            ? MeterOCRResult(value: "1234.5", confidence: 0.99, rawText: "1234.5", engine: "live-e2e-fixture", note: "")
            : nil
        let now = Date()
        let gps = GpsPayload.fix(latitude: -6.8, longitude: 39.28, accuracyM: 8, capturedAt: now.addingTimeInterval(-2))
        let draft = CaptureDraft(mode: requirements.requiredMode, readingText: "1234.5", hasPhoto: true, ocr: ocr,
                                 photoAttempts: 1, gps: gps)
        #expect(CaptureValidator.issues(draft, requirements).isEmpty)
        let photo = try evidence.store(Self.jpeg(bytes: 300_000), fileExtension: "jpg", contentType: "image/jpeg")
        let captureID = UUID()
        let op = try recorder.recordCapture(
            job: job.job, kind: .opening, mode: requirements.requiredMode, reading: "1234.5", ocr: ocr, photo: photo,
            gps: gps, capturedAt: now, snapshot: snapshot, captureID: captureID)
        #expect(try store.outbox.operation(id: op.id)?.status == .pending)

        // 3. Sync: the photo uploads (resumable blob API) before the capture is pushed and ACKED.
        let second = try await engine.sync(force: true)
        #expect(second.outcome == .synced, "second sync: \(second.outcome)")
        #expect(second.uploaded == 1)
        let acked = try #require(try store.outbox.operation(id: op.id))
        #expect(acked.status == .acked, "operation \(acked.status) \(acked.errorCode ?? "") \(acked.lastError ?? "")")
        let files = try store.attachments.attachments(tenantID: fixture.tenantID, statuses: Set(LocalAttachmentStatus.allCases))
        #expect(files.count == 1)
        let serverAttachment = try #require(files.first?.attachmentID)
        #expect(files.first?.status == .complete)
        let payload = try JSONValue.parse(acked.payloadJSON)
        #expect(payload["photo_attachment_id"]?.stringValue == serverAttachment.lowercased)

        // 4. Replay of the same client operation id (lost response): DUPLICATE, no second effect.
        let replay = try await api.push(PushIn(deviceNow: Date(), operations: [
            OperationIn(id: acked.id, opType: acked.opType, createdAtDevice: acked.createdAtDevice,
                        dependsOn: acked.dependencies, payload: payload),
        ]))
        #expect(replay.results.map(\.status) == [.duplicate])
        #expect(replay.results.first?.id == acked.id)
        let third = try await engine.sync(force: true) // nothing left to send
        #expect(third.outcome == .synced)
        #expect(third.pushed.isEmpty)

        // 5. Server side: exactly one opening reading, with the uploaded photo.
        let captures = try await client.send(
            APIRequest<[JSONValue]>.get("/api/v1/tenant/jobs/\(fixture.jobID.lowercased)/meter-captures"))
        #expect(captures.count == 1)
        let row = try #require(captures.first)
        #expect(row["id"]?.stringValue == captureID.lowercased)
        #expect(row["kind"]?.stringValue == "OPENING")
        #expect(row["reading"]?.stringValue.flatMap { Decimal(string: $0) } == Decimal(string: "1234.5"))
        #expect(row["capture_mode"]?.stringValue == requirements.requiredMode.rawValue)
        #expect(row["photo_attachment_id"]?.stringValue == serverAttachment.lowercased)
        #expect(row["gps_status"]?.stringValue == "FIX")
    }

    /// JPEG-framed random bytes (unique per run so the server's content dedupe does not short-circuit the upload).
    static func jpeg(bytes: Int) -> Data {
        var data = Data([0xFF, 0xD8, 0xFF, 0xE0])
        data.append(contentsOf: (0..<bytes).map { _ in UInt8.random(in: 0...255) })
        data.append(contentsOf: [0xFF, 0xD9])
        return data
    }
}

private extension ISO8601DateFormatter {
    static func lenient(_ text: String) -> Date? {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = formatter.date(from: text) { return date }
        formatter.formatOptions = [.withInternetDateTime]
        return formatter.date(from: text)
    }
}
