import AssetaFleetMap
import AssetaModel
import AssetaNetwork
import Foundation
import Testing

/// Same cases as Android `FleetMapRulesTest`.
struct FleetMapRulesTests {
    static func machine(_ code: String, lat: Double? = -6.8, lon: Double? = 39.2, connectivity: String = "RECENT",
                        isLive: Bool = false, lastMessage: String? = "2026-11-14T08:00:00Z") throws -> MachineMapDTO {
        func json(_ v: Double?) -> String { v.map { "\($0)" } ?? "null" }
        return try AssetaJSON.decoder().decode(MachineMapDTO.self, from: Data("""
        {"machine_id":"\(UUID().uuidString.lowercased())","asset_code":"\(code)","name":"Excavator \(code)",
         "machine_status":"ACTIVE","connectivity":"\(connectivity)","is_live":\(isLive),"observed_engine":"OFF",
         "observed_motion":"STATIONARY","reported_work_status":"WORKING","location_compliance":"UNKNOWN",
         "open_alerts":0,"policy_version":"p","latitude":\(json(lat)),"longitude":\(json(lon)),
         "last_message_at":\(lastMessage.map { "\"\($0)\"" } ?? "null"),"last_seen_age_seconds":\(lastMessage == nil ? "null" : "300")}
        """.utf8))
    }

    static func server(_ status: Int) -> APIError {
        .server(status: status, body: ErrorBody(code: "X", message: "x", correlationID: "c"))
    }

    @Test func switchShowsOnlyWithFleetRead() {
        #expect(FleetMapRules.canShowMap(permissions: ["tenant.meter.write", "tenant.fleet.read"]))
        #expect(!FleetMapRules.canShowMap(permissions: ["tenant.meter.write", "tenant.job.request"]))
        #expect(!FleetMapRules.canShowMap(permissions: [String]()))
    }

    @Test func offlineNeverCallsTheServer() async throws {
        let one = try Self.machine("EX-1")
        var calls = 0
        let state = await FleetMapRules.load(online: false) { calls += 1; return [one] }
        #expect(state == .offline)
        #expect(calls == 0)
    }

    @Test func onlineLoadsEveryMachineTheServerReturns() async throws {
        // Scope ALL: machines that are not in the phone's "My machines" list are shown too (no client-side filter).
        let server = [try Self.machine("EX-1"), try Self.machine("EX-2"), try Self.machine("TR-9")]
        let at = Date(timeIntervalSince1970: 42)
        let state = await FleetMapRules.load(online: true, now: { at }) { server }
        #expect(state == .loaded(server, fetchedAt: at))
    }

    @Test func forbiddenAndNotFoundBecomePlainMessages() async {
        #expect(await FleetMapRules.load(online: true) { throw Self.server(403) } == .failed(FleetMapRules.forbidden))
        #expect(await FleetMapRules.load(online: true) { throw Self.server(404) } == .failed(FleetMapRules.notFound))
        #expect(await FleetMapRules.load(online: true) { throw Self.server(500) } == .failed(FleetMapRules.failed))
        #expect(await FleetMapRules.load(online: true) {
            throw APIError.transport(code: -1009, message: "offline", correlationID: "c")
        } == .failed(FleetMapRules.noConnection))
    }

    @Test func machinesWithoutPositionAreCountedNotPlaced() throws {
        let placed = try Self.machine("EX-1")
        let noFix = try Self.machine("EX-2", lat: nil, lon: nil)
        let half = try Self.machine("EX-3", lat: -6.8, lon: nil)
        let split = FleetMapRules.split([placed, noFix, half])
        #expect(split.placed == [placed])
        #expect(split.unplaced == [noFix, half])
        #expect(FleetMapRules.unplacedNote(split.unplaced.count) == "2 machines have no known position (see List).")
        #expect(FleetMapRules.unplacedNote(1) == "1 machine has no known position (see List).")
        #expect(FleetMapRules.unplacedNote(0) == nil)
    }

    @Test func statusCardLines() throws {
        let now = AssetaJSON.parseInstant("2026-11-14T08:05:00Z")!
        let live = try Self.machine("EX-1", connectivity: "LIVE", isLive: true)
        let s = FleetMapRules.status(live, fetchedAt: now, now: now)
        #expect(s.title == "EX-1 · Excavator EX-1")
        #expect(s.connectivity == "Live")
        #expect(s.lastSeen == "Last seen 5 min ago")
        #expect(s.reported == "Reported: Working")
        // An old response is never shown as live.
        #expect(FleetMapRules.status(live, fetchedAt: now.addingTimeInterval(-600), now: now).connectivity == "Recent")
        #expect(FleetMapRules.status(try Self.machine("EX-1", lastMessage: nil), fetchedAt: now, now: now).lastSeen == "Never seen")
    }
}
