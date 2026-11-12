import AssetaModel
import AssetaNetwork
import Foundation

/// The company-closure request as the Owner app shows it (read-only; starting a closure is web-only). Wording
/// identical to Android `CompanyClosureText`.
public enum CompanyClosureText {
    public static let title = "Company closure"
    public static let bannerAction = "View closure request"
    public static let status = "Status"
    public static let askedBy = "Asked by"
    public static let unknownName = "Unknown"
    public static let askedOn = "Asked on"
    public static let deletionDate = "Deletion date"
    public static let reason = "Reason"
    public static let cancelledBy = "Cancelled by"
    public static let cancelReason = "Cancel reason"
    public static let none = "No closure has been requested for this company."
    public static let footer = "Closing a company is started on the web. Until the deletion date, anyone who may close "
        + "the company can cancel it."
    public static let cancelAction = "Cancel closure"
    public static let cancelTitle = "Cancel the closure?"
    public static let cancelReasonLabel = "Reason (required)"
    public static let cancelKeep = "Keep it"
    public static let reasonTooShort = "Enter a reason (at least 3 characters)."
    public static let offline = "Connect to the internet to cancel the closure."
    public static let cancelled = "Closure cancelled. The company is back to normal."

    /// Permission to view (and cancel) the company's closure request.
    public static let permission = "tenant.company.close"

    public static func statusLabel(_ status: CompanyDeletionStatus) -> String {
        switch status {
        case .requested: "Requested"
        case .inProgress: "Deletion in progress"
        case .cancelled: "Cancelled"
        case .completed: "Completed"
        default: status.humanized
        }
    }

    /// Whether the home banner opens the closure request (the user may close the company).
    public static func canOpen(_ tenant: TenantMembership) -> Bool { tenant.permissions.contains(permission) }

    /// Only a request still waiting for its deletion date can be cancelled.
    public static func canCancel(_ request: CompanyDeletionRequestDTO?) -> Bool { request?.status == .requested }

    /// Label/value rows of a request; dates are days (`12 Dec 2026`) in `timeZone`.
    public static func rows(_ request: CompanyDeletionRequestDTO, timeZone: TimeZone = .current) -> [(String, String)] {
        var rows: [(String, String)] = [
            (status, statusLabel(request.status)),
            (askedBy, name(request.requestedByName)),
            (askedOn, OwnerFormat.date(request.requestedAt, timeZone: timeZone)),
            (deletionDate, OwnerFormat.date(request.scheduledFor, timeZone: timeZone)),
            (reason, request.reason),
        ]
        if request.status == .cancelled {
            rows.append((cancelledBy, name(request.cancelledByName)))
            if let text = request.cancelReason, !text.isEmpty { rows.append((cancelReason, text)) }
        }
        return rows
    }

    /// The trimmed cancel reason, or nil when shorter than 3 characters.
    public static func validReason(_ text: String) -> String? {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.count >= 3 ? trimmed : nil
    }

    private static func name(_ value: String?) -> String {
        let trimmed = value?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return trimmed.isEmpty ? unknownName : trimmed
    }
}

extension OwnerAPI {
    /// `GET /tenant/company/deletion-request` (permission `tenant.company.close`).
    public static func companyDeletion() -> APIRequest<CompanyDeletionStatusDTO> { .get("\(tenant)/company/deletion-request") }

    /// `POST /tenant/company/deletion-request/cancel` with the reason (trimmed by ``CompanyClosureText/validReason(_:)``).
    public static func cancelCompanyDeletion(reason: String, idempotencyKey: UUID) throws
        -> APIRequest<CompanyDeletionRequestDTO> {
        try .mutation(.post, "\(tenant)/company/deletion-request/cancel", body: DeletionReasonIn(reason: reason),
                      idempotencyKey: idempotencyKey)
    }
}

/// Cancelling a closure: validates the reason, then sends it. Not blocked by the read-only company (the closure is
/// what made it read-only), only by being offline.
public enum CompanyClosureCancel {
    public enum Outcome: Equatable, Sendable {
        case cancelled(CompanyDeletionRequestDTO)
        /// Nothing sent: the reason is too short or the phone is offline; or the server's message.
        case failed(String)
    }

    public static func run(client: APIClient, reason: String, isOnline: Bool) async -> Outcome {
        guard let valid = CompanyClosureText.validReason(reason) else { return .failed(CompanyClosureText.reasonTooShort) }
        guard isOnline else { return .failed(CompanyClosureText.offline) }
        do {
            let request = try OwnerAPI.cancelCompanyDeletion(reason: valid, idempotencyKey: UUID())
            return .cancelled(try await client.send(request))
        } catch let APIError.server(_, body) {
            return .failed(body.message)
        } catch {
            return .failed(DecisionErrorText.message(for: error))
        }
    }
}
