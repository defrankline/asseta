import AssetaModel
import AssetaNetwork
import AssetaSecurity
import Foundation

/// Owns the OAuth session: sign-in (Authorization Code + PKCE), token persistence in the Keychain,
/// coalesced refresh and logout. Serves as the ``AccessTokenProvider`` for ``APIClient``.
///
/// The app asks for `offline_access`, so the refresh token outlives the 30-minute browser session (14 days of non-use).
/// Keycloak rotates refresh tokens: each refresh result replaces the stored tokens at once. Only the token endpoint's
/// refusal ends the session; a network failure never does (the app works offline).
///
/// The browser step is performed by the UI layer (SwiftUI `WebAuthenticationSession`, ephemeral)
/// between ``beginSignIn()`` and ``completeSignIn(callbackURL:pending:)`` so this type stays
/// testable without UIKit.
public actor AuthSession: AccessTokenProvider {
    public enum State: Sendable, Equatable {
        case signedOut
        case signedIn
    }

    private let config: OIDCConfiguration
    private let transport: any HTTPTransport
    private let tokenStore: TokenStore
    private let tokenClient: TokenClient
    private let now: @Sendable () -> Date
    /// Refresh this long before nominal expiry to absorb clock skew and request latency.
    private let refreshMargin: TimeInterval

    /// The user signed in when this session object was created (app launch, before any new
    /// sign-in): owner of field data written before per-user ownership was recorded.
    public nonisolated let launchAccount: AccountIdentity?

    private var metadata: OIDCProviderMetadata?
    private var tokens: StoredTokens?
    private var refreshTask: Task<StoredTokens, any Error>?

    public init(
        config: OIDCConfiguration,
        transport: any HTTPTransport = URLSessionTransport(),
        tokenStore: TokenStore,
        refreshMargin: TimeInterval = 60,
        now: @escaping @Sendable () -> Date = { Date() }
    ) {
        self.config = config
        self.transport = transport
        self.tokenStore = tokenStore
        self.tokenClient = TokenClient(config: config, transport: transport, now: now)
        self.refreshMargin = refreshMargin
        self.now = now
        let restored = try? tokenStore.load()
        self.tokens = restored
        self.launchAccount = restored.flatMap(Self.account)
    }

    public var state: State { tokens == nil ? .signedOut : .signedIn }

    /// The signed-in user (ID token `sub`, falling back to the access token), or nil when signed
    /// out. Identifies the owner of this phone's local field data; never used for authorization.
    public var account: AccountIdentity? { tokens.flatMap(Self.account) }

    static func account(_ tokens: StoredTokens) -> AccountIdentity? {
        AccountIdentity(jwt: tokens.idToken) ?? AccountIdentity(jwt: tokens.accessToken)
    }

    public nonisolated var callbackScheme: String { config.callbackScheme }

    // MARK: - Sign in

    public func beginSignIn() async throws -> PendingAuthorization {
        try PendingAuthorization.make(config: config, metadata: try await providerMetadata())
    }

    public func completeSignIn(callbackURL: URL, pending: PendingAuthorization) async throws {
        let code = try pending.authorizationCode(from: callbackURL, config: config)
        let fresh = try await tokenClient.exchange(code: code, pending: pending)
        try tokenStore.save(fresh)
        tokens = fresh
    }

    // MARK: - Change password

    /// The sign-in request plus `kc_action=UPDATE_PASSWORD`: Keycloak shows its own password page
    /// (re-authenticating if needed), so the app never sees the password.
    public func beginPasswordChange() async throws -> PendingAuthorization {
        try PendingAuthorization.make(config: config, metadata: try await providerMetadata(),
                                      kcAction: KeycloakAction.updatePassword)
    }

    /// Exchanges a returned code exactly like sign-in (replacing the stored tokens) and reports
    /// Keycloak's `kc_action_status`. The current session is kept whatever the outcome.
    public func completePasswordChange(callbackURL: URL, pending: PendingAuthorization) async throws -> PasswordChangeOutcome {
        let callback = try pending.actionCallback(from: callbackURL, config: config)
        if let code = callback.code {
            let fresh = try await tokenClient.exchange(code: code, pending: pending)
            try tokenStore.save(fresh)
            tokens = fresh
        }
        return PasswordChangeOutcome(status: callback.status)
    }

    // MARK: - AccessTokenProvider

    public func validAccessToken() async throws -> String {
        guard let current = tokens else { throw APIError.notAuthenticated }
        if current.accessTokenExpiresAt.timeIntervalSince(now()) > refreshMargin {
            return current.accessToken
        }
        return try await refresh().accessToken
    }

    public func refreshedAccessToken(rejected: String) async throws -> String {
        guard let current = tokens else { throw APIError.notAuthenticated }
        // Another caller may already have refreshed since `rejected` was handed out.
        if current.accessToken != rejected { return current.accessToken }
        let fresh = try await refresh()
        guard fresh.accessToken != rejected else {
            try? signOutLocally()
            throw APIError.notAuthenticated
        }
        return fresh.accessToken
    }

    // MARK: - Logout

    /// Ends the server session (best effort) and always wipes local tokens.
    /// Returns false if the server could not be reached (session then expires server-side).
    @discardableResult
    public func signOut() async -> Bool {
        let current = tokens
        refreshTask?.cancel()
        refreshTask = nil
        try? signOutLocally()
        guard let current else { return true }
        do {
            try await tokenClient.endSession(current, metadata: try await providerMetadata())
            return true
        } catch {
            return false
        }
    }

    // MARK: - Private

    private func signOutLocally() throws {
        tokens = nil
        try tokenStore.clear()
    }

    private func providerMetadata() async throws -> OIDCProviderMetadata {
        if let metadata { return metadata }
        let discovered = try await OIDCProviderMetadata.discover(config, transport: transport)
        metadata = discovered
        return discovered
    }

    /// Single-flight refresh: concurrent callers await the same network exchange. The task is registered before
    /// anything suspends, so a rotated refresh token (Keycloak `revokeRefreshToken`) is never sent twice.
    private func refresh() async throws -> StoredTokens {
        if let refreshTask { return try await refreshTask.value }
        guard let current = tokens else { throw APIError.notAuthenticated }
        let task = Task { try await self.exchangeRefreshToken(current) }
        refreshTask = task
        defer { refreshTask = nil }
        return try await task.value
    }

    /// One refresh round trip. Only the token endpoint's refusal (``refusesSession(_:)``) ends the session; anything
    /// else (offline, timeout, DNS, a captive portal, 5xx) keeps it and fails like a network error
    /// (``APIError/isRetryable``). The refresh token's own expiry is the server's to judge, not the phone clock's.
    private func exchangeRefreshToken(_ current: StoredTokens) async throws -> StoredTokens {
        let fresh: StoredTokens
        do {
            let metadata = try await providerMetadata()
            fresh = try await tokenClient.refresh(current, metadata: metadata)
        } catch let error as AuthError where Self.refusesSession(error) {
            // Refresh token expired, revoked or rotated out, or the user was disabled in Keycloak: the session is over.
            if tokens == current { try? signOutLocally() }
            throw APIError.notAuthenticated
        } catch {
            throw Self.temporary(error)
        }
        // Signed out or signed in again meanwhile: this result belongs to a session that is gone.
        guard tokens == current else {
            guard let tokens else { throw APIError.notAuthenticated }
            return tokens
        }
        // In memory first, then the Keychain (one item, replaced atomically): the newest refresh token is never lost
        // while the app runs, even if the Keychain write fails.
        tokens = fresh
        try? tokenStore.save(fresh)
        return fresh
    }

    /// An authoritative refusal by the token endpoint: HTTP 400/401 with an OAuth error (`invalid_grant`, ...), or no
    /// refresh token to use. A body-less 4xx (a proxy or captive portal) and every 5xx are not.
    static func refusesSession(_ error: AuthError) -> Bool {
        switch error {
        case let .tokenEndpoint(status, code, _): (status == 400 || status == 401) && !(code ?? "").isEmpty
        case .notSignedIn: true
        default: false
        }
    }

    /// A refresh that could not be done now, as the network error callers already retry (`APIError.transport` for no
    /// connection, timeouts and unreadable answers; `unexpectedStatus` for a sign-in server answering 5xx).
    static func temporary(_ error: any Error) -> any Error {
        switch error {
        case is CancellationError, is APIError: return error
        case let url as URLError:
            return APIError.transport(code: url.errorCode, message: url.localizedDescription, correlationID: "")
        case let AuthError.tokenEndpoint(status, _, _), let AuthError.discoveryFailed(status):
            return APIError.unexpectedStatus(status: status, correlationID: "")
        default:
            return APIError.transport(code: URLError.badServerResponse.rawValue,
                                      message: "The sign-in server could not be reached. Try again when you are online.",
                                      correlationID: "")
        }
    }
}
