import Foundation

// DEC-031 Phase 5 (oversight): the people scorecard and idle machines. Shapes follow `contracts/openapi.json`
// (`ScorecardRowDto`, `ScorecardDetailDto`, `ScorecardRecordDto`, `IdleMachineDto`); same as Android.

extension TenantCapability {
    /// The per-person scorecard (`tenant.oversight.scorecard.read`).
    public static let scorecard = "SCORECARD"
    /// Machines without approved machine-report hours for N days.
    public static let idleMachines = "IDLE_MACHINES"
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
    public static let refusedAttempt = ScorecardItem(rawValue: "REFUSED_ATTEMPT")
    public static let patternSignal = ScorecardItem(rawValue: "PATTERN_SIGNAL")

    /// The filterable items, in the server's order (the detail `?item=` values).
    public static let filterable: [ScorecardItem] = [
        .missingDailyReport, .lateDailyReport, .unexplainedHours, .alert, .cashHeldTooLong, .cashDifference, .refusedAttempt,
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
    public let refusedAttempts: Int
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
        case cashDifferencesNearThreshold = "cash_differences_near_threshold", refusedAttempts = "refused_attempts"
        case patternSignals = "pattern_signals"
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
        refusedAttempts = try c.decode(Int.self, forKey: .refusedAttempts)
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
        case recordType = "record_type", recordID = "record_id"
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

// MARK: - Idle machines

/// `IdleMachineDto`: an active machine with no approved machine-report hours for the tenant's days.
public struct IdleMachineDTO: Codable, Hashable, Sendable, Identifiable {
    public let machineID: UUID
    public let machineCode: String?
    public let machineName: String?
    public let categoryID: UUID?
    public let idleSince: Date
    public let idleDays: Int
    /// The machine's latest machine report, if any.
    public let lastMachineReportID: UUID?
    public let lastMachineReportNumber: String?
    /// Last meter increase or tracker engine-on.
    public let lastEngineActivityAt: Date?

    public var id: UUID { machineID }

    enum CodingKeys: String, CodingKey {
        case machineID = "machine_id", machineCode = "machine_code", machineName = "machine_name", categoryID = "category_id"
        case idleSince = "idle_since", idleDays = "idle_days", lastMachineReportID = "last_machine_report_id"
        case lastMachineReportNumber = "last_machine_report_number", lastEngineActivityAt = "last_engine_activity_at"
    }
}
