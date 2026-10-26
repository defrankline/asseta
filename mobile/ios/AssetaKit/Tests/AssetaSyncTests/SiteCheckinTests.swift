import AssetaModel
import AssetaStore
@testable import AssetaSync
import Foundation
import Testing

/// DEC-031 Phase 5 (M3) on the field side: the `SITE_CHECKIN` operation, its gating and the saved schedule. Same rules
/// as Android.
struct SiteCheckinTests {
    static let caps = AccountabilityTests.all + ["OP_SITE_CHECKIN"]
    static let permissions: Set<String> = ["tenant.site_checkin.record"]

    @Test func checkInNeedsCapabilityPermissionAndTheSwitch() {
        let on = FieldAccess(capabilities: Set(Self.caps), permissions: Self.permissions)
        #expect(on.siteCheckin && on.siteCheckinOn)
        #expect(!FieldAccess(capabilities: Set(AccountabilityTests.all), permissions: Self.permissions).siteCheckin)
        #expect(!FieldAccess(capabilities: nil, permissions: Self.permissions).siteCheckin)
        #expect(!FieldAccess(capabilities: Set(Self.caps), permissions: []).siteCheckin)
        let off = FieldAccess(capabilities: Set(Self.caps), permissions: Self.permissions,
                              disabledCapabilities: [TenantCapability.siteCheckin])
        #expect(!off.siteCheckin && !off.siteCheckinOn)
    }

