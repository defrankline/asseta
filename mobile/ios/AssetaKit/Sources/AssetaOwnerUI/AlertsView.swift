#if os(iOS)
import AssetaAppShell
import AssetaModel
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
            Picker("Status", selection: $status) {
                Text("Open").tag(AlertStatus?.some(.open))
                Text("Acknowledged").tag(AlertStatus?.some(.acknowledged))
                Text("Resolved").tag(AlertStatus?.some(.resolved))
                Text("All").tag(AlertStatus?.none)
            }
            .pickerStyle(.segmented)
            .listRowBackground(Color.clear)
            if let page = loader.value {
                if page.items.isEmpty {
                    ContentUnavailableView("No alerts", systemImage: "checkmark.shield",
                                           description: Text("Nothing needs attention here."))
                }
                ForEach(page.items.sorted { ($0.severity.rank, $0.eventTime) > ($1.severity.rank, $1.eventTime) }) { alert in
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
            Text(alert.alertType.split(separator: "_").joined(separator: " ").lowercased().capitalizedFirst)
                .font(.subheadline).foregroundStyle(.secondary)
        }
        .accessibilityElement(children: .combine)
    }
}

/// One alert. There is no single-alert endpoint, so it is found in the latest alert list.
struct AlertDetailView: View {
    let model: OwnerModel
    let alertID: UUID
    @State private var loader = Loader<Page<AlertDTO>>()
    @State private var note = ""
    @State private var working = false
    @State private var actionError: String?
    @State private var resolved: AlertDTO?

    private var alert: AlertDTO? { resolved ?? loader.value?.items.first { $0.id == alertID } }

    var body: some View {
        Form {
            if let alert {
                Section {
                    LabeledContent("Severity") { Pill(text: alert.severity.label, color: alert.severity.color) }
                    LabeledContent("Status", value: alert.status.humanized)
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
                            LabeledContent(key.replacingOccurrences(of: "_", with: " ").capitalizedFirst,
                                           value: text(fields[key] ?? .null))
                        }
                    }
                }
                if !alert.status.isClosed { actions(alert) }
            } else if let error = loader.error {
                LoadFailure(message: error) { await reload() }
            } else if loader.value != nil {
                ContentUnavailableView("Alert not found", systemImage: "questionmark",
                                       description: Text("It may be older than the latest 200 alerts. Open it in the web console."))
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
                TextField("Note (required to resolve)", text: $note, axis: .vertical)
                    .lineLimit(2...5)
                if alert.status == .open {
                    Button("Acknowledge") { Task { await act(.acknowledge) } }.disabled(working)
                }
                Button("Resolve") { Task { await act(.resolve) } }
                    .disabled(working || note.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                if let actionError {
                    Text(actionError).foregroundStyle(.red).font(.footnote).accessibilityIdentifier("alert.error")
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
            resolved = try await repository.send(request)
            actionError = nil
            note = ""
            UIAccessibility.post(notification: .announcement, argument: action == .resolve ? "Alert resolved" : "Alert acknowledged")
        } catch {
            actionError = DecisionErrorText.message(for: error)
            model.handle(error)
        }
    }

    private func reload() async {
        await loader.load(model, .alerts(nil), OwnerAPI.alerts(status: nil, pageSize: 200))
    }

    private func text(_ value: JSONValue) -> String {
        switch value {
        case let .string(s): s
        case let .number(n): "\(n)"
        case let .bool(b): b ? "Yes" : "No"
        case .null: "—"
        default: (try? value.jsonString()) ?? "—"
        }
    }
}
#endif
