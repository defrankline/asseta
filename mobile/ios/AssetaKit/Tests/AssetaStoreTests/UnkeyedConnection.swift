import Foundation
import SQLCipher

/// Opens a database file *without* supplying a key, as an attacker with only the file would.
struct UnkeyedConnection {
    struct Failure: Error { let code: Int32; let message: String }
    let url: URL

    init(url: URL) throws { self.url = url }

    func firstText(_ sql: String) throws -> String? {
        var db: OpaquePointer?
        guard sqlite3_open_v2(url.path, &db, SQLITE_OPEN_READONLY, nil) == SQLITE_OK else {
            defer { sqlite3_close(db) }
            throw Failure(code: -1, message: "open failed")
        }
        defer { sqlite3_close(db) }
        var statement: OpaquePointer?
        let rc = sqlite3_prepare_v2(db, sql, -1, &statement, nil)
        defer { sqlite3_finalize(statement) }
        guard rc == SQLITE_OK else { throw Failure(code: rc, message: String(cString: sqlite3_errmsg(db))) }
        let step = sqlite3_step(statement)
        guard step == SQLITE_ROW else { throw Failure(code: step, message: String(cString: sqlite3_errmsg(db))) }
        return sqlite3_column_text(statement, 0).map { String(cString: $0) }
    }
}
