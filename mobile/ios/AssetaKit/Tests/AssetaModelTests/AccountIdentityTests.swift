import AssetaModel
import Foundation
import Testing

struct AccountIdentityTests {
    private func jwt(_ claims: String) -> String {
        func encode(_ text: String) -> String {
            Data(text.utf8).base64EncodedString().replacingOccurrences(of: "+", with: "-")
                .replacingOccurrences(of: "/", with: "_").replacingOccurrences(of: "=", with: "")
        }
        return encode(#"{"alg":"RS256"}"#) + "." + encode(claims) + ".sig"
    }

    @Test func readsSubjectAndReadableLabel() {
        #expect(AccountIdentity(jwt: jwt(#"{"sub":"8d1c-user","email":"sam@example.com","preferred_username":"sam"}"#))
            == AccountIdentity(subject: "8d1c-user", label: "sam@example.com"))
        #expect(AccountIdentity(jwt: jwt(#"{"sub":"u2","preferred_username":"sam"}"#)) == AccountIdentity(subject: "u2", label: "sam"))
        #expect(AccountIdentity(jwt: jwt(#"{"sub":"u3"}"#)) == AccountIdentity(subject: "u3"))
    }

    @Test func malformedOrSubjectlessTokensHaveNoAccount() {
        #expect(AccountIdentity(jwt: nil) == nil)
        #expect(AccountIdentity(jwt: "not-a-jwt") == nil)
        #expect(AccountIdentity(jwt: jwt(#"{"email":"x@example.com"}"#)) == nil)
        #expect(AccountIdentity(jwt: "a.%%%.c") == nil)
    }
}
