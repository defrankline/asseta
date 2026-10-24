@testable import AssetaOwnerKit
import AssetaModel
import AssetaNetwork
import Foundation
import Testing

struct MutationGuardTests {
    @Test func offlineAndCachedDataBlockEveryMutation() {
        #expect(MutationGuard.check(isOnline: false, showingCachedData: false, accessState: .full, permitted: true) == .offline)
        #expect(MutationGuard.check(isOnline: true, showingCachedData: true, accessState: .full, permitted: true)
            == .showingCachedData)
    }

    @Test func readOnlyTenantAndMissingPermissionBlock() {
        #expect(MutationGuard.check(isOnline: true, showingCachedData: false, accessState: .readOnly, permitted: true)
            == .readOnlyTenant)
        #expect(MutationGuard.check(isOnline: true, showingCachedData: false,
                                    accessState: TenantAccessState(rawValue: "FUTURE"), permitted: true) == .readOnlyTenant)
        #expect(MutationGuard.check(isOnline: true, showingCachedData: false, accessState: .full, permitted: false)
            == .notPermitted)
        #expect(MutationGuard.check(isOnline: true, showingCachedData: false, accessState: .full, permitted: true) == nil)
    }

    @Test func featuresFollowPermissionHints() {
        let viewer = OwnerFeatures(permissions: ["tenant.finance.read", "tenant.approval.read"])
        #expect(viewer.overview && !viewer.fleet && viewer.approvals && !viewer.decideApprovals && !viewer.manageAlerts)
        let owner = OwnerFeatures(permissions: ["tenant.fleet.read", "tenant.fleet.alert_manage", "tenant.approval.expense",
                                                "tenant.case.read", "tenant.notification.read", "tenant.meter.read"])
        #expect(owner.fleet && owner.manageAlerts && owner.decideApprovals && owner.cases && owner.meterEvidence)
        #expect(!OwnerFeatures(permissions: []).overview)
    }

    @Test func segregationOfDutiesIsExplained() {
        let sod = APIError.server(status: 422, body: ErrorBody(code: "SEGREGATION_OF_DUTIES",
                                                               message: "Submitters cannot approve", correlationID: "abc"))
        #expect(DecisionErrorText.message(for: sod).hasPrefix("Segregation of duties"))
        let other = APIError.server(status: 409, body: ErrorBody(code: "WHATEVER", message: "Nope", correlationID: "1234567890"))
        #expect(DecisionErrorText.message(for: other) == "Nope (ref 12345678)")
    }
}

struct DeepLinkTests {
    let id = UUID(uuidString: "12121212-0000-4000-8000-000000000001")!
    let tenant = UUID(uuidString: Samples.tenant)!

    @Test func notificationTargetsMapToScreens() throws {
        #expect(DeepLinkParser.route(entity: "alert", id: id.uuidString, path: "/tenant/alerts") == .alert(id))
        #expect(DeepLinkParser.route(entity: "approval", id: id.uuidString, path: nil) == .approval(id))
        #expect(DeepLinkParser.route(entity: "case", id: id.uuidString, path: nil) == .investigation(id))
        #expect(DeepLinkParser.route(entity: "job", id: id.uuidString, path: nil) == .job(id))
        #expect(DeepLinkParser.route(entity: "machine", id: id.uuidString, path: nil) == .machine(id))
        #expect(DeepLinkParser.route(entity: "subscription", id: nil, path: "/tenant/subscription") == nil)
        let note = try AssetaJSON.decoder().decode(NotificationDTO.self,
                                                   from: Data(Samples.notificationJSON(entity: "screen", id: nil, path: nil).utf8))
        #expect(DeepLinkParser.route(for: note) == .notifications)
    }

    @Test func consolePathsMapToScreens() {
        #expect(DeepLinkParser.route(path: "/tenant/cases/\(id.uuidString)") == .investigation(id))
        #expect(DeepLinkParser.route(path: "/tenant/jobs/\(id.uuidString)?tab=summary") == .job(id))
        #expect(DeepLinkParser.route(path: "/tenant/alerts") == .alerts)
        #expect(DeepLinkParser.route(path: "/tenant/approvals") == .approvals)
        #expect(DeepLinkParser.route(path: "/tenant/fleet/machines/\(id.uuidString)") == .machine(id))
        #expect(DeepLinkParser.route(path: "/platform/models/\(id.uuidString)") == nil)
        #expect(DeepLinkParser.route(path: "javascript:alert(1)") == nil)
    }

    @Test func pushWithRecordLinkOpensRecordInItsTenant() {
        let link = DeepLinkParser.parse(pushPayload: [
            "notification_id": UUID().uuidString, "tenant_id": tenant.uuidString,
            "link": "/tenant/cases/\(id.uuidString)", "aps": ["alert": "x"],
        ])
        #expect(link?.route == .investigation(id))
        #expect(link?.tenantID == tenant)
    }

