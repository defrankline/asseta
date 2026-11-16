import Foundation

// Shared by the Supervisor (Dashboard, Home, report form) and the Owner (overdue machines) apps.

/// Where a machine of mine stands (Dashboard pills, Home "Hours to report", the report form's first step).
public enum MachineReportStanding: Equatable, Sendable {
    /// No starting reading yet: the first report only records the reading.
    case opening
    /// A report is due (never reported, or no report for the tenant's reminder days).
    case due
    /// A report waits for the owner or manager (or is still on this phone, not sent).
    case awaitingApproval(notSent: Bool)
    /// The last report was rejected: the split is redone on the same reading.
    case rejected(reportID: UUID)
    case upToDate

    /// Counts towards "Hours to report" / the Machine report tile's "due" badge.
    public var needsReport: Bool {
        switch self {
        case .opening, .due, .rejected: true
        case .awaitingApproval, .upToDate: false
        }
    }

    /// The machine's status from its synced state, this phone's unsent report and the tenant's reminder days
    /// (`machine_report_reminder_days`; nil = reminders off, then only a machine never reported is due).
    public static func of(_ state: MachineReportStatusDTO, unsentReport: Bool, reminderDays: Int?) -> MachineReportStanding {
        if unsentReport { return .awaitingApproval(notSent: true) }
        if state.pendingReportID != nil { return .awaitingApproval(notSent: false) }
        if let rejected = state.rejectedReportID { return .rejected(reportID: rejected) }
        if state.previousReading == nil { return .opening }
        guard let days = state.daysSinceReport else { return .due }
        if let reminderDays, days >= reminderDays { return .due }
        return .upToDate
    }
}

extension MachineReportStanding {
    /// `CUSTOMER_HOURS.machine_report_reminder_days` when the tenant's policy cannot be read.
    public static let defaultReminderDays = 3

    /// The reminder days to judge machines by: the policy's value (nil = the tenant switched reminders off), or 3 when
    /// the policy could not be loaded (refused, failed, unreadable) or does not carry the setting.
    public static func reminderDays(_ policy: CustomerHoursPolicyValues?) -> Int? {
        guard let policy else { return defaultReminderDays }
        return policy.machineReportReminderDays
    }
}
