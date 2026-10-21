import AssetaModel
import Foundation

/// What the active policy snapshot demands for one reading (OPENING or CLOSING).
public struct CaptureRequirements: Sendable, Equatable {
    public let kind: ReadingKind
    public let requiredMode: CaptureMode
    public let photoRequired: Bool
    public let decimalPlaces: Int
    public let minOCRConfidence: Double
    public let maxRecaptureAttempts: Int

    public init(policy: MeterCapturePolicy, kind: ReadingKind, decimalPlaces: Int) {
        self.kind = kind
        self.requiredMode = policy.mode(for: kind)
        // AUTOMATIC is "camera photo + OCR", so it always has a photo; MANUAL follows the policy.
        self.photoRequired = requiredMode == .automatic || policy.manualPhotoRequired
        self.decimalPlaces = min(max(decimalPlaces, 0), 2)
        self.minOCRConfidence = policy.minOCRConfidence
        self.maxRecaptureAttempts = max(policy.maxRecaptureAttempts, 0)
    }
}

/// Decision after an AUTOMATIC photo has been read.
public enum AutomaticDecision: Sendable, Equatable {
    /// Show the value and confidence for the supervisor to confirm (or correct).
    case confirm(value: String, confidence: Double)
    /// Too uncertain: ask for another photo. `remaining` recaptures are left after this one.
    case recapture(remaining: Int)
    /// Recaptures exhausted: manual entry is allowed; photo and OCR output are kept as evidence.
    case manualEntry(suggestion: String?)
}

public enum AutomaticCapturePolicy {
    /// `attempts` = photos taken so far for this capture (the first photo is attempt 1).
    public static func decide(_ ocr: MeterOCRResult, attempts: Int, requirements: CaptureRequirements) -> AutomaticDecision {
        if let value = ocr.value, ocr.confidence >= requirements.minOCRConfidence {
            return .confirm(value: value, confidence: ocr.confidence)
        }
        let recapturesUsed = max(attempts - 1, 0)
        if recapturesUsed < requirements.maxRecaptureAttempts {
            return .recapture(remaining: requirements.maxRecaptureAttempts - recapturesUsed - 1)
        }
        return .manualEntry(suggestion: ocr.value)
    }
}

/// Field-level problems that block saving a capture. Shown to the user verbatim.
public enum CaptureIssue: Error, Sendable, Equatable, CustomStringConvertible {
    case wrongMode(required: CaptureMode)
    case readingMissing
    case readingInvalid
    case tooManyDecimals(max: Int)
    case photoRequired
    case ocrNotAttempted
    case recaptureRequired
    case gpsNotAttempted

    public var description: String {
        switch self {
        case let .wrongMode(required): "This reading must be captured \(required == .automatic ? "with the camera (automatic)" : "manually")."
        case .readingMissing: "Enter the meter reading."
        case .readingInvalid: "The reading must be a non-negative number."
        case let .tooManyDecimals(max): max == 0 ? "This meter shows whole hours only." : "This meter shows at most \(max) decimal place\(max == 1 ? "" : "s")."
        case .photoRequired: "A photo of the meter is required."
        case .ocrNotAttempted: "Take a photo so the reading can be recognized."
        case .recaptureRequired: "The photo could not be read reliably. Take another photo."
        case .gpsNotAttempted: "A location attempt is required for every reading."
        }
    }
}

/// Everything the supervisor has captured so far for one reading.
public struct CaptureDraft: Sendable, Equatable {
    public var mode: CaptureMode
    public var readingText: String
    public var hasPhoto: Bool
    public var ocr: MeterOCRResult?
    public var photoAttempts: Int
    public var gps: GpsPayload?

    public init(mode: CaptureMode, readingText: String = "", hasPhoto: Bool = false, ocr: MeterOCRResult? = nil,
                photoAttempts: Int = 0, gps: GpsPayload? = nil) {
        self.mode = mode
        self.readingText = readingText
        self.hasPhoto = hasPhoto
        self.ocr = ocr
        self.photoAttempts = photoAttempts
        self.gps = gps
    }
}

public enum CaptureValidator {
    /// Canonical reading string (`decimalPlaces` fraction digits) or the problem with the input.
    public static func normalizeReading(_ text: String, decimalPlaces: Int) -> Result<String, CaptureIssue> {
        let trimmed = text.trimmingCharacters(in: .whitespaces).replacingOccurrences(of: ",", with: ".")
        guard !trimmed.isEmpty else { return .failure(.readingMissing) }
        let parts = trimmed.split(separator: ".", omittingEmptySubsequences: false)
        guard parts.count <= 2, let integerPart = parts.first, !integerPart.isEmpty, integerPart.count <= 12,
              integerPart.allSatisfy({ $0.isASCII && $0.isNumber }),
              parts.count == 1 || parts[1].allSatisfy({ $0.isASCII && $0.isNumber })
        else { return .failure(.readingInvalid) }
        let fraction = parts.count == 2 ? String(parts[1]) : ""
        guard fraction.count <= decimalPlaces else { return .failure(.tooManyDecimals(max: decimalPlaces)) }
        var integer = String(integerPart.drop(while: { $0 == "0" }))
        if integer.isEmpty { integer = "0" }
        guard decimalPlaces > 0 else { return .success(integer) }
        return .success("\(integer).\(fraction)\(String(repeating: "0", count: decimalPlaces - fraction.count))")
    }

    /// All blocking issues for `draft`; empty means the capture may be saved.
    public static func issues(_ draft: CaptureDraft, _ requirements: CaptureRequirements) -> [CaptureIssue] {
        var issues: [CaptureIssue] = []
        if draft.mode != requirements.requiredMode { issues.append(.wrongMode(required: requirements.requiredMode)) }
        if case let .failure(issue) = normalizeReading(draft.readingText, decimalPlaces: requirements.decimalPlaces) {
            issues.append(issue)
        }
        if requirements.photoRequired && !draft.hasPhoto { issues.append(.photoRequired) }
        if draft.mode == .automatic {
            if let ocr = draft.ocr {
                let decision = AutomaticCapturePolicy.decide(ocr, attempts: draft.photoAttempts, requirements: requirements)
                if case .recapture = decision { issues.append(.recaptureRequired) }
            } else if draft.hasPhoto {
                issues.append(.ocrNotAttempted)
            }
        }
        if draft.gps == nil { issues.append(.gpsNotAttempted) }
        return issues
    }
}
