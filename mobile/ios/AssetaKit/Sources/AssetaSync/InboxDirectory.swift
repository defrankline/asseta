import AssetaModel
import AssetaStore
import Foundation

/// A reading of mine: the server's copy (state, findings, review) and/or this phone's capture
/// (its outbox operation) with its sync state. Same model as Android `ReadingItem`.
public struct ReadingItem: Sendable, Identifiable, Equatable {
    public let id: UUID
    public let jobID: UUID
    public let machineID: UUID?
    public let kind: String
    public let reading: String
    public let captureMode: String
    public let at: Date
    public let status: InboxStatus
    public let server: SyncMeterCaptureDTO?
    public let op: ClientOperation?
    /// The capture as recorded on this phone (OCR, GPS), when it was recorded here.
    public let localPayload: JSONValue?

    public var findings: [FindingDTO] { server?.findings ?? [] }
    public var openFindings: Int { findings.filter { $0.status == "OPEN" }.count }
    public var blockingFindings: Int { findings.filter { $0.blocking && $0.status == "OPEN" }.count }
    /// Counts towards a job's opening/closing figures (not refused by the server or replaced).
    public var counts: Bool { ![.rejected, .superseded, .notSynced].contains(status) }
}

public struct ResetItem: Sendable, Identifiable, Equatable {
    public let id: UUID
    public let machineID: UUID?
    public let oldReading: String
    public let newReading: String
    public let effectiveAt: Date
    public let reason: String
    public let at: Date
    public let status: InboxStatus
    public let decidedAt: Date?
    public let hasEvidence: Bool
    public let server: SyncMeterResetDTO?
    public let op: ClientOperation?
}

public struct ExpenseItem: Sendable, Identifiable, Equatable {
    public let id: UUID
    public let serverID: UUID?
    public let description: String
    public let supplier: String?
    public let amount: String
    public let currency: String
    public let paidFrom: String
    public let categoryID: UUID?
    public let jobID: UUID?
    public let machineID: UUID?
    public let at: Date
    public let status: InboxStatus
    public let decisionNote: String?
    public let decidedAt: Date?
    public let receiptAttachmentIDs: [UUID]
    public let op: ClientOperation?
}

public struct FuelItem: Sendable, Identifiable, Equatable {
    public let id: UUID
    public let eventType: String
    public let litres: String
    public let unitPrice: String?
    public let attributedCost: String?
    public let currency: String?
    public let machineID: UUID?
    public let jobID: UUID?
    public let expenseID: UUID?
    public let meterReading: String?
    public let supplier: String?
    public let note: String?
    public let at: Date
    public let status: InboxStatus
    public let op: ClientOperation?
}

/// A cash collection or handover (`customerID` nil for a handover).
public struct CashItem: Sendable, Identifiable, Equatable {
    public let id: UUID
    public let isCollection: Bool
    public let customerID: UUID?
    public let amount: String
    public let currency: String
    public let reference: String?
    public let note: String?
    public let at: Date
    public let status: InboxStatus
    public let decisionNote: String?
    public let verifiedAt: Date?
    public let allocations: Int
    public let op: ClientOperation?
}

/// A work-log entry: the server's activity and/or this phone's entry (`running` until stopped).
public struct ActivityItem: Sendable, Identifiable, Equatable {
    public let id: UUID
    public let jobID: UUID
    public let activityType: String
    public let start: Date
    public let end: Date?
    public let note: String?
    public let running: Bool
    public let status: InboxStatus
}

public struct AcknowledgementItem: Sendable, Identifiable, Equatable {
    public let id: UUID
    public let jobID: UUID
    public let method: String
    public let signerName: String
    public let signerPhone: String?
    public let hours: String?
    public let signatureAttachmentID: UUID?
    public let at: Date
    public let status: InboxStatus
    public let op: ClientOperation?
}

