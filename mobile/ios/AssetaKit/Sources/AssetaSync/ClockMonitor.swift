import Darwin
import Foundation

/// Time sources, injectable for tests.
public protocol ClockSource: Sendable {
    var wallNow: Date { get }
    /// Monotonic nanoseconds that keep counting during sleep and reset at boot.
    var monotonicNanos: UInt64 { get }
    /// Identifies the current boot; changes after a reboot (nil if unavailable).
    var bootSessionID: String? { get }
}

public struct SystemClockSource: ClockSource {
    public init() {}

    public var wallNow: Date { Date() }

    /// `CLOCK_MONOTONIC_RAW` on Darwin is unaffected by wall-clock changes and NTP slewing and keeps
    /// running while asleep (unlike `ProcessInfo.systemUptime`).
    public var monotonicNanos: UInt64 { clock_gettime_nsec_np(CLOCK_MONOTONIC_RAW) }

    public var bootSessionID: String? {
        var size = 0
        guard sysctlbyname("kern.bootsessionuuid", nil, &size, nil, 0) == 0, size > 0 else { return nil }
        var buffer = [UInt8](repeating: 0, count: size)
        guard sysctlbyname("kern.bootsessionuuid", &buffer, &size, nil, 0) == 0 else { return nil }
        return String(decoding: buffer.prefix { $0 != 0 }, as: UTF8.self)
    }
}

/// Last trusted server time and the monotonic instant it was observed at.
public struct ClockReference: Codable, Sendable, Equatable {
    public let serverTime: Date
    public let monotonicNanos: UInt64
    public let bootSessionID: String?

    public init(serverTime: Date, monotonicNanos: UInt64, bootSessionID: String?) {
        self.serverTime = serverTime
        self.monotonicNanos = monotonicNanos
        self.bootSessionID = bootSessionID
    }
}

public enum ClockStatus: Sendable, Equatable {
    /// No usable reference (never synced, or the device rebooted since).
    case unknown
    case consistent(deviationSeconds: Double)
    /// Wall clock disagrees with server time + elapsed monotonic time by more than the threshold.
    case tamperSuspected(deviationSeconds: Double)

    public var isTamperSuspected: Bool { if case .tamperSuspected = self { true } else { false } }
}

/// Local clock tamper alert. Captures always record the *true device time*; this only warns the
/// supervisor (and the server compares `device_now` itself).
public enum ClockMonitor {
    public static let thresholdSeconds: Double = 300

    public static func reference(serverTime: Date, source: any ClockSource) -> ClockReference {
        ClockReference(serverTime: serverTime, monotonicNanos: source.monotonicNanos, bootSessionID: source.bootSessionID)
    }

    /// Server time now, estimated from the reference; nil after a reboot (monotonic clock reset).
    public static func trustedNow(_ reference: ClockReference?, source: any ClockSource) -> Date? {
        guard let reference else { return nil }
        let mono = source.monotonicNanos
        if let boot = reference.bootSessionID, let current = source.bootSessionID, boot != current { return nil }
        guard mono >= reference.monotonicNanos else { return nil } // rebooted (counter restarted)
        return reference.serverTime.addingTimeInterval(Double(mono - reference.monotonicNanos) / 1_000_000_000)
    }

    public static func status(_ reference: ClockReference?, source: any ClockSource,
                              threshold: Double = thresholdSeconds) -> ClockStatus {
        guard let expected = trustedNow(reference, source: source) else { return .unknown }
        let deviation = source.wallNow.timeIntervalSince(expected)
        return abs(deviation) > threshold ? .tamperSuspected(deviationSeconds: deviation) : .consistent(deviationSeconds: deviation)
    }

    /// The later of wall time and trusted time: used for expiry checks so a clock wound back
    /// cannot revive an expired policy snapshot or offline grant.
    public static func enforcementNow(_ reference: ClockReference?, source: any ClockSource) -> Date {
        let wall = source.wallNow
        guard let trusted = trustedNow(reference, source: source) else { return wall }
        return max(wall, trusted)
    }
}
