import AssetaModel
import CoreLocation
import Foundation

/// ADR-008: the area of a reading from Apple's reverse geocoder ("Mbezi Beach, Kinondoni, Dar es Salaam"; never a
/// street or street number). Best effort only: offline, no result or after `timeout` it gives nil, and nothing ever
/// waits on it (the capture is saved without a place).
@MainActor
public enum PlaceGeocoder {
    public static let timeout: TimeInterval = 3

    /// The area label of the coordinates, or nil (failed, empty, or slower than `timeout` seconds).
    public static func place(latitude: Double, longitude: Double, timeout: TimeInterval = PlaceGeocoder.timeout) async -> String? {
        let geocoder = CLGeocoder()
        let location = CLLocation(latitude: latitude, longitude: longitude)
        let once = Once()
        return await withCheckedContinuation { (continuation: CheckedContinuation<String?, Never>) in
            once.continuation = continuation
            geocoder.reverseGeocodeLocation(location) { placemarks, _ in
                let label = placemarks?.first.flatMap {
                    VisitTexts.placeLabel(subLocality: $0.subLocality, district: $0.subAdministrativeArea, locality: $0.locality)
                }
                Task { @MainActor in once.finish(label) }
            }
            Task { @MainActor in
                try? await Task.sleep(nanoseconds: UInt64(timeout * 1_000_000_000))
                if once.continuation != nil { geocoder.cancelGeocode() }
                once.finish(nil)
            }
        }
    }

    /// Resumes the lookup once: with the label, or nil at the timeout, whichever comes first.
    @MainActor private final class Once {
        var continuation: CheckedContinuation<String?, Never>?
        func finish(_ value: String?) {
            continuation?.resume(returning: value)
            continuation = nil
        }
    }
}
