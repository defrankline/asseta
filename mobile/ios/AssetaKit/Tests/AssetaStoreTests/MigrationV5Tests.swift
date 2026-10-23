import AssetaModel
@testable import AssetaStore
import Foundation
import Testing

/// Migration 5 (per-user field data) upgrades a v4 database in place; the data written before it
/// belongs to the user signed in at launch, or to an unknown previous account when nobody was.
struct MigrationV5Tests {
    let tenant = UUID()
    let job = UUID()
    let legacy = AccountIdentity(subject: "legacy-user-sub", label: "sam@example.com")

    /// A v4 store with a queued capture waiting for its photo, a handover, a cursor and a running entry.
    private func v4Store() throws -> (EncryptedDatabase, op: UUID, handover: UUID, file: UUID) {
        let db = try EncryptedDatabase(url: try temporaryDatabaseURL(), key: Data((0..<32).map { UInt8($0) }))
        #expect(try Migrator(migrations: Array(AssetaSchema.migrations.prefix(4))).migrate(db) == 4)
        let v4 = LocalStore(database: db)
        // Rows written with the v4 schema (raw SQL: today's repositories write the owner columns).
        let file = UUID(), op = UUID(), handover = UUID()
        try db.execute(
            """
            INSERT INTO local_attachment (id, tenant_id, purpose, file_name, sha256, size_bytes, content_type, status, created_at)
            VALUES (?, ?, 'METER_PHOTO', 'a.jpg', ?, 10, 'image/jpeg', 'PENDING', 1)
            """, [.text(file.lowercased), .text(tenant.lowercased), .text(String(repeating: "a", count: 64))])
        for (id, type, created) in [(op, "METER_CAPTURE", 1), (handover, "CASH_HANDOVER", 2)] {
            try db.execute(
                """
                INSERT INTO client_operation (id, tenant_id, op_type, entity_type, entity_id, payload_json, created_at_device,
                    status, attempt_count)
                VALUES (?, ?, ?, 'x', ?, '{}', ?, 'PENDING', 0)
                """, [.text(id.lowercased), .text(tenant.lowercased), .text(type), .text(UUID().lowercased),
                      .integer(Int64(created))])
        }
        try db.execute("INSERT INTO operation_attachment (operation_id, attachment_local_id, payload_field) VALUES (?, ?, ?)",
                       [.text(op.lowercased), .text(file.lowercased), .text("photo_attachment_id")])
        try v4.syncState.setValue("53", for: "cursor", tenant: tenant.lowercased)
        try v4.syncState.setValue(#"{"x":1}"#, for: "work_log_running.\(job.lowercased)", tenant: tenant.lowercased)
        #expect(try Migrator(migrations: Array(AssetaSchema.migrations.prefix(5))).migrate(db) == 5)
        return (db, op, handover, file)
    }

    @Test func existingFieldDataBelongsToTheUserSignedInAtLaunch() throws {
        let (db, op, handover, file) = try v4Store()
        let store = LocalStore(database: db)
        try store.adoptLegacyData(owner: legacy)
        try store.adoptLegacyData(owner: AccountIdentity(subject: "someone-else")) // idempotent: already owned
        let migrated = try #require(try store.outbox.operation(id: op))
        #expect(migrated.ownerSubject == legacy.subject)
        #expect(migrated.ownerLabel == legacy.label)
        #expect(try store.attachments.attachment(id: file)?.ownerSubject == legacy.subject)
        #expect(try store.syncState.value(SyncStateStore.ownerKey, tenant: tenant.lowercased) == legacy.subject)
        #expect(try store.syncState.value("work_log_running.\(legacy.subject).\(job.lowercased)", tenant: tenant.lowercased)
            == #"{"x":1}"#)
        // The same user keeps working: nothing is reset and the queued work is still sent.
        #expect(try !store.syncState.claim(tenantID: tenant, owner: legacy.subject))
        #expect(try store.syncState.value("cursor", tenant: tenant.lowercased) == "53")
        #expect(try store.outbox.readyToSend(tenantID: tenant, owner: legacy.subject, now: Date(), limit: 10).map(\.id) == [handover])
        #expect(try store.attachments.pendingUploads(tenantID: tenant, owner: legacy.subject, now: Date()).map(\.id) == [file])
        #expect(try store.outbox.readyToSend(tenantID: tenant, owner: "next-user", now: Date(), limit: 10).isEmpty)
        #expect(try db.query("SELECT name FROM schema_migration ORDER BY version") { $0.string(0) }.last == "per_user_field_data")
    }

    @Test func withNobodySignedInTheWorkIsHeldForAnUnknownPreviousAccount() throws {
        let (db, _, _, file) = try v4Store()
        let store = LocalStore(database: db)
        try store.adoptLegacyData(owner: nil)
        #expect(try store.attachments.attachment(id: file)?.ownerSubject == AccountIdentity.unknownSubject)
        try Migrator.asseta.migrate(db) // today's claim also clears the v6 inbox
        // Whoever signs in next gets a fresh start and never sees, uploads or sends the held work.
        #expect(try store.syncState.claim(tenantID: tenant, owner: "next-user"))
        #expect(try store.syncState.value("cursor", tenant: tenant.lowercased) == nil)
        #expect(try store.outbox.readyToSend(tenantID: tenant, owner: "next-user", now: Date(), limit: 10).isEmpty)
        #expect(try store.attachments.pendingUploads(tenantID: tenant, owner: "next-user", now: Date()).isEmpty)
        #expect(try store.outbox.statusCounts(tenantID: tenant, owner: "next-user").values.reduce(0, +) == 0)
        #expect(try store.outbox.heldAccounts(tenantID: tenant, excluding: "next-user")
            == [HeldAccount(subject: AccountIdentity.unknownSubject, label: nil, count: 2)])
        // The held running entry survives the reset under its owner's key.
        #expect(try store.syncState.value("work_log_running.\(AccountIdentity.unknownSubject).\(job.lowercased)",
                                          tenant: tenant.lowercased) != nil)
    }
}
