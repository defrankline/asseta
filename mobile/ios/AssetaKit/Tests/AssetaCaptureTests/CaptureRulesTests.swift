@testable import AssetaCapture
import AssetaModel
import CoreGraphics
import Foundation
import Testing

struct CaptureRulesTests {
    let policy = MeterCapturePolicy(openingMode: .automatic, closingMode: .manual, manualPhotoRequired: true,
                                    minOCRConfidence: 0.85, maxRecaptureAttempts: 2)
    var opening: CaptureRequirements { CaptureRequirements(policy: policy, kind: .opening, decimalPlaces: 1) }
    var closing: CaptureRequirements { CaptureRequirements(policy: policy, kind: .closing, decimalPlaces: 1) }
    let gps = GpsPayload.failed(.timeout)

    func ocr(_ value: String?, _ confidence: Double) -> MeterOCRResult {
        MeterOCRResult(value: value, confidence: confidence, rawText: value ?? "", engine: "t", note: "")
    }

    @Test func requiredModeComesFromTheSnapshotPerKind() {
        #expect(opening.requiredMode == .automatic && opening.photoRequired)
        #expect(closing.requiredMode == .manual && closing.photoRequired)
        let noPhoto = MeterCapturePolicy(openingMode: .manual, closingMode: .manual, manualPhotoRequired: false,
                                         minOCRConfidence: 0.8, maxRecaptureAttempts: 1)
        #expect(!CaptureRequirements(policy: noPhoto, kind: .opening, decimalPlaces: 0).photoRequired)
        let draft = CaptureDraft(mode: .manual, readingText: "100.0", gps: gps)
        #expect(CaptureValidator.issues(draft, opening).contains(.wrongMode(required: .automatic)))
    }

    @Test func manualReadingFollowsMeterDecimalPlacesAndPhotoRule() throws {
        #expect(CaptureValidator.issues(CaptureDraft(mode: .manual, readingText: "0123.4", hasPhoto: true, gps: gps), closing).isEmpty)
        #expect(CaptureValidator.issues(CaptureDraft(mode: .manual, readingText: "123.45", hasPhoto: true, gps: gps), closing)
                == [.tooManyDecimals(max: 1)])
        #expect(CaptureValidator.issues(CaptureDraft(mode: .manual, readingText: "12a", hasPhoto: true, gps: gps), closing)
                == [.readingInvalid])
        #expect(CaptureValidator.issues(CaptureDraft(mode: .manual, readingText: "-5", hasPhoto: true, gps: gps), closing)
                == [.readingInvalid])
        #expect(CaptureValidator.issues(CaptureDraft(mode: .manual, readingText: "", hasPhoto: true, gps: gps), closing)
                == [.readingMissing])
        #expect(CaptureValidator.issues(CaptureDraft(mode: .manual, readingText: "5", gps: gps), closing) == [.photoRequired])
        #expect(CaptureValidator.issues(CaptureDraft(mode: .manual, readingText: "5", hasPhoto: true), closing) == [.gpsNotAttempted])
        #expect(try CaptureValidator.normalizeReading("0123,4", decimalPlaces: 2).get() == "123.40")
        #expect(try CaptureValidator.normalizeReading("7", decimalPlaces: 0).get() == "7")
    }

    @Test func automaticNeedsPhotoAndConfidentOCRUntilRecapturesRunOut() {
        let base = CaptureDraft(mode: .automatic, readingText: "4521.7", hasPhoto: true, gps: gps)
        var draft = base
        #expect(CaptureValidator.issues(draft, opening) == [.ocrNotAttempted])
        draft.ocr = ocr("4521.7", 0.5)
        draft.photoAttempts = 1
        #expect(AutomaticCapturePolicy.decide(draft.ocr!, attempts: 1, requirements: opening) == .recapture(remaining: 1))
        #expect(CaptureValidator.issues(draft, opening) == [.recaptureRequired])
        draft.photoAttempts = 2
        #expect(AutomaticCapturePolicy.decide(draft.ocr!, attempts: 2, requirements: opening) == .recapture(remaining: 0))
        draft.photoAttempts = 3 // max_recapture_attempts (2) used up → manual entry, photo + OCR kept
        #expect(AutomaticCapturePolicy.decide(draft.ocr!, attempts: 3, requirements: opening) == .manualEntry(suggestion: "4521.7"))
        #expect(CaptureValidator.issues(draft, opening).isEmpty)
        draft.ocr = ocr("4521.7", 0.92)
        draft.photoAttempts = 1
        #expect(AutomaticCapturePolicy.decide(draft.ocr!, attempts: 1, requirements: opening) == .confirm(value: "4521.7", confidence: 0.92))
        draft.readingText = "4521.9" // user corrects the recognized value: allowed (manual correction)
        #expect(CaptureValidator.issues(draft, opening).isEmpty)
        #expect(CaptureValidator.issues(CaptureDraft(mode: .automatic, readingText: "1", gps: gps), opening).contains(.photoRequired))
    }
}

struct GpsAttemptTests {
    let start = Date(timeIntervalSince1970: 1_792_000_000)

