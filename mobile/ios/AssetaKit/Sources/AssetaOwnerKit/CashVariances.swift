import AssetaModel
import AssetaNetwork
import AssetaStore // UUID.lowercased
import Foundation

/// `VarianceStatus` values the app acts on; the partial reason's "waiting" status.
public enum VarianceStatuses {
    public static let writeOffProposed = "WRITE_OFF_PROPOSED"
    public static let closureProposed = "CLOSURE_PROPOSED"
    public static let pendingReason = "PENDING"
}

/// Wording copied exactly from `docs/requirements/accountability-mobile-strings.md` (owner.partial.*, owner.closure.*,
/// owner.variance.*, owner.remit.*, owner.number).
public enum VarianceTexts {
    public static let number = "Number"
    public static let partialSection = "Partial remittance reasons"
    public static let partialEmpty = "No partial remittance reasons waiting."
    public static let partialTitle = "Partial remittance reason"
    public static func partialRow(amount: String, custodian: String) -> String { "\(amount) not remitted · \(custodian)" }
    public static let partialRemitted = "Remitted"
    public static let partialNotRemitted = "Not remitted"
    public static let closureSection = "Variance closures"
    public static let closureEmpty = "No variance closures waiting."
    public static let closureTitle = "Variance closure"
    public static func closureRow(difference: String, outcome: String) -> String { "Close \(difference) (\(outcome))" }
    public static let closureOutcome = "Proposed outcome"
    public static let varianceTitle = "Variance"
    public static let assignee = "Assigned to"
    public static let assignedBy = "Assigned by"
    public static let explanation = "Explanation"
    public static let explainedBy = "Explained by"
    public static let evidence = "Evidence"
    public static let history = "History"
    public static let check = "What was found"
    public static let customer = "Customer"
    public static let machine = "Machine"
    public static let purchase = "Purchase"
    public static let job = "Job"
    public static let unitHours = "Hours"
    public static let remitNumber = "Remittance number"
    public static let remitEvidence = "Evidence"
    public static let remitOutstanding = "Difference still open"
    public static let remitPartialReason = "Why part stayed with the custodian"
    public static let remitPartialStatus = "Reason status"
    public static let remitPartialReview = "Review the reason"

    public static func outcome(_ wire: String) -> String {
        switch wire {
        case "RECOVERED": "Recovered"
        case "CORRECTED_ERROR": "Corrected error"
        case "EXPLAINED": "Explained"
        case "WRITTEN_OFF": "Written off"
        default: OwnerFormat.humanize(wire)
        }
    }

    public static func checkText(_ wire: String) -> String {
        switch wire {
        case "PURCHASE_OVER_ACTIVATED": "Purchase over-activated"
        case "NEGATIVE_REMAINING": "Negative hours remaining"
        case "CONSUMPTION_MISMATCH": "Usage does not match records"
        case "ALLOCATION_MISMATCH": "Allocation does not match records"
        default: OwnerFormat.humanize(wire)
        }
    }

    public static func historyAction(_ wire: String) -> String {
        switch wire {
        case "OPENED": "Opened"
        case "ASSIGNED": "Assigned"
        case "EXPLAINED": "Explained"
        case "CLOSURE_PROPOSED": "Closure proposed"
        case "CLOSURE_APPROVED": "Closure approved"
        case "CLOSURE_REJECTED": "Closure rejected"
        case "WRITE_OFF_PROPOSED": "Write-off proposed"
        case "WRITE_OFF_APPROVED": "Write-off approved"
        case "WRITE_OFF_REJECTED": "Write-off rejected"
        case "RESOLVED": "Resolved"
        default: OwnerFormat.humanize(wire)
        }
    }

    public static func remitEvidenceText(_ wire: String) -> String {
        switch wire {
        case "DECLARED": "Declared by the field"
        case "SUPPORTED": "Supported by evidence"
        case "CONFIRMED": "Confirmed by the company"
        default: OwnerFormat.humanize(wire)
        }
    }

    /// owner.closure.error.*: nil for a code without its own wording.
    public static func closureError(_ code: String?) -> String? {
        switch code {
        case "SEGREGATION_OF_DUTIES": "You proposed this closure, so someone else must decide it."
        case "CLOSURE_NOT_PROPOSED": "This closure was already decided. Reload to see it."
        case "WRITEOFF_APPROVAL_REQUIRED": "A write-off needs its own approval."
        case "VARIANCE_OUTCOME_NOT_ALLOWED": "This outcome is not allowed for this variance."
        default: nil
        }
    }

