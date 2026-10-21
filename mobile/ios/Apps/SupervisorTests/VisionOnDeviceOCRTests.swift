import AssetaCapture
import Foundation
import Testing

/// The same fixture acceptance as `swift test`, but on the iOS runtime (Simulator/device Vision).
struct VisionOnDeviceOCRTests {
    struct Manifest: Decodable {
        struct Image: Decodable { let file: String; let expected_reading: String; let decimal_places: Int; let category: String }
        let images: [Image]
    }

    @Test func fixturesOnIOSRuntime() throws {
        // .../mobile/ios/Apps/SupervisorTests/<file> → repo root
        let root = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        let dir = root.appendingPathComponent("contracts/fixtures/ocr")
        guard FileManager.default.fileExists(atPath: dir.path) else {
            print("OCR fixtures not reachable from this runtime (physical device); skipped")
            return
        }
        let manifest = try JSONDecoder().decode(Manifest.self, from: Data(contentsOf: dir.appendingPathComponent("manifest.json")))
        var mustRead = 0, correct = 0, confidentWrong = 0
        for image in manifest.images {
            let result = MeterOCR().recognize(imageData: try Data(contentsOf: dir.appendingPathComponent(image.file)),
                                              decimalPlaces: image.decimal_places)
            let ok = result.value == image.expected_reading, confident = result.confidence >= 0.85
            if confident && !ok { confidentWrong += 1 }
            if image.category == "must_read" { mustRead += 1; if ok && confident { correct += 1 } }
            print("iOS OCR \(image.file): \(result.value ?? "nil") conf=\(result.confidence) [\(result.note)]")
        }
        print("iOS OCR must_read \(correct)/\(mustRead), confident wrong \(confidentWrong)")
        #expect(confidentWrong == 0)
        #expect(Double(correct) / Double(mustRead) >= 0.9)
    }
}
