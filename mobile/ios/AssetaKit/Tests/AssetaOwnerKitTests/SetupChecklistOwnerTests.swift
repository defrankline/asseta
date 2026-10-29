@testable import AssetaOwnerKit
import AssetaModel
import AssetaNetwork
import Foundation
import Testing

/// Go-live checklist on the Owner side (strings doc "Go-live checklist"): contract decoding, /me banner figures,
/// requests, step actions (app screen or web), manage buttons, wording and the deep link.
struct SetupChecklistOwnerTests {
    static let user = "11111111-0000-4000-8000-000000000001"

    static func step(_ key: String, order: Int, status: String, link: String, canSkip: Bool = true,
                     done: String = "null", total: String = "null", notNeeded: String = "null", checks: String = "[]") -> String {
        """
        {"key":"\(key)","order":\(order),"title":"Title \(order)","description":"Do it","status":"\(status)",
         "done_count":\(done),"total_count":\(total),"link":"\(link)","required_permission":"tenant.machine.write",
         "can_mark_not_needed":\(canSkip),"not_needed":\(notNeeded),"checks":\(checks)}
        """
    }

    static let checklist = """
    {"steps":[
      \(step("MACHINES", order: 4, status: "TODO", link: "/tenant/machines", done: "2", total: "5",
             checks: #"[{"key":"registered","label":"Machines registered","done":true,"optional":false,"done_count":5,"total_count":5,"link":"/tenant/machines","required_permission":"tenant.machine.write"},{"key":"trackers","label":"Trackers fitted","done":false,"optional":true,"done_count":null,"total_count":null,"link":"/tenant/machines?missing=tracker","required_permission":"tenant.machine.write"}]"#)),
      \(step("COMPANY_SETTINGS", order: 1, status: "DONE", link: "/tenant/subscription", canSkip: false)),
      \(step("TRACKERS", order: 5, status: "NOT_NEEDED", link: "/tenant/trackers",
             notNeeded: #"{"reason":"No trackers yet","marked_by":"\#(user)","marked_by_name":"Asha","marked_at":"2026-10-26T10:00:00Z"}"#)),
      \(step("CONTROLS_CHOSEN", order: 8, status: "TODO", link: "/tenant/policies")),
      \(step("DEPOSIT_ACCOUNTS", order: 10, status: "NOT_APPLICABLE", link: "/tenant/finance/deposit-accounts")),
      \(step("FUTURE_STEP", order: 14, status: "SOMETHING_NEW", link: "/tenant/jobs"))
    ],"steps_done":2,"steps_total":12,"percent":17,"complete":false,"dismissed":false,"dismissed_by":null,
    "dismissed_by_name":null,"dismissed_at":null,"controls_confirmed_by":null,"controls_confirmed_by_name":null,
    "controls_confirmed_at":null,"as_of":"2026-10-29T09:00:00Z"}
    """

    static func decode() throws -> SetupChecklistDTO {
        try AssetaJSON.decoder().decode(SetupChecklistDTO.self, from: Data(checklist.utf8))
    }

    static let all = ["tenant.setup.read", "tenant.setup.manage", "tenant.fleet.read", "tenant.job.read",
                      "tenant.approval.read", "tenant.finance.read", "tenant.hours.read"]

    @Test func decodesTheContractInServerOrder() throws {
        let c = try Self.decode()
        #expect(c.orderedSteps.map(\.order) == [1, 4, 5, 8, 10, 14])
        let machines = try #require(c.steps.first { $0.key == .machines })
        #expect(machines.checks.count == 2)
        #expect(machines.checks[1].optional)
        #expect(c.steps.last?.status.rawValue == "SOMETHING_NEW")
        #expect(SetupTexts.status(c.steps.last!.status) == "Something new")
        #expect(SetupTexts.status(.notApplicable) == "Does not apply")
    }

    @Test func meFiguresDriveTheBanner() throws {
        let json = """
        {"tenant_id":"\(Self.user)","name":"Co","status":"ACTIVE","access_state":"FULL","permissions":[],"menus":[],
         "setup_complete":false,"setup_percent":17,"setup_steps_done":2,"setup_steps_total":12,"setup_dismissed":false}
        """
        let tenant = try AssetaJSON.decoder().decode(TenantMembership.self, from: Data(json.utf8))
        let progress = SetupProgress(tenant)
        #expect(progress.bannerText == "Get ready to go live — 2 of 12 done")
        // Without tenant.setup.read the figures are null: no banner.
        let bare = try AssetaJSON.decoder().decode(TenantMembership.self, from: Data("""
        {"tenant_id":"\(Self.user)","name":"Co","status":"ACTIVE","access_state":"FULL","permissions":[],"menus":[]}
        """.utf8))
        #expect(SetupProgress(bare).bannerText == nil)
        #expect(SetupProgress(stepsDone: 12, stepsTotal: 12, complete: true, dismissed: false).showsBanner == false)
        #expect(SetupProgress(stepsDone: 2, stepsTotal: 12, complete: false, dismissed: true).showsBanner == false)
        #expect(SetupProgress(stepsDone: 0, stepsTotal: 0, complete: false, dismissed: false).showsBanner == false)
        // The checklist replaces the /me figures.
        #expect(SetupProgress(try Self.decode()) == SetupProgress(stepsDone: 2, stepsTotal: 12, complete: false, dismissed: false))
    }

