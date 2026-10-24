@testable import AssetaOwnerKit
import AssetaModel
import AssetaNetwork
import Foundation
import Testing

/// The owner's "New job" (create and assign), mirroring the web job form. Identical to Android `JobCreateTest`.
@MainActor
struct JobCreateTests {
    static let contract = OwnerContractDTO(
        id: UUID(uuidString: "dddddddd-0000-4000-8000-000000000001")!, customerID: UUID(), contractNumber: "C-2026-007",
        reference: "Katavi road", currency: "TZS", jobSiteID: nil, status: "ACTIVE")
    static let supervisor = OwnerStaffDTO(id: UUID(uuidString: "dddddddd-0000-4000-8000-00000000000d")!,
                                          fullName: "Juma Field", kind: "SUPERVISOR", employeeCode: nil, isActive: true)
    static let start = Date(timeIntervalSince1970: 1_792_821_600) // 2026-10-24T06:00:00Z

    static func machine() throws -> OwnerMachineDTO {
        try AssetaJSON.decoder().decode(OwnerMachineDTO.self, from: Data("""
        {"id":"bbbbbbbb-0000-4000-8000-000000000002","asset_code":"EX-07","name":"CAT 320","status":"ACTIVE",
         "ownership":"OWNED","manufacturer":null,"model":null,"year_of_manufacture":null}
        """.utf8))
    }

    static func form() throws -> JobCreateForm {
        var form = JobCreateForm(now: start)
        form.contract = contract
        form.machine = try machine()
        form.supervisor = supervisor
        form.jobNumber = "  J-2026-200 "
        return form
    }

    static func job(_ status: String) throws -> JobDTO {
        var fields = JobApprovalTests.fields(rateSource: "RATE_CARD:x", status: status, requestedBy: nil, note: nil,
                                             requested: false)
        fields["job_number"] = "J-2026-200"
        return try AssetaJSON.decoder().decode(JobDTO.self, from: JSONSerialization.data(withJSONObject: fields))
    }

    func body(_ data: Data?) throws -> [String: Any] {
        try #require(data.flatMap { try JSONSerialization.jsonObject(with: $0) as? [String: Any] })
    }

    func apiError(_ code: String, status: Int = 422) -> APIError {
        .server(status: status, body: ErrorBody(code: code, message: "x", correlationID: "c"))
    }

