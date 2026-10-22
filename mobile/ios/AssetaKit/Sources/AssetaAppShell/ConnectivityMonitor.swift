import Foundation
import Network

/// Reports connectivity changes (NWPathMonitor) on the main actor. Shared by both apps: the
/// Supervisor app syncs on reconnect, the Owner app switches between live and cached data.
@MainActor
public final class ConnectivityMonitor {
    private let monitor = NWPathMonitor()
    public private(set) var isOnline = true

    public init() {}

    public func start(onChange: @escaping @MainActor (Bool) -> Void) {
        monitor.pathUpdateHandler = { path in
            let online = path.status == .satisfied
            Task { @MainActor [weak self] in
                guard let self, self.isOnline != online else { return }
                self.isOnline = online
                onChange(online)
            }
        }
        monitor.start(queue: DispatchQueue(label: "asseta.connectivity"))
    }

    public func stop() { monitor.cancel() }
}
