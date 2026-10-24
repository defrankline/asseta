import AssetaModel
import AssetaNetwork
import AssetaStore // UUID.lowercased
import Foundation

// Accountability decisions the Owner app lists under Approvals and decides (contracts/openapi.json): customer
// discounts, credit arrangements, hours transfers and cancellations, meter baselines, engine-hour classifications,
// reading corrections, cash write-offs, retentions and custody adjustments. Every kind needs its read permission to be
// listed and its decide permission to be decided; the server enforces both and segregation of duties.

/// `DecisionIn` (hours, cash): approve or reject with an optional note (at most 1000 characters).
public struct DecisionIn: Encodable, Hashable, Sendable {
    public let approve: Bool
    public let note: String?
}

/// `MeterDecisionIn` (baselines, classifications, corrections): APPROVE or REJECT with a 5..2000 character note.
public struct MeterDecisionIn: Encodable, Hashable, Sendable {
    public let decision: String
    public let note: String
}

/// One kind of accountability decision. Same list, wording and permissions as Android.
public enum DecisionKind: String, CaseIterable, Codable, Hashable, Sendable {
    case discount, credit, hoursTransfer, cancellation, baseline, classification, correction, writeOff, retention, adjustment

    /// `GET` path and the status that means "waiting for a decision".
    var list: (path: String, pendingStatus: String) {
        switch self {
        case .discount: ("customer-discounts", "PROPOSED")
        case .credit: ("credit-arrangements", "PROPOSED")
        case .hoursTransfer: ("hours-transfers", "PENDING")
        case .cancellation: ("hours-cancellations", "PENDING")
        case .baseline: ("meter-baselines", "PROPOSED")
        case .classification: ("engine-hours/classifications", "PROPOSED")
        case .correction: ("meter-corrections", "PROPOSED")
        case .writeOff: ("cash/variances", "WRITE_OFF_PROPOSED")
        case .retention: ("cash/retentions", "PENDING")
        case .adjustment: ("cash/adjustments", "PENDING")
        }
    }

    /// `POST` path of the decision.
    func decisionPath(_ id: UUID) -> String {
        let record = "\(list.path)/\(id.lowercased)"
        return self == .writeOff ? "\(record)/write-off-decision" : "\(record)/decision"
    }

    /// Meter decisions take `MeterDecisionIn` (note required, 5+ characters); the others `DecisionIn`.
    public var usesMeterDecision: Bool { [.baseline, .classification, .correction].contains(self) }

    /// The permission that lists this kind (as the server's list endpoint).
    public var readPermissions: [String] {
        switch self {
        case .discount, .credit, .hoursTransfer, .cancellation: ["tenant.hours.read"]
        case .baseline, .classification, .correction: ["tenant.meter.read"]
        case .writeOff, .adjustment: ["tenant.finance.read"]
        case .retention: ["tenant.collection.record", "tenant.finance.read"]
        }
    }

    /// The permission that decides this kind.
    public var decidePermission: String {
        switch self {
        case .discount: "tenant.hours.discount_approve"
        case .credit: "tenant.hours.credit_approve"
        case .hoursTransfer: "tenant.hours.transfer_approve"
        case .cancellation: "tenant.hours.cancel_approve"
        case .baseline, .correction: "tenant.meter.approve"
        case .classification: "tenant.meter.classify"
        case .writeOff: "tenant.finance.writeoff"
        case .retention: "tenant.finance.retention_approve"
        case .adjustment: "tenant.finance.adjustment_approve"
        }
    }

    public func visible(permissions: [String]) -> Bool { !Set(readPermissions).isDisjoint(with: permissions) }
    public func decidable(permissions: [String]) -> Bool { permissions.contains(decidePermission) }

    public var sectionTitle: String {
        switch self {
        case .discount: OwnerAccountabilityTexts.approvalsDiscounts
        case .credit: OwnerAccountabilityTexts.approvalsCredit
        case .hoursTransfer: OwnerAccountabilityTexts.approvalsHoursTransfers
        case .cancellation: OwnerAccountabilityTexts.approvalsCancellations
        case .baseline: OwnerAccountabilityTexts.approvalsBaselines
        case .classification: OwnerAccountabilityTexts.approvalsClassifications
        case .correction: OwnerAccountabilityTexts.approvalsCorrections
        case .writeOff: OwnerAccountabilityTexts.approvalsWriteOffs
        case .retention: OwnerAccountabilityTexts.approvalsRetentions
        case .adjustment: OwnerAccountabilityTexts.approvalsAdjustments
        }
    }

