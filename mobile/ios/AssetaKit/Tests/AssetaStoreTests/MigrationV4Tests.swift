@testable import AssetaStore
import Foundation
import Testing

/// Migration 4 (finance receipts + cash custody) upgrades a v3 database without losing data (and on to the latest).
struct MigrationV4Tests {
    let tenant = UUID()

    private func v3Database() throws -> EncryptedDatabase {
        let db = try EncryptedDatabase(url: try temporaryDatabaseURL(), key: Data((0..<32).map { UInt8($0) }))
        let v3 = Migrator(migrations: Array(AssetaSchema.migrations.prefix(3)))
        #expect(try v3.migrate(db) == 3)
        return db
    }

    @Test func upgradesV3InPlaceKeepingQueuedOperationsAndUploads() throws {
        let db = try v3Database()
        let v3Store = LocalStore(database: db)
        // Rows written with the v3 schema (raw SQL: today's repositories write later columns).
        let fileID = UUID()
        try db.execute(
            """
            INSERT INTO local_attachment (id, tenant_id, purpose, file_name, sha256, size_bytes, content_type, status, created_at)
            VALUES (?, ?, 'METER_PHOTO', 'a.jpg', ?, 10, 'image/jpeg', 'PENDING', 1)
            """, [.text(fileID.lowercased), .text(tenant.lowercased), .text(String(repeating: "a", count: 64))])
        let session = UUID()
        try v3Store.attachments.updateSession(id: fileID, sessionID: session, expiresAt: Date(timeIntervalSince1970: 1_800_000_000),
                                              chunkSize: 4, received: [0, 2])
        let opID = UUID()
        try db.execute(
            """
            INSERT INTO client_operation (id, tenant_id, op_type, entity_type, entity_id, payload_json, created_at_device,
                status, attempt_count)
            VALUES (?, ?, 'METER_CAPTURE', 'meter_capture', ?, '{"photo_attachment_id":null,"reading":"12.5"}', 1, 'PENDING', 0)
            """, [.text(opID.lowercased), .text(tenant.lowercased), .text(UUID().lowercased)])
        try db.execute("INSERT INTO operation_attachment (operation_id, attachment_local_id, payload_field) VALUES (?, ?, ?)",
                       [.text(opID.lowercased), .text(fileID.lowercased), .text("photo_attachment_id")])
        try v3Store.syncState.setValue("42", for: "cursor", tenant: tenant.lowercased)

        #expect(try Migrator.asseta.migrate(db) == AssetaSchema.migrations.count)

        let store = LocalStore(database: db)
        let migrated = try #require(try store.attachments.attachment(id: fileID))
        #expect(migrated.sessionID == session)
        #expect(migrated.receivedChunks == [0, 2])
        #expect(migrated.chunkSize == 4)
        #expect(try store.outbox.operation(id: opID)?.payloadJSON.contains("12.5") == true)
        #expect(try store.attachments.operationsAwaitingUpload(tenantID: tenant) == [opID])
        #expect(try store.syncState.value("cursor", tenant: tenant.lowercased) == "42")
        // The meter photo link still fills its payload field after the upgrade.
        let serverID = UUID()
        try store.attachments.markComplete(id: fileID, attachmentID: serverID)
        #expect(try store.outbox.operation(id: opID)?.payloadJSON.contains(serverID.lowercased) == true)
        #expect(try db.query("PRAGMA foreign_key_check") { $0.string(0) }.isEmpty)
        #expect(try db.query("SELECT name FROM schema_migration ORDER BY version") { $0.string(0) }
            .contains("finance_receipts_cash_custody"))
        let leftovers = try db.query("SELECT name FROM sqlite_master WHERE name LIKE '%_v3'") { $0.string(0) }
        #expect(leftovers.isEmpty)
    }

    @Test func receiptUploadIDsAreAppendedOnceAndCustodyIsReplaced() throws {
        let db = try v3Database()
        #expect(try Migrator.asseta.migrate(db) == AssetaSchema.migrations.count)
        let store = LocalStore(database: db)
        let receipt = try store.attachments.add(NewLocalAttachment(
            tenantID: tenant, purpose: "EXPENSE_RECEIPT", fileName: "r.jpg", sha256: String(repeating: "b", count: 64),
            sizeBytes: 10, contentType: "image/jpeg"))
        let op = try store.outbox.enqueue(NewClientOperation(
            tenantID: tenant, opType: "EXPENSE", entityType: "expense", entityID: UUID(),
            payloadJSON: #"{"amount":"10","receipt_upload_ids":[]}"#, attachments: [(receipt.id, .receiptUploads)]))
        #expect(try store.outbox.readyToSend(tenantID: tenant, limit: 10).isEmpty) // gated on the upload
        let upload = UUID()
        try store.attachments.markComplete(id: receipt.id, attachmentID: UUID(), uploadID: upload)
        try store.attachments.markComplete(id: receipt.id, attachmentID: UUID(), uploadID: upload) // idempotent
        let payload = try #require(try store.outbox.operation(id: op.id)?.payloadJSON)
        #expect(payload.contains(#""receipt_upload_ids":["\#(upload.lowercased)"]"#))
        #expect(try store.outbox.readyToSend(tenantID: tenant, limit: 10).map(\.id) == [op.id])

        let staff = UUID()
        let t1 = Date(timeIntervalSince1970: 1_800_000_000)
        try store.syncState.replaceCustody([StoredCustodyBalance(staffMemberID: staff, currency: "TZS", json: #"{"a":1}"#, asOf: t1)],
                                           asOf: t1, tenantID: tenant)
        // An older (late) list is ignored; a newer one replaces everything.
        #expect(try !store.syncState.replaceCustody([], asOf: t1.addingTimeInterval(-60), tenantID: tenant))
        #expect(try store.syncState.custody(tenantID: tenant).count == 1)
        let t2 = t1.addingTimeInterval(60)
        try store.syncState.replaceCustody([StoredCustodyBalance(staffMemberID: staff, currency: "USD", json: "{}", asOf: t2)],
                                           asOf: t2, tenantID: tenant)
        #expect(try store.syncState.custody(tenantID: tenant).map(\.currency) == ["USD"])
    }
}
