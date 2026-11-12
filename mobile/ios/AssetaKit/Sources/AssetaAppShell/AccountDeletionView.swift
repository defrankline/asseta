#if os(iOS)
import SwiftUI

/// "Delete my account" (both apps, under the Sign out entry): what is deleted, an optional reason, type DELETE, then
/// the unsynced-work warning (Supervisor) and a final confirmation. Online only. On success the session signs out and
/// the login screen says "Your account was deleted."
public struct AccountDeletionView: View {
    @State private var flow: AccountDeletionFlow
    private let isOnline: Bool

    public init(session: SessionModel, isOnline: Bool) {
        _flow = State(initialValue: session.makeAccountDeletionFlow(isOnline: isOnline))
        self.isOnline = isOnline
    }

    public var body: some View {
        Form {
            Section {
                Text(AccountDeletionText.explain)
            }
            Section(AccountDeletionText.reasonLabel) {
                TextField(AccountDeletionText.reasonLabel, text: $flow.reason, axis: .vertical)
                    .lineLimit(2...5)
                    .accessibilityIdentifier("accountDeletion.reason")
            }
            Section {
                TextField(AccountDeletionText.confirmWord, text: $flow.typed)
                    .textInputAutocapitalization(.characters)
                    .autocorrectionDisabled()
                    .accessibilityIdentifier("accountDeletion.typed")
            } header: {
                Text(AccountDeletionText.typeLabel)
            } footer: {
                if !flow.isOnline { Text(AccountDeletionText.offline) }
            }
            Section {
                Button(role: .destructive) {
                    Task { await flow.submit() }
                } label: {
                    if flow.step == .deleting || flow.step == .syncing {
                        HStack(spacing: 8) {
                            ProgressView()
                            Text(flow.step == .deleting ? AccountDeletionText.deleting : AccountDeletionText.syncing)
                        }
                    } else {
                        Text(AccountDeletionText.submit)
                    }
                }
                .disabled(!flow.canSubmit)
                .accessibilityIdentifier("accountDeletion.submit")
                if let error = flow.error {
                    Text(error).font(.footnote).foregroundStyle(.red).accessibilityIdentifier("accountDeletion.error")
                }
            }
        }
        .navigationTitle(AccountDeletionText.title)
        .navigationBarTitleDisplayMode(.inline)
        .onChange(of: isOnline, initial: true) { _, online in flow.isOnline = online }
        .alert(AccountDeletionText.unsyncedTitle, isPresented: binding { if case .unsynced = $0 { true } else { false } }) {
            Button(AccountDeletionText.syncFirst) { Task { await flow.syncFirst() } }
            Button(AccountDeletionText.deleteAnyway, role: .destructive) { flow.deleteAnyway() }
            Button("Cancel", role: .cancel) { flow.cancel() }
        } message: {
            if case let .unsynced(count) = flow.step { Text(AccountDeletionText.unsyncedMessage(count)) }
        }
        .alert(AccountDeletionText.finalTitle, isPresented: binding { $0 == .confirm }) {
            Button(AccountDeletionText.finalAction, role: .destructive) { Task { await flow.confirm() } }
            Button("Cancel", role: .cancel) { flow.cancel() }
        } message: {
            Text(AccountDeletionText.finalMessage)
        }
    }

    /// Presented while `matches(step)`; dismissing by other means returns to the form.
    private func binding(_ matches: @escaping (AccountDeletionFlow.Step) -> Bool) -> Binding<Bool> {
        Binding(get: { matches(flow.step) }, set: { if !$0, matches(flow.step) { flow.cancel() } })
    }
}

/// The home-screen banner when the company's access is limited (e.g. a requested closure, with its deletion date).
/// `action` (Owner app, with permission to close the company) adds a second line and makes the banner open it.
public struct AccessReasonBanner: View {
    private let text: String
    private let actionLabel: String?
    private let action: (() -> Void)?

    public init(text: String, actionLabel: String? = nil, action: (() -> Void)? = nil) {
        self.text = text
        self.actionLabel = actionLabel
        self.action = action
    }

    public var body: some View {
        if let action {
            Button(action: action) { content(chevron: true) }
                .buttonStyle(.plain)
                .accessibilityAddTraits(.isButton)
        } else {
            content(chevron: false)
        }
    }

    private func content(chevron: Bool) -> some View {
        HStack(spacing: 12) {
            Image(systemName: "exclamationmark.triangle.fill").font(.title3).foregroundStyle(.white).accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 2) {
                Text(text).font(.subheadline.weight(.semibold)).foregroundStyle(.white)
                if let actionLabel { Text(actionLabel).font(.caption).foregroundStyle(.white.opacity(0.9)) }
            }
            Spacer(minLength: 0)
            if chevron { Image(systemName: "chevron.right").foregroundStyle(.white).accessibilityHidden(true) }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.red.opacity(0.85), in: RoundedRectangle(cornerRadius: 12))
        .accessibilityElement(children: .combine)
        .accessibilityIdentifier("access.banner")
    }
}
#endif