    public var emptyText: String {
        switch self {
        case .discount: OwnerAccountabilityTexts.approvalsDiscountsEmpty
        case .credit: OwnerAccountabilityTexts.approvalsCreditEmpty
        case .hoursTransfer: OwnerAccountabilityTexts.approvalsHoursTransfersEmpty
        case .cancellation: OwnerAccountabilityTexts.approvalsCancellationsEmpty
        case .baseline: OwnerAccountabilityTexts.approvalsBaselinesEmpty
        case .classification: OwnerAccountabilityTexts.approvalsClassificationsEmpty
        case .correction: OwnerAccountabilityTexts.approvalsCorrectionsEmpty
        case .writeOff: OwnerAccountabilityTexts.approvalsWriteOffsEmpty
        case .retention: OwnerAccountabilityTexts.approvalsRetentionsEmpty
        case .adjustment: OwnerAccountabilityTexts.approvalsAdjustmentsEmpty
        }
    }

    public var decisionTitle: String {
        switch self {
        case .discount: OwnerAccountabilityTexts.decisionTitleDiscount
        case .credit: OwnerAccountabilityTexts.decisionTitleCredit
        case .hoursTransfer: OwnerAccountabilityTexts.decisionTitleHoursTransfer
        case .cancellation: OwnerAccountabilityTexts.decisionTitleCancellation
        case .baseline: OwnerAccountabilityTexts.decisionTitleBaseline
        case .classification: OwnerAccountabilityTexts.decisionTitleClassification
        case .correction: OwnerAccountabilityTexts.decisionTitleCorrection
        case .writeOff: OwnerAccountabilityTexts.decisionTitleWriteOff
        case .retention: OwnerAccountabilityTexts.decisionTitleRetention
        case .adjustment: OwnerAccountabilityTexts.decisionTitleAdjustment
        }
    }

    /// From a notification target entity (`customer_discount`, `baseline`, `cash_retention`, ...).
    public init?(entity: String) {
        switch entity {
        case "customer_discount": self = .discount
        case "credit_arrangement": self = .credit
        case "hours_transfer": self = .hoursTransfer
        case "hours_cancellation": self = .cancellation
        case "baseline", "meter_baseline": self = .baseline
        case "classification", "engine_hours_classification": self = .classification
        case "correction", "meter_correction": self = .correction
        case "cash_variance": self = .writeOff
        case "cash_retention": self = .retention
        case "custody_adjustment": self = .adjustment
        default: return nil
        }
    }
}

/// One labelled value on the decision screen.
public struct DecisionField: Codable, Hashable, Sendable {
    public let label: String
    public let value: String
}

/// A decision of any kind, normalized for the list row and the decision screen.
public struct PendingDecision: Codable, Hashable, Sendable, Identifiable {
    public let kind: DecisionKind
    public let recordID: UUID
    public let headline: String
    public let status: String
    public let proposedBy: UUID?
    public let proposedByName: String?
    public let proposedAt: Date
    public let reason: String?
    public let fields: [DecisionField]
    public let machineID: UUID?
    public let photoAttachmentID: UUID?

    public var id: String { "\(kind.rawValue):\(recordID.lowercased)" }
    public var isPending: Bool { status == kind.list.pendingStatus }

    /// The signed-in user proposed it: someone else must decide (the server refuses it too).
    public func isOwn(userID: UUID?) -> Bool { userID != nil && proposedBy == userID }
}

// MARK: - DTOs (the part the Owner app shows)

struct DiscountDTO: Codable, Sendable {
    let id: UUID, customerID: UUID, percent: DecimalString, effectiveFrom: Date, effectiveTo: Date?, reason: String
    let status: String, proposedBy: UUID?, proposedAt: Date
    enum CodingKeys: String, CodingKey {
        case id, percent, reason, status, customerID = "customer_id", effectiveFrom = "effective_from"
        case effectiveTo = "effective_to", proposedBy = "proposed_by", proposedAt = "proposed_at"
    }
}

