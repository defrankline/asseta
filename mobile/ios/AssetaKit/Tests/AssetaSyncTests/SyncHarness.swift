import AssetaCapture
import AssetaModel
import AssetaNetwork
import AssetaSecurity
import AssetaStore
@testable import AssetaSync
import AssetaTestSupport
import Foundation

/// Controllable time for engine tests.
final class TestClock: ClockSource, @unchecked Sendable {
    private let lock = NSLock()
    private var wall: Date
    private var mono: UInt64 = 5_000_000_000
    private var boot = "boot-1"

    init(_ start: Date) { wall = start }

    var wallNow: Date { lock.withLock { wall } }
    var monotonicNanos: UInt64 { lock.withLock { mono } }
    var bootSessionID: String? { lock.withLock { boot } }

    /// Real time passing: wall and monotonic clocks advance together.
    func advance(_ seconds: TimeInterval) {
        lock.withLock { wall = wall.addingTimeInterval(seconds); mono += UInt64(seconds * 1_000_000_000) }
    }

    /// The user changes the wall clock; monotonic time is unaffected.
    func setWall(_ date: Date) { lock.withLock { wall = date } }

    func reboot() { lock.withLock { mono = 1_000_000_000; boot = "boot-\(UUID().uuidString)" } }
}

enum SyncFixtures {
    static let tenant = UUID(uuidString: "11111111-1111-4111-8111-111111111111")!
    static let jobID = UUID(uuidString: "aaaaaaaa-0000-4000-8000-000000000001")!
    static let machineID = UUID(uuidString: "bbbbbbbb-0000-4000-8000-000000000002")!
    static let versionID = UUID(uuidString: "cccccccc-0000-4000-8000-000000000003")!

    static func job(status: String = "APPROVED", version: Int = 1) -> [String: Any] {
        ["id": jobID.uuidString.lowercased(), "contract_id": UUID().uuidString.lowercased(), "job_number": "J-1001",
         "machine_id": machineID.uuidString.lowercased(), "job_site_id": NSNull(), "supervisor_id": NSNull(),
         "status": status, "planned_start": "2026-10-20T06:00:00.000Z", "planned_end": NSNull(), "currency": "ZMW",
         "hourly_rate": "100.00", "minimum_hours": "0", "standby_treatment": "EXCLUDED", "standby_rate": NSNull(),
         "mobilization_fee": "0", "discount_percent": "0", "tax_rate_percent": "0", "rate_source": "CONTRACT",
         "approved_at": NSNull(), "started_at": NSNull(), "completed_at": NSNull(), "version": version]
    }

    static func machine() -> [String: Any] {
        ["id": machineID.uuidString.lowercased(), "asset_code": "EX-07", "name": "Excavator 7", "meter_decimal_places": 1,
         "version": 2]
    }

    static func meterValues(opening: String = "AUTOMATIC", closing: String = "MANUAL") -> [String: Any] {
        ["opening_mode": opening, "closing_mode": closing, "manual_photo_required": true, "min_ocr_confidence": 0.85,
         "max_recapture_attempts": 2, "manual_correction_requires_review": true, "gps_enforcement": "SOFT",
         "gps_max_accuracy_m": 50, "gps_max_age_seconds": 120, "tracker_comparison_window_seconds": 600,
         "tracker_distance_tolerance_m": 200, "max_hours_per_elapsed_hour": "1.05", "continuity_tolerance_hours": "0.5",
         "telemetry_engine_hours_tolerance": "0.5"]
    }

    static func snapshot(scope: String, validUntil: Date, opening: String = "AUTOMATIC") -> [String: Any] {
        ["policy_type": "METER_CAPTURE", "scope_key": scope, "version_ids": [versionID.uuidString.lowercased()],
         "version_stamp": "v1", "values": meterValues(opening: opening), "valid_until": AssetaJSON.formatInstant(validUntil)]
    }

    static var jobDTO: JobDTO {
        try! AssetaJSON.decoder().decode(JobDTO.self, from: try! JSONSerialization.data(withJSONObject: job()))
    }