    /// owner.partial.error.*: nil for a code without its own wording.
    public static func partialError(_ code: String?) -> String? {
        switch code {
        case "SEGREGATION_OF_DUTIES": "You recorded this remittance, so someone else must decide its reason."
        case "PARTIAL_APPROVAL_NOT_FOUND": "This reason was already decided. Reload to see it."
        default: nil
        }
    }
}

/// `CashVarianceDto`: a cash or customer-hour difference under investigation (DEC-032 Phase 3). Fields added after
/// DEC-031 are optional so a record from an older server still decodes.
public struct CashVarianceDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID, sourceType: String, currency: String, declaredAmount: DecimalString, receivedAmount: DecimalString
    public let amount: DecimalString, status: String, proposedBy: UUID?, proposedAt: Date?, proposalNote: String?, openedAt: Date
    public let staffMemberID: UUID?, staffMemberName: String?, counterpartyStaffName: String?, proposedByName: String?
    public let counterpartyStaffID: UUID?, resolvedBy: UUID?, resolvedByName: String?, resolutionNote: String?
    public let resolvedAt: Date?, outcome: String?, reasonID: UUID?, caseID: UUID?, sourceID: UUID?
    public let openedBy: UUID?, openedByName: String?
    /// SHORTFALL / SURPLUS (DEC-031); nil from older servers.
    public let kind: String?
    /// `MONEY` or `HOURS`; nil from older servers (money).
    public let unit: String?
    public let proposedOutcome: String?
    public let assigneeUserID: UUID?, assigneeUserName: String?, assignedBy: UUID?, assignedByName: String?, assignedAt: Date?
    public let explanation: String?, explainedBy: UUID?, explainedByName: String?, explainedAt: Date?
    public let evidenceAttachmentIDs: [UUID]?
    /// `PURCHASE_OVER_ACTIVATED`, `NEGATIVE_REMAINING`, `CONSUMPTION_MISMATCH`, `ALLOCATION_MISMATCH` (hours variances).
    public let checkCode: String?
    public let customerID: UUID?, customerName: String?, machineID: UUID?, machineCode: String?, machineName: String?
    public let purchaseID: UUID?, purchaseNumber: String?, jobID: UUID?, jobNumber: String?

    /// More received than declared ("Surplus to explain"); without a kind a negative amount means the same.
    public var isSurplus: Bool { kind == "SURPLUS" || (kind == nil && amount.value < 0) }
    public var isHours: Bool { unit == "HOURS" }
    public var evidence: [UUID] { evidenceAttachmentIDs ?? [] }

    enum CodingKeys: String, CodingKey {
        case kind, unit, outcome, explanation, id, currency, amount, status
        case counterpartyStaffID = "counterparty_staff_id", resolvedBy = "resolved_by", resolvedByName = "resolved_by_name"
        case resolutionNote = "resolution_note", resolvedAt = "resolved_at", reasonID = "reason_id", caseID = "case_id"
        case sourceID = "source_id", openedBy = "opened_by", openedByName = "opened_by_name"
        case staffMemberID = "staff_member_id", staffMemberName = "staff_member_name"
        case counterpartyStaffName = "counterparty_staff_name", proposedByName = "proposed_by_name"
        case sourceType = "source_type", declaredAmount = "declared_amount"
        case receivedAmount = "received_amount", proposedBy = "proposed_by", proposedAt = "proposed_at"
        case proposalNote = "proposal_note", openedAt = "opened_at", proposedOutcome = "proposed_outcome"
        case assigneeUserID = "assignee_user_id", assigneeUserName = "assignee_user_name", assignedBy = "assigned_by"
        case assignedByName = "assigned_by_name", assignedAt = "assigned_at", explainedBy = "explained_by"
        case explainedByName = "explained_by_name", explainedAt = "explained_at"
        case evidenceAttachmentIDs = "evidence_attachment_ids", checkCode = "check_code"
        case customerID = "customer_id", customerName = "customer_name", machineID = "machine_id", machineCode = "machine_code"
        case machineName = "machine_name", purchaseID = "purchase_id", purchaseNumber = "purchase_number"
        case jobID = "job_id", jobNumber = "job_number"
    }
}

/// `VarianceEventDto`: one step of a variance's history (`action` is a `VarianceEventAction`, kept as text).
public struct VarianceEventDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let action: String
    public let actorUserID: UUID?
    public let actorUserName: String?
    public let note: String?
    public let occurredAt: Date

    enum CodingKeys: String, CodingKey {
        case id, action, note, actorUserID = "actor_user_id", actorUserName = "actor_user_name", occurredAt = "occurred_at"
    }
}

