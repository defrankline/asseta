import Foundation

public enum LocalAttachmentStatus: String, Sendable, CaseIterable {
    case pending = "PENDING", complete = "COMPLETE", failed = "FAILED"
}

/// A captured evidence file (meter photo, signature) waiting for, or done with, resumable upload.
/// The file itself lives in the protected evidence directory; this row tracks the upload.
public struct LocalAttachment: Equatable, Sendable, Identifiable {
    public let id: UUID
    public let tenantID: UUID
    public let purpose: String
    public let fileName: String
    public let sha256: String
    public let sizeBytes: Int64
    public let contentType: String
    public let status: LocalAttachmentStatus
    public let sessionID: UUID?
    public let sessionExpiresAt: Date?
    public let chunkSize: Int?
    /// Chunk indexes the server last reported as received for `sessionID`.
    public let receivedChunks: Set<Int>
    public let attachmentID: UUID?
    public let attemptCount: Int
    public let lastError: String?
    public let nextAttemptAt: Date?
    public let createdAt: Date
}

public struct NewLocalAttachment: Sendable {
    public let id: UUID
    public let tenantID: UUID
    public let purpose: String
    public let fileName: String
    public let sha256: String
    public let sizeBytes: Int64
    public let contentType: String
    public let createdAt: Date

    public init(id: UUID = UUID(), tenantID: UUID, purpose: String, fileName: String, sha256: String,
                sizeBytes: Int64, contentType: String, createdAt: Date = Date()) {
        self.id = id
        self.tenantID = tenantID
        self.purpose = purpose
        self.fileName = fileName
        self.sha256 = sha256
        self.sizeBytes = sizeBytes
        self.contentType = contentType
        self.createdAt = createdAt
    }
}

public final class AttachmentRepository: Sendable {
    private let db: EncryptedDatabase

    private static let columns = """
        id, tenant_id, purpose, file_name, sha256, size_bytes, content_type, status, session_id, attachment_id,
        attempt_count, last_error, next_attempt_at, created_at, session_expires_at, chunk_size, received_chunks
        """

    public init(database: EncryptedDatabase) {
        self.db = database
    }

    @discardableResult
    public func add(_ new: NewLocalAttachment) throws -> LocalAttachment {
        try db.execute(
            """
            INSERT INTO local_attachment (id, tenant_id, purpose, file_name, sha256, size_bytes, content_type,
                status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'PENDING', ?)
            """,
            [.text(new.id.lowercased), .text(new.tenantID.lowercased), .text(new.purpose), .text(new.fileName),
             .text(new.sha256), .integer(new.sizeBytes), .text(new.contentType),
             .integer(new.createdAt.millisecondsSince1970)]
        )
        guard let stored = try attachment(id: new.id) else { throw OutboxError.attachmentMissing(new.id) }
        return stored
    }

    public func attachment(id: UUID) throws -> LocalAttachment? {
        try db.query("SELECT \(Self.columns) FROM local_attachment WHERE id = ?", [.text(id.lowercased)],
                     map: Self.decode).first
    }

    /// PENDING uploads whose retry time has come, oldest first.
    public func pendingUploads(tenantID: UUID, now: Date, limit: Int = 20) throws -> [LocalAttachment] {
        try db.query(
            """
            SELECT \(Self.columns) FROM local_attachment
            WHERE tenant_id = ? AND status = 'PENDING' AND (next_attempt_at IS NULL OR next_attempt_at <= ?)
            ORDER BY created_at, id LIMIT ?
            """,
            [.text(tenantID.lowercased), .integer(now.millisecondsSince1970), .integer(Int64(limit))],
            map: Self.decode
        )
    }

    public func attachments(tenantID: UUID, statuses: Set<LocalAttachmentStatus>) throws -> [LocalAttachment] {
        let ordered = statuses.map(\.rawValue).sorted()
        guard !ordered.isEmpty else { return [] }
        let placeholders = Array(repeating: "?", count: ordered.count).joined(separator: ", ")
        return try db.query(
            """
            SELECT \(Self.columns) FROM local_attachment WHERE tenant_id = ? AND status IN (\(placeholders))
            ORDER BY created_at, id
            """,
            [.text(tenantID.lowercased)] + ordered.map(SQLValue.text),
            map: Self.decode
        )
    }

