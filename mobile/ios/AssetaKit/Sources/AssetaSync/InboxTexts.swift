import AssetaModel
import Foundation

/// The five bottom tabs, in order (same on Android).
public enum SupervisorTab: String, CaseIterable, Sendable, Hashable {
    case jobs, readings, fuel, money, inbox

    public var label: String {
        switch self {
        case .jobs: "Jobs"
        case .readings: "Readings"
        case .fuel: "Fuel"
        case .money: "Money"
        case .inbox: "Inbox"
        }
    }
}

/// Jobs tab segments.
public enum JobSegment: String, CaseIterable, Sendable, Hashable {
    case inProgress, ready, closed, machines

    public var label: String {
        switch self {
        case .inProgress: "In progress"
        case .ready: "Ready to start"
        case .closed: "Recently closed"
        case .machines: "My machines"
        }
    }
}

public enum MoneySegment: String, CaseIterable, Sendable, Hashable {
    case expenses, collections, handovers

    public var label: String {
        switch self {
        case .expenses: "Expenses"
        case .collections: "Collections"
        case .handovers: "Handovers"
        }
    }
}

public enum FuelSegment: String, CaseIterable, Sendable, Hashable {
    case purchase = "PURCHASE", issue = "ISSUE", usage = "USAGE"

    public var label: String {
        switch self {
        case .purchase: "Purchase"
        case .issue: "Issue"
        case .usage: "Usage"
        }
    }
}

/// Wording of the supervisor tabs, word for word the Android `InboxTexts`. Pure functions so wording
/// and the small display rules are unit-tested.
public enum InboxTexts {
    /// Jobs segment of a job by its status on this device.
    public static func segment(_ displayStatus: JobStatus) -> JobSegment {
        switch displayStatus {
        case .inProgress: .inProgress
        case .completed, .cancelled: .closed
        default: .ready
        }
    }

    public static func jobsEmpty(_ segment: JobSegment) -> (title: String, message: String) {
        switch segment {
        case .inProgress: ("No jobs in progress", "Jobs you have started appear here.")
        case .ready: ("No jobs ready to start", "Approved jobs assigned to you appear here after a sync.")
        case .closed: ("No recently closed jobs", "Jobs completed or cancelled in the last 14 days appear here.")
        case .machines: ("No machines", "Machines of your jobs appear here after a sync.")
        }
    }

    public static func readingKind(_ kind: String) -> String { kind == "OPENING" ? "Opening reading" : "Closing reading" }

    public static func captureMode(_ mode: String) -> String {
        switch mode {
        case "AUTOMATIC": "Camera (automatic)"
        case "MANUAL": "Typed in"
        default: sentence(mode)
        }
    }

    /// GPS result of a reading.
    public static func gps(status: String, latitude: Double?, longitude: Double?, accuracyM: Double?) -> String {
        switch status {
        case "FIX":
            guard let latitude, let longitude else { return "Position recorded" }
            let position = String(format: "%.5f, %.5f", locale: Locale(identifier: "en_US_POSIX"), latitude, longitude)
            return position + (accuracyM.map { " (±\(Int($0)) m)" } ?? "")
        case "NO_FIX": return "No GPS fix could be obtained"
        case "TIMEOUT": return "No GPS fix within 20 seconds"
        case "PERMISSION_DENIED": return "Location permission denied"
        case "DISABLED": return "Location services are turned off"
        default: return sentence(status)
        }
    }

    /// "92 %" from an OCR confidence 0…1.
    public static func confidence(_ value: Double?) -> String? { value.map { "\(Int($0 * 100)) %" } }

    public static func reviewOutcome(_ reviewStatus: String?, findings: Int) -> String {
        if findings == 0 { return "No findings" }
        switch reviewStatus {
        case "PENDING_REVIEW": return "Waiting for the office to review"
        case "REVIEWED": return "Reviewed by the office"
        default: return "No review needed"
        }
    }

    public static func fuelType(_ code: String) -> String { FuelSegment(rawValue: code)?.label ?? sentence(code) }

