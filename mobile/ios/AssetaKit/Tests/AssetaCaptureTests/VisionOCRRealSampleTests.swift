@testable import AssetaCapture
import Foundation
import Testing

/// Real dashboard photos (EXT-05). The bar today is safety: no confident wrong read. Each result is
/// printed so accuracy on real displays can be tracked as the parser improves.
struct VisionOCRRealSampleTests {
    struct Manifest: Decodable {
        struct Acceptance: Decodable { let wrong_confident_reads_allowed: Int }
        struct Image: Decodable { let file: String; let expected_reading: String; let decimal_places: Int; let category: String }
        let acceptance: Acceptance
        let images: [Image]
    }

    @Test func everyRealSample() throws {
        let dir = FixturePaths.ocrDirectory.appendingPathComponent("real")
        let manifest = try JSONDecoder().decode(Manifest.self, from: Data(contentsOf: dir.appendingPathComponent("manifest.json")))
        let ocr = MeterOCR()
        var confidentWrong = 0
        for image in manifest.images {
            let result = ocr.recognize(imageData: try Data(contentsOf: dir.appendingPathComponent(image.file)),
                                       decimalPlaces: image.decimal_places)
            let correct = result.value == image.expected_reading
            if result.confidence >= VisionOCRFixtureTests.confidentThreshold && !correct { confidentWrong += 1 }
            print("real \(image.file) expected=\(image.expected_reading) got=\(result.value ?? "nil") "
                + String(format: "conf=%.2f", result.confidence) + " [\(result.note)] raw=\(result.rawText)")
        }
        #expect(confidentWrong <= manifest.acceptance.wrong_confident_reads_allowed)
    }
}
