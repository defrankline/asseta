import Foundation

// Typed read views of server-owned sync entities (only the fields the Supervisor app shows) and
// the operation payloads the device pushes. Payload shapes follow `MeterCaptureIn`, `GpsIn`,
// `ActivityIn`, `AcknowledgementIn` and the `JOB_TRANSITION` op in `contracts/openapi.json`.

public enum JobStatus: String, Codable, Sendable, CaseIterable {
    case draft = "DRAFT", pendingApproval = "PENDING_APPROVAL", approved = "APPROVED"
    case inProgress = "IN_PROGRESS", completed = "COMPLETED", cancelled = "CANCELLED"
}

public struct JobDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let contractID: UUID
    public let jobNumber: String
    public let machineID: UUID
    public let jobSiteID: UUID?
    public let status: JobStatus
    public let plannedStart: Date
    public let plannedEnd: Date?
    public let startedAt: Date?
    public let completedAt: Date?
    public let version: Int

    enum CodingKeys: String, CodingKey {
        case id, status, version
        case contractID = "contract_id", jobNumber = "job_number", machineID = "machine_id"
        case jobSiteID = "job_site_id", plannedStart = "planned_start", plannedEnd = "planned_end"
        case startedAt = "started_at", completedAt = "completed_at"
    }
}

public struct MachineDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let assetCode: String
    public let name: String
    public let meterDecimalPlaces: Int
    public let version: Int

    enum CodingKeys: String, CodingKey {
        case id, name, version, assetCode = "asset_code", meterDecimalPlaces = "meter_decimal_places"
    }
}

public struct JobSiteDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let code: String
    public let name: String
    public let address: String?
}

public struct CustomerDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let code: String
    public let name: String
}

public struct ContractDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let customerID: UUID
    public let contractNumber: String

    enum CodingKeys: String, CodingKey { case id, customerID = "customer_id", contractNumber = "contract_number" }
}

// MARK: - Policy

public enum CaptureMode: String, Codable, Sendable, CaseIterable {
    case automatic = "AUTOMATIC", manual = "MANUAL"
}

public enum ReadingKind: String, Codable, Sendable, CaseIterable {
    case opening = "OPENING", closing = "CLOSING"
}

/// `METER_CAPTURE` policy values as delivered in a policy snapshot (owner-controlled rules).
public struct MeterCapturePolicy: Codable, Hashable, Sendable {
    public let openingMode: CaptureMode
    public let closingMode: CaptureMode
    public let manualPhotoRequired: Bool
    public let minOCRConfidence: Double
    public let maxRecaptureAttempts: Int
    public let gpsEnforcement: String?
    public let gpsMaxAccuracyM: Double?
    public let gpsMaxAgeSeconds: Int?

    public init(openingMode: CaptureMode, closingMode: CaptureMode, manualPhotoRequired: Bool,
                minOCRConfidence: Double, maxRecaptureAttempts: Int, gpsEnforcement: String? = "SOFT",
                gpsMaxAccuracyM: Double? = nil, gpsMaxAgeSeconds: Int? = nil) {
        self.openingMode = openingMode
        self.closingMode = closingMode
        self.manualPhotoRequired = manualPhotoRequired
        self.minOCRConfidence = minOCRConfidence
        self.maxRecaptureAttempts = maxRecaptureAttempts
        self.gpsEnforcement = gpsEnforcement
        self.gpsMaxAccuracyM = gpsMaxAccuracyM
        self.gpsMaxAgeSeconds = gpsMaxAgeSeconds
    }

    public func mode(for kind: ReadingKind) -> CaptureMode {
        kind == .opening ? openingMode : closingMode
    }

    enum CodingKeys: String, CodingKey {
        case openingMode = "opening_mode", closingMode = "closing_mode"
        case manualPhotoRequired = "manual_photo_required", minOCRConfidence = "min_ocr_confidence"
        case maxRecaptureAttempts = "max_recapture_attempts", gpsEnforcement = "gps_enforcement"
        case gpsMaxAccuracyM = "gps_max_accuracy_m", gpsMaxAgeSeconds = "gps_max_age_seconds"
    }
}

// MARK: - Operation payloads

public enum OperationType: String, Codable, Sendable, CaseIterable {
    case meterCapture = "METER_CAPTURE", jobActivity = "JOB_ACTIVITY"
    case jobAcknowledgement = "JOB_ACKNOWLEDGEMENT", jobTransition = "JOB_TRANSITION"
}

public enum GpsStatus: String, Codable, Sendable, CaseIterable {
    case fix = "FIX", noFix = "NO_FIX", timeout = "TIMEOUT", permissionDenied = "PERMISSION_DENIED"
    case disabled = "DISABLED"
}

/// Result of the mandatory GPS attempt (`GpsIn`). Coordinates exist exactly when `status == .fix`.
public struct GpsPayload: Codable, Hashable, Sendable {
    public let status: GpsStatus
    public let latitude: Double?
    public let longitude: Double?
    public let accuracyM: Double?
    public let capturedAt: Date?
    public let provider: String?

    public static func fix(latitude: Double, longitude: Double, accuracyM: Double, capturedAt: Date,
                           provider: String = "corelocation") -> GpsPayload {
        GpsPayload(status: .fix, latitude: latitude, longitude: longitude, accuracyM: accuracyM,
                   capturedAt: capturedAt, provider: provider)
    }

