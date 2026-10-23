import AssetaModel
import AssetaStore
import Foundation

/// A timed work-log entry that is still running on this phone. It stays local (encrypted key/value
/// store, one per job) until it is stopped; stopping queues exactly one `JOB_ACTIVITY` with its end.
public struct RunningWorkEntry: Codable, Sendable, Equatable {
    public let clientID: UUID
    public let activityType: ActivityType
    public let startedAt: Date
    public let note: String?

    enum CodingKeys: String, CodingKey {
        case note
        case clientID = "client_id", activityType = "activity_type", startedAt = "started_at"
    }
}

/// One line of a job's work log: a recorded `JOB_ACTIVITY` or the running entry.
public struct WorkLogLine: Sendable, Equatable, Identifiable {
    public let id: UUID
    public let type: ActivityType
    public let startedAt: Date
    public let endedAt: Date?
    public let note: String?
    public let isRunning: Bool
}

extension FieldRecorder {
    /// One running entry per job and user: `work_log_running.<owner>.<job>` (legacy entries without
    /// an owner are moved to their owner's key by `LocalStore.adoptLegacyData`).
    func runningKey(_ jobID: UUID) -> String {
        let job = jobID.uuidString.lowercased()
        return owner.map { "work_log_running.\($0.subject).\(job)" } ?? "work_log_running.\(job)"
    }
    private var tenantKey: String { tenantID.uuidString.lowercased() }

    public func runningEntry(jobID: UUID) throws -> RunningWorkEntry? {
        guard let text = try store.syncState.value(runningKey(jobID), tenant: tenantKey) else { return nil }
        return try? AssetaJSON.decoder().decode(RunningWorkEntry.self, from: Data(text.utf8))
    }

    /// Starts a timed WORK/STANDBY/DOWNTIME/MOBILIZATION entry (local until stopped). One running entry per job.
    @discardableResult
    public func startEntry(job: JobDTO, type: ActivityType, startedAt: Date, note: String?) throws -> RunningWorkEntry {
        guard type != .note else { throw FieldRecorderError.invalid("A note is not timed.") }
        guard try progress(jobID: job.id, serverStatus: job.status).canLogActivity else {
            throw FieldRecorderError.notAllowed("Work can only be logged on approved or running jobs.")
        }
        if try runningEntry(jobID: job.id) != nil { throw FieldRecorderError.notAllowed("Stop the running entry first.") }
        let trimmed = note?.trimmingCharacters(in: .whitespacesAndNewlines)
        let entry = RunningWorkEntry(clientID: UUID(), activityType: type, startedAt: startedAt,
                                     note: (trimmed?.isEmpty ?? true) ? nil : String(trimmed!.prefix(2000)))
        let json = String(decoding: try AssetaJSON.encoder().encode(entry), as: UTF8.self)
        try store.syncState.setValue(json, for: runningKey(job.id), tenant: tenantKey)
        return entry
    }

    /// Stops the running entry of `job` and queues its single `JOB_ACTIVITY` (client id kept from the start).
    @discardableResult
    public func stopEntry(job: JobDTO, at date: Date = Date()) throws -> ClientOperation {
        guard let entry = try runningEntry(jobID: job.id) else {
            throw FieldRecorderError.notAllowed("This entry is already stopped.")
        }
        return try store.database.transaction {
            let op = try recordActivity(job: job, type: entry.activityType, startedAt: entry.startedAt,
                                        endedAt: max(date, entry.startedAt), billable: nil, note: entry.note, at: date,
                                        clientID: entry.clientID)
            try store.syncState.setValue(nil, for: runningKey(job.id), tenant: tenantKey)
            return op
        }
    }

    /// The job's work log: every recorded activity (oldest first) followed by the running entry.
    public func workLog(jobID: UUID) throws -> [WorkLogLine] {
        let decoder = AssetaJSON.decoder()
        var lines = try store.outbox.operations(tenantID: tenantID, owner: owner?.subject, jobID: jobID)
            .filter { $0.opType == OperationType.jobActivity.rawValue }
            .compactMap { try? decoder.decode(ActivityPayload.self, from: Data($0.payloadJSON.utf8)) }
            .map { WorkLogLine(id: $0.clientID, type: $0.activityType, startedAt: $0.startedAt, endedAt: $0.endedAt,
                               note: $0.note, isRunning: false) }
            .sorted { $0.startedAt < $1.startedAt }
        if let running = try runningEntry(jobID: jobID) {
            lines.append(WorkLogLine(id: running.clientID, type: running.activityType, startedAt: running.startedAt,
                                     endedAt: nil, note: running.note, isRunning: true))
        }
        return lines
    }
}
