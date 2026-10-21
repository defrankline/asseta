import AssetaAppShell
import SwiftUI

@main
struct AssetaSupervisorApp: App {
    var body: some Scene {
        WindowGroup {
            AssetaAppScene(flavor: .supervisor)
        }
    }
}
