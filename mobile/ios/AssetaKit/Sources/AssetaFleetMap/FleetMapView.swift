#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaOwnerKit
import MapKit
import SwiftUI

/// Machine map (MapKit) shared by the Owner and Supervisor apps: one marker per machine with a known position, styled
/// by connectivity, and the "N machines have no known position (see List)" note. No user location: the map never asks
/// for it.
public struct FleetMapView: View {
    let machines: [MachineMapDTO]
    let dataIsCached: Bool
    let markerHint: String
    let onSelect: (UUID) -> Void
    @State private var camera: MapCameraPosition = .automatic

    public init(machines: [MachineMapDTO], dataIsCached: Bool, markerHint: String = "Opens machine details",
                onSelect: @escaping (UUID) -> Void) {
        self.machines = machines
        self.dataIsCached = dataIsCached
        self.markerHint = markerHint
        self.onSelect = onSelect
    }

    public var body: some View {
        let placed = machines.filter(\.hasPosition)
        return Map(position: $camera) {
            ForEach(placed) { machine in
                let style = FleetPresentation.style(for: machine, dataIsCached: dataIsCached)
                Annotation(machine.assetCode, coordinate: CLLocationCoordinate2D(latitude: machine.latitude ?? 0,
                                                                                 longitude: machine.longitude ?? 0)) {
                    Button { onSelect(machine.id) } label: { MachineMarker(style: style, alerts: machine.openAlerts) }
                        .accessibilityLabel(style.accessibilityLabel)
                        .accessibilityHint(markerHint)
                }
            }
        }
        .mapControls { MapCompass(); MapScaleView() }
        .overlay(alignment: .bottom) {
            if let note = FleetPresentation.unplacedNote(machines.count - placed.count) {
                Text(note)
                    .font(.caption).padding(8)
                    .background(.regularMaterial, in: Capsule()).padding(.bottom, 8)
            }
        }
    }
}

public struct MachineMarker: View {
    let style: MachineMarkerStyle
    let alerts: Int

    public init(style: MachineMarkerStyle, alerts: Int) {
        self.style = style
        self.alerts = alerts
    }

    public var body: some View {
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
                    .padding(4).background(Palette.offline, in: Circle()).offset(x: 6, y: -6)
            }
        }
        .frame(minWidth: 44, minHeight: 44)
    }
}

extension MarkerTone {
    public var color: Color {
        switch self {
        case .live: Palette.live
        case .recent: Palette.recent
        case .stale: Palette.stale
        case .offline: Palette.offline
        case .unknown: Palette.neutral
        }
    }
}
#endif
