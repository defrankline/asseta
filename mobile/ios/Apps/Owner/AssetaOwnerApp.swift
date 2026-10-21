import AssetaAppShell
import SwiftUI

@main
struct AssetaOwnerApp: App {
    var body: some Scene {
        WindowGroup {
            AssetaAppScene(flavor: .owner)
        }
    }
}
