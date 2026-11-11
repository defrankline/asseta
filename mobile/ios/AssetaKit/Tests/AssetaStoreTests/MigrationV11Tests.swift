import AssetaModel
@testable import AssetaStore
import Foundation
import Testing

/// Migration 11 (petty cash evidence, DEC-033) upgrades a v10 database in place: queued work survives and the new purpose is stored.
struct MigrationV11Tests {
    let tenant = UUID()

    @Test func keepsQueuedWorkAndAcceptsThePettyCashPurpose() throws {
        let db = try EncryptedDatabase(url: try temporaryDatabaseURL(), key: Data((0..<32).map { UInt8($0) }))
        #expect(try Migrator(migrations: Array(AssetaSchema.migrations.prefix(10))).migrate(db) == 10)
        let file = UUID()
        try db.execute(
            """
            INSERT INTO local_attachment (id, tenant_id, purpose, file_name, sha256, size_bytes, content_type, status, created_at, owner_subject)
            VALUES (?, ?, 'ADJUSTMENT_EVIDENCE', 'a.jpg', ?, 10, 'image/jpeg', 'PENDING', 1, 'u1')
            """, [.text(file.lowercased), .text(tenant.lowercased), .text(String(repeating: "a", count: 64))])
        #expect(try Migrator.asseta.migrate(db) == AssetaSchema.migrations.count)
        let store = LocalStore(database: db)
        #expect(try store.attachments.attachment(id: file)?.purpose == "ADJUSTMENT_EVIDENCE")
        let photo = try store.attachments.add(NewLocalAttachment(
            tenantID: tenant, purpose: "PETTY_CASH_EVIDENCE", fileName: "b.jpg", sha256: String(repeating: "b", count: 64),
            sizeBytes: 10, contentType: "image/jpeg", ownerSubject: "u1"))
        #expect(photo.purpose == "PETTY_CASH_EVIDENCE")
    }
}
