import AssetaModel
import AssetaNetwork
import Foundation

/// What the Owner app shows for a tenant membership. Derived from the `/me` permission hints only
/// to hide UI; the server re-authorizes every call.
public struct OwnerFeatures: Equatable, Sendable {
    public let overview: Bool
    public let fleet: Bool
    public let manageAlerts: Bool
    public let jobs: Bool
    public let finance: Bool
    public let approvals: Bool
    public let decideApprovals: Bool
    public let cases: Bool
    public let meterEvidence: Bool
    public let meterApprove: Bool
    public let expenses: Bool
    public let notifications: Bool

    public init(permissions: [String]) {
        let set = Set(permissions)
        fleet = set.contains("tenant.fleet.read")
        manageAlerts = set.contains("tenant.fleet.alert_manage")
        jobs = set.contains("tenant.job.read")
        finance = set.contains("tenant.finance.read")
        overview = fleet || jobs || finance
        approvals = set.contains("tenant.approval.read")
        decideApprovals = set.contains("tenant.approval.expense")
        cases = set.contains("tenant.case.read")
        meterEvidence = set.contains("tenant.meter.read")
        meterApprove = set.contains("tenant.meter.approve")
        expenses = set.contains("tenant.expense.read")
        notifications = set.contains("tenant.notification.read")
    }

    public init(_ tenant: TenantMembership) { self.init(permissions: tenant.permissions) }
}

/// Why a mutation (alert action, approval decision, settings change) is not offered right now.
public enum MutationBlock: Equatable, Sendable {
    case offline
    case showingCachedData
    case readOnlyTenant
    case notPermitted

    public var message: String {
        switch self {
        case .offline: "You're offline. Changes need a connection."
        case .showingCachedData: "Showing saved data. Refresh while online before making changes."
        case .readOnlyTenant: "This company is read-only. Changes are disabled."
        case .notPermitted: "Your role can view this but not change it."
        }
    }
}

/// The Owner app's offline mutation guard: cached snapshots are strictly read-only, so any change
/// requires a live connection, live (not cached) data, a writable tenant and the permission hint.
public enum MutationGuard {
    public static func check(isOnline: Bool, showingCachedData: Bool, accessState: TenantAccessState,
                             permitted: Bool) -> MutationBlock? {
        if !isOnline { return .offline }
        if showingCachedData { return .showingCachedData }
        if accessState != .full { return .readOnlyTenant }
        if !permitted { return .notPermitted }
        return nil
    }
}

/// Maps decision errors to wording an owner can act on.
public enum DecisionErrorText {
    /// Same wording as the Android Owner app (`OwnerErrors`).
    public static func message(for error: any Error) -> String {
        guard let api = error as? APIError else { return "Unexpected response from the server. Please try again." }
        if case .transport = api { return "Cannot reach Asseta. Check your connection and try again." }
        switch api.code {
        case "SEGREGATION_OF_DUTIES":
            return "Segregation of duties: you cannot decide on a request you submitted or recorded yourself. "
                + "Another authorised person must approve or reject it."
        case "NOTE_REQUIRED":
            return "Add a note explaining how the alert was resolved."
        case "ALERT_CLOSED":
            return "This alert was already closed by someone else. The list has been refreshed."
        case "APPROVAL_ALREADY_DECIDED":
            return "This request was already decided by someone else. The list has been refreshed."
        case "RESET_DECIDED":
            return MeterResetText.alreadyDecided
        case "SUBSCRIPTION_READ_ONLY":
            return "This company's subscription is read-only, so changes are not accepted right now."
        case "PERMISSION_DENIED":
            return "You do not have permission to do this."
        case "TENANT_ACCESS_DENIED", "TENANT_ACCESS_BLOCKED", "MANDATE_ENDED", "MANDATE_REQUIRED":
            return "Your access to this company has ended. Its saved data was removed from this device."
        default:
            let text = api.localizedDescription
            return api.correlationID.map { "\(text) (ref \($0.prefix(8)))" } ?? text
        }
    }

    /// A meter reset decision: the requester-can't-decide refusal is worded for resets; everything else as above.
    public static func resetMessage(for error: any Error) -> String {
        if (error as? APIError)?.code == "SEGREGATION_OF_DUTIES" { return MeterResetText.ownRequest }
        return message(for: error)
    }

    /// Codes after which the shown record is out of date and must be reloaded (as on Android).
    public static func needsReload(_ error: any Error) -> Bool {
        guard let api = error as? APIError else { return false }
        return api.code == "ALERT_CLOSED" || api.code == "APPROVAL_ALREADY_DECIDED" || api.code == "RESET_DECIDED"
    }
}
