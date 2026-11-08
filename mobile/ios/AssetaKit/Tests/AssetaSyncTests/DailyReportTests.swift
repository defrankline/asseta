import AssetaCapture
import AssetaModel
import AssetaStore
@testable import AssetaSync
import Foundation
import Testing

/// DEC-032 Phase 1 on the field side: the daily report form's rules, its offline operation (evidence, waiting for
/// unsent readings, once per form visit), the changeover reading, conflicts and the report list. Same rules as Android
/// `DailyReportRules`, `DailyReportCapture` and `DailyReportData`.
struct DailyReportTests {
    typealias T = DailyReportTexts
    static let all = AccountabilityTests.all + [SyncCapability.dailyReport, SyncCapability.meterChangeover]
    static let opening = UUID(uuidString: "e0000000-0000-4000-8000-000000000001")!
    static let closing = UUID(uuidString: "e0000000-0000-4000-8000-000000000002")!
    static let reason = UUID(uuidString: "e0000000-0000-4000-8000-000000000003")!
    static let other = UUID(uuidString: "e0000000-0000-4000-8000-000000000004")!

    static func draft(opening: UUID? = Self.opening, closing: UUID? = Self.closing, from: String? = "100", to: String? = "108") -> DailyReportDraft {
        var d = DailyReportDraft(machineID: SyncFixtures.machineID, reportDate: "2026-11-08", openingRef: opening, closingRef: closing)
        d.openingReading = from
        d.closingReading = to
        return d
    }

    static func messages(_ d: DailyReportDraft, photos: Int = 0, required: Bool = false) -> [String] {
        if case let .failure(p) = DailyReportRules.check(d, photos: photos, evidenceRequired: required) { return p.messages }
        return []
    }

    @Test func entriesNeedCapabilityPermissionAndEngineHours() {
        let perms: Set<String> = ["tenant.meter.capture"]
        let on = FieldAccess(capabilities: Set(Self.all), permissions: perms)
        #expect(on.dailyReport && on.changeover)
        #expect(!FieldAccess(capabilities: Set(AccountabilityTests.all), permissions: perms).dailyReport)
        #expect(!FieldAccess(capabilities: nil, permissions: perms).changeover)
        #expect(!FieldAccess(capabilities: Set(Self.all), permissions: []).dailyReport)
        let off = FieldAccess(capabilities: Set(Self.all), permissions: perms, disabledCapabilities: [TenantCapability.engineHours])
        #expect(!off.dailyReport && !off.changeover)
    }

    @Test func prefillUsesTheDaysFirstOrTheLatestBefore() {
        let start = Date(timeIntervalSince1970: 1000), end = Date(timeIntervalSince1970: 2000)
        func r(_ at: TimeInterval) -> ReportReading { ReportReading(id: UUID(), reading: "1", at: Date(timeIntervalSince1970: at), synced: true) }
        let before = r(900), older = r(800), first = r(1100), last = r(1900), after = r(2100)
        var picked = DailyReportRules.prefill([older, before, first, last, after], dayStart: start, dayEnd: end)
        #expect(picked.opening == first.id && picked.closing == last.id)
        picked = DailyReportRules.prefill([older, before, last], dayStart: start, dayEnd: end)
        #expect(picked.opening == before.id && picked.closing == last.id)
        picked = DailyReportRules.prefill([before], dayStart: start, dayEnd: end)
        #expect(picked.opening == before.id && picked.closing == nil)
    }

    @Test func totalsAndNotAccounted() {
        #expect(DailyReportRules.total(opening: "100.5", closing: "108") == Decimal(string: "7.5"))
        #expect(DailyReportRules.total(opening: "108", closing: "100") == nil)
        #expect(DailyReportRules.total(opening: nil, closing: "100") == nil)
        let line = [UnbillableDraft(reasonID: Self.reason, hoursText: "2")]
        // Empty billable: the total minus the unbillable hours, so nothing is left over.
        #expect(DailyReportRules.notAccounted(total: 8, billableText: "", lines: line) == 0)
        #expect(DailyReportRules.notAccounted(total: 8, billableText: "5", lines: line) == 1)
        #expect(DailyReportRules.notAccounted(total: 8, billableText: "x", lines: line) == nil)
        #expect(DailyReportRules.notAccounted(total: nil, billableText: "5", lines: line) == nil)
    }

