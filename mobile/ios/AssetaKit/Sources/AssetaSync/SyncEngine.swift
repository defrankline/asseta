import AssetaCapture
import AssetaModel
import AssetaNetwork
import AssetaStore
import Foundation

public struct SyncConfiguration: Sendable, Equatable {
    public var appVersion: String
    /// Operations per push (bounded; halved automatically if the server says the batch is too large).
    public var batchSize: Int
    public var maxBatchesPerCycle: Int
    public var maxPagesPerCycle: Int
    public var backoff: Backoff

    public init(appVersion: String, batchSize: Int = 25, maxBatchesPerCycle: Int = 20, maxPagesPerCycle: Int = 20,
                backoff: Backoff = Backoff()) {
        self.appVersion = appVersion
        self.batchSize = batchSize
        self.maxBatchesPerCycle = maxBatchesPerCycle
        self.maxPagesPerCycle = maxPagesPerCycle
        self.backoff = backoff
    }
}

public struct SyncReport: Sendable, Equatable {
    public enum Outcome: Sendable, Equatable {
        case synced
        /// Network unreachable / timed out; retried with backoff.
        case offline(String)
        /// 5xx, 429 or another server-side failure; retried with backoff.
        case serverUnavailable(String)
        case notAuthenticated
        case backingOff(until: Date)
        case alreadyRunning
    }

    public var outcome: Outcome
    public var pushed: [AppliedOutcome] = []
    public var uploaded = 0
    public var pulledEntities = 0
}

/// Keys the engine keeps in `sync_kv` (tenant scope unless noted).
enum SyncKey {
    static let registered = "device_registered"
    static let cursor = "cursor"
    static let grantUntil = "offline_grant_until"
    static let grantSeconds = "offline_grant_seconds"
    static let failures = "consecutive_failures"
    static let nextSyncAt = "next_sync_at"
    static let lastSuccessAt = "last_success_at"
    static let clockSkewAlert = "server_clock_skew_alert"
    /// Device scope.
    static let clockReference = "clock_reference"
}