    @Test func requests() throws {
        let key = UUID()
        let get = OwnerAPI.setupChecklist()
        #expect(get.method == .get && get.path == "/api/v1/tenant/setup-checklist")
        let mark = try OwnerAPI.markStepNotNeeded(.trackers, reason: "  none  ", idempotencyKey: key)
        #expect(mark.method == .post && mark.path == "/api/v1/tenant/setup-checklist/steps/TRACKERS/not-needed")
        #expect(String(decoding: mark.body ?? Data(), as: UTF8.self) == #"{"reason":"none"}"#)
        let undo = try OwnerAPI.undoStepNotNeeded(.trackers, idempotencyKey: key)
        #expect(undo.method == .delete && undo.path.hasSuffix("/steps/TRACKERS/not-needed"))
        let confirm = try OwnerAPI.confirmControls(note: "  ", idempotencyKey: key)
        #expect(confirm.method == .post && confirm.path.hasSuffix("/confirm-controls"))
        #expect(String(decoding: confirm.body ?? Data(), as: UTF8.self) == "{}")
    }

    @Test func linksMapToAppScreensTheRoleMayOpen() {
        let f = OwnerFeatures(permissions: Self.all)
        #expect(SetupPresentation.target(link: "/tenant/machines", features: f) == .app(.fleet, label: "Open Fleet"))
        #expect(SetupPresentation.target(link: "/tenant/machines?missing=tracker", features: f) == .web(path: "/tenant/machines?missing=tracker"))
        #expect(SetupPresentation.target(link: "/tenant/jobs", features: f) == .app(.jobs, label: "Open Jobs"))
        #expect(SetupPresentation.target(link: "/tenant/meter-baselines?missing=true", features: f) == .app(.approvals, label: "Open Approvals"))
        #expect(SetupPresentation.target(link: "/tenant/hours/purchases", features: f) == .app(.customerHours, label: "Open Customer hours"))
        #expect(SetupPresentation.target(link: "/tenant/hours/reasons", features: f) == .web(path: "/tenant/hours/reasons"))
        #expect(SetupPresentation.target(link: "/tenant/finance/cash", features: f) == .app(.cash, label: "Open Cash with supervisors"))
        #expect(SetupPresentation.target(link: "/tenant/finance/cash?tab=reasons", features: f) == .web(path: "/tenant/finance/cash?tab=reasons"))
        #expect(SetupPresentation.target(link: "/tenant/policies", features: f).label == "Open on the web")
        // Without the screen's permission (or customer hours switched off): the web.
        let none = OwnerFeatures(permissions: ["tenant.setup.read", "tenant.hours.read"], disabledCapabilities: ["CUSTOMER_HOURS"])
        #expect(SetupPresentation.target(link: "/tenant/machines", features: none) == .web(path: "/tenant/machines"))
        #expect(SetupPresentation.target(link: "/tenant/hours", features: none) == .web(path: "/tenant/hours"))
    }

    @Test func actionsAndManageButtons() throws {
        let c = try Self.decode()
        let f = OwnerFeatures(permissions: Self.all)
        func s(_ k: SetupStepKey) -> SetupStepDTO { c.steps.first { $0.key == k }! }
        #expect(SetupPresentation.action(for: s(.companySettings), features: f) == nil) // done: no action
        #expect(SetupPresentation.action(for: s(.depositAccounts), features: f) == nil) // not applicable
        #expect(SetupPresentation.action(for: s(.trackers), features: f) == nil) // not needed
        #expect(SetupPresentation.action(for: s(.machines), features: f) == .app(.fleet, label: "Open Fleet"))
        #expect(SetupPresentation.needsAccess(s(.machines), features: f)) // lacks tenant.machine.write
        let checks = s(.machines).checks
        #expect(SetupPresentation.action(for: checks[0], of: s(.machines), features: f) == nil)
        #expect(SetupPresentation.action(for: checks[1], of: s(.machines), features: f) == .web(path: "/tenant/machines?missing=tracker"))
        #expect(SetupPresentation.count(s(.machines)) == "2 of 5")
        #expect(SetupPresentation.count(checks[1]) == nil)
        #expect(SetupPresentation.canMarkNotNeeded(s(.machines)))
        #expect(!SetupPresentation.canMarkNotNeeded(s(.companySettings)))
        #expect(SetupPresentation.canUndo(s(.trackers)))
        #expect(SetupPresentation.canConfirmControls(s(.controlsChosen), checklist: c))
        #expect(!SetupPresentation.canConfirmControls(s(.machines), checklist: c))
        #expect(SetupPresentation.title(s(.machines)) == "4. Title 4")
        #expect(SetupPresentation.notNeededNote(s(.trackers), timeZone: TimeZone(identifier: "UTC")!)
            == "Marked not needed by Asha on 26 Oct 2026: No trackers yet")
        #expect(SetupPresentation.isValidReason(" ab ") == false)
        #expect(SetupPresentation.isValidReason("abc"))
        #expect(SetupPresentation.isValidNote(String(repeating: "x", count: 501)) == false)
    }

    @Test func gatesErrorsAndDeepLink() {
        #expect(OwnerFeatures(permissions: ["tenant.setup.read"]).setupRead)
        #expect(!OwnerFeatures(permissions: ["tenant.setup.read"]).setupManage)
        #expect(OwnerFeatures(permissions: ["tenant.setup.read"]).moreEntries.first == "Go-live checklist")
        #expect(OwnerFeatures(permissions: []).allows(.setupChecklist) == false)
        #expect(DeepLinkParser.route(path: "/tenant/setup") == .setupChecklist)
        let error = APIError.server(status: 422, body: ErrorBody(code: "SETUP_STEP_REQUIRED", message: "x", correlationID: "c"))
        #expect(SetupPresentation.errorMessage(error)
            == "This step is needed before going live, so it cannot be marked as not needed.")
    }
}
