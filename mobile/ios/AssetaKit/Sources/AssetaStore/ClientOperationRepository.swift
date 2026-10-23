import Foundation

/// Outbox persistence API. The sync engine drives these transitions; this layer only guarantees
/// they are durable, tenant-scoped and legal.
public protocol ClientOperationRepository: Sendable {
    @discardableResult
    func enqueue(_ operation: NewClientOperation) throws -> ClientOperation
    func operation(id: UUID) throws -> ClientOperation?
    /// Sendable operations, oldest first: PENDING (or QUARANTINED, for re-sending) whose retry time
    /// has come, whose dependencies are all ACKED and whose attachments are all uploaded. `owner`
    /// (the signed-in user's subject) limits them to that user's operations — another user's are
    /// never sent under this token; nil means every owner.
    func readyToSend(tenantID: UUID, owner: String?, now: Date, limit: Int) throws -> [ClientOperation]
    func operations(tenantID: UUID, owner: String?, statuses: Set<ClientOperationStatus>) throws -> [ClientOperation]
    /// Operations whose payload references `jobID`, oldest first.
    func operations(tenantID: UUID, owner: String?, jobID: UUID) throws -> [ClientOperation]
    func statusCounts(tenantID: UUID, owner: String?) throws -> [ClientOperationStatus: Int]
    /// Unsynced operations queued on this phone by other users than `owner`, per user: held (kept,
    /// never sent under this user's token) until their owner signs in again.
    func heldAccounts(tenantID: UUID, excluding owner: String) throws -> [HeldAccount]
    func markSent(id: UUID) throws
    func markAcked(id: UUID, resultJSON: String, serverRevision: Int64?) throws
    func markFailed(id: UUID, code: String?, message: String, resultJSON: String?) throws
    func markConflict(id: UUID, code: String?, message: String, resultJSON: String?) throws
    func quarantine(id: UUID, reason: String, resultJSON: String?, retryAt: Date?) throws
    /// SENT → PENDING without an outcome (DEFERRED, lost response, network error, 5xx).
    func release(id: UUID, error: String?, retryAt: Date?) throws
    /// FAILED → PENDING on explicit user request.
    func requeue(id: UUID) throws
    /// After a crash/termination: every SENT operation goes back to PENDING (safe: idempotent ids).
    @discardableResult
    func recoverInFlight(tenantID: UUID) throws -> Int
}

/// Another user's unsynced work on this phone (`label` nil when that user is not known).
public struct HeldAccount: Sendable, Equatable {
    public let subject: String
    public let label: String?
    public let count: Int

    public init(subject: String, label: String?, count: Int) {
        self.subject = subject
        self.label = label
        self.count = count
    }
}

extension ClientOperationRepository {
    public func readyToSend(tenantID: UUID, limit: Int) throws -> [ClientOperation] {
        try readyToSend(tenantID: tenantID, owner: nil, now: Date(), limit: limit)
    }

    public func readyToSend(tenantID: UUID, now: Date, limit: Int) throws -> [ClientOperation] {
        try readyToSend(tenantID: tenantID, owner: nil, now: now, limit: limit)
    }

    public func operations(tenantID: UUID, statuses: Set<ClientOperationStatus>) throws -> [ClientOperation] {
        try operations(tenantID: tenantID, owner: nil, statuses: statuses)
    }

    public func operations(tenantID: UUID, jobID: UUID) throws -> [ClientOperation] {
        try operations(tenantID: tenantID, owner: nil, jobID: jobID)
    }

    public func statusCounts(tenantID: UUID) throws -> [ClientOperationStatus: Int] {
        try statusCounts(tenantID: tenantID, owner: nil)
    }

    public func markAcked(id: UUID, serverRevision: Int64) throws {
        try markAcked(id: id, resultJSON: #"{"server_revision":\#(serverRevision)}"#, serverRevision: serverRevision)
    }

    public func markFailed(id: UUID, error: String) throws {
        try markFailed(id: id, code: nil, message: error, resultJSON: nil)
    }

    public func quarantine(id: UUID, reason: String) throws {
        try quarantine(id: id, reason: reason, resultJSON: nil, retryAt: nil)
    }
}

public final class SQLiteClientOperationRepository: ClientOperationRepository {
    private let db: EncryptedDatabase

