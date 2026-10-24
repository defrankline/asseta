import Foundation

// Read DTOs (and the two decision bodies) the Owner app uses for jobs, tracking alerts, approvals,
// investigation cases and meter evidence (`JobSummaryDto`, `AlertDto`, `ApprovalRequestDto`,
// `AnomalyCaseDto`, `AnomalyCaseDetailDto`, `MeterCaptureDto`, `PhotoUrlDto`).

// MARK: - Jobs

public struct JobChargeLineDTO: Codable, Hashable, Sendable {
    public let kind: String
    public let description: String
    public let quantity: DecimalString
    public let unitPrice: DecimalString
    public let amount: DecimalString

    enum CodingKeys: String, CodingKey { case kind, description, quantity, unitPrice = "unit_price", amount }
}

public struct JobChargesDTO: Codable, Hashable, Sendable {
    public let currency: String
    public let lines: [JobChargeLineDTO]
    public let subtotal: DecimalString
    public let discountTotal: DecimalString
    public let taxTotal: DecimalString
    public let total: DecimalString

    enum CodingKeys: String, CodingKey {
        case currency, lines, subtotal, discountTotal = "discount_total", taxTotal = "tax_total", total
    }
}

public struct JobSummaryDTO: Codable, Hashable, Sendable {
    public let job: JobDTO
    public let openingReading: DecimalString?
    public let closingReading: DecimalString?
    public let meterHours: DecimalString?
    public let nonbillableHours: DecimalString
    public let standbyHours: DecimalString?
    public let billableHours: DecimalString?
    public let openExceptions: Int
    public let blockingExceptions: Int
    public let billingReady: Bool
    public let charges: JobChargesDTO?
    public let policyVersion: String

    enum CodingKeys: String, CodingKey {
        case job, charges
        case openingReading = "opening_reading", closingReading = "closing_reading", meterHours = "meter_hours"
        case nonbillableHours = "nonbillable_hours", standbyHours = "standby_hours", billableHours = "billable_hours"
        case openExceptions = "open_exceptions", blockingExceptions = "blocking_exceptions"
        case billingReady = "billing_ready", policyVersion = "policy_version"
    }
}

// MARK: - Alerts

public struct AlertSeverity: OpenStringEnum {
    public let rawValue: String
    public init(rawValue: String) { self.rawValue = rawValue }

    public static let info = AlertSeverity(rawValue: "INFO")
    public static let warning = AlertSeverity(rawValue: "WARNING")
    public static let critical = AlertSeverity(rawValue: "CRITICAL")

    /// Higher is more urgent; unknown values rank with WARNING so they are not hidden.
    public var rank: Int {
        switch self {
        case .critical: 3
        case .info: 1
        default: 2
        }
    }
}

public struct AlertStatus: OpenStringEnum {
    public let rawValue: String
    public init(rawValue: String) { self.rawValue = rawValue }

    public static let open = AlertStatus(rawValue: "OPEN")
    public static let acknowledged = AlertStatus(rawValue: "ACKNOWLEDGED")
    public static let resolved = AlertStatus(rawValue: "RESOLVED")
    public static let superseded = AlertStatus(rawValue: "SUPERSEDED")

    /// Closed alerts accept no further action (the server answers `ALERT_CLOSED`).
    public var isClosed: Bool { self == .resolved || self == .superseded }
}

public struct AlertDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let machineID: UUID?
    public let trackerID: UUID?
    public let alertType: String
    public let severity: AlertSeverity
    public let status: AlertStatus
    public let eventTime: Date
    public let title: String
    public let evidence: JSONValue
    public let policyVersion: String?
    public let createdAt: Date
    public let acknowledgedAt: Date?
    public let resolvedAt: Date?
    public let resolutionNote: String?

    enum CodingKeys: String, CodingKey {
        case id, machineID = "machine_id", trackerID = "tracker_id", alertType = "alert_type", severity, status
        case eventTime = "event_time", title, evidence, policyVersion = "policy_version", createdAt = "created_at"
        case acknowledgedAt = "acknowledged_at", resolvedAt = "resolved_at", resolutionNote = "resolution_note"
    }
}

public enum AlertAction: String, Codable, Sendable { case acknowledge = "ACKNOWLEDGE", resolve = "RESOLVE" }

public struct AlertActionIn: Codable, Hashable, Sendable {
    public let action: AlertAction
    public let note: String?

    public init(action: AlertAction, note: String?) {
        self.action = action
        self.note = note
    }
}

// MARK: - Approvals

public struct ApprovalStatus: OpenStringEnum {
    public let rawValue: String
    public init(rawValue: String) { self.rawValue = rawValue }

    public static let pending = ApprovalStatus(rawValue: "PENDING")
    public static let approved = ApprovalStatus(rawValue: "APPROVED")
    public static let rejected = ApprovalStatus(rawValue: "REJECTED")
}

