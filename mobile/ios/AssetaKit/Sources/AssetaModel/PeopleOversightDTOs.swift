import Foundation

// DEC-031 Phase 5 (oversight): the people scorecard, unbilled work, idle machines and site check-ins. Shapes follow
// `contracts/openapi.json` (`ScorecardRowDto`, `ScorecardDetailDto`, `ScorecardRecordDto`, `UnbilledJobDto`,
// `IdleMachineDto`, `SiteCheckinDto`, `MySiteCheckinsDto`, `CheckinSlotDto`, `SiteCheckinIn`); same as Android.

extension SyncCapability {
    /// `SITE_CHECKIN` (a supervisor's GPS check-in at the site), announced only while the tenant requires check-ins.
    public static let siteCheckin = "OP_SITE_CHECKIN"
}

extension TenantCapability {
    /// The per-person scorecard (`tenant.oversight.scorecard.read`).
    public static let scorecard = "SCORECARD"
    /// Completed, billing-ready work not on an issued invoice after N days.
    public static let unbilledWork = "UNBILLED_WORK"
    /// Machines without work or engine activity for N days.
    public static let idleMachines = "IDLE_MACHINES"
    /// Supervisors check in by GPS at the tenant's times.
    public static let siteCheckin = "SITE_CHECKIN"
}

// MARK: - Site check-ins

/// `SiteCheckinIn`: the `SITE_CHECKIN` payload (and `POST /site-checkins`). A failed GPS attempt is sent as such,
/// never with made-up coordinates. `client_id` makes a replay return the same check-in.
public struct SiteCheckinPayload: Codable, Hashable, Sendable {
    public let clientID: UUID
    public let capturedAt: Date
    public let gps: GpsPayload
    public let jobSiteID: UUID?

    public init(clientID: UUID, capturedAt: Date, gps: GpsPayload, jobSiteID: UUID? = nil) {
        self.clientID = clientID
        self.capturedAt = capturedAt
        self.gps = gps
        self.jobSiteID = jobSiteID
    }

    enum CodingKeys: String, CodingKey { case gps, clientID = "client_id", capturedAt = "captured_at", jobSiteID = "job_site_id" }
}

/// `CheckinSlotDto.status`.
public struct CheckinSlotStatus: OpenStringEnum {
    public let rawValue: String
    public init(rawValue: String) { self.rawValue = rawValue }

    public static let made = CheckinSlotStatus(rawValue: "MADE")
    public static let missed = CheckinSlotStatus(rawValue: "MISSED")
    public static let due = CheckinSlotStatus(rawValue: "DUE")
    public static let upcoming = CheckinSlotStatus(rawValue: "UPCOMING")
}

/// `SiteCheckinDto`: one check-in as the server stored it (job and site inferred, distance from the site centre).
public struct SiteCheckinDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let clientID: UUID
    public let staffMemberID: UUID
    public let staffMemberName: String?
    public let recordedBy: UUID
    public let recordedByName: String?
    public let capturedAt: Date
    public let receivedAt: Date
    public let gpsStatus: String
    public let latitude: Double?
    public let longitude: Double?
    public let accuracyM: Double?
    public let jobSiteID: UUID?
    public let jobSiteName: String?
    public let jobID: UUID?
    public let jobNumber: String?
    public let distanceM: Double?
    /// Against the tenant's maximum distance; nil when not judged (no fix, no site or no maximum).
    public let withinDistance: Bool?
    public let source: String

    enum CodingKeys: String, CodingKey {
        case id, latitude, longitude, source
        case clientID = "client_id", staffMemberID = "staff_member_id", staffMemberName = "staff_member_name"
        case recordedBy = "recorded_by", recordedByName = "recorded_by_name", capturedAt = "captured_at"
        case receivedAt = "received_at", gpsStatus = "gps_status", accuracyM = "accuracy_m", jobSiteID = "job_site_id"
        case jobSiteName = "job_site_name", jobID = "job_id", jobNumber = "job_number", distanceM = "distance_m"
        case withinDistance = "within_distance"
    }
}

/// `CheckinSlotDto`: one scheduled check-in time of the person.
public struct CheckinSlotDTO: Codable, Hashable, Sendable {
    public let scheduledAt: Date
    public let windowMinutes: Int
    public let status: CheckinSlotStatus
    public let checkinID: UUID?
    public let jobID: UUID?
    public let jobNumber: String?

    enum CodingKeys: String, CodingKey {
        case status, scheduledAt = "scheduled_at", windowMinutes = "window_minutes", checkinID = "checkin_id"
        case jobID = "job_id", jobNumber = "job_number"
    }
}

