import AssetaModel
import Foundation

/// Visual tone of a machine marker; the UI maps tones to brand colours.
public enum MarkerTone: String, Equatable, Sendable {
    case live, recent, stale, offline, unknown
}

/// How a machine is drawn and announced on the fleet map and lists.
public struct MachineMarkerStyle: Equatable, Sendable {
    public let tone: MarkerTone
    /// Short status label ("Live", "Last seen 3 h ago", …).
    public let label: String
    public let systemImage: String
    /// True only when the server says the position is live *and* the data was just fetched.
    public let claimsLive: Bool
    public let accessibilityLabel: String
}

/// Connectivity → presentation. The app never calls a position "live" unless the server marked it
/// LIVE with `is_live` in a response fetched just now; cached (offline) data is at best "last known".
public enum FleetPresentation {
    public static func style(for machine: MachineMapDTO, dataIsCached: Bool, now: Date = Date()) -> MachineMarkerStyle {
        let seen = lastSeenText(machine, dataIsCached: dataIsCached, now: now)
        let claimsLive = !dataIsCached && machine.connectivity == .live && machine.isLive
        let (tone, label, image): (MarkerTone, String, String) = switch machine.connectivity {
        case .live where claimsLive: (.live, "Live", "dot.radiowaves.left.and.right")
        // Not live right now (or not verifiable offline): describe the age instead.
        case .live, .recent: (dataIsCached ? .stale : .recent, seen, "clock")
        case .stale: (.stale, seen, "clock.badge.exclamationmark")
        case .offline: (.offline, "Offline · \(seen.lowercasedFirst)", "wifi.slash")
        case .neverReported: (.unknown, "Never reported", "questionmark.circle")
        case .noTracker: (.unknown, "No tracker", "antenna.radiowaves.left.and.right.slash")
        default: (.unknown, machine.connectivity.humanized, "questionmark.circle")
        }
        var spoken = "\(machine.assetCode), \(machine.name). \(label)."
        if machine.openAlerts > 0 { spoken += " \(machine.openAlerts) open alert\(machine.openAlerts == 1 ? "" : "s")." }
        if !machine.hasPosition { spoken += " No position." }
        return MachineMarkerStyle(tone: tone, label: label, systemImage: image, claimsLive: claimsLive,
                                  accessibilityLabel: spoken)
    }

    /// "Last seen 5 min ago", computed from `last_message_at` (or position time) against `now`, so a
    /// cached snapshot keeps ageing instead of freezing at the age it had when fetched.
    public static func lastSeenText(_ machine: MachineMapDTO, dataIsCached: Bool, now: Date) -> String {
        if let seen = machine.lastMessageAt ?? machine.positionTime {
            return "Last seen \(OwnerFormat.age(since: seen, now: now))"
        }
        if let age = machine.lastSeenAgeSeconds, !dataIsCached {
            return "Last seen \(OwnerFormat.age(seconds: age))"
        }
        return "Never seen"
    }

    /// Machines sorted for lists: open alerts first, then most recently seen, then asset code.
    public static func sorted(_ machines: [MachineMapDTO]) -> [MachineMapDTO] {
        machines.sorted { a, b in
            if (a.openAlerts > 0) != (b.openAlerts > 0) { return a.openAlerts > 0 }
            let sa = a.lastMessageAt ?? .distantPast, sb = b.lastMessageAt ?? .distantPast
            if sa != sb { return sa > sb }
            return a.assetCode < b.assetCode
        }
    }
}

extension String {
    var lowercasedFirst: String { prefix(1).lowercased() + dropFirst() }
}
