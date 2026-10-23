/// Shared wording of the "Change password" account action (identical on Android).
public enum PasswordChangeText {
    public static let action = "Change password"
    public static let footer = "Opens the secure Asseta sign-in page."
    public static let offline = "Connect to the internet to change your password."
    public static let changed = "Password changed."
    public static let failedTitle = "Couldn't change password"
    public static let failed = "Your password was not changed. Please try again."
}

#if os(iOS)
import AssetaAuth
import AuthenticationServices
import SwiftUI

/// "Change password": opens Keycloak's password page in the same ephemeral browser session as
/// sign-in. Disabled offline or while the page is open. `showsFooter` adds the explanation as a
/// second line (menus); in a Form the section footer carries it instead.
public struct ChangePasswordButton: View {
    private let session: SessionModel
    private let isOnline: Bool
    private let showsFooter: Bool
    @Environment(\.webAuthenticationSession) private var webAuthenticationSession

    public init(session: SessionModel, isOnline: Bool, showsFooter: Bool = false) {
        self.session = session
        self.isOnline = isOnline
        self.showsFooter = showsFooter
    }

    public var body: some View {
        Button {
            Task { await session.changePassword(using: authenticate) }
        } label: {
            Text(PasswordChangeText.action)
            if showsFooter { Text(isOnline ? PasswordChangeText.footer : PasswordChangeText.offline) }
        }
        .disabled(!isOnline || session.passwordChange == .inProgress)
        .accessibilityIdentifier("account.changePassword")
    }

    private func authenticate(url: URL, callbackScheme: String) async throws -> URL {
        try await webAuthenticationSession.ephemeralAuthenticate(url: url, callbackScheme: callbackScheme)
    }
}

/// Footer for the "Change password" row: what it opens, or why it is disabled.
public func changePasswordFooter(isOnline: Bool) -> Text {
    Text(isOnline ? PasswordChangeText.footer : PasswordChangeText.offline)
}

extension WebAuthenticationSession {
    /// Ephemeral browser session: no shared Safari cookies, so signing out of the app also
    /// leaves no reusable Keycloak SSO cookie on the device.
    func ephemeralAuthenticate(url: URL, callbackScheme: String) async throws -> URL {
        do {
            return try await authenticate(using: url, callbackURLScheme: callbackScheme,
                                          preferredBrowserSession: .ephemeral)
        } catch let error as ASWebAuthenticationSessionError where error.code == .canceledLogin {
            throw AuthError.userCancelled
        }
    }
}

/// Presents "Password changed." on success and a short error on failure (a cancel shows nothing).
struct PasswordChangeAlerts: ViewModifier {
    let session: SessionModel

    func body(content: Content) -> some View {
        content
            .alert(PasswordChangeText.changed, isPresented: binding { $0 == .changed }) {
                Button("OK") { session.dismissPasswordChange() }
            }
            .alert(PasswordChangeText.failedTitle, isPresented: binding { if case .failed = $0 { true } else { false } }) {
                Button("OK") { session.dismissPasswordChange() }
            } message: {
                if case let .failed(message) = session.passwordChange { Text(message) }
            }
    }

    private func binding(_ matches: @escaping (SessionModel.PasswordChangeState) -> Bool) -> Binding<Bool> {
        Binding(get: { matches(session.passwordChange) },
                set: { if !$0, matches(session.passwordChange) { session.dismissPasswordChange() } })
    }
}
#endif
