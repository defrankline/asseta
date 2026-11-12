import Foundation

/// `AccountDeletionIn`: `POST /api/v1/me/account-deletion` (no tenant). `confirm` is always true.
public struct AccountDeletionIn: Encodable, Hashable, Sendable {
    public let confirm: Bool
    public let reason: String?

    public init(reason: String?) {
        confirm = true
        self.reason = reason
    }

    enum CodingKeys: String, CodingKey { case confirm, reason }

    public func encode(to encoder: any Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(confirm, forKey: .confirm)
        try c.encodeIfPresent(reason, forKey: .reason)
    }
}

/// `AccountDeletionDto`: the anonymised name the person's records now show and the companies left.
public struct AccountDeletionDTO: Codable, Hashable, Sendable {
    public let userID: UUID
    public let displayName: String
    public let deletedAt: Date
    public let companies: [String]

    public init(userID: UUID, displayName: String, deletedAt: Date, companies: [String]) {
        self.userID = userID
        self.displayName = displayName
        self.deletedAt = deletedAt
        self.companies = companies
    }

    enum CodingKeys: String, CodingKey {
        case userID = "user_id", displayName = "display_name", deletedAt = "deleted_at", companies
    }
}

/// `DeletionStatus` of a company closure request (open: unknown future values decode).
public struct CompanyDeletionStatus: OpenStringEnum {
    public let rawValue: String
    public init(rawValue: String) { self.rawValue = rawValue }

    public static let requested = Self(rawValue: "REQUESTED")
    public static let cancelled = Self(rawValue: "CANCELLED")
    public static let inProgress = Self(rawValue: "IN_PROGRESS")
    public static let completed = Self(rawValue: "COMPLETED")
}

/// `CompanyDeletionRequestDto` (the fields the phone shows).
public struct CompanyDeletionRequestDTO: Codable, Hashable, Sendable {
    public let id: UUID
    public let status: CompanyDeletionStatus
    public let reason: String
    public let requestedByName: String?
    public let requestedAt: Date
    public let scheduledFor: Date
    public let cancelledByName: String?
    public let cancelReason: String?

    public init(id: UUID, status: CompanyDeletionStatus, reason: String, requestedByName: String?, requestedAt: Date,
                scheduledFor: Date, cancelledByName: String? = nil, cancelReason: String? = nil) {
        self.id = id
        self.status = status
        self.reason = reason
        self.requestedByName = requestedByName
        self.requestedAt = requestedAt
        self.scheduledFor = scheduledFor
        self.cancelledByName = cancelledByName
        self.cancelReason = cancelReason
    }

    enum CodingKeys: String, CodingKey {
        case id, status, reason
        case requestedByName = "requested_by_name", requestedAt = "requested_at", scheduledFor = "scheduled_for"
        case cancelledByName = "cancelled_by_name", cancelReason = "cancel_reason"
    }
}

/// `CompanyDeletionStatusDto`: the company name, the waiting period and the active (else latest) request.
public struct CompanyDeletionStatusDTO: Codable, Hashable, Sendable {
    public let tenantID: UUID
    public let companyName: String
    public let waitingDays: Int
    public let request: CompanyDeletionRequestDTO?

    public init(tenantID: UUID, companyName: String, waitingDays: Int, request: CompanyDeletionRequestDTO?) {
        self.tenantID = tenantID
        self.companyName = companyName
        self.waitingDays = waitingDays
        self.request = request
    }

    enum CodingKeys: String, CodingKey {
        case tenantID = "tenant_id", companyName = "company_name", waitingDays = "waiting_days", request
    }
}

/// `DeletionReasonIn`: the reason for cancelling a closure (3 to 1000 characters).
public struct DeletionReasonIn: Codable, Hashable, Sendable {
    public let reason: String
    public init(reason: String) { self.reason = reason }
}
