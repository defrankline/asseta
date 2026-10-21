import AssetaCapture
import AssetaSecurity
import AssetaStore
import AssetaSync
import Foundation
import Security
import Testing

/// Gate 4 device-level checks inside the signed app host (real data-protection Keychain).
struct FieldDeviceIntegrationTests {
    let secrets = KeychainSecretStore(service: "com.asseta.tests.field.\(UUID().uuidString)")

    @Test func deviceIdentityIsGeneratedOnceAndKeptInTheKeychain() throws {
        defer { try? secrets.remove(DeviceIdentity.account) }
        let first = try DeviceIdentity.loadOrCreate(store: secrets)
        #expect(UUID(uuidString: first) != nil)
        #expect(try DeviceIdentity.loadOrCreate(store: secrets) == first)
        #expect(try secrets.accessibility(for: DeviceIdentity.account)
                == (kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly as String))
    }

    @Test func revocationWipeErasesDatabaseKeyTokensAndEvidence() throws {
        let keys = DatabaseKeyProvider(store: secrets)
        let tokens = TokenStore(store: secrets)
        defer {
            try? keys.destroyKey(); try? tokens.clear(); try? secrets.remove(DeviceIdentity.account)
        }
        let root = FileManager.default.temporaryDirectory.appendingPathComponent("wipe-\(UUID().uuidString)")
        let url = root.appendingPathComponent("db/asseta.sqlite")
        let store = try LocalStore.open(at: url, keyProvider: keys)
        let tenant = UUID()
        try store.outbox.enqueue(NewClientOperation(tenantID: tenant, opType: "METER_CAPTURE", entityType: "meter_capture",
                                                    entityID: UUID(), payloadJSON: #"{"reading":"1.0"}"#))
        try tokens.save(StoredTokens(accessToken: "a", accessTokenExpiresAt: .distantFuture, refreshToken: "r",
                                     refreshTokenExpiresAt: nil, idToken: nil))
        let deviceID = try DeviceIdentity.loadOrCreate(store: secrets)
        let evidence = EvidenceStore(directory: root.appendingPathComponent("evidence"))
        let photo = try evidence.store(Data(repeating: 7, count: 1024), fileExtension: "jpg", contentType: "image/jpeg")
        #if !targetEnvironment(simulator)
        let protection = try FileManager.default.attributesOfItem(atPath: evidence.url(for: photo.fileName).path)[.protectionKey]
        #expect(protection as? FileProtectionType == .complete)
        #endif
        let keyBefore = try #require(try secrets.data(for: DatabaseKeyProvider.defaultAccount))

        let errors = DeviceWipe.wipe(database: store.database, databaseURL: url, keyProvider: keys, tokens: tokens, evidence: evidence)
        #expect(errors.isEmpty)
        #expect(!FileManager.default.fileExists(atPath: url.path))
        #expect(!FileManager.default.fileExists(atPath: url.path + "-wal"))
        #expect(try secrets.data(for: DatabaseKeyProvider.defaultAccount) == nil)
        #expect(try tokens.load() == nil)
        #expect(!FileManager.default.fileExists(atPath: evidence.directory.path))
        #expect(try DeviceIdentity.loadOrCreate(store: secrets) == deviceID) // stays the same (revoked) device

        let fresh = try LocalStore.open(at: url, keyProvider: keys)
        #expect(try fresh.outbox.statusCounts(tenantID: tenant).values.reduce(0, +) == 0)
        #expect(try secrets.data(for: DatabaseKeyProvider.defaultAccount) != keyBefore)
    }
}