    @Test func formProblemsInOrder() {
        #expect(Self.messages(Self.draft(opening: nil, closing: nil)) == [T.errOpening, T.errClosing])
        #expect(Self.messages(Self.draft(closing: Self.opening)) == [T.errSameReading])
        var d = Self.draft()
        d.billableText = "1.234"
        d.unbillable = [UnbillableDraft(reasonID: nil, hoursText: "1"), UnbillableDraft(reasonID: Self.reason, hoursText: "0"),
                        UnbillableDraft(reasonID: Self.reason, hoursText: "2")]
        #expect(Self.messages(d, required: true) == [T.errBillable, T.errReasonMissing, T.errReasonHours, T.errReasonRepeated, T.errPhoto])
    }

    @Test func aBlankLineIsIgnoredAndHoursCannotExceedTheTotal() throws {
        var d = Self.draft()
        d.billableText = "6.5"
        d.unbillable = [UnbillableDraft(), UnbillableDraft(reasonID: Self.reason, hoursText: "2")]
        #expect(Self.messages(d) == ["Billable and unbillable hours are more than the 8 h between the readings."])
        d.billableText = "6"
        guard case let .success(values) = DailyReportRules.check(d, photos: 0, evidenceRequired: false) else { Issue.record("invalid"); return }
        #expect(values.billable == 6 && values.unbillable == [UnbillableLineIn(reasonID: Self.reason, hours: 2)] && values.note == nil)
        // A backwards pair has no local total: the server decides.
        var backwards = Self.draft(from: "108", to: "100")
        backwards.billableText = "50"
        #expect(Self.messages(backwards).isEmpty)
    }

    @Test func changeoverProblems() {
        #expect(ChangeoverRules.problem(customerID: nil, jobID: nil, jobRequired: false) == T.changeoverErrorCustomer)
        #expect(ChangeoverRules.problem(customerID: Self.reason, jobID: nil, jobRequired: true) == T.changeoverErrorJob)
        #expect(ChangeoverRules.problem(customerID: Self.reason, jobID: nil, jobRequired: false) == nil)
        #expect(ChangeoverRules.problem(customerID: Self.reason, jobID: Self.other, jobRequired: true) == nil)
    }

    @Test func nextJobsOffered() {
        #expect(ChangeoverRules.jobOffered(.pendingApproval))
        #expect(!ChangeoverRules.jobOffered(.approved) && !ChangeoverRules.jobOffered(.inProgress) && !ChangeoverRules.jobOffered(.completed))
    }

    static func changeoverJob(_ id: UUID, number: String, customer: UUID = reason, name: String = "Acme", status: String = "PENDING_APPROVAL",
                              machine: UUID = SyncFixtures.machineID, revision: Int = 5) -> [String: Any] {
        ["id": id.lowercased, "job_number": number, "machine_id": machine.lowercased, "customer_id": customer.lowercased,
         "customer_name": name, "status": status, "sync_revision": revision]
    }

    static func syncedReason(_ id: UUID, _ name: String, active: Bool = true, revision: Int = 5) -> [String: Any] {
        ["id": id.lowercased, "code": name.uppercased(), "name": name, "description": NSNull(), "is_active": active, "sync_revision": revision]
    }

    @Test func changeoverJobsSyncAndLeaveOnceTheyNoLongerApply() async throws {
        let h = try SyncHarness()
        let waiting = UUID(), approved = UUID(), elsewhere = UUID(), other = Self.other
        h.server.mutate {
            $0.capabilities = Self.all + [SyncCapability.changeoverJobs]
            $0.changeoverJobs = [Self.changeoverJob(waiting, number: "J-2"), Self.changeoverJob(approved, number: "J-1", status: "APPROVED"),
                                 Self.changeoverJob(elsewhere, number: "J-3", machine: UUID()),
                                 Self.changeoverJob(other, number: "J-4", customer: Self.opening, name: "Beta")]
        }
        let directory = AccountabilityDirectory(store: h.store, tenantID: SyncFixtures.tenant, owner: nil)
        let engine = h.engine()
        _ = try await engine.sync()
        #expect(directory.changeoverJobs.count == 4)
        let machine = SyncFixtures.machineID, running = SyncFixtures.jobID
        #expect(ChangeoverRules.nextJobs(directory.changeoverJobs, machineID: machine, customerID: Self.reason, excluding: running).map(\.id) == [waiting])
        let customers = ChangeoverRules.nextCustomers(directory.changeoverJobs, machineID: machine, excluding: running)
        #expect(Set(customers.map(\.name)) == ["Acme", "Beta"])
        // A delta with another status drops the job from the choices.
        h.server.mutate { $0.changeoverJobs = [Self.changeoverJob(waiting, number: "J-2", status: "CANCELLED", revision: 9)] }
        _ = try await engine.sync(force: true)
        #expect(ChangeoverRules.nextJobs(directory.changeoverJobs, machineID: machine, customerID: Self.reason, excluding: running).isEmpty)
        #expect(!directory.changeoverJobs.contains { $0.id == waiting })
    }

