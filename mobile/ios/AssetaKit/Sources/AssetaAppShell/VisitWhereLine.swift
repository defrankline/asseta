import AssetaModel
import SwiftUI

/// "Where: Mbezi Beach, Kinondoni (at Yard A) · -6.7924, 39.2083 (±5 m)" (ADR-008, Supervisor and Owner): tapping it
/// opens Apple Maps at the coordinates; nothing without coordinates.
public struct VisitWhereLine: View {
    let visit: VisitPoint?
    let identifier: String
    @Environment(\.openURL) private var openURL

    public init(visit: VisitPoint?, identifier: String = "visit.where") {
        self.visit = visit
        self.identifier = identifier
    }

    public var body: some View {
        if let line = VisitTexts.whereLine(visit) {
            Button { if let url = VisitTexts.mapsURL(visit) { openURL(url) } } label: {
                Text(line).font(.system(size: 13)).foregroundStyle(Shell.accent)
                    .multilineTextAlignment(.leading)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier(identifier)
        }
    }
}

/// "Last visit: 17 Nov, 15:26 · Where: …" (the previous visit of a report); tapping opens Apple Maps when the visit has
/// coordinates. Nothing for a first visit.
public struct LastVisitLine: View {
    let visit: VisitPoint?
    let identifier: String
    @Environment(\.openURL) private var openURL

    public init(visit: VisitPoint?, identifier: String = "visit.last") {
        self.visit = visit
        self.identifier = identifier
    }

    public var body: some View {
        if let line = VisitTexts.lastVisitLine(visit) {
            if let url = VisitTexts.mapsURL(visit) {
                Button { openURL(url) } label: {
                    Text(line).font(.system(size: 13)).foregroundStyle(Shell.accent).multilineTextAlignment(.leading)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier(identifier)
            } else {
                Text(line).font(.system(size: 13)).foregroundStyle(Shell.muted)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .accessibilityIdentifier(identifier)
            }
        }
    }
}
