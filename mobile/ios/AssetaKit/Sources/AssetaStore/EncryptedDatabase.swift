import Foundation
import SQLCipher

public enum DatabaseError: Error, Equatable, Sendable {
    case open(code: Int32, message: String)
    case keyRejected(message: String)
    case notEncrypted
    case prepare(code: Int32, message: String, sql: String)
    case step(code: Int32, message: String)
    case bind(code: Int32, index: Int32)
    case constraint(message: String)
    case migration(version: Int, message: String)
    case invalidKeyLength(Int)
}

/// A single SQLCipher connection guarded by a lock.
///
/// The whole database file (pages, schema, journal/WAL) is AES-256 encrypted by SQLCipher using a
/// raw 256-bit key (no KDF needed because the key is already random). Opening fails with
/// ``DatabaseError/keyRejected(message:)`` if the key is wrong or missing.
public final class EncryptedDatabase: @unchecked Sendable {
    // @unchecked: the sqlite3 handle is only touched while holding `lock` (serialized access).
    private let lock = NSRecursiveLock()
    private var handle: OpaquePointer?
    public let url: URL

    public init(url: URL, key: Data) throws {
        guard key.count == 32 else { throw DatabaseError.invalidKeyLength(key.count) }
        self.url = url
        var db: OpaquePointer?
        let flags = SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE | SQLITE_OPEN_FULLMUTEX
        let rc = sqlite3_open_v2(url.path, &db, flags, nil)
        guard rc == SQLITE_OK, let db else {
            let message = db.map { String(cString: sqlite3_errmsg($0)) } ?? "unknown"
            sqlite3_close_v2(db)
            throw DatabaseError.open(code: rc, message: message)
        }
        handle = db
        do {
            try applyKey(key)
            try execute("PRAGMA foreign_keys = ON")
            try execute("PRAGMA journal_mode = WAL")
            try Self.applyFileProtection(url)
        } catch {
            close()
            throw error
        }
    }

    deinit { close() }

    public func close() {
        lock.withLock {
            if let handle { sqlite3_close_v2(handle) }
            handle = nil
        }
    }

    /// The linked SQLCipher version; empty would mean plain SQLite was linked by mistake.
    public func cipherVersion() throws -> String {
        (try query("PRAGMA cipher_version") { $0.string(0) }.first ?? nil) ?? ""
    }

    // MARK: - Execution

    public func execute(_ sql: String, _ bindings: [SQLValue] = []) throws {
        try lock.withLock {
            let statement = try prepare(sql)
            defer { sqlite3_finalize(statement) }
            try bind(bindings, to: statement)
            var rc = sqlite3_step(statement)
            while rc == SQLITE_ROW { rc = sqlite3_step(statement) }
            guard rc == SQLITE_DONE else { throw stepError(rc) }
        }
    }

    public func query<T>(_ sql: String, _ bindings: [SQLValue] = [], map: (Row) throws -> T) throws -> [T] {
        try lock.withLock {
            let statement = try prepare(sql)
            defer { sqlite3_finalize(statement) }
            try bind(bindings, to: statement)
            var results: [T] = []
            while true {
                let rc = sqlite3_step(statement)
                if rc == SQLITE_DONE { break }
                guard rc == SQLITE_ROW else { throw stepError(rc) }
                results.append(try map(Row(statement: statement)))
            }
            return results
        }
    }

    /// Number of rows changed by the most recent statement on this connection.
    public var changes: Int {
        lock.withLock { handle.map { Int(sqlite3_changes($0)) } ?? 0 }
    }

    /// Runs `body` in an IMMEDIATE transaction; rolls back on any thrown error.
    public func transaction<T>(_ body: () throws -> T) throws -> T {
        try lock.withLock {
            try execute("BEGIN IMMEDIATE")
            do {
                let value = try body()
                try execute("COMMIT")
                return value
            } catch {
                try? execute("ROLLBACK")
                throw error
            }
        }
    }

    // MARK: - Internals

    private func applyKey(_ key: Data) throws {
        let hex = key.map { String(format: "%02x", $0) }.joined()
        // Raw key syntax: SQLCipher uses the bytes directly, skipping PBKDF2.
        try execute("PRAGMA key = \"x'\(hex)'\"")
        // SQLCipher only validates the key when the first page is read.
        do {
            _ = try query("SELECT count(*) FROM sqlite_master") { $0.int(0) }
        } catch let DatabaseError.prepare(_, message, _) {
            throw DatabaseError.keyRejected(message: message)
        } catch let DatabaseError.step(_, message) {
            throw DatabaseError.keyRejected(message: message)
        }
        guard try !cipherVersion().isEmpty else { throw DatabaseError.notEncrypted }
    }

    private func prepare(_ sql: String) throws -> OpaquePointer {
        guard let handle else { throw DatabaseError.open(code: SQLITE_MISUSE, message: "database closed") }
        var statement: OpaquePointer?
        let rc = sqlite3_prepare_v2(handle, sql, -1, &statement, nil)
        guard rc == SQLITE_OK, let statement else {
            throw DatabaseError.prepare(code: rc, message: String(cString: sqlite3_errmsg(handle)), sql: sql)
        }
        return statement
    }

    private static let transient = unsafeBitCast(-1, to: sqlite3_destructor_type.self)

    private func bind(_ values: [SQLValue], to statement: OpaquePointer) throws {
        for (offset, value) in values.enumerated() {
            let index = Int32(offset + 1)
            let rc: Int32
            switch value {
            case .null: rc = sqlite3_bind_null(statement, index)
            case let .integer(v): rc = sqlite3_bind_int64(statement, index, v)
            case let .text(v): rc = sqlite3_bind_text(statement, index, v, -1, Self.transient)
            case let .blob(v):
                rc = v.withUnsafeBytes { sqlite3_bind_blob(statement, index, $0.baseAddress, Int32(v.count), Self.transient) }
            }
            guard rc == SQLITE_OK else { throw DatabaseError.bind(code: rc, index: index) }
        }
    }

    private func stepError(_ rc: Int32) -> DatabaseError {
        let message = handle.map { String(cString: sqlite3_errmsg($0)) } ?? "closed"
        if rc & 0xFF == SQLITE_CONSTRAINT { return .constraint(message: message) }
        return .step(code: rc, message: message)
    }

    private static func applyFileProtection(_ url: URL) throws {
        #if os(iOS)
        // Matches the Keychain class: available to background sync after first unlock.
        try FileManager.default.setAttributes(
            [.protectionKey: FileProtectionType.completeUntilFirstUserAuthentication],
            ofItemAtPath: url.path
        )
        #endif
    }
}

public enum SQLValue: Sendable, Equatable {
    case null
    case integer(Int64)
    case text(String)
    case blob(Data)

    public static func optionalText(_ value: String?) -> SQLValue { value.map(SQLValue.text) ?? .null }
    public static func optionalInteger(_ value: Int64?) -> SQLValue { value.map(SQLValue.integer) ?? .null }
}

/// Read-only view of the current result row; valid only inside the `query` mapping closure.
public struct Row {
    fileprivate let statement: OpaquePointer

    public func isNull(_ column: Int32) -> Bool { sqlite3_column_type(statement, column) == SQLITE_NULL }
    public func int(_ column: Int32) -> Int64 { sqlite3_column_int64(statement, column) }
    public func string(_ column: Int32) -> String? {
        guard let text = sqlite3_column_text(statement, column) else { return nil }
        return String(cString: text)
    }
}
