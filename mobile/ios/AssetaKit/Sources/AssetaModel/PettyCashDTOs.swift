import Foundation

// DEC-033 petty cash funds: the holder's snapshot rows (Supervisor, OP_PETTY_CASH), the offline operation payloads and the
// Owner's approval reads. Shapes follow `contracts/openapi.json` (`PettyCash*Dto`, `PettyCash*In`); money is a decimal
// string. Only the fields the apps show are decoded; everything optional the server may leave out is optional here.

extension SyncCapability {
    /// `PETTY_CASH_*` operations, `EXPENSE.paid_from = PETTY_CASH` and the `petty_cash_*` snapshots.
    public static let pettyCash = "OP_PETTY_CASH"
    /// `SyncData.petty_cash_witnesses`: who may witness a count (never me), so a witnessed count is recorded offline.
    public static let pettyCashWitnesses = "SYNC_PETTY_CASH_WITNESSES"
}

/// `PettyCashWitnessDto`: a login that may witness a count (active, holding the count permission, never the caller).
public struct PettyCashWitnessDTO: Codable, Hashable, Sendable, Identifiable {
    public let userID: UUID
    public let name: String
    public var id: UUID { userID }

    public init(userID: UUID, name: String) {
        self.userID = userID
        self.name = name
    }

    enum CodingKeys: String, CodingKey {
        case userID = "user_id", name
    }
}

/// `PettyCashBalanceDto`: the server's figures of one fund (the phone never computes a balance).
public struct PettyCashBalanceDTO: Codable, Hashable, Sendable {
    public let balance: DecimalString
    public let availableToSpend: DecimalString
    public let approvedLimit: DecimalString?
    public let pendingSpending: DecimalString?
    public let awaitingAcknowledgement: DecimalString?
    public let returnsClaimed: DecimalString?
    public let belowLowBalance: Bool?
    public let lastCountAt: Date?
    public let nextCountDueAt: Date?
    public let asOf: Date?

    enum CodingKeys: String, CodingKey {
        case balance, availableToSpend = "available_to_spend", approvedLimit = "approved_limit"
        case pendingSpending = "pending_spending", awaitingAcknowledgement = "awaiting_acknowledgement"
        case returnsClaimed = "returns_claimed", belowLowBalance = "below_low_balance", lastCountAt = "last_count_at"
        case nextCountDueAt = "next_count_due_at", asOf = "as_of"
    }
}

/// `PettyCashFundDto` (with its balance in the sync snapshot).
public struct PettyCashFundDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let code: String
    public let name: String
    public let holderStaffID: UUID
    public let holderStaffName: String?
    public let currency: String
    public let approvedLimit: DecimalString
    public let isActive: Bool?
    public let balance: PettyCashBalanceDTO?

    enum CodingKeys: String, CodingKey {
        case id, code, name, currency, balance, holderStaffID = "holder_staff_id", holderStaffName = "holder_staff_name"
        case approvedLimit = "approved_limit", isActive = "is_active"
    }
}

/// `PettyCashMovementDto`: a funding, top-up or return.
public struct PettyCashMovementDTO: Codable, Hashable, Sendable, Identifiable {
    public static let funding = "FUNDING", topUp = "TOP_UP"

    public let id: UUID
    public let number: String
    public let fundID: UUID
    public let pettyCashFundName: String?
    public let kind: String
    public let status: String
    public let holderStaffID: UUID?
    public let holderStaffName: String?
    public let amount: DecimalString
    public let currency: String
    public let reference: String?
    public let note: String?
    public let suggestedAmount: DecimalString?
    public let capAmount: DecimalString?
    public let aboveCapReason: String?
    public let createdBy: UUID?
    public let createdByName: String?
    public let createdAt: Date?
    public let decidedBy: UUID?
    public let decidedByName: String?
    public let decisionNote: String?
    public let issuedByName: String?
    public let issuedAt: Date?

    enum CodingKeys: String, CodingKey {
        case id, number, kind, status, amount, currency, reference, note
        case fundID = "fund_id", pettyCashFundName = "petty_cash_fund_name", holderStaffID = "holder_staff_id"
        case holderStaffName = "holder_staff_name", suggestedAmount = "suggested_amount", capAmount = "cap_amount"
        case aboveCapReason = "above_cap_reason", createdBy = "created_by", createdByName = "created_by_name"
        case createdAt = "created_at", decidedBy = "decided_by", decidedByName = "decided_by_name"
        case decisionNote = "decision_note", issuedByName = "issued_by_name", issuedAt = "issued_at"
    }
}