    public static func paidFrom(_ code: String) -> String {
        switch code {
        case "CASH_CUSTODY": "My cash"
        case "COMPANY": "Company"
        default: sentence(code)
        }
    }

    public static func ackMethod(_ code: String) -> String {
        switch code {
        case "SIGNATURE": "Signature"
        case "NAME_CONFIRMATION": "Name confirmation"
        default: sentence(code)
        }
    }

    public static func money(_ amount: String, _ currency: String?) -> String {
        plain(amount) + (currency.map { " \($0)" } ?? "")
    }

    public static func litres(_ value: String) -> String { plain(value) + " L" }

    public static func hours(_ value: Decimal) -> String {
        var copy = value
        return NSDecimalString(&copy, Locale(identifier: "en_US_POSIX")) + " h"
    }

    /// Money list section of a record: this phone's own (not confirmed yet) or the office's status.
    public static func moneyGroup(_ status: InboxStatus) -> String {
        switch status {
        case .waiting, .synced, .notSynced: onThisPhone
        default: status.label
        }
    }

    /// Money list sections in display order: on this phone, waiting for the office, approved/verified, rejected.
    public static func moneyGroups<T>(_ items: [T], status: (T) -> InboxStatus) -> [(title: String, items: [T])] {
        let order = [onThisPhone, InboxStatus.pendingApproval.label, InboxStatus.claimed.label, InboxStatus.approved.label,
                     InboxStatus.verified.label, InboxStatus.rejected.label]
        var titles: [String] = []
        var groups: [String: [T]] = [:]
        for item in items {
            let title = moneyGroup(status(item))
            if groups[title] == nil { titles.append(title) }
            groups[title, default: []].append(item)
        }
        func rank(_ title: String) -> Int { order.firstIndex(of: title) ?? order.count }
        return titles.sorted { rank($0) < rank($1) }.map { ($0, groups[$0] ?? []) }
    }

    public static let onThisPhone = "On this phone"

    /// Title of a "Needs attention" row.
    public static func attentionTitle(_ kind: AttentionItem.Kind) -> String {
        switch kind {
        case .reading: "Meter reading"
        case .reset: "Meter reset request"
        case .expense: "Expense"
        case .fuel: "Fuel event"
        case .collection: "Cash collection"
        case .handover: "Cash handover"
        case .operation: "Job step"
        case .upload: "Photo or signature upload"
        }
    }

    public static func attentionDetail(_ status: InboxStatus) -> String {
        switch status {
        case .rejected: "Rejected by the office"
        case .flagged: "Flagged: the office will review it"
        case .notSynced: "Not accepted by the server. Open Sync status for details."
        default: status.label
        }
    }

    /// Inbox badge: unread notifications plus items that need attention.
    public static func inboxBadge(unread: Int, attention: Int) -> Int { unread + attention }

    public static func machine(_ assetCode: String?, _ name: String?) -> String {
        let text = [assetCode, name].compactMap { $0 }.joined(separator: " · ")
        return text.isEmpty ? "Machine" : text
    }

    public static func activityType(_ type: String) -> String { sentence(type) }

    public static let reconciliationFooter = "From the office's books today: opening balance, floats, collections, "
        + "approved spending and verified handovers."
    public static let estimateFooter = "Offline estimate from the last synced balance and what this phone has recorded "
        + "since. Connect to see today's figures from the office."
    public static let notificationsOffline = "Showing the notifications saved on this phone. Connect to check for new ones."

    /// "1250.5000" → "1250.5"; non-numeric text unchanged.
    static func plain(_ text: String) -> String {
        guard let value = Decimal(string: text, locale: Locale(identifier: "en_US_POSIX")),
              DecimalString(string: text) != nil else { return text }
        var copy = value
        return NSDecimalString(&copy, Locale(identifier: "en_US_POSIX"))
    }

    /// "NEVER_REPORTED" → "Never reported".
    static func sentence(_ code: String) -> String {
        let lower = code.lowercased().replacingOccurrences(of: "_", with: " ")
        return lower.prefix(1).uppercased() + lower.dropFirst()
    }
}
