import CryptoKit
import Foundation

/// A file of original evidence (meter photo JPEG bytes, signature PNG) as written to disk.
public struct StoredEvidence: Sendable, Equatable {
    public let fileName: String
    public let sha256: String
    public let sizeBytes: Int64
    public let contentType: String
}

public enum EvidenceError: Error, Equatable, Sendable {
    case empty
    case missing(String)
    case hashMismatch(String)
}

/// App-private evidence files. Bytes are stored exactly as captured (never re-encoded), excluded
/// from backups and written with `NSFileProtectionComplete` on iOS: unreadable while the device
/// is locked, so a locked-phone background upload simply waits for the next foreground sync.
public struct EvidenceStore: Sendable {
    public let directory: URL

    public init(directory: URL) {
        self.directory = directory
    }

    /// Default location: Application Support/AssetaEvidence (not Caches: evidence must not be purged).
    public static func defaultDirectory() throws -> URL {
        var url = try FileManager.default.url(for: .applicationSupportDirectory, in: .userDomainMask,
                                              appropriateFor: nil, create: true)
            .appendingPathComponent("AssetaEvidence", isDirectory: true)
        try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
        var values = URLResourceValues()
        values.isExcludedFromBackup = true
        try url.setResourceValues(values)
        return url
    }

    public static func sha256Hex(_ data: Data) -> String {
        SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
    }

    public func store(_ data: Data, fileExtension: String, contentType: String, id: UUID = UUID()) throws -> StoredEvidence {
        guard !data.isEmpty else { throw EvidenceError.empty }
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let name = "\(id.uuidString.lowercased()).\(fileExtension)"
        var options: Data.WritingOptions = [.withoutOverwriting]
        #if os(iOS)
        options.insert(.completeFileProtection)
        #endif
        try data.write(to: directory.appendingPathComponent(name), options: options)
        return StoredEvidence(fileName: name, sha256: Self.sha256Hex(data), sizeBytes: Int64(data.count),
                              contentType: contentType)
    }

    public func url(for fileName: String) -> URL { directory.appendingPathComponent(fileName) }

    public func read(_ fileName: String) throws -> Data {
        let url = url(for: fileName)
        guard FileManager.default.fileExists(atPath: url.path) else { throw EvidenceError.missing(fileName) }
        return try Data(contentsOf: url)
    }

    /// Reads the file and verifies it still matches the hash recorded at capture time.
    public func readVerified(_ fileName: String, sha256: String) throws -> Data {
        let data = try read(fileName)
        guard Self.sha256Hex(data) == sha256 else { throw EvidenceError.hashMismatch(fileName) }
        return data
    }

    /// Deletes every evidence file (device wipe).
    public func wipeAll() throws {
        guard FileManager.default.fileExists(atPath: directory.path) else { return }
        try FileManager.default.removeItem(at: directory)
    }
}
