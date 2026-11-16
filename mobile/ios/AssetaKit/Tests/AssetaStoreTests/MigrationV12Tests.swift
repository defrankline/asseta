import AssetaModel
@testable import AssetaStore
import Foundation
import Testing

/// Migration 12 (ADR-008, jobs removed) upgrades a v11 database in place: the job leftovers go (cached jobs,
/// contracts, changeover jobs and hire invoices, work-log / acknowledgement inbox records, running work-log entries and
/// `inbox_record.job_id`), while queued work, evidence links and every other cached record survive.
struct MigrationV12Tests {
    let tenant = UUID()

    @Test func dropsJobLeftoversAndKeepsEverythingElse() throws {
        let db = try EncryptedDatabase(url: try temporaryDatabaseURL(), key: Data((0..<32).map { UInt8($0) }))
        #expect(try Migrator(migrations: Array(AssetaSchema.migrations.prefix(11))).migrate(db) == 11)
        let t = tenant.lowercased
        let op = UUID(), file = UUID(), machine = UUID(), job = UUID(), expense = UUID(), activity = UUID()
        try db.execute(
            """
            INSERT INTO local_attachment (id, tenant_id, purpose, file_name, sha256, size_bytes, content_type, status, created_at, owner_subject)
            VALUES (?, ?, 'METER_PHOTO', 'a.jpg', ?, 10, 'image/jpeg', 'PENDING', 1, 'u1')
            """, [.text(file.lowercased), .text(t), .text(String(repeating: "a", count: 64))])
        try db.execute(
            """
            INSERT INTO client_operation (id, tenant_id, op_type, entity_type, entity_id, payload_json, created_at_device,
                status, attempt_count, owner_subject)
            VALUES (?, ?, 'METER_CAPTURE', 'meter_capture', ?, '{}', 1, 'PENDING', 0, 'u1')
            """, [.text(op.lowercased), .text(t), .text(UUID().lowercased)])
        try db.execute("INSERT INTO operation_attachment (operation_id, attachment_local_id, payload_field) VALUES (?, ?, ?)",
                       [.text(op.lowercased), .text(file.lowercased), .text("photo_attachment_id")])
        for (type, id) in [("job", job), ("contract", UUID()), ("changeover_job", UUID()), ("open_invoice", UUID()),
                           ("machine", machine)] {
            try db.execute("INSERT INTO sync_entity (tenant_id, entity_type, id, revision, version, json) VALUES (?, ?, ?, 1, NULL, '{}')",
                           [.text(t), .text(type), .text(id.lowercased)])
        }
        for (kind, id, jobID) in [("JOB_ACTIVITY", activity, job), ("ACKNOWLEDGEMENT", UUID(), job), ("EXPENSE", expense, job)] {
            try db.execute(
                """
                INSERT INTO inbox_record (kind, id, tenant_id, client_id, job_id, machine_id, status, occurred_at, sync_revision, json)
                VALUES (?, ?, ?, NULL, ?, NULL, 'PENDING_APPROVAL', 1, 1, '{}')
                """, [.text(kind), .text(id.lowercased), .text(t), .text(jobID.lowercased)])
        }
        let store = LocalStore(database: db)
        try store.syncState.setValue("{}", for: "work_log_running.u1.\(job.lowercased)", tenant: t)
        try store.syncState.setValue("53", for: "cursor", tenant: t)

        #expect(try Migrator.asseta.migrate(db) == AssetaSchema.migrations.count)
        #expect(AssetaSchema.migrations.last?.name == "adr008_job_removal")

        // Job leftovers are gone.
        for type in ["job", "contract", "changeover_job", "open_invoice"] {
            #expect(try store.syncState.entities(type: type, tenantID: tenant).isEmpty, "\(type) still cached")
        }
        #expect(try store.syncState.value("work_log_running.u1.\(job.lowercased)", tenant: t) == nil)
        let columns = try db.query("SELECT name FROM pragma_table_info('inbox_record')") { $0.string(0) ?? "" }
        #expect(!columns.contains("job_id"))
        let indexes = try db.query("SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'inbox_record'") {
            $0.string(0) ?? ""
        }
        #expect(!indexes.contains("ix_inbox_record_job"))

        // Everything else survives: the inbox expense, the cached machine, the cursor, queued work and its evidence link.
        #expect(try store.inbox.records(tenantID: tenant).map(\.id) == [expense])
        #expect(try store.syncState.entity(type: "machine", id: machine, tenantID: tenant) != nil)
        #expect(try store.syncState.value("cursor", tenant: t) == "53")
        #expect(try store.attachments.operationsAwaitingUpload(tenantID: tenant) == [op])
        #expect(try store.attachments.attachments(operationID: op).map(\.id) == [file])

        // The rebuilt inbox table still takes new records.
        let written = try store.inbox.upsert([InboxRecord(kind: .meterCapture, id: UUID(), clientID: nil, machineID: machine,
                                                          status: "ACCEPTED", occurredAt: Date(), syncRevision: 2, json: "{}")],
                                             tenantID: tenant)
        #expect(written == 1)
    }
}
