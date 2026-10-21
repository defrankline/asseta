#if os(iOS)
import AssetaCapture
import AssetaModel
import AssetaSync
import Foundation
import Observation

/// State of one meter capture (OPENING or CLOSING). The capture id is generated once, here; the
/// GPS attempt starts as soon as the capture screen opens and its real outcome is recorded.
@MainActor
@Observable
final class MeterCaptureModel {
    enum GpsState: Equatable { case locating, done(GpsPayload) }

    let job: FieldJob
    let kind: ReadingKind
    let snapshot: MeterPolicySnapshot
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

    init(job: FieldJob, kind: ReadingKind, snapshot: MeterPolicySnapshot) {
        self.job = job
        self.kind = kind
        self.snapshot = snapshot
        requirements = CaptureRequirements(policy: snapshot.policy, kind: kind, decimalPlaces: job.decimalPlaces)
        // The mode is not a user choice: the owner's policy decides it.
        draft = CaptureDraft(mode: requirements.requiredMode)
    }

    var issues: [CaptureIssue] { CaptureValidator.issues(draft, requirements) }

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
        if case let .blocked(reason) = model.gate(job) { // the snapshot may have expired meanwhile
            errorMessage = reason.message
            return false
        }
        let capturedAt = photoTakenAt ?? Date() // true device time of the reading
        do {
            try model.perform {
                try $0.recordCapture(job: job.job, kind: kind, mode: draft.mode, reading: reading, ocr: draft.ocr,
                                     photo: photo, gps: gps, capturedAt: capturedAt, snapshot: snapshot, captureID: captureID)
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
