import AssetaSecurity
import AssetaStore
import Foundation
import Security
import Testing

/// Runs inside the signed AssetaSupervisor host so the real data-protection Keychain is available
/// (unsigned `swift test` hosts cannot use it). No skipping here: failures are real failures.
struct KeychainIntegrationTests {
    let store = KeychainSecretStore(service: "com.asseta.tests.\(UUID().uuidString)")

    @Test func secretsUseAfterFirstUnlockThisDeviceOnly() throws {
        defer { try? store.remove("k") }
        try store.set(Data("v1".utf8), for: "k")
        try store.set(Data("v2".utf8), for: "k")
        #expect(try store.data(for: "k") == Data("v2".utf8))
        #expect(try store.accessibility(for: "k") == (kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly as String))
        try store.remove("k")
        #expect(try store.data(for: "k") == nil)
    }

    @Test func encryptedStoreOpensWithKeychainKeyAndIsFileProtected() throws {
        let keys = DatabaseKeyProvider(store: store)
        defer { try? keys.destroyKey() }
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("\(UUID().uuidString).sqlite")
        let local = try LocalStore.open(at: url, keyProvider: keys)
        let op = try local.outbox.enqueue(NewClientOperation(
            tenantID: UUID(), opType: "CREATE", entityType: "job", entityID: UUID(), payloadJSON: "{}"))
        #expect(try LocalStore.open(at: url, keyProvider: keys).outbox.operation(id: op.id) != nil)
        #if !targetEnvironment(simulator)
        // The Simulator does not implement Data Protection classes, so this is device-only.
        let protection = try FileManager.default.attributesOfItem(atPath: url.path)[.protectionKey] as? FileProtectionType
        #expect(protection == .completeUntilFirstUserAuthentication)
        #endif
        // A destroyed key means the file can no longer be opened.
        try keys.destroyKey()
        #expect(throws: (any Error).self) { try EncryptedDatabase(url: url, key: try keys.loadOrCreateKey()) }
    }
}
