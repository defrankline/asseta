import AssetaModel
import AssetaNetwork
import Foundation
import Observation

/// Shared wording of "Delete my account" and of a deleted or disabled account (identical on Android).
public enum AccountDeletionText {
    public static let action = "Delete my account"
    public static let title = "Delete my account"
    public static let submit = "Delete my account"
    public static let explain = "Your login is deleted for good. Your name and email are removed; your records stay "
        + "with the company under an anonymous name. This cannot be undone."
    public static let reasonLabel = "Reason (optional)"
    public static let typeLabel = "Type DELETE to confirm"
    public static let confirmWord = "DELETE"
    public static let finalTitle = "Delete your account for good?"
    public static let finalMessage = "You will be signed out and this phone's saved data is erased. This cannot be undone."
    public static let finalAction = "Delete for good"
    public static let deleting = "Deleting…"
    public static let offline = "Connect to the internet to delete your account."
    public static let unsyncedTitle = "Records not yet sent will be lost"
    public static let syncFirst = "Sync first"
    public static let deleteAnyway = "Delete anyway"
    public static let syncing = "Syncing…"
    public static let deleted = "Your account was deleted."
    public static let inactive = "This account was deleted or disabled."
    public static let platformAccount = "Platform accounts are removed by the platform owner."
    public static let network = "Cannot reach Asseta. Check your connection and try again."

    public static func unsyncedMessage(_ count: Int) -> String {
        "\(count) item(s) on this phone are not synced yet. If you delete your account now they are lost. "
            + "Sync first to send them."
    }

    /// LAST_OWNER: the server's message (it names the companies); PLATFORM_ACCOUNT: who removes such accounts;
    /// no connection: the network message; anything else: the server's message.
    public static func message(for error: any Error) -> String {
        switch error {
        case let APIError.server(_, body) where body.code == "PLATFORM_ACCOUNT": platformAccount
        case let APIError.server(_, body): body.message
        case APIError.transport, is URLError: network
        case let error as APIError: error.localizedDescription
        default: network
        }
    }

    /// True when `typed` is the confirmation word (surrounding spaces ignored, case must match).
    public static func isConfirmed(_ typed: String) -> Bool {
        typed.trimmingCharacters(in: .whitespacesAndNewlines) == confirmWord
    }
}

/// What the signed-in app adds to "Delete my account". The Owner app needs none of it (its sign-out already erases
/// its saved data); the Supervisor app counts and syncs its unsynced work and erases its field data.
public struct AccountDeletionHooks: Sendable {
    /// This account's items on the phone not yet accepted by the server.
    public let unsyncedCount: @MainActor @Sendable () async -> Int
    /// Runs a sync now ("Sync first").
    public let syncNow: @MainActor @Sendable () async -> Void
    /// After the server deleted the account, before the normal sign-out.
    public let eraseLocalData: @MainActor @Sendable () async -> Void

    public init(unsyncedCount: @escaping @MainActor @Sendable () async -> Int,
                syncNow: @escaping @MainActor @Sendable () async -> Void,
                eraseLocalData: @escaping @MainActor @Sendable () async -> Void) {
        self.unsyncedCount = unsyncedCount
        self.syncNow = syncNow
        self.eraseLocalData = eraseLocalData
    }

    public static let none = AccountDeletionHooks(unsyncedCount: { 0 }, syncNow: {}, eraseLocalData: {})
}

/// "Delete my account": form (reason, type DELETE) → unsynced-work warning when this phone holds unsent items
/// (Sync first / Delete anyway) → final confirmation → deleting. A failure returns to the form with its message;
/// success signs out (the session shows "Your account was deleted."). Online only.
@MainActor
@Observable
public final class AccountDeletionFlow {
    public enum Step: Equatable {
        case form
        case unsynced(Int)
        case syncing
        case confirm
        case deleting
    }

    public var reason = ""
    public var typed = ""
    public var isOnline: Bool
    public private(set) var step: Step = .form
    public private(set) var error: String?

    private let hooks: AccountDeletionHooks
    private let perform: @MainActor (String?) async throws -> Void

    public init(isOnline: Bool, hooks: AccountDeletionHooks,
                perform: @escaping @MainActor (String?) async throws -> Void) {
        self.isOnline = isOnline
        self.hooks = hooks
        self.perform = perform
    }

    /// The submit button: online, DELETE typed, nothing in progress.
    public var canSubmit: Bool { isOnline && AccountDeletionText.isConfirmed(typed) && step == .form }

    /// The trimmed reason, nil when empty.
    public var trimmedReason: String? {
        let text = reason.trimmingCharacters(in: .whitespacesAndNewlines)
        return text.isEmpty ? nil : text
    }

    /// "Delete my account": warns about unsynced work first, else asks for the final confirmation.
    public func submit() async {
        error = nil
        guard isOnline else { error = AccountDeletionText.offline; return }
        guard AccountDeletionText.isConfirmed(typed), step == .form else { return }
        await checkUnsynced()
    }

    /// "Sync first": syncs, then warns again while items are still waiting.
    public func syncFirst() async {
        step = .syncing
        await hooks.syncNow()
        await checkUnsynced()
    }

    /// "Delete anyway": the unsent items are given up.
    public func deleteAnyway() { step = .confirm }

    /// Any "Cancel": back to the form, nothing sent.
    public func cancel() { step = .form }

    /// "Delete for good". True when the account was deleted (the session has signed out).
    @discardableResult
    public func confirm() async -> Bool {
        guard isOnline else {
            error = AccountDeletionText.offline
            step = .form
            return false
        }
        step = .deleting
        do {
            try await perform(trimmedReason)
            return true
        } catch {
            self.error = AccountDeletionText.message(for: error)
            step = .form
            return false
        }
    }

    private func checkUnsynced() async {
        let count = await hooks.unsyncedCount()
        step = count > 0 ? .unsynced(count) : .confirm
    }
}

/// The company-closure (or other limited-access) banner on the home screen of both apps.
public enum AccessBanner {
    /// `access_state_reason` of the open company while its access is limited; nil at full access (the server keeps
    /// a stale reason such as "Onboarding" or "Company closure cancelled" there).
    public static func text(_ tenant: TenantMembership) -> String? {
        guard tenant.accessState != .full, let reason = tenant.accessStateReason?.trimmingCharacters(in: .whitespacesAndNewlines),
              !reason.isEmpty else { return nil }
        return reason
    }
}
