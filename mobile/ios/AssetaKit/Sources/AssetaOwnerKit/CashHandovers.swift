import AssetaModel
import AssetaNetwork
import AssetaStore // UUID.lowercased
import Foundation

/// `GET /tenant/cash/handovers`: cash a supervisor says they handed to the office. CLAIMED until someone other than
/// the recorder confirms (VERIFIED) or disputes (REJECTED) it; only a confirmed handover reduces what they hold.
public struct CashHandoverDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let clientID: UUID?
    public let staffMemberID: UUID
    public let amount: DecimalString
    public let currency: String
    public let handedAt: Date
    public let reference: String?
    public let note: String?
    public let status: String
    public let source: String
    public let recordedBy: UUID?
    public let recordedAt: Date
    public let verifiedBy: UUID?
    public let verifiedAt: Date?
    public let decisionNote: String?
    /// What the office counted when confirming (may differ from the declared amount).
    public let amountReceived: DecimalString?
    /// The custodian's expected balance when remitted, and the part not covered by an approved retention
    /// (non-null = flagged as a partial remittance).
    public let expectedBalance: DecimalString?
    public let partialShortfall: DecimalString?
    /// Display names beside the ids (nullable).
    public let staffMemberName: String?
    public let recordedByName: String?
    public let verifiedByName: String?
    /// DEC-031 D2 (nil on remittances recorded before it): `RemittanceMethod`, the company account, slip photos.
    public let method: String?
    public let depositAccountID: UUID?
    public let depositAccountName: String?
    public let evidenceAttachmentIDs: [UUID]?

    /// Evidence photo ids (empty when none or from an older server).
    public var evidence: [UUID] { evidenceAttachmentIDs ?? [] }

    enum CodingKeys: String, CodingKey {
        case method, depositAccountID = "deposit_account_id", depositAccountName = "deposit_account_name"
        case evidenceAttachmentIDs = "evidence_attachment_ids"
        case staffMemberName = "staff_member_name", recordedByName = "recorded_by_name", verifiedByName = "verified_by_name"
        case id, amount, currency, reference, note, status, source
        case clientID = "client_id", staffMemberID = "staff_member_id", handedAt = "handed_at"
        case recordedBy = "recorded_by", recordedAt = "recorded_at", verifiedBy = "verified_by"
        case verifiedAt = "verified_at", decisionNote = "decision_note", amountReceived = "amount_received"
        case expectedBalance = "expected_balance", partialShortfall = "partial_shortfall"
    }
}

/// `RemittanceDecisionIn`: `verified` true confirms the remittance with the amount actually received, false disputes it.
public struct SettlementDecisionIn: Encodable, Hashable, Sendable {
    public let verified: Bool
    public let note: String?
    public let amountReceived: DecimalString?

    public init(verified: Bool, note: String?, amountReceived: DecimalString? = nil) {
        self.verified = verified
        self.note = note
        self.amountReceived = amountReceived
    }

    enum CodingKeys: String, CodingKey { case verified, note, amountReceived = "amount_received" }

    public func encode(to encoder: any Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(verified, forKey: .verified)
        try c.encodeIfPresent(note, forKey: .note)
        if verified { try c.encodeIfPresent(amountReceived, forKey: .amountReceived) }
    }
}

/// `CashFloatIn` for a float issued to a supervisor (entry type FLOAT_ISSUED, issued now).
public struct CashFloatIn: Encodable, Hashable, Sendable {
    public let staffMemberID: UUID
    public let amount: DecimalString
    public let currency: String?
    public let note: String?

    enum CodingKeys: String, CodingKey {
        case amount, currency, note
        case staffMemberID = "staff_member_id", entryType = "entry_type"
    }

    public func encode(to encoder: any Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(staffMemberID.lowercased, forKey: .staffMemberID)
        try c.encode("FLOAT_ISSUED", forKey: .entryType)
        try c.encode(amount, forKey: .amount)
        try c.encodeIfPresent(currency, forKey: .currency)
        try c.encodeIfPresent(note, forKey: .note)
    }
}

/// `POST /tenant/cash/floats` response: one entry in the supervisor's custody ledger.
public struct CashCustodyEntryDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let staffMemberID: UUID
    public let entryType: String
    public let amount: DecimalString
    public let currency: String
    public let occurredAt: Date
    public let reference: String?
    public let note: String?

    enum CodingKeys: String, CodingKey {
        case id, amount, currency, reference, note
        case staffMemberID = "staff_member_id", entryType = "entry_type", occurredAt = "occurred_at"
    }
}

