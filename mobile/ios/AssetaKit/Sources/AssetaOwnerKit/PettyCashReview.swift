import AssetaModel
import AssetaNetwork
import AssetaStore // UUID.lowercased
import Foundation

// DEC-033 in the Owner app: approve or reject petty cash fundings, top-ups and fund adjustments (online). Identical to
// Android `PettyCashReviewText` (strings doc "DEC-033 — petty cash funds", Owner).

extension SnapshotKey {
    public static let pettyCashMovementsToApprove = SnapshotKey("pettycash.movements.proposed")
    public static let pettyCashAdjustmentsToApprove = SnapshotKey("pettycash.adjustments.pending")
    public static func pettyCashMovement(_ id: UUID) -> SnapshotKey { SnapshotKey("pettycash.movement.\(id.lowercased)") }
    public static func pettyCashAdjustment(_ id: UUID) -> SnapshotKey { SnapshotKey("pettycash.adjustment.\(id.lowercased)") }
    public static func pettyCashMovementExpenses(_ id: UUID) -> SnapshotKey { SnapshotKey("pettycash.movement.expenses.\(id.lowercased)") }
}

extension OwnerAPI {
    static let pettyCash = "\(tenant)/petty-cash"

    /// Fundings and top-ups waiting for approval (PROPOSED), newest first.
    public static func pettyCashMovementsToApprove(pageSize: Int = 100) -> APIRequest<Page<PettyCashMovementDTO>> {
        .get("\(pettyCash)/movements", query: paging(1, pageSize) + compact([("status", PettyCashReviewText.proposed)]))
    }

    /// Fund adjustments waiting for approval (PENDING).
    public static func pettyCashAdjustmentsToApprove(pageSize: Int = 100) -> APIRequest<Page<PettyCashAdjustmentDTO>> {
        .get("\(pettyCash)/adjustments", query: paging(1, pageSize) + compact([("status", PettyCashReviewText.pending)]))
    }

    public static func pettyCashMovement(_ id: UUID) -> APIRequest<PettyCashMovementDTO> {
        .get("\(pettyCash)/movements/\(id.lowercased)")
    }

    public static func pettyCashAdjustment(_ id: UUID) -> APIRequest<PettyCashAdjustmentDTO> {
        .get("\(pettyCash)/adjustments/\(id.lowercased)")
    }

    /// The approved spending a top-up proposal was based on.
    public static func pettyCashMovementExpenses(_ id: UUID) -> APIRequest<[PettyCashTopUpExpenseDTO]> {
        .get("\(pettyCash)/movements/\(id.lowercased)/expenses")
    }

    /// Approve or reject a proposed funding or top-up (never the proposer, never the fund's holder).
    public static func decidePettyCashMovement(_ id: UUID, approve: Bool, note: String,
                                               idempotencyKey: UUID) throws -> APIRequest<PettyCashMovementDTO> {
        try .mutation(.post, "\(pettyCash)/movements/\(id.lowercased)/decision",
                      body: PettyCashDecisionIn(approve: approve, note: Optional(note).nonEmpty), idempotencyKey: idempotencyKey)
    }

    public static func decidePettyCashAdjustment(_ id: UUID, approve: Bool, note: String,
                                                 idempotencyKey: UUID) throws -> APIRequest<PettyCashAdjustmentDTO> {
        try .mutation(.post, "\(pettyCash)/adjustments/\(id.lowercased)/decision",
                      body: PettyCashDecisionIn(approve: approve, note: Optional(note).nonEmpty), idempotencyKey: idempotencyKey)
    }
}

extension OwnerFeatures {
    /// PETTY_CASH on and the role reads petty cash: a petty cash record opens (as Android `pettyCashRead`).
    public var pettyCashRead: Bool {
        !disabledCapabilities.contains(TenantCapability.pettyCash) && permissions.contains("tenant.pettycash.read")
    }

    /// "Petty cash to approve": PETTY_CASH on, the role reads petty cash and approves it.
    public var pettyCashApprove: Bool { pettyCashRead && permissions.contains("tenant.pettycash.approve") }
}

/// One row of the Approvals section: a funding / top-up or a fund adjustment.
public enum PettyCashRequest: Hashable, Sendable, Identifiable {
    case movement(PettyCashMovementDTO)
    case adjustment(PettyCashAdjustmentDTO)

    public var id: UUID {
        switch self {
        case let .movement(m): m.id
        case let .adjustment(a): a.id
        }
    }

    public var route: OwnerRoute {
        switch self {
        case let .movement(m): .pettyCashMovement(m.id)
        case let .adjustment(a): .pettyCashAdjustment(a.id)
        }
    }
}

