#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaNetwork
import AssetaOwnerKit
import SwiftUI

/// Tracking alerts; acknowledge/resolve when permitted (one of the app's two business mutations).
struct AlertsView: View {
    let model: OwnerModel
    let machineID: UUID?
    @State private var status: AlertStatus? = .open
    @State private var loader = Loader<Page<AlertDTO>>()

    var body: some View {
        List {
            FilterChips(options: AlertText.filters, selection: $status)
                .listRowInsets(EdgeInsets()).listRowBackground(Color.clear)
            if let page = loader.value {
                if page.items.isEmpty {
                    EmptyState(title: AlertText.emptyTitle, message: AlertText.emptyMessage, systemImage: "checkmark.shield")
                }
                ForEach(AlertText.sorted(page.items)) { alert in
                    NavigationLink(value: OwnerRoute.alert(alert.id)) { AlertRow(alert: alert) }
                }
            } else if let error = loader.error {
                LoadFailure(message: error) { await reload() }
            } else {
                ProgressView().frame(maxWidth: .infinity)
            }
        }
        .staleBanner(loader, model: model)
        .navigationTitle("Alerts")
        .refreshable { await reload() }
        .task(id: ReloadKey(tick: model.changeTick, filter: status?.rawValue)) { await reload() }
    }

    private func reload() async {
        await loader.load(model, .alerts(status), OwnerAPI.alerts(status: status, pageSize: 100))
    }
}

/// Severity, status and time; title; type (same lines as Android's `AlertRow`).
struct AlertRow: View {
    let alert: AlertDTO

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Pill(text: alert.severity.label, color: alert.severity.color)
                Text(alert.status.humanized).font(.caption).foregroundStyle(.secondary)
                Spacer()
                Text(alert.eventTime.shortStamp).font(.caption).foregroundStyle(.secondary)
            }
            Text(alert.title).font(.headline)
            Text(OwnerFormat.humanize(alert.alertType)).font(.subheadline).foregroundStyle(.secondary)
        }
        .accessibilityElement(children: .combine)
    }
}

/// One alert. There is no single-alert endpoint, so it is found in the latest 200 alerts.
struct AlertDetailView: View {
    let model: OwnerModel
    let alertID: UUID
    @State private var loader = Loader<Page<AlertDTO>>()
    @State private var note = ""
    @State private var working = false
    @State private var actionError: String?
    @State private var message: String?
    @State private var resolved: AlertDTO?

    private var alert: AlertDTO? { resolved ?? loader.value?.items.first { $0.id == alertID } }

    var body: some View {
        Form {
            if let alert {
                Section {
                    LabeledContent("Severity") { Pill(text: alert.severity.label, color: alert.severity.color) }
                    LabeledContent("Status", value: alert.status.humanized)
                    LabeledContent("Type", value: OwnerFormat.humanize(alert.alertType))
                    LabeledContent("Happened", value: alert.eventTime.shortStamp)
                    if let ack = alert.acknowledgedAt { LabeledContent("Acknowledged", value: ack.shortStamp) }
                    if let done = alert.resolvedAt { LabeledContent("Resolved", value: done.shortStamp) }
                    if let resolution = alert.resolutionNote { LabeledContent("Resolution", value: resolution) }
                    if let machine = alert.machineID, model.features.fleet {
                        NavigationLink(value: OwnerRoute.machine(machine)) { Text("Open machine") }
                    }
                } header: {
                    Text(alert.title)
                }
                if case let .object(fields) = alert.evidence, !fields.isEmpty {
                    Section("Evidence") {
                        ForEach(fields.keys.sorted(), id: \.self) { key in
                            LabeledContent(OwnerFormat.humanize(key), value: AlertText.evidence(fields[key] ?? .null))
                        }
                    }
                }
                if !alert.status.isClosed { actions(alert) }
                if let message {
                    Text(message).foregroundStyle(Brand.amber).accessibilityIdentifier("alert.message")
                }
            } else if let error = loader.error {
                LoadFailure(message: error) { await reload() }
            } else if loader.value != nil {
                EmptyState(title: AlertText.notFoundTitle, message: AlertText.notFoundMessage, systemImage: "questionmark")
            } else {
                ProgressView()
            }
        }
        .staleBanner(loader, model: model)
        .navigationTitle("Alert")
        .refreshable { await reload() }
        .task(id: model.changeTick) { await reload() }
    }

    @ViewBuilder private func actions(_ alert: AlertDTO) -> some View {
        let block = model.mutationBlock(permitted: model.features.manageAlerts, showingCachedData: loader.isFromCache)
        Section {
            if let block {
                BlockedNote(block: block)
            } else {
                TextField(AlertText.noteLabel, text: $note, axis: .vertical)
                    .lineLimit(2...5)
                if alert.status == .open {
                    Button("Acknowledge") { Task { await act(.acknowledge) } }.disabled(working)
                }
                Button("Resolve") { Task { await act(.resolve) } }
                    .disabled(working || note.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                if let actionError {
                    Text(actionError).foregroundStyle(Palette.offline).font(.footnote).accessibilityIdentifier("alert.error")
                }
            }
        } header: {
            Text("Action")
        }
    }

    private func act(_ action: AlertAction) async {
        guard let repository = model.repository else { return }
        working = true
        defer { working = false }
        do {
            let request = try OwnerAPI.actOnAlert(alertID, action: action, note: note, idempotencyKey: UUID())
            let updated = try await repository.send(request)
            resolved = updated
            actionError = nil
            note = ""
            message = AlertText.done(updated.status)
            UIAccessibility.post(notification: .announcement, argument: message)
        } catch {
            actionError = DecisionErrorText.message(for: error)
            model.handle(error)
            if DecisionErrorText.needsReload(error) {
                resolved = nil
                await reload()
            }
        }
    }

    private func reload() async {
        await loader.load(model, .recentAlerts, OwnerAPI.alerts(status: nil, pageSize: 200))
    }
}
#endif
