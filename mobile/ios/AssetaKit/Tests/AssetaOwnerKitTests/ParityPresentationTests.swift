@testable import AssetaOwnerKit
import AssetaModel
import Foundation
import Testing

/// Wording and rules that must match the Android Owner app exactly. Android's `ParityPresentationTest` asserts the
/// same strings for the same inputs; change both together.
struct ParityPresentationTests {
    let now = AssetaJSON.parseInstant("2026-10-22T08:10:00Z")!

    func overview() throws -> TenantOverviewDTO {
        try AssetaJSON.decoder().decode(TenantOverviewDTO.self, from: Data("""
        {"tenant_id":"\(Samples.tenant)","as_of":"2026-10-22T08:00:00Z","timezone":"UTC",
         "fleet":{"machines":5,"connectivity":{"live":2,"recent":1,"stale":1,"offline":1,"never":0,"no_tracker":0},
           "engine_on_verified":2,"open_alerts":{"critical":1,"warning":2,"info":0},"reported_work_state":{"WORKING":3},
           "latest_source_at":"2026-10-22T08:05:00Z"},
         "work":{"jobs_by_status":{"APPROVED":1,"IN_PROGRESS":2},"pending_approvals":1,"open_exceptions":0,
           "readings_needing_review":2},
         "money":{"month_start":"2026-10-01","currencies":[]},
         "risk":{"open_cases":{"critical":0,"warning":1,"info":0},"signals_last_7_days":{"critical":0,"warning":0,"info":3}}}
        """.utf8))
    }

    /// Android `NavigationChromeTest`: same badge text for the same unread counts.
    @Test func unreadBadgeHidesZeroAndCapsAt99() {
        #expect(OwnerFormat.badge(nil) == nil)
        #expect(OwnerFormat.badge(0) == nil)
        #expect(OwnerFormat.badge(-3) == nil)
        #expect(OwnerFormat.badge(7) == "7")
        #expect(OwnerFormat.badge(99) == "99")
        #expect(OwnerFormat.badge(100) == "99+")
    }