/// `MySiteCheckinsDto` (`GET /site-checkins/mine`): the person's schedule, slots and check-ins of a period.
public struct MySiteCheckinsDTO: Codable, Hashable, Sendable {
    public let required: Bool
    /// Tenant-local "HH:MM".
    public let times: [String]
    public let windowMinutes: Int
    public let maxDistanceM: Int?
    public let timezone: String
    public let dayFrom: String
    public let dayTo: String
    public let slots: [CheckinSlotDTO]
    public let checkins: [SiteCheckinDTO]

    enum CodingKeys: String, CodingKey {
        case required, times, timezone, slots, checkins
        case windowMinutes = "window_minutes", maxDistanceM = "max_distance_m", dayFrom = "day_from", dayTo = "day_to"
    }
}

// MARK: - Scorecard

/// `ScorecardItem` (plus `PATTERN_SIGNAL` on records).
public struct ScorecardItem: OpenStringEnum {
    public let rawValue: String
    public init(rawValue: String) { self.rawValue = rawValue }

    public static let missingDailyReport = ScorecardItem(rawValue: "MISSING_DAILY_REPORT")
    public static let lateDailyReport = ScorecardItem(rawValue: "LATE_DAILY_REPORT")
    public static let unexplainedHours = ScorecardItem(rawValue: "UNEXPLAINED_HOURS")
    public static let alert = ScorecardItem(rawValue: "ALERT")
    public static let cashHeldTooLong = ScorecardItem(rawValue: "CASH_HELD_TOO_LONG")
    public static let cashDifference = ScorecardItem(rawValue: "CASH_DIFFERENCE")
    public static let revenueDifference = ScorecardItem(rawValue: "REVENUE_DIFFERENCE")
    public static let refusedAttempt = ScorecardItem(rawValue: "REFUSED_ATTEMPT")
    public static let missedCheckin = ScorecardItem(rawValue: "MISSED_CHECKIN")
    public static let patternSignal = ScorecardItem(rawValue: "PATTERN_SIGNAL")

    /// The filterable items, in the server's order (the detail `?item=` values).
    public static let filterable: [ScorecardItem] = [
        .missingDailyReport, .lateDailyReport, .unexplainedHours, .alert, .cashHeldTooLong, .cashDifference,
        .revenueDifference, .refusedAttempt, .missedCheckin,
    ]
}

/// `AmountByCurrencyDto`.
public struct AmountByCurrencyDTO: Codable, Hashable, Sendable {
    public let currency: String
    public let count: Int
    public let amount: DecimalString
}

/// `CashHeldDto`: cash the person holds now.
public struct CashHeldDTO: Codable, Hashable, Sendable {
    public let currency: String
    public let amount: DecimalString
    public let heldSince: Date?
    public let heldDays: Int?

    enum CodingKeys: String, CodingKey { case currency, amount, heldSince = "held_since", heldDays = "held_days" }
}

/// `ScorecardRowDto`: one person's items in the period (counts, never a verdict).
public struct ScorecardRowDTO: Codable, Hashable, Sendable, Identifiable {
    public let staffMemberID: UUID
    public let staffMemberName: String?
    public let staffKind: String
    public let employeeCode: String?
    public let isActive: Bool
    public let dayFrom: String
    public let dayTo: String
    public let machines: Int
    public let dailyReportsMissing: Int
    public let dailyReportsLate: Int
    public let unexplainedHours: DecimalString
    public let unexplainedItems: Int
    public let alerts: Int
    public let alertsOpen: Int
    public let alertsAcknowledged: Int
    public let avgHoursToAcknowledge: DecimalString?
    public let maxHoursToAcknowledge: DecimalString?
    public let cashHeld: [CashHeldDTO]
    public let cashHeldTooLong: Int
    public let cashDifferences: Int
    public let cashDifferenceTotals: [AmountByCurrencyDTO]
    public let cashDifferencesNearThreshold: Int
    public let revenueDifferences: Int
    public let revenueDifferenceTotals: [AmountByCurrencyDTO]
    public let refusedAttempts: Int
    /// Nil while site check-ins were never required in the period.
    public let checkinsMissed: Int?
    public let checkinsMade: Int
    public let patternSignals: Int
    public let itemsTotal: Int

    public var id: UUID { staffMemberID }

