import AssetaSecurity
import CryptoKit
import Foundation

/// RFC 7636 PKCE pair with S256 challenge.
public struct PKCE: Sendable, Equatable {
    public let verifier: String
    public let challenge: String
    public let method = "S256"

    public init(verifier: String) {
        self.verifier = verifier
        self.challenge = Self.base64URL(Data(SHA256.hash(data: Data(verifier.utf8))))
    }

    /// 32 random bytes -> 43-char base64url verifier (within RFC 7636's 43...128).
    public static func generate() throws -> PKCE {
        PKCE(verifier: try randomToken())
    }

    public static func randomToken(byteCount: Int = 32) throws -> String {
        base64URL(try DatabaseKeyProvider.randomBytes(count: byteCount))
    }

    public static func base64URL(_ data: Data) -> String {
        data.base64EncodedString()
            .replacingOccurrences(of: "+", with: "-")
            .replacingOccurrences(of: "/", with: "_")
            .replacingOccurrences(of: "=", with: "")
    }

    public static func decodeBase64URL(_ text: String) -> Data? {
        var base64 = text.replacingOccurrences(of: "-", with: "+").replacingOccurrences(of: "_", with: "/")
        base64 += String(repeating: "=", count: (4 - base64.count % 4) % 4)
        return Data(base64Encoded: base64)
    }
}
