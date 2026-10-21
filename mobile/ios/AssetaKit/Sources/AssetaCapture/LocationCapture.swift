import AssetaModel
import CoreLocation
import Foundation

/// Pure bookkeeping for one GPS attempt, separated from CoreLocation so the rules are testable:
/// only fixes produced *after* the attempt started count (never a cached or earlier location),
/// the most accurate fresh fix wins, and a failed attempt never carries coordinates.
public struct GpsAttempt: Sendable {
    public let startedAt: Date
    public let goodEnoughAccuracyM: Double
    private(set) var best: (latitude: Double, longitude: Double, accuracy: Double, timestamp: Date)?
    private(set) var sawLocationUnknown = false
    private(set) var finalStatus: GpsStatus?

    public init(startedAt: Date, goodEnoughAccuracyM: Double = 10) {
        self.startedAt = startedAt
        self.goodEnoughAccuracyM = goodEnoughAccuracyM
    }

    /// Returns true when the attempt can stop early (accurate enough).
    public mutating func record(latitude: Double, longitude: Double, horizontalAccuracy: Double, timestamp: Date) -> Bool {
        guard horizontalAccuracy >= 0, timestamp >= startedAt.addingTimeInterval(-0.5),
              (-90...90).contains(latitude), (-180...180).contains(longitude) else { return false }
        if best == nil || horizontalAccuracy < best!.accuracy {
            best = (latitude, longitude, horizontalAccuracy, timestamp)
        }
        return horizontalAccuracy <= goodEnoughAccuracyM
    }

    public mutating func recordLocationUnknown() { sawLocationUnknown = true }
    public mutating func recordDenied() { finalStatus = .permissionDenied }
    public mutating func recordDisabled() { finalStatus = .disabled }

    /// Final result when the attempt ends (early, on error, or at the timeout).
    public func result() -> GpsPayload {
        if let status = finalStatus { return .failed(status) }
        if let best {
            return .fix(latitude: best.latitude, longitude: best.longitude, accuracyM: best.accuracy,
                        capturedAt: best.timestamp)
        }
        return .failed(sawLocationUnknown ? .noFix : .timeout)
    }
}

/// One-shot, foreground-only GPS fix for a capture (when-in-use permission, requested just in
/// time; no background location). Every capture calls ``captureFix(timeout:)`` afresh.
@MainActor
public final class LocationCapturer: NSObject, CLLocationManagerDelegate {
    private let manager = CLLocationManager()
    private var attempt: GpsAttempt?
    private var continuation: CheckedContinuation<GpsPayload, Never>?
    private var authorizationContinuation: CheckedContinuation<Void, Never>?
    private var timeoutTask: Task<Void, Never>?

    public override init() {
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyBest
        manager.distanceFilter = kCLDistanceFilterNone
    }

    public func captureFix(timeout: TimeInterval = 20) async -> GpsPayload {
        guard continuation == nil else { return .failed(.noFix) }
        if manager.authorizationStatus == .notDetermined {
            await withCheckedContinuation { authorizationContinuation = $0; manager.requestWhenInUseAuthorization() }
        }
        switch manager.authorizationStatus {
        case .denied, .restricted: return .failed(.permissionDenied)
        case .notDetermined: return .failed(.permissionDenied)
        default: break
        }
        guard CLLocationManager.locationServicesEnabled() else { return .failed(.disabled) }
        attempt = GpsAttempt(startedAt: Date())
        return await withCheckedContinuation { continuation in
            self.continuation = continuation
            manager.startUpdatingLocation()
            timeoutTask = Task { [weak self] in
                try? await Task.sleep(for: .seconds(timeout))
                self?.finish()
            }
        }
    }

    private func finish() {
        manager.stopUpdatingLocation()
        timeoutTask?.cancel()
        timeoutTask = nil
        let result = attempt?.result() ?? .failed(.noFix)
        attempt = nil
        continuation?.resume(returning: result)
        continuation = nil
    }

    nonisolated public func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        let determined = manager.authorizationStatus != .notDetermined
        Task { @MainActor in
            guard determined else { return }
            self.authorizationContinuation?.resume()
            self.authorizationContinuation = nil
        }
    }

    nonisolated public func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        let samples = locations.map {
            ($0.coordinate.latitude, $0.coordinate.longitude, $0.horizontalAccuracy, $0.timestamp)
        }
        Task { @MainActor in
            guard self.attempt != nil else { return }
            var done = false
            for sample in samples {
                done = self.attempt!.record(latitude: sample.0, longitude: sample.1, horizontalAccuracy: sample.2,
                                            timestamp: sample.3) || done
            }
            if done { self.finish() }
        }
    }

    nonisolated public func locationManager(_ manager: CLLocationManager, didFailWithError error: any Error) {
        let code = (error as? CLError)?.code
        Task { @MainActor in
            guard self.attempt != nil else { return }
            switch code {
            case .denied: self.attempt!.recordDenied(); self.finish()
            case .locationUnknown: self.attempt!.recordLocationUnknown() // transient: keep trying until timeout
            default: self.attempt!.recordLocationUnknown()
            }
        }
    }
}