    private static let columns = [
        "id", "tenant_id", "op_type", "entity_type", "entity_id", "payload_json", "created_at_device", "status",
        "attempt_count", "last_error", "error_code", "server_revision", "server_result_json", "next_attempt_at",
        "owner_subject", "owner_label",
    ]

    private static func select(alias: String) -> String {
        let cols = columns.map { "\(alias).\($0)" }.joined(separator: ", ")
        return """
            SELECT \(cols),
              (SELECT group_concat(d.depends_on_id) FROM client_operation_dependency d WHERE d.operation_id = \(alias).id)
            FROM client_operation \(alias)
            """
    }

    public init(database: EncryptedDatabase) {
        self.db = database
    }

    @discardableResult
    public func enqueue(_ op: NewClientOperation) throws -> ClientOperation {
        guard let data = op.payloadJSON.data(using: .utf8),
              (try? JSONSerialization.jsonObject(with: data, options: [.fragmentsAllowed])) != nil
        else { throw OutboxError.invalidPayload }
        return try db.transaction {
            for dependency in op.dependsOn {
                guard let parent = try operation(id: dependency) else { throw OutboxError.dependencyMissing(dependency) }
                guard parent.tenantID == op.tenantID else { throw OutboxError.crossTenantDependency(dependency) }
            }
            try db.execute(
                """
                INSERT INTO client_operation (id, tenant_id, op_type, entity_type, entity_id, payload_json,
                    depends_on, created_at_device, status, attempt_count, owner_subject, owner_label)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING', 0, ?, ?)
                """,
                [
                    .text(op.id.lowercased), .text(op.tenantID.lowercased), .text(op.opType), .text(op.entityType),
                    .text(op.entityID.lowercased), .text(op.payloadJSON), .optionalText(op.dependsOn.first?.lowercased),
                    .integer(op.createdAtDevice.millisecondsSince1970), .optionalText(op.owner?.subject),
                    .optionalText(op.owner?.label),
                ]
            )
            for dependency in op.dependsOn {
                try db.execute(
                    "INSERT INTO client_operation_dependency (operation_id, depends_on_id) VALUES (?, ?)",
                    [.text(op.id.lowercased), .text(dependency.lowercased)]
                )
            }
            for attachment in op.attachments {
                let exists = try db.query(
                    "SELECT count(*) FROM local_attachment WHERE id = ? AND tenant_id = ?",
                    [.text(attachment.localID.lowercased), .text(op.tenantID.lowercased)]
                ) { $0.int(0) }.first ?? 0
                guard exists == 1 else { throw OutboxError.attachmentMissing(attachment.localID) }
                try db.execute(
                    "INSERT INTO operation_attachment (operation_id, attachment_local_id, payload_field) VALUES (?, ?, ?)",
                    [.text(op.id.lowercased), .text(attachment.localID.lowercased), .text(attachment.field.rawValue)]
                )
            }
            guard let stored = try operation(id: op.id) else { throw OutboxError.notFound(op.id) }
            return stored
        }
    }

    public func operation(id: UUID) throws -> ClientOperation? {
        try db.query("\(Self.select(alias: "op")) WHERE op.id = ?", [.text(id.lowercased)], map: Self.decode).first
    }

    public func readyToSend(tenantID: UUID, owner: String?, now: Date, limit: Int) throws -> [ClientOperation] {
        try db.query(
            """
            \(Self.select(alias: "op"))
            WHERE op.tenant_id = ? AND (? IS NULL OR op.owner_subject = ?) AND op.status IN ('PENDING', 'QUARANTINED')
              AND (op.next_attempt_at IS NULL OR op.next_attempt_at <= ?)
              AND NOT EXISTS (
                SELECT 1 FROM client_operation_dependency d JOIN client_operation p ON p.id = d.depends_on_id
                WHERE d.operation_id = op.id AND p.status <> 'ACKED')
              AND NOT EXISTS (
                SELECT 1 FROM operation_attachment oa JOIN local_attachment a ON a.id = oa.attachment_local_id
                WHERE oa.operation_id = op.id AND a.status <> 'COMPLETE')
            ORDER BY op.created_at_device, op.id
            LIMIT ?
            """,
            [.text(tenantID.lowercased), .optionalText(owner), .optionalText(owner), .integer(now.millisecondsSince1970),
             .integer(Int64(max(limit, 0)))],
            map: Self.decode
        )
    }

