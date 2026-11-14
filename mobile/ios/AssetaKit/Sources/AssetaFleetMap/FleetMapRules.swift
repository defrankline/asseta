import AssetaModel
import AssetaNetwork
import AssetaOwnerKit
import Foundation

/// Rules of the machine map (`getFleetMap`) shared by the apps; same rules as Android `FleetMapRules`.
///
/// The server decides which machines a person sees (a supervisor gets their own machines unless the company setting
/// `TRACKING.field_fleet_scope` is `ALL`), so the app never filters the list itself. The map is online only.
public enum FleetMapRules {
    /// Permission behind the fleet map endpoints. Without it the Map / List switch is not shown at all.
    public static let permission = "tenant.fleet.read"

    public static func canShowMap(permissions: some Sequence<String>) -> Bool {
        permissions.contains(permission)
    }

    /// Machines drawn on the map (with a known position) and those without one (counted in `unplacedNote`).
    public static func split(_ machines: [MachineMapDTO]) -> (placed: [MachineMapDTO], unplaced: [MachineMapDTO]) {
        (machines.filter(\.hasPosition), machines.filter { !$0.hasPosition })
    }

    /// Shown over the map when machines have no known position.
    public static func unplacedNote(_ count: Int) -> String? { FleetPresentation.unplacedNote(count) }

    /// What the map pane shows.
    public enum State: Equatable, Sendable {
        /// No connection: the map is not loaded (the List keeps working from the phone's data).
        case offline
        case loading
        case failed(String)
        case loaded([MachineMapDTO], fetchedAt: Date)
    }

    /// Loads the map when `online`; offline it never calls the server. Errors become a plain message, never a crash.
    public static func load(isolation: isolated (any Actor)? = #isolation, online: Bool, now: () -> Date = Date.init,
                            fetch: () async throws -> [MachineMapDTO]) async -> State {
        guard online else { return .offline }
        do {
            return .loaded(try await fetch(), fetchedAt: now())
        } catch {
            return .failed(errorMessage(error))
        }
    }

    public static func errorMessage(_ error: any Error) -> String {
        guard let api = error as? APIError else { return failed }
        switch api.httpStatus {
        case 403: return forbidden
        case 404: return notFound
        default:
            if case .transport = api { return noConnection }
            return failed
        }
    }

    /// The card shown when a marker is tapped.
    public struct Status: Equatable, Sendable {
        public let title: String
        public let tone: MarkerTone
        public let connectivity: String
        public let lastSeen: String
        public let reported: String
    }

    /// Asset code and name, connectivity (never "Live" unless the server says so in a fresh response), when it was last
    /// seen and the reported work status.
    public static func status(_ m: MachineMapDTO, fetchedAt: Date, now: Date = Date()) -> Status {
        let style = FleetPresentation.style(for: m, dataIsCached: false, now: now)
        var tone = style.tone
        var label = FleetPresentation.statusLabel(m, dataIsCached: false, now: now)
        // Same as Android `Freshness`: a response older than two minutes no longer proves a live position.
        if tone == .live, now.timeIntervalSince(fetchedAt) > liveResponseMaxAge {
            tone = .recent
            label = "Recent"
        }
        return Status(title: FleetPresentation.title(m), tone: tone, connectivity: label,
                      lastSeen: FleetPresentation.lastSeenText(m, dataIsCached: false, now: now),
                      reported: "Reported: \(OwnerFormat.humanize(m.reportedWorkStatus))")
    }

    public static func mapDescription(placed: Int) -> String {
        "Map of your machines with \(placed == 1 ? "1 machine" : "\(placed) machines"). Use the List view for details."
    }

    static let liveResponseMaxAge: TimeInterval = 120

    public static let map = "Map"
    public static let list = "List"
    public static let offline = "The map needs a connection. Your machines are still listed under List."
    public static let loading = "Loading the map…"
    public static let empty = "No machines to show on the map."
    public static let forbidden = "You do not have access to the machine map in this company."
    public static let notFound = "The machine map is not available in this company."
    public static let noConnection = "Could not reach the server. Check your connection and try again."
    public static let failed = "Could not load the map. Try again."
    public static let tryAgain = "Try again"
}
