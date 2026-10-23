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
        Migration(
            version: 2,
            name: "outbox_sync_protocol",
            statements: OutboxV2.statements
        ),
        Migration(
            version: 3,
            name: "sync_state_entities_policies",
            statements: [
                """
                CREATE TABLE sync_kv (
                    tenant_id TEXT NOT NULL,
                    key TEXT NOT NULL CHECK (length(key) > 0),
                    value TEXT NOT NULL,
                    PRIMARY KEY (tenant_id, key)
                )
                """,
                """
                CREATE TABLE sync_entity (
                    tenant_id TEXT NOT NULL CHECK (length(tenant_id) = 36),
                    entity_type TEXT NOT NULL CHECK (length(entity_type) > 0),
                    id TEXT NOT NULL CHECK (length(id) = 36),
                    revision INTEGER NOT NULL,
                    version INTEGER NULL,
                    json TEXT NOT NULL CHECK (json_valid(json)),
                    PRIMARY KEY (tenant_id, entity_type, id)
                )
                """,
                """
                CREATE TABLE policy_snapshot (
                    tenant_id TEXT NOT NULL CHECK (length(tenant_id) = 36),
                    policy_type TEXT NOT NULL,
                    scope_key TEXT NOT NULL,
                    version_ids_json TEXT NOT NULL CHECK (json_valid(version_ids_json)),
                    version_stamp TEXT NOT NULL,
                    values_json TEXT NOT NULL CHECK (json_valid(values_json)),
                    valid_until INTEGER NOT NULL,
                    received_at INTEGER NOT NULL,
                    PRIMARY KEY (tenant_id, policy_type, scope_key)
                )
                """,
            ]
        ),
        Migration(
            version: 4,
            name: "finance_receipts_cash_custody",
            statements: FinanceV4.statements
        ),
        Migration(
            version: 5,
            name: "per_user_field_data",
            statements: OwnersV5.statements
        ),
        Migration(
            version: 6,
            name: "supervisor_inbox",
            statements: InboxV6.statements
        ),
    ]
}

/// Migration 2 rebuilds `client_operation` (SQLite cannot alter CHECK constraints): adds the
/// CONFLICT state, the stored server result (required for ACKED instead of a revision, because
/// push results carry the entity, not a revision), error code and retry time; moves
/// dependencies to a join table (the protocol allows several) and adds the local attachment
/// queue whose upload gates dependent operations.
enum OutboxV2 {
    static let statements: [String] = [
        "ALTER TABLE client_operation RENAME TO client_operation_v1",
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
                CHECK (status IN ('PENDING','SENT','ACKED','FAILED','CONFLICT','QUARANTINED')),
            attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
            last_error TEXT NULL,
            error_code TEXT NULL,
            server_revision INTEGER NULL,
            server_result_json TEXT NULL CHECK (server_result_json IS NULL OR json_valid(server_result_json)),
            next_attempt_at INTEGER NULL,
            CHECK (depends_on IS NULL OR depends_on <> id),
            CHECK (status <> 'ACKED' OR server_result_json IS NOT NULL)
        )
        """,
        """
        INSERT INTO client_operation (id, tenant_id, op_type, entity_type, entity_id, payload_json, depends_on,
            created_at_device, status, attempt_count, last_error, server_revision, server_result_json)
        SELECT id, tenant_id, op_type, entity_type, entity_id, payload_json, depends_on, created_at_device,
            status, attempt_count, last_error, server_revision,
            CASE WHEN status = 'ACKED' THEN json_object('server_revision', server_revision) END
        FROM client_operation_v1
        """,
        "UPDATE client_operation_v1 SET depends_on = NULL",
        "DROP TABLE client_operation_v1",
        "CREATE INDEX ix_client_operation_status_created ON client_operation (tenant_id, status, created_at_device)",
        "CREATE INDEX ix_client_operation_depends_on ON client_operation (depends_on)",
        """
        CREATE TABLE client_operation_dependency (
            operation_id TEXT NOT NULL REFERENCES client_operation(id) ON DELETE CASCADE,
            depends_on_id TEXT NOT NULL REFERENCES client_operation(id) ON DELETE RESTRICT,
            PRIMARY KEY (operation_id, depends_on_id),
            CHECK (operation_id <> depends_on_id)
        )
        """,
        """
        INSERT INTO client_operation_dependency (operation_id, depends_on_id)
        SELECT id, depends_on FROM client_operation WHERE depends_on IS NOT NULL
        """,
        "CREATE INDEX ix_client_operation_dependency_parent ON client_operation_dependency (depends_on_id)",
        """
        CREATE TABLE local_attachment (
            id TEXT PRIMARY KEY NOT NULL CHECK (length(id) = 36),
            tenant_id TEXT NOT NULL CHECK (length(tenant_id) = 36),
            purpose TEXT NOT NULL CHECK (purpose IN ('METER_PHOTO','SIGNATURE','RESET_EVIDENCE')),
            file_name TEXT NOT NULL CHECK (length(file_name) > 0),
            sha256 TEXT NOT NULL CHECK (length(sha256) = 64),
            size_bytes INTEGER NOT NULL CHECK (size_bytes > 0),
            content_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','COMPLETE','FAILED')),
            session_id TEXT NULL,
            session_expires_at INTEGER NULL,
            chunk_size INTEGER NULL CHECK (chunk_size IS NULL OR chunk_size > 0),
            received_chunks TEXT NOT NULL DEFAULT '',
            attachment_id TEXT NULL,
            attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
            last_error TEXT NULL,
            next_attempt_at INTEGER NULL,
            created_at INTEGER NOT NULL,
            CHECK (status <> 'COMPLETE' OR attachment_id IS NOT NULL)
        )
        """,
        """
        CREATE TABLE operation_attachment (
            operation_id TEXT NOT NULL REFERENCES client_operation(id) ON DELETE CASCADE,
            attachment_local_id TEXT NOT NULL REFERENCES local_attachment(id) ON DELETE RESTRICT,
            payload_field TEXT NOT NULL CHECK (payload_field IN ('photo_attachment_id','signature_attachment_id')),
            PRIMARY KEY (operation_id, attachment_local_id)
        )
        """,
    ]
}

extension Date {
    public var millisecondsSince1970: Int64 { Int64((timeIntervalSince1970 * 1000).rounded()) }
    public init(millisecondsSince1970 ms: Int64) { self.init(timeIntervalSince1970: TimeInterval(ms) / 1000) }
}
