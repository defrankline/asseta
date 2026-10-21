import Foundation

/// Exponential backoff with jitter for network failures and 5xx/429: the n-th consecutive failure
/// waits `min(maxDelay, base · 2^(n-1))`, scaled by a random factor in [0.5, 1.0) so many devices
/// coming back online at once do not retry in lockstep.
public struct Backoff: Sendable, Equatable {
    public let base: TimeInterval
    public let maxDelay: TimeInterval

    public init(base: TimeInterval = 2, maxDelay: TimeInterval = 15 * 60) {
        self.base = base
        self.maxDelay = maxDelay
    }

    public func ceiling(failures: Int) -> TimeInterval {
        guard failures > 0 else { return 0 }
        let exponent = min(failures - 1, 30)
        return min(maxDelay, base * pow(2, Double(exponent)))
    }

    /// `unitRandom` must return a value in [0, 1).
    public func delay(failures: Int, unitRandom: Double) -> TimeInterval {
        ceiling(failures: failures) * (0.5 + 0.5 * min(max(unitRandom, 0), 0.999_999))
    }
}