    /// Records the server upload session and what it has received (persisted after every chunk,
    /// so an upload resumes where it stopped even after the app was terminated).
    public func updateSession(id: UUID, sessionID: UUID?, expiresAt: Date?, chunkSize: Int?, received: Set<Int>) throws {
        try db.execute(
            """
            UPDATE local_attachment SET session_id = ?, session_expires_at = ?, chunk_size = ?, received_chunks = ?
            WHERE id = ?
            """,
            [.optionalText(sessionID?.lowercased), .optionalInteger(expiresAt?.millisecondsSince1970),
             .optionalInteger(chunkSize.map(Int64.init)), .text(received.sorted().map(String.init).joined(separator: ",")),
             .text(id.lowercased)]
        )
    }

    /// Records a failed attempt; the upload stays PENDING and is retried at `retryAt`.
    public func recordAttemptFailure(id: UUID, error: String, retryAt: Date?) throws {
        try db.execute(
            """
            UPDATE local_attachment SET attempt_count = attempt_count + 1, last_error = ?, next_attempt_at = ?
            WHERE id = ? AND status = 'PENDING'
            """,
            [.text(error), .optionalInteger(retryAt?.millisecondsSince1970), .text(id.lowercased)]
        )
    }

    /// Operations still waiting for one of their files to finish uploading.
    public func operationsAwaitingUpload(tenantID: UUID) throws -> Set<UUID> {
        Set(try db.query(
            """
            SELECT oa.operation_id FROM operation_attachment oa
            JOIN local_attachment a ON a.id = oa.attachment_local_id
            WHERE a.tenant_id = ? AND a.status <> 'COMPLETE'
            """,
            [.text(tenantID.lowercased)]
        ) { $0.string(0).flatMap(UUID.init(uuidString:)) }.compactMap { $0 })
    }

    /// Permanent failure (e.g. the local evidence file no longer matches its recorded hash).
    public func markFailed(id: UUID, error: String) throws {
        try db.execute("UPDATE local_attachment SET status = 'FAILED', last_error = ? WHERE id = ?",
                       [.text(error), .text(id.lowercased)])
    }

    /// Marks the upload complete and, in the same transaction, writes the server attachment id into
    /// every operation payload waiting for it — so the stored payload is exactly what is pushed.
    public func markComplete(id: UUID, attachmentID: UUID) throws {
        try db.transaction {
            try db.execute(
                """
                UPDATE local_attachment SET status = 'COMPLETE', attachment_id = ?, last_error = NULL,
                    next_attempt_at = NULL
                WHERE id = ?
                """,
                [.text(attachmentID.lowercased), .text(id.lowercased)]
            )
            let links = try db.query(
                "SELECT operation_id, payload_field FROM operation_attachment WHERE attachment_local_id = ?",
                [.text(id.lowercased)]
            ) { ($0.string(0) ?? "", $0.string(1) ?? "") }
            for (operationID, field) in links {
                guard AttachmentPayloadField(rawValue: field) != nil else { continue }
                // Only unsent operations are rewritten; an op already sent keeps its exact payload.
                try db.execute(
                    """
                    UPDATE client_operation SET payload_json = json_set(payload_json, '$.\(field)', ?)
                    WHERE id = ? AND status = 'PENDING'
                    """,
                    [.text(attachmentID.lowercased), .text(operationID)]
                )
            }
        }
    }

    private static func decode(_ row: Row) throws -> LocalAttachment {
        func uuid(_ column: Int32) -> UUID? { row.string(column).flatMap(UUID.init(uuidString:)) }
        guard let id = uuid(0), let tenant = uuid(1),
              let status = row.string(7).flatMap(LocalAttachmentStatus.init(rawValue:))
        else { throw DatabaseError.step(code: -1, message: "Corrupt local_attachment row") }
        return LocalAttachment(
            id: id, tenantID: tenant, purpose: row.string(2) ?? "", fileName: row.string(3) ?? "",
            sha256: row.string(4) ?? "", sizeBytes: row.int(5), contentType: row.string(6) ?? "",
            status: status, sessionID: uuid(8),
            sessionExpiresAt: row.isNull(14) ? nil : Date(millisecondsSince1970: row.int(14)),
            chunkSize: row.isNull(15) ? nil : Int(row.int(15)),
            receivedChunks: Set((row.string(16) ?? "").split(separator: ",").compactMap { Int($0) }),
            attachmentID: uuid(9), attemptCount: Int(row.int(10)),
            lastError: row.string(11),
            nextAttemptAt: row.isNull(12) ? nil : Date(millisecondsSince1970: row.int(12)),
            createdAt: Date(millisecondsSince1970: row.int(13))
        )
    }
}