    @Test func overviewSectionsLabelsAndLinks() throws {
        let o = try overview()
        let sections = OverviewPresentation.sections(o, cached: false, now: now)
        #expect(sections.map(\.title) == ["Fleet", "Jobs and work", "Money (month from 2026-10-01)", "Investigations and signals"])
        let fleet = sections[0].groups[0].rows
        #expect(fleet.map(\.label) == ["Machines", "Live now", "Recent", "Stale", "Offline", "Never reported", "No tracker",
                                       "Engine on (tracker verified)", "Reported working", "Open alerts"])
        let alerts = try #require(fleet.last)
        #expect(alerts.value == "3" && alerts.detail == "1 critical · 2 warning · 0 info")
        #expect(alerts.tone == .critical && alerts.route == .alerts)
        #expect(sections[0].freshness == "Source data updated 5 min ago")
        #expect(sections[1].groups[0].rows.map(\.label)
            == ["In progress", "Approved", "Pending approvals", "Readings needing review", "Open meter exceptions"])
        #expect(sections[2].emptyText == "No financial activity this month.")
        #expect(sections[3].groups[0].rows.map(\.label) == ["Open investigations", "Signals (last 7 days)"])
        #expect(sections[3].freshness == "No source data yet")
        #expect(OverviewPresentation.asOf(o) == "Figures as of 22 Oct 2026, 08:00 (UTC)")
        #expect(OverviewPresentation.sections(o, cached: true, now: now)[0].groups[0].rows[1].label == "Live when saved")
    }

    func machine(alerts: Int, code: String, lastMessage: String?) throws -> MachineMapDTO {
        try AssetaJSON.decoder().decode(MachineMapDTO.self, from: Data("""
        {"machine_id":"\(Samples.machine)","asset_code":"\(code)","name":"Excavator","machine_status":"ACTIVE",
         "connectivity":"OFFLINE","is_live":false,"observed_engine":"OFF","observed_motion":"STATIONARY",
         "reported_work_status":"IDLE","location_compliance":"UNKNOWN","open_alerts":\(alerts),"policy_version":"p",
         "operator":"Ali","supervisor":"Neema","last_message_at":\(lastMessage.map { "\"\($0)\"" } ?? "null"),
         "last_seen_age_seconds":\(lastMessage == nil ? "null" : "120")}
        """.utf8))
    }

    @Test func fleetRowsReadAndSortLikeAndroid() throws {
        let b = try machine(alerts: 0, code: "B-2", lastMessage: "2026-10-22T08:00:00Z")
        let c = try machine(alerts: 2, code: "C-3", lastMessage: "2026-10-01T00:00:00Z")
        let a = try machine(alerts: 0, code: "A-1", lastMessage: nil)
        #expect(FleetPresentation.sorted([b, c, a]).map(\.assetCode) == ["C-3", "B-2", "A-1"])
        let at = AssetaJSON.parseInstant("2026-10-22T08:02:00Z")!
        #expect(FleetPresentation.title(b) == "B-2 · Excavator")
        #expect(FleetPresentation.detailLine(b, dataIsCached: false, now: at) == "Last seen 2 min ago · engine off · stationary")
        #expect(FleetPresentation.detailLine(a, dataIsCached: false, now: at) == "Never seen · engine off · stationary")
        #expect(FleetPresentation.reportedLine(b) == "Reported: Idle · operator Ali")
        #expect(FleetPresentation.alertsLine(2) == "2 open alerts")
        #expect(FleetPresentation.unplacedNote(0) == nil)
        #expect(FleetPresentation.unplacedNote(1) == "1 machine has no known position (see List).")
        #expect(FleetPresentation.unplacedNote(3) == "3 machines have no known position (see List).")
        #expect(FleetPresentation.statusLabel(b, dataIsCached: false, now: at) == "Offline")
    }

    @Test func tabsAndMoreFollowTheRole() {
        let fleetOnly = OwnerFeatures(permissions: ["tenant.fleet.read"])
        #expect(fleetOnly.tabs == [.overview, .fleet, .alerts, .more])
        let inboxOnly = OwnerFeatures(permissions: ["tenant.notification.read"])
        #expect(inboxOnly.tabs == [.more])
        #expect(inboxOnly.moreEntries == ["Notifications", "Settings"])
        #expect(!inboxOnly.allows(.investigations) && fleetOnly.allows(.alerts))
    }

    @Test func listFiltersOrderingAndDecisionRules() throws {
        #expect(JobsPresentation.filters.map(\.1) == ["In progress", "Approved", "Pending approval", "Completed", "Cancelled", "All"])
        #expect(JobsPresentation.defaultFilter == .inProgress)
        #expect(AlertText.filters.map(\.1) == ["Open", "Acknowledged", "Resolved", "All"])
        let decoder = AssetaJSON.decoder()
        let info = try decoder.decode(AlertDTO.self, from: Data(Samples.alertJSON(severity: "INFO").utf8))
        let critical = try decoder.decode(AlertDTO.self, from: Data(Samples.alertJSON(severity: "CRITICAL").utf8))
        #expect(AlertText.sorted([info, critical]).map(\.severity) == [.critical, .info])
        #expect(AlertText.evidence(.string("Site A")) == "Site A" && AlertText.evidence(.bool(true)) == "Yes")
        #expect(ApprovalText.canDecide(approve: true, note: ""))
        #expect(!ApprovalText.canDecide(approve: false, note: "  "))
        #expect(RoutingMatrix.label("ACTION") == "Needs your action")
        #expect(SettingsText.pushStatus(available: true, registered: false, tenantName: "Acme") == "Not registered yet")
        #expect(OwnerFormat.humanize("TRACKER_OFFLINE") == "Tracker offline")
        let utc = TimeZone(identifier: "UTC")!
        #expect(OwnerFormat.stamp(AssetaJSON.parseInstant("2026-10-21T14:05:00Z")!, timeZone: utc) == "21 Oct 2026, 14:05")
    }

    @Test func listRoutesFromConsolePaths() {
        #expect(DeepLinkParser.route(path: "/tenant/cases") == .investigations)
        #expect(DeepLinkParser.route(path: "/tenant/jobs") == .jobs)
        #expect(DeepLinkParser.route(path: "/tenant/fleet") == .fleet)
        #expect(!OwnerRoute.fleet.identifiesRecord)
    }

    @Test func ownerOnlyDTOsDecode() throws {
        let decoder = AssetaJSON.decoder()
        let machine = try decoder.decode(OwnerMachineDTO.self, from: Data("""
        {"id":"\(Samples.machine)","asset_code":"EX-01","name":"Excavator","status":"ACTIVE","ownership":"OWNED",
         "manufacturer":"CAT","model":"320","year_of_manufacture":2019,"meter_decimal_places":1,"version":1,
         "created_at":"2026-01-01T00:00:00Z","category_id":null,"operating_area_id":null,"serial_number":null,
         "capacity_value":null,"capacity_unit":null}
        """.utf8))
        #expect(machine.modelLine == "CAT 320 2019")
        let expense = try decoder.decode(ExpenseDTO.self, from: Data("""
        {"id":"\(Samples.job)","amount":"150000.0000","currency":"TZS","description":"Fuel","status":"SUBMITTED",
         "incurred_at":"2026-10-22T08:00:00Z","paid_from":"PETTY_CASH","supplier":null,
         "receipt_attachment_ids":["\(Samples.machine)"]}
        """.utf8))
        #expect(expense.receiptAttachmentIDs.count == 1 && expense.supplier == nil)
        let ack = try decoder.decode(AcknowledgementDTO.self, from: Data("""
        {"id":"\(Samples.job)","method":"SIGNATURE","signer_name":"Juma","signer_phone":null,
         "signature_attachment_id":null,"acknowledged_hours":"8.5000","captured_at":"2026-10-22T08:00:00Z"}
        """.utf8))
        #expect(ack.signerName == "Juma" && OwnerFormat.hours(ack.acknowledgedHours, locale: Locale(identifier: "en_US")) == "8.5 h")
    }
}
