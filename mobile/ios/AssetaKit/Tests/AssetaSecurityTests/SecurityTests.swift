import AssetaSecurity
import Foundation
import Security
import Testing

struct DatabaseKeyProviderTests {
    @Test func createsRandom256BitKeyOnceAndReusesIt() throws {
        let store = InMemorySecretStore()
        let provider = DatabaseKeyProvider(store: store)
        let first = try provider.loadOrCreateKey()
        #expect(first.count == 32)
        #expect(try provider.loadOrCreateKey() == first)
        #expect(try DatabaseKeyProvider(store: InMemorySecretStore()).loadOrCreateKey() != first)
    }

    @Test func rejectsCorruptKey() throws {
        let store = InMemorySecretStore()
        try store.set(Data([1, 2, 3]), for: DatabaseKeyProvider.defaultAccount)
        #expect(throws: SecretStoreError.corruptValue(key: DatabaseKeyProvider.defaultAccount)) {
            try DatabaseKeyProvider(store: store).loadOrCreateKey()
        }
    }
}

struct TokenStoreTests {
    @Test func roundTripsAndClears() throws {
        let store = TokenStore(store: InMemorySecretStore())
        let tokens = StoredTokens(accessToken: "a", accessTokenExpiresAt: Date(timeIntervalSince1970: 10),
                                  refreshToken: "r", refreshTokenExpiresAt: nil, idToken: "i")
        try store.save(tokens)
        #expect(try store.load() == tokens)
        try store.clear()
        #expect(try store.load() == nil)
    }

    @Test func dropsUndecodableBlob() throws {
        let secrets = InMemorySecretStore()
        try secrets.set(Data("garbage".utf8), for: TokenStore.defaultAccount)
        #expect(try TokenStore(store: secrets).load() == nil)
        #expect(try secrets.data(for: TokenStore.defaultAccount) == nil)
    }
}

/// Exercises the real Keychain. The data-protection keychain needs an entitlement-bearing host:
/// it works in the iOS Simulator (xcodebuild test) but an unsigned `swift test` binary on macOS
/// gets errSecMissingEntitlement (-34018), in which case the test is skipped with a note.
struct KeychainSecretStoreTests {
    @Test func storesWithDeviceOnlyAfterFirstUnlockAccessibility() throws {
        let store = KeychainSecretStore(service: "com.asseta.tests.\(UUID().uuidString)")
        do {
            try store.set(Data("v1".utf8), for: "k")
        } catch SecretStoreError.keychain(status: errSecMissingEntitlement, _) {
            print("SKIPPED: data-protection keychain needs an entitled host (see AssetaSupervisorTests)")
            return
        }
        defer { try? store.remove("k") }
        #expect(try store.data(for: "k") == Data("v1".utf8))
        try store.set(Data("v2".utf8), for: "k")
        #expect(try store.data(for: "k") == Data("v2".utf8))
        #expect(try store.accessibility(for: "k") == (kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly as String))
        try store.remove("k")
        #expect(try store.data(for: "k") == nil)
    }
}
