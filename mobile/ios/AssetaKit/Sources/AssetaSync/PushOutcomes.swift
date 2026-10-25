import AssetaModel
import AssetaStore
import Foundation

/// The local consequence of one per-operation push result.
public enum AppliedOutcome: Sendable, Equatable {
    case acked
    case deferred
    case conflict(code: String?)
    case rejected(code: String?)
    case quarantined
    /// No result for an operation that was sent: kept pending, re-sent later.
    case missing
}

/// Maps `OperationResultDTO`s onto outbox transitions. Nothing is marked synced before a durable
/// ACK; conflicts and rejections keep their evidence and server result for the user to see.
public struct PushOutcomeApplier: Sendable {
    public static let deferDelay: TimeInterval = 10
    public static let quarantineRetry: TimeInterval = 15 * 60
    static let conflictCodes: Set<String> = [
        "INVALID_JOB_TRANSITION", "READING_NOT_ALLOWED", "MACHINE_BUSY", "CAPTURE_ID_CONFLICT", "JOB_NOT_ACTIVE",
        "STALE_VERSION", "DUPLICATE_PAYMENT_REFERENCE",
        // Accountability ops (same set as the server's sync CONFLICT_CODES).
        "TRANSFER_ALREADY_DECIDED", "FLOAT_ALREADY_ACKNOWLEDGED", "NO_AVAILABLE_HOURS", "EXCEEDS_REMAINING_HOURS",
        "BASELINE_REQUIRED", "OVERLAPPING_ALLOCATION", "OVERLAPPING_ACTIVITY", "BASELINE_PENDING", "CORRECTION_PENDING",
        "RETENTION_NOT_ALLOWED", "DUPLICATE_RETENTION",
        // A capability the tenant's policy switched off (F1).
        "ENGINE_HOURS_DISABLED", "CASH_CUSTODY_DISABLED",
    ]

    let outbox: any ClientOperationRepository

    public init(outbox: any ClientOperationRepository) {
        self.outbox = outbox
    }

    /// `DUPLICATE` replays the *stored* outcome: it is only an ACK when that outcome had no error.
    /// A duplicate of a quarantined op (tenant still read-only) stays quarantined; a duplicate of a
    /// rejected/conflicting op keeps that state.
    public static func classify(_ result: OperationResultDTO) -> AppliedOutcome {
        switch result.status {
        case .acked: return .acked
        case .deferred: return .deferred
        case .quarantined: return .quarantined
        case .conflict: return .conflict(code: result.errorCode)
        case .rejected: return .rejected(code: result.errorCode)
        case .duplicate:
            guard let code = result.errorCode else { return .acked }
            if code == "SUBSCRIPTION_READ_ONLY" { return .quarantined }
            if conflictCodes.contains(code) || result.result["server_state"] != nil { return .conflict(code: code) }
            return .rejected(code: code)
        }
    }

    @discardableResult
    public func apply(_ result: OperationResultDTO, now: Date) throws -> AppliedOutcome {
        let outcome = Self.classify(result)
        let stored = try Self.storedResult(result)
        let message = result.errorMessage ?? result.errorCode ?? result.status.rawValue
        switch outcome {
        case .acked:
            let version = result.result["entity"]?["version"]?.intValue
                ?? result.result["entity"]?["capture"]?["version"]?.intValue
            try outbox.markAcked(id: result.id, resultJSON: stored, serverRevision: version.map(Int64.init))
        case .deferred:
            try outbox.release(id: result.id, error: "Waiting for an earlier item (DEFERRED)",
                               retryAt: now.addingTimeInterval(Self.deferDelay))
        case let .conflict(code):
            try outbox.markConflict(id: result.id, code: code, message: message, resultJSON: stored)
        case let .rejected(code):
            try outbox.markFailed(id: result.id, code: code, message: message, resultJSON: stored)
        case .quarantined:
            try outbox.quarantine(id: result.id, reason: "Held: subscription read-only. Will be re-sent.",
                                  resultJSON: stored, retryAt: now.addingTimeInterval(Self.quarantineRetry))
        case .missing:
            try outbox.release(id: result.id, error: "No result returned", retryAt: nil)
        }
        return outcome
    }

    /// Applies a whole push response; operations without a result go back to pending.
    public func apply(_ response: PushResultDTO, sent: [UUID], now: Date) throws -> [UUID: AppliedOutcome] {
        var outcomes: [UUID: AppliedOutcome] = [:]
        for result in response.results where sent.contains(result.id) {
            outcomes[result.id] = try apply(result, now: now)
        }
        for id in sent where outcomes[id] == nil {
            try outbox.release(id: id, error: "No result returned", retryAt: nil)
            outcomes[id] = .missing
        }
        return outcomes
    }

    static func storedResult(_ result: OperationResultDTO) throws -> String {
        var object: [String: JSONValue] = ["status": .string(result.status.rawValue), "result": result.result]
        if let error = result.error { object["error"] = error }
        return try JSONValue.object(object).jsonString()
    }
}