extension SnapshotKey {
    /// Handovers waiting for confirmation (CLAIMED) or the latest of any status.
    public static func cashHandovers(claimedOnly: Bool) -> SnapshotKey {
        SnapshotKey("cash_handovers:\(claimedOnly ? HandoverText.claimedStatus : "ALL")")
    }
}

extension OwnerAPI {
    /// Cash handovers, newest first (`status` nil = all).
    public static func cashHandovers(status: String? = nil, page: Int = 1,
                                     pageSize: Int = 100) -> APIRequest<Page<CashHandoverDTO>> {
        .get("\(tenant)/cash/handovers", query: paging(page, pageSize) + compact([("status", status)]))
    }

    /// Confirms (`verified: true`, with the amount actually received) or disputes a claimed handover; never by the
    /// person who recorded it.
    public static func decideHandover(_ id: UUID, confirm: Bool, note: String?, amountReceived: Decimal? = nil,
                                      idempotencyKey: UUID) throws -> APIRequest<CashHandoverDTO> {
        try .mutation(.post, "\(tenant)/cash/handovers/\(id.lowercased)/decision",
                      body: SettlementDecisionIn(verified: confirm, note: note.nonEmpty,
                                                 amountReceived: amountReceived.map(DecimalString.init)),
                      idempotencyKey: idempotencyKey)
    }

    /// Presigned URL of a remittance's deposit slip photo, fetched on demand only (never cached).
    public static func remittanceEvidenceURL(handoverID: UUID, attachmentID: UUID) -> APIRequest<PhotoURLDTO> {
        .get("\(tenant)/cash/handovers/\(handoverID.lowercased)/evidence/\(attachmentID.lowercased)/url")
    }

    /// Issues a cash float into a supervisor's custody (added to what they must account for).
    public static func issueFloat(staffMemberID: UUID, amount: Decimal, currency: String?, note: String?,
                                  idempotencyKey: UUID) throws -> APIRequest<CashCustodyEntryDTO> {
        try .mutation(.post, "\(tenant)/cash/floats",
                      body: CashFloatIn(staffMemberID: staffMemberID, amount: DecimalString(amount),
                                        currency: currency.nonEmpty, note: note.nonEmpty),
                      idempotencyKey: idempotencyKey)
    }
}

/// Wording and input rules of confirming cash handovers. Identical to Android `HandoverText`.
public enum HandoverText {
    public static let sectionTitle = "Cash handovers"
    public static let empty = "No cash handovers waiting."
    public static let confirm = "Confirm received"
    public static let dispute = "Dispute"
    public static let confirmTitle = "Confirm this handover?"
    public static let disputeTitle = "Dispute this handover?"
    public static let note = "Note"
    public static let reason = "Reason"
    public static let confirmed = "Handover confirmed."
    public static let disputed = "Handover disputed."
    public static let unknownSupervisor = "A supervisor"
    public static let notFound = "Handover not found"
    public static let screenTitle = "Cash handover"
    public static let card = "Handover"
    public static let alreadyDecided = "Someone already decided this handover. Reload to see it."
    public static let claimedStatus = "CLAIMED"
    /// The server keeps notes of at most 1000 characters.
    public static let maxNoteLength = 1000

    /// "<supervisor> handed over TZS 150,000.00". The server's `staff_member_name` wins over `supervisor` (a name
    /// looked up from today's cash summary).
    public static func title(_ h: CashHandoverDTO, supervisor: String?,
                             money: (DecimalString, String) -> String = { OwnerFormat.money($0, currency: $1) }) -> String {
        let name = (h.staffMemberName ?? supervisor)?.trimmingCharacters(in: .whitespacesAndNewlines)
        return "\((name?.isEmpty ?? true) ? unknownSupervisor : name!) handed over \(money(h.amount, h.currency))"
    }

    /// "Claimed 22 Oct 2026, 14:05" (when the supervisor says they handed it over).
    public static func claimed(_ h: CashHandoverDTO, timeZone: TimeZone = .current) -> String {
        "Claimed \(OwnerFormat.stamp(h.handedAt, timeZone: timeZone))"
    }

