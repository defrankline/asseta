import AssetaAuth
import Foundation

/// Environment endpoints, read from the app's Info.plist (populated from build settings in
/// `project.yml`), so no URL is hard-coded in source.
public struct AppConfiguration: Sendable, Equatable {
    public let apiBaseURL: URL
    public let oidc: OIDCConfiguration
    public let keychainService: String

    public init(apiBaseURL: URL, oidc: OIDCConfiguration, keychainService: String) {
        self.apiBaseURL = apiBaseURL
        self.oidc = oidc
        self.keychainService = keychainService
    }

    public enum LoadError: Error, Equatable {
        case missingKey(String)
        case invalidURL(String)
    }

    public static func load(from info: [String: Any]) throws -> AppConfiguration {
        func url(_ key: String) throws -> URL {
            guard let raw = info[key] as? String, !raw.isEmpty else { throw LoadError.missingKey(key) }
            guard let value = URL(string: raw), value.scheme != nil else {
                throw LoadError.invalidURL(key)
            }
            return value
        }
        guard let bundleID = info["CFBundleIdentifier"] as? String else { throw LoadError.missingKey("CFBundleIdentifier") }
        let api = try url("AssetaAPIBaseURL"), issuer = try url("AssetaOIDCIssuer")
        for (key, value) in [("AssetaAPIBaseURL", api), ("AssetaOIDCIssuer", issuer)] where value.host == nil {
            throw LoadError.invalidURL(key)
        }
        let oidc = OIDCConfiguration(
            issuer: issuer,
            redirectURI: try url("AssetaOIDCRedirectURI"),
            postLogoutRedirectURI: try url("AssetaOIDCPostLogoutRedirectURI")
        )
        do {
            try oidc.validateRedirects()
        } catch {
            throw LoadError.invalidURL("AssetaOIDCRedirectURI/AssetaOIDCPostLogoutRedirectURI")
        }
        return AppConfiguration(apiBaseURL: api, oidc: oidc, keychainService: bundleID)
    }
}
