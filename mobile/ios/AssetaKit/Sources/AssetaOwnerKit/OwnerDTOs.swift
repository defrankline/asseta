import AssetaModel
import Foundation

// Owner-only read DTOs the Android Owner app already shows (`MachineDto`, `ExpenseDto`, `AcknowledgementDto` in
// `contracts/openapi.json`). Only the fields the Owner screens use are decoded.

/// `GET /tenant/machines/{id}`: the register entry behind a fleet machine (make, model, ownership).
public struct OwnerMachineDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let assetCode: String
    public let name: String
    public let status: String
    public let ownership: String
    public let manufacturer: String?
    public let model: String?
    public let yearOfManufacture: Int?

    enum CodingKeys: String, CodingKey {
        case id, name, status, ownership, manufacturer, model
        case assetCode = "asset_code", yearOfManufacture = "year_of_manufacture"
    }

    /// "Caterpillar 320 2019", or nil when nothing is known.
    public var modelLine: String? {
        let parts = [manufacturer, model, yearOfManufacture.map(String.init)].compactMap { $0 }
        return parts.isEmpty ? nil : parts.joined(separator: " ")
    }
}

/// `GET /tenant/expenses/{id}` (the expense behind an approval, fetched on demand) and `GET /tenant/expenses`
/// (job detail and Field spend lists, cached).
public struct ExpenseDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let amount: DecimalString
    public let currency: String
    public let description: String
    public let status: String
    public let incurredAt: Date
    public let paidFrom: String
    public let supplier: String?
    public let receiptAttachmentIDs: [UUID]
    public let decisionNote: String?
    public let jobID: UUID?
    public let machineID: UUID?
    public let custodianStaffID: UUID?
    public let receiptRequired: Bool

    enum CodingKeys: String, CodingKey {
        case id, amount, currency, description, status, supplier
        case incurredAt = "incurred_at", paidFrom = "paid_from", receiptAttachmentIDs = "receipt_attachment_ids"
        case decisionNote = "decision_note", jobID = "job_id", machineID = "machine_id"
        case custodianStaffID = "custodian_staff_id", receiptRequired = "receipt_required"
    }

    public init(from decoder: any Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(UUID.self, forKey: .id)
        amount = try c.decode(DecimalString.self, forKey: .amount)
        currency = try c.decode(String.self, forKey: .currency)
        description = try c.decode(String.self, forKey: .description)
        status = try c.decode(String.self, forKey: .status)
        incurredAt = try c.decode(Date.self, forKey: .incurredAt)
        paidFrom = try c.decode(String.self, forKey: .paidFrom)
        supplier = try c.decodeIfPresent(String.self, forKey: .supplier)
        receiptAttachmentIDs = try c.decodeIfPresent([UUID].self, forKey: .receiptAttachmentIDs) ?? []
        decisionNote = try c.decodeIfPresent(String.self, forKey: .decisionNote)
        jobID = try c.decodeIfPresent(UUID.self, forKey: .jobID)
        machineID = try c.decodeIfPresent(UUID.self, forKey: .machineID)
        custodianStaffID = try c.decodeIfPresent(UUID.self, forKey: .custodianStaffID)
        receiptRequired = try c.decodeIfPresent(Bool.self, forKey: .receiptRequired) ?? false
    }
}

/// `GET /tenant/jobs/{id}/acknowledgements`: the customer's sign-off of the hours.
public struct AcknowledgementDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let method: String
    public let signerName: String
    public let capturedAt: Date
    public let acknowledgedHours: DecimalString?
    public let signatureAttachmentID: UUID?

    enum CodingKeys: String, CodingKey {
        case id, method, signerName = "signer_name", capturedAt = "captured_at"
        case acknowledgedHours = "acknowledged_hours", signatureAttachmentID = "signature_attachment_id"
    }
}

/// `GET /tenant/jobs/{id}/activities`: the job's work log (work, standby, downtime, …).
public struct ActivityDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let activityType: String
    public let startedAt: Date
    public let endedAt: Date?
    public let billable: Bool
    public let note: String?

    enum CodingKeys: String, CodingKey {
        case id, billable, note
        case activityType = "activity_type", startedAt = "started_at", endedAt = "ended_at"
    }
}

