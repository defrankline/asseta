import AssetaModel
import AssetaNetwork
import AssetaStore // UUID.lowercased
import Foundation

/// `HireAllocationDto`: the part of a payment set against one invoice (released once the payment is rejected).
public struct PaymentAllocationDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let invoiceID: UUID
    public let amount: DecimalString
    public let releasedAt: Date?

    enum CodingKeys: String, CodingKey { case id, amount, invoiceID = "invoice_id", releasedAt = "released_at" }
}

/// `PurchaseLinkDto`: the hours purchase a customer payment is linked to.
public struct PaymentPurchaseLinkDTO: Codable, Hashable, Sendable, Identifiable {
    public let purchaseID: UUID
    public let purchaseNumber: String
    public let amount: DecimalString

    public var id: UUID { purchaseID }

    enum CodingKeys: String, CodingKey { case amount, purchaseID = "purchase_id", purchaseNumber = "purchase_number" }
}

/// `CustomerPaymentDto` in full (`CustomerPaymentDTO` reads only whether a payment was reversed): money a customer
/// paid. `status` is CLAIMED until someone other than the recorder confirms (VERIFIED) or rejects (REJECTED) it.
public struct CustomerPaymentRecordDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let customerID: UUID
    public let customerName: String?
    public let amount: DecimalString
    public let currency: String
    public let method: String
    public let status: String
    public let receivedAt: Date
    public let recordedAt: Date
    public let reference: String?
    public let note: String?
    public let collectionNumber: String?
    public let receivedByStaffID: UUID?
    public let receivedByStaffName: String?
    public let recordedBy: UUID?
    public let recordedByName: String?
    public let verifiedBy: UUID?
    public let verifiedByName: String?
    public let verifiedAt: Date?
    public let decisionNote: String?
    public let reversedAt: Date?
    public let allocations: [PaymentAllocationDTO]?
    public let purchaseLinks: [PaymentPurchaseLinkDTO]?

    enum CodingKeys: String, CodingKey {
        case id, amount, currency, method, status, reference, note, allocations
        case customerID = "customer_id", customerName = "customer_name", receivedAt = "received_at", recordedAt = "recorded_at"
        case collectionNumber = "collection_number", receivedByStaffID = "received_by_staff_id"
        case receivedByStaffName = "received_by_staff_name", recordedBy = "recorded_by", recordedByName = "recorded_by_name"
        case verifiedBy = "verified_by", verifiedByName = "verified_by_name", verifiedAt = "verified_at"
        case decisionNote = "decision_note", reversedAt = "reversed_at", purchaseLinks = "purchase_links"
    }
}

/// `PaymentEvidenceDto`: one photo attached to a customer payment.
public struct PaymentEvidenceDTO: Codable, Hashable, Sendable {
    public let attachmentID: UUID

    enum CodingKeys: String, CodingKey { case attachmentID = "attachment_id" }
}

/// `HireInvoiceDto`, only what names an invoice beside a payment.
public struct InvoiceNumberDTO: Codable, Hashable, Sendable {
    public let invoiceNumber: String?

    enum CodingKeys: String, CodingKey { case invoiceNumber = "invoice_number" }
}

extension SnapshotKey {
    public static let paymentsToConfirm = SnapshotKey("payments.claimed")
    public static func paymentReview(_ id: UUID) -> SnapshotKey { SnapshotKey("payments.review.\(id.lowercased)") }
    public static func paymentEvidence(_ id: UUID) -> SnapshotKey { SnapshotKey("payments.evidence.\(id.lowercased)") }
    public static func invoiceNumber(_ id: UUID) -> SnapshotKey { SnapshotKey("payments.invoice.\(id.lowercased)") }
}

extension OwnerAPI {
    /// Customer payments waiting to be confirmed (CLAIMED), newest first.
    public static func paymentsToConfirm(pageSize: Int = 100) -> APIRequest<Page<CustomerPaymentRecordDTO>> {
        .get("\(tenant)/customer-payments", query: paging(1, pageSize) + compact([("status", PaymentReviewText.claimed)]))
    }

    public static func paymentReview(_ id: UUID) -> APIRequest<CustomerPaymentRecordDTO> {
        .get("\(tenant)/customer-payments/\(id.lowercased)")
    }

    /// Confirms (`verified: true`) or rejects a claimed payment; never by the person who recorded it.
    public static func decidePayment(_ id: UUID, confirm: Bool, note: String, idempotencyKey: UUID) throws -> APIRequest<CustomerPaymentRecordDTO> {
        try .mutation(.post, "\(tenant)/customer-payments/\(id.lowercased)/decision",
                      body: SettlementDecisionIn(verified: confirm, note: Optional(note).nonEmpty),
                      idempotencyKey: idempotencyKey)
    }

