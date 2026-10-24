#if os(iOS)
import AssetaCapture
import AssetaModel
import AssetaSync
import Foundation
import Observation

/// What a capture is for: a job reading, a DAILY reading outside a job, a baseline proposal or a correction of one of
/// my readings (same evidence rules; Android `CaptureTarget`).
enum CaptureTarget {
    case job(FieldJob, ReadingKind)
    case daily(MachineDTO)
    case baseline(MachineDTO)
    case correction(ReadingItem, MachineDTO)

    var machine: MachineDTO? {
        switch self {
        case let .job(job, _): job.machine
        case let .daily(machine), let .baseline(machine), let .correction(_, machine): machine
        }
    }

    var machineID: UUID? {
        switch self {
        case let .job(job, _): job.job.machineID
        default: machine?.id
        }
    }

    /// The reading kind whose evidence rules apply (a baseline follows the closing/daily rules).
    var kind: ReadingKind {
        switch self {
        case let .job(_, kind): kind
        case .daily, .baseline: .daily
        case let .correction(reading, _): ReadingKind(rawValue: reading.kind) ?? .closing
        }
    }

    var title: String {
        switch self {
        case let .job(_, kind): kind == .opening ? "Opening reading" : "Closing reading"
        case .daily: FieldAccountabilityTexts.titleDailyReading
        case .baseline: FieldAccountabilityTexts.titleBaseline
        case .correction: FieldAccountabilityTexts.titleCorrection
        }
    }
}

/// State of one meter capture (OPENING, CLOSING, DAILY, baseline or correction). The capture id is generated once,
/// here; the GPS attempt starts as soon as the capture screen opens and its real outcome is recorded.
@MainActor
@Observable
final class MeterCaptureModel {
    enum GpsState: Equatable { case locating, done(GpsPayload) }

    let target: CaptureTarget
    let kind: ReadingKind
    let snapshot: MeterPolicySnapshot
    /// The baseline note or the correction reason.
    var extraText = ""
    let requirements: CaptureRequirements
    let captureID = UUID()

    var draft: CaptureDraft
    private(set) var photo: StoredEvidence?
    private(set) var photoData: Data?
    private(set) var photoTakenAt: Date?
    private(set) var isReadingPhoto = false
    private(set) var decision: AutomaticDecision?
    private(set) var gpsState: GpsState = .locating
    var errorMessage: String?

    convenience init(job: FieldJob, kind: ReadingKind, snapshot: MeterPolicySnapshot) {
        self.init(target: .job(job, kind), snapshot: snapshot)
    }

    init(target: CaptureTarget, snapshot: MeterPolicySnapshot) {
        self.target = target
        kind = target.kind
        self.snapshot = snapshot
        requirements = CaptureRequirements(policy: snapshot.policy, kind: target.kind,
                                           decimalPlaces: target.machine?.meterDecimalPlaces ?? 1)
        // The mode is not a user choice: the owner's policy decides it.
        draft = CaptureDraft(mode: requirements.requiredMode)
    }

    var issues: [CaptureIssue] { CaptureValidator.issues(draft, requirements) }

    /// A correction needs a reason of 10+ characters before it can be saved.
    var extraBlocksSave: Bool {
        if case .correction = target { return !AccountabilityRules.correctionReasonValid(extraText) }
        return false
    }

    /// A fresh fix for every capture (never a cached or earlier location).
    func locate(using locator: LocationCapturer) async {
        gpsState = .locating
        draft.gps = nil
        let result = await locator.captureFix(timeout: 20)
        draft.gps = result
        gpsState = .done(result)
    }

    /// Keeps the original JPEG bytes as evidence and, for AUTOMATIC, reads them on-device.
    func photoTaken(_ data: Data, model: FieldModel) async {
        do {
            let stored = try model.storeEvidence(data, fileExtension: "jpg", contentType: "image/jpeg")
            if let previous = photo { model.discardEvidence(previous) } // superseded by the recapture
            photo = stored
            photoData = data
            photoTakenAt = Date()
            draft.hasPhoto = true
            draft.photoAttempts += 1
        } catch {
            errorMessage = "The photo could not be saved: \(error)"
            return
        }
        guard draft.mode == .automatic else { return }
        isReadingPhoto = true
        let ocr = model.ocr
        let places = requirements.decimalPlaces
        let result = await Task.detached(priority: .userInitiated) {
            ocr.recognize(imageData: data, decimalPlaces: places)
        }.value
        isReadingPhoto = false
        draft.ocr = result
        let decision = AutomaticCapturePolicy.decide(result, attempts: draft.photoAttempts, requirements: requirements)
        self.decision = decision
        switch decision {
        case let .confirm(value, _): draft.readingText = value
        case let .manualEntry(suggestion): draft.readingText = suggestion ?? ""
        case .recapture: draft.readingText = ""
        }
    }

    /// True when the supervisor changed the recognized value (sent as a manual correction; the
    /// OCR value and raw text are kept).
    var isCorrection: Bool {
        guard let value = draft.ocr?.value,
              case let .success(reading) = CaptureValidator.normalizeReading(draft.readingText, decimalPlaces: requirements.decimalPlaces)
        else { return false }
        return reading != value
    }

    func save(model: FieldModel) -> Bool {
        guard issues.isEmpty, let gps = draft.gps,
              case let .success(reading) = CaptureValidator.normalizeReading(draft.readingText, decimalPlaces: requirements.decimalPlaces)
        else { return false }
        guard let machineID = target.machineID else { return false }
        if case let .blocked(reason) = model.gate(machineID: machineID) { // the snapshot may have expired meanwhile
            errorMessage = reason.message
            return false
        }
        let capturedAt = photoTakenAt ?? Date() // true device time of the reading
        let (mode, ocr, photo, snapshot, captureID, note) = (draft.mode, draft.ocr, photo, snapshot, captureID, extraText)
        do {
            try model.perform { recorder in
                switch target {
                case let .job(job, kind):
                    try recorder.recordCapture(job: job.job, kind: kind, mode: mode, reading: reading, ocr: ocr, photo: photo,
                                               gps: gps, capturedAt: capturedAt, snapshot: snapshot, captureID: captureID)
                case .daily:
                    try recorder.recordDailyReading(machineID: machineID, mode: mode, reading: reading, ocr: ocr, photo: photo,
                                                    gps: gps, capturedAt: capturedAt, snapshot: snapshot, captureID: captureID)
                case .baseline:
                    try recorder.proposeBaseline(machineID: machineID, reading: reading, photo: photo, gps: gps, note: note,
                                                 capturedAt: capturedAt, baselineID: captureID)
                case let .correction(original, _):
                    try recorder.proposeCorrection(of: original, machineID: machineID, mode: mode, value: reading, ocr: ocr,
                                                   photo: photo, gps: gps, capturedAt: capturedAt, reason: note,
                                                   snapshot: snapshot, replacementID: captureID)
                }
            }
            return true
        } catch {
            errorMessage = JobDetailView.describe(error)
            return false
        }
    }

    func cancel(model: FieldModel) {
        if let photo { model.discardEvidence(photo) }
    }
}
#endif