/// `PettyCashHolderChangeDto`: a fund being handed to me (the old holder stays accountable until I accept).
public struct PettyCashHolderChangeDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let fundID: UUID
    public let pettyCashFundName: String?
    public let fromStaffID: UUID?
    public let fromStaffName: String?
    public let toStaffID: UUID?
    public let status: String?
    public let note: String?
    public let requestedBy: UUID?
    public let requestedByName: String?
    public let requestedAt: Date?

    enum CodingKeys: String, CodingKey {
        case id, status, note, fundID = "fund_id", pettyCashFundName = "petty_cash_fund_name", fromStaffID = "from_staff_id"
        case fromStaffName = "from_staff_name", toStaffID = "to_staff_id", requestedBy = "requested_by"
        case requestedByName = "requested_by_name", requestedAt = "requested_at"
    }
}

/// `PettyCashAdvanceDto`: cash out of a fund before a purchase (phase 3, `advances_enabled`).
public struct PettyCashAdvanceDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let number: String
    public let fundID: UUID
    public let pettyCashFundName: String?
    public let recipientStaffID: UUID
    public let recipientStaffName: String?
    public let amount: DecimalString
    public let currency: String
    public let purpose: String?
    public let status: String?
    public let dueAt: Date?
    public let overdue: Bool?
    public let approvedSpending: DecimalString?
    public let pendingSpending: DecimalString?
    public let remaining: DecimalString?

    enum CodingKeys: String, CodingKey {
        case id, number, amount, currency, purpose, status, overdue, remaining
        case fundID = "fund_id", pettyCashFundName = "petty_cash_fund_name", recipientStaffID = "recipient_staff_id"
        case recipientStaffName = "recipient_staff_name", dueAt = "due_at", approvedSpending = "approved_spending"
        case pendingSpending = "pending_spending"
    }
}

/// `PettyCashAdjustmentDto` (Owner approvals).
public struct PettyCashAdjustmentDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let number: String
    public let fundID: UUID
    public let pettyCashFundName: String?
    public let amount: DecimalString
    public let currency: String
    public let reason: String
    public let status: String
    public let createdBy: UUID?
    public let createdByName: String?
    public let createdAt: Date?
    public let decidedBy: UUID?
    public let decidedByName: String?
    public let decisionNote: String?

    enum CodingKeys: String, CodingKey {
        case id, number, amount, currency, reason, status, fundID = "fund_id", pettyCashFundName = "petty_cash_fund_name"
        case createdBy = "created_by", createdByName = "created_by_name", createdAt = "created_at", decidedBy = "decided_by"
        case decidedByName = "decided_by_name", decisionNote = "decision_note"
    }
}

/// `TopUpExpenseDto`: approved spending a top-up proposal was based on.
public struct PettyCashTopUpExpenseDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let description: String
    public let amount: DecimalString
    public let incurredAt: Date?

    enum CodingKeys: String, CodingKey { case id, description, amount, incurredAt = "incurred_at" }
}

/// `PettyCashDecisionIn`.
public struct PettyCashDecisionIn: Codable, Hashable, Sendable {
    public let approve: Bool
    public let note: String?

    public init(approve: Bool, note: String?) {
        self.approve = approve
        self.note = note
    }
}

// MARK: - Operation payloads

/// `PETTY_CASH_ACKNOWLEDGEMENT` (`PettyCashAcknowledgementIn` + the movement id): a dispute carries no amount.
public struct PettyCashAckPayload: Codable, Hashable, Sendable {
    public let movementID: UUID
    public let acknowledged: Bool
    public let amountReceived: DecimalString?
    public let note: String?

    public init(movementID: UUID, acknowledged: Bool, amountReceived: Decimal?, note: String?) {
        self.movementID = movementID
        self.acknowledged = acknowledged
        self.amountReceived = acknowledged ? amountReceived.map(DecimalString.init) : nil
        self.note = note
    }

    enum CodingKeys: String, CodingKey { case acknowledged, note, movementID = "movement_id", amountReceived = "amount_received" }
}

/// `PETTY_CASH_TOP_UP_REQUEST` (`TopUpRequestIn` + the fund): no amount = the server's imprest suggestion.
public struct PettyCashTopUpPayload: Codable, Hashable, Sendable {
    public let clientID: UUID
    public let fundID: UUID
    public let amount: DecimalString?
    public let note: String?
    public let aboveCapReason: String?

    public init(clientID: UUID, fundID: UUID, amount: Decimal?, note: String?, aboveCapReason: String?) {
        self.clientID = clientID
        self.fundID = fundID
        self.amount = amount.map(DecimalString.init)
        self.note = note
        self.aboveCapReason = aboveCapReason
    }

    enum CodingKeys: String, CodingKey {
        case amount, note, clientID = "client_id", fundID = "fund_id", aboveCapReason = "above_cap_reason"
    }
}

