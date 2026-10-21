import Foundation

/// A server-owned entity as stored locally (raw JSON exactly as the server sent it).
public struct StoredEntity: Equatable, Sendable {
    public let entityType: String
    public let id: UUID
    public let revision: Int64
    public let version: Int64?
    public let json: String

    public init(entityType: String, id: UUID, revision: Int64, version: Int64?, json: String) {
        self.entityType = entityType
        self.id = id
        self.revision = revision
        self.version = version
        self.json = json
    }
}

public struct StoredPolicySnapshot: Equatable, Sendable {
    public let policyType: String
    public let scopeKey: String
    public let versionIDsJSON: String
    public let versionStamp: String
    public let valuesJSON: String
    public let validUntil: Date
    public let receivedAt: Date

    public init(policyType: String, scopeKey: String, versionIDsJSON: String, versionStamp: String,
                valuesJSON: String, validUntil: Date, receivedAt: Date) {
        self.policyType = policyType
        self.scopeKey = scopeKey
        self.versionIDsJSON = versionIDsJSON
        self.versionStamp = versionStamp
        self.valuesJSON = valuesJSON
        self.validUntil = validUntil
        self.receivedAt = receivedAt
    }
}

/// Sync bookkeeping (cursor, registration, clock reference), server-owned entities and policy
/// snapshots. Device-wide values use the empty tenant key.
public final class SyncStateStore: Sendable {
    public static let deviceScope = ""
    let db: EncryptedDatabase

    public init(database: EncryptedDatabase) {
        self.db = database
    }

    // MARK: - Key/value

    public func value(_ key: String, tenant: String) throws -> String? {
        try db.query("SELECT value FROM sync_kv WHERE tenant_id = ? AND key = ?", [.text(tenant), .text(key)]) {
            $0.string(0)
        }.first ?? nil
    }

    public func setValue(_ value: String?, for key: String, tenant: String) throws {
        if let value {
            try db.execute(
                """
                INSERT INTO sync_kv (tenant_id, key, value) VALUES (?, ?, ?)
                ON CONFLICT (tenant_id, key) DO UPDATE SET value = excluded.value
                """,
                [.text(tenant), .text(key), .text(value)]
            )
        } else {
            try db.execute("DELETE FROM sync_kv WHERE tenant_id = ? AND key = ?", [.text(tenant), .text(key)])
        }
    }

    // MARK: - Entities

    /// Upserts by id. An incoming row replaces the stored one only if its `revision` (the pull
    /// cursor it arrived with) is not older and, when both carry a server `version`, the version is
    /// not older either — so a late or replayed page never rolls server data back.
    /// Returns the number of rows written.
    @discardableResult
    public func upsert(_ entities: [StoredEntity], tenantID: UUID) throws -> Int {
        try db.transaction {
            var written = 0
            for entity in entities {
                try db.execute(
                    """
                    INSERT INTO sync_entity (tenant_id, entity_type, id, revision, version, json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT (tenant_id, entity_type, id) DO UPDATE SET
                        revision = excluded.revision, version = excluded.version, json = excluded.json
                    WHERE excluded.revision >= sync_entity.revision
                      AND (excluded.version IS NULL OR sync_entity.version IS NULL
                           OR excluded.version >= sync_entity.version)
                    """,
                    [.text(tenantID.lowercased), .text(entity.entityType), .text(entity.id.lowercased),
                     .integer(entity.revision), .optionalInteger(entity.version), .text(entity.json)]
                )
                written += db.changes
            }
            return written
        }
    }

    public func entities(type: String, tenantID: UUID) throws -> [StoredEntity] {
        try db.query(
            "SELECT entity_type, id, revision, version, json FROM sync_entity WHERE tenant_id = ? AND entity_type = ?",
            [.text(tenantID.lowercased), .text(type)], map: Self.decodeEntity
        )
    }

    public func entity(type: String, id: UUID, tenantID: UUID) throws -> StoredEntity? {
        try db.query(
            """
            SELECT entity_type, id, revision, version, json FROM sync_entity
            WHERE tenant_id = ? AND entity_type = ? AND id = ?
            """,
            [.text(tenantID.lowercased), .text(type), .text(id.lowercased)], map: Self.decodeEntity
        ).first
    }

    /// Replaces all entities of a tenant (bootstrap is an authoritative snapshot).
    public func replaceAll(_ entities: [StoredEntity], tenantID: UUID) throws {
        try db.transaction {
            try db.execute("DELETE FROM sync_entity WHERE tenant_id = ?", [.text(tenantID.lowercased)])
            try upsert(entities, tenantID: tenantID)
        }
    }

    // MARK: - Policy snapshots

    public func savePolicySnapshots(_ snapshots: [StoredPolicySnapshot], tenantID: UUID) throws {
        try db.transaction {
            for snapshot in snapshots {
                try db.execute(
                    """
                    INSERT INTO policy_snapshot (tenant_id, policy_type, scope_key, version_ids_json, version_stamp,
                        values_json, valid_until, received_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (tenant_id, policy_type, scope_key) DO UPDATE SET
                        version_ids_json = excluded.version_ids_json, version_stamp = excluded.version_stamp,
                        values_json = excluded.values_json, valid_until = excluded.valid_until,
                        received_at = excluded.received_at
                    WHERE excluded.received_at >= policy_snapshot.received_at
                    """,
                    [.text(tenantID.lowercased), .text(snapshot.policyType), .text(snapshot.scopeKey),
                     .text(snapshot.versionIDsJSON), .text(snapshot.versionStamp), .text(snapshot.valuesJSON),
                     .integer(snapshot.validUntil.millisecondsSince1970),
                     .integer(snapshot.receivedAt.millisecondsSince1970)]
                )
            }
        }
    }

    public func policySnapshots(policyType: String, tenantID: UUID) throws -> [StoredPolicySnapshot] {
        try db.query(
            """
            SELECT policy_type, scope_key, version_ids_json, version_stamp, values_json, valid_until, received_at
            FROM policy_snapshot WHERE tenant_id = ? AND policy_type = ? ORDER BY scope_key
            """,
            [.text(tenantID.lowercased), .text(policyType)]
        ) { row in
            StoredPolicySnapshot(
                policyType: row.string(0) ?? "", scopeKey: row.string(1) ?? "", versionIDsJSON: row.string(2) ?? "[]",
                versionStamp: row.string(3) ?? "", valuesJSON: row.string(4) ?? "{}",
                validUntil: Date(millisecondsSince1970: row.int(5)), receivedAt: Date(millisecondsSince1970: row.int(6))
            )
        }
    }

    private static func decodeEntity(_ row: Row) throws -> StoredEntity {
        guard let id = row.string(1).flatMap(UUID.init(uuidString:)) else {
            throw DatabaseError.step(code: -1, message: "Corrupt sync_entity id")
        }
        return StoredEntity(entityType: row.string(0) ?? "", id: id, revision: row.int(2),
                            version: row.isNull(3) ? nil : row.int(3), json: row.string(4) ?? "{}")
    }
}