    public static func paymentEvidence(_ id: UUID) -> APIRequest<[PaymentEvidenceDTO]> {
        .get("\(tenant)/customer-payments/\(id.lowercased)/evidence")
    }

    /// Presigned URL of one evidence photo, fetched on demand only (never cached).
    public static func paymentEvidenceURL(paymentID: UUID, attachmentID: UUID) -> APIRequest<PhotoURLDTO> {
        .get("\(tenant)/customer-payments/\(paymentID.lowercased)/evidence/\(attachmentID.lowercased)/url")
    }

    public static func invoiceNumber(_ id: UUID) -> APIRequest<InvoiceNumberDTO> {
        .get("\(tenant)/hire-invoices/\(id.lowercased)")
    }
}

/// Wording and rules of "Payments to confirm". Identical to Android `PaymentReviewText` (strings doc "Go-live fixes —
/// payments to confirm").
public enum PaymentReviewText {
    public static let section = "Payments to confirm"
    public static let empty = "No customer payments waiting."
    public static let screenTitle = "Customer payment"
    public static let card = "Payment"
    public static let customerFallback = "A customer"
    public static let claimed = "CLAIMED"
    public static let verified = "VERIFIED"
    public static let fieldCustomer = "Customer"
    public static let fieldAmount = "Amount"
    public static let fieldMethod = "Method"
    public static let fieldReference = "Reference"
    public static let fieldCollection = "Collection number"
    public static let fieldReceivedAt = "Received"
    public static let fieldReceivedBy = "Received by"
    public static let fieldRecordedBy = "Recorded by"
    public static let fieldRecordedAt = "Recorded"
    public static let fieldNote = "Note"
    public static let fieldStatus = "Status"
    public static let fieldDecidedBy = "Decided by"
    public static let fieldDecisionNote = "Decision note"
    public static let fieldReversed = "Reversed"
    public static let linksPurchases = "Hours purchases"
    public static let linksInvoices = "Invoices"
    public static let evidence = "Evidence"
    public static let evidenceNone = "No evidence photos attached."
    public static let evidenceFailed = "Evidence photos could not be loaded. Pull to try again."
    public static let decision = "Decision"
    public static let explanation = "Confirm only when the money has been received (bank statement, mobile money record or cash counted). "
        + "Confirmed money reduces what the customer owes. Rejecting releases what it was linked to."
    public static let confirm = "Confirm"
    public static let reject = "Reject"
    public static let cancel = "Cancel"
    public static let confirmTitle = "Confirm this payment?"
    public static let rejectTitle = "Reject this payment?"
    public static let noteOptional = "Note (optional)"
    public static let reasonRequired = "Reason (required)"
    public static let errReasonShort = "Write at least 3 characters."
    public static let confirmed = "Payment confirmed."
    public static let rejected = "Payment rejected."
    public static let own = "You recorded this payment, so someone else must confirm or reject it."
    public static let alreadyDecided = "Someone already decided this payment. Reload to see it."
    public static let noteMin = 3
    public static let noteMax = 1000

    public static func headline(_ p: CustomerPaymentRecordDTO,
                                money: (DecimalString, String) -> String = { OwnerFormat.money($0, currency: $1) }) -> String {
        let name = p.customerName?.trimmingCharacters(in: .whitespacesAndNewlines)
        return "\((name?.isEmpty ?? true) ? customerFallback : name!) paid \(money(p.amount, p.currency))"
    }

    public static func received(_ p: CustomerPaymentRecordDTO, timeZone: TimeZone = .current) -> String {
        "Received \(OwnerFormat.stamp(p.receivedAt, timeZone: timeZone))"
    }

    public static func recordedBy(_ p: CustomerPaymentRecordDTO) -> String? {
        DisplayName.optional(p.recordedByName, id: p.recordedBy).map { "Recorded by \($0)" }
    }

    public static func method(_ raw: String) -> String {
        switch raw {
        case "CASH": "Cash"
        case "BANK": "Bank transfer"
        case "MOBILE_MONEY": "Mobile money"
        default: OwnerFormat.humanize(raw)
        }
    }

    public static func status(_ raw: String) -> String {
        switch raw {
        case claimed: "Waiting to be confirmed"
        case verified: "Confirmed"
        case "REJECTED": "Rejected"
        default: OwnerFormat.humanize(raw)
        }
    }

    public static func statusTone(_ status: String) -> KPITone {
        switch status {
        case claimed: .warning
        case verified: .good
        case "REJECTED": .critical
        default: .muted
        }
    }

