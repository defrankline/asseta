import Foundation

// Supervisor inbox (capability SUPERVISOR_INBOX_V1): the caller's own field records as the server
// knows them, delivered by bootstrap/changes in `SyncData.my_*` and upserted by (id, sync_revision).
// Shapes follow `contracts/openapi.json` (`SyncMeterCaptureDto` ... `SyncCashHandoverDto`); every
// contract-required field is mapped (SyncContractTests). Money, litres and readings stay decimal
// strings; unknown enum values are kept as text. Same DTOs as Android `InboxDtos.kt`.

public enum SyncCapability {
    public static let supervisorInbox = "SUPERVISOR_INBOX_V1"
    public static let meterResetRequest = "OP_METER_RESET_REQUEST"
}

/// `ExceptionDto`: a server finding on a reading (type, severity, blocking) and its review.
public struct FindingDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let exceptionType: String
    public let severity: String
    public let blocking: Bool
    public let status: String
    public let machineID: UUID
    public let jobID: UUID?
    public let meterCaptureID: UUID?
    public let policyVersion: String?
    public let reviewNote: String?
    public let reviewedAt: Date?
    public let createdAt: Date
    public let evidence: JSONValue

    enum CodingKeys: String, CodingKey {
        case id, severity, blocking, status, evidence
        case exceptionType = "exception_type", machineID = "machine_id", jobID = "job_id"
        case meterCaptureID = "meter_capture_id", policyVersion = "policy_version", reviewNote = "review_note"
        case reviewedAt = "reviewed_at", createdAt = "created_at"
    }
}

public struct SyncMeterCaptureDTO: Codable, Hashable, Sendable, Identifiable {
    /// The device-generated capture id (also the local capture's id).
    public let id: UUID
    public let jobID: UUID
    public let machineID: UUID
    public let kind: String
    public let captureMode: String
    public let reading: String
    public let state: String
    public let gpsStatus: String
    public let latitude: Double?
    public let longitude: Double?
    public let accuracyM: Double?
    public let locationCapturedAt: Date?
    public let photoAttachmentID: UUID?
    public let photoSHA256: String?
    public let ocrValue: String?
    public let ocrConfidence: Double?
    public let manuallyCorrected: Bool
    public let policyVersion: String
    public let supersedesID: UUID?
    public let trackerComparison: JSONValue?
    public let capturedAt: Date
    public let receivedAt: Date
    public let syncRevision: Int64
    public let reviewStatus: String
    public let findings: [FindingDTO]

    enum CodingKeys: String, CodingKey {
        case id, kind, reading, state, latitude, longitude, findings
        case jobID = "job_id", machineID = "machine_id", captureMode = "capture_mode", gpsStatus = "gps_status"
        case accuracyM = "accuracy_m", locationCapturedAt = "location_captured_at"
        case photoAttachmentID = "photo_attachment_id", photoSHA256 = "photo_sha256", ocrValue = "ocr_value"
        case ocrConfidence = "ocr_confidence", manuallyCorrected = "manually_corrected", policyVersion = "policy_version"
        case supersedesID = "supersedes_id", trackerComparison = "tracker_comparison", capturedAt = "captured_at"
        case receivedAt = "received_at", syncRevision = "sync_revision", reviewStatus = "review_status"
    }

    public init(from decoder: any Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(UUID.self, forKey: .id)
        jobID = try c.decode(UUID.self, forKey: .jobID)
        machineID = try c.decode(UUID.self, forKey: .machineID)
        kind = try c.decode(String.self, forKey: .kind)
        captureMode = try c.decode(String.self, forKey: .captureMode)
        reading = try c.decode(String.self, forKey: .reading)
        state = try c.decode(String.self, forKey: .state)
        gpsStatus = try c.decode(String.self, forKey: .gpsStatus)
        latitude = try c.decodeIfPresent(Double.self, forKey: .latitude)
        longitude = try c.decodeIfPresent(Double.self, forKey: .longitude)
        accuracyM = try c.decodeIfPresent(Double.self, forKey: .accuracyM)
        locationCapturedAt = try c.decodeIfPresent(Date.self, forKey: .locationCapturedAt)
        photoAttachmentID = try c.decodeIfPresent(UUID.self, forKey: .photoAttachmentID)
        photoSHA256 = try c.decodeIfPresent(String.self, forKey: .photoSHA256)
        ocrValue = try c.decodeIfPresent(String.self, forKey: .ocrValue)
        ocrConfidence = try c.decodeIfPresent(Double.self, forKey: .ocrConfidence)
        manuallyCorrected = try c.decode(Bool.self, forKey: .manuallyCorrected)
        policyVersion = try c.decode(String.self, forKey: .policyVersion)
        supersedesID = try c.decodeIfPresent(UUID.self, forKey: .supersedesID)
        let comparison = try c.decodeIfPresent(JSONValue.self, forKey: .trackerComparison)
        trackerComparison = comparison == .null ? nil : comparison
        capturedAt = try c.decode(Date.self, forKey: .capturedAt)
        receivedAt = try c.decode(Date.self, forKey: .receivedAt)
        syncRevision = try c.decode(Int64.self, forKey: .syncRevision)
        reviewStatus = try c.decodeIfPresent(String.self, forKey: .reviewStatus) ?? "NONE"
        findings = try c.decodeIfPresent([FindingDTO].self, forKey: .findings) ?? []
    }
}

