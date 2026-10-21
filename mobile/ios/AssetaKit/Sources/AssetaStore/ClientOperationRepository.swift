import Foundation

/// Outbox persistence API. The sync engine (Gate 4) drives these transitions; this layer only
/// guarantees they are durable, tenant-scoped and legal.
public protocol ClientOperationRepository: Sendable {
    @discardableResult
    func enqueue(_ operation: NewClientOperation) throws -> ClientOperation
    func operation(id: UUID) throws -> ClientOperation?
    /// PENDING operations whose dependency (if any) is ACKED, oldest first.
    func readyToSend(tenantID: UUID, limit: Int) throws -> [ClientOperation]
    func operations(tenantID: UUID, statuses: Set<ClientOperationStatus>) throws -> [ClientOperation]
    func statusCounts(tenantID: UUID) throws -> [ClientOperationStatus: Int]
    func markSent(id: UUID) throws
    func markAcked(id: UUID, serverRevision: Int64) throws
    func markFailed(id: UUID, error: String) throws
    func requeue(id: UUID) throws
    func quarantine(id: UUID, reason: String) throws
}

public final class SQLiteClientOperationRepository: ClientOperationRepository {
    private let db: EncryptedDatabase

    private static let columns = """
        id, tenant_id, op_type, entity_type, entity_id, payload_json, depends_on,
        created_at_device, status, attempt_count, last_error, server_revision
        """

    public init(database: EncryptedDatabase) {
        self.db = database
    }

    @discardableResult
    public func enqueue(_ op: NewClientOperation) throws -> ClientOperation {
        guard let data = op.payloadJSON.data(using: .utf8),
              (try? JSONSerialization.jsonObject(with: data, options: [.fragmentsAllowed])) != nil
        else { throw OutboxError.invalidPayload }
        return try db.transaction {
            if let dependency = op.dependsOn {
                guard let parent = try operation(id: dependency) else { throw OutboxError.dependencyMissing(dependency) }
                guard parent.tenantID == op.tenantID else { throw OutboxError.crossTenantDependency(dependency) }
            }
            try db.execute(
                """
                INSERT INTO client_operation (id, tenant_id, op_type, entity_type, entity_id, payload_json,
                    depends_on, created_at_device, status, attempt_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', 0)
                """,
                [
                    .text(op.id.uuidString.lowercased()), .text(op.tenantID.uuidString.lowercased()),
                    .text(op.opType), .text(op.entityType), .text(op.entityID.uuidString.lowercased()),
                    .text(op.payloadJSON), .optionalText(op.dependsOn?.uuidString.lowercased()),
                    .integer(op.createdAtDevice.millisecondsSince1970),
                ]
            )
            guard let stored = try operation(id: op.id) else { throw OutboxError.notFound(op.id) }
            return stored
        }
    }

    public func operation(id: UUID) throws -> ClientOperation? {
        try db.query(
            "SELECT \(Self.columns) FROM client_operation WHERE id = ?",
            [.text(id.uuidString.lowercased())],
            map: Self.decode
        ).first
    }

    public func readyToSend(tenantID: UUID, limit: Int) throws -> [ClientOperation] {
        let qualified = Self.columns
            .split(separator: ",")
            .map { "op." + $0.trimmingCharacters(in: .whitespacesAndNewlines) }
            .joined(separator: ", ")
        return try db.query(
            """
            SELECT \(qualified) FROM client_operation op
            LEFT JOIN client_operation dep ON dep.id = op.depends_on
            WHERE op.tenant_id = ? AND op.status = 'PENDING'
              AND (op.depends_on IS NULL OR dep.status = 'ACKED')
            ORDER BY op.created_at_device, op.id
            LIMIT ?
            """,
            [.text(tenantID.uuidString.lowercased()), .integer(Int64(max(limit, 0)))],
            map: Self.decode
        )
    }

