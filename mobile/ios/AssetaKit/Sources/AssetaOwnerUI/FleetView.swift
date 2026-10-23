#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaOwnerKit
import MapKit
import SwiftUI

/// Fleet map (MapKit) and list of last-known machine positions, styled by connectivity.
struct FleetView: View {
    enum Mode: String, CaseIterable { case map = "Map", list = "List" }

    let model: OwnerModel
    @State private var loader = Loader<[MachineMapDTO]>()
    @State private var mode: Mode = .map
    @State private var search = ""
    @State private var tone: MarkerTone?
    @State private var selected: UUID?
    @State private var camera: MapCameraPosition = .automatic

    var body: some View {
        VStack(spacing: 0) {
            Picker("View", selection: $mode) {
                ForEach(Mode.allCases, id: \.self) { Text($0.rawValue) }
            }
            .pickerStyle(.segmented)
            .padding([.horizontal, .top])
            .padding(.bottom, 8)
            filters
            if loader.isFromCache {
                StaleBanner(fetchedAt: loader.snapshot?.fetchedAt, isOnline: model.isOnline).padding(.horizontal)
            }
            content
        }
        .navigationTitle("Fleet")
        .navigationBarTitleDisplayMode(.inline)
        .searchable(text: $search, prompt: "Search machine, code, operator")
        .refreshable { await reload() }
        .task(id: model.changeTick) { await reload() }
        .navigationDestination(item: $selected) { MachineDetailView(model: model, machineID: $0) }
    }

    private func reload() async { await loader.load(model, .fleetMap, OwnerAPI.fleetMap()) }

    private var machines: [MachineMapDTO] {
        FleetPresentation.filter(FleetPresentation.sorted(loader.value ?? []), query: search, tone: tone,
                                 dataIsCached: loader.isFromCache)
    }

    /// Live / Recent / Stale / Offline chips and the "N of M machines" count, as in the Android Owner app.
    private var filters: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 6) {
                ForEach(FleetPresentation.filterTones, id: \.self) { t in
                    let on = tone == t
                    Button(t.rawValue.capitalized) { tone = on ? nil : t }
                        .font(.footnote)
                        .buttonStyle(.bordered)
                        .tint(on ? Brand.amber : .secondary)
                        .accessibilityAddTraits(on ? .isSelected : [])
                }
            }
            if let all = loader.value {
                Text("\(machines.count) of \(all.count) machines").font(.caption).foregroundStyle(.secondary)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal)
        .padding(.bottom, 8)
    }

    @ViewBuilder private var content: some View {
        if loader.value == nil, let error = loader.error {
            LoadFailure(message: error) { await reload() }
        } else if loader.value == nil {
            ProgressView("Loading fleet…").frame(maxHeight: .infinity)
        } else if mode == .map {
            map
        } else {
            list
        }
    }

    private var map: some View {
        let placed = machines.filter(\.hasPosition)
        return Map(position: $camera) {
            ForEach(placed) { machine in
                let style = FleetPresentation.style(for: machine, dataIsCached: loader.isFromCache)
                Annotation(machine.assetCode, coordinate: CLLocationCoordinate2D(latitude: machine.latitude ?? 0,
                                                                                 longitude: machine.longitude ?? 0)) {
                    Button { selected = machine.id } label: { MachineMarker(style: style, alerts: machine.openAlerts) }
                        .accessibilityLabel(style.accessibilityLabel)
                        .accessibilityHint("Opens machine details")
                }
            }
        }
        .mapControls { MapCompass(); MapScaleView() } // no user location: the Owner app never asks for it
        .overlay(alignment: .bottom) {
            if let note = FleetPresentation.unplacedNote(machines.count - placed.count) {
                Text(note)
                    .font(.caption).padding(8)
                    .background(.regularMaterial, in: Capsule()).padding(.bottom, 8)
            }
        }
    }

    private var list: some View {
        List(machines) { machine in
            Button { selected = machine.id } label: {
                MachineRow(machine: machine, dataIsCached: loader.isFromCache)
            }
            .foregroundStyle(.primary)
        }
        .listStyle(.plain)
        .overlay {
            if machines.isEmpty {
                EmptyState(title: FleetPresentation.emptyTitle, message: FleetPresentation.emptyMessage, systemImage: "magnifyingglass")
            }
        }
    }
}

struct MachineMarker: View {
    let style: MachineMarkerStyle
    let alerts: Int

    var body: some View {
        ZStack(alignment: .topTrailing) {
            Image(systemName: "truck.box.fill")
                .font(.system(size: 14, weight: .bold))
                .foregroundStyle(.white)
                .padding(8)
                .background(style.tone.color, in: Circle())
                .overlay(Circle().strokeBorder(.white, lineWidth: 2))
                // Live markers are solid; anything else is dashed so colour is not the only cue.
                .overlay(Circle().strokeBorder(style: StrokeStyle(lineWidth: style.claimsLive ? 0 : 2, dash: [3, 3]))
                    .foregroundStyle(Brand.slate.opacity(0.6)))
            if alerts > 0 {
                Text("\(alerts)").font(.caption2.bold()).foregroundStyle(.white)
                    .padding(4).background(.red, in: Circle()).offset(x: 6, y: -6)
            }
        }
        .frame(minWidth: 44, minHeight: 44)
    }
}

struct MachineRow: View {
    let machine: MachineMapDTO
    let dataIsCached: Bool

    /// Same lines as the Android fleet list: title + status pill, last seen and tracker state, reported work and
    /// operator, supervisor, open alerts.
    var body: some View {
        let style = FleetPresentation.style(for: machine, dataIsCached: dataIsCached)
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: style.systemImage).foregroundStyle(style.tone.color).frame(width: 28)
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 2) {
                HStack {
                    Text(FleetPresentation.title(machine)).font(.headline)
                    Spacer()
                    Pill(text: FleetPresentation.statusLabel(machine, dataIsCached: dataIsCached), color: style.tone.color)
                }
                Text(FleetPresentation.detailLine(machine, dataIsCached: dataIsCached)).font(.caption).foregroundStyle(.secondary)
                Text(FleetPresentation.reportedLine(machine)).font(.caption).foregroundStyle(.secondary)
                if let supervisor = machine.supervisor {
                    Text("Supervisor: \(supervisor)").font(.caption).foregroundStyle(.secondary)
                }
                if machine.openAlerts > 0 {
                    Text(FleetPresentation.alertsLine(machine.openAlerts)).font(.caption).foregroundStyle(.red)
                }
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(style.accessibilityLabel)
    }
}
#endif
