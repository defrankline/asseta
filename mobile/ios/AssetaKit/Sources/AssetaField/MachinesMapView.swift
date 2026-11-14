#if os(iOS)
import AssetaAppShell
import AssetaFleetMap
import AssetaModel
import AssetaNetwork
import AssetaOwnerKit
import SwiftUI

extension FieldModel {
    /// `tenant.fleet.read` (from `/me` for this company) offers the Map / List switch on My machines.
    var canSeeMachineMap: Bool { FleetMapRules.canShowMap(permissions: tenant.permissions) }

    /// The machine map (online only): the server returns this supervisor's own machines, or every machine when the
    /// company's `TRACKING.field_fleet_scope` is `ALL`. Never filtered on the phone.
    func loadMachineMap() async -> FleetMapRules.State {
        let client = session.tenantClient
        return await FleetMapRules.load(online: isOnline) {
            guard let client else { throw APIError.tenantRequired }
            return try await client.send(OwnerAPI.fleetMap())
        }
    }
}

/// The Map / List switch over "My machines" (same look as the Owner app's Fleet screen).
struct MapListSwitch: View {
    @Binding var showMap: Bool

    var body: some View {
        Picker("View", selection: $showMap) {
            Text(FleetMapRules.map).tag(true)
            Text(FleetMapRules.list).tag(false)
        }
        .pickerStyle(.segmented)
    }
}

/// Map of the machines the server lets this supervisor see. Online only: offline it says so and the List keeps working
/// from the phone's data. Tapping a marker opens a small status card.
struct MachinesMapView: View {
    let model: FieldModel
    @State private var state: FleetMapRules.State = .loading
    @State private var retry = 0
    @State private var selected: MachineMapDTO?

    private struct LoadKey: Equatable { let online: Bool; let retry: Int }

    var body: some View {
        content
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .task(id: LoadKey(online: model.isOnline, retry: retry)) {
                if model.isOnline { state = .loading }
                state = await model.loadMachineMap()
            }
            .sheet(item: $selected) { machine in
                if case let .loaded(_, fetchedAt) = state {
                    MachineStatusCard(status: FleetMapRules.status(machine, fetchedAt: fetchedAt))
                        .presentationDetents([.height(170)])
                }
            }
    }

    @ViewBuilder private var content: some View {
        switch state {
        case .offline:
            ContentUnavailableView(FleetMapRules.map, systemImage: "wifi.slash", description: Text(FleetMapRules.offline))
        case .loading:
            ProgressView(FleetMapRules.loading)
        case let .failed(message):
            ContentUnavailableView {
                Label(FleetMapRules.map, systemImage: "exclamationmark.icloud")
            } description: {
                Text(message)
            } actions: {
                Button(FleetMapRules.tryAgain) { retry += 1 }.buttonStyle(.borderedProminent)
            }
        case let .loaded(machines, _):
            if machines.isEmpty {
                ContentUnavailableView(FleetMapRules.map, systemImage: "map", description: Text(FleetMapRules.empty))
            } else {
                FleetMapView(machines: machines, dataIsCached: false, markerHint: "Shows the machine's status") { id in
                    selected = machines.first { $0.id == id }
                }
            }
        }
    }
}

/// Asset code and name, connectivity, last seen and reported work status of a tapped marker.
struct MachineStatusCard: View {
    let status: FleetMapRules.Status

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(status.title).font(.headline)
                Spacer()
                Pill(text: status.connectivity, color: status.tone.color)
            }
            Text(status.lastSeen).font(.subheadline).foregroundStyle(.secondary)
            Text(status.reported).font(.subheadline).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding()
        .accessibilityElement(children: .combine)
    }
}
#endif