/// `PETTY_CASH_RETURN` (`PettyCashReturnIn` + `evidence_upload_ids`, filled as each photo upload completes).
public struct PettyCashReturnPayload: Codable, Hashable, Sendable {
    public let clientID: UUID
    public let fundID: UUID
    public let amount: DecimalString
    public let depositAccountID: UUID?
    public let method: String?
    public let reference: String?
    public let note: String?
    public let evidenceUploadIDs: [UUID]

    public init(clientID: UUID, fundID: UUID, amount: Decimal, depositAccountID: UUID?, method: String?, reference: String?,
                note: String?) {
        self.clientID = clientID
        self.fundID = fundID
        self.amount = DecimalString(amount)
        self.depositAccountID = depositAccountID
        self.method = method
        self.reference = reference
        self.note = note
        evidenceUploadIDs = []
    }

    enum CodingKeys: String, CodingKey {
        case amount, method, reference, note, clientID = "client_id", fundID = "fund_id"
        case depositAccountID = "deposit_account_id", evidenceUploadIDs = "evidence_upload_ids"
    }
}

/// `PETTY_CASH_COUNT` (`PettyCashCountIn` + `evidence_upload_ids`).
public struct PettyCashCountPayload: Codable, Hashable, Sendable {
    public let clientID: UUID
    public let fundID: UUID
    public let countedAmount: DecimalString
    public let witnessUserID: UUID?
    public let note: String?
    public let evidenceUploadIDs: [UUID]

    public init(clientID: UUID, fundID: UUID, countedAmount: Decimal, witnessUserID: UUID?, note: String?) {
        self.clientID = clientID
        self.fundID = fundID
        self.countedAmount = DecimalString(countedAmount)
        self.witnessUserID = witnessUserID
        self.note = note
        evidenceUploadIDs = []
    }

    enum CodingKeys: String, CodingKey {
        case note, clientID = "client_id", fundID = "fund_id", countedAmount = "counted_amount"
        case witnessUserID = "witness_user_id", evidenceUploadIDs = "evidence_upload_ids"
    }
}

/// `PETTY_CASH_HOLDER_CHANGE_ACKNOWLEDGEMENT` (`PettyCashHolderChangeDecisionIn` + the change id).
public struct PettyCashHolderChangePayload: Codable, Hashable, Sendable {
    public let holderChangeID: UUID
    public let accept: Bool
    public let note: String?

    public init(holderChangeID: UUID, accept: Bool, note: String?) {
        self.holderChangeID = holderChangeID
        self.accept = accept
        self.note = note
    }

    enum CodingKeys: String, CodingKey { case accept, note, holderChangeID = "holder_change_id" }
}

/// `PETTY_CASH_ADVANCE_CLEARANCE` (`PettyCashAdvanceClearIn` + the advance id).
public struct PettyCashAdvanceClearPayload: Codable, Hashable, Sendable {
    public let advanceID: UUID
    public let changeReturned: DecimalString
    public let note: String?

    public init(advanceID: UUID, changeReturned: Decimal, note: String?) {
        self.advanceID = advanceID
        self.changeReturned = DecimalString(changeReturned)
        self.note = note
    }

    enum CodingKeys: String, CodingKey { case note, advanceID = "advance_id", changeReturned = "change_returned" }
}

/// `PersonDto` (`GET /tenant/people?q=`): a colleague's display name for the count witness picker.
public struct PersonDTO: Codable, Hashable, Sendable, Identifiable {
    public let userID: UUID
    public let displayName: String
    public var id: UUID { userID }

    public init(userID: UUID, displayName: String) {
        self.userID = userID
        self.displayName = displayName
    }

    enum CodingKeys: String, CodingKey { case userID = "user_id", displayName = "display_name" }
}

/// Expense control flags (`ExpenseDto.control_flags`, DEC-033): why a human must look at an expense, in neutral words
/// (shared by the Supervisor and Owner apps; strings doc `expense.flags.*`).
public enum ExpenseFlags {
    public static let title = "To check"
    public static let paidFromPettyCash = "Petty cash"

    public static func label(_ code: String) -> String {
        switch code {
        case "OVERSPEND": "Recorded above what the fund had available"
        case "SPENT_FROM_COLLECTIONS": "Paid from collected cash"
        case "ABOVE_PETTY_CASH_MAXIMUM": "Above the petty cash maximum per expense"
        default: humanize(code)
        }
    }

    public static func lines(_ flags: [String]) -> [String] { flags.filter { !$0.isEmpty }.map(label) }

    /// "SOME_FLAG" -> "Some flag".
    static func humanize(_ raw: String) -> String {
        let words = raw.replacingOccurrences(of: "_", with: " ").lowercased()
        return words.prefix(1).uppercased() + words.dropFirst()
    }
}
