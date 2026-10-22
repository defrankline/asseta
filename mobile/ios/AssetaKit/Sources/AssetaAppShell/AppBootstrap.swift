import AssetaAuth
import AssetaModel
import AssetaNetwork
import AssetaSecurity
import Foundation
import SwiftUI

/// Builds the shared dependency graph for an app target from its Info.plist.
@MainActor
public enum AppBootstrap {
    public static func makeSession(info: [String: Any]) throws -> SessionModel {
        let configuration = try AppConfiguration.load(from: info)
        let secrets = KeychainSecretStore(service: configuration.keychainService)
        let transport = URLSessionTransport()
        let auth = AuthSession(config: configuration.oidc, transport: transport, tokenStore: TokenStore(store: secrets))
        let api = APIClient(baseURL: configuration.apiBaseURL, transport: transport, tokens: auth)
        return SessionModel(auth: auth, api: api, configuration: configuration, secrets: secrets)
    }
}

#if os(iOS)
/// What a feature home screen receives once the user is signed in with a tenant selected.
public struct HomeContext {
    public let session: SessionModel
    public let me: MeResponse
    public let tenant: TenantMembership
}

/// Optional replacement for the default post-login screen (the Supervisor field app uses it).
public typealias HomeBuilder = @MainActor (HomeContext) -> AnyView

/// Scene content for both apps; shows a clear error if the build is misconfigured.
public struct AssetaAppScene: View {
    private let flavor: AppFlavor
    private let home: HomeBuilder?
    @State private var result: Result<SessionModel, any Error>

    /// `configure` runs once on the new session (e.g. the Owner app installs its offline profile
    /// cache and sign-out wipe).
    public init(flavor: AppFlavor, info: [String: Any] = Bundle.main.infoDictionary ?? [:], home: HomeBuilder? = nil,
                configure: (@MainActor (SessionModel) -> Void)? = nil) {
        self.flavor = flavor
        self.home = home
        let result = Result { try AppBootstrap.makeSession(info: info) }
        if case let .success(model) = result { configure?(model) }
        _result = State(initialValue: result)
    }

    public var body: some View {
        switch result {
        case let .success(model):
            RootView(flavor: flavor, model: model, home: home)
        case let .failure(error):
            ContentUnavailableView(
                "Build misconfigured",
                systemImage: "exclamationmark.triangle",
                description: Text(String(describing: error))
            )
        }
    }
}
#endif
