import AssetaModel
@testable import AssetaStore
import Foundation
import Testing

/// Migration 6 (supervisor inbox) upgrades a v5 database in place: queued work and its evidence links
/// survive the `operation_attachment` rebuild, and the new `inbox_record` table works (revision-guarded
/// upsert, pruning, cleared when another user claims the tenant).
struct MigrationV6Tests {
    let tenant = UUID()

    private func v5Store() throws -> (EncryptedDatabase, op: UUID, file: UUID) {
        let db = try EncryptedDatabase(url: try temporaryDatabaseURL(), key: Data((0..<32).map { UInt8($0) }))
        #expect(try Migrator(migrations: Array(AssetaSchema.migrations.prefix(5))).migrate(db) == 5)
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
        try LocalStore(database: db).syncState.setValue("53", for: "cursor", tenant: tenant.lowercased)
        #expect(try Migrator(migrations: Array(AssetaSchema.migrations.prefix(6))).migrate(db) == 6)
        return (db, op, file)
    }

    private func record(_ id: UUID, status: String, revision: Int64, at: Date) -> InboxRecord {
        InboxRecord(kind: .expense, id: id, clientID: nil, jobID: nil, machineID: nil, status: status, occurredAt: at,
                    syncRevision: revision, json: #"{"rev":\#(revision)}"#)
    }

    @Test func keepsQueuedWorkAndEvidenceLinks() throws {
        let (db, op, file) = try v5Store()
        let store = LocalStore(database: db)
        #expect(try store.syncState.value("cursor", tenant: tenant.lowercased) == "53")
        #expect(try store.attachments.operationsAwaitingUpload(tenantID: tenant) == [op])
        #expect(try store.attachments.attachments(operationID: op).map(\.id) == [file])
        // The rebuilt link table accepts the reset evidence field.
        let evidence = try store.attachments.add(NewLocalAttachment(
            tenantID: tenant, purpose: "RESET_EVIDENCE", fileName: "r.jpg", sha256: String(repeating: "b", count: 64),
            sizeBytes: 10, contentType: "image/jpeg", ownerSubject: "u1"))
        try db.execute("INSERT INTO operation_attachment (operation_id, attachment_local_id, payload_field) VALUES (?, ?, ?)",
                       [.text(op.lowercased), .text(evidence.id.lowercased), .text("evidence_upload_id")])
        #expect(try store.attachments.attachments(operationID: op).count == 2)
        #expect(try db.query("SELECT name FROM schema_migration ORDER BY version") { $0.string(0) }.last == "supervisor_inbox")
        #expect(try store.inbox.count(tenantID: tenant) == 0)
    }

    @Test func inboxUpsertsByRevisionPrunesAndIsClearedForAnotherUser() throws {
        let (db, _, _) = try v5Store()
        let store = LocalStore(database: db)
        try store.syncState.claim(tenantID: tenant, owner: "u1")
        let id = UUID(), open = UUID()
        #expect(try store.inbox.upsert([record(id, status: "PENDING_APPROVAL", revision: 5, at: Date(timeIntervalSince1970: 10))],
                                       tenantID: tenant) == 1)
        // An older (replayed) revision never overwrites a newer one; a newer one does.
        #expect(try store.inbox.upsert([record(id, status: "APPROVED", revision: 4, at: Date(timeIntervalSince1970: 10))],
                                       tenantID: tenant) == 0)
        #expect(try store.inbox.records(tenantID: tenant).first?.status == "PENDING_APPROVAL")
        try store.inbox.upsert([record(id, status: "REJECTED", revision: 6, at: Date(timeIntervalSince1970: 10)),
                                record(open, status: "PENDING_APPROVAL", revision: 7, at: Date(timeIntervalSince1970: 10))],
                               tenantID: tenant)
        #expect(try store.inbox.records(tenantID: tenant, kind: .expense).first { $0.id == id }?.status == "REJECTED")
        // Pruning keeps records still waiting for the office.
        #expect(try store.inbox.prune(tenantID: tenant, before: Date(timeIntervalSince1970: 100)) == 1)
        #expect(try store.inbox.records(tenantID: tenant).map(\.id) == [open])
        // Another user signing in clears the inbox with the rest of the tenant's server data.
        #expect(try !store.syncState.claim(tenantID: tenant, owner: "u1"))
        #expect(try store.inbox.count(tenantID: tenant) == 1)
        #expect(try store.syncState.claim(tenantID: tenant, owner: "u2"))
        #expect(try store.inbox.count(tenantID: tenant) == 0)
    }
}