    @Test func unbillableReasonsSyncAndDeactivationsLeaveTheForm() async throws {
        let h = try SyncHarness()
        h.server.mutate {
            $0.capabilities = Self.all + [SyncCapability.unbillableReasons]
            $0.unbillableReasons = [Self.syncedReason(Self.reason, "Rain"), Self.syncedReason(Self.other, "Breakdown")]
        }
        let directory = AccountabilityDirectory(store: h.store, tenantID: SyncFixtures.tenant, owner: nil)
        let engine = h.engine()
        _ = try await engine.sync()
        #expect(directory.unbillableReasons.map(\.name) == ["Breakdown", "Rain"])
        h.server.mutate { $0.unbillableReasons = [Self.syncedReason(Self.other, "Breakdown", active: false, revision: 9)] }
        _ = try await engine.sync(force: true)
        #expect(directory.unbillableReasons.map(\.name) == ["Rain"])
    }

    @Test func aMissingListKeepsTheLastOnlineReasons() throws {
        let h = try SyncHarness()
        let saved = [EngineHourReasonDTO(id: Self.reason, kind: EngineHourReasonKinds.unbillable, code: "RAIN", name: "Rain", description: nil, isActive: true)]
        try SavedOnline.write(SavedOnline(value: saved, forbidden: false, fetchedAt: Date()), h.store, SyncFixtures.tenant, AccountabilityKey.unbillableReasons)
        #expect(AccountabilityDirectory(store: h.store, tenantID: SyncFixtures.tenant, owner: nil).unbillableReasons.map(\.name) == ["Rain"])
    }

    @Test func reportDaysAreCutInTheTenantsZone() throws {
        let dar = try #require(TimeZone(identifier: "Africa/Dar_es_Salaam")), utc = try #require(TimeZone(identifier: "UTC"))
        // 22:30 UTC on 7 Nov is already 8 Nov at 01:30 in Dar es Salaam.
        let at = try #require(AssetaJSON.parseInstant("2026-11-07T22:30:00Z"))
        #expect(DailyReportRules.localDay(at, timeZone: dar) == "2026-11-08" && DailyReportRules.localDay(at, timeZone: utc) == "2026-11-07")
        #expect(DailyReportRules.recentDays(now: at, timeZone: dar) == ["2026-11-08", "2026-11-07", "2026-11-06"])
        let (start, end) = try #require(DailyReportRules.dayBounds("2026-11-08", timeZone: dar))
        #expect(start == AssetaJSON.parseInstant("2026-11-07T21:00:00Z") && end == AssetaJSON.parseInstant("2026-11-08T21:00:00Z"))
        #expect(DailyReportRules.dayBounds("not-a-day", timeZone: dar) == nil)
    }

    @Test func theTenantsZoneComesFromSyncAndAnOlderServerLeavesItUnknown() async throws {
        let h = try SyncHarness()
        let directory = AccountabilityDirectory(store: h.store, tenantID: SyncFixtures.tenant, owner: nil)
        let engine = h.engine()
        _ = try await engine.sync()
        let device = try #require(TimeZone(identifier: "Europe/Paris"))
        #expect(directory.syncedTenantTimezone == nil && directory.reportTimeZone(device: device) == device)
        h.server.mutate { $0.timezone = "Africa/Dar_es_Salaam" }
        _ = try await engine.sync(force: true)
        #expect(directory.reportTimeZone(device: device).identifier == "Africa/Dar_es_Salaam")
        // A later pull that omits it keeps the zone.
        h.server.mutate { $0.timezone = nil }
        _ = try await engine.sync(force: true)
        #expect(directory.syncedTenantTimezone == "Africa/Dar_es_Salaam")
    }

    @Test func theZoneFallsBackInOrder() throws {
        let device = try #require(TimeZone(identifier: "Europe/Paris"))
        #expect(TenantZone.resolve(["Africa/Dar_es_Salaam", "Africa/Lusaka"], device: device).identifier == "Africa/Dar_es_Salaam")
        #expect(TenantZone.resolve([nil, "Not/AZone", "Africa/Lusaka"], device: device).identifier == "Africa/Lusaka")
        #expect(TenantZone.resolve([nil, nil], device: device) == device)
    }