/// Something that needs the supervisor's attention (Inbox "Needs attention").
public struct AttentionItem: Sendable, Identifiable, Equatable {
    public enum Kind: String, Sendable { case reading, reset, expense, fuel, collection, handover, operation, upload }
    public let id: String
    public let kind: Kind
    public let refID: UUID
    public let at: Date
    public let status: InboxStatus
}

/// Everything the supervisor tabs show, merged once per refresh.
public struct InboxSnapshot: Sendable, Equatable {
    public var readings: [ReadingItem] = []
    public var resets: [ResetItem] = []
    public var expenses: [ExpenseItem] = []
    public var fuel: [FuelItem] = []
    public var collections: [CashItem] = []
    public var handovers: [CashItem] = []
    public var activities: [ActivityItem] = []
    public var acknowledgements: [AcknowledgementItem] = []
    /// Refused job steps (start/complete, work log, acknowledgement) and evidence that failed for good.
    public var problemOperations: [ClientOperation] = []
    public var failedUploads: [LocalAttachment] = []
    public var machines: [UUID: MachineDTO] = [:]
    public var jobs: [UUID: JobDTO] = [:]

    public init() {}

    /// Newest first: flagged/rejected readings, rejected expenses and cash, refused sync items, failed uploads.
    public var attention: [AttentionItem] {
        var items: [AttentionItem] = []
        items += readings.filter(\.status.needsAttention).map { AttentionItem(id: "r-\($0.id)", kind: .reading, refID: $0.id, at: $0.at, status: $0.status) }
        items += resets.filter(\.status.needsAttention).map { AttentionItem(id: "m-\($0.id)", kind: .reset, refID: $0.id, at: $0.at, status: $0.status) }
        items += expenses.filter(\.status.needsAttention).map { AttentionItem(id: "e-\($0.id)", kind: .expense, refID: $0.id, at: $0.at, status: $0.status) }
        items += fuel.filter(\.status.needsAttention).map { AttentionItem(id: "f-\($0.id)", kind: .fuel, refID: $0.id, at: $0.at, status: $0.status) }
        items += collections.filter(\.status.needsAttention).map { AttentionItem(id: "c-\($0.id)", kind: .collection, refID: $0.id, at: $0.at, status: $0.status) }
        items += handovers.filter(\.status.needsAttention).map { AttentionItem(id: "h-\($0.id)", kind: .handover, refID: $0.id, at: $0.at, status: $0.status) }
        items += problemOperations.map { AttentionItem(id: "o-\($0.id)", kind: .operation, refID: $0.id, at: $0.createdAtDevice, status: .notSynced) }
        items += failedUploads.map { AttentionItem(id: "u-\($0.id)", kind: .upload, refID: $0.id, at: $0.createdAt, status: .notSynced) }
        return items.sorted { $0.at > $1.at }
    }

    public func readings(ofJob jobID: UUID) -> [ReadingItem] { readings.filter { $0.jobID == jobID } }

    public func machine(of reading: ReadingItem) -> UUID? { reading.machineID ?? jobs[reading.jobID]?.machineID }

    /// Latest counted reading per machine (my captures).
    public func latestReadingByMachine() -> [UUID: ReadingItem] {
        var latest: [UUID: ReadingItem] = [:]
        for reading in readings where reading.counts {
            guard let machine = machine(of: reading) else { continue }
            if latest[machine].map({ $0.at < reading.at }) ?? true { latest[machine] = reading }
        }
        return latest
    }

    /// The latest counted opening / closing reading of a job.
    public func jobReading(_ jobID: UUID, kind: String) -> ReadingItem? {
        readings.filter { $0.jobID == jobID && $0.kind == kind && $0.counts }.max { $0.at < $1.at }
    }
}

/// Read side of the supervisor tabs: the server's copies of my records (`inbox_record`) merged with
/// this phone's own records (outbox operations, running work-log entries) of the signed-in `owner`.
/// Local records show "Waiting to sync" until acknowledged, then merge with the server record
/// (matched by client id or the acknowledged server id). Same rules as Android `InboxRepository`.
public struct InboxDirectory: Sendable {
    let store: LocalStore
    let tenantID: UUID
    let owner: AccountIdentity?