    /// Supervisor names by staff id, from today's cash summary (best effort).
    public static func names(_ summary: [CashSupervisorSummaryDTO]) -> [UUID: String] {
        Dictionary(summary.map { ($0.staffMemberID, $0.staffName) }, uniquingKeysWith: { first, _ in first })
    }

    /// Confirming takes an optional note; disputing needs a reason.
    public static func canDecide(confirm: Bool, text: String) -> Bool {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard trimmed.count <= maxNoteLength else { return false }
        return confirm || !trimmed.isEmpty
    }

    /// Confirming also needs the amount received (0 or more), prefilled with the declared amount.
    public static func canConfirm(amountReceived: String, text: String) -> Bool {
        parseReceived(amountReceived) != nil && canDecide(confirm: true, text: text)
    }

    /// The counted amount: a plain decimal of 0 or more (`150000`, `150,000.50`), else nil.
    public static func parseReceived(_ text: String) -> Decimal? {
        let cleaned = text.trimmingCharacters(in: .whitespaces).replacingOccurrences(of: ",", with: "")
        guard let value = DecimalString(string: cleaned)?.value, value >= 0 else { return nil }
        return value
    }

    /// The declared amount as the editable starting value ("150000.5").
    public static func prefill(_ h: CashHandoverDTO) -> String { h.amount.description }

    /// Method, Paid into and Reference of a remittance (DEC-031 D2), in screen order; empty values left out. Shown
    /// in the Handover card and repeated read-only in the confirm dialog above "Amount received".
    public static func details(_ h: CashHandoverDTO) -> [DecisionField] {
        typealias T = OwnerAccountabilityTexts
        let account = h.depositAccountID.map { DisplayName.or(h.depositAccountName, id: $0) }
        return PendingDecision.fields([(T.remitMethod, T.remitMethodText(h.method)), (T.remitAccount, account),
                                       (T.remitReference, h.reference)])
    }

    /// "No deposit slip photo" applies: a bank / mobile-money remittance (method other than cash) without a photo.
    public static func missingPhoto(_ h: CashHandoverDTO) -> Bool {
        guard let method = h.method, method != RemittanceMethod.cashToOffice.rawValue else { return false }
        return h.evidence.isEmpty
    }

    public static func done(confirm: Bool) -> String { confirm ? confirmed : disputed }

    public static func statusTone(_ status: String) -> KPITone {
        switch status {
        case "CLAIMED": .warning
        case "VERIFIED": .good
        case "REJECTED": .critical
        default: .muted
        }
    }

    /// Codes after which the handover must be reloaded (someone else decided it).
    public static func needsReload(_ error: any Error) -> Bool { (error as? APIError)?.code == "HANDOVER_ALREADY_DECIDED" }

    public static func message(for error: any Error) -> String {
        if (error as? APIError)?.code == "HANDOVER_ALREADY_DECIDED" { return alreadyDecided }
        return DecisionErrorText.message(for: error)
    }
}

/// Wording and input rules of issuing a cash float. Identical to Android `FloatText`.
public enum FloatText {
    public static let action = "Issue float"
    public static let title = "Issue a cash float"
    public static let note = "Note (optional)"
    public static let submit = "Issue"
    public static let issued = "Float issued."

    /// "Amount (TZS)".
    public static func amountLabel(currency: String?) -> String {
        guard let currency, !currency.isEmpty else { return "Amount" }
        return "Amount (\(currency))"
    }

    /// The typed amount: a plain positive decimal (`50000`, `50,000.50`), else nil.
    public static func parseAmount(_ text: String) -> Decimal? { JobApprovalText.parseRate(text) }

    public static func canIssue(amount: String, note: String) -> Bool {
        parseAmount(amount) != nil && note.trimmingCharacters(in: .whitespacesAndNewlines).count <= HandoverText.maxNoteLength
    }

    /// Same hints as the web finance screens.
    public static func message(for error: any Error) -> String {
        switch (error as? APIError)?.code {
        case "NOT_CUSTODIAN": "Only office cash staff may record custody for someone else."
        case "STAFF_INACTIVE": "The staff member is inactive."
        case "STAFF_NOT_LINKED": "Your login is not linked to a staff record; pick the staff member explicitly."
        case "CURRENCY_NOT_CONFIGURED": "Choose a configured currency."
        case "CURRENCY_MISMATCH": "All amounts on one record must share a single currency."
        default: DecisionErrorText.message(for: error)
        }
    }
}
