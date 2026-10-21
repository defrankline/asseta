import AssetaAppShell
import AssetaField
import SwiftUI

@main
struct AssetaSupervisorApp: App {
    init() {
        // BGTaskScheduler requires registration before launch completes.
        BackgroundSync.register()
    }

    var body: some Scene {
        WindowGroup {
            AssetaAppScene(flavor: .supervisor, home: FieldRootView.home)
        }
    }
}