/// `GET /tenant/fuel-events`: fuel bought, issued or used (litres exact, cost in the event's currency).
public struct FuelEventDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let eventType: String
    public let litres: DecimalString
    public let unitPrice: DecimalString?
    public let attributedCost: DecimalString
    public let currency: String
    public let machineID: UUID?
    public let jobID: UUID?
    public let expenseID: UUID?
    public let meterReading: DecimalString?
    public let supplier: String?
    public let occurredAt: Date
    public let note: String?
    public let source: String?

    enum CodingKeys: String, CodingKey {
        case id, litres, currency, supplier, note, source
        case eventType = "event_type", unitPrice = "unit_price", attributedCost = "attributed_cost"
        case machineID = "machine_id", jobID = "job_id", expenseID = "expense_id", meterReading = "meter_reading"
        case occurredAt = "occurred_at"
    }
}

/// `GET /tenant/exceptions`: a meter exception raised on a reading.
public struct MeterExceptionDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let jobID: UUID?
    public let machineID: UUID
    public let exceptionType: String
    public let severity: String
    public let blocking: Bool
    public let status: String
    public let reviewNote: String?
    public let reviewedAt: Date?
    public let createdAt: Date
    /// What was measured (shown on the exception detail).
    public let evidence: JSONValue?

    enum CodingKeys: String, CodingKey {
        case id, severity, blocking, status, evidence
        case jobID = "job_id", machineID = "machine_id", exceptionType = "exception_type", reviewNote = "review_note"
        case reviewedAt = "reviewed_at", createdAt = "created_at"
    }
}

/// `GET /tenant/meter-resets`: a request to restart a machine's meter from a new reading (decided by someone else).
public struct MeterResetDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let machineID: UUID
    public let oldReading: DecimalString
    public let newReading: DecimalString
    public let effectiveAt: Date
    public let reason: String
    public let evidenceAttachmentID: UUID?
    public let status: String
    public let requestedBy: UUID?
    public let decidedAt: Date?

    enum CodingKeys: String, CodingKey {
        case id, reason, status
        case machineID = "machine_id", oldReading = "old_reading", newReading = "new_reading", effectiveAt = "effective_at"
        case evidenceAttachmentID = "evidence_attachment_id", requestedBy = "requested_by", decidedAt = "decided_at"
    }
}

/// `POST /tenant/meter-resets/{id}/decision`: `EXPLAINED` approves the reset, `CONFIRMED` rejects it.
public struct MeterResetDecisionIn: Encodable, Sendable {
    public let outcome: String
    public let note: String
}

/// `GET /tenant/cash/supervisor-summary`: one custodian x currency over a period (dates are tenant-local days).
public struct CashSupervisorSummaryDTO: Codable, Hashable, Sendable, Identifiable {
    public let staffMemberID: UUID
    public let staffName: String
    public let currency: String
    public let periodFrom: String
    public let periodTo: String
    public let opening: DecimalString
    public let floatsIssued: DecimalString
    public let collections: DecimalString
    public let approvedSpending: DecimalString
    public let verifiedHandovers: DecimalString
    public let closingOutstanding: DecimalString
    public let claimedUnverifiedHandovers: DecimalString
    public let pendingSpending: DecimalString
    public let unverifiedCollections: DecimalString

    public var id: String { "\(staffMemberID.uuidString)-\(currency)" }

    enum CodingKeys: String, CodingKey {
        case opening, collections, currency
        case staffMemberID = "staff_member_id", staffName = "staff_name", periodFrom = "period_from"
        case periodTo = "period_to", floatsIssued = "floats_issued", approvedSpending = "approved_spending"
        case verifiedHandovers = "verified_handovers", closingOutstanding = "closing_outstanding"
        case claimedUnverifiedHandovers = "claimed_unverified_handovers", pendingSpending = "pending_spending"
        case unverifiedCollections = "unverified_collections"
    }
}