/// Offline-first sync for one tenant: register → bootstrap (first time) → upload evidence →
/// push outbox in bounded batches → pull changes. All state is in the encrypted database, so a
/// cycle interrupted by app termination resumes safely (SENT operations go back to PENDING and are
/// re-sent with the same ids; the server answers DUPLICATE).
///
/// Every cycle belongs to the signed-in `account`: a tenant last synced by another user is reset
/// first (fresh bootstrap, see ``SyncStateStore/claim(tenantID:owner:)``) and only this user's
/// evidence and operations are uploaded and pushed under their token. Without an account (tests,
/// tools) every owner's work is synced.
public actor SyncEngine {
    public let tenantID: UUID
    public let account: AccountIdentity?
    let store: LocalStore
    let evidence: EvidenceStore
    let api: SyncAPI
    let configuration: SyncConfiguration
    let clock: any ClockSource
    let random: @Sendable () -> Double
    private var running = false
    private var recovered = false

    public init(store: LocalStore, evidence: EvidenceStore, api: SyncAPI, tenantID: UUID,
                configuration: SyncConfiguration, clock: any ClockSource = SystemClockSource(),
                random: @escaping @Sendable () -> Double = { Double.random(in: 0..<1) },
                account: AccountIdentity? = nil) {
        self.account = account
        self.store = store
        self.evidence = evidence
        self.api = api
        self.tenantID = tenantID
        self.configuration = configuration
        self.clock = clock
        self.random = random
    }

    private var tenantKey: String { tenantID.uuidString.lowercased() }

    /// Runs one sync cycle. Throws only ``SyncError/deviceRevoked(message:)`` (the caller must wipe).
    /// `force` ignores the backoff window (user pressed "Sync now", connectivity just returned).
    public func sync(force: Bool = false) async throws -> SyncReport {
        guard !running else { return SyncReport(outcome: .alreadyRunning) }
        if let account {
            // Never resume another user's cursor: their state is reset before anything is sent or pulled.
            do { try store.syncState.claim(tenantID: tenantID, owner: account.subject) } catch {
                return SyncReport(outcome: .serverUnavailable(String(describing: error)))
            }
        }
        let now = clock.wallNow
        if !force, let next = try? date(SyncKey.nextSyncAt), next > now {
            return SyncReport(outcome: .backingOff(until: next))
        }
        running = true
        defer { running = false }
        var report = SyncReport(outcome: .synced)
        do {
            if !recovered {
                try store.outbox.recoverInFlight(tenantID: tenantID)
                recovered = true
            }
            try await ensureRegistered()
            if try value(SyncKey.cursor) == nil { report.pulledEntities += try await bootstrap() }
            report.uploaded = try await uploadAttachments()
            report.pushed = try await pushAll()
            report.pulledEntities += try await pullChanges()
            try setValue("0", SyncKey.failures)
            try setValue(nil, SyncKey.nextSyncAt)
            try setDate(clock.wallNow, SyncKey.lastSuccessAt)
        } catch let error as SyncError {
            switch error {
            case .deviceRevoked: throw error
            case .notAuthenticated: report.outcome = .notAuthenticated
            }
        } catch {
            if let api = error as? APIError, api.serverCode == "DEVICE_NOT_REGISTERED" {
                try? setValue(nil, SyncKey.registered)
            }
            report.outcome = Self.classify(error)
            try? recordFailure()
        }
        return report
    }

    static func classify(_ error: any Error) -> SyncReport.Outcome {
        switch error {
        case let api as APIError:
            if case .transport = api { return .offline(api.localizedDescription) }
            return .serverUnavailable("\(api.code): \(api.localizedDescription)")
        case let url as URLError:
            return .offline(url.localizedDescription)
        default:
            return .serverUnavailable(String(describing: error))
        }
    }

    private func recordFailure() throws {
        let failures = (Int(try value(SyncKey.failures) ?? "0") ?? 0) + 1
        try setValue(String(failures), SyncKey.failures)
        let delay = configuration.backoff.delay(failures: failures, unitRandom: random())
        try setDate(clock.wallNow.addingTimeInterval(delay), SyncKey.nextSyncAt)
    }

    // MARK: - Steps

    private func ensureRegistered() async throws {
        guard try value(SyncKey.registered) == nil else { return }
        let session = try await api.register(appVersion: configuration.appVersion)
        try setDate(session.offlineGrantUntil, SyncKey.grantUntil)
        try setValue(api.deviceID, SyncKey.registered)
    }

    private func bootstrap() async throws -> Int {
        let response = try await api.bootstrap()
        let entities = try Self.entities(response.data, revision: response.cursor)
        try store.database.transaction {
            try store.syncState.replaceAll(entities, tenantID: tenantID)
            try saveCustody(response.data.cashCustody, asOf: response.serverTime)
            try saveSnapshots(response.policySnapshots, receivedAt: response.serverTime)
            try setValue(String(response.cursor), SyncKey.cursor)
            try setDate(response.deviceSession.offlineGrantUntil, SyncKey.grantUntil)
            let seconds = response.deviceSession.offlineGrantUntil.timeIntervalSince(response.serverTime)
            try setValue(String(Int(seconds)), SyncKey.grantSeconds)
        }
        try observe(serverTime: response.serverTime)
        return entities.count
    }

    private func pullChanges() async throws -> Int {
        var written = 0
        for _ in 0..<configuration.maxPagesPerCycle {
            let cursor = Int64(try value(SyncKey.cursor) ?? "0") ?? 0
            let page = try await api.changes(cursor: cursor)
            let entities = try Self.entities(page.data, revision: page.cursor)
            try store.database.transaction {
                written += try store.syncState.upsert(entities, tenantID: tenantID)
                try saveCustody(page.data.cashCustody, asOf: page.serverTime)
                try saveSnapshots(page.policySnapshots, receivedAt: page.serverTime)
                try setValue(String(max(page.cursor, cursor)), SyncKey.cursor)
            }
            try observe(serverTime: page.serverTime)
            if !page.hasMore { break }
        }
        return written
    }

    private func uploadAttachments() async throws -> Int {
        let uploader = BlobUploader(api: api, attachments: store.attachments, evidence: evidence)
        var done = 0
        for attachment in try store.attachments.pendingUploads(tenantID: tenantID, owner: account?.subject, now: clock.wallNow) {
            do {
                if case .complete = try await uploader.upload(attachment, now: clock.wallNow) { done += 1 }
            } catch let error as SyncError {
                throw error
            } catch let error as APIError where !error.isRetryable {
                // A permanent server refusal for this file: record it and move on to the others.
                try store.attachments.recordAttemptFailure(
                    id: attachment.id, error: "\(error.code): \(error.localizedDescription)",
                    retryAt: clock.wallNow.addingTimeInterval(configuration.backoff.maxDelay))
            } catch {
                try store.attachments.recordAttemptFailure(id: attachment.id, error: String(describing: error), retryAt: nil)
                throw error
            }
        }
        return done
    }

    private func pushAll() async throws -> [AppliedOutcome] {
        let applier = PushOutcomeApplier(outbox: store.outbox)
        var outcomes: [AppliedOutcome] = []
        var batchSize = max(1, configuration.batchSize)
        for _ in 0..<configuration.maxBatchesPerCycle {
            let ready = try store.outbox.readyToSend(tenantID: tenantID, owner: account?.subject, now: clock.wallNow,
                                                     limit: batchSize)
            guard !ready.isEmpty else { break }
            let operations = try ready.map { op in
                OperationIn(id: op.id, opType: op.opType, createdAtDevice: op.createdAtDevice,
                            dependsOn: op.dependencies, payload: try JSONValue.parse(op.payloadJSON))
            }
            for op in ready { try store.outbox.markSent(id: op.id) }
            let response: PushResultDTO
            do {
                response = try await api.push(PushIn(deviceNow: clock.wallNow, operations: operations))
            } catch {
                // Never synced before an ACK: everything in the batch goes back to pending.
                for op in ready { try? store.outbox.release(id: op.id, error: String(describing: error), retryAt: nil) }
                if let api = error as? APIError, api.serverCode == "BATCH_TOO_LARGE", batchSize > 1 {
                    batchSize = max(1, batchSize / 2)
                    continue
                }
                throw error
            }
            try observe(serverTime: response.serverTime)
            try setValue(response.clockSkewAlert ? "1" : "0", SyncKey.clockSkewAlert)
            let applied = try applier.apply(response, sent: ready.map(\.id), now: clock.wallNow)
            outcomes += ready.compactMap { applied[$0.id] }
        }
        return outcomes
    }

    // MARK: - Helpers

    static func entities(_ data: SyncData, revision: Int64) throws -> [StoredEntity] {
        try data.byType.flatMap { type, objects in
            try objects.compactMap { object -> StoredEntity? in
                guard let id = object["id"]?.stringValue.flatMap(UUID.init(uuidString:)) else { return nil }
                return StoredEntity(entityType: type, id: id, revision: revision,
                                    version: object["version"]?.intValue.map(Int64.init), json: try object.jsonString())
            }
        }
    }

    /// Custody is a complete, current list (not a delta): it replaces the local copy.
    private func saveCustody(_ objects: [JSONValue], asOf: Date) throws {
        let balances = try objects.compactMap { object -> StoredCustodyBalance? in
            guard let staff = object["staff_member_id"]?.stringValue.flatMap(UUID.init(uuidString:)),
                  let currency = object["currency"]?.stringValue, currency.count == 3 else { return nil }
            let at = object["as_of"]?.stringValue.flatMap(AssetaJSON.parseInstant) ?? asOf
            return StoredCustodyBalance(staffMemberID: staff, currency: currency, json: try object.jsonString(), asOf: at)
        }
        try store.syncState.replaceCustody(balances, asOf: asOf, tenantID: tenantID)
    }

    private func saveSnapshots(_ snapshots: [PolicySnapshotDTO], receivedAt: Date) throws {
        try store.syncState.savePolicySnapshots(
            try snapshots.map { try MeterPolicySnapshot.stored($0, receivedAt: receivedAt) }, tenantID: tenantID)
    }

    /// Every server response refreshes the clock reference and, like the server's own `touch`,
    /// extends the offline grant from server time.
    private func observe(serverTime: Date) throws {
        let reference = ClockMonitor.reference(serverTime: serverTime, source: clock)
        try store.syncState.setValue(String(decoding: try JSONEncoder().encode(reference), as: UTF8.self),
                                     for: SyncKey.clockReference, tenant: SyncStateStore.deviceScope)
        if let seconds = try value(SyncKey.grantSeconds).flatMap(Double.init) {
            try setDate(serverTime.addingTimeInterval(seconds), SyncKey.grantUntil)
        }
    }

    private func value(_ key: String) throws -> String? { try store.syncState.value(key, tenant: tenantKey) }
    private func setValue(_ value: String?, _ key: String) throws {
        try store.syncState.setValue(value, for: key, tenant: tenantKey)
    }
    private func date(_ key: String) throws -> Date? {
        try value(key).flatMap(Int64.init).map(Date.init(millisecondsSince1970:))
    }
    private func setDate(_ date: Date, _ key: String) throws { try setValue(String(date.millisecondsSince1970), key) }
}
