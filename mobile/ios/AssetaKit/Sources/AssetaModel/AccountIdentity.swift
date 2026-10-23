import Foundation

/// The signed-in user that owns this phone's field data for a tenant: `subject` is the Keycloak
/// `sub` of the ID token (stable per user), `label` a readable name for the sync screen (email or
/// username; never used for decisions). Local sync state, outbox operations and evidence files are
/// recorded with their owner, so another user signing in on the same phone gets a fresh bootstrap
/// and never sees, or sends under their own token, the previous user's work.
public struct AccountIdentity: Sendable, Equatable, Codable {
    /// Owner of rows written before owners were recorded when nobody was signed in at the update.
    public static let unknownSubject = "unknown"

    public let subject: String
    public let label: String?

    public init(subject: String, label: String? = nil) {
        self.subject = subject
        self.label = label
    }

    /// Reads `sub` (and `email` / `preferred_username` / `name` as the label) from a JWT's claims.
    /// Identification only: the token is not verified here and authorization stays on the server.
    public init?(jwt: String?) {
        let parts = jwt?.split(separator: ".", omittingEmptySubsequences: false) ?? []
        guard parts.count == 3 else { return nil }
        var base64 = parts[1].replacingOccurrences(of: "-", with: "+").replacingOccurrences(of: "_", with: "/")
        base64 += String(repeating: "=", count: (4 - base64.count % 4) % 4)
        guard let data = Data(base64Encoded: base64),
              let claims = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
        else { return nil }
        func text(_ key: String) -> String? {
            (claims[key] as? String).flatMap { $0.trimmingCharacters(in: .whitespaces).isEmpty ? nil : $0 }
        }
        guard let subject = text("sub") else { return nil }
        self.init(subject: subject, label: text("email") ?? text("preferred_username") ?? text("name"))
    }
}