struct CreditArrangementDTO: Codable, Sendable {
    let id: UUID, customerID: UUID, limitAmount: DecimalString, currency: String, effectiveFrom: Date, effectiveTo: Date?
    let terms: String?, reason: String, status: String, proposedBy: UUID?, proposedAt: Date
    enum CodingKeys: String, CodingKey {
        case id, currency, terms, reason, status, customerID = "customer_id", limitAmount = "limit_amount"
        case effectiveFrom = "effective_from", effectiveTo = "effective_to", proposedBy = "proposed_by", proposedAt = "proposed_at"
    }
}

struct HoursTransferDTO: Codable, Sendable {
    let id: UUID, purchaseID: UUID, fromMachineID: UUID, toMachineID: UUID, hours: DecimalString, reason: String
    let status: String, requestedBy: UUID?, requestedAt: Date
    enum CodingKeys: String, CodingKey {
        case id, hours, reason, status, purchaseID = "purchase_id", fromMachineID = "from_machine_id"
        case toMachineID = "to_machine_id", requestedBy = "requested_by", requestedAt = "requested_at"
    }
}

struct CancellationDTO: Codable, Sendable {
    let id: UUID, purchaseID: UUID, reason: String, status: String, requestedBy: UUID?, requestedAt: Date
    enum CodingKeys: String, CodingKey {
        case id, reason, status, purchaseID = "purchase_id", requestedBy = "requested_by", requestedAt = "requested_at"
    }
}

struct BaselineDTO: Codable, Sendable {
    let id: UUID, machineID: UUID, machineCode: String?, machineName: String?, reading: DecimalString, capturedAt: Date
    let source: String, photoAttachmentID: UUID?, note: String?, status: String, proposedBy: UUID?, proposedByName: String?
    let proposedAt: Date
    enum CodingKeys: String, CodingKey {
        case id, reading, source, note, status, machineID = "machine_id", machineCode = "machine_code"
        case machineName = "machine_name", capturedAt = "captured_at", photoAttachmentID = "photo_attachment_id"
        case proposedBy = "proposed_by", proposedByName = "proposed_by_name", proposedAt = "proposed_at"
    }
}

struct ClassificationDTO: Codable, Sendable {
    let id: UUID, machineID: UUID, machineCode: String?, startAt: Date, endAt: Date, hours: DecimalString, outcome: String
    let reasonName: String?, note: String, status: String, proposedBy: UUID?, proposedByName: String?, proposedAt: Date
    enum CodingKeys: String, CodingKey {
        case id, hours, outcome, note, status, machineID = "machine_id", machineCode = "machine_code", startAt = "start_at"
        case endAt = "end_at", reasonName = "reason_name", proposedBy = "proposed_by", proposedByName = "proposed_by_name"
        case proposedAt = "proposed_at"
    }
}

struct CorrectionDTO: Codable, Sendable {
    let id: UUID, machineID: UUID, machineCode: String?, oldReading: DecimalString, newReading: DecimalString, reason: String
    let status: String, proposedBy: UUID?, proposedByName: String?, proposedAt: Date
    enum CodingKeys: String, CodingKey {
        case id, reason, status, machineID = "machine_id", machineCode = "machine_code", oldReading = "old_reading"
        case newReading = "new_reading", proposedBy = "proposed_by", proposedByName = "proposed_by_name"
        case proposedAt = "proposed_at"
    }
}

struct CashVarianceDTO: Codable, Sendable {
    let id: UUID, sourceType: String, currency: String, declaredAmount: DecimalString, receivedAmount: DecimalString
    let amount: DecimalString, status: String, proposedBy: UUID?, proposedAt: Date?, proposalNote: String?, openedAt: Date
    enum CodingKeys: String, CodingKey {
        case id, currency, amount, status, sourceType = "source_type", declaredAmount = "declared_amount"
        case receivedAmount = "received_amount", proposedBy = "proposed_by", proposedAt = "proposed_at"
        case proposalNote = "proposal_note", openedAt = "opened_at"
    }
}

