import Foundation

// Typed read views of server-owned sync entities (only the fields the Supervisor app shows) and
// the operation payloads the device pushes. Payload shapes follow `MeterCaptureIn` and `GpsIn` in
// `contracts/openapi.json`.

public struct MachineDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let assetCode: String
    public let name: String
    public let meterDecimalPlaces: Int
    public let version: Int

    public init(id: UUID, assetCode: String, name: String, meterDecimalPlaces: Int = 1, version: Int = 0) {
        self.id = id
        self.assetCode = assetCode
        self.name = name
        self.meterDecimalPlaces = meterDecimalPlaces
        self.version = version
    }

    enum CodingKeys: String, CodingKey {
        case id, name, version, assetCode = "asset_code", meterDecimalPlaces = "meter_decimal_places"
    }
}

public struct CustomerDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let code: String
    public let name: String
    /// Deltas carry deactivated customers with `is_active=false` (bootstrap ships active ones only).
    public let isActive: Bool?

    enum CodingKeys: String, CodingKey { case id, code, name, isActive = "is_active" }
}

// MARK: - Policy

public enum CaptureMode: String, Codable, Sendable, CaseIterable {
    case automatic = "AUTOMATIC", manual = "MANUAL"
}

/// `MeterCaptureIn.kind`: every reading is a DAILY reading (ADR-008; the job opening/closing kinds are gone).
public enum ReadingKind: String, Codable, Sendable, CaseIterable {
    case daily = "DAILY"
}

/// `METER_CAPTURE` policy values as delivered in a policy snapshot (owner-controlled rules).
public struct MeterCapturePolicy: Codable, Hashable, Sendable {
    /// How a reading is expected to be taken (`capture_mode`; snapshots stored before ADR-008 carry `closing_mode`).
    public let captureMode: CaptureMode
    public let manualPhotoRequired: Bool
    public let minOCRConfidence: Double
    public let maxRecaptureAttempts: Int
    public let gpsEnforcement: String?
    public let gpsMaxAccuracyM: Double?
    public let gpsMaxAgeSeconds: Int?

    public init(captureMode: CaptureMode, manualPhotoRequired: Bool, minOCRConfidence: Double, maxRecaptureAttempts: Int,
                gpsEnforcement: String? = "SOFT", gpsMaxAccuracyM: Double? = nil, gpsMaxAgeSeconds: Int? = nil) {
        self.captureMode = captureMode
        self.manualPhotoRequired = manualPhotoRequired
        self.minOCRConfidence = minOCRConfidence
        self.maxRecaptureAttempts = maxRecaptureAttempts
        self.gpsEnforcement = gpsEnforcement
        self.gpsMaxAccuracyM = gpsMaxAccuracyM
        self.gpsMaxAgeSeconds = gpsMaxAgeSeconds
    }

    public init(from decoder: any Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        if let mode = try c.decodeIfPresent(CaptureMode.self, forKey: .captureMode) {
            captureMode = mode
        } else {
            captureMode = try c.decode(CaptureMode.self, forKey: .closingMode)
        }
        manualPhotoRequired = try c.decode(Bool.self, forKey: .manualPhotoRequired)
        minOCRConfidence = try c.decode(Double.self, forKey: .minOCRConfidence)
        maxRecaptureAttempts = try c.decode(Int.self, forKey: .maxRecaptureAttempts)
        gpsEnforcement = try c.decodeIfPresent(String.self, forKey: .gpsEnforcement)
        gpsMaxAccuracyM = try c.decodeIfPresent(Double.self, forKey: .gpsMaxAccuracyM)
        gpsMaxAgeSeconds = try c.decodeIfPresent(Int.self, forKey: .gpsMaxAgeSeconds)
    }

    public func encode(to encoder: any Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(captureMode, forKey: .captureMode)
        try c.encode(manualPhotoRequired, forKey: .manualPhotoRequired)
        try c.encode(minOCRConfidence, forKey: .minOCRConfidence)
        try c.encode(maxRecaptureAttempts, forKey: .maxRecaptureAttempts)
        try c.encodeIfPresent(gpsEnforcement, forKey: .gpsEnforcement)
        try c.encodeIfPresent(gpsMaxAccuracyM, forKey: .gpsMaxAccuracyM)
        try c.encodeIfPresent(gpsMaxAgeSeconds, forKey: .gpsMaxAgeSeconds)
    }

