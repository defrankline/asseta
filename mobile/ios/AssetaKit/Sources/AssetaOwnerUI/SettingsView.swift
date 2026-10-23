#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaOwnerKit
import SwiftUI

/// Push priority matrix (category × severity), push devices, offline data and account (same sections and
/// wording as the Android Owner app, from `SettingsText`).
struct SettingsView: View {
    let model: OwnerModel
    @State private var routing = Loader<[NotificationRoutingDTO]>()
    @State private var devices = Loader<Page<PushDeviceDTO>>()
    @State private var matrix: RoutingMatrix?
    @State private var original: RoutingMatrix?
    @State private var saving = false
    @State private var message: String?
    @State private var deviceError: String?
    @State private var confirmSignOut = false
    @State private var push = PushCenter.shared

    var body: some View {
        Form {
            if model.features.notifications { pushMatrix }
            Section {
                LabeledContent("This phone", value: push.statusText)
                LabeledContent("Provider", value: push.providerName)
                if push.isEnabled {
                    Button("Enable push notifications") { Task { await push.enable(); await reloadDevices() } }
                        .disabled(!model.isOnline)
                } else {
                    FootNote(SettingsText.pushUnavailable)
                }
                if (devices.value?.items ?? []).isEmpty {
                    Text("No devices registered for push.").font(.footnote).foregroundStyle(.secondary)
                }
                ForEach(devices.value?.items ?? []) { device in
                    VStack(alignment: .leading, spacing: 2) {
                        Text("\(device.deviceLabel ?? device.platform) · \(OwnerFormat.humanize(device.app)) · …\(device.tokenHint)")
                            .font(.subheadline)
                        Text("\(device.active ? "Active" : "Inactive") · registered \(device.lastRegisteredAt.shortStamp)")
                            .font(.caption).foregroundStyle(.secondary)
                        if device.active {
                            Button("Stop push to this device") { Task { await deactivate(device) } }
                                .font(.subheadline).buttonStyle(.borderless)
                                .disabled(!model.isOnline)
                        }
                    }
                }
                if let deviceError { Text(deviceError).font(.footnote).foregroundStyle(.red) }
            } header: {
                Text("Push devices")
            } footer: {
                Text(SettingsText.devicesFooter)
            }
            Section {
                Text(SettingsText.offlineData).font(.footnote).foregroundStyle(.secondary)
            } header: {
                Text("Offline data")
            }
            Section("Account") {
                LabeledContent("Company", value: model.tenant.name)
                LabeledContent("Signed in as", value: model.me.email)
                if model.me.tenants.filter({ $0.accessState.allowsEntry }).count > 1 {
                    Button("Switch company") { model.leaveTenant() }
                }
                Button("Sign out", role: .destructive) { confirmSignOut = true }
                    .accessibilityIdentifier("settings.signOut")
            }
        }
        .navigationTitle("Settings")
        .task { await reload() }
        .refreshable { await reload() }
        .confirmationDialog(SettingsText.signOutConfirm, isPresented: $confirmSignOut, titleVisibility: .visible) {
            Button(SettingsText.signOutAction, role: .destructive) { Task { await model.signOut() } }
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
                                    Label(matrix.severityLabel(category, severity), systemImage: "circle.fill")
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
            Text(SettingsText.matrixTitle)
        } footer: {
            Text(SettingsText.matrixFooter)
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
        await reloadDevices()
    }

    private func reloadDevices() async {
        if let repository = model.repository, model.isOnline,
           let page = try? await repository.send(OwnerAPI.pushDevices()) {
            devices.replace(page)
        }
    }

    private func deactivate(_ device: PushDeviceDTO) async {
        guard let repository = model.repository,
              let request = try? OwnerAPI.deactivatePushDevice(device.id, idempotencyKey: UUID()) else { return }
        do {
            _ = try await repository.send(request)
            deviceError = nil
            await reloadDevices()
        } catch {
            deviceError = DecisionErrorText.message(for: error)
            model.handle(error)
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
            message = SettingsText.saved
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
