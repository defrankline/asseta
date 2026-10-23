import Foundation

/// Migration 6 (supervisor inbox), non-destructive:
/// - `inbox_record`: the signed-in supervisor's own records as the server knows them
///   (SUPERVISOR_INBOX_V1), kept as the server JSON with the columns lists filter and sort on;
/// - rebuilds `operation_attachment` so a meter reset request's evidence photo can fill
///   `evidence_upload_id` (SQLite cannot alter a CHECK; the child table is copied row by row).
/// Same table and columns as Android Room v7 (`inbox_record`).
enum InboxV6 {
    static let statements: [String] = [
        """
        CREATE TABLE inbox_record (
            kind TEXT NOT NULL CHECK (length(kind) > 0),
            id TEXT NOT NULL CHECK (length(id) = 36),
            tenant_id TEXT NOT NULL CHECK (length(tenant_id) = 36),
            client_id TEXT NULL,
            job_id TEXT NULL,
            machine_id TEXT NULL,
            status TEXT NULL,
            occurred_at INTEGER NOT NULL,
            sync_revision INTEGER NOT NULL,
            json TEXT NOT NULL CHECK (json_valid(json)),
            PRIMARY KEY (kind, id)
        )
        """,
        "CREATE INDEX ix_inbox_record_kind ON inbox_record (tenant_id, kind, occurred_at)",
        "CREATE INDEX ix_inbox_record_client ON inbox_record (client_id)",
        "CREATE INDEX ix_inbox_record_job ON inbox_record (job_id)",
        "ALTER TABLE operation_attachment RENAME TO operation_attachment_v5",
        """
        CREATE TABLE operation_attachment (
            operation_id TEXT NOT NULL REFERENCES client_operation(id) ON DELETE CASCADE,
            attachment_local_id TEXT NOT NULL REFERENCES local_attachment(id) ON DELETE RESTRICT,
            payload_field TEXT NOT NULL CHECK (payload_field IN
                ('photo_attachment_id','signature_attachment_id','receipt_upload_ids','evidence_upload_id')),
            PRIMARY KEY (operation_id, attachment_local_id)
        )
        """,
        """
        INSERT INTO operation_attachment (operation_id, attachment_local_id, payload_field)
        SELECT operation_id, attachment_local_id, payload_field FROM operation_attachment_v5
        """,
        "DROP TABLE operation_attachment_v5",
        "CREATE INDEX ix_operation_attachment_local ON operation_attachment (attachment_local_id)",
    ]
}

/// One server record of the supervisor inbox.
public struct InboxRecord: Equatable, Sendable {
    public enum Kind: String, Sendable, CaseIterable {
        case meterCapture = "METER_CAPTURE", meterReset = "METER_RESET", jobActivity = "JOB_ACTIVITY"
        case acknowledgement = "ACKNOWLEDGEMENT", expense = "EXPENSE", fuelEvent = "FUEL_EVENT"
        case cashCollection = "CASH_COLLECTION", cashHandover = "CASH_HANDOVER"
    }

    public let kind: Kind
    public let id: UUID
    /// Device client id of the record (nil for server-created ones); a meter capture's id is its client id.
    public let clientID: UUID?
    public let jobID: UUID?
    public let machineID: UUID?
    /// Server status (capture state or review status, expense/settlement/reset status).
    public let status: String?
    /// When it happened (captured / started / incurred / received / handed): list order and pruning.
    public let occurredAt: Date
    public let syncRevision: Int64
    public let json: String

    public init(kind: Kind, id: UUID, clientID: UUID?, jobID: UUID?, machineID: UUID?, status: String?, occurredAt: Date,
                syncRevision: Int64, json: String) {
        self.kind = kind
        self.id = id
        self.clientID = clientID
        self.jobID = jobID
        self.machineID = machineID
        self.status = status
        self.occurredAt = occurredAt
        self.syncRevision = syncRevision
        self.json = json
    }