public struct ApprovalRequestDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let subjectType: String
    public let subjectID: UUID
    public let amount: DecimalString
    public let currency: String
    public let reason: String
    public let policyVersion: String
    public let status: ApprovalStatus
    public let requestedBy: UUID?
    public let requestedAt: Date
    public let decidedBy: UUID?
    public let decidedAt: Date?
    public let decisionNote: String?

    enum CodingKeys: String, CodingKey {
        case id, subjectType = "subject_type", subjectID = "subject_id", amount, currency, reason
        case policyVersion = "policy_version", status, requestedBy = "requested_by", requestedAt = "requested_at"
        case decidedBy = "decided_by", decidedAt = "decided_at", decisionNote = "decision_note"
    }
}

public struct ApprovalDecisionIn: Codable, Hashable, Sendable {
    public let approve: Bool
    public let note: String?

    public init(approve: Bool, note: String?) {
        self.approve = approve
        self.note = note
    }
}

// MARK: - Investigation cases (read-only in the Owner app)

public struct CaseStatus: OpenStringEnum {
    public let rawValue: String
    public init(rawValue: String) { self.rawValue = rawValue }

    public static let open = CaseStatus(rawValue: "OPEN")
    public static let inReview = CaseStatus(rawValue: "IN_REVIEW")
    public static let resolved = CaseStatus(rawValue: "RESOLVED")
}

public struct AnomalyCaseDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let caseNumber: String
    public let title: String
    public let subjectType: String
    public let subjectID: UUID
    public let machineID: UUID?
    public let jobID: UUID?
    public let severity: AlertSeverity
    public let status: CaseStatus
    public let assigneeName: String?
    public let openedAt: Date
    public let lastSignalAt: Date
    public let resolvedAt: Date?
    public let latestOutcome: String?
    public let signalCount: Int?
    public let policyVersion: String
    public let version: Int

    enum CodingKeys: String, CodingKey {
        case id, caseNumber = "case_number", title, subjectType = "subject_type", subjectID = "subject_id"
        case machineID = "machine_id", jobID = "job_id", severity, status, assigneeName = "assignee_name"
        case openedAt = "opened_at", lastSignalAt = "last_signal_at", resolvedAt = "resolved_at"
        case latestOutcome = "latest_outcome", signalCount = "signal_count", policyVersion = "policy_version", version
    }
}

public struct CaseSignalDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let sourceType: String
    public let sourceID: UUID
    public let code: String
    public let severity: AlertSeverity
    public let observedAt: Date
    public let evidence: JSONValue
    public let linkedAt: Date

    enum CodingKeys: String, CodingKey {
        case id, sourceType = "source_type", sourceID = "source_id", code, severity, observedAt = "observed_at"
        case evidence, linkedAt = "linked_at"
    }
}

public struct CaseNoteDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let kind: String
    public let body: String
    public let authorName: String?
    public let createdAt: Date

    enum CodingKeys: String, CodingKey { case id, kind, body, authorName = "author_name", createdAt = "created_at" }
}

public struct CaseOutcomeDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let sequence: Int
    public let outcome: String
    public let explanation: String
    public let decidedByName: String?
    public let decidedAt: Date

    enum CodingKeys: String, CodingKey {
        case id, sequence, outcome, explanation, decidedByName = "decided_by_name", decidedAt = "decided_at"
    }
}

public struct AnomalyCaseDetailDTO: Codable, Hashable, Sendable {
    public let `case`: AnomalyCaseDTO
    public let signals: [CaseSignalDTO]
    public let notes: [CaseNoteDTO]
    public let outcomes: [CaseOutcomeDTO]
}

// MARK: - Meter evidence

public struct MeterCaptureDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    /// Nil for a DAILY reading outside a job.
    public let jobID: UUID?
    public let machineID: UUID
    /// Kept as text so a reading kind added later never breaks a list.
    public let kind: String
    public let captureMode: String
    public let reading: DecimalString
    public let ocrValue: DecimalString?
    public let ocrConfidence: Double?
    public let manuallyCorrected: Bool
    public let photoAttachmentID: UUID?
    public let gpsStatus: GpsStatus
    public let latitude: Double?
    public let longitude: Double?
    public let capturedAt: Date
    public let receivedAt: Date
    public let state: String

    enum CodingKeys: String, CodingKey {
        case id, jobID = "job_id", machineID = "machine_id", kind, captureMode = "capture_mode", reading
        case ocrValue = "ocr_value", ocrConfidence = "ocr_confidence", manuallyCorrected = "manually_corrected"
        case photoAttachmentID = "photo_attachment_id", gpsStatus = "gps_status", latitude, longitude
        case capturedAt = "captured_at", receivedAt = "received_at", state
    }
}

/// A short-lived presigned download URL; never cached.
public struct PhotoURLDTO: Codable, Hashable, Sendable {
    public let url: URL
    public let expiresInSeconds: Int

    enum CodingKeys: String, CodingKey { case url, expiresInSeconds = "expires_in_seconds" }
}
