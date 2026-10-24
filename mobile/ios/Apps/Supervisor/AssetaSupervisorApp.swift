import AssetaAppShell
import AssetaField
import SwiftUI

@main
struct AssetaSupervisorApp: App {
    // APNs callbacks and notification taps (registration itself is gated by AssetaPushEnabled).
    @UIApplicationDelegateAdaptor(SupervisorAppDelegate.self) private var appDelegate

    init() {
        // BGTaskScheduler requires registration before launch completes.
        BackgroundSync.register()
    }

    var body: some Scene {
        WindowGroup {
            AssetaAppScene(flavor: .supervisor, home: FieldRootView.home, configure: SupervisorPush.configure)
        }
    }
}
