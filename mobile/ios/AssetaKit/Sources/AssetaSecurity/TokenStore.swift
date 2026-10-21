import Foundation

/// OAuth tokens as persisted on device. Raw token strings are opaque to the app;
/// authorization decisions are made by the server, not by inspecting these.
public struct StoredTokens: Codable, Equatable, Sendable {
    public var accessToken: String
    public var accessTokenExpiresAt: Date
    public var refreshToken: String?
    public var refreshTokenExpiresAt: Date?
    public var idToken: String?

    public init(
        accessToken: String,
        accessTokenExpiresAt: Date,
        refreshToken: String?,
        refreshTokenExpiresAt: Date?,
        idToken: String?
    ) {
        self.accessToken = accessToken
        self.accessTokenExpiresAt = accessTokenExpiresAt
        self.refreshToken = refreshToken
        self.refreshTokenExpiresAt = refreshTokenExpiresAt
        self.idToken = idToken
    }
}

/// Persists ``StoredTokens`` as one JSON blob in a ``SecretStore``.
public struct TokenStore: Sendable {
    public static let defaultAccount = "asseta.oauth.tokens.v1"

    private let store: any SecretStore
    private let account: String

    public init(store: any SecretStore, account: String = TokenStore.defaultAccount) {
        self.store = store
        self.account = account
    }

    public func load() throws -> StoredTokens? {
        guard let data = try store.data(for: account) else { return nil }
        do {
            return try JSONDecoder().decode(StoredTokens.self, from: data)
        } catch {
            // Undecodable tokens are useless; drop them so the user re-authenticates.
            try store.remove(account)
            return nil
        }
    }

    public func save(_ tokens: StoredTokens) throws {
        try store.set(try JSONEncoder().encode(tokens), for: account)
    }

    public func clear() throws {
        try store.remove(account)
    }
}
