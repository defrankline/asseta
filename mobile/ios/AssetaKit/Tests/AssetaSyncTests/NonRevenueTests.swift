import AssetaModel
import AssetaNetwork
import AssetaSecurity
import AssetaStore
@testable import AssetaSync
import AssetaTestSupport
import Foundation
import Testing

/// DEC-031 Phase 1 on the Supervisor side: the non-revenue status of work-log entries (matched by the server activity
/// id), "Explain" for explain holders while NONE / REJECTED, the online requests and the refusals in plain words.
struct NonRevenueTests {
    static let activityID = UUID(uuidString: "f7000000-0000-4000-8000-000000000001")!
    static let reasonID = UUID(uuidString: "f5000000-0000-4000-8000-000000000001")!

    static func activity(status: String, id: UUID = activityID) -> String {
        """
        {"activity_id":"\(id.uuidString.lowercased())","activity_type":"MOBILIZATION","approval_status":"\(status)",
         "approval_id":null,"job_id":"\(SyncFixtures.jobID.uuidString.lowercased())","job_number":"J-12",
         "machine_id":"\(SyncFixtures.machineID.uuidString.lowercased())","machine_code":"EX-01","machine_name":null,
         "started_at":"2026-10-26T06:00:00Z","ended_at":"2026-10-26T07:30:00Z","hours":"1.50","note":null}
        """
    }