/// `VarianceAssigneeDto`: someone a variance can be assigned to.
public struct VarianceAssigneeDTO: Codable, Hashable, Sendable, Identifiable {
    public let userID: UUID
    public let displayName: String
    public let email: String?
    public var id: UUID { userID }

    enum CodingKeys: String, CodingKey { case email, userID = "user_id", displayName = "display_name" }
}

/// `DecisionIn`: approve or reject a proposal (variance closure, partial remittance reason).
public struct ApproveDecisionIn: Encodable, Hashable, Sendable {
    public let approve: Bool
    public let note: String?

    public init(approve: Bool, note: String?) {
        self.approve = approve
        self.note = note
    }
}

struct VarianceAssignIn: Encodable, Sendable {
    let assigneeUserID: UUID
    enum CodingKeys: String, CodingKey { case assigneeUserID = "assignee_user_id" }
    func encode(to encoder: any Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(assigneeUserID.lowercased, forKey: .assigneeUserID)
    }
}

extension OwnerAPI {
    private static func variancePath(_ id: UUID) -> String { "\(tenant)/cash/variances/\(id.lowercased)" }

    public static func cashVariances(status: String? = nil, sourceType: String? = nil, assignee: UUID? = nil, page: Int = 1,
                                     pageSize: Int = 100) -> APIRequest<Page<CashVarianceDTO>> {
        .get("\(tenant)/cash/variances", query: paging(page, pageSize) + compact([
            ("status", status), ("source_type", sourceType), ("assignee_user_id", assignee?.lowercased),
        ]))
    }

    public static func cashVariance(_ id: UUID) -> APIRequest<CashVarianceDTO> { .get(variancePath(id)) }

    public static func cashVarianceHistory(_ id: UUID) -> APIRequest<[VarianceEventDTO]> { .get("\(variancePath(id))/history") }

    public static func varianceAssignees(query: String?) -> APIRequest<[VarianceAssigneeDTO]> {
        .get("\(tenant)/cash/variances/assignees", query: compact([("q", query.nonEmpty)]))
    }

    public static func assignVariance(_ id: UUID, to assignee: UUID, idempotencyKey: UUID) throws -> APIRequest<CashVarianceDTO> {
        try .mutation(.post, "\(variancePath(id))/assignment", body: VarianceAssignIn(assigneeUserID: assignee),
                      idempotencyKey: idempotencyKey)
    }

    public static func decideVarianceClosure(_ id: UUID, approve: Bool, note: String?,
                                             idempotencyKey: UUID) throws -> APIRequest<CashVarianceDTO> {
        try .mutation(.post, "\(variancePath(id))/closure-decision", body: ApproveDecisionIn(approve: approve, note: note.nonEmpty),
                      idempotencyKey: idempotencyKey)
    }

    /// Approves or rejects the reason given for a partial remittance (`tenant.finance.retention_approve`).
    public static func decidePartialReason(handoverID: UUID, approve: Bool, note: String?,
                                           idempotencyKey: UUID) throws -> APIRequest<CashHandoverDTO> {
        try .mutation(.post, "\(tenant)/cash/handovers/\(handoverID.lowercased)/partial-reason-decision",
                      body: ApproveDecisionIn(approve: approve, note: note.nonEmpty), idempotencyKey: idempotencyKey)
    }
}

extension DecisionKind {
    /// The kind a variance record is decided as: its own status wins, so opening a CLOSURE_PROPOSED variance from a
    /// notification decides the closure and a WRITE_OFF_PROPOSED one the write-off. Other kinds are unchanged.
    public func effective(varianceStatus status: String?) -> DecisionKind {
        guard self == .writeOff || self == .varianceClosure else { return self }
        switch status {
        case VarianceStatuses.closureProposed: return .varianceClosure
        case VarianceStatuses.writeOffProposed: return .writeOff
        default: return self
        }
    }

    /// The screen title of a variance by its status: the decision it waits for, else plain "Variance".
    public func varianceTitle(status: String?) -> String {
        switch status {
        case VarianceStatuses.closureProposed: VarianceTexts.closureTitle
        case VarianceStatuses.writeOffProposed: decisionTitle
        default: VarianceTexts.varianceTitle
        }
    }
}

/// Variances and partial remittance reasons on the decision list and screen.
public enum VariancePresentation {
    typealias T = VarianceTexts
    typealias O = OwnerAccountabilityTexts

    /// The figure of a variance: hours for a customer-hour variance, otherwise money.
    static func figure(_ v: CashVarianceDTO, _ value: DecimalString) -> String {
        v.isHours ? OwnerFormat.hours(value) : OwnerFormat.money(value, currency: v.currency)
    }

    private static func who(_ name: String?, _ id: UUID?) -> String? { DisplayName.optional(name, id: id) }

