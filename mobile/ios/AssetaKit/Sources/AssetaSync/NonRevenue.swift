import AssetaModel
import AssetaNetwork
import AssetaStore
import Foundation

// DEC-031 Phase 1 in the Supervisor app (strings doc "DEC-031 Phase 1 — revenue", Supervisor): under each work-log
// entry the server lists as non-revenue (`GET /non-revenue-activities?job_id=`), its status line, and "Explain" for
// explain holders while NONE or REJECTED. Online only: no sync operation, nothing is queued.

/// Wording of the non-revenue time screens, copied exactly from the strings doc (Android `FieldRevenueTexts`).
public enum FieldRevenueTexts {
    /// field.nonrev.status.* (unknown → humanized wire value).
    public static func status(_ wire: String) -> String {
        switch wire {
        case NonRevenueStatus.none: "Counted as revenue until explained"
        case NonRevenueStatus.proposed: "Explained · waiting for approval"
        case NonRevenueStatus.approved: "Approved as non-revenue time"
        case NonRevenueStatus.rejected: "Not approved · counted as revenue"
        default: humanize(wire)
        }
    }

    public static let explain = "Explain" // field.nonrev.explain
    public static let title = "Explain non-revenue time" // field.nonrev.title
    public static let entry = "Work log entry" // field.nonrev.entry
    /// "Mobilization · 08:00 → 09:30 (1.5 h)" (field.nonrev.entryLine).
    public static func entryLine(type: String, start: String, end: String, hours: String) -> String {
        "\(type) · \(start) → \(end) (\(hours) h)"
    }
    public static let reason = "Reason" // field.nonrev.reason
    public static let chooseReason = "Choose a reason" // field.nonrev.chooseReason
    public static let reasonsEmpty = "Your company has no revenue reasons yet. Ask the office." // field.nonrev.reasonsEmpty
    public static let note = "Note (at least 5 characters)" // field.nonrev.note
    public static let send = "Send" // field.nonrev.send
    public static let footer = "This time counts as revenue until someone else approves it. Needs a connection." // field.nonrev.footer
    public static let sent = "Sent. Someone else will approve it." // field.nonrev.sent
    public static let offline = "Explaining needs a connection." // field.nonrev.offline

    /// field.nonrev.err.* for the known refusals; other refusals show the server message.
    public static func error(code: String?) -> String? {
        switch code {
        case "NON_REVENUE_PENDING": "This time is already waiting for approval."
        case "NON_REVENUE_APPROVAL_NOT_REQUIRED": "Your company does not need approval for this time."
        case "REVENUE_RECONCILIATION_DISABLED": "Your company has switched off revenue checks."
        case "REASON_INACTIVE": "This reason is no longer in use. Choose another."
        default: nil
        }
    }

    static func humanize(_ raw: String) -> String {
        let text = raw.lowercased().replacingOccurrences(of: "_", with: " ")
        return text.prefix(1).uppercased() + text.dropFirst()
    }
}

/// `NonRevenueActivityDto.approval_status` values.
public enum NonRevenueStatus {
    public static let none = "NONE"
    public static let proposed = "PROPOSED"
    public static let approved = "APPROVED"
    public static let rejected = "REJECTED"
}

/// Colour of a status line (the app maps it to its palette).
public enum NonRevenueTone: Sendable, Equatable { case warning, accent, live }

/// Rules of the non-revenue explanation (as Android `NonRevenueRules`; the server re-validates).
public enum NonRevenueRules {
    public static let noteMin = 5, noteMax = 2000

    /// Warning for NONE / REJECTED (counted as revenue), accent while waiting, live once approved.
    public static func tone(_ status: String) -> NonRevenueTone {
        switch status {
        case NonRevenueStatus.proposed: .accent
        case NonRevenueStatus.approved: .live
        default: .warning
        }
    }

    /// "Explain" is offered for NONE and REJECTED only (to explain holders).
    public static func explainable(_ status: String) -> Bool {
        status == NonRevenueStatus.none || status == NonRevenueStatus.rejected
    }

    public static func noteOK(_ note: String) -> Bool {
        let n = note.trimmingCharacters(in: .whitespacesAndNewlines).count
        return n >= noteMin && n <= noteMax
    }

    public static func canSend(reasonID: UUID?, note: String, online: Bool) -> Bool {
        online && reasonID != nil && noteOK(note)
    }

    /// The status of each work-log entry the server lists as non-revenue, by server activity id.
    public static func byActivity(_ items: [NonRevenueActivityDTO]) -> [UUID: NonRevenueActivityDTO] {
        Dictionary(items.map { ($0.activityID, $0) }, uniquingKeysWith: { first, _ in first })
    }

    /// Active reasons sorted by name.
    public static func pickable(_ reasons: [RevenueReasonDTO]) -> [RevenueReasonDTO] {
        reasons.filter(\.isActive).sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }
    }

    /// The refusal in plain words: a known code, else the server's message.
    public static func message(for error: any Error) -> String {
        if let api = error as? APIError {
            if let text = FieldRevenueTexts.error(code: api.code) { return text }
            if case .transport = api { return FieldRevenueTexts.offline }
            return api.localizedDescription
        }
        return error.localizedDescription
    }
}

extension FieldAccess {
    /// Revenue checks are on (`REVENUE_RECONCILIATION`, default off: listed as disabled until the tenant opts in).
    public var revenueOn: Bool { !disabledCapabilities.contains(TenantCapability.revenueReconciliation) }
    /// The work log shows the non-revenue status lines (`tenant.revenue.read`).
    public var nonRevenueStatus: Bool { revenueOn && permissions.contains(RevenuePermission.read) }
    /// "Explain" on non-revenue time (`tenant.revenue.explain` + read for the reasons).
    public var explainNonRevenue: Bool { nonRevenueStatus && permissions.contains(RevenuePermission.explain) }
}

extension SupervisorOnline {
    /// The job's work-log entries the server counts as non-revenue, with their explanation status (online only).
    public func nonRevenueActivities(jobID: UUID) async throws -> [NonRevenueActivityDTO] {
        try await client.send(APIRequest<Page<NonRevenueActivityDTO>>.get(
            "\(Self.tenant)/non-revenue-activities",
            query: Self.page(200) + [URLQueryItem(name: "job_id", value: jobID.lowercased)])).items
    }

    /// Active revenue reasons for the picker (online only).
    public func revenueReasons() async throws -> [RevenueReasonDTO] {
        NonRevenueRules.pickable(try await client.send(APIRequest<Page<RevenueReasonDTO>>.get(
            "\(Self.tenant)/revenue-reasons", query: Self.page(200))).items)
    }

    /// Explains one entry as non-revenue time (`POST /non-revenue-approvals`); someone else approves it.
    public func explainNonRevenue(activityID: UUID, reasonID: UUID, note: String) async throws -> NonRevenueApprovalDTO {
        let body = NonRevenueApprovalIn(activityID: activityID, reasonID: reasonID,
                                        note: note.trimmingCharacters(in: .whitespacesAndNewlines))
        return try await client.send(try APIRequest<NonRevenueApprovalDTO>.mutation(
            .post, "\(Self.tenant)/non-revenue-approvals", body: body, idempotencyKey: UUID()))
    }
}