struct CustodyAdjustmentDTO: Codable, Sendable {
    let id: UUID, kind: String, amount: DecimalString, currency: String, occurredAt: Date, reason: String, status: String
    let createdBy: UUID?, createdAt: Date
    enum CodingKeys: String, CodingKey {
        case id, kind, amount, currency, reason, status, occurredAt = "occurred_at", createdBy = "created_by"
        case createdAt = "created_at"
    }
}

extension PendingDecision {
    typealias T = OwnerAccountabilityTexts

    /// Normalizes one server record of `kind` (nil when it does not decode).
    public static func from(_ json: JSONValue, kind: DecisionKind, timeZone: TimeZone = .current) -> PendingDecision? {
        func stamp(_ date: Date) -> String { OwnerFormat.stamp(date, timeZone: timeZone) }
        func money(_ amount: DecimalString, _ currency: String) -> String { OwnerFormat.money(amount, currency: currency) }
        switch kind {
        case .discount:
            guard let d = try? json.decode(as: DiscountDTO.self) else { return nil }
            return PendingDecision(kind: kind, recordID: d.id, headline: T.rowDiscount(d.percent.description), status: d.status,
                                   proposedBy: d.proposedBy, proposedByName: nil, proposedAt: d.proposedAt, reason: d.reason,
                                   fields: [DecisionField(label: T.fieldDiscount, value: "\(d.percent.description)%"),
                                            DecisionField(label: T.fieldEffectiveFrom, value: stamp(d.effectiveFrom))]
                                       + (d.effectiveTo.map { [DecisionField(label: T.fieldEffectiveTo, value: stamp($0))] } ?? []),
                                   machineID: nil, photoAttachmentID: nil)
        case .credit:
            guard let c = try? json.decode(as: CreditArrangementDTO.self) else { return nil }
            var fields = [DecisionField(label: T.fieldCreditLimit, value: money(c.limitAmount, c.currency)),
                          DecisionField(label: T.fieldEffectiveFrom, value: stamp(c.effectiveFrom))]
            if let to = c.effectiveTo { fields.append(DecisionField(label: T.fieldEffectiveTo, value: stamp(to))) }
            if let terms = c.terms, !terms.isEmpty { fields.append(DecisionField(label: T.fieldTerms, value: terms)) }
            return PendingDecision(kind: kind, recordID: c.id, headline: T.rowCredit(money(c.limitAmount, c.currency)),
                                   status: c.status, proposedBy: c.proposedBy, proposedByName: nil, proposedAt: c.proposedAt,
                                   reason: c.reason, fields: fields, machineID: nil, photoAttachmentID: nil)
        case .hoursTransfer:
            guard let t = try? json.decode(as: HoursTransferDTO.self) else { return nil }
            return PendingDecision(kind: kind, recordID: t.id, headline: T.rowHoursTransfer(OwnerFormat.hours(t.hours)),
                                   status: t.status, proposedBy: t.requestedBy, proposedByName: nil, proposedAt: t.requestedAt,
                                   reason: t.reason, fields: [DecisionField(label: T.fieldHours, value: OwnerFormat.hours(t.hours))],
                                   machineID: t.fromMachineID, photoAttachmentID: nil)
        case .cancellation:
            guard let c = try? json.decode(as: CancellationDTO.self) else { return nil }
            return PendingDecision(kind: kind, recordID: c.id, headline: T.rowCancellation, status: c.status,
                                   proposedBy: c.requestedBy, proposedByName: nil, proposedAt: c.requestedAt, reason: c.reason,
                                   fields: [], machineID: nil, photoAttachmentID: nil)
        case .baseline:
            guard let b = try? json.decode(as: BaselineDTO.self) else { return nil }
            let machine = b.machineCode ?? b.machineName ?? ""
            var fields = [DecisionField(label: T.fieldMachine, value: [b.machineCode, b.machineName].compactMap { $0 }.joined(separator: " · ")),
                          DecisionField(label: T.fieldReading, value: OwnerFormat.hours(b.reading)),
                          DecisionField(label: T.fieldSource, value: OwnerFormat.humanize(b.source))]
            if let note = b.note, !note.isEmpty { fields.append(DecisionField(label: T.fieldNote, value: note)) }
            return PendingDecision(kind: kind, recordID: b.id, headline: T.rowBaseline(reading: b.reading.description, machine: machine),
                                   status: b.status, proposedBy: b.proposedBy, proposedByName: b.proposedByName,
                                   proposedAt: b.proposedAt, reason: nil, fields: fields, machineID: b.machineID,
                                   photoAttachmentID: b.photoAttachmentID)
        case .classification:
            guard let c = try? json.decode(as: ClassificationDTO.self) else { return nil }
            let category = c.reasonName ?? OwnerFormat.humanize(c.outcome)
            return PendingDecision(
                kind: kind, recordID: c.id, headline: T.rowClassification(hours: c.hours.description, category: category),
                status: c.status, proposedBy: c.proposedBy, proposedByName: c.proposedByName, proposedAt: c.proposedAt,
                reason: c.note,
                fields: [DecisionField(label: T.fieldMachine, value: c.machineCode ?? ""),
                         DecisionField(label: T.fieldHours, value: OwnerFormat.hours(c.hours)),
                         DecisionField(label: T.fieldPeriod, value: "\(stamp(c.startAt)) – \(stamp(c.endAt))"),
                         DecisionField(label: T.fieldOutcome, value: T.outcome(c.outcome)),
                         DecisionField(label: T.fieldCategory, value: category)],
                machineID: c.machineID, photoAttachmentID: nil)
        case .correction:
            guard let c = try? json.decode(as: CorrectionDTO.self) else { return nil }
            return PendingDecision(
                kind: kind, recordID: c.id,
                headline: T.rowCorrection(old: c.oldReading.description, new: c.newReading.description, machine: c.machineCode ?? ""),
                status: c.status, proposedBy: c.proposedBy, proposedByName: c.proposedByName, proposedAt: c.proposedAt,
                reason: c.reason,
                fields: [DecisionField(label: T.fieldMachine, value: c.machineCode ?? ""),
                         DecisionField(label: T.fieldOldReading, value: OwnerFormat.hours(c.oldReading)),
                         DecisionField(label: T.fieldNewReading, value: OwnerFormat.hours(c.newReading))],
                machineID: c.machineID, photoAttachmentID: nil)
        case .writeOff:
            guard let v = try? json.decode(as: CashVarianceDTO.self) else { return nil }
            return PendingDecision(
                kind: kind, recordID: v.id, headline: T.rowWriteOff(money(v.amount, v.currency)), status: v.status,
                proposedBy: v.proposedBy, proposedByName: nil, proposedAt: v.proposedAt ?? v.openedAt, reason: v.proposalNote,
                fields: [DecisionField(label: T.fieldSource, value: OwnerFormat.humanize(v.sourceType)),
                         DecisionField(label: T.fieldDeclared, value: money(v.declaredAmount, v.currency)),
                         DecisionField(label: T.fieldReceived, value: money(v.receivedAmount, v.currency)),
                         DecisionField(label: T.fieldDifference, value: money(v.amount, v.currency))],
                machineID: nil, photoAttachmentID: nil)
        case .retention:
            guard let r = try? json.decode(as: CashRetentionDTO.self) else { return nil }
            var fields = [DecisionField(label: T.fieldAmount, value: money(r.amount, r.currency))]
            if let until = r.validUntil { fields.append(DecisionField(label: T.fieldValidUntil, value: stamp(until))) }
            return PendingDecision(kind: kind, recordID: r.id, headline: T.rowRetention(money(r.amount, r.currency)),
                                   status: r.status, proposedBy: r.createdBy, proposedByName: nil, proposedAt: r.createdAt,
                                   reason: r.reason, fields: fields, machineID: nil, photoAttachmentID: nil)
        case .adjustment:
            guard let a = try? json.decode(as: CustodyAdjustmentDTO.self) else { return nil }
            return PendingDecision(
                kind: kind, recordID: a.id, headline: T.rowAdjustment(kind: OwnerFormat.humanize(a.kind), money: money(a.amount, a.currency)),
                status: a.status, proposedBy: a.createdBy, proposedByName: nil, proposedAt: a.createdAt, reason: a.reason,
                fields: [DecisionField(label: T.fieldKind, value: OwnerFormat.humanize(a.kind)),
                         DecisionField(label: T.fieldAmount, value: money(a.amount, a.currency))],
                machineID: nil, photoAttachmentID: nil)
        }
    }