    enum CodingKeys: String, CodingKey {
        case captureMode = "capture_mode", closingMode = "closing_mode"
        case manualPhotoRequired = "manual_photo_required", minOCRConfidence = "min_ocr_confidence"
        case maxRecaptureAttempts = "max_recapture_attempts", gpsEnforcement = "gps_enforcement"
        case gpsMaxAccuracyM = "gps_max_accuracy_m", gpsMaxAgeSeconds = "gps_max_age_seconds"
    }
}

// MARK: - Operation payloads

public enum OperationType: String, Codable, Sendable, CaseIterable {
    case meterCapture = "METER_CAPTURE"
    case expense = "EXPENSE", cashCollection = "CASH_COLLECTION", cashHandover = "CASH_HANDOVER"
    case fuelEvent = "FUEL_EVENT"
    /// Needs the server capability ``SyncCapability/meterResetRequest``.
    case meterResetRequest = "METER_RESET_REQUEST"
    /// Accountability ops (each needs its server capability, see ``SyncCapability``).
    case hoursPurchase = "HOURS_PURCHASE", hoursTransferRequest = "HOURS_TRANSFER_REQUEST"
    case cashTransfer = "CASH_TRANSFER", cashTransferAcknowledgement = "CASH_TRANSFER_ACKNOWLEDGEMENT"
    case cashFloatAcknowledgement = "CASH_FLOAT_ACKNOWLEDGEMENT"
    case meterBaseline = "METER_BASELINE", meterCorrection = "METER_CORRECTION"
    /// Ask to keep cash (`CashRetentionIn` with `client_id`); needs ``SyncCapability/cashRetentionRequest``.
    case cashRetentionRequest = "CASH_RETENTION_REQUEST"
    /// DEC-033 petty cash (``SyncCapability/pettyCash``): acknowledgements, top-up requests, returns, counts, holder
    /// changes and advance clearances.
    case pettyCashAcknowledgement = "PETTY_CASH_ACKNOWLEDGEMENT", pettyCashTopUpRequest = "PETTY_CASH_TOP_UP_REQUEST"
    case pettyCashReturn = "PETTY_CASH_RETURN", pettyCashCount = "PETTY_CASH_COUNT"
    case pettyCashHolderChangeAcknowledgement = "PETTY_CASH_HOLDER_CHANGE_ACKNOWLEDGEMENT"
    case pettyCashAdvanceClearance = "PETTY_CASH_ADVANCE_CLEARANCE"
    /// The holder hands out an advance (``SyncCapability/pettyCashAdvance``).
    case pettyCashAdvance = "PETTY_CASH_ADVANCE"
    /// ADR-008: a machine report (``SyncCapability/machineReport``; the operation id is the report id) and a payment of
    /// a credit invoice (``SyncCapability/creditInvoicePayment``; the operation id is the payment's client id).
    case machineReport = "MACHINE_REPORT", creditInvoicePayment = "CREDIT_INVOICE_PAYMENT"
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

/// `METER_CAPTURE` payload (`MeterCaptureIn`): a DAILY reading of one machine.
public struct MeterCapturePayload: Codable, Hashable, Sendable {
    public let id: UUID
    public let machineID: UUID
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

    public init(id: UUID, machineID: UUID, kind: ReadingKind = .daily, captureMode: CaptureMode, reading: String,
                ocrRawText: String?, ocrValue: String?, ocrConfidence: Double?, ocrEngine: String?,
                photoAttachmentID: UUID?, gps: GpsPayload, deviceID: String, capturedAt: Date, policyVersionIDs: [UUID]) {
        self.id = id
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
        case machineID = "machine_id", captureMode = "capture_mode", ocrRawText = "ocr_raw_text"
        case ocrValue = "ocr_value"
        case ocrConfidence = "ocr_confidence", ocrEngine = "ocr_engine", photoAttachmentID = "photo_attachment_id"
        case deviceID = "device_id", capturedAt = "captured_at", policyVersionIDs = "policy_version_ids"
    }
}