public struct SyncMeterResetDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let machineID: UUID
    public let oldReading: String
    public let newReading: String
    public let effectiveAt: Date
    public let reason: String
    public let status: String
    public let evidenceAttachmentID: UUID?
    public let requestedBy: UUID?
    public let decidedBy: UUID?
    public let decidedAt: Date?
    public let createdAt: Date
    public let syncRevision: Int64

    enum CodingKeys: String, CodingKey {
        case id, reason, status
        case machineID = "machine_id", oldReading = "old_reading", newReading = "new_reading", effectiveAt = "effective_at"
        case evidenceAttachmentID = "evidence_attachment_id", requestedBy = "requested_by", decidedBy = "decided_by"
        case decidedAt = "decided_at", createdAt = "created_at", syncRevision = "sync_revision"
    }
}

public struct SyncJobActivityDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let jobID: UUID
    public let clientID: UUID
    public let activityType: String
    public let startedAt: Date
    public let endedAt: Date?
    public let durationMinutes: Int?
    public let billable: Bool
    public let note: String?
    public let recordedBy: UUID?
    public let receivedAt: Date
    public let syncRevision: Int64

    enum CodingKeys: String, CodingKey {
        case id, billable, note
        case jobID = "job_id", clientID = "client_id", activityType = "activity_type", startedAt = "started_at"
        case endedAt = "ended_at", durationMinutes = "duration_minutes", recordedBy = "recorded_by"
        case receivedAt = "received_at", syncRevision = "sync_revision"
    }
}

public struct SyncAcknowledgementDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let jobID: UUID
    public let clientID: UUID
    public let method: String
    public let signerName: String
    public let signerPhone: String?
    public let acknowledgedHours: String?
    public let signatureAttachmentID: UUID?
    public let capturedAt: Date
    public let recordedBy: UUID?
    public let receivedAt: Date
    public let syncRevision: Int64

    enum CodingKeys: String, CodingKey {
        case id, method
        case jobID = "job_id", clientID = "client_id", signerName = "signer_name", signerPhone = "signer_phone"
        case acknowledgedHours = "acknowledged_hours", signatureAttachmentID = "signature_attachment_id"
        case capturedAt = "captured_at", recordedBy = "recorded_by", receivedAt = "received_at"
        case syncRevision = "sync_revision"
    }
}

