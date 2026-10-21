import Foundation
import Security

/// Generic-password Keychain wrapper.
///
/// Every item is written with `kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly`: readable by
/// background sync after the first unlock following boot, never included in backups or
/// migrated to another device. On macOS the data-protection keychain is used so the same
/// accessibility semantics apply (requires a signed host; see README for test notes).
public struct KeychainSecretStore: SecretStore {
    public let service: String
    public let accessGroup: String?

    public init(service: String, accessGroup: String? = nil) {
        self.service = service
        self.accessGroup = accessGroup
    }

    private func baseQuery(_ key: String) -> [String: Any] {
        var query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
            kSecUseDataProtectionKeychain as String: true,
        ]
        if let accessGroup {
            query[kSecAttrAccessGroup as String] = accessGroup
        }
        return query
    }

    public func data(for key: String) throws -> Data? {
        var query = baseQuery(key)
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        switch status {
        case errSecSuccess:
            guard let data = result as? Data else { throw SecretStoreError.corruptValue(key: key) }
            return data
        case errSecItemNotFound:
            return nil
        default:
            throw SecretStoreError.keychain(status: status, operation: "read")
        }
    }

    public func set(_ data: Data, for key: String) throws {
        let attributes: [String: Any] = [
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly,
        ]
        let updateStatus = SecItemUpdate(baseQuery(key) as CFDictionary, attributes as CFDictionary)
        switch updateStatus {
        case errSecSuccess:
            return
        case errSecItemNotFound:
            var insert = baseQuery(key)
            insert.merge(attributes) { _, new in new }
            let addStatus = SecItemAdd(insert as CFDictionary, nil)
            guard addStatus == errSecSuccess else {
                throw SecretStoreError.keychain(status: addStatus, operation: "add")
            }
        default:
            throw SecretStoreError.keychain(status: updateStatus, operation: "update")
        }
    }

    public func remove(_ key: String) throws {
        let status = SecItemDelete(baseQuery(key) as CFDictionary)
        guard status == errSecSuccess || status == errSecItemNotFound else {
            throw SecretStoreError.keychain(status: status, operation: "delete")
        }
    }

    /// Reads back the accessibility class actually stored for `key` (used by tests/diagnostics).
    public func accessibility(for key: String) throws -> String? {
        var query = baseQuery(key)
        query[kSecReturnAttributes as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: CFTypeRef?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        if status == errSecItemNotFound { return nil }
        guard status == errSecSuccess, let attributes = result as? [String: Any] else {
            throw SecretStoreError.keychain(status: status, operation: "attributes")
        }
        return attributes[kSecAttrAccessible as String] as? String
    }
}
