import Foundation

/// One forward-only schema migration. Versions are dense and start at 1.
/// Never edit a shipped migration; append a new one.
public struct Migration: Sendable {
    public let version: Int
    public let name: String
    public let statements: [String]

    public init(version: Int, name: String, statements: [String]) {
        self.version = version
        self.name = name
        self.statements = statements
    }
}

/// Applies pending migrations, each in its own transaction, tracking progress in
/// `PRAGMA user_version` plus an auditable `schema_migration` table.
public struct Migrator: Sendable {
    public let migrations: [Migration]

    public init(migrations: [Migration]) {
        precondition(
            migrations.enumerated().allSatisfy { $0.offset + 1 == $0.element.version },
            "Migration versions must be dense and ordered starting at 1"
        )
        self.migrations = migrations
    }

    public static let asseta = Migrator(migrations: AssetaSchema.migrations)

    public func currentVersion(_ db: EncryptedDatabase) throws -> Int {
        Int(try db.query("PRAGMA user_version") { $0.int(0) }.first ?? 0)
    }

    @discardableResult
    public func migrate(_ db: EncryptedDatabase, now: Date = Date()) throws -> Int {
        let current = try currentVersion(db)
        if let latest = migrations.last?.version, current > latest {
            throw DatabaseError.migration(version: current, message: "Database is newer than this app build (\(latest))")
        }
        for migration in migrations where migration.version > current {
            do {
                try db.transaction {
                    try db.execute("""
                        CREATE TABLE IF NOT EXISTS schema_migration (
                            version INTEGER PRIMARY KEY NOT NULL,
                            name TEXT NOT NULL,
                            applied_at INTEGER NOT NULL
                        )
                        """)
                    for statement in migration.statements {
                        try db.execute(statement)
                    }
                    try db.execute(
                        "INSERT INTO schema_migration (version, name, applied_at) VALUES (?, ?, ?)",
                        [.integer(Int64(migration.version)), .text(migration.name), .integer(now.millisecondsSince1970)]
                    )
                    // PRAGMA cannot be parameterized; version is a trusted Int.
                    try db.execute("PRAGMA user_version = \(migration.version)")
                }
            } catch {
                throw DatabaseError.migration(version: migration.version, message: String(describing: error))
            }
        }
        return try currentVersion(db)
    }
}

/// The versioned local schema of the Asseta mobile apps.
public enum AssetaSchema {
    public static let migrations: [Migration] = [
        Migration(
            version: 1,
            name: "create_client_operation_outbox",
            statements: [
                """
                CREATE TABLE client_operation (
                    id TEXT PRIMARY KEY NOT NULL CHECK (length(id) = 36),
                    tenant_id TEXT NOT NULL CHECK (length(tenant_id) = 36),
                    op_type TEXT NOT NULL CHECK (length(op_type) > 0),
                    entity_type TEXT NOT NULL CHECK (length(entity_type) > 0),
                    entity_id TEXT NOT NULL CHECK (length(entity_id) = 36),
                    payload_json TEXT NOT NULL CHECK (json_valid(payload_json)),
                    depends_on TEXT NULL REFERENCES client_operation(id) ON DELETE RESTRICT,
                    created_at_device INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'PENDING'
                        CHECK (status IN ('PENDING','SENT','ACKED','FAILED','QUARANTINED')),
                    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
                    last_error TEXT NULL,
                    server_revision INTEGER NULL,
                    CHECK (depends_on IS NULL OR depends_on <> id),
                    CHECK (status <> 'ACKED' OR server_revision IS NOT NULL)
                )
                """,
                "CREATE INDEX ix_client_operation_status_created ON client_operation (tenant_id, status, created_at_device)",
                "CREATE INDEX ix_client_operation_depends_on ON client_operation (depends_on)",
            ]
        ),
    ]
}

extension Date {
    var millisecondsSince1970: Int64 { Int64((timeIntervalSince1970 * 1000).rounded()) }
    init(millisecondsSince1970 ms: Int64) { self.init(timeIntervalSince1970: TimeInterval(ms) / 1000) }
}