    /// The second line of a row: method and the collection number, else the payer's reference.
    public static func summary(_ p: CustomerPaymentRecordDTO) -> String {
        ([method(p.method), number(p)] as [String?]).compactMap { $0 }.joined(separator: " · ")
    }

    private static func number(_ p: CustomerPaymentRecordDTO) -> String? { p.collectionNumber.nonEmpty ?? p.reference.nonEmpty }

    /// The payment's facts in screen order; empty values left out.
    public static func fields(_ p: CustomerPaymentRecordDTO, timeZone: TimeZone = .current,
                              money: (DecimalString, String) -> String = { OwnerFormat.money($0, currency: $1) }) -> [DecisionField] {
        PendingDecision.fields([(fieldCustomer, DisplayName.optional(p.customerName, id: p.customerID)),
                                (fieldAmount, money(p.amount, p.currency)),
                                (fieldMethod, method(p.method)),
                                (fieldReference, p.reference),
                                (fieldCollection, p.collectionNumber),
                                (fieldReceivedAt, OwnerFormat.stamp(p.receivedAt, timeZone: timeZone)),
                                (fieldReceivedBy, DisplayName.optional(p.receivedByStaffName, id: p.receivedByStaffID)),
                                (fieldRecordedBy, DisplayName.optional(p.recordedByName, id: p.recordedBy)),
                                (fieldRecordedAt, OwnerFormat.stamp(p.recordedAt, timeZone: timeZone)),
                                (fieldNote, p.note)])
    }

    /// Who decided it and why, once decided.
    public static func decisionFields(_ p: CustomerPaymentRecordDTO, timeZone: TimeZone = .current) -> [DecisionField] {
        PendingDecision.fields([(fieldDecidedBy, DisplayName.optional(p.verifiedByName, id: p.verifiedBy)),
                                (fieldDecisionNote, p.decisionNote),
                                (fieldReversed, p.reversedAt.map { OwnerFormat.stamp($0, timeZone: timeZone) })])
    }

    /// "HP-9 · TZS 50,000.00".
    public static func link(number: String, money: String) -> String { "\(number) · \(money)" }

    /// The purchases the payment is linked to, as "number · amount" with the purchase id.
    public static func purchases(_ p: CustomerPaymentRecordDTO,
                                 money: (DecimalString, String) -> String = { OwnerFormat.money($0, currency: $1) }) -> [(id: UUID, text: String)] {
        (p.purchaseLinks ?? []).map { ($0.purchaseID, link(number: $0.purchaseNumber, money: money($0.amount, p.currency))) }
    }

    /// Allocations still in force (released ones are left out).
    public static func activeAllocations(_ p: CustomerPaymentRecordDTO) -> [PaymentAllocationDTO] {
        (p.allocations ?? []).filter { $0.releasedAt == nil }
    }

    /// "Number · amount" of each invoice the payment is set against (the short id until a number is known).
    public static func invoices(_ p: CustomerPaymentRecordDTO, numbers: [UUID: String],
                                money: (DecimalString, String) -> String = { OwnerFormat.money($0, currency: $1) }) -> [String] {
        activeAllocations(p).map { link(number: numbers[$0.invoiceID] ?? DisplayName.or(nil, id: $0.invoiceID), money: money($0.amount, p.currency)) }
    }

    public static func photo(_ n: Int) -> String { "photo \(n)" }

    /// A rejection must say why (at least 3 characters); confirming takes an optional note.
    public static func canDecide(confirm: Bool, note: String) -> Bool {
        let length = note.trimmingCharacters(in: .whitespacesAndNewlines).count
        return length <= noteMax && (confirm || length >= noteMin)
    }

    /// The recorder can never decide their own payment (segregation of duties; the server refuses it too).
    public static func isOwn(_ p: CustomerPaymentRecordDTO, userID: UUID?) -> Bool { userID != nil && p.recordedBy == userID }

    /// The decision section is offered only while the payment waits and was not reversed.
    public static func decidable(_ p: CustomerPaymentRecordDTO) -> Bool { p.status == claimed && p.reversedAt == nil }

    public static func done(confirm: Bool) -> String { confirm ? confirmed : rejected }

    /// Codes after which the payment must be reloaded (someone else decided it).
    public static func needsReload(_ error: any Error) -> Bool { (error as? APIError)?.code == "PAYMENT_ALREADY_DECIDED" }

    public static func message(for error: any Error) -> String {
        switch (error as? APIError)?.code {
        case "SEGREGATION_OF_DUTIES": own
        case "PAYMENT_ALREADY_DECIDED": alreadyDecided
        default: DecisionErrorText.message(for: error)
        }
    }
}