    @Test func conflictsAreInPlainWordsAndKeptForReview() {
        for code in ["REPORT_READINGS_INVALID", "REPORT_HOURS_EXCEED_TOTAL", "REPORT_ID_CONFLICT", "REPORT_NOT_SUPERSEDABLE",
                     "REPORT_EVIDENCE_REQUIRED", "CHANGEOVER_NOT_ALLOWED", "CHANGEOVER_SAME_CUSTOMER", "CHANGEOVER_JOB_REQUIRED",
                     "CHANGEOVER_JOB_INVALID"] {
            #expect(FieldAccountabilityTexts.conflictText(code) != nil, "\(code)")
            #expect(PushOutcomeApplier.conflictCodes.contains(code), "\(code)")
        }
        #expect(FieldAccountabilityTexts.conflictText("REASON_NOT_ALLOWED") != nil)
        #expect(FieldAccountabilityTexts.conflictText("SOMETHING_ELSE") == nil)
    }

    @Test func outboxTitles() {
        #expect(FieldAccountabilityTexts.operationTitle(.dailyReport, payload: nil) == "Daily report")
        let payload = JSONValue.object(["kind": .string("DAILY"), "changeover_to_customer_id": .string("x")])
        #expect(FieldAccountabilityTexts.operationTitle(.meterCapture, payload: payload) == "Changeover reading")
        #expect(FieldAccountabilityTexts.operationTitle(.meterCapture, payload: .object(["kind": .string("DAILY")])) == "Daily reading")
    }

    private func gps(_ h: SyncHarness) -> GpsPayload { .fix(latitude: -6.8, longitude: 39.3, accuracyM: 7, capturedAt: h.clock.wallNow) }

    private func reading(_ h: SyncHarness, _ value: String) throws -> ClientOperation {
        try h.recorder.recordDailyReading(machineID: SyncFixtures.machineID, mode: .manual, reading: value, ocr: nil, photo: nil, gps: gps(h),
                                          capturedAt: h.clock.wallNow, snapshot: SyncFixtures.meterSnapshot)
    }

    @Test func aReportWaitsForItsPhotoThenAcksWithTheUploadID() async throws {
        let h = try SyncHarness().withFinanceData()
        h.server.mutate { $0.capabilities = Self.all }
        let engine = h.engine()
        _ = try await engine.sync()
        let photo = try h.evidence.store(Data((0..<1500).map { UInt8($0 % 191) }), fileExtension: "jpg", contentType: "image/jpeg")
        var d = Self.draft()
        d.billableText = "6"
        d.unbillable = [UnbillableDraft(reasonID: Self.reason, hoursText: "1.50")]
        d.note = " Rain stopped work "
        let id = UUID()
        let op = try h.recorder.recordDailyReport(d, evidenceRequired: true, evidence: [photo], at: h.clock.wallNow, reportID: id)
        #expect(op.id == id && op.entityID == id && op.opType == "DAILY_REPORT" && op.entityType == "daily_report")
        let queued = try JSONValue.parse(op.payloadJSON)
        #expect(queued["evidence_upload_ids"] == .array([]) && queued["id"] == nil)
        #expect(queued["report_date"]?.stringValue == "2026-11-08" && queued["billable_hours"]?.stringValue == "6")
        guard case let .array(lines)? = queued["unbillable"] else { Issue.record("no lines"); return }
        #expect(lines.first?["reason_id"]?.stringValue == Self.reason.lowercased && lines.first?["hours"]?.stringValue == "1.5")
        #expect(queued["note"]?.stringValue == "Rain stopped work" && queued["client_created_at"]?.stringValue != nil)
        #expect(try h.store.outbox.readyToSend(tenantID: SyncFixtures.tenant, now: h.clock.wallNow, limit: 10).isEmpty)
        #expect(try h.directoryView.overview().items.first { $0.id == id }?.waitingFor == T.waitingPhotos)
        _ = try await engine.sync(force: true)
        #expect(try h.status(id) == .acked)
        let session = try #require(h.server.read { $0.blobs.keys.first })
        let applied = try #require(h.server.read { $0.appliedPayloads[id] })
        #expect(applied["evidence_upload_ids"] as? [String] == [session.lowercased])
        #expect(h.server.read { $0.blobs.values.first?.purpose } == "DAILY_REPORT_EVIDENCE")
    }