    public static func list(_ page: Page<JSONValue>, kind: DecisionKind) -> [PendingDecision] {
        page.items.compactMap { from($0, kind: kind) }
    }
}

extension SnapshotKey {
    /// A kind's decisions waiting for a decision (`pendingOnly`) or the latest of any status.
    public static func decisions(_ kind: DecisionKind, pendingOnly: Bool) -> SnapshotKey {
        SnapshotKey("decisions.\(kind.rawValue).\(pendingOnly ? "PENDING" : "ALL")")
    }

    public static let accountability = SnapshotKey("accountability.summary")
}

extension OwnerAPI {
    /// The records of `kind`, newest first: waiting ones (`pendingOnly`) or the latest of any status.
    public static func decisions(_ kind: DecisionKind, pendingOnly: Bool, pageSize: Int = 100) -> APIRequest<Page<JSONValue>> {
        .get("\(tenant)/\(kind.list.path)", query: paging(1, pageSize) + compact([
            ("status", pendingOnly ? kind.list.pendingStatus : nil),
        ]))
    }

    /// Approves or rejects one record. Meter kinds need a note of 5+ characters; others take an optional note.
    public static func decide(_ kind: DecisionKind, id: UUID, approve: Bool, note: String,
                              idempotencyKey: UUID) throws -> APIRequest<JSONValue> {
        let text = note.trimmingCharacters(in: .whitespacesAndNewlines)
        if kind.usesMeterDecision {
            return try .mutation(.post, "\(tenant)/\(kind.decisionPath(id))",
                                 body: MeterDecisionIn(decision: approve ? "APPROVE" : "REJECT", note: text),
                                 idempotencyKey: idempotencyKey)
        }
        return try .mutation(.post, "\(tenant)/\(kind.decisionPath(id))",
                             body: DecisionIn(approve: approve, note: text.isEmpty ? nil : text), idempotencyKey: idempotencyKey)
    }