public struct SyncExpenseDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let clientID: UUID?
    public let categoryID: UUID
    public let description: String
    public let supplier: String?
    public let amount: String
    public let currency: String
    public let paidFrom: String
    public let status: String
    public let decisionNote: String?
    public let decidedAt: Date?
    public let decidedBy: UUID?
    public let incurredAt: Date
    public let submittedAt: Date
    public let submittedBy: UUID?
    public let custodianStaffID: UUID?
    public let jobID: UUID?
    public let machineID: UUID?
    public let gpsStatus: String?
    public let gpsAccuracyM: Double?
    public let latitude: Double?
    public let longitude: Double?
    public let policyVersion: String
    public let receiptRequired: Bool
    public let source: String
    public let receiptAttachmentIDs: [UUID]
    public let approvalRequestID: UUID?
    public let syncRevision: Int64

    enum CodingKeys: String, CodingKey {
        case id, description, supplier, amount, currency, status, latitude, longitude, source
        case clientID = "client_id", categoryID = "category_id", paidFrom = "paid_from", decisionNote = "decision_note"
        case decidedAt = "decided_at", decidedBy = "decided_by", incurredAt = "incurred_at", submittedAt = "submitted_at"
        case submittedBy = "submitted_by", custodianStaffID = "custodian_staff_id", jobID = "job_id", machineID = "machine_id"
        case gpsStatus = "gps_status", gpsAccuracyM = "gps_accuracy_m", policyVersion = "policy_version"
        case receiptRequired = "receipt_required", receiptAttachmentIDs = "receipt_attachment_ids"
        case approvalRequestID = "approval_request_id", syncRevision = "sync_revision"
    }

    public init(from decoder: any Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(UUID.self, forKey: .id)
        clientID = try c.decodeIfPresent(UUID.self, forKey: .clientID)
        categoryID = try c.decode(UUID.self, forKey: .categoryID)
        description = try c.decode(String.self, forKey: .description)
        supplier = try c.decodeIfPresent(String.self, forKey: .supplier)
        amount = try c.decode(String.self, forKey: .amount)
        currency = try c.decode(String.self, forKey: .currency)
        paidFrom = try c.decode(String.self, forKey: .paidFrom)
        status = try c.decode(String.self, forKey: .status)
        decisionNote = try c.decodeIfPresent(String.self, forKey: .decisionNote)
        decidedAt = try c.decodeIfPresent(Date.self, forKey: .decidedAt)
        decidedBy = try c.decodeIfPresent(UUID.self, forKey: .decidedBy)
        incurredAt = try c.decode(Date.self, forKey: .incurredAt)
        submittedAt = try c.decode(Date.self, forKey: .submittedAt)
        submittedBy = try c.decodeIfPresent(UUID.self, forKey: .submittedBy)
        custodianStaffID = try c.decodeIfPresent(UUID.self, forKey: .custodianStaffID)
        jobID = try c.decodeIfPresent(UUID.self, forKey: .jobID)
        machineID = try c.decodeIfPresent(UUID.self, forKey: .machineID)
        gpsStatus = try c.decodeIfPresent(String.self, forKey: .gpsStatus)
        gpsAccuracyM = try c.decodeIfPresent(Double.self, forKey: .gpsAccuracyM)
        latitude = try c.decodeIfPresent(Double.self, forKey: .latitude)
        longitude = try c.decodeIfPresent(Double.self, forKey: .longitude)
        policyVersion = try c.decode(String.self, forKey: .policyVersion)
        receiptRequired = try c.decode(Bool.self, forKey: .receiptRequired)
        source = try c.decode(String.self, forKey: .source)
        receiptAttachmentIDs = try c.decodeIfPresent([UUID].self, forKey: .receiptAttachmentIDs) ?? []
        approvalRequestID = try c.decodeIfPresent(UUID.self, forKey: .approvalRequestID)
        syncRevision = try c.decode(Int64.self, forKey: .syncRevision)
    }
}

public struct SyncFuelEventDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let clientID: UUID?
    public let eventType: String
    public let litres: String
    public let unitPrice: String?
    public let attributedCost: String
    public let currency: String
    public let machineID: UUID?
    public let jobID: UUID?
    public let expenseID: UUID?
    public let meterReading: String?
    public let supplier: String?
    public let note: String?
    public let occurredAt: Date
    public let recordedBy: UUID?
    public let source: String
    public let syncRevision: Int64

    enum CodingKeys: String, CodingKey {
        case id, litres, currency, supplier, note, source
        case clientID = "client_id", eventType = "event_type", unitPrice = "unit_price", attributedCost = "attributed_cost"
        case machineID = "machine_id", jobID = "job_id", expenseID = "expense_id", meterReading = "meter_reading"
        case occurredAt = "occurred_at", recordedBy = "recorded_by", syncRevision = "sync_revision"
    }
}

/// `HireAllocationDto`: the part of a collection the office allocated to an invoice.
public struct HireAllocationDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let invoiceID: UUID
    public let amount: String
    public let createdAt: Date
    public let releasedAt: Date?
    public let releaseReason: String?

    enum CodingKeys: String, CodingKey {
        case id, amount
        case invoiceID = "invoice_id", createdAt = "created_at", releasedAt = "released_at", releaseReason = "release_reason"
    }
}

