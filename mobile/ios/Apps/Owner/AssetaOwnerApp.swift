import AssetaAppShell
import AssetaOwnerUI
import SwiftUI

@main
struct AssetaOwnerApp: App {
    // APNs callbacks and notification taps (registration itself is gated by AssetaPushEnabled).
    @UIApplicationDelegateAdaptor(OwnerAppDelegate.self) private var appDelegate

    var body: some Scene {
        WindowGroup {
            AssetaAppScene(flavor: .owner, home: OwnerApp.home, configure: OwnerApp.configure)
        }
    }
}
