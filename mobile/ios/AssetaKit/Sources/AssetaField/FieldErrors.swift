#if os(iOS)
import AssetaSync
import Foundation

/// The message shown when a form cannot be saved.
enum FieldErrors {
    static func describe(_ error: any Error) -> String {
        if case let FieldRecorderError.notAllowed(message) = error { return message }
        if case let FieldRecorderError.invalid(message) = error { return message }
        return String(describing: error)
    }
}
#endif