public enum PettyCashReviewText {
    public static let proposed = "PROPOSED"
    public static let pending = "PENDING"
    public static let section = "Petty cash to approve"
    public static let empty = "No petty cash requests waiting."
    public static let titleMovement = "Petty cash request"
    public static let titleAdjustment = "Fund adjustment"
    public static let fundFallback = "A fund"
    public static let card = "Request"
    public static let fieldFund = "Fund"
    public static let fieldHolder = "Holder"
    public static let fieldKind = "Kind"
    public static let fieldNumber = "Number"
    public static let fieldAmount = "Amount"
    public static let fieldSuggested = "Suggested"
    public static let fieldCap = "Brings the fund to its limit"
    public static let fieldAboveCapReason = "Reason for going above the limit"
    public static let fieldReason = "Reason"
    public static let fieldNote = "Note"
    public static let fieldProposedBy = "Proposed by"
    public static let fieldProposedAt = "Proposed"
    public static let fieldStatus = "Status"
    public static let fieldDecidedBy = "Decided by"
    public static let fieldDecisionNote = "Decision note"
    public static let expenses = "Spending behind this top-up"
    public static let expensesNone = "No expenses listed."
    public static let expensesFailed = "The expenses could not be loaded. Pull to try again."
    public static let decision = "Decision"
    public static let explanationMovement = "Approving lets the office hand the money over. It counts in the fund only after the holder acknowledges it."
    public static let explanationAdjustment = "Approving changes the fund balance by this amount."
    public static let approve = "Approve"
    public static let reject = "Reject"
    public static let cancel = "Cancel"
    public static let approveTitle = "Approve this request?"
    public static let rejectTitle = "Reject this request?"
    public static let noteOptional = "Note (optional)"
    public static let reasonRequired = "Reason (required)"
    public static let errReasonShort = "Write at least 3 characters."
    public static let approved = "Request approved."
    public static let rejected = "Request rejected."
    public static let own = "You proposed this, so someone else must approve or reject it."
    public static let alreadyDecided = "Someone already decided this. Reload to see it."
    public static let noteMin = 3
    public static let noteMax = 1000

    public typealias Money = (DecimalString, String) -> String

    public static func kind(_ raw: String) -> String {
        switch raw {
        case "FUNDING": "Funding"
        case "TOP_UP": "Top-up"
        case "ADJUSTMENT": "Fund adjustment"
        default: OwnerFormat.humanize(raw)
        }
    }

    public static func status(_ raw: String) -> String {
        switch raw {
        case proposed, pending: "Waiting for approval"
        case "APPROVED": "Approved"
        case "REJECTED": "Rejected"
        default: OwnerFormat.humanize(raw)
        }
    }

    public static func statusTone(_ raw: String) -> KPITone {
        switch raw {
        case proposed, pending: .warning
        case "APPROVED": .good
        case "REJECTED": .critical
        default: .muted
        }
    }

    static func fund(_ name: String?) -> String {
        let trimmed = name?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return trimmed.isEmpty ? fundFallback : trimmed
    }

    /// An adjustment is signed: "+TZS 5,000.00" raises the fund, "-TZS 5,000.00" lowers it.
    public static func amount(_ r: PettyCashRequest, money: Money = { OwnerFormat.money($0, currency: $1) }) -> String {
        switch r {
        case let .movement(m): return money(m.amount, m.currency)
        case let .adjustment(a):
            let v = a.amount.value
            return (v < 0 ? "-" : "+") + money(DecimalString(v < 0 ? -v : v), a.currency)
        }
    }

    /// "{kind} {amount} · {fund}".
    public static func headline(_ r: PettyCashRequest, money: Money = { OwnerFormat.money($0, currency: $1) }) -> String {
        switch r {
        case let .movement(m): "\(kind(m.kind)) \(amount(r, money: money)) · \(fund(m.pettyCashFundName))"
        case let .adjustment(a): "\(kind("ADJUSTMENT")) \(amount(r, money: money)) · \(fund(a.pettyCashFundName))"
        }
    }

    /// "Proposed by {name}".
    public static func proposedBy(_ r: PettyCashRequest) -> String? {
        let (name, id): (String?, UUID?) = switch r {
        case let .movement(m): (m.createdByName, m.createdBy)
        case let .adjustment(a): (a.createdByName, a.createdBy)
        }
        return DisplayName.optional(name, id: id).map { "Proposed by \($0)" }
    }

    /// The row's second line: "<number> · Proposed by <name>".
    public static func summary(_ r: PettyCashRequest) -> String {
        let number = switch r {
        case let .movement(m): m.number
        case let .adjustment(a): a.number
        }
        return ([number, proposedBy(r)] as [String?]).compactMap { $0 }.joined(separator: " · ")
    }