    @Test func statusWordingAndTones() {
        #expect(FieldRevenueTexts.status("NONE") == "Counted as revenue until explained")
        #expect(FieldRevenueTexts.status("PROPOSED") == "Explained · waiting for approval")
        #expect(FieldRevenueTexts.status("APPROVED") == "Approved as non-revenue time")
        #expect(FieldRevenueTexts.status("REJECTED") == "Not approved · counted as revenue")
        #expect(FieldRevenueTexts.status("LATER_STATE") == "Later state")
        #expect(NonRevenueRules.tone("NONE") == .warning && NonRevenueRules.tone("REJECTED") == .warning)
        #expect(NonRevenueRules.tone("PROPOSED") == .accent && NonRevenueRules.tone("APPROVED") == .live)
        #expect(NonRevenueRules.explainable("NONE") && NonRevenueRules.explainable("REJECTED"))
        #expect(!NonRevenueRules.explainable("PROPOSED") && !NonRevenueRules.explainable("APPROVED"))
        #expect(FieldRevenueTexts.entryLine(type: "Mobilization", start: "06:00", end: "07:30", hours: "1.5")
            == "Mobilization · 06:00 → 07:30 (1.5 h)")
    }

    @Test func sendNeedsAReasonANoteAndAConnection() {
        #expect(NonRevenueRules.canSend(reasonID: Self.reasonID, note: "Moved to site B", online: true))
        #expect(!NonRevenueRules.canSend(reasonID: nil, note: "Moved to site B", online: true))
        #expect(!NonRevenueRules.canSend(reasonID: Self.reasonID, note: " abc ", online: true))
        #expect(!NonRevenueRules.canSend(reasonID: Self.reasonID, note: "Moved to site B", online: false))
        #expect(!NonRevenueRules.noteOK(String(repeating: "x", count: 2001)))
    }

    @Test func accessFollowsCapabilityAndPermissions() {
        let all: Set<String> = [RevenuePermission.read, RevenuePermission.explain]
        let on = FieldAccess(capabilities: [], permissions: all)
        #expect(on.revenueOn && on.nonRevenueStatus && on.explainNonRevenue)
        let off = FieldAccess(capabilities: [], permissions: all, disabledCapabilities: [TenantCapability.revenueReconciliation])
        #expect(!off.nonRevenueStatus && !off.explainNonRevenue)
        let readOnly = FieldAccess(capabilities: [], permissions: [RevenuePermission.read])
        #expect(readOnly.nonRevenueStatus && !readOnly.explainNonRevenue)
        // An older server never grants the revenue permissions: the work log is unchanged.
        #expect(!FieldAccess(capabilities: [], permissions: ["tenant.job.log"]).nonRevenueStatus)
    }

    @Test func refusalsInPlainWords() {
        func refusal(_ code: String) -> APIError {
            .server(status: 409, body: ErrorBody(code: code, message: "Server says no", correlationID: "c"))
        }
        #expect(NonRevenueRules.message(for: refusal("NON_REVENUE_PENDING")) == "This time is already waiting for approval.")
        #expect(NonRevenueRules.message(for: refusal("NON_REVENUE_APPROVAL_NOT_REQUIRED"))
            == "Your company does not need approval for this time.")
        #expect(NonRevenueRules.message(for: refusal("REVENUE_RECONCILIATION_DISABLED")) == "Your company has switched off revenue checks.")
        #expect(NonRevenueRules.message(for: refusal("REASON_INACTIVE")) == "This reason is no longer in use. Choose another.")
        #expect(NonRevenueRules.message(for: refusal("SOMETHING_ELSE")) == "Server says no")
        #expect(NonRevenueRules.message(for: APIError.transport(code: -1009, message: "offline", correlationID: "c"))
            == "Explaining needs a connection.")
    }

    @Test func onlineRequests() async throws {
        let store = try LocalStore.open(at: try temporaryDirectory().appendingPathComponent("n.sqlite"),
                                        keyProvider: DatabaseKeyProvider(store: InMemorySecretStore()))
        let activities = #"{"items":[\#(Self.activity(status: "NONE")),\#(Self.activity(status: "PROPOSED", id: UUID()))],"total":2,"page":1,"page_size":200}"#
        let reasons = #"{"items":[{"id":"\#(Self.reasonID.uuidString.lowercased())","code":"MOVE","name":"Move to site","description":null,"is_active":true,"version":1},{"id":"f5000000-0000-4000-8000-000000000002","code":"OLD","name":"Old","description":null,"is_active":false,"version":2}],"total":2,"page":1,"page_size":200}"#
        let approval = RevenueSamples.approval
        let transport = MockTransport { request in
            let path = request.url?.path ?? ""
            if path.hasSuffix("/non-revenue-activities") { return (200, Data(activities.utf8)) }
            if path.hasSuffix("/revenue-reasons") { return (200, Data(reasons.utf8)) }
            return (201, Data(approval.utf8))
        }
        let client = APIClient(baseURL: URL(string: "https://api.test")!, transport: transport,
                               tokens: StaticTokenProvider(token: "t"), tenantID: SyncFixtures.tenant)
        let online = SupervisorOnline(client: client, store: store, tenantID: SyncFixtures.tenant)

        let items = try await online.nonRevenueActivities(jobID: SyncFixtures.jobID)
        #expect(items.count == 2 && NonRevenueRules.byActivity(items)[Self.activityID]?.approvalStatus == "NONE")
        let listURL = try #require(transport.requests.first?.url)
        #expect(listURL.query?.contains("job_id=\(SyncFixtures.jobID.uuidString.lowercased())") == true)

        #expect(try await online.revenueReasons().map(\.name) == ["Move to site"])

        let created = try await online.explainNonRevenue(activityID: Self.activityID, reasonID: Self.reasonID, note: "  Moved to site B ")
        #expect(created.status == "PROPOSED")
        let post = try #require(transport.requests.last)
        #expect(post.httpMethod == "POST" && post.url?.path == "/api/v1/tenant/non-revenue-approvals")
        #expect(post.value(forHTTPHeaderField: "Idempotency-Key") != nil)
        let body = try JSONValue.parse(String(decoding: try #require(post.httpBody), as: UTF8.self))
        #expect(body["note"]?.stringValue == "Moved to site B")
        #expect(body["activity_id"]?.stringValue.flatMap(UUID.init(uuidString:)) == Self.activityID)
    }

    @Test func workLogEntriesCarryTheServerActivityID() async throws {
        let h = try SyncHarness()
        let job = SyncFixtures.jobDTO
        let op = try h.recorder.recordActivity(job: job, type: .mobilization, startedAt: h.clock.wallNow,
                                               endedAt: h.clock.wallNow.addingTimeInterval(3600), billable: false, note: nil)
        #expect(try InboxDirectory(store: h.store, tenantID: SyncFixtures.tenant).snapshot().activities.first?.serverID == nil)
        _ = try await h.engine().sync(force: true)
        let entry = try #require(try InboxDirectory(store: h.store, tenantID: SyncFixtures.tenant).snapshot().activities.first)
        // The fake server acknowledges with the entity id it assigned (the operation id here).
        #expect(entry.serverID == op.id)
    }
}

enum RevenueSamples {
    static let approval = """
    {"id":"f2000000-0000-4000-8000-000000000001","activity_id":"f7000000-0000-4000-8000-000000000001","activity_type":"MOBILIZATION",
     "job_id":"bbbbbbbb-0000-4000-8000-000000000001","job_number":"J-12","machine_id":"aaaaaaaa-0000-4000-8000-000000000001",
     "machine_code":"EX-01","machine_name":null,"started_at":"2026-10-26T06:00:00Z","ended_at":"2026-10-26T07:30:00Z",
     "hours":"1.50","reason_id":"f5000000-0000-4000-8000-000000000001","reason_name":"Move to site","note":"Moved to site B",
     "status":"PROPOSED","proposed_by":null,"proposed_by_name":null,"proposed_at":"2026-10-26T08:00:00Z","decided_by":null,
     "decided_by_name":null,"decided_at":null,"decision_note":null,"policy_version":"r1"}
    """
}