    static func decision(_ v: CashVarianceDTO, kind: DecisionKind, timeZone: TimeZone) -> PendingDecision {
        let positive = DecimalString(abs(v.amount.value))
        let difference = v.isSurplus ? figure(v, positive) : figure(v, v.isHours ? positive : v.amount)
        let outcome = (v.proposedOutcome ?? v.outcome).map(T.outcome)
        let headline: String
        if kind == .varianceClosure {
            headline = T.closureRow(difference: difference, outcome: outcome ?? "")
        } else {
            headline = v.isSurplus ? O.rowSurplus(difference) : O.rowWriteOff(difference)
        }
        let rows: [(String, String?)] = [
            (O.fieldCustodian, who(v.staffMemberName, v.staffMemberID)),
            (O.fieldCounterparty, who(v.counterpartyStaffName, v.counterpartyStaffID)),
            (O.fieldSource, OwnerFormat.humanize(v.sourceType)),
            (T.check, v.checkCode.map(T.checkText)),
            (T.customer, who(v.customerName, v.customerID)),
            (T.machine, v.machineID.map { DisplayName.machine(code: v.machineCode, name: v.machineName, id: $0) }),
            (T.purchase, who(v.purchaseNumber, v.purchaseID)),
            (T.job, who(v.jobNumber, v.jobID)),
            (O.fieldDeclared, figure(v, v.declaredAmount)),
            (O.fieldReceived, figure(v, v.receivedAmount)),
            (v.isSurplus ? O.varianceSurplus : O.fieldDifference, difference),
            (T.closureOutcome, kind == .varianceClosure ? outcome : nil),
            (O.fieldProposedBy, who(v.proposedByName, v.proposedBy)),
            (O.fieldDecidedBy, who(v.resolvedByName, v.resolvedBy)),
            (O.fieldDecisionNote, v.resolutionNote),
        ]
        return PendingDecision(kind: kind, recordID: v.id, headline: headline, status: v.status, proposedBy: v.proposedBy,
                               proposedByName: who(v.proposedByName, v.proposedBy), proposedAt: v.proposedAt ?? v.openedAt,
                               reason: v.proposalNote, fields: PendingDecision.fields(rows), machineID: v.machineID,
                               photoAttachmentID: nil)
    }

    /// Nil for a handover nobody gave a partial reason on (it is not a decision).
    static func partialDecision(_ h: CashHandoverDTO) -> PendingDecision? {
        guard let p = h.partialApproval else { return nil }
        let custodian = DisplayName.or(h.staffMemberName, id: h.staffMemberID)
        let shortfall = h.partialShortfall.map { OwnerFormat.money($0, currency: h.currency) }
        let rows: [(String, String?)] = [
            (O.fieldCustodian, custodian), (T.partialRemitted, OwnerFormat.money(h.amount, currency: h.currency)),
            (T.partialNotRemitted, shortfall), (O.fieldReason, p.reason),
            (O.fieldProposedBy, who(p.createdByName, p.createdBy)),
            (O.fieldDecidedBy, who(p.decidedByName, p.decidedBy)), (O.fieldDecisionNote, p.decisionNote),
        ]
        return PendingDecision(kind: .partialRemittance, recordID: h.id,
                               headline: T.partialRow(amount: shortfall ?? "—", custodian: custodian), status: p.status,
                               proposedBy: p.createdBy, proposedByName: who(p.createdByName, p.createdBy), proposedAt: p.createdAt,
                               reason: p.reason, fields: PendingDecision.fields(rows), machineID: nil, photoAttachmentID: nil)
    }

    /// Who is on it and what they found (the "Investigation" rows of the Variance screen).
    public static func investigation(_ v: CashVarianceDTO) -> [DecisionField] {
        PendingDecision.fields([
            (T.assignee, who(v.assigneeUserName, v.assigneeUserID)), (T.assignedBy, who(v.assignedByName, v.assignedBy)),
            (T.explanation, v.explanation), (T.explainedBy, who(v.explainedByName, v.explainedBy)),
        ])
    }

    /// "{when} · {action} · {who}" (the person left out when unknown).
    public static func historyRow(_ e: VarianceEventDTO, timeZone: TimeZone = .current) -> String {
        [OwnerFormat.stamp(e.occurredAt, timeZone: timeZone), T.historyAction(e.action), who(e.actorUserName, e.actorUserID)]
            .compactMap { $0 }.joined(separator: " · ")
    }
}

extension SnapshotKey {
    public static func varianceHistory(_ id: UUID) -> SnapshotKey { SnapshotKey("variance.history.\(id.lowercased)") }
}
