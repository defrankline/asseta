#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaNetwork
import AssetaOwnerKit
import SwiftUI

/// The company's closure request, read-only (opened from the home banner with `tenant.company.close`): status, who
/// asked, the deletion date, and "Cancel closure" with a required reason while it waits. Read live, never cached.
struct CompanyClosureView: View {
    let model: OwnerModel
    @State private var status: CompanyDeletionStatusDTO?
    @State private var loadError: String?
    @State private var askCancel = false
    @State private var reason = ""
    @State private var cancelError: String?
    @State private var message: String?
    @State private var cancelling = false

    var body: some View {
        Form {
            if let status {
                if let request = status.request {
                    Section {
                        ForEach(Array(CompanyClosureText.rows(request).enumerated()), id: \.offset) { _, row in
                            LabeledContent(row.0, value: row.1)
                        }
                    } footer: {
                        Text(CompanyClosureText.footer)
                    }
                    if CompanyClosureText.canCancel(request) {
                        Section {
                            Button(CompanyClosureText.cancelAction, role: .destructive) {
                                reason = ""
                                cancelError = nil
                                askCancel = true
                            }
                            .disabled(!model.isOnline || cancelling)
                            .accessibilityIdentifier("closure.cancel")
                        } footer: {
                            if !model.isOnline { Text(CompanyClosureText.offline) }
                        }
                    }
                } else {
                    Section { Text(CompanyClosureText.none).foregroundStyle(.secondary) }
                }
            } else if let loadError {
                Section {
                    Text(loadError).foregroundStyle(.red)
                    Button("Retry") { Task { await load() } }
                }
            } else {
                ProgressView().frame(maxWidth: .infinity)
            }
            if let cancelError { Section { Text(cancelError).foregroundStyle(.red) } }
        }
        .navigationTitle(CompanyClosureText.title)
        .navigationBarTitleDisplayMode(.inline)
        .task { await load() }
        .refreshable { await load() }
        .alert(CompanyClosureText.cancelTitle, isPresented: $askCancel) {
            TextField(CompanyClosureText.cancelReasonLabel, text: $reason)
            Button(CompanyClosureText.cancelAction, role: .destructive) { Task { await cancel() } }
            Button(CompanyClosureText.cancelKeep, role: .cancel) {}
        }
        .alert(CompanyClosureText.cancelled, isPresented: Binding(get: { message != nil }, set: { if !$0 { message = nil } })) {
            // The company is back to normal: `/me` drops the banner (and the read-only state).
            Button("OK") { message = nil; Task { await model.session.loadProfile() } }
        }
    }

    private func load() async {
        guard let client = model.session.tenantClient else { loadError = "This build is missing its configuration."; return }
        do {
            status = try await client.send(OwnerAPI.companyDeletion())
            loadError = nil
        } catch {
            loadError = DecisionErrorText.message(for: error)
            model.handle(error)
        }
    }

    private func cancel() async {
        guard let client = model.session.tenantClient else { return }
        cancelling = true
        defer { cancelling = false }
        switch await CompanyClosureCancel.run(client: client, reason: reason, isOnline: model.isOnline) {
        case .cancelled:
            cancelError = nil
            await load()
            message = CompanyClosureText.cancelled
        case let .failed(text):
            cancelError = text
        }
    }
}
#endif
