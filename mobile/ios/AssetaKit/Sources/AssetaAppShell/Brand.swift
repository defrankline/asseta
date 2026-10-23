import SwiftUI

/// Asseta brand palette (see `branding/README.md`).
public enum Brand {
    public static let slate = Color(red: 0x0F / 255, green: 0x2A / 255, blue: 0x3D / 255)
    public static let amber = Color(red: 0xF5 / 255, green: 0xA3 / 255, blue: 0x00 / 255)
    public static let offWhite = Color(red: 0xF7 / 255, green: 0xF8 / 255, blue: 0xFA / 255)
}

/// Which app is hosting the shared shell. Only presentation differs; rules live in AssetaKit
/// and on the server.
public struct AppFlavor: Sendable, Equatable {
    public let appName: String
    public let tagline: String
    /// Product name under the "Asseta" wordmark on the sign-in screen (as Android's `AppRole` label).
    public let role: String

    public init(appName: String, tagline: String, role: String) {
        self.appName = appName
        self.tagline = tagline
        self.role = role
    }

    public static let supervisor = AppFlavor(appName: "Asseta Supervisor", tagline: "Field jobs, meters and evidence",
                                             role: "Supervisor")
    public static let owner = AppFlavor(appName: "Asseta Owner", tagline: "Your fleet at a glance", role: "Owner")
}