    @Test func emptyFormNamesWhatIsMissing() {
        let form = JobCreateForm(now: Self.start)
        #expect(form.plannedStart == Self.start && form.priceMode == .rateCard && form.plannedEnd == nil)
        #expect(form.errors().map(\.1) == [
            "Choose the customer contract.", "Choose the machine.", "Choose the supervisor.", "Enter the job number.",
        ])
        #expect(form.payload() == nil)
    }

    @Test func negotiatedRateAndPlannedEndAreChecked() throws {
        var form = try Self.form()
        #expect(form.isValid)
        form.priceMode = .negotiated
        #expect(form.error(.hourlyRate) == "Enter the hourly rate.")
        form.hourlyRate = "0"
        #expect(form.error(.hourlyRate) == "Enter the hourly rate.")
        form.hourlyRate = "95,000.50"
        #expect(form.error(.hourlyRate) == nil)
        form.plannedEnd = Self.start.addingTimeInterval(-60)
        #expect(form.error(.plannedEnd) == "The planned end is before the planned start.")
        form.plannedEnd = Self.start
        #expect(form.error(.plannedEnd) == "The planned end is before the planned start.")
        form.plannedEnd = Self.start.addingTimeInterval(3600)
        form.minimumHours = "eight"
        #expect(form.error(.minimumHours) == "Enter the minimum hours as a number.")
        form.minimumHours = "8"
        form.jobNumber = String(repeating: "J", count: 33)
        #expect(form.error(.jobNumber) == "The job number is at most 32 characters.")
        form.jobNumber = String(repeating: "J", count: 32)
        #expect(form.isValid)
    }

    @Test func rateCardSendsTheWebDefaults() throws {
        let key = UUID()
        let request = try OwnerAPI.createJob(try #require(try Self.form().payload()), idempotencyKey: key)
        #expect(request.method == .post && request.path == "/api/v1/tenant/jobs" && request.idempotencyKey == key)
        let body = try body(request.body)
        #expect(body["contract_id"] as? String == "dddddddd-0000-4000-8000-000000000001")
        #expect(body["job_number"] as? String == "J-2026-200")
        #expect(body["machine_id"] as? String == "bbbbbbbb-0000-4000-8000-000000000002")
        #expect(body["supervisor_id"] as? String == "dddddddd-0000-4000-8000-00000000000d")
        #expect(body["planned_start"] as? String == "2026-10-24T06:00:00.000Z")
        #expect(body["job_site_id"] is NSNull && body["planned_end"] is NSNull)
        #expect(body["hourly_rate"] is NSNull && body["minimum_hours"] is NSNull && body["standby_rate"] is NSNull)
        #expect(body["standby_treatment"] as? String == "EXCLUDED")
        #expect(body["mobilization_fee"] as? String == "0" && body["discount_percent"] as? String == "0")
        #expect(body["tax_rate_percent"] as? String == "0")
        let json = String(decoding: try #require(request.body), as: UTF8.self)
        #expect(try Contract.missingRequired(schema: "JobIn", json: json) == [])
    }

    @Test func negotiatedRateIsSentAsADecimalString() throws {
        var form = try Self.form()
        form.priceMode = .negotiated
        form.hourlyRate = "95,000.50"
        form.minimumHours = "4"
        form.plannedEnd = Self.start.addingTimeInterval(8 * 3600)
        let body = try body(OwnerAPI.createJob(try #require(form.payload()), idempotencyKey: UUID()).body)
        #expect(body["hourly_rate"] as? String == "95000.5" && body["minimum_hours"] as? String == "4")
        #expect(body["planned_end"] as? String == "2026-10-24T14:00:00.000Z")
        // Switching back to the rate card drops the typed rate.
        form.priceMode = .rateCard
        #expect(try self.body(OwnerAPI.createJob(try #require(form.payload()), idempotencyKey: UUID()).body)["hourly_rate"] is NSNull)
    }

    @Test func lookupsUseTheWebPickerEndpoints() {
        let contracts = OwnerAPI.contractOptions(query: " C-20 ")
        #expect(contracts.path == "/api/v1/tenant/contracts")
        #expect(contracts.queryItems.map(\.name) == ["page", "page_size", "q"] && contracts.queryItems[2].value == "C-20")
        #expect(OwnerAPI.machineOptions(query: "").path == "/api/v1/tenant/machines")
        #expect(OwnerAPI.machineOptions(query: "").queryItems.map(\.name) == ["page", "page_size"])
        let staff = OwnerAPI.supervisorOptions(query: "ju")
        #expect(staff.path == "/api/v1/tenant/staff" && staff.queryItems.contains(URLQueryItem(name: "kind", value: "SUPERVISOR")))
        #expect(OwnerAPI.jobSiteOptions(query: "kat").path == "/api/v1/tenant/job-sites")
        #expect(Self.contract.label == "C-2026-007 · Katavi road")
    }

    @Test func approveNowCreatesSubmitsAndApprovesInSequence() async throws {
        var progress = JobCreateProgress()
        var sent: [(String, String?, UUID?)] = []
        let replies = [try Self.job("DRAFT"), try Self.job("PENDING_APPROVAL"), try Self.job("APPROVED")]
        let outcome = await JobCreateFlow.run(form: try Self.form(), approveNow: true, progress: &progress) { request in
            let action = try request.body.flatMap { try JSONSerialization.jsonObject(with: $0) as? [String: Any] }?["action"] as? String
            sent.append((request.path, action, request.idempotencyKey))
            return replies[sent.count - 1]
        }
        let jobPath = "/api/v1/tenant/jobs/\(JobApprovalTests.jobID.uuidString.lowercased())/transitions"
        #expect(sent.map(\.0) == ["/api/v1/tenant/jobs", jobPath, jobPath])
        #expect(sent.map(\.1) == [nil, "SUBMIT", "APPROVE"])
        #expect(sent.map(\.2) == [progress.createKey, progress.submitKey, progress.approveKey])
        #expect(outcome == .done(replies[2], message: "Job J-2026-200 created and assigned to Juma Field."))
        #expect(progress.remaining(approveNow: true).isEmpty)
    }

    @Test func withoutApprovalTheJobIsSentForApproval() async throws {
        var progress = JobCreateProgress()
        var actions: [String?] = []
        let replies = [try Self.job("DRAFT"), try Self.job("PENDING_APPROVAL")]
        let outcome = await JobCreateFlow.run(form: try Self.form(), approveNow: false, progress: &progress) { request in
            actions.append(try request.body.flatMap { try JSONSerialization.jsonObject(with: $0) as? [String: Any] }?["action"] as? String)
            return replies[actions.count - 1]
        }
        #expect(actions == [nil, "SUBMIT"])
        #expect(outcome == .done(replies[1], message: "Job J-2026-200 created and sent for approval."))
    }

    @Test func aFailedApprovalShowsTheJobAndNeverCreatesItTwice() async throws {
        var progress = JobCreateProgress()
        var calls = 0
        let draft = try Self.job("DRAFT"), pending = try Self.job("PENDING_APPROVAL")
        let outcome = await JobCreateFlow.run(form: try Self.form(), approveNow: true, progress: &progress) { _ in
            calls += 1
            if calls == 1 { return draft }
            if calls == 2 { return pending }
            throw self.apiError("MACHINE_BUSY", status: 409)
        }
        #expect(outcome == .partly(pending, message: "Job J-2026-200 was created and sent for approval, but not approved: "
            + "This machine already has an approved or running job; complete or cancel that job first."))
        #expect(progress.job == pending && progress.remaining(approveNow: true) == [.approve])

        // A failed SUBMIT leaves a DRAFT: a retry resumes at SUBMIT, never POST /jobs again.
        var second = JobCreateProgress()
        var paths: [String] = []
        let failed = await JobCreateFlow.run(form: try Self.form(), approveNow: false, progress: &second) { request in
            paths.append(request.path)
            if paths.count == 1 { return draft }
            throw APIError.transport(code: -1009, message: "offline", correlationID: "c")
        }
        guard case let .partly(job, message) = failed else { Issue.record("expected partly"); return }
        #expect(job == draft && message.hasPrefix("Job J-2026-200 was created but not sent for approval: "))
        #expect(second.remaining(approveNow: false) == [.submit])
        let retried = await JobCreateFlow.run(form: try Self.form(), approveNow: false, progress: &second) { request in
            paths.append(request.path)
            return pending
        }
        #expect(paths.filter { $0 == "/api/v1/tenant/jobs" }.count == 1)
        #expect(retried == .done(pending, message: "Job J-2026-200 created and sent for approval."))
    }

    @Test func refusedCreatesAreExplainedAndGetANewKey() async throws {
        var progress = JobCreateProgress()
        let firstKey = progress.createKey
        let noRate = await JobCreateFlow.run(form: try Self.form(), approveNow: false, progress: &progress) { _ in
            throw self.apiError("NO_RATE")
        }
        #expect(noRate == .notCreated(message: "No rate card applies to this machine; choose Negotiated rate and enter a price."))
        #expect(progress.job == nil && progress.createKey != firstKey)
        // A lost response keeps the key: the server replays the create instead of making a second job.
        let kept = progress.createKey
        _ = await JobCreateFlow.run(form: try Self.form(), approveNow: false, progress: &progress) { _ in
            throw APIError.transport(code: -1001, message: "timeout", correlationID: "c")
        }
        #expect(progress.createKey == kept)
        #expect(JobCreateText.message(for: apiError("DUPLICATE_JOB", status: 409)) == "That job number is already used.")
        #expect(JobCreateText.message(for: apiError("CONTRACT_NOT_ACTIVE")) == "Choose an active contract.")
    }

    @Test func creatingIsGatedOnJobWriteAndApproveNowOnJobApprove() {
        let writer = OwnerFeatures(permissions: ["tenant.job.read", "tenant.job.write"])
        #expect(writer.createJobs && !writer.approveJobs && !writer.pickJobSites)
        #expect(!OwnerFeatures(permissions: ["tenant.job.read", "tenant.job.approve"]).createJobs)
        #expect(OwnerFeatures(permissions: ["tenant.geofence.read"]).pickJobSites)
        #expect(JobCreateText.submitLabel(approveNow: true, canApprove: true) == "Create and approve")
        #expect(JobCreateText.submitLabel(approveNow: true, canApprove: false) == "Create")
        #expect(JobCreateText.submitLabel(approveNow: false, canApprove: true) == "Create")
        #expect(MutationGuard.check(isOnline: true, showingCachedData: false, accessState: .full,
                                    permitted: writer.createJobs) == nil)
        #expect(MutationGuard.check(isOnline: false, showingCachedData: false, accessState: .full,
                                    permitted: writer.createJobs) == .offline)
        #expect(MutationGuard.check(isOnline: true, showingCachedData: true, accessState: .full,
                                    permitted: writer.createJobs) == .showingCachedData)
        #expect(JobCreateText.hourlyRateLabel(currency: "TZS") == "Hourly rate (TZS)")
    }

    @Test func lookupSamplesMatchTheContract() throws {
        let contract = """
        {"id":"dddddddd-0000-4000-8000-000000000001","customer_id":"dddddddd-0000-4000-8000-000000000009",
         "contract_number":"C-2026-007","reference":null,"currency":"TZS","job_site_id":null,"status":"ACTIVE",
         "starts_on":"2026-10-01T00:00:00Z","ends_on":null}
        """
        #expect(try Contract.missingRequired(schema: "ContractDto", json: contract) == [])
        #expect(try AssetaJSON.decoder().decode(OwnerContractDTO.self, from: Data(contract.utf8)).label == "C-2026-007")
        let staff = """
        {"id":"dddddddd-0000-4000-8000-00000000000d","full_name":"Juma Field","kind":"SUPERVISOR","employee_code":null,
         "phone":null,"keycloak_subject":null,"is_active":true,"deactivated_at":null,"deactivation_reason":null,"version":1}
        """
        #expect(try Contract.missingRequired(schema: "StaffDto", json: staff) == [])
        #expect(try AssetaJSON.decoder().decode(OwnerStaffDTO.self, from: Data(staff.utf8)).fullName == "Juma Field")
    }
}
