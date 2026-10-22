import AssetaAuth
import AssetaModel
import AssetaNetwork
import AssetaSecurity
import Foundation
import Observation

/// UI state machine shared by both apps: sign-in, profile (`/me`) and tenant selection.
///
/// Permissions/menus from `/me` only decide what is *shown*; the server re-authorizes every call.
@MainActor
@Observable
public final class SessionModel {
    public enum Phase: Equatable {
        case signedOut
        case signingIn
        case loadingProfile
        /// Signed in, but `/me` could not be loaded (e.g. offline); ``errorMessage`` explains.
        case profileUnavailable
        case ready(MeResponse)
    }

    /// Opens the authorization URL in a browser and returns the callback URL.
    public typealias BrowserAuthenticator = @MainActor (_ url: URL, _ callbackScheme: String) async throws -> URL

    public private(set) var phase: Phase = .signedOut
    public private(set) var selectedTenant: TenantMembership?
    public private(set) var errorMessage: String?

    /// Optional offline fallback for `/me` (Owner app): the last profile saved in its encrypted
    /// cache, shown read-only when the server cannot be reached. Nil keeps the strict behaviour.
    public struct ProfileCache {
        public let load: @MainActor () -> MeResponse?
        public let save: @MainActor (MeResponse) -> Void

        public init(load: @escaping @MainActor () -> MeResponse?, save: @escaping @MainActor (MeResponse) -> Void) {
            self.load = load
            self.save = save
        }
    }

    public var profileCache: ProfileCache?
    /// True while ``phase`` shows a cached profile because the server was unreachable.
    public private(set) var isProfileFromCache = false
    /// Runs on every sign-out (user, `/me` 401, server-forced) before the tokens are wiped; the
    /// Owner app wipes its offline cache here.
    public var onSignOut: (@MainActor () async -> Void)?

    private let auth: AuthSession
    private let api: APIClient
    /// Build configuration and Keychain store, for feature modules that need them (e.g. field sync).
    public let configuration: AppConfiguration?
    public let secrets: (any SecretStore)?

    public init(auth: AuthSession, api: APIClient, configuration: AppConfiguration? = nil,
                secrets: (any SecretStore)? = nil) {
        self.auth = auth
        self.api = api
        self.configuration = configuration
        self.secrets = secrets
    }

    /// Bearer token source for non-REST channels (the realtime WebSocket).
    public var accessTokens: any AccessTokenProvider { auth }

    /// Client scoped to the selected tenant (sends `X-Tenant-ID`), for feature screens.
    public var tenantClient: APIClient? {
        selectedTenant.map { api.withTenant($0.tenantID) }
    }

    /// Restores a persisted session on launch.
    public func start() async {
        if await auth.state == .signedIn {
            await loadProfile()
        } else {
            phase = .signedOut
        }
    }

    public func signIn(using authenticate: BrowserAuthenticator) async {
        errorMessage = nil
        phase = .signingIn
        do {
            let pending = try await auth.beginSignIn()
            let callback = try await authenticate(pending.url, auth.callbackScheme)
            try await auth.completeSignIn(callbackURL: callback, pending: pending)
        } catch {
            phase = .signedOut
            errorMessage = Self.message(for: error)
            return
        }
        await loadProfile()
    }

    public func loadProfile() async {
        errorMessage = nil
        phase = .loadingProfile
        do {
            let me = try await api.me()
            isProfileFromCache = false
            profileCache?.save(me)
            apply(me)
        } catch APIError.notAuthenticated {
            await signOut()
        } catch {
            // Offline (or server down) with a cached profile: open read-only cached data instead.
            if (error as? APIError)?.isRetryable == true, await auth.state == .signedIn,
               let cached = profileCache?.load() {
                isProfileFromCache = true
                apply(cached)
                return
            }
            errorMessage = Self.message(for: error)
            // Stay signed in (e.g. offline); user can retry.
            phase = await auth.state == .signedIn ? .profileUnavailable : .signedOut
        }
    }

    private func apply(_ me: MeResponse) {
        phase = .ready(me)
        // Keep the selection only if the server still grants entry to that tenant.
        if let current = selectedTenant {
            selectedTenant = me.tenants.first { $0.tenantID == current.tenantID && $0.accessState.allowsEntry }
        }
        if selectedTenant == nil {
            let enterable = me.tenants.filter { $0.accessState.allowsEntry }
            if enterable.count == 1 { selectedTenant = enterable[0] }
        }
    }

    public func selectTenant(_ tenant: TenantMembership) {
        guard tenant.accessState.allowsEntry else { return }
        selectedTenant = tenant
    }

    public func clearTenantSelection() {
        selectedTenant = nil
    }

    public func signOut() async {
        selectedTenant = nil
        phase = .signedOut
        isProfileFromCache = false
        await onSignOut?()
        await auth.signOut()
    }

    /// Ends the session because the server demands it (e.g. this device was revoked) and shows
    /// `explanation` on the login screen. Local tokens are wiped by sign-out.
    public func endSession(explanation: String) async {
        await signOut()
        errorMessage = explanation
    }

    public func dismissError() {
        errorMessage = nil
    }

    static func message(for error: any Error) -> String? {
        switch error {
        case AuthError.userCancelled:
            return nil
        case let error as APIError:
            if let cid = error.correlationID {
                return "\(error.localizedDescription) (ref \(cid.prefix(8)))"
            }
            return error.localizedDescription
        case let AuthError.authorizationDenied(code, description):
            return description ?? "Sign-in was refused (\(code))."
        case is AuthError:
            return "Sign-in failed. Please try again."
        case let error as URLError:
            return error.localizedDescription
        default:
            return "Something went wrong. Please try again."
        }
    }
}
