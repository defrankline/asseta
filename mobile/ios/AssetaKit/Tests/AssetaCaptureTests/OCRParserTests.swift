@testable import AssetaCapture
import Foundation
import Testing

/// Shared OCR text → reading spec: every case in `contracts/fixtures/ocr/parse_cases.json` must
/// produce exactly the reference result (same file Android and the backend test against).
struct OCRParserTests {
    struct Case: Decodable, CustomTestStringConvertible {
        let text: String
        let decimal_places: Int
        let value: String?
        let reason: String
        var testDescription: String { "\(text.debugDescription) @\(decimal_places)" }
    }

    struct CaseFile: Decodable {
        let spec_version: String
        let cases: [Case]
    }

    static func load() throws -> CaseFile {
        let url = FixturePaths.ocrDirectory.appendingPathComponent("parse_cases.json")
        return try JSONDecoder().decode(CaseFile.self, from: Data(contentsOf: url))
    }

    @Test func fixtureFileIsTheSharedSpecVersion() throws {
        let file = try Self.load()
        #expect(file.spec_version == MeterReadingParser.specVersion)
        #expect(file.cases.count >= 12)
    }

    @Test(arguments: try load().cases)
    func sharedCase(_ c: Case) {
        let result = MeterReadingParser.parse(c.text, decimalPlaces: c.decimal_places)
        #expect(result.value == c.value)
        #expect(result.reason.rawValue == c.reason)
    }

    @Test func extraEdgeCasesMatchReferenceBehaviour() {
        #expect(MeterReadingParser.parse("000.5", decimalPlaces: 1).value == "0.5")
        #expect(MeterReadingParser.parse("17945 9", decimalPlaces: 1).value == "17945.9")
        #expect(MeterReadingParser.parse("17945 9", decimalPlaces: 0).value == "17945")
        #expect(MeterReadingParser.parse("12.50", decimalPlaces: 1).reason == .precisionExceedsMeter)
        #expect(MeterReadingParser.parse("1234,56", decimalPlaces: 2).value == "1234.56")
        #expect(MeterReadingParser.parse("07:30:15 0451.2", decimalPlaces: 1).value == "451.2")
    }
}
