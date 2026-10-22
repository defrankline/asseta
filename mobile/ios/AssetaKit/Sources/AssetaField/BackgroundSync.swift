#if os(iOS)
import BackgroundTasks
import Foundation

/// Opportunistic background refresh via `BGAppRefreshTask`. iOS decides if and when it runs (often
/// rarely, never after the user force-quits the app), so this is a bonus, not a guarantee: the
/// app syncs reliably when foregrounded and when connectivity returns. There is no background
/// location and no promise of continuous sync.
public enum BackgroundSync {
    public static let identifier = "com.asseta.supervisor.sync"

    /// The live field model registers its sync here; nil when no tenant session is open.
    @MainActor static var runner: (@MainActor () async -> Void)?

    /// Call once from the app's `init` (before launch completes), as `BGTaskScheduler` requires.
    public static func register() {
        BGTaskScheduler.shared.register(forTaskWithIdentifier: identifier, using: .main) { task in
            // Delivered on the main queue (`using: .main`).
            nonisolated(unsafe) let task = task
            MainActor.assumeIsolated { handle(task) }
        }
    }

    public static func schedule(after seconds: TimeInterval = 15 * 60) {
        let request = BGAppRefreshTaskRequest(identifier: identifier)
        request.earliestBeginDate = Date(timeIntervalSinceNow: seconds)
        try? BGTaskScheduler.shared.submit(request)
    }

    @MainActor private static func handle(_ task: BGTask) {
        schedule()
        nonisolated(unsafe) let task = task
        let work = Task { @MainActor in
            await runner?()
            task.setTaskCompleted(success: true)
        }
        task.expirationHandler = { work.cancel() }
    }
}
#endif
