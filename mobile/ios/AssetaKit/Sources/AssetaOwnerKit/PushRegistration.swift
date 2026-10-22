import AssetaModel
import Foundation

/// APNs registration rules of the Owner app (no UIKit here so it is testable on macOS).
public enum PushRegistration {
    /// Info.plist key (from the `ASSETA_PUSH_ENABLED` build setting). Push stays off unless the
    /// build has the `aps-environment` entitlement and sets this to YES.
    public static let infoKey = "AssetaPushEnabled"

    /// Capability check: only a build that declares push support asks for permission or registers.
    public static func isEnabled(info: [String: Any]) -> Bool {
        switch info[infoKey] {
        case let flag as Bool: flag
        case let text as String: ["yes", "true", "1"].contains(text.lowercased())
        case let number as NSNumber: number.boolValue
        default: false
        }
    }

    /// APNs device token bytes as the lowercase hex string providers expect.
    public static func hexToken(_ token: Data) -> String {
        token.map { String(format: "%02x", $0) }.joined()
    }

    /// The `/me/push-devices` body for this installation (platform IOS, app OWNER).
    public static func request(token: Data, appVersion: String?, deviceLabel: String?) -> PushDeviceIn? {
        guard !token.isEmpty else { return nil }
        return PushDeviceIn(platform: "IOS", app: "OWNER", token: hexToken(token), appVersion: appVersion,
                            deviceLabel: deviceLabel.flatMap { $0.isEmpty ? nil : String($0.prefix(80)) })
    }

    /// Whether a (token, tenant) pair still needs to be sent. The server binds a device to the
    /// tenant it was registered under, so a company switch re-registers; the same pair is sent once
    /// per app launch at most.
    public static func needsRegistration(token: Data, tenantID: UUID, lastRegistered: (Data, UUID)?) -> Bool {
        guard let lastRegistered else { return true }
        return lastRegistered.0 != token || lastRegistered.1 != tenantID
    }
}
