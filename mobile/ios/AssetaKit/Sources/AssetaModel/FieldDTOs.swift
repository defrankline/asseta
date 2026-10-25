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
    // Commercial terms: present on the REST `JobDto` (Owner app), optional so synced entities that
    // omit them still decode.
    public let supervisorID: UUID?
    public let currency: String?
    public let hourlyRate: DecimalString?
    public let minimumHours: DecimalString?
    public let approvedAt: Date?
    /// `RATE_CARD:<id>`, `NEGOTIATED`, `OWNER_APPROVED`, or `PENDING_PRICE` for a field request no rate card covers.
    public let rateSource: String?
    /// What the customer asked for, written by the supervisor who requested the job from the field.
    public let requestNote: String?
    /// The staff member who requested the job from the field (nil for jobs created in the office).
    public let requestedByStaffID: UUID?
    /// Name of the supervisor who requested the job from the field.
    public let requestedByName: String?
    /// Why the job was cancelled (for a field request: why the owner declined it).
    public let cancellationReason: String?

    /// A job a supervisor requested from the field (``OperationType/jobRequest``).
    public var isFieldRequest: Bool { requestedByStaffID != nil || requestNote != nil }
    /// No rate card applied: the approver must set the hourly rate (`PRICE_REQUIRED` otherwise).
    public var needsPrice: Bool { rateSource == JobDTO.pendingPrice }
    public static let pendingPrice = "PENDING_PRICE"

    enum CodingKeys: String, CodingKey {
        case id, status, version
        case contractID = "contract_id", jobNumber = "job_number", machineID = "machine_id"
        case jobSiteID = "job_site_id", plannedStart = "planned_start", plannedEnd = "planned_end"
        case startedAt = "started_at", completedAt = "completed_at"
        case supervisorID = "supervisor_id", currency, hourlyRate = "hourly_rate", minimumHours = "minimum_hours"
        case approvedAt = "approved_at", rateSource = "rate_source", requestNote = "request_note"
        case requestedByStaffID = "requested_by_staff_id", requestedByName = "requested_by_name"
        case cancellationReason = "cancellation_reason"
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
    /// Deltas carry deactivated customers with `is_active=false` (bootstrap ships active ones only).
    public let isActive: Bool?

    enum CodingKeys: String, CodingKey { case id, code, name, isActive = "is_active" }
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
    /// DAILY: a reading outside a job (server capability METER_DAILY_READING); `job_id` may be null.
    case opening = "OPENING", closing = "CLOSING", daily = "DAILY"
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

    /// A DAILY reading carries the same evidence rules as a closing reading (server rule).
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
    case expense = "EXPENSE", cashCollection = "CASH_COLLECTION", cashHandover = "CASH_HANDOVER"
    case fuelEvent = "FUEL_EVENT"
    /// Needs the server capability ``SyncCapability/meterResetRequest``.
    case meterResetRequest = "METER_RESET_REQUEST"
    /// A job requested from the field for owner approval (permission `tenant.job.request`).
    case jobRequest = "JOB_REQUEST"
    /// Accountability ops (each needs its server capability, see ``SyncCapability``).
    case hoursPurchase = "HOURS_PURCHASE", hoursTransferRequest = "HOURS_TRANSFER_REQUEST"
    case cashTransfer = "CASH_TRANSFER", cashTransferAcknowledgement = "CASH_TRANSFER_ACKNOWLEDGEMENT"
    case cashFloatAcknowledgement = "CASH_FLOAT_ACKNOWLEDGEMENT"
    case meterBaseline = "METER_BASELINE", meterCorrection = "METER_CORRECTION"
    /// Ask to keep cash (`CashRetentionIn` with `client_id`); needs ``SyncCapability/cashRetentionRequest``.
    case cashRetentionRequest = "CASH_RETENTION_REQUEST"
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
    /// Nil for a DAILY reading outside a job (then `machineID` names the machine).
    public let jobID: UUID?
    public let machineID: UUID?
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

    public init(id: UUID, jobID: UUID?, machineID: UUID? = nil, kind: ReadingKind, captureMode: CaptureMode, reading: String,
                ocrRawText: String?, ocrValue: String?, ocrConfidence: Double?, ocrEngine: String?,
                photoAttachmentID: UUID?, gps: GpsPayload, deviceID: String, capturedAt: Date,
                policyVersionIDs: [UUID]) {
        self.id = id
        self.jobID = jobID
        self.machineID = machineID
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
        case jobID = "job_id", machineID = "machine_id", captureMode = "capture_mode", ocrRawText = "ocr_raw_text"
        case ocrValue = "ocr_value"
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

/// `JOB_REQUEST` payload (`JobRequestIn`): the supervisor asks the office for a job; the owner prices and
/// approves it. `client_id` becomes the job id, so a replay returns the same job.
public struct JobRequestPayload: Codable, Hashable, Sendable {
    public let clientID: UUID
    public let contractID: UUID
    public let machineID: UUID
    public let jobSiteID: UUID?
    public let plannedStart: Date
    public let plannedEnd: Date?
    public let note: String?

    public init(clientID: UUID, contractID: UUID, machineID: UUID, jobSiteID: UUID?, plannedStart: Date,
                plannedEnd: Date?, note: String?) {
        self.clientID = clientID
        self.contractID = contractID
        self.machineID = machineID
        self.jobSiteID = jobSiteID
        self.plannedStart = plannedStart
        self.plannedEnd = plannedEnd
        self.note = note
    }

    enum CodingKeys: String, CodingKey {
        case note
        case clientID = "client_id", contractID = "contract_id", machineID = "machine_id", jobSiteID = "job_site_id"
        case plannedStart = "planned_start", plannedEnd = "planned_end"
    }
}

/// One active contract the requester may ask a job for (`GET /tenant/field/contracts`).
public struct FieldContractDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let contractNumber: String
    public let customerID: UUID?
    public let customerName: String?
    public let jobSiteID: UUID?
    public let siteName: String?
    public let currency: String?
    public let startsOn: Date?
    public let endsOn: Date?
    /// The customer's own reference (searchable in the picker).
    public let reference: String?

    public init(id: UUID, contractNumber: String, customerID: UUID?, customerName: String?, jobSiteID: UUID?,
                siteName: String?, currency: String?, startsOn: Date? = nil, endsOn: Date? = nil, reference: String? = nil) {
        self.startsOn = startsOn
        self.endsOn = endsOn
        self.reference = reference
        self.id = id
        self.contractNumber = contractNumber
        self.customerID = customerID
        self.customerName = customerName
        self.jobSiteID = jobSiteID
        self.siteName = siteName
        self.currency = currency
    }

    enum CodingKeys: String, CodingKey {
        case id, currency, reference
        case startsOn = "starts_on", endsOn = "ends_on"
        case contractNumber = "contract_number", customerID = "customer_id", customerName = "customer_name"
        case jobSiteID = "job_site_id", siteName = "job_site_name"
    }
}