    public func operations(tenantID: UUID, owner: String?, statuses: Set<ClientOperationStatus>) throws -> [ClientOperation] {
        guard !statuses.isEmpty else { return [] }
        let ordered = statuses.map(\.rawValue).sorted()
        let placeholders = Array(repeating: "?", count: ordered.count).joined(separator: ", ")
        return try db.query(
            """
            \(Self.select(alias: "op"))
            WHERE op.tenant_id = ? AND (? IS NULL OR op.owner_subject = ?) AND op.status IN (\(placeholders))
            ORDER BY op.created_at_device, op.id
            """,
            [.text(tenantID.lowercased), .optionalText(owner), .optionalText(owner)] + ordered.map(SQLValue.text),
            map: Self.decode
        )
    }

    public func operations(tenantID: UUID, owner: String?, jobID: UUID) throws -> [ClientOperation] {
        try db.query(
            """
            \(Self.select(alias: "op"))
            WHERE op.tenant_id = ? AND (? IS NULL OR op.owner_subject = ?)
              AND lower(json_extract(op.payload_json, '$.job_id')) = ?
            ORDER BY op.created_at_device, op.id
            """,
            [.text(tenantID.lowercased), .optionalText(owner), .optionalText(owner), .text(jobID.lowercased)],
            map: Self.decode
        )
    }

    public func statusCounts(tenantID: UUID, owner: String?) throws -> [ClientOperationStatus: Int] {
        var counts = Dictionary(uniqueKeysWithValues: ClientOperationStatus.allCases.map { ($0, 0) })
        let rows = try db.query(
            """
            SELECT status, count(*) FROM client_operation WHERE tenant_id = ? AND (? IS NULL OR owner_subject = ?)
            GROUP BY status
            """,
            [.text(tenantID.lowercased), .optionalText(owner), .optionalText(owner)]
        ) { row in (row.string(0).flatMap(ClientOperationStatus.init(rawValue:)), Int(row.int(1))) }
        for case let (status?, count) in rows { counts[status] = count }
        return counts
    }

    public func heldAccounts(tenantID: UUID, excluding owner: String) throws -> [HeldAccount] {
        try db.query(
            """
            SELECT owner_subject, max(owner_label), count(*) FROM client_operation
            WHERE tenant_id = ? AND owner_subject IS NOT NULL AND owner_subject <> ? AND status <> 'ACKED'
            GROUP BY owner_subject ORDER BY min(created_at_device)
            """,
            [.text(tenantID.lowercased), .text(owner)]
        ) { HeldAccount(subject: $0.string(0) ?? "", label: $0.string(1), count: Int($0.int(2))) }
    }

    public func markSent(id: UUID) throws {
        try transition(id, to: .sent, set: ["attempt_count = attempt_count + 1"])
    }

    public func markAcked(id: UUID, resultJSON: String, serverRevision: Int64?) throws {
        try transition(
            id, to: .acked,
            set: ["server_result_json = ?", "server_revision = ?", "last_error = NULL", "error_code = NULL",
                  "next_attempt_at = NULL"],
            [.text(resultJSON), .optionalInteger(serverRevision)]
        )
    }

    public func markFailed(id: UUID, code: String?, message: String, resultJSON: String?) throws {
        try transition(
            id, to: .failed, set: ["last_error = ?", "error_code = ?", "server_result_json = ?"],
            [.text(message), .optionalText(code), .optionalText(resultJSON)]
        )
    }

    public func markConflict(id: UUID, code: String?, message: String, resultJSON: String?) throws {
        try transition(
            id, to: .conflict, set: ["last_error = ?", "error_code = ?", "server_result_json = ?"],
            [.text(message), .optionalText(code), .optionalText(resultJSON)]
        )
    }

