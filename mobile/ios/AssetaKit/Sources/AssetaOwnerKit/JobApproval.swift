import AssetaModel
import AssetaNetwork
import AssetaStore // UUID.lowercased
import Foundation

/// `JobTransitionIn` for the owner's decision on a job: APPROVE (with `hourly_rate` when the job has no price yet)
/// or CANCEL with a reason (declining a field request).
public struct JobTransitionIn: Encodable, Hashable, Sendable {
    public let action: String
    public let reason: String?
    public let hourlyRate: DecimalString?

    public init(action: String, reason: String? = nil, hourlyRate: DecimalString? = nil) {
        self.action = action
        self.reason = reason
        self.hourlyRate = hourlyRate
    }

    enum CodingKeys: String, CodingKey { case action, reason, hourlyRate = "hourly_rate" }

    public func encode(to encoder: any Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(action, forKey: .action)
        try c.encodeIfPresent(reason, forKey: .reason)
        try c.encodeIfPresent(hourlyRate, forKey: .hourlyRate)
    }
}

extension OwnerAPI {
    /// Approves a job waiting for approval; `hourlyRate` sets the price (required when `rate_source` is PENDING_PRICE).
    public static func approveJob(_ id: UUID, hourlyRate: Decimal?, idempotencyKey: UUID) throws -> APIRequest<JobDTO> {
        try .mutation(.post, "\(tenant)/jobs/\(id.lowercased)/transitions",
                      body: JobTransitionIn(action: "APPROVE", hourlyRate: hourlyRate.map(DecimalString.init)),
                      idempotencyKey: idempotencyKey)
    }

    /// Declines a job waiting for approval (CANCEL with the reason the supervisor will see).
    public static func declineJob(_ id: UUID, reason: String, idempotencyKey: UUID) throws -> APIRequest<JobDTO> {
        try .mutation(.post, "\(tenant)/jobs/\(id.lowercased)/transitions",
                      body: JobTransitionIn(action: "CANCEL", reason: reason.trimmingCharacters(in: .whitespacesAndNewlines)),
                      idempotencyKey: idempotencyKey)
    }
}

/// Wording and input rules of the owner's job approval. Identical to Android `JobApprovalText`.
public enum JobApprovalText {
    public static let sectionTitle = "Jobs"
    public static let empty = "No jobs waiting for approval."
    public static let requestTitle = "Request"
    public static let decisionTitle = "Decision"
    public static let customerAsked = "What the customer asked for"
    public static let approve = "Approve"
    public static let decline = "Decline"
    public static let reason = "Reason"
    public static let approveTitle = "Approve this job?"
    public static let declineTitle = "Decline this job?"
    public static let hourlyRateTitle = "Hourly rate"
    public static let pendingPriceHelper = "No rate card applies — set the price to approve"
    public static let priceRequired = "Set an hourly rate before approving this job."
    public static let alreadyDecided = "This job is no longer waiting for approval. It has been refreshed."
    public static let approved = "Job approved."
    public static let declined = "Job declined."
    public static let unknownRequester = "a supervisor"

    /// "Requested from the field by <name>" for a field request, else nil.
    public static func requestedBy(_ job: JobDTO) -> String? {
        guard job.isFieldRequest else { return nil }
        let name = job.requestedByName?.trimmingCharacters(in: .whitespacesAndNewlines)
        return "Requested from the field by \((name?.isEmpty ?? true) ? unknownRequester : name!)"
    }

    public static func hourlyRateLabel(currency: String?) -> String {
        guard let currency, !currency.isEmpty else { return hourlyRateTitle }
        return "\(hourlyRateTitle) (\(currency))"
    }

    /// The typed hourly rate: a plain positive decimal (`1500`, `1500.50`, `1,500.50`), else nil.
    public static func parseRate(_ text: String) -> Decimal? {
        let cleaned = text.trimmingCharacters(in: .whitespaces).replacingOccurrences(of: ",", with: "")
        guard let value = DecimalString(string: cleaned)?.value, value > 0 else { return nil }
        return value
    }

    /// The rate to send with APPROVE: required for a job without a price; otherwise the price stays (nil).
    public static func rateToSend(job: JobDTO, text: String) -> Decimal?? {
        if job.needsPrice { return parseRate(text).map { .some($0) } }
        return .some(nil)
    }

    public static func canApprove(job: JobDTO, rateText: String) -> Bool { rateToSend(job: job, text: rateText) != nil }

    public static func canDecline(reason: String) -> Bool { !reason.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }

    /// Error codes after which the job must be reloaded (someone else decided it).
    public static func needsReload(_ error: any Error) -> Bool {
        guard let code = (error as? APIError)?.code else { return false }
        return code == "INVALID_JOB_TRANSITION" || code == "VERSION_CONFLICT"
    }

    public static func message(for error: any Error) -> String {
        switch (error as? APIError)?.code {
        case "PRICE_REQUIRED": priceRequired
        case "INVALID_JOB_TRANSITION": alreadyDecided
        default: DecisionErrorText.message(for: error)
        }
    }
}