    @Test func checkInIsQueuedWithTheGpsAttemptAsItCame() throws {
        let h = try SyncHarness()
        try AccountabilityTests.supported(h.store, Self.caps)
        let at = Date(timeIntervalSince1970: 1_793_000_000)
        let clientID = UUID()
        let gps = GpsPayload.fix(latitude: -6.8, longitude: 39.28, accuracyM: 12, capturedAt: at)
        let op = try h.recorder.recordSiteCheckin(gps: gps, capturedAt: at, clientID: clientID)
        #expect(op.opType == "SITE_CHECKIN" && op.entityType == "site_checkin" && op.entityID == clientID)
        let p = try JSONValue.parse(op.payloadJSON)
        #expect(p["client_id"]?.stringValue == clientID.lowercased)
        #expect(p["gps"]?["status"]?.stringValue == "FIX" && p["gps"]?["latitude"]?.doubleValue == -6.8)
        #expect(p["job_site_id"] == nil || p["job_site_id"] == .null)
        #expect(throws: FieldRecorderError.notAllowed(FieldAccountabilityTexts.alreadySaved)) {
            try h.recorder.recordSiteCheckin(gps: gps, capturedAt: at, clientID: clientID)
        }
        // A failed attempt goes as such: no coordinates.
        let failed = try h.recorder.recordSiteCheckin(gps: .failed(.permissionDenied), capturedAt: at)
        let q = try JSONValue.parse(failed.payloadJSON)
        #expect(q["gps"]?["status"]?.stringValue == "PERMISSION_DENIED" && q["gps"]?["latitude"] == nil)
        #expect(FieldAccountabilityTexts.operationTitle(.siteCheckin, payload: nil) == SiteCheckinTexts.outbox)
    }

    @Test func checkInNeedsTheServerCapability() throws {
        let h = try SyncHarness()
        try AccountabilityTests.supported(h.store)
        #expect(throws: FieldRecorderError.notAllowed(FieldAccountabilityTexts.serverTooOld)) {
            try h.recorder.recordSiteCheckin(gps: .failed(.timeout), capturedAt: Date())
        }
    }

    @Test func conflictsAreKeptAndWorded() {
        for code in ["SITE_CHECKIN_DISABLED", "CHECKIN_ID_CONFLICT"] {
            let result = OperationResultDTO(id: UUID(), status: .duplicate, error: .object(["code": .string(code)]))
            #expect(PushOutcomeApplier.classify(result) == .conflict(code: code))
            #expect(FieldAccountabilityTexts.conflictText(code) != nil)
        }
    }

    @Test func savedScheduleMergesWithQueuedCheckins() throws {
        let h = try SyncHarness()
        try AccountabilityTests.supported(h.store, Self.caps)
        let queuedID = UUID(), serverOnlyID = UUID()
        _ = try h.recorder.recordSiteCheckin(gps: .failed(.noFix), capturedAt: Date(timeIntervalSince1970: 1_793_100_000),
                                             clientID: queuedID)
        let json = """
        {"required":true,"times":["08:00","14:00"],"window_minutes":60,"max_distance_m":500,"timezone":"Africa/Dar_es_Salaam",
         "day_from":"2026-10-20","day_to":"2026-10-26",
         "slots":[{"scheduled_at":"2026-10-26T05:00:00Z","window_minutes":60,"status":"MADE","checkin_id":"\(UUID().lowercased)",
                   "job_id":null,"job_number":"J-7"},
                  {"scheduled_at":"2026-10-26T11:00:00Z","window_minutes":60,"status":"UPCOMING","checkin_id":null,"job_id":null,
                   "job_number":null},
                  {"scheduled_at":"2026-10-25T11:00:00Z","window_minutes":60,"status":"MISSED"}],
         "checkins":[{"id":"\(UUID().lowercased)","client_id":"\(serverOnlyID.lowercased)","staff_member_id":"\(UUID().lowercased)",
                      "recorded_by":"\(UUID().lowercased)","captured_at":"2026-10-26T05:10:00Z","received_at":"2026-10-26T05:11:00Z",
                      "gps_status":"FIX","latitude":-6.8,"longitude":39.2,"accuracy_m":10,"job_site_id":null,"job_site_name":"North pit",
                      "job_id":null,"job_number":"J-7","distance_m":120.5,"within_distance":true,"source":"SYNC"}]}
        """
        let dto = try AssetaJSON.decoder().decode(MySiteCheckinsDTO.self, from: Data(json.utf8))
        try SavedOnline.write(SavedOnline(value: dto, forbidden: false, fetchedAt: Date()), h.store, SyncFixtures.tenant,
                              AccountabilityKey.siteCheckins)
        let directory = AccountabilityDirectory(store: h.store, tenantID: SyncFixtures.tenant, owner: nil)
        #expect(directory.siteCheckins?.value?.times == ["08:00", "14:00"])
        let items = directory.myCheckins()
        #expect(items.map(\.id) == [queuedID, serverOnlyID])
        #expect(items[0].syncStatus == .pending && items[0].gpsStatus == "NO_FIX")
        #expect(items[1].syncStatus == nil && items[1].withinDistance == true && items[1].jobSiteName == "North pit")
        #expect(SiteCheckinPresentation.state(dto.slots[1], items: items, now: Date(timeIntervalSince1970: 0)) == .upcoming)
        #expect(SiteCheckinPresentation.state(dto.slots[2], items: items, now: Date()) == .missed)
        #expect(SiteCheckinPresentation.state(dto.slots[0], items: items, now: Date()) == .made)
    }

    @Test func rowsSlotsAndJobsLineAsAndroid() throws {
        let h = try SyncHarness()
        try AccountabilityTests.supported(h.store, Self.caps)
        let utc = TimeZone(identifier: "UTC")!
        let slotAt = try #require(AssetaJSON.parseInstant("2026-10-26T05:00:00Z"))
        let queued = try h.recorder.recordSiteCheckin(gps: .failed(.timeout), capturedAt: slotAt.addingTimeInterval(600))
        let json = """
        {"required":true,"times":["08:00"],"window_minutes":60,"max_distance_m":300,"timezone":"UTC","day_from":"2026-10-20",
         "day_to":"2026-10-26","slots":[{"scheduled_at":"2026-10-26T05:00:00Z","window_minutes":60,"status":"DUE"},
                                        {"scheduled_at":"2026-10-26T11:00:00Z","window_minutes":30,"status":"UPCOMING"}],
         "checkins":[{"id":"\(UUID().lowercased)","client_id":"\(UUID().lowercased)","staff_member_id":"\(UUID().lowercased)",
                      "recorded_by":"\(UUID().lowercased)","captured_at":"2026-10-25T05:10:00Z","received_at":"2026-10-25T05:11:00Z",
                      "gps_status":"FIX","latitude":-6.8,"longitude":39.2,"accuracy_m":10,"job_site_id":null,"job_site_name":null,
                      "job_id":null,"distance_m":420.4,"within_distance":false,"source":"SYNC"}]}
        """
        let dto = try AssetaJSON.decoder().decode(MySiteCheckinsDTO.self, from: Data(json.utf8))
        let directory = AccountabilityDirectory(store: h.store, tenantID: SyncFixtures.tenant, owner: nil)
        #expect(SiteCheckinPresentation.jobsSubtitle(nil, items: [], now: slotAt) == SiteCheckinTexts.never)
        // Before the check-in: due until 06:00.
        #expect(SiteCheckinPresentation.jobsSubtitle(dto, items: [], now: slotAt) == "Check-in due now, until 06:00")
        let items = directory.myCheckins()
        let today = SiteCheckinPresentation.today(dto, items: items, now: slotAt.addingTimeInterval(900))
        #expect(today.map(\.state) == [.saved, .upcoming] && today[0].window == "Between 04:00 and 06:00" && today[0].time == "05:00")
        #expect(SiteCheckinPresentation.jobsSubtitle(dto, items: items, now: slotAt.addingTimeInterval(900)) == "Next check-in at 11:00")
        #expect(SiteCheckinPresentation.jobsSubtitle(dto, items: items, now: slotAt.addingTimeInterval(8 * 3600)) == SiteCheckinTexts.noneLeft)
        try SavedOnline.write(SavedOnline(value: dto, forbidden: false, fetchedAt: slotAt), h.store, SyncFixtures.tenant,
                              AccountabilityKey.siteCheckins)
        let rows = SiteCheckinPresentation.rows(directory.myCheckins(), timeZone: utc)
        #expect(rows.count == 2)
        #expect(rows[0].id == queued.entityID && rows[0].value == "" && rows[0].caption == "Waiting to sync" && rows[0].tone == .info)
        #expect(rows[1].label == "25 Oct 2026, 05:10" && rows[1].value == "No site")
        #expect(rows[1].caption == "420 m from the site · Further from the site than allowed" && rows[1].tone == .warning)
        #expect(SiteCheckinPresentation.footer(dto, savedAt: slotAt, timeZone: utc).hasSuffix(
            "Check in within 300 m of the site. Schedule from 26 Oct 2026, 05:00. Connect to update it."))
    }

    @Test func unbilledWorkNotificationOpensTheJob() {
        let id = UUID()
        #expect(InboxLink.from(record: RecordRef(kind: .job, id: id)) == .job(id))
    }
}
