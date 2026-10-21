@testable import AssetaStore
import AssetaSecurity
import Foundation
import Testing

func temporaryDatabaseURL() throws -> URL {
    let directory = FileManager.default.temporaryDirectory.appendingPathComponent("asseta-tests-\(UUID().uuidString)")
    try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
    return directory.appendingPathComponent("test.sqlite")
}

struct EncryptionTests {
    static let marker = "PLAINTEXT-MARKER-asseta-7c1f"

    private func populatedDatabase() throws -> (URL, Data) {
        let url = try temporaryDatabaseURL()
        let key = try DatabaseKeyProvider.randomBytes(count: 32)
        let db = try EncryptedDatabase(url: url, key: key)
        try db.execute("CREATE TABLE secret (value TEXT)")
        try db.execute("INSERT INTO secret VALUES (?)", [.text(Self.marker)])
        // Fold the WAL into the main file so the on-disk bytes include the data.
        try db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        db.close()
        return (url, key)
    }

    @Test func linksSQLCipher() throws {
        let db = try EncryptedDatabase(url: try temporaryDatabaseURL(), key: try DatabaseKeyProvider.randomBytes(count: 32))
        #expect(try !db.cipherVersion().isEmpty)
    }

    @Test func fileBytesContainNoPlaintextOrSQLiteHeader() throws {
        let (url, _) = try populatedDatabase()
        let bytes = try Data(contentsOf: url)
        #expect(bytes.count > 0)
        #expect(!bytes.starts(with: Data("SQLite format 3\0".utf8)))
        #expect(bytes.range(of: Data(Self.marker.utf8)) == nil)
        #expect(bytes.range(of: Data("CREATE TABLE".utf8)) == nil)
    }

    @Test func wrongKeyIsRejected() throws {
        let (url, _) = try populatedDatabase()
        #expect {
            try EncryptedDatabase(url: url, key: try DatabaseKeyProvider.randomBytes(count: 32))
        } throws: { error in
            if case DatabaseError.keyRejected = error { return true }
            return false
        }
    }

    @Test func cannotBeReadWithoutKey() throws {
        let (url, _) = try populatedDatabase()
        // Open with SQLCipher but no key at all: behaves like plain SQLite and must fail.
        let raw = try UnkeyedConnection(url: url)
        #expect(throws: (any Error).self) { try raw.firstText("SELECT value FROM secret") }
        #expect(throws: (any Error).self) { try raw.firstText("SELECT count(*) FROM sqlite_master") }
    }

    @Test func correctKeyReadsData() throws {
        let (url, key) = try populatedDatabase()
        let db = try EncryptedDatabase(url: url, key: key)
        #expect(try db.query("SELECT value FROM secret") { $0.string(0) } == [Self.marker])
    }

    @Test func rejectsShortKeys() {
        #expect(throws: DatabaseError.invalidKeyLength(16)) {
            try EncryptedDatabase(url: try temporaryDatabaseURL(), key: Data(count: 16))
        }
    }
}
