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
    /// Role shown under the brand name on the sign-in screen ("Supervisor", "Owner").
    public let roleName: String
    public let tagline: String

    public init(appName: String, roleName: String, tagline: String) {
        self.appName = appName
        self.roleName = roleName
        self.tagline = tagline
    }

    public static let supervisor = AppFlavor(appName: "Asseta Supervisor", roleName: "Supervisor",
                                             tagline: "Field jobs, meters and evidence")
    public static let owner = AppFlavor(appName: "Asseta Owner", roleName: "Owner", tagline: "Your fleet at a glance")
}
