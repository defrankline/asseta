import Foundation

// MARK: - DEC-032 Phase 2: adjustments ledger, hour corrections, refunds, reversals (online only, never synced)

/// `AdjustmentRequestType` values the apps name (unknown values are shown humanized).
public enum AdjustmentRequestTypes {
    public static let hoursCorrection = "HOURS_CORRECTION"
    public static let hoursRefund = "HOURS_REFUND"
    public static let paymentReversal = "PAYMENT_REVERSAL"
    public static let collectionReversal = "COLLECTION_REVERSAL"
    public static let purchaseReversal = "PURCHASE_REVERSAL"
    public static let invoiceVoid = "INVOICE_VOID"
    public static let zeroAmountActivation = "ZERO_AMOUNT_ACTIVATION"
}

/// `AdjustmentRequestStatus` values.
public enum AdjustmentRequestStatuses {
    public static let proposed = "PROPOSED"
    public static let approved = "APPROVED"
    public static let rejected = "REJECTED"
    public static let withdrawn = "WITHDRAWN"
}

/// `AdjustmentEntryStatus` values.
public enum AdjustmentEntryStatuses {
    public static let approved = "APPROVED"
    public static let rejected = "REJECTED"
    public static let revoked = "REVOKED"
}

/// `RefundSettlement` values.
public enum RefundSettlements {
    public static let credit = "CREDIT"
    public static let payOut = "PAY_OUT"
}

/// `AdjustmentDecisionIn`: APPROVE or REJECT with an optional note (at most 1000 characters).
public struct AdjustmentDecisionIn: Encodable, Hashable, Sendable {
    public let decision: String
    public let note: String?

    public init(decision: String, note: String?) {
        self.decision = decision
        self.note = note
    }
}

/// `AdjustmentWithdrawIn`: why the proposer takes the request back (3..1000 characters).
public struct AdjustmentWithdrawIn: Encodable, Hashable, Sendable {
    public let reason: String

    public init(reason: String) { self.reason = reason }
}