    public init(store: LocalStore, tenantID: UUID, owner: AccountIdentity? = nil) {
        self.store = store
        self.tenantID = tenantID
        self.owner = owner
    }

    public func snapshot() throws -> InboxSnapshot {
        let operations = try store.outbox.operations(tenantID: tenantID, owner: owner?.subject,
                                                     statuses: Set(ClientOperationStatus.allCases))
        let records = try store.inbox.records(tenantID: tenantID)
        let failed = try store.attachments.attachments(tenantID: tenantID, statuses: [.failed], owner: owner?.subject)
        let jobs = try decodeAll("job", as: JobDTO.self)
        let machines = try decodeAll("machine", as: MachineDTO.self)
        return Self.build(records: records, operations: operations, running: try runningEntries(), failedUploads: failed,
                          machines: machines, jobs: jobs)
    }

    /// Running work-log entries of the signed-in user (`work_log_running.<owner>.<job>`).
    private func runningEntries() throws -> [(jobID: UUID, entry: RunningWorkEntry)] {
        let prefix = owner.map { "work_log_running.\($0.subject)." } ?? "work_log_running."
        let rows = try store.database.query(
            "SELECT key, value FROM sync_kv WHERE tenant_id = ? AND key LIKE ?",
            [.text(tenantID.lowercased), .text(prefix + "%")]
        ) { ($0.string(0) ?? "", $0.string(1) ?? "") }
        return rows.compactMap { key, value in
            guard let job = UUID(uuidString: String(key.dropFirst(prefix.count))),
                  let entry = try? AssetaJSON.decoder().decode(RunningWorkEntry.self, from: Data(value.utf8)) else { return nil }
            return (job, entry)
        }
    }

    private func decodeAll<T: Decodable>(_ type: String, as: T.Type) throws -> [T] {
        try store.syncState.entities(type: type, tenantID: tenantID)
            .compactMap { try? AssetaJSON.decoder().decode(T.self, from: Data($0.json.utf8)) }
    }

