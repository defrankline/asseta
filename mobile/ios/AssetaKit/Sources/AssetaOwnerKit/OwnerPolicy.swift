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
    /// Approve (pricing it when needed) or decline jobs waiting for approval (`tenant.job.approve`).
    public let approveJobs: Bool
    /// Create a job and assign it to a supervisor (`tenant.job.write`, as the web "New job" dialog).
    public let createJobs: Bool
    /// Pick the job site on a new job (`tenant.geofence.read`, as the web form shows the site picker).
    public let pickJobSites: Bool
    public let finance: Bool
    /// Confirm or dispute cash handovers (`tenant.finance.verify`, as the web Handovers tab).
    public let verifyHandovers: Bool
    /// Issue cash floats to supervisors (`tenant.finance.cash`, as the web float dialog).
    public let issueFloats: Bool
    public let approvals: Bool
    public let decideApprovals: Bool
    public let cases: Bool
    public let meterEvidence: Bool
    public let meterApprove: Bool
    /// Review meter exceptions (`tenant.meter.review`, as the web review dialog).
    public let reviewExceptions: Bool
    public let expenses: Bool
    public let notifications: Bool
    /// The accountability dashboard summary (`tenant.accountability.read`).
    public let accountability: Bool
    /// Accountability decisions this role may list (each kind by its read permission), in Approvals order.
    public let decisionKinds: [DecisionKind]
    /// The `/me` permission hints (decide permissions per decision kind).
    public let permissions: [String]
    /// Tenant capabilities switched off by policy (`/me` `disabled_capabilities`): their entry points are hidden.
    public let disabledCapabilities: Set<String>

    /// Customer hours are in use (not switched off by the tenant's policy).
    public var customerHours: Bool { !disabledCapabilities.contains(TenantCapability.customerHours) }
    /// Engine-hour controls are in use (baselines, corrections, classifications, unexplained hours).
    public var engineHours: Bool { !disabledCapabilities.contains(TenantCapability.engineHours) }
    /// The DEC-030 cash additions are in use (transfers, acknowledgements, write-offs, retentions, adjustments,
    /// remittance cut-off, amount received on a remittance).
    public var cashCustody: Bool { !disabledCapabilities.contains(TenantCapability.cashCustody) }

    /// The Approvals screen shows approval requests or at least one kind of accountability decision.
    public var approvalsScreen: Bool { approvals || !decisionKinds.isEmpty }

    public func canDecide(_ kind: DecisionKind) -> Bool { kind.decidable(permissions: permissions) }

    public init(permissions: [String], disabledCapabilities: [String] = []) {
        let set = Set(permissions)
        let disabled = Set(disabledCapabilities)
        self.permissions = permissions
        self.disabledCapabilities = disabled
        accountability = set.contains("tenant.accountability.read")
        decisionKinds = DecisionKind.allCases.filter {
            $0.visible(permissions: permissions) && !($0.capability.map(disabled.contains) ?? false)
        }
        fleet = set.contains("tenant.fleet.read")
        manageAlerts = set.contains("tenant.fleet.alert_manage")
        jobs = set.contains("tenant.job.read")
        approveJobs = set.contains("tenant.job.approve")
        createJobs = set.contains("tenant.job.write")
        pickJobSites = set.contains("tenant.geofence.read")
        finance = set.contains("tenant.finance.read")
        verifyHandovers = set.contains("tenant.finance.verify")
        issueFloats = set.contains("tenant.finance.cash")
        overview = fleet || jobs || finance
        approvals = set.contains("tenant.approval.read")
        decideApprovals = set.contains("tenant.approval.expense")
        cases = set.contains("tenant.case.read")
        meterEvidence = set.contains("tenant.meter.read")
        meterApprove = set.contains("tenant.meter.approve")
        reviewExceptions = set.contains("tenant.meter.review")
        expenses = set.contains("tenant.expense.read")
        notifications = set.contains("tenant.notification.read")
    }

    public init(_ tenant: TenantMembership) {
        self.init(permissions: tenant.permissions, disabledCapabilities: tenant.disabledCapabilities)
    }
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
        case "HANDOVER_ALREADY_DECIDED":
            return HandoverText.alreadyDecided
        case "ALREADY_REVIEWED":
            return ExceptionReviewText.alreadyReviewed
        case "SUBSCRIPTION_READ_ONLY":
            return "This company's subscription is read-only, so changes are not accepted right now."
        case "PRICE_REQUIRED":
            return JobApprovalText.priceRequired
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
