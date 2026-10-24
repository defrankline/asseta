import AssetaAppShell
import AssetaModel
import Foundation
import Testing

/// Push registration shared by the Owner and Supervisor apps, and the Supervisor's status row
/// (same wording as Android).
struct PushRegistrationTests {
    @Test func capabilityFlagGatesRegistration() {
        #expect(!PushRegistration.isEnabled(info: [:]))
        #expect(!PushRegistration.isEnabled(info: [PushRegistration.infoKey: "NO"]))
        #expect(!PushRegistration.isEnabled(info: [PushRegistration.infoKey: ""]))
        #expect(PushRegistration.isEnabled(info: [PushRegistration.infoKey: "YES"]))
        #expect(PushRegistration.isEnabled(info: [PushRegistration.infoKey: true]))
    }

    @Test func tokenIsHexAndBodyIsIOSOwner() throws {
        let token = Data([0x00, 0xAB, 0x10, 0xFF])
        #expect(PushRegistration.hexToken(token) == "00ab10ff")
        let body = try #require(PushRegistration.request(token: token, app: .owner, appVersion: "0.1.0 (1)", deviceLabel: ""))
        #expect(body.platform == "IOS" && body.app == "OWNER" && body.token == "00ab10ff" && body.deviceLabel == nil)
        #expect(PushRegistration.request(token: Data(), app: .owner, appVersion: nil, deviceLabel: nil) == nil)
    }

    @Test func supervisorRegistersAsIOSSupervisor() throws {
        let body = try #require(PushRegistration.request(token: Data([1]), app: .supervisor, appVersion: nil, deviceLabel: "Phone"))
        #expect(body.platform == "IOS" && body.app == "SUPERVISOR" && body.token == "01" && body.deviceLabel == "Phone")
    }

    @Test func reRegistersOnlyForANewTokenOrCompany() {
        let token = Data([1, 2]), a = UUID(), b = UUID()
        #expect(PushRegistration.needsRegistration(token: token, tenantID: a, lastRegistered: nil))
        #expect(!PushRegistration.needsRegistration(token: token, tenantID: a, lastRegistered: (token, a)))
        #expect(PushRegistration.needsRegistration(token: token, tenantID: b, lastRegistered: (token, a)))
        #expect(PushRegistration.needsRegistration(token: Data([3]), tenantID: a, lastRegistered: (token, a)))
    }

    @Test func tapPayloadCarriesTheNotificationID() {
        let id = UUID()
        #expect(PushRegistration.notificationID(pushPayload: ["notification_id": id.uuidString.lowercased(), "link": ""]) == id)
        #expect(PushRegistration.notificationID(pushPayload: ["notification_id": "nope"]) == nil)
        #expect(PushRegistration.notificationID(pushPayload: [:]) == nil)
    }

    @Test func statusRowWording() {
        #expect(PushStatus.title == "Notifications on this phone")
        #expect(PushStatus.of(buildEnabled: false, permission: .allowed, registered: true).text == "Not available on this build")
        #expect(PushStatus.of(buildEnabled: true, permission: .denied, registered: true).text
            == "Off — allow notifications in Settings")
        #expect(PushStatus.of(buildEnabled: true, permission: .allowed, registered: true).text == "On")
        let notYet = PushStatus.of(buildEnabled: true, permission: .notAsked, registered: false)
        #expect(notYet.text == "Not registered yet" && notYet.canTurnOn && PushStatus.turnOn == "Turn on")
        #expect(PushStatus.of(buildEnabled: true, permission: .allowed, registered: false) == .notRegistered)
        #expect(!PushStatus.on.canTurnOn && !PushStatus.off.canTurnOn && !PushStatus.unavailable.canTurnOn)
    }
}
