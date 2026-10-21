import Foundation
import Security

/// Provides the 256-bit SQLCipher key for the local database.
///
/// The key is generated once with `SecRandomCopyBytes`, stored in the ``SecretStore``
/// (Keychain in production, device-only, after-first-unlock) and never leaves the device.
/// Losing the key (e.g. app reinstall on a new device) makes the old database unreadable
/// by design; the app must then re-bootstrap from the server.
public struct DatabaseKeyProvider: Sendable {
    public static let keyByteCount = 32
    public static let defaultAccount = "asseta.db.key.v1"

    private let store: any SecretStore
    private let account: String

    public init(store: any SecretStore, account: String = DatabaseKeyProvider.defaultAccount) {
        self.store = store
        self.account = account
    }

    /// Returns the existing key, or creates and persists a new random one.
    public func loadOrCreateKey() throws -> Data {
        if let existing = try store.data(for: account) {
            guard existing.count == Self.keyByteCount else {
                throw SecretStoreError.corruptValue(key: account)
            }
            return existing
        }
        let key = try Self.randomBytes(count: Self.keyByteCount)
        try store.set(key, for: account)
        return key
    }

    /// Removes the key, making any database encrypted with it permanently unreadable.
    public func destroyKey() throws {
        try store.remove(account)
    }

    public static func randomBytes(count: Int) throws -> Data {
        var bytes = [UInt8](repeating: 0, count: count)
        let status = SecRandomCopyBytes(kSecRandomDefault, count, &bytes)
        guard status == errSecSuccess else {
            throw SecretStoreError.randomGenerationFailed(status: status)
        }
        return Data(bytes)
    }
}