    public func operations(tenantID: UUID, statuses: Set<ClientOperationStatus>) throws -> [ClientOperation] {
        guard !statuses.isEmpty else { return [] }
        let ordered = statuses.map(\.rawValue).sorted()
        let placeholders = Array(repeating: "?", count: ordered.count).joined(separator: ", ")
        return try db.query(
            """
            SELECT \(Self.columns) FROM client_operation
            WHERE tenant_id = ? AND status IN (\(placeholders))
            ORDER BY created_at_device, id
            """,
            [.text(tenantID.uuidString.lowercased())] + ordered.map(SQLValue.text),
            map: Self.decode
        )
    }

    public func statusCounts(tenantID: UUID) throws -> [ClientOperationStatus: Int] {
        var counts = Dictionary(uniqueKeysWithValues: ClientOperationStatus.allCases.map { ($0, 0) })
        let rows = try db.query(
            "SELECT status, count(*) FROM client_operation WHERE tenant_id = ? GROUP BY status",
            [.text(tenantID.uuidString.lowercased())]
        ) { row in (row.string(0).flatMap(ClientOperationStatus.init(rawValue:)), Int(row.int(1))) }
        for case let (status?, count) in rows { counts[status] = count }
        return counts
    }

    public func markSent(id: UUID) throws {
        try transition(id, to: .sent, set: "attempt_count = attempt_count + 1")
    }

    public func markAcked(id: UUID, serverRevision: Int64) throws {
        try transition(id, to: .acked, set: "server_revision = ?, last_error = NULL", [.integer(serverRevision)])
    }

    public func markFailed(id: UUID, error: String) throws {
        try transition(id, to: .failed, set: "last_error = ?", [.text(error)])
    }

    public func requeue(id: UUID) throws {
        try transition(id, to: .pending, set: nil)
    }

    public func quarantine(id: UUID, reason: String) throws {
        try transition(id, to: .quarantined, set: "last_error = ?", [.text(reason)])
    }

    // MARK: - Private

    private func transition(
        _ id: UUID,
        to target: ClientOperationStatus,
        set extra: String?,
        _ extraBindings: [SQLValue] = []
    ) throws {
        try db.transaction {
            let sources = target.allowedSources.map(\.rawValue).sorted()
            let placeholders = Array(repeating: "?", count: sources.count).joined(separator: ", ")
            let assignments = ["status = ?"] + (extra.map { [$0] } ?? [])
            try db.execute(
                """
                UPDATE client_operation SET \(assignments.joined(separator: ", "))
                WHERE id = ? AND status IN (\(placeholders))
                """,
                [.text(target.rawValue)] + extraBindings + [.text(id.uuidString.lowercased())] + sources.map(SQLValue.text)
            )
            guard db.changes == 1 else {
                guard try operation(id: id) != nil else { throw OutboxError.notFound(id) }
                throw OutboxError.invalidTransition(id: id, to: target)
            }
        }
    }

    private static func decode(_ row: Row) throws -> ClientOperation {
        func uuid(_ column: Int32) throws -> UUID {
            guard let text = row.string(column), let value = UUID(uuidString: text) else {
                throw DatabaseError.step(code: -1, message: "Corrupt UUID in column \(column)")
            }
            return value
        }
        guard let status = row.string(8).flatMap(ClientOperationStatus.init(rawValue:)) else {
            throw DatabaseError.step(code: -1, message: "Corrupt status")
        }
        return ClientOperation(
            id: try uuid(0),
            tenantID: try uuid(1),
            opType: row.string(2) ?? "",
            entityType: row.string(3) ?? "",
            entityID: try uuid(4),
            payloadJSON: row.string(5) ?? "",
            dependsOn: row.isNull(6) ? nil : try uuid(6),
            createdAtDevice: Date(millisecondsSince1970: row.int(7)),
            status: status,
            attemptCount: Int(row.int(9)),
            lastError: row.string(10),
            serverRevision: row.isNull(11) ? nil : row.int(11)
        )
    }
}