    @Test func aReportIsSavedOncePerFormVisitAndNeedsItsCapability() async throws {
        let h = try SyncHarness().withFinanceData()
        h.server.mutate { $0.capabilities = AccountabilityTests.all }
        _ = try await h.engine().sync()
        let id = UUID()
        #expect(throws: FieldRecorderError.notAllowed(FieldAccountabilityTexts.serverTooOld)) {
            try h.recorder.recordDailyReport(Self.draft(), evidenceRequired: false, evidence: [], reportID: id)
        }
        try AccountabilityTests.supported(h.store, Self.all)
        try h.recorder.recordDailyReport(Self.draft(), evidenceRequired: false, evidence: [], reportID: id)
        #expect(throws: FieldRecorderError.notAllowed(FieldAccountabilityTexts.alreadySaved)) {
            try h.recorder.recordDailyReport(Self.draft(), evidenceRequired: false, evidence: [], reportID: id)
        }
        #expect(throws: FieldRecorderError.invalid(T.errPhoto)) {
            try h.recorder.recordDailyReport(Self.draft(), evidenceRequired: true, evidence: [])
        }
    }

    @Test func aReportWaitsForUnsentReadingsAndRefusesOnesNotAccepted() async throws {
        let h = try SyncHarness().withFinanceData()
        h.server.mutate { $0.capabilities = Self.all }
        _ = try await h.engine().sync()
        let first = try reading(h, "100"), second = try reading(h, "108")
        let op = try h.recorder.recordDailyReport(Self.draft(opening: first.entityID, closing: second.entityID), evidenceRequired: false, evidence: [])
        #expect(Set(op.dependencies) == [first.id, second.id])
        // A reading the server refused cannot back a report.
        let third = try reading(h, "120")
        try h.store.outbox.markSent(id: third.id)
        try h.store.outbox.markConflict(id: third.id, code: "READING_NOT_ALLOWED", message: "no", resultJSON: "{}")
        #expect(throws: FieldRecorderError.notAllowed(T.readingNotAccepted)) {
            try h.recorder.recordDailyReport(Self.draft(opening: first.entityID, closing: third.entityID), evidenceRequired: false, evidence: [])
        }
    }

    private func running(_ h: SyncHarness) throws -> JobDTO {
        let json = SyncFixtures.job(status: "IN_PROGRESS")
        return try AssetaJSON.decoder().decode(JobDTO.self, from: JSONSerialization.data(withJSONObject: json))
    }

    @Test func aChangeoverIsADailyReadingOnTheRunningJob() async throws {
        let h = try SyncHarness().withFinanceData()
        h.server.mutate { $0.capabilities = Self.all }
        _ = try await h.engine().sync()
        let job = try running(h)
        let op = try h.recorder.recordChangeover(job: job, toCustomerID: Self.reason, toJobID: Self.other, jobRequired: true, mode: .manual,
                                                 reading: "150", ocr: nil, photo: nil, gps: gps(h), capturedAt: h.clock.wallNow,
                                                 snapshot: SyncFixtures.meterSnapshot)
        let payload = try JSONValue.parse(op.payloadJSON)
        #expect(op.opType == "METER_CAPTURE" && payload["kind"]?.stringValue == "DAILY")
        #expect(payload["job_id"]?.stringValue == SyncFixtures.jobID.lowercased && payload["machine_id"] == nil)
        #expect(payload["changeover_to_customer_id"]?.stringValue == Self.reason.lowercased)
        #expect(payload["changeover_to_job_id"]?.stringValue == Self.other.lowercased)
    }

    @Test func aChangeoverNeedsARunningJobTheCapabilityAndTheNextCustomer() async throws {
        let h = try SyncHarness().withFinanceData()
        h.server.mutate { $0.capabilities = Self.all }
        _ = try await h.engine().sync()
        func record(_ job: JobDTO, customer: UUID? = Self.reason, jobRequired: Bool = false) throws {
            try h.recorder.recordChangeover(job: job, toCustomerID: customer, toJobID: nil, jobRequired: jobRequired, mode: .manual, reading: "150",
                                            ocr: nil, photo: nil, gps: gps(h), capturedAt: h.clock.wallNow, snapshot: SyncFixtures.meterSnapshot)
        }
        #expect(throws: FieldRecorderError.notAllowed(T.changeoverNotRunning)) { try record(SyncFixtures.jobDTO) }
        #expect(throws: FieldRecorderError.notAllowed(T.changeoverErrorCustomer)) { try record(try running(h), customer: nil) }
        #expect(throws: FieldRecorderError.notAllowed(T.changeoverErrorJob)) { try record(try running(h), jobRequired: true) }
        try AccountabilityTests.supported(h.store, AccountabilityTests.all)
        #expect(throws: FieldRecorderError.notAllowed(FieldAccountabilityTexts.serverTooOld)) { try record(try running(h)) }
    }

    static func report(_ id: UUID, status: String = "SUBMITTED", day: String = "2026-11-07", by: UUID? = nil) throws -> DailyReportDTO {
        let json = """
        {"id":"\(id.uuidString.lowercased())","machine_id":"\(SyncFixtures.machineID.uuidString.lowercased())","machine_code":"EX-07",
         "report_date":"\(day)","opening_ref":"\(opening.uuidString.lowercased())","closing_ref":"\(closing.uuidString.lowercased())",
         "opening_reading":"100.0","closing_reading":"108.0","total_hours":"8.00","billable_hours":"6.00","unbillable_hours":"2.00",
         "difference_hours":"0.00","unbillable":[],"allocations":[],"note":null,"evidence_attachment_ids":[],"status":"\(status)","source":"SYNC",
         "policy_version":"v1","duplicate_of_id":null,"is_late":false,"supersedes_id":null,"submitted_at":"2026-11-07T18:00:00Z",
         "submitted_by":\(by.map { "\"\($0.uuidString.lowercased())\"" } ?? "null"),"client_created_at":"2026-11-07T17:59:00Z",
         "reviewed_at":null,"reviewed_by":null,"review_note":null}
        """
        return try AssetaJSON.decoder().decode(DailyReportDTO.self, from: Data(json.utf8))
    }

    @Test func theListMergesServerCopiesWithUnsentReports() async throws {
        let h = try SyncHarness().withFinanceData()
        h.server.mutate { $0.capabilities = Self.all }
        _ = try await h.engine().sync()
        let sentID = UUID(), localID = UUID()
        let sent = try h.recorder.recordDailyReport(Self.draft(), evidenceRequired: false, evidence: [], reportID: sentID)
        let unsent = try h.recorder.recordDailyReport(Self.draft(), evidenceRequired: false, evidence: [], reportID: localID)
        let rows = DailyReportRow.merge(server: [try Self.report(sentID, status: "RETURNED")], ops: [sent, unsent])
        #expect(rows.map(\.id) == [localID, sentID])
        #expect(rows[0].statusText == T.statusWaiting && rows[0].server == nil && !rows[0].returned)
        #expect(rows[1].returned && rows[1].statusText == "Sent back" && rows[1].op?.id == sentID)
    }

    @Test func onlyAReturnedReportCanBeSentAgain() throws {
        #expect(DailyReportRules.canResubmit(try Self.report(UUID(), status: "RETURNED")))
        #expect(!DailyReportRules.canResubmit(try Self.report(UUID(), status: "REVIEWED")))
    }

    @Test func reasonsAndPolicyDecodeTolerantly() throws {
        let json = #"[{"id":"e0000000-0000-4000-8000-000000000003","kind":"UNBILLABLE_REASON","code":"RAIN","name":"Rain","description":null,"is_active":true},{"id":"e0000000-0000-4000-8000-000000000004","kind":"UNBILLABLE_REASON","code":"OLD","name":"Old","description":null,"is_active":false},{"id":"e0000000-0000-4000-8000-000000000005","kind":"VARIANCE_REASON","code":"V","name":"V","description":null,"is_active":true}]"#
        let reasons = try AssetaJSON.decoder().decode([EngineHourReasonDTO].self, from: Data(json.utf8))
        #expect(DailyReportRules.pickable(reasons).map(\.name) == ["Rain"])
        let policy = try AssetaJSON.decoder().decode(EngineHoursPolicyValues.self, from: Data(#"{"daily_report_evidence_required":true}"#.utf8))
        #expect(policy.dailyReportEvidenceRequired && !policy.changeoverSplitsBilling && policy.allocationCorrectionRequiresApproval)
    }

    @Test func reportNotificationOpensTheReport() {
        let id = Self.reason
        #expect(InboxLink.from(entity: "daily_report", id: id.lowercased) == .dailyReport(id))
        #expect(InboxLink.from(record: RecordRef(kind: .dailyReport, id: id)) == .dailyReport(id))
    }
}
