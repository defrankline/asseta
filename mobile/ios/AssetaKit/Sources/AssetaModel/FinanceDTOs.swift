import Foundation

// Gate 5 field finance: typed views of the synced finance data and the payloads of the EXPENSE,
// CASH_COLLECTION, CASH_HANDOVER and FUEL_EVENT operations. Shapes follow `ExpenseCategoryDto`,
// `CashCustodyBalanceDto`, `ExpenseCapturePolicy`, `ExpenseIn` (+ `receipt_upload_ids`),
// `CashCollectionIn`, `CashHandoverIn` and `FuelEventIn` in `contracts/openapi.json`.
// Money, litres, prices and readings are `DecimalString` on the wire: never a JSON number, never Double.

public struct ExpenseCategoryDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let code: String
    public let name: String
    public let isActive: Bool

    enum CodingKeys: String, CodingKey { case id, code, name, isActive = "is_active" }
}

/// The supervisor's server-computed cash custody in one currency (current, not a delta).
public struct CashCustodyBalanceDTO: Codable, Hashable, Sendable {
    public let staffMemberID: UUID
    public let currency: String
    /// floats + collections − approved spending − verified handovers.
    public let outstanding: DecimalString
    public let claimedUnverifiedHandovers: DecimalString
    public let pendingSpending: DecimalString
    public let asOf: Date
    /// Employee accountability (DEC-032 Phase 4): absent from older payloads.
    public var inTransitOut: DecimalString? = nil
    public var pendingFloats: DecimalString? = nil
    public var approvedRetention: DecimalString? = nil

    public init(staffMemberID: UUID, currency: String, outstanding: DecimalString,
                claimedUnverifiedHandovers: DecimalString, pendingSpending: DecimalString, asOf: Date) {
        self.staffMemberID = staffMemberID
        self.currency = currency
        self.outstanding = outstanding
        self.claimedUnverifiedHandovers = claimedUnverifiedHandovers
        self.pendingSpending = pendingSpending
        self.asOf = asOf
    }

    enum CodingKeys: String, CodingKey {
        case currency, outstanding
        case staffMemberID = "staff_member_id", claimedUnverifiedHandovers = "claimed_unverified_handovers"
        case pendingSpending = "pending_spending", asOf = "as_of"
        case inTransitOut = "in_transit_out", pendingFloats = "pending_floats", approvedRetention = "approved_retention"
    }
}

/// `EXPENSE_CAPTURE` policy values as delivered in a policy snapshot. Thresholds are in the
/// tenant's base currency; another currency always needs a receipt and an approval.
public struct ExpenseCapturePolicy: Codable, Hashable, Sendable {
    public let receiptRequiredAbove: DecimalString
    public let gpsRequired: Bool
    public let gpsMaxAccuracyM: Double
    public let autoApproveLimit: DecimalString

    public init(receiptRequiredAbove: Decimal, gpsRequired: Bool, gpsMaxAccuracyM: Double, autoApproveLimit: Decimal) {
        self.receiptRequiredAbove = DecimalString(receiptRequiredAbove)
        self.gpsRequired = gpsRequired
        self.gpsMaxAccuracyM = gpsMaxAccuracyM
        self.autoApproveLimit = DecimalString(autoApproveLimit)
    }

    enum CodingKeys: String, CodingKey {
        case receiptRequiredAbove = "receipt_required_above", gpsRequired = "gps_required"
        case gpsMaxAccuracyM = "gps_max_accuracy_m", autoApproveLimit = "auto_approve_limit"
    }
}

public enum ExpensePaidFrom: String, Codable, Sendable, CaseIterable {
    case cashCustody = "CASH_CUSTODY", company = "COMPANY"
    /// Paid from a petty cash fund (DEC-033, OP_PETTY_CASH): needs `petty_cash_fund_id`.
    case pettyCash = "PETTY_CASH"
}

public enum FuelEventType: String, Codable, Sendable, CaseIterable {
    case purchase = "PURCHASE", issue = "ISSUE", usage = "USAGE"
}