    /// A failed attempt: no coordinates, ever.
    public static func failed(_ status: GpsStatus, provider: String = "corelocation") -> GpsPayload {
        precondition(status != .fix, "A FIX needs coordinates")
        return GpsPayload(status: status, latitude: nil, longitude: nil, accuracyM: nil, capturedAt: nil,
                          provider: provider)
    }

    enum CodingKeys: String, CodingKey {
        case status, latitude, longitude, provider, accuracyM = "accuracy_m", capturedAt = "captured_at"
    }
}

public struct MeterCapturePayload: Codable, Hashable, Sendable {
    public let id: UUID
    public let jobID: UUID
    public let kind: ReadingKind
    public let captureMode: CaptureMode
    /// Decimal string, never a float.
    public let reading: String
    public let ocrRawText: String?
    public let ocrValue: String?
    public let ocrConfidence: Double?
    public let ocrEngine: String?
    public let photoAttachmentID: UUID?
    public let gps: GpsPayload
    public let deviceID: String
    public let capturedAt: Date
    public let policyVersionIDs: [UUID]

    public init(id: UUID, jobID: UUID, kind: ReadingKind, captureMode: CaptureMode, reading: String,
                ocrRawText: String?, ocrValue: String?, ocrConfidence: Double?, ocrEngine: String?,
                photoAttachmentID: UUID?, gps: GpsPayload, deviceID: String, capturedAt: Date,
                policyVersionIDs: [UUID]) {
        self.id = id
        self.jobID = jobID
        self.kind = kind
        self.captureMode = captureMode
        self.reading = reading
        self.ocrRawText = ocrRawText
        self.ocrValue = ocrValue
        self.ocrConfidence = ocrConfidence
        self.ocrEngine = ocrEngine
        self.photoAttachmentID = photoAttachmentID
        self.gps = gps
        self.deviceID = deviceID
        self.capturedAt = capturedAt
        self.policyVersionIDs = policyVersionIDs
    }

    enum CodingKeys: String, CodingKey {
        case id, kind, reading, gps
        case jobID = "job_id", captureMode = "capture_mode", ocrRawText = "ocr_raw_text", ocrValue = "ocr_value"
        case ocrConfidence = "ocr_confidence", ocrEngine = "ocr_engine", photoAttachmentID = "photo_attachment_id"
        case deviceID = "device_id", capturedAt = "captured_at", policyVersionIDs = "policy_version_ids"
    }
}

public enum ActivityType: String, Codable, Sendable, CaseIterable {
    case work = "WORK", standby = "STANDBY", downtime = "DOWNTIME", mobilization = "MOBILIZATION", note = "NOTE"
}

public struct ActivityPayload: Codable, Hashable, Sendable {
    public let jobID: UUID
    public let clientID: UUID
    public let activityType: ActivityType
    public let startedAt: Date
    public let endedAt: Date?
    public let billable: Bool?
    public let note: String?
    public let deviceID: String?

    public init(jobID: UUID, clientID: UUID = UUID(), activityType: ActivityType, startedAt: Date,
                endedAt: Date?, billable: Bool?, note: String?, deviceID: String?) {
        self.jobID = jobID
        self.clientID = clientID
        self.activityType = activityType
        self.startedAt = startedAt
        self.endedAt = endedAt
        self.billable = billable
        self.note = note
        self.deviceID = deviceID
    }

    enum CodingKeys: String, CodingKey {
        case billable, note
        case jobID = "job_id", clientID = "client_id", activityType = "activity_type", startedAt = "started_at"
        case endedAt = "ended_at", deviceID = "device_id"
    }
}

public enum AcknowledgementMethod: String, Codable, Sendable, CaseIterable {
    case signature = "SIGNATURE", nameConfirmation = "NAME_CONFIRMATION"
}

public struct AcknowledgementPayload: Codable, Hashable, Sendable {
    public let jobID: UUID
    public let clientID: UUID
    public let method: AcknowledgementMethod
    public let signerName: String
    public let signerPhone: String?
    public let signatureAttachmentID: UUID?
    public let acknowledgedHours: String?
    public let capturedAt: Date

    public init(jobID: UUID, clientID: UUID = UUID(), method: AcknowledgementMethod, signerName: String,
                signerPhone: String?, signatureAttachmentID: UUID?, acknowledgedHours: String?, capturedAt: Date) {
        self.jobID = jobID
        self.clientID = clientID
        self.method = method
        self.signerName = signerName
        self.signerPhone = signerPhone
        self.signatureAttachmentID = signatureAttachmentID
        self.acknowledgedHours = acknowledgedHours
        self.capturedAt = capturedAt
    }

    enum CodingKeys: String, CodingKey {
        case method
        case jobID = "job_id", clientID = "client_id", signerName = "signer_name", signerPhone = "signer_phone"
        case signatureAttachmentID = "signature_attachment_id", acknowledgedHours = "acknowledged_hours"
        case capturedAt = "captured_at"
    }
}

public enum JobAction: String, Codable, Sendable { case start = "START", complete = "COMPLETE" }

public struct JobTransitionPayload: Codable, Hashable, Sendable {
    public let jobID: UUID
    public let action: JobAction

    public init(jobID: UUID, action: JobAction) {
        self.jobID = jobID
        self.action = action
    }

    enum CodingKeys: String, CodingKey { case jobID = "job_id", action }
}
