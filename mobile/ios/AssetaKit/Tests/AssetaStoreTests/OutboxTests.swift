@testable import AssetaStore
import AssetaSecurity
import Foundation
import Testing

struct OutboxTests {
    let store: LocalStore
    let tenant = UUID()

    init() throws {
        store = try LocalStore.open(at: try temporaryDatabaseURL(), keyProvider: DatabaseKeyProvider(store: InMemorySecretStore()))
    }

    private func newOp(dependsOn: UUID? = nil, tenant: UUID? = nil, at seconds: TimeInterval = 0) -> NewClientOperation {
        NewClientOperation(tenantID: tenant ?? self.tenant, opType: "CREATE", entityType: "job", entityID: UUID(),
                           payloadJSON: #"{"amount":"10.00"}"#, dependsOn: dependsOn.map { [$0] } ?? [],
                           createdAtDevice: Date(timeIntervalSince1970: 1_700_000_000 + seconds))
    }

    @Test func migrationsAreVersionedAndIdempotent() throws {
        #expect(try Migrator.asseta.currentVersion(store.database) == AssetaSchema.migrations.count)
        #expect(try Migrator.asseta.migrate(store.database) == AssetaSchema.migrations.count)
        let applied = try store.database.query("SELECT version, name FROM schema_migration") { $0.string(1) }
        #expect(applied == ["create_client_operation_outbox", "outbox_sync_protocol", "sync_state_entities_policies"])
    }

    @Test func refusesDatabaseNewerThanApp() throws {
        try store.database.execute("PRAGMA user_version = 99")
        #expect(throws: DatabaseError.self) { try Migrator.asseta.migrate(store.database) }
    }

    @Test func enqueuePersistsAllFields() throws {
        let input = newOp()
        let stored = try store.outbox.enqueue(input)
        #expect(stored.id == input.id)
        #expect(stored.status == .pending)
        #expect(stored.attemptCount == 0)
        #expect(stored.serverRevision == nil)
        #expect(stored.createdAtDevice == input.createdAtDevice)
        #expect(try store.outbox.operation(id: input.id) == stored)
    }

    @Test func duplicateIDIsRejected() throws {
        let input = newOp()
        try store.outbox.enqueue(input)
        #expect(throws: DatabaseError.self) { try store.outbox.enqueue(input) }
    }

    @Test func invalidPayloadIsRejected() {
        let bad = NewClientOperation(tenantID: tenant, opType: "X", entityType: "job", entityID: UUID(), payloadJSON: "{nope")
        #expect(throws: OutboxError.invalidPayload) { try store.outbox.enqueue(bad) }
    }

    @Test func dependenciesMustExistInSameTenant() throws {
        #expect(throws: OutboxError.self) { try store.outbox.enqueue(newOp(dependsOn: UUID())) }
        let other = try store.outbox.enqueue(newOp(tenant: UUID()))
        #expect(throws: OutboxError.crossTenantDependency(other.id)) {
            try store.outbox.enqueue(newOp(dependsOn: other.id))
        }
    }

    @Test func readyToSendRespectsOrderDependenciesAndTenant() throws {
        let parent = try store.outbox.enqueue(newOp(at: 1))
        let child = try store.outbox.enqueue(newOp(dependsOn: parent.id, at: 2))
        let older = try store.outbox.enqueue(newOp(at: 0))
        try store.outbox.enqueue(newOp(tenant: UUID(), at: -5))

        #expect(try store.outbox.readyToSend(tenantID: tenant, limit: 10).map(\.id) == [older.id, parent.id])
        #expect(try store.outbox.readyToSend(tenantID: tenant, limit: 1).map(\.id) == [older.id])

        try store.outbox.markSent(id: parent.id)
        // SENT is not synced: the child must still wait for the durable ACK.
        #expect(try !store.outbox.readyToSend(tenantID: tenant, limit: 10).map(\.id).contains(child.id))
        try store.outbox.markAcked(id: parent.id, serverRevision: 7)
        #expect(try store.outbox.readyToSend(tenantID: tenant, limit: 10).map(\.id) == [older.id, child.id])
    }

    @Test func lifecycleTransitionsAreEnforced() throws {
        let op = try store.outbox.enqueue(newOp())
        #expect(throws: OutboxError.invalidTransition(id: op.id, to: .acked)) {
            try store.outbox.markAcked(id: op.id, serverRevision: 1)
        }
        try store.outbox.markSent(id: op.id)
        try store.outbox.markFailed(id: op.id, error: "timeout")
        var current = try #require(try store.outbox.operation(id: op.id))
        #expect(current.status == .failed)
        #expect(current.lastError == "timeout")
        #expect(current.attemptCount == 1)

        try store.outbox.requeue(id: op.id)
        try store.outbox.markSent(id: op.id)
        try store.outbox.markAcked(id: op.id, serverRevision: 42)
        current = try #require(try store.outbox.operation(id: op.id))
        #expect(current.status == .acked)
        #expect(current.serverRevision == 42)
        #expect(current.attemptCount == 2)
        #expect(current.lastError == nil)

        #expect(throws: OutboxError.invalidTransition(id: op.id, to: .quarantined)) {
            try store.outbox.quarantine(id: op.id, reason: "x")
        }
        #expect(throws: OutboxError.notFound(UUID(uuidString: "00000000-0000-0000-0000-000000000000")!)) {
            try store.outbox.markSent(id: UUID(uuidString: "00000000-0000-0000-0000-000000000000")!)
        }
    }

    @Test func ackRequiresStoredServerResultAtSchemaLevel() throws {
        let op = try store.outbox.enqueue(newOp())
        #expect(throws: DatabaseError.self) {
            try store.database.execute("UPDATE client_operation SET status = 'ACKED' WHERE id = ?",
                                       [.text(op.id.uuidString.lowercased())])
        }
    }

    @Test func quarantineAndVisibilityCounts() throws {
        let a = try store.outbox.enqueue(newOp())
        try store.outbox.enqueue(newOp())
        try store.outbox.quarantine(id: a.id, reason: "conflict: approved record")
        let counts = try store.outbox.statusCounts(tenantID: tenant)
        #expect(counts[.pending] == 1)
        #expect(counts[.quarantined] == 1)
        #expect(counts[.acked] == 0)
        let quarantined = try store.outbox.operations(tenantID: tenant, statuses: [.quarantined])
        #expect(quarantined.map(\.lastError) == ["conflict: approved record"])
    }

    @Test func dataSurvivesReopenWithSameKey() throws {
        let url = try temporaryDatabaseURL()
        let keys = DatabaseKeyProvider(store: InMemorySecretStore())
        let op = try LocalStore.open(at: url, keyProvider: keys).outbox.enqueue(newOp())
        #expect(try LocalStore.open(at: url, keyProvider: keys).outbox.operation(id: op.id)?.id == op.id)
    }
}