    /// Statuses that keep a record past the pruning window (still waiting for the office).
    public static let openStatuses = ["PENDING_APPROVAL", "CLAIMED", "PENDING", "PENDING_REVIEW", "PROVISIONAL"]
}

/// Server-owned, read-only supervisor inbox (`inbox_record`), upserted by (kind, id, sync_revision)
/// and cleared with the tenant's other server data when another user signs in.
public final class InboxStore: Sendable {
    let db: EncryptedDatabase

    public init(database: EncryptedDatabase) {
        self.db = database
    }

    /// An older (lookback replay) revision never overwrites a newer one. Returns rows written.
    @discardableResult
    public func upsert(_ records: [InboxRecord], tenantID: UUID) throws -> Int {
        try db.transaction {
            var written = 0
            for r in records {
                try db.execute(
                    """
                    INSERT INTO inbox_record (kind, id, tenant_id, client_id, job_id, machine_id, status, occurred_at,
                        sync_revision, json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (kind, id) DO UPDATE SET
                        tenant_id = excluded.tenant_id, client_id = excluded.client_id, job_id = excluded.job_id,
                        machine_id = excluded.machine_id, status = excluded.status, occurred_at = excluded.occurred_at,
                        sync_revision = excluded.sync_revision, json = excluded.json
                    WHERE excluded.sync_revision >= inbox_record.sync_revision
                    """,
                    [.text(r.kind.rawValue), .text(r.id.lowercased), .text(tenantID.lowercased),
                     .optionalText(r.clientID?.lowercased), .optionalText(r.jobID?.lowercased),
                     .optionalText(r.machineID?.lowercased), .optionalText(r.status),
                     .integer(r.occurredAt.millisecondsSince1970), .integer(r.syncRevision), .text(r.json)]
                )
                written += db.changes
            }
            return written
        }
    }

    public func deleteTenant(_ tenantID: UUID) throws {
        try db.execute("DELETE FROM inbox_record WHERE tenant_id = ?", [.text(tenantID.lowercased)])
    }

    /// Drops records older than `before` that no longer wait for the office (the server window is 30 days).
    @discardableResult
    public func prune(tenantID: UUID, before: Date) throws -> Int {
        let open = InboxRecord.openStatuses.map { "'\($0)'" }.joined(separator: ",")
        try db.execute(
            "DELETE FROM inbox_record WHERE tenant_id = ? AND occurred_at < ? AND (status IS NULL OR status NOT IN (\(open)))",
            [.text(tenantID.lowercased), .integer(before.millisecondsSince1970)]
        )
        return db.changes
    }

    /// Every record of the tenant, newest first.
    public func records(tenantID: UUID, kind: InboxRecord.Kind? = nil) throws -> [InboxRecord] {
        var sql = """
            SELECT kind, id, client_id, job_id, machine_id, status, occurred_at, sync_revision, json
            FROM inbox_record WHERE tenant_id = ?
            """
        var bindings: [SQLValue] = [.text(tenantID.lowercased)]
        if let kind {
            sql += " AND kind = ?"
            bindings.append(.text(kind.rawValue))
        }
        return try db.query(sql + " ORDER BY occurred_at DESC, id", bindings) { row in
            func uuid(_ c: Int32) -> UUID? { row.string(c).flatMap(UUID.init(uuidString:)) }
            guard let kind = row.string(0).flatMap(InboxRecord.Kind.init(rawValue:)), let id = uuid(1) else {
                throw DatabaseError.step(code: -1, message: "Corrupt inbox_record row")
            }
            return InboxRecord(kind: kind, id: id, clientID: uuid(2), jobID: uuid(3), machineID: uuid(4), status: row.string(5),
                               occurredAt: Date(millisecondsSince1970: row.int(6)), syncRevision: row.int(7),
                               json: row.string(8) ?? "{}")
        }
    }

    public func count(tenantID: UUID) throws -> Int {
        Int(try db.query("SELECT count(*) FROM inbox_record WHERE tenant_id = ?", [.text(tenantID.lowercased)]) {
            $0.int(0)
        }.first ?? 0)
    }
}