    @Test func onlyFreshFixesCountAndTheMostAccurateWins() {
        var attempt = GpsAttempt(startedAt: start)
        let early1 = attempt.record(latitude: 1, longitude: 1, horizontalAccuracy: 5, timestamp: start.addingTimeInterval(-60))
        #expect(!early1)
        #expect(attempt.result() == .failed(.timeout)) // a cached location is never reused
        let early2 = attempt.record(latitude: -15.40, longitude: 28.30, horizontalAccuracy: 40, timestamp: start.addingTimeInterval(2))
        #expect(!early2)
        let early3 = attempt.record(latitude: 9, longitude: 9, horizontalAccuracy: -1, timestamp: start.addingTimeInterval(3))
        #expect(!early3)
        let early4 = attempt.record(latitude: -15.41, longitude: 28.31, horizontalAccuracy: 6, timestamp: start.addingTimeInterval(4))
        #expect(early4)
        #expect(attempt.result() == .fix(latitude: -15.41, longitude: 28.31, accuracyM: 6, capturedAt: start.addingTimeInterval(4)))
    }

    @Test func failuresCarryNoCoordinates() {
        var unknown = GpsAttempt(startedAt: start)
        unknown.recordLocationUnknown()
        #expect(unknown.result() == .failed(.noFix))
        var denied = GpsAttempt(startedAt: start)
        _ = denied.record(latitude: 1, longitude: 1, horizontalAccuracy: 5, timestamp: start)
        denied.recordDenied()
        let result = denied.result()
        #expect(result.status == .permissionDenied && result.latitude == nil && result.longitude == nil && result.accuracyM == nil)
        var disabled = GpsAttempt(startedAt: start)
        disabled.recordDisabled()
        #expect(disabled.result().status == .disabled)
    }
}

struct EvidenceStoreTests {
    @Test func storesOriginalBytesWithHashAndDetectsTampering() throws {
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("ev-\(UUID().uuidString)")
        let store = EvidenceStore(directory: dir)
        let bytes = Data("original jpeg bytes".utf8)
        let saved = try store.store(bytes, fileExtension: "jpg", contentType: "image/jpeg")
        #expect(saved.sha256 == EvidenceStore.sha256Hex(bytes))
        #expect(try store.readVerified(saved.fileName, sha256: saved.sha256) == bytes)
        try Data("changed".utf8).write(to: store.url(for: saved.fileName))
        #expect(throws: EvidenceError.hashMismatch(saved.fileName)) { try store.readVerified(saved.fileName, sha256: saved.sha256) }
        #expect(throws: EvidenceError.empty) { try store.store(Data(), fileExtension: "jpg", contentType: "image/jpeg") }
        try store.wipeAll()
        #expect(!FileManager.default.fileExists(atPath: dir.path))
    }

    @Test func knownSHA256Vector() {
        #expect(EvidenceStore.sha256Hex(Data("abc".utf8)) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
    }
}

struct OCRCompositionTests {
    func row(_ widths: [Int], dot: Int? = nil, red: Int? = nil) -> GlyphRow {
        var x = 0
        let glyphs = widths.map { w -> GlyphBox in defer { x += w + 10 }; return GlyphBox(x0: x, y0: 0, x1: x + w - 1, y1: 49, area: w * 50) }
        return GlyphRow(glyphs: glyphs, dotAfter: dot, ambiguousDots: false, redTenths: red)
    }

    @Test func drumRedTenthsWheelIsSplitNotMerged() {
        let text = MeterOCR.compose(Array("202641"), row: row([30, 30, 30, 30, 30, 30], red: 5))
        #expect(text == "20264 1")
        #expect(MeterReadingParser.parse(text!, decimalPlaces: 1).value == "20264.1")
    }

    @Test func geometricDotUnitLettersAndSymbols() {
        #expect(MeterOCR.compose(Array("716916"), row: row([30, 8, 30, 30, 8, 30], dot: 4)) == "71691.6")
        #expect(MeterOCR.compose(Array("31906H"), row: row([30, 30, 30, 30, 30, 30], dot: 3)) == "3190.6 H")
        #expect(MeterOCR.compose(Array("41₴133"), row: row([30, 30, 30, 30, 30, 30])) == nil)
        #expect(MeterOCR.compose(Array("12H34"), row: row([30, 30, 30, 30, 30])) == nil) // digits must be contiguous
    }

    @Test func wideOneIsSuspicious() {
        #expect(MeterOCR.hasWideOne(Array("16165"), row: row([28, 35, 8, 35, 35])))
        #expect(!MeterOCR.hasWideOne(Array("71691"), row: row([28, 8, 35, 35, 8])))
    }

    @Test func blankImageReadsNothing() throws {
        let ctx = CGContext(data: nil, width: 320, height: 160, bitsPerComponent: 8, bytesPerRow: 0,
                            space: CGColorSpaceCreateDeviceRGB(), bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
        ctx.setFillColor(red: 0.5, green: 0.5, blue: 0.5, alpha: 1)
        ctx.fill(CGRect(x: 0, y: 0, width: 320, height: 160))
        let result = MeterOCR().recognize(cgImage: ctx.makeImage()!, decimalPlaces: 1)
        #expect(result.value == nil)
        #expect(result.confidence == 0)
    }
}