    @Test func pushWithListLinkOpensTheNotificationToResolveItsTarget() {
        let notification = UUID()
        let link = DeepLinkParser.parse(pushPayload: [
            "notification_id": notification.uuidString, "tenant_id": tenant.uuidString, "link": "/tenant/alerts",
        ])
        #expect(link?.route == .notification(notification))
    }

    @Test func pushWithoutUsableFieldsIsIgnoredOrFallsBackToInbox() {
        #expect(DeepLinkParser.parse(pushPayload: ["aps": ["alert": "x"]]) == nil)
        #expect(DeepLinkParser.parse(pushPayload: ["link": "/tenant/alerts"])?.route == .alerts)
        #expect(DeepLinkParser.parse(pushPayload: ["tenant_id": tenant.uuidString, "link": ""])?.route == .notifications)
        #expect(DeepLinkParser.parse(pushPayload: ["notification_id": "not-a-uuid", "tenant_id": "x"]) == nil)
    }
}

struct RoutingMatrixTests {
    func matrix() throws -> RoutingMatrix {
        RoutingMatrix(try AssetaJSON.decoder().decode([NotificationRoutingDTO].self, from: Data(Samples.routing.utf8)))
    }

    @Test func categoriesInServerOrderAndMandatoryPushIsLocked() throws {
        let m = try matrix()
        #expect(m.categories == ["ACTION", "ANOMALY", "BILLING"])
        #expect(m.isPushLocked("ACTION", .critical))
        #expect(!m.isPushLocked("ACTION", .warning))
        #expect(m.isPushLocked("REMINDER", .info)) // missing cell: nothing to toggle
    }

    @Test func onlyChangedCellsAreSentAndLockedCellsRefuse() throws {
        let original = try matrix()
        var edited = original
        let locked = edited.setPush(false, category: "ACTION", severity: .critical)
        let a = edited.setPush(false, category: "ACTION", severity: .warning)
        let b = edited.setPush(true, category: "ANOMALY", severity: .info)
        let unchanged = edited.setPush(false, category: "BILLING", severity: .warning) // same value as before
        #expect(!locked && a && b && unchanged)
        let changes = edited.changes(from: original)
        #expect(changes == [
            NotificationRoutingChangeIn(category: "ACTION", severity: .warning, push: false, email: false),
            NotificationRoutingChangeIn(category: "ANOMALY", severity: .info, push: true, email: false),
        ])
    }
}

struct RealtimeTests {
    @Test func framesDecode() throws {
        func decode(_ text: String) throws -> RealtimeEvent { try RealtimeEvent.decode(Data(text.utf8)) }
        #expect(try decode(#"{"type":"auth_ok","payload":{"unread_count":3,"heartbeat_seconds":25}}"#)
            == .authOK(unreadCount: 3, heartbeatSeconds: 25))
        #expect(try decode(#"{"type":"unread_count","payload":{"count":7}}"#) == .unreadCount(7))
        #expect(try decode(#"{"type":"ping"}"#) == .ping)
        #expect(try decode(#"{"type":"reauth_required","payload":{"expires_at":1}}"#) == .reauthRequired)
        #expect(try decode(#"{"type":"auth_error","payload":{"code":"MANDATE_ENDED","message":"Ended"}}"#)
            == .authError(code: "MANDATE_ENDED", message: "Ended"))
        #expect(try decode(#"{"type":"entity.changed","payload":{"entity":"alert","id":"x","action":"updated"}}"#)
            == .entityChanged(EntityChangedDTO(entity: "alert", id: "x", action: "updated")))
        #expect(try decode(#"{"type":"something_new"}"#) == .other("something_new"))
        guard case let .notification(note) = try decode(#"{"type":"notification","payload":\#(Samples.notificationJSON())}"#)
        else { Issue.record("not a notification"); return }
        #expect(note.category == "ANOMALY")
    }

    @Test func socketURLProtocolsAndBackoff() {
        #expect(RealtimeClient.socketURL(baseURL: URL(string: "http://localhost:8000")!).absoluteString
            == "ws://localhost:8000/api/v1/ws")
        #expect(RealtimeClient.socketURL(baseURL: URL(string: "https://api.example.com/base")!).absoluteString
            == "wss://api.example.com/base/api/v1/ws")
        #expect(RealtimeClient.protocols(token: "jwt") == ["asseta.v1", "bearer.jwt"])
        #expect([0, 1, 2, 3, 10].map(RealtimeClient.backoff) == [1, 1, 2, 4, 60])
        #expect(RealtimeClient.isAccessDenied(code: "TENANT_ACCESS_BLOCKED"))
        #expect(!RealtimeClient.isAccessDenied(code: "TOKEN_EXPIRED"))
    }
}