    /// Pure merge of one state of the store (unit-tested).
    public static func build(records: [InboxRecord], operations: [ClientOperation],
                             running: [(jobID: UUID, entry: RunningWorkEntry)], failedUploads: [LocalAttachment],
                             machines: [MachineDTO], jobs: [JobDTO]) -> InboxSnapshot {
        let decoder = AssetaJSON.decoder()
        func parse<T: Decodable>(_ kind: InboxRecord.Kind, _ type: T.Type) -> [T] {
            records.filter { $0.kind == kind }.compactMap { try? decoder.decode(T.self, from: Data($0.json.utf8)) }
        }
        func ops(_ type: OperationType) -> [ClientOperation] { operations.filter { $0.opType == type.rawValue } }
        func payload(_ op: ClientOperation?) -> JSONValue? { op.flatMap { try? JSONValue.parse($0.payloadJSON) } }
        func localKey(_ op: ClientOperation) -> LocalKey { LocalKey(entityID: op.entityID, serverID: serverID(of: op)) }
        func date(_ value: JSONValue?, _ key: String) -> Date? { value?[key]?.stringValue.flatMap(AssetaJSON.parseInstant) }
        func uuid(_ value: JSONValue?, _ key: String) -> UUID? { value?[key]?.stringValue.flatMap(UUID.init(uuidString:)) }
        func text(_ value: JSONValue?, _ key: String) -> String? {
            guard let field = value?[key], !field.isNull else { return nil }
            return field.stringValue ?? field.decimalValue.map { "\($0)" }
        }

        var snapshot = InboxSnapshot()
        snapshot.readings = InboxMerge.merge(
            server: parse(.meterCapture, SyncMeterCaptureDTO.self), local: ops(.meterCapture),
            serverKeys: { [$0.id] }, localKey: localKey
        ).compactMap { m -> ReadingItem? in
            let s = m.server
            let p = payload(m.local)
            guard let id = s?.id ?? m.local?.entityID, let job = s?.jobID ?? uuid(p, "job_id") else { return nil }
            let server = s.map { InboxStatusRules.reading(state: $0.state, reviewStatus: $0.reviewStatus,
                                                          findingStatuses: $0.findings.map(\.status)) }
            return ReadingItem(
                id: id, jobID: job, machineID: s?.machineID, kind: s?.kind ?? text(p, "kind") ?? "",
                reading: s?.reading ?? text(p, "reading") ?? "", captureMode: s?.captureMode ?? text(p, "capture_mode") ?? "",
                at: date(p, "captured_at") ?? s?.capturedAt ?? m.local?.createdAtDevice ?? .distantPast,
                status: InboxStatusRules.combined(local: m.local?.status, server: server), server: s, op: m.local,
                localPayload: p)
        }.sorted { $0.at > $1.at }

        snapshot.resets = InboxMerge.merge(
            server: parse(.meterReset, SyncMeterResetDTO.self), local: ops(.meterResetRequest),
            serverKeys: { [$0.id] }, localKey: localKey
        ).compactMap { m -> ResetItem? in
            let s = m.server
            let p = payload(m.local)
            guard let id = s?.id ?? m.local?.id else { return nil }
            return ResetItem(
                id: id, machineID: s?.machineID ?? uuid(p, "machine_id"),
                oldReading: s?.oldReading ?? text(p, "old_reading") ?? "", newReading: s?.newReading ?? text(p, "new_reading") ?? "",
                effectiveAt: s?.effectiveAt ?? date(p, "effective_at") ?? m.local?.createdAtDevice ?? .distantPast,
                reason: s?.reason ?? text(p, "reason") ?? "", at: m.local?.createdAtDevice ?? s?.createdAt ?? .distantPast,
                status: InboxStatusRules.combined(local: m.local?.status, server: s.map { InboxStatusRules.reset($0.status) }),
                decidedAt: s?.decidedAt, hasEvidence: s?.evidenceAttachmentID != nil || m.local != nil, server: s, op: m.local)
        }.sorted { $0.at > $1.at }

        snapshot.expenses = InboxMerge.merge(
            server: parse(.expense, SyncExpenseDTO.self), local: ops(.expense),
            serverKeys: { [$0.id] + ($0.clientID.map { [$0] } ?? []) }, localKey: localKey
        ).compactMap { m -> ExpenseItem? in
            let s = m.server
            let p = payload(m.local)
            guard let id = s?.id ?? m.local?.id else { return nil }
            return ExpenseItem(
                id: id, serverID: s?.id, description: s?.description ?? text(p, "description") ?? "",
                supplier: s?.supplier ?? text(p, "supplier"), amount: s?.amount ?? text(p, "amount") ?? "",
                currency: s?.currency ?? text(p, "currency") ?? "", paidFrom: s?.paidFrom ?? text(p, "paid_from") ?? "",
                categoryID: s?.categoryID ?? uuid(p, "category_id"), jobID: s?.jobID ?? uuid(p, "job_id"),
                machineID: s?.machineID ?? uuid(p, "machine_id"),
                at: s?.incurredAt ?? date(p, "incurred_at") ?? m.local?.createdAtDevice ?? .distantPast,
                status: InboxStatusRules.combined(local: m.local?.status, server: s.map { InboxStatusRules.expense($0.status) }),
                decisionNote: s?.decisionNote, decidedAt: s?.decidedAt, receiptAttachmentIDs: s?.receiptAttachmentIDs ?? [],
                op: m.local)
        }.sorted { $0.at > $1.at }

        snapshot.fuel = InboxMerge.merge(
            server: parse(.fuelEvent, SyncFuelEventDTO.self), local: ops(.fuelEvent),
            serverKeys: { [$0.id] + ($0.clientID.map { [$0] } ?? []) }, localKey: localKey
        ).compactMap { m -> FuelItem? in
            let s = m.server
            let p = payload(m.local)
            guard let id = s?.id ?? m.local?.id else { return nil }
            return FuelItem(
                id: id, eventType: s?.eventType ?? text(p, "event_type") ?? "", litres: s?.litres ?? text(p, "litres") ?? "",
                unitPrice: s?.unitPrice ?? text(p, "unit_price"), attributedCost: s?.attributedCost,
                currency: s?.currency ?? text(p, "currency"), machineID: s?.machineID ?? uuid(p, "machine_id"),
                jobID: s?.jobID ?? uuid(p, "job_id"), expenseID: s?.expenseID,
                meterReading: s?.meterReading ?? text(p, "meter_reading"), supplier: s?.supplier ?? text(p, "supplier"),
                note: s?.note ?? text(p, "note"),
                at: s?.occurredAt ?? date(p, "occurred_at") ?? m.local?.createdAtDevice ?? .distantPast,
                status: InboxStatusRules.combined(local: m.local?.status, server: s.map { _ in .recorded }), op: m.local)
        }.sorted { $0.at > $1.at }

        snapshot.collections = InboxMerge.merge(
            server: parse(.cashCollection, SyncCashCollectionDTO.self), local: ops(.cashCollection),
            serverKeys: { [$0.id] + ($0.clientID.map { [$0] } ?? []) }, localKey: localKey
        ).compactMap { m -> CashItem? in
            let s = m.server
            let p = payload(m.local)
            guard let id = s?.id ?? m.local?.id else { return nil }
            return CashItem(
                id: id, isCollection: true, customerID: s?.customerID ?? uuid(p, "customer_id"),
                amount: s?.amount ?? text(p, "amount") ?? "", currency: s?.currency ?? text(p, "currency") ?? "",
                reference: s?.reference ?? text(p, "reference"), note: s?.note ?? text(p, "note"),
                at: s?.receivedAt ?? date(p, "received_at") ?? m.local?.createdAtDevice ?? .distantPast,
                status: InboxStatusRules.combined(local: m.local?.status, server: s.map { InboxStatusRules.settlement($0.status) }),
                decisionNote: s?.decisionNote, verifiedAt: s?.verifiedAt, allocations: s?.allocations.count ?? 0, op: m.local)
        }.sorted { $0.at > $1.at }

        snapshot.handovers = InboxMerge.merge(
            server: parse(.cashHandover, SyncCashHandoverDTO.self), local: ops(.cashHandover),
            serverKeys: { [$0.id] + ($0.clientID.map { [$0] } ?? []) }, localKey: localKey
        ).compactMap { m -> CashItem? in
            let s = m.server
            let p = payload(m.local)
            guard let id = s?.id ?? m.local?.id else { return nil }
            return CashItem(
                id: id, isCollection: false, customerID: nil,
                amount: s?.amount ?? text(p, "amount") ?? "", currency: s?.currency ?? text(p, "currency") ?? "",
                reference: s?.reference ?? text(p, "reference"), note: s?.note ?? text(p, "note"),
                at: s?.handedAt ?? date(p, "handed_at") ?? m.local?.createdAtDevice ?? .distantPast,
                status: InboxStatusRules.combined(local: m.local?.status, server: s.map { InboxStatusRules.settlement($0.status) }),
                decisionNote: s?.decisionNote, verifiedAt: s?.verifiedAt, allocations: 0, op: m.local)
        }.sorted { $0.at > $1.at }

        // Work log: server activities, this phone's recorded activities and its running entries.
        struct LocalEntry { let op: ClientOperation?; let jobID: UUID; let clientID: UUID; let type: String; let start: Date; let end: Date?; let note: String? }
        let recorded = ops(.jobActivity).compactMap { op -> LocalEntry? in
            let p = payload(op)
            guard let job = uuid(p, "job_id"), let start = date(p, "started_at") else { return nil }
            return LocalEntry(op: op, jobID: job, clientID: op.entityID, type: text(p, "activity_type") ?? "", start: start,
                              end: date(p, "ended_at"), note: text(p, "note"))
        }
        let runningEntries = running.map {
            LocalEntry(op: nil, jobID: $0.jobID, clientID: $0.entry.clientID, type: $0.entry.activityType.rawValue,
                       start: $0.entry.startedAt, end: nil, note: $0.entry.note)
        }
        snapshot.activities = InboxMerge.merge(
            server: parse(.jobActivity, SyncJobActivityDTO.self), local: recorded + runningEntries,
            serverKeys: { [$0.id, $0.clientID] }, localKey: { LocalKey(entityID: $0.clientID, serverID: nil) }
        ).compactMap { m -> ActivityItem? in
            let s = m.server
            let e = m.local
            guard let id = s?.clientID ?? e?.clientID, let job = s?.jobID ?? e?.jobID, let start = s?.startedAt ?? e?.start else {
                return nil
            }
            return ActivityItem(
                id: id, jobID: job, activityType: s?.activityType ?? e?.type ?? "", start: start, end: s?.endedAt ?? e?.end,
                note: s?.note ?? e?.note, running: s == nil && e != nil && e?.op == nil,
                status: InboxStatusRules.combined(local: e?.op?.status, server: s.map { _ in .recorded }))
        }.sorted { $0.start < $1.start }

        snapshot.acknowledgements = InboxMerge.merge(
            server: parse(.acknowledgement, SyncAcknowledgementDTO.self), local: ops(.jobAcknowledgement),
            serverKeys: { [$0.id, $0.clientID] }, localKey: localKey
        ).compactMap { m -> AcknowledgementItem? in
            let s = m.server
            let p = payload(m.local)
            guard let id = s?.id ?? m.local?.id, let job = s?.jobID ?? uuid(p, "job_id") else { return nil }
            return AcknowledgementItem(
                id: id, jobID: job, method: s?.method ?? text(p, "method") ?? "", signerName: s?.signerName ?? text(p, "signer_name") ?? "",
                signerPhone: s?.signerPhone ?? text(p, "signer_phone"), hours: s?.acknowledgedHours ?? text(p, "acknowledged_hours"),
                signatureAttachmentID: s?.signatureAttachmentID,
                at: s?.capturedAt ?? date(p, "captured_at") ?? m.local?.createdAtDevice ?? .distantPast,
                status: InboxStatusRules.combined(local: m.local?.status, server: s.map { _ in .recorded }), op: m.local)
        }.sorted { $0.at > $1.at }

        // Refused job steps have no list of their own: they are listed under "Needs attention" as sync items.
        let jobSteps: Set<String> = [OperationType.jobTransition.rawValue, OperationType.jobActivity.rawValue,
                                     OperationType.jobAcknowledgement.rawValue]
        snapshot.problemOperations = operations.filter { jobSteps.contains($0.opType) && ($0.status == .failed || $0.status == .conflict) }
        snapshot.failedUploads = failedUploads
        snapshot.machines = Dictionary(machines.map { ($0.id, $0) }, uniquingKeysWith: { a, _ in a })
        snapshot.jobs = Dictionary(jobs.map { ($0.id, $0) }, uniquingKeysWith: { a, _ in a })
        return snapshot
    }

    /// The server id an acknowledgement returned (`result.entity.id`), if any.
    static func serverID(of op: ClientOperation) -> UUID? {
        guard let text = op.serverResultJSON, let value = try? JSONValue.parse(text) else { return nil }
        return (value["result"]?["entity"]?["id"] ?? value["entity"]?["id"])?.stringValue.flatMap(UUID.init(uuidString:))
    }
}

private func serverID(of op: ClientOperation) -> UUID? { InboxDirectory.serverID(of: op) }
