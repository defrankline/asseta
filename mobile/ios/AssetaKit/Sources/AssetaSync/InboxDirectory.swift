import AssetaModel
import AssetaStore
import Foundation

/// A reading of mine: the server's copy (state, findings, review) and/or this phone's capture
/// (its outbox operation) with its sync state. Same model as Android `ReadingItem`.
public struct ReadingItem: Sendable, Identifiable, Equatable {
    public let id: UUID
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
    /// Counts as the machine's latest reading (not refused by the server or replaced).
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
    public let machineID: UUID?
    public let at: Date
    public let status: InboxStatus
    public let decisionNote: String?
    public let decidedAt: Date?
    public let receiptAttachmentIDs: [UUID]
    public let op: ClientOperation?
    /// DEC-033: why the office checks it (neutral flags, from the server copy).
    public var controlFlags: [String] = []
}

public struct FuelItem: Sendable, Identifiable, Equatable {
    public let id: UUID
    public let eventType: String
    public let litres: String
    public let unitPrice: String?
    public let attributedCost: String?
    public let currency: String?
    public let machineID: UUID?
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
    public let op: ClientOperation?
    /// The collection / remittance number once the server has it (DEC-032 Phase 3).
    public var number: String? = nil
}

/// Something that needs the supervisor's attention (Inbox "Needs attention").
public struct AttentionItem: Sendable, Identifiable, Equatable {
    public enum Kind: String, Sendable { case reading, reset, expense, fuel, collection, handover, upload }
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
    /// Evidence that failed for good.
    public var failedUploads: [LocalAttachment] = []
    public var machines: [UUID: MachineDTO] = [:]

    public init() {}

    /// Newest first: flagged/rejected readings, rejected expenses and cash, failed uploads.
    public var attention: [AttentionItem] {
        var items: [AttentionItem] = []
        items += readings.filter(\.status.needsAttention).map { AttentionItem(id: "r-\($0.id)", kind: .reading, refID: $0.id, at: $0.at, status: $0.status) }
        items += resets.filter(\.status.needsAttention).map { AttentionItem(id: "m-\($0.id)", kind: .reset, refID: $0.id, at: $0.at, status: $0.status) }
        items += expenses.filter(\.status.needsAttention).map { AttentionItem(id: "e-\($0.id)", kind: .expense, refID: $0.id, at: $0.at, status: $0.status) }
        items += fuel.filter(\.status.needsAttention).map { AttentionItem(id: "f-\($0.id)", kind: .fuel, refID: $0.id, at: $0.at, status: $0.status) }
        items += collections.filter(\.status.needsAttention).map { AttentionItem(id: "c-\($0.id)", kind: .collection, refID: $0.id, at: $0.at, status: $0.status) }
        items += handovers.filter(\.status.needsAttention).map { AttentionItem(id: "h-\($0.id)", kind: .handover, refID: $0.id, at: $0.at, status: $0.status) }
        items += failedUploads.map { AttentionItem(id: "u-\($0.id)", kind: .upload, refID: $0.id, at: $0.createdAt, status: .notSynced) }
        return items.sorted { $0.at > $1.at }
    }

    public func machine(of reading: ReadingItem) -> UUID? { reading.machineID }

    /// Latest counted reading per machine (my captures).
    public func latestReadingByMachine() -> [UUID: ReadingItem] {
        var latest: [UUID: ReadingItem] = [:]
        for reading in readings where reading.counts {
            guard let machine = machine(of: reading) else { continue }
            if latest[machine].map({ $0.at < reading.at }) ?? true { latest[machine] = reading }
        }
        return latest
    }

}

/// Read side of the supervisor tabs: the server's copies of my records (`inbox_record`) merged with
/// this phone's own records (outbox operations) of the signed-in `owner`.
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
        let machines = try decodeAll("machine", as: MachineDTO.self)
        return Self.build(records: records, operations: operations, failedUploads: failed, machines: machines)
    }

    private func decodeAll<T: Decodable>(_ type: String, as: T.Type) throws -> [T] {
        try store.syncState.entities(type: type, tenantID: tenantID)
            .compactMap { try? AssetaJSON.decoder().decode(T.self, from: Data($0.json.utf8)) }
    }

    /// Pure merge of one state of the store (unit-tested).
    public static func build(records: [InboxRecord], operations: [ClientOperation], failedUploads: [LocalAttachment],
                             machines: [MachineDTO]) -> InboxSnapshot {
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
            guard let id = s?.id ?? m.local?.entityID else { return nil }
            let server = s.map { InboxStatusRules.reading(state: $0.state, reviewStatus: $0.reviewStatus,
                                                          findingStatuses: $0.findings.map(\.status)) }
            return ReadingItem(
                id: id, machineID: s?.machineID ?? uuid(p, "machine_id"), kind: s?.kind ?? text(p, "kind") ?? "",
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
                categoryID: s?.categoryID ?? uuid(p, "category_id"),
                machineID: s?.machineID ?? uuid(p, "machine_id"),
                at: s?.incurredAt ?? date(p, "incurred_at") ?? m.local?.createdAtDevice ?? .distantPast,
                status: InboxStatusRules.combined(local: m.local?.status, server: s.map { InboxStatusRules.expense($0.status) }),
                decisionNote: s?.decisionNote, decidedAt: s?.decidedAt, receiptAttachmentIDs: s?.receiptAttachmentIDs ?? [],
                op: m.local, controlFlags: s?.controlFlags ?? [])
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
                expenseID: s?.expenseID,
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
                decisionNote: s?.decisionNote, verifiedAt: s?.verifiedAt, op: m.local,
                number: s?.collectionNumber)
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
                decisionNote: s?.decisionNote, verifiedAt: s?.verifiedAt, op: m.local, number: s?.remittanceNumber)
        }.sorted { $0.at > $1.at }

        snapshot.failedUploads = failedUploads
        snapshot.machines = Dictionary(machines.map { ($0.id, $0) }, uniquingKeysWith: { a, _ in a })
        return snapshot
    }

    /// The server id an acknowledgement returned (`result.entity.id`), if any.
    static func serverID(of op: ClientOperation) -> UUID? {
        guard let text = op.serverResultJSON, let value = try? JSONValue.parse(text) else { return nil }
        return (value["result"]?["entity"]?["id"] ?? value["entity"]?["id"])?.stringValue.flatMap(UUID.init(uuidString:))
    }
}

private func serverID(of op: ClientOperation) -> UUID? { InboxDirectory.serverID(of: op) }