    /// The row's third line: the reason (adjustment), else the reason for going above the limit, else the note.
    public static func reasonLine(_ r: PettyCashRequest) -> String? {
        switch r {
        case let .movement(m): m.aboveCapReason.nonEmpty ?? m.note.nonEmpty
        case let .adjustment(a): Optional(a.reason).nonEmpty
        }
    }

    public static func createdAt(_ r: PettyCashRequest) -> Date? {
        switch r {
        case let .movement(m): m.createdAt
        case let .adjustment(a): a.createdAt
        }
    }

    /// Rows of the Approvals section: fundings and top-ups that wait, then adjustments that wait.
    public static func rows(movements: [PettyCashMovementDTO], adjustments: [PettyCashAdjustmentDTO]) -> [PettyCashRequest] {
        movements.filter { $0.status == proposed && ($0.kind == PettyCashMovementDTO.funding || $0.kind == PettyCashMovementDTO.topUp) }
            .map(PettyCashRequest.movement) + adjustments.filter { $0.status == pending }.map(PettyCashRequest.adjustment)
    }

    public static func fields(_ m: PettyCashMovementDTO, timeZone: TimeZone = .current, money: Money = { OwnerFormat.money($0, currency: $1) }) -> [DecisionField] {
        PendingDecision.fields([(fieldFund, fund(m.pettyCashFundName)),
                                (fieldHolder, DisplayName.optional(m.holderStaffName, id: m.holderStaffID)),
                                (fieldKind, kind(m.kind)),
                                (fieldNumber, m.number),
                                (fieldAmount, amount(.movement(m), money: money)),
                                (fieldSuggested, m.suggestedAmount.map { money($0, m.currency) }),
                                (fieldCap, m.capAmount.map { money($0, m.currency) }),
                                (fieldAboveCapReason, m.aboveCapReason),
                                (fieldNote, m.note),
                                (fieldProposedBy, DisplayName.optional(m.createdByName, id: m.createdBy)),
                                (fieldProposedAt, m.createdAt.map { OwnerFormat.stamp($0, timeZone: timeZone) })])
    }

    public static func fields(_ a: PettyCashAdjustmentDTO, timeZone: TimeZone = .current, money: Money = { OwnerFormat.money($0, currency: $1) }) -> [DecisionField] {
        PendingDecision.fields([(fieldFund, fund(a.pettyCashFundName)),
                                (fieldKind, kind("ADJUSTMENT")),
                                (fieldNumber, a.number),
                                (fieldAmount, amount(.adjustment(a), money: money)),
                                (fieldReason, a.reason),
                                (fieldProposedBy, DisplayName.optional(a.createdByName, id: a.createdBy)),
                                (fieldProposedAt, a.createdAt.map { OwnerFormat.stamp($0, timeZone: timeZone) })])
    }

    public static func decisionFields(decidedByName: String?, decidedBy: UUID?, note: String?) -> [DecisionField] {
        PendingDecision.fields([(fieldDecidedBy, DisplayName.optional(decidedByName, id: decidedBy)), (fieldDecisionNote, note)])
    }

    /// "{description} · {amount}".
    public static func expenseLine(_ e: PettyCashTopUpExpenseDTO, currency: String, money: Money = { OwnerFormat.money($0, currency: $1) }) -> String {
        "\(e.description) · \(money(e.amount, currency))"
    }

    /// A rejection must say why (at least 3 characters); approving takes an optional note.
    public static func canDecide(approve: Bool, note: String) -> Bool {
        let length = note.trimmingCharacters(in: .whitespacesAndNewlines).count
        return length <= noteMax && (approve || length >= noteMin)
    }

    /// The proposer never decides their own request (the server refuses it, and the holder, too).
    public static func isOwn(createdBy: UUID?, userID: UUID?) -> Bool { userID != nil && createdBy == userID }

    public static func decidable(_ status: String) -> Bool { status == proposed || status == pending }

    public static func done(approve: Bool) -> String { approve ? approved : rejected }

    public static func needsReload(_ error: any Error) -> Bool { (error as? APIError)?.code == "PETTY_CASH_ALREADY_DECIDED" }

    /// Every refusal in the server's own words, except "already decided" (then the record reloads); a connection
    /// problem keeps the usual wording.
    public static func message(for error: any Error) -> String {
        guard let api = error as? APIError else { return DecisionErrorText.message(for: error) }
        if api.code == "PETTY_CASH_ALREADY_DECIDED" { return alreadyDecided }
        if case let .server(_, body) = api, !body.message.isEmpty { return body.message }
        return DecisionErrorText.message(for: error)
    }
}
