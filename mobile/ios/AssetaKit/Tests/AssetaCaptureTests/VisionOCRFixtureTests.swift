@testable import AssetaCapture
import Foundation
import Testing

/// Runs the real Vision pipeline over every synthetic fixture image (Vision works on macOS too)
/// and enforces the manifest acceptance: zero confident wrong reads, must-read accuracy ≥ 0.9.
/// Synthetic images are a baseline only; real dashboard samples are required (EXT-05).
/// Serialized: concurrent Vision requests hung the hosted macOS runner.
@Suite(.serialized)
struct VisionOCRFixtureTests {
    struct Manifest: Decodable {
        struct Acceptance: Decodable { let must_read_min_accuracy: Double; let wrong_confident_reads_allowed: Int }
        struct Image: Decodable { let file: String; let style: String; let expected_reading: String; let decimal_places: Int; let category: String }
        let acceptance: Acceptance
        let images: [Image]
    }

    static let confidentThreshold = 0.85

    @Test func everyFixtureImage() throws {
        let dir = FixturePaths.ocrDirectory
        let manifest = try JSONDecoder().decode(Manifest.self, from: Data(contentsOf: dir.appendingPathComponent("manifest.json")))
        let ocr = MeterOCR()
        var mustRead = 0, mustReadConfidentCorrect = 0, mustReadValueCorrect = 0, confidentWrong = 0
        var lines: [String] = []
        for image in manifest.images {
            let data = try Data(contentsOf: dir.appendingPathComponent(image.file))
            let result = ocr.recognize(imageData: data, decimalPlaces: image.decimal_places)
            let correct = result.value == image.expected_reading
            let confident = result.confidence >= Self.confidentThreshold
            if confident && !correct { confidentWrong += 1 }
            if image.category == "must_read" {
                mustRead += 1
                if correct { mustReadValueCorrect += 1 }
                if correct && confident { mustReadConfidentCorrect += 1 }
            }
            lines.append(String(format: "%-34@ %-11@ expected=%@ got=%@ conf=%.2f %@ [%@]",
                                image.file as NSString, image.category as NSString, image.expected_reading,
                                result.value ?? "nil", result.confidence,
                                correct ? (confident ? "OK" : "ok-low") : (confident ? "WRONG-CONFIDENT" : "fallback"),
                                result.note))
        }
        let accuracy = Double(mustReadConfidentCorrect) / Double(max(mustRead, 1))
        print("OCR fixture report\n" + lines.joined(separator: "\n"))
        print(String(format: "must_read: %d/%d confident-correct (accuracy %.3f), %d/%d value-correct; confident wrong reads: %d",
                     mustReadConfidentCorrect, mustRead, accuracy, mustReadValueCorrect, mustRead, confidentWrong))
        #expect(confidentWrong <= manifest.acceptance.wrong_confident_reads_allowed)
        #expect(accuracy >= manifest.acceptance.must_read_min_accuracy)
    }

    struct RealManifest: Decodable {
        struct Acceptance: Decodable { let wrong_confident_reads_allowed: Int }
        struct Image: Decodable { let file: String; let expected_reading: String; let decimal_places: Int; let category: String }
        let acceptance: Acceptance
        let images: [Image]
    }

    /// Real dashboard photos (EXT-05). The bar today is safety: no confident wrong read; results are printed.
    @Test func everyRealSample() throws {
        let dir = FixturePaths.ocrDirectory.appendingPathComponent("real")
        let manifest = try JSONDecoder().decode(RealManifest.self, from: Data(contentsOf: dir.appendingPathComponent("manifest.json")))
        let ocr = MeterOCR()
        var confidentWrong = 0
        for image in manifest.images {
            let result = ocr.recognize(imageData: try Data(contentsOf: dir.appendingPathComponent(image.file)),
                                       decimalPlaces: image.decimal_places)
            let correct = result.value == image.expected_reading
            if result.confidence >= Self.confidentThreshold && !correct { confidentWrong += 1 }
            print("real \(image.file) expected=\(image.expected_reading) got=\(result.value ?? "nil") "
                + String(format: "conf=%.2f", result.confidence) + " [\(result.note)] raw=\(result.rawText)")
        }
        #expect(confidentWrong <= manifest.acceptance.wrong_confident_reads_allowed)
    }
}