/// `AdjustmentRequestDto`: a proposed correction, refund, reversal or invoice void. Open values are strings and the
/// additive fields default, so an older build keeps working when the server adds to them.
public struct AdjustmentRequestDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let requestType: String
    /// ARQ- number (DEC-032 Phase 3); nil from older servers.
    public let requestNumber: String?
    public let status: String
    public let originalType: String?
    public let originalID: UUID?
    public let originalReference: String?
    public let customerID: UUID?
    public let customerName: String?
    public let machineID: UUID?
    public let machineCode: String?
    public let machineName: String?
    public let purchaseID: UUID?
    public let purchaseNumber: String?
    public let hours: DecimalString?
    public let amount: DecimalString?
    public let currency: String?
    public let settlement: String?
    public let params: JSONValue
    public let reason: String
    public let reasonCodeID: UUID?
    public let reasonLabel: String?
    public let evidenceAttachmentIDs: [UUID]
    public let proposedBy: UUID?
    public let proposedByName: String?
    public let proposedAt: Date
    public let decidedBy: UUID?
    public let decidedByName: String?
    public let decidedAt: Date?
    public let decisionNote: String?
    /// While PROPOSED: what approving would do now; once decided: what it did. `{refused: code}` when it could not.
    public let effects: JSONValue

    public init(from decoder: any Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(UUID.self, forKey: .id)
        requestType = try c.decode(String.self, forKey: .requestType)
        requestNumber = try c.decodeIfPresent(String.self, forKey: .requestNumber)
        status = try c.decode(String.self, forKey: .status)
        originalType = try c.decodeIfPresent(String.self, forKey: .originalType)
        originalID = try c.decodeIfPresent(UUID.self, forKey: .originalID)
        originalReference = try c.decodeIfPresent(String.self, forKey: .originalReference)
        customerID = try c.decodeIfPresent(UUID.self, forKey: .customerID)
        customerName = try c.decodeIfPresent(String.self, forKey: .customerName)
        machineID = try c.decodeIfPresent(UUID.self, forKey: .machineID)
        machineCode = try c.decodeIfPresent(String.self, forKey: .machineCode)
        machineName = try c.decodeIfPresent(String.self, forKey: .machineName)
        purchaseID = try c.decodeIfPresent(UUID.self, forKey: .purchaseID)
        purchaseNumber = try c.decodeIfPresent(String.self, forKey: .purchaseNumber)
        hours = try c.decodeIfPresent(DecimalString.self, forKey: .hours)
        amount = try c.decodeIfPresent(DecimalString.self, forKey: .amount)
        currency = try c.decodeIfPresent(String.self, forKey: .currency)
        settlement = try c.decodeIfPresent(String.self, forKey: .settlement)
        params = try c.decodeIfPresent(JSONValue.self, forKey: .params) ?? .object([:])
        reason = try c.decodeIfPresent(String.self, forKey: .reason) ?? ""
        reasonCodeID = try c.decodeIfPresent(UUID.self, forKey: .reasonCodeID)
        reasonLabel = try c.decodeIfPresent(String.self, forKey: .reasonLabel)
        evidenceAttachmentIDs = try c.decodeIfPresent([UUID].self, forKey: .evidenceAttachmentIDs) ?? []
        proposedBy = try c.decodeIfPresent(UUID.self, forKey: .proposedBy)
        proposedByName = try c.decodeIfPresent(String.self, forKey: .proposedByName)
        proposedAt = try c.decode(Date.self, forKey: .proposedAt)
        decidedBy = try c.decodeIfPresent(UUID.self, forKey: .decidedBy)
        decidedByName = try c.decodeIfPresent(String.self, forKey: .decidedByName)
        decidedAt = try c.decodeIfPresent(Date.self, forKey: .decidedAt)
        decisionNote = try c.decodeIfPresent(String.self, forKey: .decisionNote)
        effects = try c.decodeIfPresent(JSONValue.self, forKey: .effects) ?? .object([:])
    }

    enum CodingKeys: String, CodingKey {
        case id, status, hours, amount, currency, settlement, params, reason, effects
        case requestNumber = "request_number"
        case requestType = "request_type", originalType = "original_type", originalID = "original_id"
        case originalReference = "original_reference", customerID = "customer_id", customerName = "customer_name"
        case machineID = "machine_id", machineCode = "machine_code", machineName = "machine_name"
        case purchaseID = "purchase_id", purchaseNumber = "purchase_number", reasonCodeID = "reason_code_id"
        case reasonLabel = "reason_label", evidenceAttachmentIDs = "evidence_attachment_ids", proposedBy = "proposed_by"
        case proposedByName = "proposed_by_name", proposedAt = "proposed_at", decidedBy = "decided_by"
        case decidedByName = "decided_by_name", decidedAt = "decided_at", decisionNote = "decision_note"
    }
}

/// `CustomerPaymentDto`, the part the Owner app reads: whether a payment was reversed.
public struct CustomerPaymentDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let reversedAt: Date?
    public let reversalID: UUID?

    enum CodingKeys: String, CodingKey {
        case id, reversedAt = "reversed_at", reversalID = "reversal_id"
    }
}

