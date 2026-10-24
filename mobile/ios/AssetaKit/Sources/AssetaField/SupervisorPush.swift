#if os(iOS)
import AssetaAppShell
import AssetaModel
import AssetaNetwork
import Foundation
import Observation
import UIKit
import UserNotifications

/// APNs registration and notification taps for the Supervisor app (same rules as the Owner `PushCenter`;
/// same behaviour as the Android Supervisor app).
///
/// Push is behind the same capability check as the Owner app: unless the build sets `AssetaPushEnabled`
/// (and carries the `aps-environment` entitlement), the app never asks for permission or registers. The
/// device registers as app SUPERVISOR for the open company once the field data is ready, only with
/// `tenant.notification.read`. Permission is asked the first time the Inbox tab appears after sign-in (or
/// from "Turn on" in the account menu); sign-out deactivates this device. Push never blocks sign-in or sync.
@MainActor
@Observable
public final class SupervisorPush {
    public static let shared = SupervisorPush()

    /// A notification tap waiting for the Inbox (a new value per tap).
    struct Tap: Equatable {
        let id = UUID()
        let notificationID: UUID?
    }

    let isEnabled = PushRegistration.isEnabled(info: Bundle.main.infoDictionary ?? [:])
    private(set) var permission: PushStatus.Permission = .notAsked
    private(set) var registeredDeviceID: UUID?
    var pendingTap: Tap?
    /// Counts pushes that arrived while the app was open (the Inbox refreshes on each).
    private(set) var arrivals = 0

    private var deviceToken: Data?
    private var client: APIClient?
    private var tenantID: UUID?
    private var lastRegistered: (Data, UUID)?
    private var askedSinceSignIn = false

    private init() {}

    var status: PushStatus { .of(buildEnabled: isEnabled, permission: permission, registered: registeredDeviceID != nil) }

    /// The open company's tenant client. If the user already allowed notifications, this device is
    /// (re-)registered for it; it never prompts.
    func attach(client: APIClient, tenantID: UUID, allowed: Bool) {
        guard allowed else { return }
        self.client = client
        self.tenantID = tenantID
        guard isEnabled else { return }
        Task { await registerIfAllowed() }
    }

    /// Back in the foreground: notifications may have been allowed or turned off in iOS Settings.
    func refresh() async {
        guard isEnabled, client != nil else { return }
        await registerIfAllowed()
    }

    /// The first time the Inbox tab appears after sign-in: asks for permission once (iOS never asks again
    /// after a refusal).
    func inboxShown() async {
        guard isEnabled, client != nil, !askedSinceSignIn else { return }
        askedSinceSignIn = true
        await readPermission()
        if permission == .notAsked { await turnOn() }
    }

    /// "Turn on" in the account menu: asks for permission, then registers this device.
    func turnOn() async {
        guard isEnabled, client != nil else { return }
        let granted = (try? await UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .badge, .sound])) ?? false
        await readPermission()
        guard granted else { return }
        UIApplication.shared.registerForRemoteNotifications()
        await registerIfNeeded()
    }

    func didRegister(token: Data) {
        deviceToken = token
        Task { await registerIfNeeded() }
    }

    /// Best-effort deactivation before sign-out so a signed-out phone stops receiving pushes.
    func unregister() async {
        defer {
            registeredDeviceID = nil
            lastRegistered = nil
            client = nil
            tenantID = nil
            askedSinceSignIn = false
        }
        guard let id = registeredDeviceID, let client,
              let request = try? PushRegistration.deactivate(id, idempotencyKey: UUID()) else { return }
        _ = try? await client.send(request)
    }

    func handleTap(userInfo: [AnyHashable: Any]) {
        pendingTap = Tap(notificationID: PushRegistration.notificationID(pushPayload: userInfo))
    }

    func didArrive() { arrivals += 1 }

    private func registerIfAllowed() async {
        await readPermission()
        guard permission == .allowed else { return }
        UIApplication.shared.registerForRemoteNotifications()
        await registerIfNeeded()
    }

    private func readPermission() async {
        switch await UNUserNotificationCenter.current().notificationSettings().authorizationStatus {
        case .authorized, .provisional, .ephemeral: permission = .allowed
        case .denied: permission = .denied
        default: permission = .notAsked
        }
    }

    private func registerIfNeeded() async {
        guard let token = deviceToken, let client, let tenantID else { return }
        guard PushRegistration.needsRegistration(token: token, tenantID: tenantID, lastRegistered: lastRegistered),
              let body = PushRegistration.request(token: token, app: .supervisor, appVersion: FieldServices.appVersion,
                                                  deviceLabel: UIDevice.current.name),
              let request = try? PushRegistration.register(body, idempotencyKey: UUID()) else { return }
        // Offline or refused: stays "Not registered yet" and is retried on the next foreground or "Turn on".
        guard let device = try? await client.send(request) else { return }
        lastRegistered = (token, tenantID)
        registeredDeviceID = device.id
    }

    /// Sign-out (user, `/me` 401, revocation) deactivates this device before the tokens are wiped.
    public static func configure(_ session: SessionModel) {
        session.onSignOut = { await SupervisorPush.shared.unregister() }
    }
}

/// `UIApplicationDelegate` for the Supervisor app (`@UIApplicationDelegateAdaptor`): APNs callbacks and
/// notification presentation/taps.
public final class SupervisorAppDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate {
    public func application(_ application: UIApplication,
                            didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil)
        -> Bool {
        UNUserNotificationCenter.current().delegate = self
        return true
    }

    public func application(_ application: UIApplication, didRegisterForRemoteNotificationsWithDeviceToken token: Data) {
        MainActor.assumeIsolated { SupervisorPush.shared.didRegister(token: token) }
    }

    public func application(_ application: UIApplication, didFailToRegisterForRemoteNotificationsWithError error: any Error) {}

    /// Foreground: show the banner (as the Owner app does) and refresh the Inbox list.
    public nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter,
                                                   willPresent notification: UNNotification)
        async -> UNNotificationPresentationOptions {
        await MainActor.run { SupervisorPush.shared.didArrive() }
        return [.banner, .list, .sound]
    }

    /// Tap: opens the Inbox tab (and that notification when the Inbox has it).
    public nonisolated func userNotificationCenter(_ center: UNUserNotificationCenter,
                                                   didReceive response: UNNotificationResponse) async {
        let info = response.notification.request.content.userInfo
        nonisolated(unsafe) let payload = info
        await MainActor.run { SupervisorPush.shared.handleTap(userInfo: payload) }
    }
}
#endif