/// `EXPENSE` operation payload. Receipts are referenced by their resumable upload session ids
/// (`receipt_upload_ids`), written into the stored payload when each upload completes.
public struct ExpensePayload: Codable, Hashable, Sendable {
    public let clientID: UUID
    public let categoryID: UUID
    public let description: String
    public let amount: DecimalString
    public let currency: String?
    public let incurredAt: Date
    public let paidFrom: ExpensePaidFrom
    public let supplier: String?
    public let machineID: UUID?
    public let jobID: UUID?
    public let gps: GpsPayload
    public let deviceID: String
    public let receiptUploadIDs: [UUID]
    /// PETTY_CASH only: the fund that paid and, optionally, the advance of that fund given to me.
    public let pettyCashFundID: UUID?
    public let pettyCashAdvanceID: UUID?

    public init(clientID: UUID, categoryID: UUID, description: String, amount: Decimal, currency: String?,
                incurredAt: Date, paidFrom: ExpensePaidFrom, supplier: String?, machineID: UUID?, jobID: UUID?,
                gps: GpsPayload, deviceID: String, receiptUploadIDs: [UUID] = [], pettyCashFundID: UUID? = nil,
                pettyCashAdvanceID: UUID? = nil) {
        self.pettyCashFundID = pettyCashFundID
        self.pettyCashAdvanceID = pettyCashAdvanceID
        self.clientID = clientID
        self.categoryID = categoryID
        self.description = description
        self.amount = DecimalString(amount)
        self.currency = currency
        self.incurredAt = incurredAt
        self.paidFrom = paidFrom
        self.supplier = supplier
        self.machineID = machineID
        self.jobID = jobID
        self.gps = gps
        self.deviceID = deviceID
        self.receiptUploadIDs = receiptUploadIDs
    }

    enum CodingKeys: String, CodingKey {
        case description, amount, currency, supplier, gps
        case clientID = "client_id", categoryID = "category_id", incurredAt = "incurred_at", paidFrom = "paid_from"
        case machineID = "machine_id", jobID = "job_id", deviceID = "device_id", receiptUploadIDs = "receipt_upload_ids"
        case pettyCashFundID = "petty_cash_fund_id", pettyCashAdvanceID = "petty_cash_advance_id"
    }
}

/// `CASH_COLLECTION`: cash received from a customer into the supervisor's own custody.
public struct CashCollectionPayload: Codable, Hashable, Sendable {
    public let clientID: UUID
    public let customerID: UUID
    public let amount: DecimalString
    public let currency: String?
    public let receivedAt: Date
    public let reference: String?
    public let note: String?

    /// The custodian who holds the cash when a recorder records for someone else (nil = the recorder).
    public let staffMemberID: UUID?
    /// CASH_DETAILS_V2: the hours purchase this cash pays for (its id, or the client id of a sale still in the outbox).
    public let purchaseID: UUID?
    /// SYNC_OPEN_INVOICES: the invoice this cash pays for (nil = key omitted, today's payload).
    public let allocations: [CollectionAllocation]?

    public init(clientID: UUID, customerID: UUID, amount: Decimal, currency: String?, receivedAt: Date,
                reference: String?, note: String?, staffMemberID: UUID? = nil, purchaseID: UUID? = nil,
                allocations: [CollectionAllocation]? = nil) {
        self.clientID = clientID
        self.customerID = customerID
        self.amount = DecimalString(amount)
        self.currency = currency
        self.receivedAt = receivedAt
        self.reference = reference
        self.note = note
        self.staffMemberID = staffMemberID
        self.purchaseID = purchaseID
        self.allocations = allocations
    }

    enum CodingKeys: String, CodingKey {
        case amount, currency, reference, note, allocations
        case clientID = "client_id", customerID = "customer_id", receivedAt = "received_at"
        case staffMemberID = "staff_member_id", purchaseID = "purchase_id"
    }
}

/// One invoice a collection pays (`HireAllocationIn`).
public struct CollectionAllocation: Codable, Hashable, Sendable {
    public let invoiceID: UUID
    public let amount: DecimalString