public struct SyncCashCollectionDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let clientID: UUID?
    public let customerID: UUID
    public let amount: String
    public let currency: String
    public let method: String
    public let status: String
    public let decisionNote: String?
    public let reference: String?
    public let note: String?
    public let receivedAt: Date
    public let receivedByStaffID: UUID?
    public let recordedAt: Date
    public let recordedBy: UUID?
    public let verifiedAt: Date?
    public let verifiedBy: UUID?
    public let source: String
    public let allocations: [HireAllocationDTO]
    public let syncRevision: Int64

    enum CodingKeys: String, CodingKey {
        case id, amount, currency, method, status, reference, note, source, allocations
        case clientID = "client_id", customerID = "customer_id", decisionNote = "decision_note", receivedAt = "received_at"
        case receivedByStaffID = "received_by_staff_id", recordedAt = "recorded_at", recordedBy = "recorded_by"
        case verifiedAt = "verified_at", verifiedBy = "verified_by", syncRevision = "sync_revision"
    }

    public init(from decoder: any Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(UUID.self, forKey: .id)
        clientID = try c.decodeIfPresent(UUID.self, forKey: .clientID)
        customerID = try c.decode(UUID.self, forKey: .customerID)
        amount = try c.decode(String.self, forKey: .amount)
        currency = try c.decode(String.self, forKey: .currency)
        method = try c.decode(String.self, forKey: .method)
        status = try c.decode(String.self, forKey: .status)
        decisionNote = try c.decodeIfPresent(String.self, forKey: .decisionNote)
        reference = try c.decodeIfPresent(String.self, forKey: .reference)
        note = try c.decodeIfPresent(String.self, forKey: .note)
        receivedAt = try c.decode(Date.self, forKey: .receivedAt)
        receivedByStaffID = try c.decodeIfPresent(UUID.self, forKey: .receivedByStaffID)
        recordedAt = try c.decode(Date.self, forKey: .recordedAt)
        recordedBy = try c.decodeIfPresent(UUID.self, forKey: .recordedBy)
        verifiedAt = try c.decodeIfPresent(Date.self, forKey: .verifiedAt)
        verifiedBy = try c.decodeIfPresent(UUID.self, forKey: .verifiedBy)
        source = try c.decode(String.self, forKey: .source)
        allocations = try c.decodeIfPresent([HireAllocationDTO].self, forKey: .allocations) ?? []
        syncRevision = try c.decode(Int64.self, forKey: .syncRevision)
    }
}

public struct SyncCashHandoverDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let clientID: UUID?
    public let staffMemberID: UUID
    public let amount: String
    public let currency: String
    public let status: String
    public let decisionNote: String?
    public let reference: String?
    public let note: String?
    public let handedAt: Date
    public let recordedAt: Date
    public let recordedBy: UUID?
    public let verifiedAt: Date?
    public let verifiedBy: UUID?
    public let source: String
    public let syncRevision: Int64

    enum CodingKeys: String, CodingKey {
        case id, amount, currency, status, reference, note, source
        case clientID = "client_id", staffMemberID = "staff_member_id", decisionNote = "decision_note"
        case handedAt = "handed_at", recordedAt = "recorded_at", recordedBy = "recorded_by", verifiedAt = "verified_at"
        case verifiedBy = "verified_by", syncRevision = "sync_revision"
    }
}

/// `CashReconciliationDto` (`GET /tenant/cash/custody/me/reconciliation`, online only).
public struct CashReconciliationDTO: Codable, Hashable, Sendable {
    public let staffMemberID: UUID
    public let currency: String
    public let timezone: String
    public let days: [CashReconciliationDayDTO]

    enum CodingKeys: String, CodingKey { case currency, timezone, days, staffMemberID = "staff_member_id" }
}

/// One day: outstanding = opening + floats_issued + collections - approved_spending - verified_handovers.
public struct CashReconciliationDayDTO: Codable, Hashable, Sendable {
    public let day: String
    public let opening: String
    public let floatsIssued: String
    public let collections: String
    public let approvedSpending: String
    public let verifiedHandovers: String
    public let outstanding: String
    public let claimedUnverifiedHandovers: String
    public let pendingSpending: String
    public let unverifiedCollections: String
    public let outstandingIfClaimsVerified: String

    enum CodingKeys: String, CodingKey {
        case day, opening, collections, outstanding
        case floatsIssued = "floats_issued", approvedSpending = "approved_spending", verifiedHandovers = "verified_handovers"
        case claimedUnverifiedHandovers = "claimed_unverified_handovers", pendingSpending = "pending_spending"
        case unverifiedCollections = "unverified_collections", outstandingIfClaimsVerified = "outstanding_if_claims_verified"
    }
}

/// Offline `METER_RESET_REQUEST` payload (`ResetIn` + `evidence_upload_id`, filled in when the photo
/// upload completes).
public struct MeterResetPayload: Codable, Hashable, Sendable {
    public let machineID: UUID
    public let oldReading: String
    public let newReading: String
    public let effectiveAt: Date
    public let reason: String
    public var evidenceUploadID: UUID?

    public init(machineID: UUID, oldReading: String, newReading: String, effectiveAt: Date, reason: String,
                evidenceUploadID: UUID? = nil) {
        self.machineID = machineID
        self.oldReading = oldReading
        self.newReading = newReading
        self.effectiveAt = effectiveAt
        self.reason = reason
        self.evidenceUploadID = evidenceUploadID
    }

    enum CodingKeys: String, CodingKey {
        case reason
        case machineID = "machine_id", oldReading = "old_reading", newReading = "new_reading", effectiveAt = "effective_at"
        case evidenceUploadID = "evidence_upload_id"
    }
}
