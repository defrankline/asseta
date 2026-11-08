import AssetaModel
@testable import AssetaStore
import Foundation
import Testing

/// Migration 9 (daily report evidence) upgrades a v8 database in place: queued work and its evidence links survive the
/// table rebuild, a daily report photo can then be stored, and completing it fills `evidence_upload_ids`.
struct MigrationV9Tests {
    let tenant = UUID()

    private func v8Store() throws -> (EncryptedDatabase, op: UUID, file: UUID) {
        let db = try EncryptedDatabase(url: try temporaryDatabaseURL(), key: Data((0..<32).map { UInt8($0) }))
        #expect(try Migrator(migrations: Array(AssetaSchema.migrations.prefix(8))).migrate(db) == 8)
        let file = UUID(), op = UUID()
        try db.execute(
            """
            INSERT INTO local_attachment (id, tenant_id, purpose, file_name, sha256, size_bytes, content_type, status,
                created_at, owner_subject)
            VALUES (?, ?, 'REMITTANCE_EVIDENCE', 'a.jpg', ?, 10, 'image/jpeg', 'PENDING', 1, 'u1')
            """, [.text(file.lowercased), .text(tenant.lowercased), .text(String(repeating: "a", count: 64))])
        try db.execute(
            """
            INSERT INTO client_operation (id, tenant_id, op_type, entity_type, entity_id, payload_json, created_at_device,
                status, attempt_count, owner_subject)
            VALUES (?, ?, 'CASH_HANDOVER', 'cash_handover', ?, '{}', 1, 'PENDING', 0, 'u1')
            """, [.text(op.lowercased), .text(tenant.lowercased), .text(UUID().lowercased)])
        try db.execute("INSERT INTO operation_attachment (operation_id, attachment_local_id, payload_field) VALUES (?, ?, ?)",
                       [.text(op.lowercased), .text(file.lowercased), .text("evidence_upload_ids")])
        #expect(try Migrator(migrations: Array(AssetaSchema.migrations.prefix(9))).migrate(db) == 9)
        return (db, op, file)
    }

    @Test func keepsQueuedWorkAndOwners() throws {
        let (db, op, file) = try v8Store()
        let store = LocalStore(database: db)
        #expect(try store.attachments.operationsAwaitingUpload(tenantID: tenant) == [op])
        let kept = try #require(try store.attachments.attachments(operationID: op).first)
        #expect(kept.id == file && kept.ownerSubject == "u1" && kept.purpose == "REMITTANCE_EVIDENCE")
        #expect(try db.query("SELECT name FROM schema_migration ORDER BY version") { $0.string(0) }.last == "daily_report_evidence")
    }

    @Test func dailyReportPhotoFillsItsPayload() throws {
        let (db, _, _) = try v8Store()
        let store = LocalStore(database: db)
        let photo = try store.attachments.add(NewLocalAttachment(
            tenantID: tenant, purpose: "DAILY_REPORT_EVIDENCE", fileName: "b.jpg", sha256: String(repeating: "b", count: 64),
            sizeBytes: 10, contentType: "image/jpeg", ownerSubject: "u1"))
        let report = try store.outbox.enqueue(NewClientOperation(
            tenantID: tenant, opType: "DAILY_REPORT", entityType: "daily_report", entityID: UUID(),
            payloadJSON: #"{"machine_id":"m","evidence_upload_ids":[]}"#, dependsOn: [],
            attachments: [(photo.id, .evidenceUploads)], createdAtDevice: Date(), owner: nil))
        let session = UUID()
        try store.attachments.markComplete(id: photo.id, attachmentID: UUID(), uploadID: session)
        let payload = try JSONValue.parse(try #require(try store.outbox.operation(id: report.id)).payloadJSON)
        #expect(payload["evidence_upload_ids"] == .array([.string(session.lowercased)]))
    }

    @Test func anUnknownPurposeIsStillRefused() throws {
        let (db, _, _) = try v8Store()
        let store = LocalStore(database: db)
        #expect(throws: (any Error).self) {
            try store.attachments.add(NewLocalAttachment(
                tenantID: tenant, purpose: "NOT_A_PURPOSE", fileName: "c.jpg", sha256: String(repeating: "c", count: 64),
                sizeBytes: 10, contentType: "image/jpeg"))
        }
    }
}
