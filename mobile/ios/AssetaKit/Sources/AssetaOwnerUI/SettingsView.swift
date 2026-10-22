#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaOwnerKit
import SwiftUI

/// Push priority matrix (category × severity), push devices, offline data and sign-out.
struct SettingsView: View {
    let model: OwnerModel
    @State private var routing = Loader<[NotificationRoutingDTO]>()
    @State private var devices = Loader<Page<PushDeviceDTO>>()
    @State private var matrix: RoutingMatrix?
    @State private var original: RoutingMatrix?
    @State private var saving = false
    @State private var message: String?
    @State private var confirmSignOut = false
    @State private var push = PushCenter.shared

    var body: some View {
        Form {
            if model.features.notifications { pushMatrix }
            Section {
                LabeledContent("This phone", value: push.statusText)
                ForEach(devices.value?.items ?? []) { device in
                    LabeledContent("\(device.deviceLabel ?? device.platform) · \(device.app.capitalized)",
                                   value: device.active ? "Active · \(device.tokenHint)" : "Inactive")
                        .font(.subheadline)
                }
            } header: {
                Text("Push devices")
            } footer: {
                Text("Push notifications go to this phone for the company that is open. Signing out unregisters it.")
            }
            Section {
                Text("Screens you have opened are kept encrypted on this phone for up to 7 days so you can look at "
                    + "them offline. Saved data is clearly marked stale and can't be changed. Signing out erases it.")
                    .font(.footnote).foregroundStyle(.secondary)
            } header: {
                Text("Offline data")
            }
            Section {
                LabeledContent("Signed in as", value: model.me.email)
                Button("Sign out", role: .destructive) { confirmSignOut = true }
                    .accessibilityIdentifier("settings.signOut")
            }
        }
        .navigationTitle("Settings")
        .task { await reload() }
        .refreshable { await reload() }
        .confirmationDialog("Sign out?", isPresented: $confirmSignOut, titleVisibility: .visible) {
            Button("Sign out and erase saved data", role: .destructive) { Task { await model.signOut() } }
        }
    }

    @ViewBuilder private var pushMatrix: some View {
        let block = model.mutationBlock(permitted: true, showingCachedData: routing.isFromCache)
        Section {
            if let matrix {
                ForEach(matrix.categories, id: \.self) { category in
                    VStack(alignment: .leading, spacing: 6) {
                        Text(RoutingMatrix.label(category)).font(.subheadline.bold())
                        ForEach(RoutingMatrix.severities, id: \.self) { severity in
                            if matrix.row(category, severity) != nil {
                                Toggle(isOn: binding(category, severity)) {
                                    Label(severity.label, systemImage: "circle.fill")
                                        .labelStyle(SeverityLabelStyle(color: severity.color))
                                }
                                .disabled(block != nil || matrix.isPushLocked(category, severity))
                                .accessibilityLabel("Push for \(RoutingMatrix.label(category)), \(severity.label)")
                                .accessibilityHint(matrix.isPushLocked(category, severity) ? "Always on, set by Asseta" : "")
                            }
                        }
                    }
                }
                if let block { BlockedNote(block: block) }
                Button(saving ? "Saving…" : "Save") { Task { await save() } }
                    .disabled(block != nil || saving || changes.isEmpty)
                if let message { Text(message).font(.footnote).foregroundStyle(.secondary) }
            } else if let error = routing.error {
                Text(error).foregroundStyle(.red)
            } else {
                ProgressView()
            }
        } header: {
            Text("Push priorities")
        } footer: {
            Text("Choose which notifications reach this phone as push. Locked switches are required by Asseta. "
                + "Every notification stays in the in-app inbox.")
        }
    }

    private var changes: [NotificationRoutingChangeIn] {
        guard let matrix, let original else { return [] }
        return matrix.changes(from: original)
    }

    private func binding(_ category: String, _ severity: AlertSeverity) -> Binding<Bool> {
        Binding(get: { matrix?.isPushOn(category, severity) ?? false },
                set: { on in matrix?.setPush(on, category: category, severity: severity) })
    }

    private func reload() async {
        await routing.load(model, .routing, OwnerAPI.routing())
        if let rows = routing.value {
            matrix = RoutingMatrix(rows)
            original = matrix
        }
        if let repository = model.repository, model.isOnline,
           let page = try? await repository.send(OwnerAPI.pushDevices()) {
            devices.replace(page)
        }
    }

    private func save() async {
        guard let repository = model.repository, !changes.isEmpty else { return }
        saving = true
        defer { saving = false }
        do {
            let rows = try await repository.send(try OwnerAPI.updateRouting(changes, idempotencyKey: UUID()))
            routing.replace(rows)
            matrix = RoutingMatrix(rows)
            original = matrix
            message = "Saved."
        } catch {
            message = DecisionErrorText.message(for: error)
            model.handle(error)
        }
    }
}

struct SeverityLabelStyle: LabelStyle {
    let color: Color

    func makeBody(configuration: Configuration) -> some View {
        HStack(spacing: 8) {
            configuration.icon.font(.caption2).foregroundStyle(color).accessibilityHidden(true)
            configuration.title
        }
    }
}
#endif