    /// `GET /tenant/accountability/summary`.
    public static func accountabilitySummary() -> APIRequest<AccountabilitySummaryDTO> { .get("\(tenant)/accountability/summary") }
}

/// Input rules of a decision (as Android `DecisionRules`).
public enum DecisionRules {
    public static let meterNoteMin = 5, meterNoteMax = 2000, noteMax = 1000

    /// Meter kinds: a note of 5..2000 characters either way. Others: optional to approve, required to reject (<= 1000).
    public static func canDecide(_ kind: DecisionKind, approve: Bool, note: String) -> Bool {
        let n = note.trimmingCharacters(in: .whitespacesAndNewlines).count
        if kind.usesMeterDecision { return n >= meterNoteMin && n <= meterNoteMax }
        return n <= noteMax && (approve || n > 0)
    }

    public static func noteLabel(_ kind: DecisionKind) -> String {
        kind.usesMeterDecision ? OwnerAccountabilityTexts.decisionNoteRequired : OwnerAccountabilityTexts.decisionNoteOptional
    }

    /// Codes after which the record must be reloaded (someone else decided it).
    public static func needsReload(_ error: any Error) -> Bool {
        guard let code = (error as? APIError)?.code else { return false }
        return code.hasSuffix("ALREADY_DECIDED") || code == "NOT_PENDING" || code == "WRITEOFF_NOT_PROPOSED"
            || code == "VARIANCE_NOT_OPEN" || code == "STALE_VERSION"
    }

    public static func message(for error: any Error) -> String {
        if (error as? APIError)?.code == "SEGREGATION_OF_DUTIES" { return OwnerAccountabilityTexts.decisionOwnRequest }
        if needsReload(error) { return "\(OwnerAccountabilityTexts.decisionNotFoundTitle). \(OwnerAccountabilityTexts.decisionNotFoundMessage)" }
        return DecisionErrorText.message(for: error)
    }
}