    public func quarantine(id: UUID, reason: String, resultJSON: String?, retryAt: Date?) throws {
        try transition(
            id, to: .quarantined,
            set: ["last_error = ?", "error_code = 'SUBSCRIPTION_READ_ONLY'", "server_result_json = ?",
                  "next_attempt_at = ?"],
            [.text(reason), .optionalText(resultJSON), .optionalInteger(retryAt?.millisecondsSince1970)]
        )
    }

    public func release(id: UUID, error: String?, retryAt: Date?) throws {
        try db.transaction {
            guard let current = try operation(id: id) else { throw OutboxError.notFound(id) }
            guard current.status == .sent else { throw OutboxError.invalidTransition(id: id, to: .pending) }
            // A quarantined operation that is re-sent without an outcome stays quarantined.
            let target: ClientOperationStatus = current.errorCode == "SUBSCRIPTION_READ_ONLY" ? .quarantined : .pending
            try db.execute(
                "UPDATE client_operation SET status = ?, last_error = ?, next_attempt_at = ? WHERE id = ?",
                [.text(target.rawValue), .optionalText(error), .optionalInteger(retryAt?.millisecondsSince1970),
                 .text(id.lowercased)]
            )
        }
    }

    public func requeue(id: UUID) throws {
        try transition(id, to: .pending, set: ["next_attempt_at = NULL"], allowedFrom: [.failed])
    }

    @discardableResult
    public func recoverInFlight(tenantID: UUID) throws -> Int {
        try db.transaction {
            try db.execute(
                """
                UPDATE client_operation
                SET status = CASE WHEN error_code = 'SUBSCRIPTION_READ_ONLY' THEN 'QUARANTINED' ELSE 'PENDING' END
                WHERE tenant_id = ? AND status = 'SENT'
                """,
                [.text(tenantID.lowercased)]
            )
            return db.changes
        }
    }

    // MARK: - Private

    private func transition(
        _ id: UUID,
        to target: ClientOperationStatus,
        set extra: [String],
        _ extraBindings: [SQLValue] = [],
        allowedFrom: Set<ClientOperationStatus>? = nil
    ) throws {
        try db.transaction {
            let sources = (allowedFrom ?? target.allowedSources).map(\.rawValue).sorted()
            let placeholders = Array(repeating: "?", count: sources.count).joined(separator: ", ")
            let assignments = ["status = ?"] + extra
            try db.execute(
                """
                UPDATE client_operation SET \(assignments.joined(separator: ", "))
                WHERE id = ? AND status IN (\(placeholders))
                """,
                [.text(target.rawValue)] + extraBindings + [.text(id.lowercased)] + sources.map(SQLValue.text)
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
        guard let status = row.string(7).flatMap(ClientOperationStatus.init(rawValue:)) else {
            throw DatabaseError.step(code: -1, message: "Corrupt status")
        }
        let dependencies = (row.string(16) ?? "")
            .split(separator: ",")
            .compactMap { UUID(uuidString: String($0)) }
            .sorted { $0.uuidString < $1.uuidString }
        return ClientOperation(
            id: try uuid(0),
            tenantID: try uuid(1),
            opType: row.string(2) ?? "",
            entityType: row.string(3) ?? "",
            entityID: try uuid(4),
            payloadJSON: row.string(5) ?? "",
            dependencies: dependencies,
            createdAtDevice: Date(millisecondsSince1970: row.int(6)),
            status: status,
            attemptCount: Int(row.int(8)),
            lastError: row.string(9),
            errorCode: row.string(10),
            serverRevision: row.isNull(11) ? nil : row.int(11),
            serverResultJSON: row.string(12),
            nextAttemptAt: row.isNull(13) ? nil : Date(millisecondsSince1970: row.int(13)),
            ownerSubject: row.string(14),
            ownerLabel: row.string(15)
        )
    }
}

extension UUID {
    /// Canonical lowercase text used for every stored and transmitted id.
    public var lowercased: String { uuidString.lowercased() }
}