    static let policy = MeterCapturePolicy(openingMode: .automatic, closingMode: .manual, manualPhotoRequired: true,
                                           minOCRConfidence: 0.85, maxRecaptureAttempts: 2)
    static var meterSnapshot: MeterPolicySnapshot {
        MeterPolicySnapshot(scopeKey: "tenant", versionIDs: [versionID], versionStamp: "v1", policy: policy,
                            validUntil: Date(timeIntervalSince1970: 1_792_100_000))
    }
}

func temporaryDirectory() throws -> URL {
    let url = FileManager.default.temporaryDirectory.appendingPathComponent("asseta-sync-\(UUID().uuidString)")
    try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
    return url
}

/// A complete client wired to a ``FakeSyncServer`` through ``MockURLProtocol``.
struct SyncHarness {
    let server = FakeSyncServer()
    let clock: TestClock
    let directory: URL
    let keys: DatabaseKeyProvider
    let store: LocalStore
    let evidence: EvidenceStore
    let deviceID = "6b1f6f43-6d1e-4d86-9a43-2f1d2b0d3f10"
    let api: SyncAPI
    let recorder: FieldRecorder

    init(batchSize: Int = 25) throws {
        clock = TestClock(server.serverTime)
        directory = try temporaryDirectory()
        keys = DatabaseKeyProvider(store: InMemorySecretStore())
        store = try LocalStore.open(at: directory.appendingPathComponent("db.sqlite"), keyProvider: keys)
        evidence = EvidenceStore(directory: directory.appendingPathComponent("evidence"))
        let server = self.server
        let session = MockURLProtocol.session { try server.handle($0) }
        let client = APIClient(baseURL: URL(string: "https://api.test")!, transport: URLSessionTransport(session: session),
                               tokens: StaticTokenProvider(token: "tkn"), tenantID: SyncFixtures.tenant)
        api = SyncAPI(client: client, deviceID: deviceID)
        recorder = FieldRecorder(store: store, tenantID: SyncFixtures.tenant, deviceID: deviceID)
        server.mutate {
            $0.jobs = [SyncFixtures.job()]
            $0.machines = [SyncFixtures.machine()]
            $0.snapshots = [SyncFixtures.snapshot(scope: "tenant", validUntil: $0.serverTime.addingTimeInterval(86400))]
        }
        self.batchSize = batchSize
    }

    let batchSize: Int

    func engine() -> SyncEngine {
        // Deterministic jitter (0.5) keeps backoff assertions exact.
        SyncEngine(store: store, evidence: evidence, api: api, tenantID: SyncFixtures.tenant,
                   configuration: SyncConfiguration(appVersion: "0.1.0 (1)", batchSize: batchSize), clock: clock,
                   random: { 0 })
    }

    var directoryView: FieldDirectory { FieldDirectory(store: store, tenantID: SyncFixtures.tenant, clock: clock) }

    /// Opening capture with a photo (AUTOMATIC) followed by START.
    @discardableResult
    func recordOpeningAndStart(photoBytes: Int = 2500) throws -> (capture: ClientOperation, start: ClientOperation) {
        let bytes = Data((0..<photoBytes).map { UInt8($0 % 251) })
        let photo = try evidence.store(bytes, fileExtension: "jpg", contentType: "image/jpeg")
        let job = SyncFixtures.jobDTO
        let capture = try recorder.recordCapture(
            job: job, kind: .opening, mode: .automatic, reading: "1234.5",
            ocr: MeterOCRResult(value: "1234.5", confidence: 0.92, rawText: "1234.5", engine: "test", note: ""),
            photo: photo, gps: .fix(latitude: -15.4, longitude: 28.3, accuracyM: 8, capturedAt: clock.wallNow),
            capturedAt: clock.wallNow, snapshot: SyncFixtures.meterSnapshot)
        clock.advance(1)
        let start = try recorder.recordTransition(job: job, action: .start, at: clock.wallNow)
        return (capture, start)
    }

    func status(_ id: UUID) throws -> ClientOperationStatus? { try store.outbox.operation(id: id)?.status }

    func syncRequests() -> [URLRequest] {
        server.read { $0.requests }.filter { $0.url!.path.hasPrefix("/api/v1/sync") }
    }
}
