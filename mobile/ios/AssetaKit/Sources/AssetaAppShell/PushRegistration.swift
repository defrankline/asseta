import AssetaModel
import AssetaNetwork
import Foundation

/// APNs registration rules shared by the Owner and Supervisor apps (no UIKit here so it is testable on macOS).
public enum PushRegistration {
    /// The app a device registers for (`PushDeviceIn.app`); the server routes pushes per app.
    public enum App: String, Sendable {
        case owner = "OWNER"
        case supervisor = "SUPERVISOR"
    }

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

    /// The `/me/push-devices` body for this installation (platform IOS).
    public static func request(token: Data, app: App, appVersion: String?, deviceLabel: String?) -> PushDeviceIn? {
        guard !token.isEmpty else { return nil }
        return PushDeviceIn(platform: "IOS", app: app.rawValue, token: hexToken(token), appVersion: appVersion,
                            deviceLabel: deviceLabel.flatMap { $0.isEmpty ? nil : String($0.prefix(80)) })
    }

    /// Whether a (token, tenant) pair still needs to be sent. The server binds a device to the
    /// tenant it was registered under, so a company switch re-registers; the same pair is sent once
    /// per app launch at most.
    public static func needsRegistration(token: Data, tenantID: UUID, lastRegistered: (Data, UUID)?) -> Bool {
        guard let lastRegistered else { return true }
        return lastRegistered.0 != token || lastRegistered.1 != tenantID
    }

    /// `POST /me/push-devices` (send with the tenant client so the device is bound to the open company).
    public static func register(_ body: PushDeviceIn, idempotencyKey: UUID) throws -> APIRequest<PushDeviceDTO> {
        try .mutation(.post, "/api/v1/me/push-devices", body: body, idempotencyKey: idempotencyKey)
    }

    /// `DELETE /me/push-devices/{id}`: this phone stops receiving pushes.
    public static func deactivate(_ id: UUID, idempotencyKey: UUID) throws -> APIRequest<PushDeviceDTO> {
        try .mutation(.delete, "/api/v1/me/push-devices/\(id.uuidString.lowercased())", body: EmptyPushBody(),
                      idempotencyKey: idempotencyKey)
    }

    /// The `notification_id` of a push payload (APNs: top-level next to `aps`), if any.
    public static func notificationID(pushPayload info: [AnyHashable: Any]) -> UUID? {
        (info["notification_id"] as? String).flatMap(UUID.init(uuidString:))
    }

    struct EmptyPushBody: Encodable {}
}

/// "Notifications on this phone" in the Supervisor account menu. Same wording as Android.
public enum PushStatus: Equatable, Sendable {
    case on, off, unavailable, notRegistered

    /// The OS notification permission, as far as the status row cares.
    public enum Permission: Sendable { case allowed, denied, notAsked }

    public static let title = "Notifications on this phone"
    public static let turnOn = "Turn on"

    /// A build without push → unavailable; permission denied → off; registered → on; else not registered yet.
    public static func of(buildEnabled: Bool, permission: Permission, registered: Bool) -> PushStatus {
        guard buildEnabled else { return .unavailable }
        if permission == .denied { return .off }
        return registered ? .on : .notRegistered
    }

    public var text: String {
        switch self {
        case .on: "On"
        case .off: "Off — allow notifications in Settings"
        case .unavailable: "Not available on this build"
        case .notRegistered: "Not registered yet"
        }
    }

    /// Only "Not registered yet" offers "Turn on" (asks for permission, then registers).
    public var canTurnOn: Bool { self == .notRegistered }
}
