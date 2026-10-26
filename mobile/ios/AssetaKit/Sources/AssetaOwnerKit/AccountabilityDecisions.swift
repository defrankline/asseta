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
    /// DEC-031: non-revenue time inside a job (e.g. movement) explained by one person, approved by another.
    case nonRevenue

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
        case .nonRevenue: ("non-revenue-approvals", "PROPOSED")
        }
    }

    /// `POST` path of the decision.
    func decisionPath(_ id: UUID) -> String {
        let record = "\(list.path)/\(id.lowercased)"
        return self == .writeOff ? "\(record)/write-off-decision" : "\(record)/decision"
    }

    /// Meter decisions (and `NonRevenueDecisionIn`, the same shape) take `MeterDecisionIn` (note required, 5+
    /// characters); the others `DecisionIn`.
    public var usesMeterDecision: Bool { [.baseline, .classification, .correction, .nonRevenue].contains(self) }

    /// The permission that lists this kind (as the server's list endpoint).
    public var readPermissions: [String] {
        switch self {
        case .discount, .credit, .hoursTransfer, .cancellation: ["tenant.hours.read"]
        case .baseline, .classification, .correction: ["tenant.meter.read"]
        case .writeOff, .adjustment: ["tenant.finance.read"]
        case .retention: ["tenant.collection.record", "tenant.finance.read"]
        case .nonRevenue: [RevenuePermission.read]
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
        case .nonRevenue: RevenuePermission.decide
        }
    }

    /// The tenant capability a policy can switch off for this kind (`/me` `disabled_capabilities`).
    public var capability: String? {
        switch self {
        case .discount, .credit, .hoursTransfer, .cancellation: TenantCapability.customerHours
        case .baseline, .correction, .classification: TenantCapability.engineHours
        case .writeOff, .retention, .adjustment: TenantCapability.cashCustody
        case .nonRevenue: TenantCapability.revenueReconciliation
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
        case .nonRevenue: RevenueTexts.sectionNonRevenue
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
        case .nonRevenue: RevenueTexts.sectionNonRevenueEmpty
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
        case .nonRevenue: RevenueTexts.titleNonRevenue
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
        case "non_revenue_approval": self = .nonRevenue
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

// Every `*_name` beside an id is nullable (older servers send none): the app shows the name, else a short id.

struct DiscountDTO: Codable, Sendable {
    let id: UUID, customerID: UUID, percent: DecimalString, effectiveFrom: Date, effectiveTo: Date?, reason: String
    let status: String, proposedBy: UUID?, proposedAt: Date
    let customerName: String?, proposedByName: String?, decidedByName: String?, decidedBy: UUID?, decisionNote: String?
    enum CodingKeys: String, CodingKey {
        case decidedBy = "decided_by", decisionNote = "decision_note"
        case customerName = "customer_name", proposedByName = "proposed_by_name", decidedByName = "decided_by_name"
        case id, percent, reason, status, customerID = "customer_id", effectiveFrom = "effective_from"
        case effectiveTo = "effective_to", proposedBy = "proposed_by", proposedAt = "proposed_at"
    }
}

struct CreditArrangementDTO: Codable, Sendable {
    let id: UUID, customerID: UUID, limitAmount: DecimalString, currency: String, effectiveFrom: Date, effectiveTo: Date?
    let terms: String?, reason: String, status: String, proposedBy: UUID?, proposedAt: Date
    let customerName: String?, proposedByName: String?, decidedByName: String?, decidedBy: UUID?, decisionNote: String?
    enum CodingKeys: String, CodingKey {
        case decidedBy = "decided_by", decisionNote = "decision_note"
        case customerName = "customer_name", proposedByName = "proposed_by_name", decidedByName = "decided_by_name"
        case id, currency, terms, reason, status, customerID = "customer_id", limitAmount = "limit_amount"
        case effectiveFrom = "effective_from", effectiveTo = "effective_to", proposedBy = "proposed_by", proposedAt = "proposed_at"
    }
}

struct HoursTransferDTO: Codable, Sendable {
    let id: UUID, purchaseID: UUID, fromMachineID: UUID, toMachineID: UUID, hours: DecimalString, reason: String
    let status: String, requestedBy: UUID?, requestedAt: Date
    let customerName: String?, purchaseNumber: String?, fromMachineName: String?, toMachineName: String?
    let requestedByName: String?, decidedByName: String?, fromMachineCode: String?, toMachineCode: String?, decidedBy: UUID?, decisionNote: String?
    enum CodingKeys: String, CodingKey {
        case fromMachineCode = "from_machine_code", toMachineCode = "to_machine_code", decidedBy = "decided_by", decisionNote = "decision_note"
        case customerName = "customer_name", purchaseNumber = "purchase_number", fromMachineName = "from_machine_name"
        case toMachineName = "to_machine_name", requestedByName = "requested_by_name", decidedByName = "decided_by_name"
        case id, hours, reason, status, purchaseID = "purchase_id", fromMachineID = "from_machine_id"
        case toMachineID = "to_machine_id", requestedBy = "requested_by", requestedAt = "requested_at"
    }
}

struct CancellationDTO: Codable, Sendable {
    let id: UUID, purchaseID: UUID, reason: String, status: String, requestedBy: UUID?, requestedAt: Date
    let customerName: String?, purchaseNumber: String?, requestedByName: String?, decidedByName: String?, decidedBy: UUID?, decisionNote: String?
    enum CodingKeys: String, CodingKey {
        case decidedBy = "decided_by", decisionNote = "decision_note"
        case customerName = "customer_name", purchaseNumber = "purchase_number", requestedByName = "requested_by_name"
        case decidedByName = "decided_by_name"
        case id, reason, status, purchaseID = "purchase_id", requestedBy = "requested_by", requestedAt = "requested_at"
    }
}

struct BaselineDTO: Codable, Sendable {
    let id: UUID, machineID: UUID, machineCode: String?, machineName: String?, reading: DecimalString, capturedAt: Date
    let source: String, photoAttachmentID: UUID?, note: String?, status: String, proposedBy: UUID?, proposedByName: String?
    let proposedAt: Date, decidedByName: String?, decidedBy: UUID?, decisionNote: String?
    enum CodingKeys: String, CodingKey {
        case decidedByName = "decided_by_name", decidedBy = "decided_by", decisionNote = "decision_note"
        case id, reading, source, note, status, machineID = "machine_id", machineCode = "machine_code"
        case machineName = "machine_name", capturedAt = "captured_at", photoAttachmentID = "photo_attachment_id"
        case proposedBy = "proposed_by", proposedByName = "proposed_by_name", proposedAt = "proposed_at"
    }
}

struct ClassificationDTO: Codable, Sendable {
    let id: UUID, machineID: UUID, machineCode: String?, startAt: Date, endAt: Date, hours: DecimalString, outcome: String
    let reasonName: String?, note: String, status: String, proposedBy: UUID?, proposedByName: String?, proposedAt: Date
    let machineName: String?, decidedByName: String?, decidedBy: UUID?, decisionNote: String?
    enum CodingKeys: String, CodingKey {
        case machineName = "machine_name", decidedByName = "decided_by_name", decidedBy = "decided_by", decisionNote = "decision_note"
        case id, hours, outcome, note, status, machineID = "machine_id", machineCode = "machine_code", startAt = "start_at"
        case endAt = "end_at", reasonName = "reason_name", proposedBy = "proposed_by", proposedByName = "proposed_by_name"
        case proposedAt = "proposed_at"
    }
}

struct CorrectionDTO: Codable, Sendable {
    let id: UUID, machineID: UUID, machineCode: String?, oldReading: DecimalString, newReading: DecimalString, reason: String
    let status: String, proposedBy: UUID?, proposedByName: String?, proposedAt: Date
    let machineName: String?, jobNumber: String?, decidedByName: String?, jobID: UUID?, decidedBy: UUID?, decisionNote: String?
    enum CodingKeys: String, CodingKey {
        case machineName = "machine_name", jobNumber = "job_number", decidedByName = "decided_by_name", jobID = "job_id", decidedBy = "decided_by", decisionNote = "decision_note"
        case id, reason, status, machineID = "machine_id", machineCode = "machine_code", oldReading = "old_reading"
        case newReading = "new_reading", proposedBy = "proposed_by", proposedByName = "proposed_by_name"
        case proposedAt = "proposed_at"
    }
}

struct CashVarianceDTO: Codable, Sendable {
    let id: UUID, sourceType: String, currency: String, declaredAmount: DecimalString, receivedAmount: DecimalString
    let amount: DecimalString, status: String, proposedBy: UUID?, proposedAt: Date?, proposalNote: String?, openedAt: Date
    let staffMemberID: UUID?, staffMemberName: String?, counterpartyStaffName: String?, proposedByName: String?
    let counterpartyStaffID: UUID?, resolvedBy: UUID?, resolvedByName: String?, resolutionNote: String?
    /// SHORTFALL / SURPLUS (DEC-031); nil from older servers.
    let kind: String?
    /// More received than declared ("Surplus to explain"); without a kind a negative amount means the same.
    var isSurplus: Bool { kind == "SURPLUS" || (kind == nil && amount.value < 0) }
    enum CodingKeys: String, CodingKey {
        case kind
        case counterpartyStaffID = "counterparty_staff_id", resolvedBy = "resolved_by", resolvedByName = "resolved_by_name"
        case resolutionNote = "resolution_note"
        case staffMemberID = "staff_member_id", staffMemberName = "staff_member_name"
        case counterpartyStaffName = "counterparty_staff_name", proposedByName = "proposed_by_name"
        case id, currency, amount, status, sourceType = "source_type", declaredAmount = "declared_amount"
        case receivedAmount = "received_amount", proposedBy = "proposed_by", proposedAt = "proposed_at"
        case proposalNote = "proposal_note", openedAt = "opened_at"
    }
}

struct CustodyAdjustmentDTO: Codable, Sendable {
    let id: UUID, kind: String, amount: DecimalString, currency: String, occurredAt: Date, reason: String, status: String
    let createdBy: UUID?, createdAt: Date
    let staffMemberID: UUID?, staffMemberName: String?, createdByName: String?, decidedByName: String?, decisionNote: String?
    let decidedBy: UUID?
    enum CodingKeys: String, CodingKey {
        case decidedBy = "decided_by"
        case staffMemberID = "staff_member_id", staffMemberName = "staff_member_name", createdByName = "created_by_name"
        case decidedByName = "decided_by_name", decisionNote = "decision_note"
        case id, kind, amount, currency, reason, status, occurredAt = "occurred_at", createdBy = "created_by"
        case createdAt = "created_at"
    }
}

extension PendingDecision {
    typealias T = OwnerAccountabilityTexts

    /// Labelled values, skipping empty ones (as Android `DecisionMapper.fields`).
    static func fields(_ pairs: [(String, String?)]) -> [DecisionField] {
        pairs.compactMap { label, value in
            guard let value, !value.trimmingCharacters(in: .whitespaces).isEmpty else { return nil }
            return DecisionField(label: label, value: value)
        }
    }

    /// Plain number ("4521", "12.5").
    static func num(_ value: DecimalString) -> String {
        value.value.formatted(.number.precision(.fractionLength(0...2)).grouping(.never).locale(Locale(identifier: "en_US_POSIX")))
    }

    /// Normalizes one server record of `kind` (nil when it does not decode). Names come from the server's `*_name`
    /// fields; only when one is null the short id stands in (`DisplayName`). Same labels and order as Android
    /// `DecisionMapper`.
    public static func from(_ json: JSONValue, kind: DecisionKind,
                            timeZone: TimeZone = .current) -> PendingDecision? {
        func date(_ d: Date) -> String { OwnerFormat.stamp(d, timeZone: timeZone) }
        func money(_ amount: DecimalString, _ currency: String) -> String { OwnerFormat.money(amount, currency: currency) }
        /// A person or record: the name, else the short id, else nothing (the field is skipped).
        func who(_ name: String?, _ id: UUID?) -> String? { DisplayName.optional(name, id: id) }
        func item(_ id: UUID, _ headline: String, _ reason: String?, _ at: Date, _ by: UUID?, _ status: String,
                  _ fields: [DecisionField], machine: UUID? = nil, photo: UUID? = nil, name: String? = nil) -> PendingDecision {
            PendingDecision(kind: kind, recordID: id, headline: headline, status: status, proposedBy: by,
                            proposedByName: who(name, by), proposedAt: at, reason: reason, fields: fields, machineID: machine,
                            photoAttachmentID: photo)
        }
        /// Decided by (name, else short id) and the decision note, as Android `DecisionMapper.decided`.
        func decided(_ name: String?, _ id: UUID?, _ note: String?) -> [(String, String?)] {
            [(T.fieldDecidedBy, who(name, id)), (T.fieldDecisionNote, note)]
        }
        switch kind {
        case .discount:
            guard let d = try? json.decode(as: DiscountDTO.self) else { return nil }
            return item(d.id, T.rowDiscount(num(d.percent)), d.reason, d.proposedAt, d.proposedBy, d.status,
                        fields([(T.fieldCustomer, who(d.customerName, d.customerID)), (T.fieldDiscount, "\(num(d.percent))%"),
                                (T.fieldEffectiveFrom, date(d.effectiveFrom)), (T.fieldEffectiveTo, d.effectiveTo.map(date)),
                                (T.fieldProposedBy, who(d.proposedByName, d.proposedBy))]
                               + decided(d.decidedByName, d.decidedBy, d.decisionNote)),
                        name: d.proposedByName)
        case .credit:
            guard let c = try? json.decode(as: CreditArrangementDTO.self) else { return nil }
            return item(c.id, T.rowCredit(money(c.limitAmount, c.currency)), c.reason, c.proposedAt, c.proposedBy, c.status,
                        fields([(T.fieldCustomer, who(c.customerName, c.customerID)),
                                (T.fieldCreditLimit, money(c.limitAmount, c.currency)), (T.fieldTerms, c.terms),
                                (T.fieldEffectiveFrom, date(c.effectiveFrom)), (T.fieldEffectiveTo, c.effectiveTo.map(date)),
                                (T.fieldProposedBy, who(c.proposedByName, c.proposedBy))]
                               + decided(c.decidedByName, c.decidedBy, c.decisionNote)),
                        name: c.proposedByName)
        case .hoursTransfer:
            guard let t = try? json.decode(as: HoursTransferDTO.self) else { return nil }
            return item(t.id, T.rowHoursTransfer(num(t.hours)), t.reason, t.requestedAt, t.requestedBy, t.status,
                        fields([(T.fieldCustomer, t.customerName), (T.fieldPurchase, who(t.purchaseNumber, t.purchaseID)),
                                (T.fieldHours, num(t.hours)),
                                (T.fieldFromMachine, DisplayName.machine(code: t.fromMachineCode, name: t.fromMachineName, id: t.fromMachineID)),
                                (T.fieldToMachine, DisplayName.machine(code: t.toMachineCode, name: t.toMachineName, id: t.toMachineID)),
                                (T.fieldRequestedBy, who(t.requestedByName, t.requestedBy))]
                               + decided(t.decidedByName, t.decidedBy, t.decisionNote)),
                        machine: t.fromMachineID, name: t.requestedByName)
        case .cancellation:
            guard let c = try? json.decode(as: CancellationDTO.self) else { return nil }
            return item(c.id, T.rowCancellation, c.reason, c.requestedAt, c.requestedBy, c.status,
                        fields([(T.fieldCustomer, c.customerName), (T.fieldPurchase, who(c.purchaseNumber, c.purchaseID)),
                                (T.fieldRequestedBy, who(c.requestedByName, c.requestedBy))]
                               + decided(c.decidedByName, c.decidedBy, c.decisionNote)),
                        name: c.requestedByName)
        case .baseline:
            guard let b = try? json.decode(as: BaselineDTO.self) else { return nil }
            return item(b.id, T.rowBaseline(reading: num(b.reading), machine: b.machineCode ?? b.machineName ?? DisplayName.shortID(b.machineID)),
                        b.note, b.proposedAt, b.proposedBy, b.status,
                        fields([(T.fieldMachine, DisplayName.machine(code: b.machineCode, name: b.machineName, id: b.machineID)),
                                (T.fieldReading, num(b.reading)), (T.fieldProposedBy, who(b.proposedByName, b.proposedBy)),
                                (T.fieldCaptured, date(b.capturedAt))]
                               + decided(b.decidedByName, b.decidedBy, b.decisionNote)),
                        machine: b.machineID, photo: b.photoAttachmentID, name: b.proposedByName)
        case .classification:
            guard let c = try? json.decode(as: ClassificationDTO.self) else { return nil }
            return item(c.id, T.rowClassification(hours: num(c.hours), category: c.reasonName ?? OwnerFormat.humanize(c.outcome)),
                        c.note, c.proposedAt, c.proposedBy, c.status,
                        fields([(T.fieldMachine, DisplayName.machine(code: c.machineCode, name: c.machineName, id: c.machineID)),
                                (T.fieldHours, num(c.hours)), (T.fieldPeriod, "\(date(c.startAt)) – \(date(c.endAt))"),
                                (T.fieldCategory, c.reasonName), (T.fieldOutcome, T.outcome(c.outcome)),
                                (T.fieldProposedBy, who(c.proposedByName, c.proposedBy))]
                               + decided(c.decidedByName, c.decidedBy, c.decisionNote)),
                        machine: c.machineID, name: c.proposedByName)
        case .correction:
            guard let c = try? json.decode(as: CorrectionDTO.self) else { return nil }
            return item(c.id, T.rowCorrection(old: num(c.oldReading), new: num(c.newReading),
                                              machine: c.machineCode ?? c.machineName ?? DisplayName.shortID(c.machineID)),
                        c.reason, c.proposedAt, c.proposedBy, c.status,
                        fields([(T.fieldMachine, DisplayName.machine(code: c.machineCode, name: c.machineName, id: c.machineID)),
                                (T.fieldJob, who(c.jobNumber, c.jobID)), (T.fieldOldReading, num(c.oldReading)),
                                (T.fieldNewReading, num(c.newReading)), (T.fieldProposedBy, who(c.proposedByName, c.proposedBy))]
                               + decided(c.decidedByName, c.decidedBy, c.decisionNote)),
                        machine: c.machineID, name: c.proposedByName)
        case .writeOff:
            guard let v = try? json.decode(as: CashVarianceDTO.self) else { return nil }
            // A surplus (more received than declared) reads "Surplus to explain" with the positive amount.
            let difference = v.isSurplus ? money(DecimalString(abs(v.amount.value)), v.currency) : money(v.amount, v.currency)
            return item(v.id, v.isSurplus ? T.rowSurplus(difference) : T.rowWriteOff(difference), v.proposalNote,
                        v.proposedAt ?? v.openedAt, v.proposedBy, v.status,
                        fields([(T.fieldCustodian, who(v.staffMemberName, v.staffMemberID)),
                                (T.fieldCounterparty, who(v.counterpartyStaffName, v.counterpartyStaffID)),
                                (T.fieldSource, OwnerFormat.humanize(v.sourceType)), (T.fieldDeclared, money(v.declaredAmount, v.currency)),
                                (T.fieldReceived, money(v.receivedAmount, v.currency)),
                                (v.isSurplus ? T.varianceSurplus : T.fieldDifference, difference),
                                (T.fieldProposedBy, who(v.proposedByName, v.proposedBy))]
                               + decided(v.resolvedByName, v.resolvedBy, v.resolutionNote)),
                        name: v.proposedByName)
        case .retention:
            guard let r = try? json.decode(as: CashRetentionDTO.self) else { return nil }
            return item(r.id, T.rowRetention(money(r.amount, r.currency)), r.reason, r.createdAt, r.createdBy, r.status,
                        fields([(T.fieldCustodian, who(r.staffMemberName, r.staffMemberID)), (T.fieldAmount, money(r.amount, r.currency)),
                                (T.fieldValidUntil, r.validUntil.map(date)), (T.fieldRequestedBy, who(r.createdByName, r.createdBy))]
                               + decided(r.decidedByName, r.decidedBy, r.decisionNote)),
                        name: r.createdByName)
        case .adjustment:
            guard let a = try? json.decode(as: CustodyAdjustmentDTO.self) else { return nil }
            return item(a.id, T.rowAdjustment(kind: OwnerFormat.humanize(a.kind), money: money(a.amount, a.currency)), a.reason,
                        a.createdAt, a.createdBy, a.status,
                        fields([(T.fieldCustodian, who(a.staffMemberName, a.staffMemberID)), (T.fieldKind, OwnerFormat.humanize(a.kind)),
                                (T.fieldAmount, money(a.amount, a.currency)), (T.fieldWhen, date(a.occurredAt)),
                                (T.fieldProposedBy, who(a.createdByName, a.createdBy))]
                               + decided(a.decidedByName, a.decidedBy, a.decisionNote)),
                        name: a.createdByName)
        case .nonRevenue:
            guard let n = try? json.decode(as: NonRevenueApprovalDTO.self) else { return nil }
            let type = RevenueTexts.activityType(n.activityType)
            return item(n.id, RevenueTexts.rowNonRevenue(hours: num(n.hours), type: type,
                                                         machine: n.machineCode ?? n.machineName ?? DisplayName.shortID(n.machineID)),
                        n.reasonName ?? n.note, n.proposedAt, n.proposedBy, n.status,
                        fields([(T.fieldMachine, DisplayName.machine(code: n.machineCode, name: n.machineName, id: n.machineID)),
                                (T.fieldJob, who(n.jobNumber, n.jobID)), (RevenueTexts.nonRevType, type),
                                (RevenueTexts.nonRevTime, "\(date(n.startedAt)) – \(date(n.endedAt))"),
                                (RevenueTexts.nonRevHours, num(n.hours)), (RevenueTexts.reason, n.reasonName),
                                (RevenueTexts.note, n.note), (T.fieldProposedBy, who(n.proposedByName, n.proposedBy))]
                               + decided(n.decidedByName, n.decidedBy, n.decisionNote)),
                        machine: n.machineID, name: n.proposedByName)
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

    /// One decision record by id.
    public static func decision(_ kind: DecisionKind, id: UUID) -> SnapshotKey {
        SnapshotKey("decision.\(kind.rawValue).\(id.lowercased)")
    }
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

    /// One record of `kind` by id (exact-record links; works whatever its status).
    public static func decision(_ kind: DecisionKind, id: UUID) -> APIRequest<JSONValue> {
        .get("\(tenant)/\(kind.list.path)/\(id.lowercased)")
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