    enum CodingKeys: String, CodingKey {
        case machines, alerts
        case staffMemberID = "staff_member_id", staffMemberName = "staff_member_name", staffKind = "staff_kind"
        case employeeCode = "employee_code", isActive = "is_active", dayFrom = "day_from", dayTo = "day_to"
        case dailyReportsMissing = "daily_reports_missing", dailyReportsLate = "daily_reports_late"
        case unexplainedHours = "unexplained_hours", unexplainedItems = "unexplained_items", alertsOpen = "alerts_open"
        case alertsAcknowledged = "alerts_acknowledged", avgHoursToAcknowledge = "avg_hours_to_acknowledge"
        case maxHoursToAcknowledge = "max_hours_to_acknowledge", cashHeld = "cash_held", cashHeldTooLong = "cash_held_too_long"
        case cashDifferences = "cash_differences", cashDifferenceTotals = "cash_difference_totals"
        case cashDifferencesNearThreshold = "cash_differences_near_threshold", revenueDifferences = "revenue_differences"
        case revenueDifferenceTotals = "revenue_difference_totals", refusedAttempts = "refused_attempts"
        case checkinsMissed = "checkins_missed", checkinsMade = "checkins_made", patternSignals = "pattern_signals"
        case itemsTotal = "items_total"
    }

    public init(from decoder: any Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        staffMemberID = try c.decode(UUID.self, forKey: .staffMemberID)
        staffMemberName = try c.decodeIfPresent(String.self, forKey: .staffMemberName)
        staffKind = try c.decode(String.self, forKey: .staffKind)
        employeeCode = try c.decodeIfPresent(String.self, forKey: .employeeCode)
        isActive = try c.decode(Bool.self, forKey: .isActive)
        dayFrom = try c.decode(String.self, forKey: .dayFrom)
        dayTo = try c.decode(String.self, forKey: .dayTo)
        machines = try c.decode(Int.self, forKey: .machines)
        dailyReportsMissing = try c.decode(Int.self, forKey: .dailyReportsMissing)
        dailyReportsLate = try c.decode(Int.self, forKey: .dailyReportsLate)
        unexplainedHours = try c.decode(DecimalString.self, forKey: .unexplainedHours)
        unexplainedItems = try c.decode(Int.self, forKey: .unexplainedItems)
        alerts = try c.decode(Int.self, forKey: .alerts)
        alertsOpen = try c.decode(Int.self, forKey: .alertsOpen)
        alertsAcknowledged = try c.decode(Int.self, forKey: .alertsAcknowledged)
        avgHoursToAcknowledge = try c.decodeIfPresent(DecimalString.self, forKey: .avgHoursToAcknowledge)
        maxHoursToAcknowledge = try c.decodeIfPresent(DecimalString.self, forKey: .maxHoursToAcknowledge)
        cashHeld = try c.decodeIfPresent([CashHeldDTO].self, forKey: .cashHeld) ?? []
        cashHeldTooLong = try c.decode(Int.self, forKey: .cashHeldTooLong)
        cashDifferences = try c.decode(Int.self, forKey: .cashDifferences)
        cashDifferenceTotals = try c.decodeIfPresent([AmountByCurrencyDTO].self, forKey: .cashDifferenceTotals) ?? []
        cashDifferencesNearThreshold = try c.decode(Int.self, forKey: .cashDifferencesNearThreshold)
        revenueDifferences = try c.decode(Int.self, forKey: .revenueDifferences)
        revenueDifferenceTotals = try c.decodeIfPresent([AmountByCurrencyDTO].self, forKey: .revenueDifferenceTotals) ?? []
        refusedAttempts = try c.decode(Int.self, forKey: .refusedAttempts)
        checkinsMissed = try c.decodeIfPresent(Int.self, forKey: .checkinsMissed)
        checkinsMade = try c.decode(Int.self, forKey: .checkinsMade)
        patternSignals = try c.decode(Int.self, forKey: .patternSignals)
        itemsTotal = try c.decode(Int.self, forKey: .itemsTotal)
    }
}

/// `ScorecardRecordDto`: one record behind a scorecard item (`record_type` + `record_id` name the record).
public struct ScorecardRecordDTO: Codable, Hashable, Sendable {
    public let item: ScorecardItem
    public let recordType: String
    public let recordID: UUID?
    public let at: Date
    public let day: String?
    public let jobID: UUID?
    public let jobNumber: String?
    public let machineID: UUID?
    public let machineCode: String?
    public let machineName: String?
    public let amount: DecimalString?
    public let currency: String?
    public let hours: DecimalString?
    public let status: String?
    public let nearThreshold: Bool
    public let detail: JSONValue?

