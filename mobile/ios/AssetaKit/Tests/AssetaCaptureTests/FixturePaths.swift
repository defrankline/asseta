import Foundation

/// Locates the shared contract fixtures in the repository (tests read them in place, so the
/// files cannot drift from what Android and the backend use).
enum FixturePaths {
    static var repositoryRoot: URL {
        // .../mobile/ios/AssetaKit/Tests/AssetaCaptureTests/FixturePaths.swift → repo root
        URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
    }

    static var ocrDirectory: URL { repositoryRoot.appendingPathComponent("contracts/fixtures/ocr") }
}
