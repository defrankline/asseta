import Foundation

/// Minimal secret storage abstraction. Production uses ``KeychainSecretStore``;
/// tests may use ``InMemorySecretStore``.
public protocol SecretStore: Sendable {
    func data(for key: String) throws -> Data?
    func set(_ data: Data, for key: String) throws
    func remove(_ key: String) throws
}

public enum SecretStoreError: Error, Equatable, Sendable {
    /// An `OSStatus` returned by the Security framework.
    case keychain(status: Int32, operation: String)
    case randomGenerationFailed(status: Int32)
    case corruptValue(key: String)
}

/// Thread-safe in-memory store for tests and previews. Never use for real secrets.
public final class InMemorySecretStore: SecretStore, @unchecked Sendable {
    // @unchecked: all access to `values` is serialized by `lock`.
    private let lock = NSLock()
    private var values: [String: Data] = [:]

    public init() {}

    public func data(for key: String) throws -> Data? {
        lock.withLock { values[key] }
    }

    public func set(_ data: Data, for key: String) throws {
        lock.withLock { values[key] = data }
    }

    public func remove(_ key: String) throws {
        lock.withLock { _ = values.removeValue(forKey: key) }
    }
}
