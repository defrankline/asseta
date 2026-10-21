import AssetaAuth
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
        return SessionModel(auth: auth, api: api)
    }
}

#if os(iOS)
/// Scene content for both apps; shows a clear error if the build is misconfigured.
public struct AssetaAppScene: View {
    private let flavor: AppFlavor
    @State private var result: Result<SessionModel, any Error>

    public init(flavor: AppFlavor, info: [String: Any] = Bundle.main.infoDictionary ?? [:]) {
        self.flavor = flavor
        _result = State(initialValue: Result { try AppBootstrap.makeSession(info: info) })
    }

    public var body: some View {
        switch result {
        case let .success(model):
            RootView(flavor: flavor, model: model)
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