/// `AdjustmentEntryDto`: one posted line of the adjustments ledger (append-only).
public struct AdjustmentEntryDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let adjustmentType: String
    public let status: String
    public let originalType: String?
    public let originalID: UUID?
    public let originalReference: String?
    public let sourceType: String?
    public let sourceID: UUID?
    public let unit: String
    public let originalValue: DecimalString?
    public let newValue: DecimalString?
    public let amount: DecimalString?
    public let currency: String?
    public let resultingBalance: DecimalString?
    public let reasonID: UUID?
    public let reasonLabel: String?
    public let reason: String?
    public let evidenceAttachmentIDs: [UUID]
    public let customerID: UUID?
    public let customerName: String?
    public let machineID: UUID?
    public let machineCode: String?
    public let machineName: String?
    public let staffMemberID: UUID?
    public let staffMemberName: String?
    public let requestedBy: UUID?
    public let requestedByName: String?
    public let requestedAt: Date?
    public let approvedBy: UUID?
    public let approvedByName: String?
    public let approvedAt: Date?
    public let decisionNote: String?
    public let details: JSONValue
    public let postedAt: Date

    public init(from decoder: any Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(UUID.self, forKey: .id)
        adjustmentType = try c.decode(String.self, forKey: .adjustmentType)
        status = try c.decode(String.self, forKey: .status)
        originalType = try c.decodeIfPresent(String.self, forKey: .originalType)
        originalID = try c.decodeIfPresent(UUID.self, forKey: .originalID)
        originalReference = try c.decodeIfPresent(String.self, forKey: .originalReference)
        sourceType = try c.decodeIfPresent(String.self, forKey: .sourceType)
        sourceID = try c.decodeIfPresent(UUID.self, forKey: .sourceID)
        unit = try c.decodeIfPresent(String.self, forKey: .unit) ?? ""
        originalValue = try c.decodeIfPresent(DecimalString.self, forKey: .originalValue)
        newValue = try c.decodeIfPresent(DecimalString.self, forKey: .newValue)
        amount = try c.decodeIfPresent(DecimalString.self, forKey: .amount)
        currency = try c.decodeIfPresent(String.self, forKey: .currency)
        resultingBalance = try c.decodeIfPresent(DecimalString.self, forKey: .resultingBalance)
        reasonID = try c.decodeIfPresent(UUID.self, forKey: .reasonID)
        reasonLabel = try c.decodeIfPresent(String.self, forKey: .reasonLabel)
        reason = try c.decodeIfPresent(String.self, forKey: .reason)
        evidenceAttachmentIDs = try c.decodeIfPresent([UUID].self, forKey: .evidenceAttachmentIDs) ?? []
        customerID = try c.decodeIfPresent(UUID.self, forKey: .customerID)
        customerName = try c.decodeIfPresent(String.self, forKey: .customerName)
        machineID = try c.decodeIfPresent(UUID.self, forKey: .machineID)
        machineCode = try c.decodeIfPresent(String.self, forKey: .machineCode)
        machineName = try c.decodeIfPresent(String.self, forKey: .machineName)
        staffMemberID = try c.decodeIfPresent(UUID.self, forKey: .staffMemberID)
        staffMemberName = try c.decodeIfPresent(String.self, forKey: .staffMemberName)
        requestedBy = try c.decodeIfPresent(UUID.self, forKey: .requestedBy)
        requestedByName = try c.decodeIfPresent(String.self, forKey: .requestedByName)
        requestedAt = try c.decodeIfPresent(Date.self, forKey: .requestedAt)
        approvedBy = try c.decodeIfPresent(UUID.self, forKey: .approvedBy)
        approvedByName = try c.decodeIfPresent(String.self, forKey: .approvedByName)
        approvedAt = try c.decodeIfPresent(Date.self, forKey: .approvedAt)
        decisionNote = try c.decodeIfPresent(String.self, forKey: .decisionNote)
        details = try c.decodeIfPresent(JSONValue.self, forKey: .details) ?? .object([:])
        postedAt = try c.decode(Date.self, forKey: .postedAt)
    }

    enum CodingKeys: String, CodingKey {
        case id, status, unit, amount, currency, reason, details
        case adjustmentType = "adjustment_type", originalType = "original_type", originalID = "original_id"
        case originalReference = "original_reference", sourceType = "source_type", sourceID = "source_id"
        case originalValue = "original_value", newValue = "new_value", resultingBalance = "resulting_balance"
        case reasonID = "reason_id", reasonLabel = "reason_label", evidenceAttachmentIDs = "evidence_attachment_ids"
        case customerID = "customer_id", customerName = "customer_name", machineID = "machine_id"
        case machineCode = "machine_code", machineName = "machine_name", staffMemberID = "staff_member_id"
        case staffMemberName = "staff_member_name", requestedBy = "requested_by", requestedByName = "requested_by_name"
        case requestedAt = "requested_at", approvedBy = "approved_by", approvedByName = "approved_by_name"
        case approvedAt = "approved_at", decisionNote = "decision_note", postedAt = "posted_at"
    }
}
