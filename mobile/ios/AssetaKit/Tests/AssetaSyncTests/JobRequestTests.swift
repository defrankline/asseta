import AssetaModel
import AssetaNetwork
import AssetaSecurity
import AssetaStore
@testable import AssetaSync
import AssetaTestSupport
import Foundation
import Testing

/// Supervisor job requests from the field (`JOB_REQUEST`), identical to Android `JobRequestTest`.
struct JobRequestTests {
    static let contractID = UUID(uuidString: "eeeeeeee-0000-4000-8000-00000000000e")!
    static let siteID = UUID(uuidString: "ffffffff-0000-4000-8000-00000000000f")!

    /// The server advertised OP_JOB_REQUEST on the last sync.
    static func supported(_ store: LocalStore) throws {
        try store.syncState.setValue("SUPERVISOR_INBOX_V1,OP_JOB_REQUEST", for: SyncKey.capabilities,
                                     tenant: SyncFixtures.tenant.uuidString.lowercased())
    }

    @Test func requestsNeedAServerThatAcceptsThem() throws {
        let h = try SyncHarness()
        #expect(h.recorder.jobRequestUnavailable() == "Sync once while online before requesting a job.")
        #expect(throws: FieldRecorderError.notAllowed(JobRequestText.neverSynced)) {
            try h.recorder.requestJob(contractID: Self.contractID, machineID: SyncFixtures.machineID, jobSiteID: nil,
                                      plannedStart: h.clock.wallNow, plannedEnd: nil, note: nil)
        }
        try h.store.syncState.setValue("SUPERVISOR_INBOX_V1", for: SyncKey.capabilities,
                                       tenant: SyncFixtures.tenant.uuidString.lowercased())
        #expect(h.recorder.jobRequestUnavailable() == "Your company's server does not accept job requests yet.")
        try Self.supported(h.store)
        #expect(h.recorder.jobRequestUnavailable() == nil)
    }

    @Test func requestIsQueuedOfflineWithItsClientIDAsTheJobID() throws {
        let h = try SyncHarness()
        try Self.supported(h.store)
        let clientID = UUID()
        let start = h.clock.wallNow
        let op = try h.recorder.requestJob(contractID: Self.contractID, machineID: SyncFixtures.machineID, jobSiteID: Self.siteID,
                                           plannedStart: start, plannedEnd: start.addingTimeInterval(3600),
                                           note: "  Dig the trench by the road  ", at: start, clientID: clientID)
        #expect(op.opType == "JOB_REQUEST" && op.entityID == clientID && op.dependencies.isEmpty && op.status == .pending)
        let payload = try JSONValue.parse(op.payloadJSON)
        #expect(payload["client_id"]?.stringValue == clientID.uuidString.lowercased())
        #expect(payload["contract_id"]?.stringValue == Self.contractID.uuidString.lowercased())
        #expect(payload["machine_id"]?.stringValue == SyncFixtures.machineID.uuidString.lowercased())
        #expect(payload["job_site_id"]?.stringValue == Self.siteID.uuidString.lowercased())
        #expect(payload["note"]?.stringValue == "Dig the trench by the road")
        #expect(payload["planned_start"]?.stringValue != nil && payload["planned_end"]?.stringValue != nil)

        // The same form visit can't save twice.
        #expect(throws: FieldRecorderError.notAllowed(JobRequestText.alreadySaved)) {
            try h.recorder.requestJob(contractID: Self.contractID, machineID: SyncFixtures.machineID, jobSiteID: nil,
                                      plannedStart: start, plannedEnd: nil, note: nil, clientID: clientID)
        }
    }

    @Test func formRulesMatchTheServer() throws {
        let h = try SyncHarness()
        try Self.supported(h.store)
        let now = h.clock.wallNow
        #expect(throws: FieldRecorderError.invalid(JobRequestText.chooseContract)) {
            try h.recorder.requestJob(contractID: nil, machineID: SyncFixtures.machineID, jobSiteID: nil, plannedStart: now,
                                      plannedEnd: nil, note: nil)
        }
        #expect(throws: FieldRecorderError.invalid(JobRequestText.chooseMachine)) {
            try h.recorder.requestJob(contractID: Self.contractID, machineID: nil, jobSiteID: nil, plannedStart: now,
                                      plannedEnd: nil, note: nil)
        }
        #expect(throws: FieldRecorderError.invalid(JobRequestText.endBeforeStart)) {
            try h.recorder.requestJob(contractID: Self.contractID, machineID: SyncFixtures.machineID, jobSiteID: nil,
                                      plannedStart: now, plannedEnd: now.addingTimeInterval(-60), note: nil)
        }
        #expect(throws: FieldRecorderError.invalid(JobRequestText.noteTooLong)) {
            try h.recorder.requestJob(contractID: Self.contractID, machineID: SyncFixtures.machineID, jobSiteID: nil,
                                      plannedStart: now, plannedEnd: nil, note: String(repeating: "x", count: 1001))
        }
        let blank = try h.recorder.requestJob(contractID: Self.contractID, machineID: SyncFixtures.machineID, jobSiteID: nil,
                                              plannedStart: now, plannedEnd: nil, note: "   ")
        let payload = try JSONValue.parse(blank.payloadJSON)
        #expect(payload["note"] == nil || payload["note"] == .null)
        #expect(payload["job_site_id"] == nil || payload["job_site_id"] == .null)
    }

    @Test func requestShowsAtOnceThenWaitsForApprovalWithTheServerNumber() async throws {
        let h = try SyncHarness()
        try Self.supported(h.store)
        let clientID = UUID()
        try h.recorder.requestJob(contractID: Self.contractID, machineID: SyncFixtures.machineID, jobSiteID: nil,
                                  plannedStart: h.clock.wallNow, plannedEnd: nil, note: "Two days of loading",
                                  clientID: clientID)
        // Offline: shown right away from the outbox, with the synced machine.
        var mine = try #require(try h.directoryView.jobs().first { $0.id == clientID })
        #expect(mine.request == .notSent && mine.request?.label == "Waiting for approval (not yet sent)")
        #expect(mine.job.status == .pendingApproval && mine.job.jobNumber == JobRequestText.unnumbered)
        #expect(mine.job.requestNote == "Two days of loading")
        #expect(InboxTexts.segment(mine.job.status) == .ready)
        #expect(h.directoryView.job(id: clientID)?.request == .notSent)

        // Accepted, but the pull did not bring the job yet: waiting, with the number from the push result.
        h.server.mutate { $0.deliverRequestedJobs = false }
        _ = try await h.engine().sync(force: true)
        let sent = try h.store.outbox.operations(tenantID: SyncFixtures.tenant, owner: nil,
                                                 statuses: Set(ClientOperationStatus.allCases))
        #expect(sent.first { $0.entityID == clientID }?.status == .acked)
        mine = try #require(try h.directoryView.jobs().first { $0.id == clientID })
        #expect(mine.request == .waiting && mine.request?.label == "Waiting for approval")
        #expect(mine.job.jobNumber == "J-2026-105")
    }

    @Test func syncedRequestedJobIsWaitingThenDeclinedWithTheReason() async throws {
        let h = try SyncHarness()
        try Self.supported(h.store)
        let clientID = UUID()
        try h.recorder.requestJob(contractID: Self.contractID, machineID: SyncFixtures.machineID, jobSiteID: nil,
                                  plannedStart: h.clock.wallNow, plannedEnd: nil, note: nil, clientID: clientID)
        _ = try await h.engine().sync(force: true)
        var mine = try #require(try h.directoryView.jobs().first { $0.id == clientID })
        #expect(mine.request == .waiting && mine.job.jobNumber == "J-2026-105" && mine.job.needsPrice)
        #expect(try h.directoryView.jobs().filter { $0.id == clientID }.count == 1)
        #expect(!(try h.recorder.progress(jobID: clientID, serverStatus: mine.job.status)).canCaptureOpening)

        // The owner declines it: CANCELLED before approval, with the reason.
        h.server.mutate { server in
            server.jobs = server.jobs.map { job in
                guard job["id"] as? String == clientID.uuidString.lowercased() else { return job }
                var copy = job
                copy["status"] = "CANCELLED"
                copy["cancellation_reason"] = "No operator free this week"
                copy["version"] = 2
                return copy
            }
            server.cursor += 1
        }
        _ = try await h.engine().sync(force: true)
        mine = try #require(try h.directoryView.jobs().first { $0.id == clientID })
        #expect(mine.request == .declined(reason: "No operator free this week") && mine.request?.label == "Declined")
    }

    @Test func officeJobsAndApprovedRequestsCarryNoRequestChip() throws {
        let decoder = AssetaJSON.decoder()
        var fields = SyncFixtures.job(status: "APPROVED")
        fields["requested_by_staff_id"] = UUID().uuidString.lowercased()
        let approved = try decoder.decode(JobDTO.self, from: try JSONSerialization.data(withJSONObject: fields))
        #expect(JobRequestState.of(job: approved, requestOp: nil) == nil)
        #expect(JobRequestState.of(job: SyncFixtures.jobDTO, requestOp: nil) == nil)
        fields["status"] = "PENDING_APPROVAL"
        let pending = try decoder.decode(JobDTO.self, from: try JSONSerialization.data(withJSONObject: fields))
        #expect(JobRequestState.of(job: pending, requestOp: nil) == .waiting)
    }

    @Test func refusedRequestsShowTheirSyncStateAndAcceptedOnesFadeAfterTwoWeeks() async throws {
        let h = try SyncHarness()
        try Self.supported(h.store)
        let refused = try h.recorder.requestJob(contractID: Self.contractID, machineID: SyncFixtures.machineID, jobSiteID: nil,
                                                plannedStart: h.clock.wallNow, plannedEnd: nil, note: nil)
        h.server.mutate { $0.script[refused.id] = ["REJECTED"]; $0.deliverRequestedJobs = false }
        let accepted = try h.recorder.requestJob(contractID: Self.contractID, machineID: SyncFixtures.machineID, jobSiteID: nil,
                                                 plannedStart: h.clock.wallNow, plannedEnd: nil, note: nil, at: h.clock.wallNow)
        _ = try await h.engine().sync(force: true)
        var jobs = try h.directoryView.jobs()
        #expect(jobs.first { $0.id == refused.entityID }?.request == .problem(.failed))
        #expect(jobs.first { $0.id == refused.entityID }?.request?.label == "Rejected")
        #expect(jobs.first { $0.id == accepted.entityID }?.request == .waiting)
        #expect(JobRequestState.of(operation: .quarantined).label == "Held")
        #expect(JobRequestState.of(operation: .sent) == .notSent)

        h.clock.advance(15 * 86400)
        jobs = try h.directoryView.jobs()
        #expect(jobs.first { $0.id == accepted.entityID } == nil)
        #expect(jobs.first { $0.id == refused.entityID } != nil)
    }

    @Test func lookupsAreSavedForOfflineAndClearedForAnotherUser() async throws {
        let store = try LocalStore.open(at: try temporaryDirectory().appendingPathComponent("l.sqlite"),
                                        keyProvider: DatabaseKeyProvider(store: InMemorySecretStore()))
        let contracts = """
        [{"id":"\(Self.contractID.uuidString.lowercased())","contract_number":"RC-2026-007",
          "customer_id":"aaaaaaaa-0000-4000-8000-0000000000aa","customer_name":"Katavi Roads Ltd",
          "job_site_id":"\(Self.siteID.uuidString.lowercased())","job_site_name":"Mpanda yard","currency":"TZS",
          "starts_on":"2026-01-01T00:00:00Z","ends_on":null,"reference":null}]
        """
        let machines = """
        [{"id":"\(SyncFixtures.machineID.uuidString.lowercased())","asset_code":"EX-07","name":"Excavator 7",
          "meter_decimal_places":1,"version":2}]
        """
        let transport = MockTransport { request in
            (200, Data((request.url!.path.hasSuffix("/field/contracts") ? contracts : machines).utf8))
        }
        let client = APIClient(baseURL: URL(string: "https://api.test")!, transport: transport,
                               tokens: StaticTokenProvider(token: "t"), tenantID: SyncFixtures.tenant)
        let online = SupervisorOnline(client: client, store: store, tenantID: SyncFixtures.tenant)
        let directory = FieldDirectory(store: store, tenantID: SyncFixtures.tenant)
        #expect(directory.requestContracts().isEmpty)
        #expect(await online.refreshRequestLookups())
        let contract = try #require(directory.requestContracts().first)
        #expect(contract.customerName == "Katavi Roads Ltd" && contract.siteName == "Mpanda yard" && contract.jobSiteID == Self.siteID)
        #expect(directory.requestMachines().map(\.assetCode) == ["EX-07"])

        // Offline: the fetch fails and the saved lists stay.
        transport.setHandler { _ in throw URLError(.notConnectedToInternet) }
        #expect(!(await online.refreshRequestLookups()))
        #expect(directory.requestContracts().count == 1 && directory.requestMachines().count == 1)

        // A request made offline shows the saved customer, site and machine.
        try Self.supported(store)
        let recorder = FieldRecorder(store: store, tenantID: SyncFixtures.tenant, deviceID: "d")
        let op = try recorder.requestJob(contractID: Self.contractID, machineID: SyncFixtures.machineID, jobSiteID: Self.siteID,
                                         plannedStart: Date(), plannedEnd: nil, note: nil)
        let job = try #require(directory.job(id: op.entityID))
        #expect(job.customer?.name == "Katavi Roads Ltd" && job.site?.name == "Mpanda yard" && job.machine?.assetCode == "EX-07")

        // Another user signing in on this phone clears them with the rest of the tenant's state.
        try store.syncState.claim(tenantID: SyncFixtures.tenant, owner: "someone-else")
        #expect(directory.cachedFieldContracts() == nil && directory.cachedFieldMachines() == nil)
    }
}
