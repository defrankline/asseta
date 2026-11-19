import Foundation

// Shared by the Supervisor (Dashboard, Home, report form) and the Owner (overdue machines) apps.

/// Where a machine of mine stands (Dashboard pills, Home "Hours to report", the report form's first step).
public enum MachineReportStanding: Equatable, Sendable {
    /// No starting reading yet: the first report only records the reading.
    case opening
    /// A report is due (never reported, the last report was rejected, or no report for the tenant's reminder days).
    case due
    /// A report waits for the owner or manager (or is still on this phone, not sent).
    case awaitingApproval(notSent: Bool)
    case upToDate

    /// Counts towards "Hours to report" / the Machine report tile's "due" badge.
    public var needsReport: Bool {
        switch self {
        case .opening, .due: true
        case .awaitingApproval, .upToDate: false
        }
    }

    /// The machine's status from its synced state, this phone's unsent report and the tenant's reminder days
    /// (`machine_report_reminder_days`; nil = reminders off, then only a machine never reported is due). A rejected
    /// report is final: the machine is due again and the supervisor sends a new report with a new reading.
    public static func of(_ state: MachineReportStatusDTO, unsentReport: Bool, reminderDays: Int?) -> MachineReportStanding {
        if unsentReport { return .awaitingApproval(notSent: true) }
        if state.pendingReportID != nil { return .awaitingApproval(notSent: false) }
        if state.previousReading == nil { return .opening }
        if state.rejectedReportID != nil { return .due }
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

    /// `CUSTOMER_HOURS.visit_gap_warning_hours` when the tenant's policy cannot be read.
    public static let defaultVisitGapWarningHours = 24

    /// The hours since the last visit above which the owner's approvals flag a report: the policy's value (nil = never
    /// flag), or 24 while the policy is unknown.
    public static func visitGapWarningHours(_ policy: CustomerHoursPolicyValues?) -> Int? {
        guard let policy else { return defaultVisitGapWarningHours }
        return policy.visitGapWarningHours
    }

    /// Whether a report's time since the last visit is over the tenant's warning (never without a gap or a setting).
    public static func visitGapFlagged(seconds: Int?, warningHours: Int?) -> Bool {
        guard let seconds, let warningHours else { return false }
        return seconds > warningHours * 3600
    }
}
