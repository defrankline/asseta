#if os(iOS)
import AssetaModel
import AssetaOwnerKit
import Foundation
import Observation
import UIKit
import UserNotifications

/// APNs registration and notification taps for the Owner app.
///
/// Push is behind a capability check: unless the build sets `AssetaPushEnabled` (and carries the
/// `aps-environment` entitlement from a provisioning profile), the app never asks for notification
/// permission or registers with APNs; in-app notifications and the realtime feed still work.
@MainActor
@Observable
public final class PushCenter {
    public static let shared = PushCenter()

    public let isEnabled = PushRegistration.isEnabled(info: Bundle.main.infoDictionary ?? [:])
    private(set) var deviceToken: Data?
    private(set) var statusText: String
    private(set) var registeredDeviceID: UUID?
    /// A notification tap waiting for the matching tenant's home screen.
    var pendingLink: DeepLink?

    private weak var model: OwnerModel?
    private var lastRegistered: (Data, UUID)?

    private init() {
        statusText = isEnabled ? "Not registered yet" : "Push is not enabled in this build"
    }

    /// The open tenant's model; registers this device for it once a token exists.
    func attach(_ model: OwnerModel) {
        self.model = model
        guard isEnabled else { return }
        Task {
            let center = UNUserNotificationCenter.current()
            let granted = (try? await center.requestAuthorization(options: [.alert, .badge, .sound])) ?? false
            guard granted else {
                statusText = "Notifications are turned off for Asseta Owner in iOS Settings"
                return
            }
            UIApplication.shared.registerForRemoteNotifications()
            await registerIfNeeded()
        }
    }

    func didRegister(token: Data) {
        deviceToken = token
        Task { await registerIfNeeded() }
    }

    func didFail(_ error: any Error) {
        statusText = "APNs registration failed: \(error.localizedDescription)"
    }

    private func registerIfNeeded() async {
        guard let token = deviceToken, let model, let repository = model.repository else { return }
        guard PushRegistration.needsRegistration(token: token, tenantID: model.tenant.tenantID,
                                                 lastRegistered: lastRegistered),
              let body = PushRegistration.request(token: token, appVersion: OwnerModel.appVersion,
                                                  deviceLabel: UIDevice.current.name) else { return }
        do {
            let device = try await repository.send(try OwnerAPI.registerPushDevice(body, idempotencyKey: UUID()))
            lastRegistered = (token, model.tenant.tenantID)
            registeredDeviceID = device.id
            statusText = "Registered for \(model.tenant.name)"
        } catch {
            statusText = "Couldn't register for push: \(DecisionErrorText.message(for: error))"
        }
    }

    /// Best-effort deactivation before sign-out so a signed-out phone stops receiving pushes.
    func unregister() async {
        defer {
            registeredDeviceID = nil
            lastRegistered = nil
            model = nil
        }
        guard let id = registeredDeviceID, let repository = model?.repository,
              let request = try? OwnerAPI.deactivatePushDevice(id, idempotencyKey: UUID()) else { return }
        _ = try? await repository.send(request)
    }

    func handleTap(userInfo: [AnyHashable: Any]) {
        if let link = DeepLinkParser.parse(pushPayload: userInfo) { pendingLink = link }
    }
}

/// `UIApplicationDelegate` for the Owner app (`@UIApplicationDelegateAdaptor`): APNs callbacks
/// and notification presentation/taps.
public final class OwnerAppDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate {
    public func application(_ application: UIApplication,
                            didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil)
        -> Bool {
        UNUserNotificationCenter.current().delegate = self
        return true
    }

    public func application(_ application: UIApplication, didRegisterForRemoteNotificationsWithDeviceToken token: Data) {
        MainActor.assumeIsolated { PushCenter.shared.didRegister(token: token) }
    }

    public func application(_ application: UIApplication, didFailToRegisterForRemoteNotificationsWithError error: any Error) {
        MainActor.assumeIsolated { PushCenter.shared.didFail(error) }
    }

    /// Foreground: show the banner (the inbox also updates live over the WebSocket).
    public nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter,
                                                   willPresent notification: UNNotification)
        async -> UNNotificationPresentationOptions {
        [.banner, .list, .sound]
    }

    public nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter,
                                                   didReceive response: UNNotificationResponse) async {
        let info = response.notification.request.content.userInfo
        nonisolated(unsafe) let payload = info
        await MainActor.run { PushCenter.shared.handleTap(userInfo: payload) }
    }
}
#endif