    public init(invoiceID: UUID, amount: Decimal) {
        self.invoiceID = invoiceID
        self.amount = DecimalString(amount)
    }

    enum CodingKeys: String, CodingKey { case amount, invoiceID = "invoice_id" }
}

/// `CASH_HANDOVER`: cash handed to the office (CLAIMED until finance verifies it). With REMITTANCE_DETAILS_V1 it
/// also says how the money reached the company (`method`), the company account it was paid into and evidence
/// photos: resumable uploads (purpose REMITTANCE_EVIDENCE) whose session ids are appended to `evidence_upload_ids`
/// when complete (the server DEFERs the op with ATTACHMENT_PENDING until then). The new keys are only written when
/// set, so a server without the capability receives today's payload.
public struct CashHandoverPayload: Codable, Hashable, Sendable {
    public let clientID: UUID
    public let amount: DecimalString
    public let currency: String?
    public let handedAt: Date
    public let reference: String?
    public let note: String?

    /// The custodian who remits when a recorder records for someone else (nil = the recorder).
    public let staffMemberID: UUID?
    public let method: RemittanceMethod?
    public let depositAccountID: UUID?
    /// Nil = no evidence photos (key omitted); otherwise starts empty and fills as uploads complete.
    public let evidenceUploadIDs: [UUID]?
    /// CASH_DETAILS_V2: why less than the expected balance is being remitted (tenant reason and/or free text).
    public let partialReason: String?
    public let partialReasonID: UUID?

    public init(clientID: UUID, amount: Decimal, currency: String?, handedAt: Date, reference: String?, note: String?,
                staffMemberID: UUID? = nil, method: RemittanceMethod? = nil, depositAccountID: UUID? = nil,
                evidenceUploadIDs: [UUID]? = nil, partialReason: String? = nil, partialReasonID: UUID? = nil) {
        self.clientID = clientID
        self.amount = DecimalString(amount)
        self.currency = currency
        self.handedAt = handedAt
        self.reference = reference
        self.note = note
        self.staffMemberID = staffMemberID
        self.method = method
        self.depositAccountID = depositAccountID
        self.evidenceUploadIDs = evidenceUploadIDs
        self.partialReason = partialReason
        self.partialReasonID = partialReasonID
    }

    enum CodingKeys: String, CodingKey {
        case amount, currency, reference, note, method, clientID = "client_id", handedAt = "handed_at"
        case staffMemberID = "staff_member_id", depositAccountID = "deposit_account_id"
        case evidenceUploadIDs = "evidence_upload_ids", partialReason = "partial_reason", partialReasonID = "partial_reason_id"
    }
}

public struct FuelEventPayload: Codable, Hashable, Sendable {
    public let clientID: UUID
    public let eventType: FuelEventType
    public let litres: DecimalString
    public let unitPrice: DecimalString?
    public let currency: String?
    public let machineID: UUID?
    public let jobID: UUID?
    public let meterReading: DecimalString?
    public let supplier: String?
    public let occurredAt: Date
    public let note: String?

    public init(clientID: UUID, eventType: FuelEventType, litres: Decimal, unitPrice: Decimal?, currency: String?,
                machineID: UUID?, jobID: UUID?, meterReading: Decimal?, supplier: String?, occurredAt: Date,
                note: String?) {
        self.clientID = clientID
        self.eventType = eventType
        self.litres = DecimalString(litres)
        self.unitPrice = unitPrice.map(DecimalString.init)
        self.currency = currency
        self.machineID = machineID
        self.jobID = jobID
        self.meterReading = meterReading.map(DecimalString.init)
        self.supplier = supplier
        self.occurredAt = occurredAt
        self.note = note
    }

    enum CodingKeys: String, CodingKey {
        case litres, currency, supplier, note
        case clientID = "client_id", eventType = "event_type", unitPrice = "unit_price", machineID = "machine_id"
        case jobID = "job_id", meterReading = "meter_reading", occurredAt = "occurred_at"
    }
}