    enum CodingKeys: String, CodingKey {
        case item, at, day, amount, currency, hours, status, detail
        case recordType = "record_type", recordID = "record_id", jobID = "job_id", jobNumber = "job_number"
        case machineID = "machine_id", machineCode = "machine_code", machineName = "machine_name"
        case nearThreshold = "near_threshold"
    }

    public init(from decoder: any Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        item = try c.decode(ScorecardItem.self, forKey: .item)
        recordType = try c.decode(String.self, forKey: .recordType)
        recordID = try c.decodeIfPresent(UUID.self, forKey: .recordID)
        at = try c.decode(Date.self, forKey: .at)
        day = try c.decodeIfPresent(String.self, forKey: .day)
        jobID = try c.decodeIfPresent(UUID.self, forKey: .jobID)
        jobNumber = try c.decodeIfPresent(String.self, forKey: .jobNumber)
        machineID = try c.decodeIfPresent(UUID.self, forKey: .machineID)
        machineCode = try c.decodeIfPresent(String.self, forKey: .machineCode)
        machineName = try c.decodeIfPresent(String.self, forKey: .machineName)
        amount = try c.decodeIfPresent(DecimalString.self, forKey: .amount)
        currency = try c.decodeIfPresent(String.self, forKey: .currency)
        hours = try c.decodeIfPresent(DecimalString.self, forKey: .hours)
        status = try c.decodeIfPresent(String.self, forKey: .status)
        nearThreshold = try c.decodeIfPresent(Bool.self, forKey: .nearThreshold) ?? false
        let value = try? c.decodeIfPresent(JSONValue.self, forKey: .detail)
        detail = value == .null ? nil : value ?? nil
    }
}

/// `ScorecardDetailDto` (`GET /scorecard/{staff_member_id}`).
public struct ScorecardDetailDTO: Codable, Hashable, Sendable {
    public let row: ScorecardRowDTO
    public let records: [ScorecardRecordDTO]
}

// MARK: - Unbilled work, idle machines

/// `UnbilledJobDto`: completed, billing-ready work not on an issued invoice after the tenant's days.
public struct UnbilledJobDTO: Codable, Hashable, Sendable, Identifiable {
    public let jobID: UUID
    public let jobNumber: String?
    public let machineID: UUID
    public let machineCode: String?
    public let machineName: String?
    public let customerID: UUID
    public let customerName: String?
    public let jobSiteID: UUID?
    public let jobSiteName: String?
    public let supervisorStaffID: UUID?
    public let supervisorStaffName: String?
    public let completedAt: Date
    public let daysUnbilled: Int
    public let billableHours: DecimalString?
    public let currency: String
    /// What the job is worth under its terms.
    public let total: DecimalString?
    /// A draft invoice already holds the job (not issued yet).
    public let draftInvoiceID: UUID?

    public var id: UUID { jobID }

    enum CodingKeys: String, CodingKey {
        case currency, total
        case jobID = "job_id", jobNumber = "job_number", machineID = "machine_id", machineCode = "machine_code"
        case machineName = "machine_name", customerID = "customer_id", customerName = "customer_name"
        case jobSiteID = "job_site_id", jobSiteName = "job_site_name", supervisorStaffID = "supervisor_staff_id"
        case supervisorStaffName = "supervisor_staff_name", completedAt = "completed_at", daysUnbilled = "days_unbilled"
        case billableHours = "billable_hours", draftInvoiceID = "draft_invoice_id"
    }
}

/// `IdleMachineDto`: a machine without work or engine activity for the tenant's days.
public struct IdleMachineDTO: Codable, Hashable, Sendable, Identifiable {
    public let machineID: UUID
    public let machineCode: String?
    public let machineName: String?
    public let categoryID: UUID?
    public let idleSince: Date
    public let idleDays: Int
    public let lastJobID: UUID?
    public let lastJobNumber: String?
    public let lastJobCompletedAt: Date?
    /// Last meter increase or tracker engine-on.
    public let lastEngineActivityAt: Date?
    /// An approved job not started yet.
    public let plannedJobID: UUID?
    public let plannedJobNumber: String?

    public var id: UUID { machineID }

    enum CodingKeys: String, CodingKey {
        case machineID = "machine_id", machineCode = "machine_code", machineName = "machine_name", categoryID = "category_id"
        case idleSince = "idle_since", idleDays = "idle_days", lastJobID = "last_job_id", lastJobNumber = "last_job_number"
        case lastJobCompletedAt = "last_job_completed_at", lastEngineActivityAt = "last_engine_activity_at"
        case plannedJobID = "planned_job_id", plannedJobNumber = "planned_job_number"
    }
}
