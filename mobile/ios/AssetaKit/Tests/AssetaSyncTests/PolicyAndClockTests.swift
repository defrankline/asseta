import AssetaModel
import AssetaStore
@testable import AssetaSync
import Foundation
import Testing

struct PolicySnapshotTests {
    let machine = SyncFixtures.machineID
    let t0 = Date(timeIntervalSince1970: 1_792_000_000)

    func snapshot(_ scope: String, opening: CaptureMode = .automatic, validFor: TimeInterval = 3600) -> MeterPolicySnapshot {
        MeterPolicySnapshot(scopeKey: scope, versionIDs: [UUID()], versionStamp: scope,
                            policy: MeterCapturePolicy(openingMode: opening, closingMode: .manual, manualPhotoRequired: false,
                                                       minOCRConfidence: 0.85, maxRecaptureAttempts: 2),
                            validUntil: t0.addingTimeInterval(validFor))
    }

    @Test func machineSnapshotWinsOverTenant() {
        let tenant = snapshot("tenant"), specific = snapshot("machine:\(machine.lowercased)", opening: .manual)
        #expect(PolicySelection.select([tenant, specific], machineID: machine) == specific)
        #expect(PolicySelection.select([tenant, snapshot("machine:\(UUID().lowercased)")], machineID: machine) == tenant)
        #expect(PolicySelection.select([], machineID: machine) == nil)
    }

    @Test func gateBlocksWithoutSnapshotWhenExpiredOrPastOfflineGrant() {
        let s = snapshot("tenant")
        #expect(CaptureGate.evaluate(snapshot: nil, offlineGrantUntil: nil, now: t0) == .blocked(.noSnapshot))
        #expect(CaptureGate.evaluate(snapshot: s, offlineGrantUntil: t0.addingTimeInterval(60), now: t0) == .allowed(s))
        #expect(CaptureGate.evaluate(snapshot: s, offlineGrantUntil: nil, now: t0.addingTimeInterval(3601))
                == .blocked(.snapshotExpired(validUntil: s.validUntil)))
        let grant = t0.addingTimeInterval(10)
        #expect(CaptureGate.evaluate(snapshot: s, offlineGrantUntil: grant, now: t0.addingTimeInterval(11))
                == .blocked(.offlineGrantExpired(until: grant)))
        #expect(CaptureBlockReason.noSnapshot.message.hasPrefix("Connect to refresh rules"))
    }

    @Test func windingTheClockBackDoesNotReviveAnExpiredSnapshot() {
        let clock = TestClock(t0)
        let reference = ClockMonitor.reference(serverTime: t0, source: clock)
        clock.advance(7200)                        // two hours really pass…
        clock.setWall(t0)                          // …but the user sets the wall clock back
        let now = ClockMonitor.enforcementNow(reference, source: clock)
        #expect(now == t0.addingTimeInterval(7200))
        #expect(CaptureGate.evaluate(snapshot: snapshot("tenant"), offlineGrantUntil: nil, now: now)
                == .blocked(.snapshotExpired(validUntil: t0.addingTimeInterval(3600))))
    }

    @Test func storedSnapshotRoundTripsAndInvalidValuesFailClosed() throws {
        let dto = try AssetaJSON.decoder().decode(PolicySnapshotDTO.self, from: JSONSerialization.data(
            withJSONObject: SyncFixtures.snapshot(scope: "tenant", validUntil: t0)))
        let stored = try MeterPolicySnapshot.stored(dto, receivedAt: t0)
        let decoded = try #require(MeterPolicySnapshot(stored))
        #expect(decoded.policy.openingMode == .automatic)
        #expect(decoded.policy.minOCRConfidence == 0.85)
        #expect(decoded.versionIDs == [SyncFixtures.versionID])
        let broken = StoredPolicySnapshot(policyType: "METER_CAPTURE", scopeKey: "tenant", versionIDsJSON: "[]",
                                          versionStamp: "x", valuesJSON: #"{"opening_mode":"MAGIC"}"#, validUntil: t0, receivedAt: t0)
        #expect(MeterPolicySnapshot(broken) == nil)
    }
}

struct ClockTamperTests {
    let t0 = Date(timeIntervalSince1970: 1_792_000_000)

    @Test func consistentClockIsNotFlagged() {
        let clock = TestClock(t0.addingTimeInterval(30)) // device 30 s ahead of the server
        let reference = ClockMonitor.reference(serverTime: t0, source: clock)
        clock.advance(3 * 3600)
        #expect(ClockMonitor.status(reference, source: clock) == .consistent(deviationSeconds: 30))
    }

    @Test func wallClockMovedBeyondThresholdIsFlaggedBothWays() {
        let clock = TestClock(t0)
        let reference = ClockMonitor.reference(serverTime: t0, source: clock)
        clock.advance(600)
        clock.setWall(t0.addingTimeInterval(600 + 301))
        #expect(ClockMonitor.status(reference, source: clock).isTamperSuspected)
        clock.setWall(t0.addingTimeInterval(600 - 3600))
        #expect(ClockMonitor.status(reference, source: clock) == .tamperSuspected(deviationSeconds: -3600))
        clock.setWall(t0.addingTimeInterval(600 + 299))
        #expect(!ClockMonitor.status(reference, source: clock).isTamperSuspected)
    }

    @Test func rebootInvalidatesTheReference() {
        let clock = TestClock(t0)
        let reference = ClockMonitor.reference(serverTime: t0, source: clock)
        clock.reboot()
        clock.setWall(t0.addingTimeInterval(-86400))
        #expect(ClockMonitor.status(reference, source: clock) == .unknown)
        #expect(ClockMonitor.trustedNow(reference, source: clock) == nil)
        #expect(ClockMonitor.status(nil, source: clock) == .unknown)
    }

    @Test func systemClockSourceIsMonotonic() {
        let source = SystemClockSource()
        let a = source.monotonicNanos, b = source.monotonicNanos
        #expect(b >= a)
        #expect(source.bootSessionID?.isEmpty == false)
    }
}

struct BackoffTests {
    @Test func exponentialWithCapAndJitterBounds() {
        let backoff = Backoff(base: 2, maxDelay: 60)
        #expect((1...7).map(backoff.ceiling(failures:)) == [2, 4, 8, 16, 32, 60, 60])
        #expect(backoff.ceiling(failures: 0) == 0)
        #expect(backoff.delay(failures: 3, unitRandom: 0) == 4)
        #expect(backoff.delay(failures: 3, unitRandom: 0.999) < 8)
        #expect(backoff.delay(failures: 3, unitRandom: 0.999) > 7.9)
        #expect(backoff.ceiling(failures: 10_000) == 60) // no overflow
    }
}
