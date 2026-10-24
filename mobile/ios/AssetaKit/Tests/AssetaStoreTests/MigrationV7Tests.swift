import AssetaModel
@testable import AssetaStore
import Foundation
import Testing

/// Migration 7 (accountability evidence) upgrades a v6 database in place: queued work, its evidence links and the
/// owner of each file survive the table rebuilds; payment evidence and correction photos can then be linked, and
/// completing their uploads fills `evidence_upload_ids` / `replacement.photo_attachment_id` of the waiting payload.
struct MigrationV7Tests {
    let tenant = UUID()

    private func v6Store() throws -> (EncryptedDatabase, op: UUID, file: UUID) {
        let db = try EncryptedDatabase(url: try temporaryDatabaseURL(), key: Data((0..<32).map { UInt8($0) }))
        #expect(try Migrator(migrations: Array(AssetaSchema.migrations.prefix(6))).migrate(db) == 6)
        let file = UUID(), op = UUID()
        try db.execute(
            """
            INSERT INTO local_attachment (id, tenant_id, purpose, file_name, sha256, size_bytes, content_type, status,
                created_at, owner_subject)
            VALUES (?, ?, 'METER_PHOTO', 'a.jpg', ?, 10, 'image/jpeg', 'PENDING', 1, 'u1')
            """, [.text(file.lowercased), .text(tenant.lowercased), .text(String(repeating: "a", count: 64))])
        try db.execute(
            """
            INSERT INTO client_operation (id, tenant_id, op_type, entity_type, entity_id, payload_json, created_at_device,
                status, attempt_count, owner_subject)
            VALUES (?, ?, 'METER_CAPTURE', 'meter_capture', ?, '{}', 1, 'PENDING', 0, 'u1')
            """, [.text(op.lowercased), .text(tenant.lowercased), .text(UUID().lowercased)])
        try db.execute("INSERT INTO operation_attachment (operation_id, attachment_local_id, payload_field) VALUES (?, ?, ?)",
                       [.text(op.lowercased), .text(file.lowercased), .text("photo_attachment_id")])
        #expect(try Migrator.asseta.migrate(db) == 7)
        return (db, op, file)
    }

    @Test func keepsQueuedWorkAndOwners() throws {
        let (db, op, file) = try v6Store()
        let store = LocalStore(database: db)
        #expect(try store.attachments.operationsAwaitingUpload(tenantID: tenant) == [op])
        let kept = try #require(try store.attachments.attachments(operationID: op).first)
        #expect(kept.id == file && kept.ownerSubject == "u1")
        #expect(try db.query("SELECT name FROM schema_migration ORDER BY version") { $0.string(0) }.last == "accountability_evidence")
    }

    @Test func paymentEvidenceAndCorrectionPhotoFillTheirPayloads() throws {
        let (db, _, _) = try v6Store()
        let store = LocalStore(database: db)
        func file(_ purpose: String, _ c: Character) throws -> LocalAttachment {
            try store.attachments.add(NewLocalAttachment(
                tenantID: tenant, purpose: purpose, fileName: "\(c).jpg", sha256: String(repeating: c, count: 64),
                sizeBytes: 10, contentType: "image/jpeg", ownerSubject: "u1"))
        }
        let receipt = try file("PAYMENT_EVIDENCE", "b"), photo = try file("METER_PHOTO", "c")
        let purchase = try store.outbox.enqueue(NewClientOperation(
            tenantID: tenant, opType: "HOURS_PURCHASE", entityType: "hours_purchase", entityID: UUID(),
            payloadJSON: #"{"machine_id":"m","hours":"5","evidence_upload_ids":[]}"#, dependsOn: [],
            attachments: [(receipt.id, .evidenceUploads)], createdAtDevice: Date(), owner: nil))
        let correction = try store.outbox.enqueue(NewClientOperation(
            tenantID: tenant, opType: "METER_CORRECTION", entityType: "meter_correction", entityID: UUID(),
            payloadJSON: #"{"reason":"Wrong digit read","replacement":{"reading":"10"}}"#, dependsOn: [],
            attachments: [(photo.id, .replacementPhoto)], createdAtDevice: Date(), owner: nil))
        let session = UUID(), attachment = UUID()
        try store.attachments.markComplete(id: receipt.id, attachmentID: UUID(), uploadID: session)
        try store.attachments.markComplete(id: photo.id, attachmentID: attachment)
        let p1 = try JSONValue.parse(try #require(try store.outbox.operation(id: purchase.id)).payloadJSON)
        #expect(p1["evidence_upload_ids"] == .array([.string(session.lowercased)]))
        let p2 = try JSONValue.parse(try #require(try store.outbox.operation(id: correction.id)).payloadJSON)
        #expect(p2["replacement"]?["photo_attachment_id"]?.stringValue == attachment.lowercased)
        #expect(p2["photo_attachment_id"] == nil)
    }
}
