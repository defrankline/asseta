import Foundation

// DEC-031 Phase 1 (revenue reconciliation): revenue differences, non-revenue time inside jobs and its approvals, and the
// daily machine sheet. Shapes follow `contracts/openapi.json`. Online only in both apps (no sync operations). Display
// names beside ids are nullable (older servers send none): the apps show the name, else a short id.

extension TenantCapability {
    /// Revenue checks (`REVENUE_RECONCILIATION`, platform default off): the daily machine sheet, revenue differences
    /// and non-revenue approvals. Off = the server answers 422 `REVENUE_RECONCILIATION_DISABLED` and hides the menus.
    public static let revenueReconciliation = "REVENUE_RECONCILIATION"
}

/// The revenue permissions (`tenant.revenue.*`).
public enum RevenuePermission {
    /// The daily machine sheet, revenue differences, non-revenue activities and approvals.
    public static let read = "tenant.revenue.read"
    /// Explain a revenue difference or non-revenue time (a second person decides).
    public static let explain = "tenant.revenue.explain"
    /// Decide on explanations, confirm differences and manage the revenue reasons.
    public static let decide = "tenant.revenue.decide"
}

/// `RevenueDifferenceStatus`.
public enum RevenueDifferenceStatus {
    public static let open = "OPEN"
    public static let explanationProposed = "EXPLANATION_PROPOSED"
    public static let explained = "EXPLAINED"
    public static let confirmed = "CONFIRMED"
    public static let cleared = "CLEARED"
    /// Still waiting for someone (to explain, or to decide on an explanation).
    public static let pending: Set<String> = [open, explanationProposed]
}

/// `RevenueAdjustmentDto`: an append-only change to a decided difference after a later approval recomputed it.
public struct RevenueAdjustmentDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let amount: DecimalString
    public let causeID: UUID
    public let causeType: String
    public let createdAt: Date
    public let createdBy: UUID?
    public let createdByName: String?
    public let previousDifference: DecimalString
    public let newDifference: DecimalString

    enum CodingKeys: String, CodingKey {
        case id, amount, causeID = "cause_id", causeType = "cause_type", createdAt = "created_at", createdBy = "created_by"
        case createdByName = "created_by_name", previousDifference = "previous_difference", newDifference = "new_difference"
    }
}

/// `RevenueDifferenceDto`: one machine-period whose money attributed fell short of the revenue expected from its hours.
public struct RevenueDifferenceDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let machineID: UUID
    public let machineCode: String?
    public let machineName: String?
    public let jobID: UUID?
    public let jobNumber: String?
    public let periodKind: String
    public let periodKey: String
    public let periodStart: Date
    public let periodEnd: Date
    /// Tenant-local days (`YYYY-MM-DD`), inclusive.
    public let localFrom: String
    public let localTo: String
    public let currency: String
    public let customerWorkHours: DecimalString
    public let nonRevenueHours: DecimalString
    public let unexplainedHours: DecimalString
    public let expectedAmount: DecimalString
    public let unexplainedExpectedAmount: DecimalString
    public let attributedAmount: DecimalString
    public let inProgressAmount: DecimalString
    public let difference: DecimalString
    public let adjustedDifference: DecimalString?
    public let adjustments: [RevenueAdjustmentDTO]
    public let status: String
    public let reasonID: UUID?
    public let reasonName: String?
    public let explanationNote: String?
    public let explainedBy: UUID?
    public let explainedByName: String?
    public let explainedAt: Date?
    public let decidedBy: UUID?
    public let decidedByName: String?
    public let decidedAt: Date?
    public let decisionNote: String?
    public let caseID: UUID?
    public let caseNumber: String?
    public let openedAt: Date
    public let computedAt: Date
    public let policyVersion: String
    /// Server breakdown (`jobs`, `money_sources`, `unexplained`), read leniently.
    public let detail: JSONValue?

    public var isPending: Bool { RevenueDifferenceStatus.pending.contains(status) }

    public init(from decoder: any Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(UUID.self, forKey: .id)
        machineID = try c.decode(UUID.self, forKey: .machineID)
        machineCode = try c.decodeIfPresent(String.self, forKey: .machineCode)
        machineName = try c.decodeIfPresent(String.self, forKey: .machineName)
        jobID = try c.decodeIfPresent(UUID.self, forKey: .jobID)
        jobNumber = try c.decodeIfPresent(String.self, forKey: .jobNumber)
        periodKind = try c.decode(String.self, forKey: .periodKind)
        periodKey = try c.decode(String.self, forKey: .periodKey)
        periodStart = try c.decode(Date.self, forKey: .periodStart)
        periodEnd = try c.decode(Date.self, forKey: .periodEnd)
        localFrom = try c.decode(String.self, forKey: .localFrom)
        localTo = try c.decode(String.self, forKey: .localTo)
        currency = try c.decode(String.self, forKey: .currency)
        customerWorkHours = try c.decode(DecimalString.self, forKey: .customerWorkHours)
        nonRevenueHours = try c.decode(DecimalString.self, forKey: .nonRevenueHours)
        unexplainedHours = try c.decode(DecimalString.self, forKey: .unexplainedHours)
        expectedAmount = try c.decode(DecimalString.self, forKey: .expectedAmount)
        unexplainedExpectedAmount = try c.decode(DecimalString.self, forKey: .unexplainedExpectedAmount)
        attributedAmount = try c.decode(DecimalString.self, forKey: .attributedAmount)
        inProgressAmount = try c.decode(DecimalString.self, forKey: .inProgressAmount)
        difference = try c.decode(DecimalString.self, forKey: .difference)
        adjustedDifference = try c.decodeIfPresent(DecimalString.self, forKey: .adjustedDifference)
        adjustments = try c.decodeIfPresent([RevenueAdjustmentDTO].self, forKey: .adjustments) ?? []
        status = try c.decode(String.self, forKey: .status)
        reasonID = try c.decodeIfPresent(UUID.self, forKey: .reasonID)
        reasonName = try c.decodeIfPresent(String.self, forKey: .reasonName)
        explanationNote = try c.decodeIfPresent(String.self, forKey: .explanationNote)
        explainedBy = try c.decodeIfPresent(UUID.self, forKey: .explainedBy)
        explainedByName = try c.decodeIfPresent(String.self, forKey: .explainedByName)
        explainedAt = try c.decodeIfPresent(Date.self, forKey: .explainedAt)
        decidedBy = try c.decodeIfPresent(UUID.self, forKey: .decidedBy)
        decidedByName = try c.decodeIfPresent(String.self, forKey: .decidedByName)
        decidedAt = try c.decodeIfPresent(Date.self, forKey: .decidedAt)
        decisionNote = try c.decodeIfPresent(String.self, forKey: .decisionNote)
        caseID = try c.decodeIfPresent(UUID.self, forKey: .caseID)
        caseNumber = try c.decodeIfPresent(String.self, forKey: .caseNumber)
        openedAt = try c.decode(Date.self, forKey: .openedAt)
        computedAt = try c.decode(Date.self, forKey: .computedAt)
        policyVersion = try c.decode(String.self, forKey: .policyVersion)
        detail = try? c.decodeIfPresent(JSONValue.self, forKey: .detail)
    }

    /// One job's figures inside the period (`detail.jobs`).
    public struct DetailJob: Hashable, Sendable {
        public let jobID: UUID?
        public let jobNumber: String?
        public let currency: String
        public let expected: Decimal
        public let inProgress: Decimal
        public let attributed: Decimal
    }

    /// `detail.jobs` of this difference's currency (entries that do not read are skipped).
    public var detailJobs: [DetailJob] {
        guard case let .array(items)? = detail?["jobs"] else { return [] }
        return items.compactMap { item in
            guard let currency = item["currency"]?.stringValue, currency == self.currency else { return nil }
            func amount(_ key: String) -> Decimal { item[key]?.stringValue.flatMap { DecimalString(string: $0)?.value } ?? 0 }
            return DetailJob(jobID: item["job_id"]?.stringValue.flatMap(UUID.init(uuidString:)),
                             jobNumber: item["job_number"]?.stringValue, currency: currency, expected: amount("expected"),
                             inProgress: amount("in_progress"), attributed: amount("attributed"))
        }
    }

    enum CodingKeys: String, CodingKey {
        case id, currency, difference, adjustments, status, detail
        case machineID = "machine_id", machineCode = "machine_code", machineName = "machine_name", jobID = "job_id"
        case jobNumber = "job_number", periodKind = "period_kind", periodKey = "period_key", periodStart = "period_start"
        case periodEnd = "period_end", localFrom = "local_from", localTo = "local_to"
        case customerWorkHours = "customer_work_hours", nonRevenueHours = "non_revenue_hours"
        case unexplainedHours = "unexplained_hours", expectedAmount = "expected_amount"
        case unexplainedExpectedAmount = "unexplained_expected_amount", attributedAmount = "attributed_amount"
        case inProgressAmount = "in_progress_amount", adjustedDifference = "adjusted_difference"
        case reasonID = "reason_id", reasonName = "reason_name", explanationNote = "explanation_note"
        case explainedBy = "explained_by", explainedByName = "explained_by_name", explainedAt = "explained_at"
        case decidedBy = "decided_by", decidedByName = "decided_by_name", decidedAt = "decided_at"
        case decisionNote = "decision_note", caseID = "case_id", caseNumber = "case_number", openedAt = "opened_at"
        case computedAt = "computed_at", policyVersion = "policy_version"
    }
}

/// `RevenueReasonDto`: a tenant reason that explains a revenue difference or non-revenue time.
public struct RevenueReasonDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let code: String
    public let name: String
    public let description: String?
    public let isActive: Bool
    public let version: Int

    public init(id: UUID, code: String, name: String, description: String? = nil, isActive: Bool = true, version: Int = 1) {
        self.id = id
        self.code = code
        self.name = name
        self.description = description
        self.isActive = isActive
        self.version = version
    }

    enum CodingKeys: String, CodingKey { case id, code, name, description, version, isActive = "is_active" }
}

/// `RevenueExplanationIn`: why a revenue difference happened (tenant reason + a 5..2000 character note).
public struct RevenueExplanationIn: Codable, Hashable, Sendable {
    public let reasonID: UUID
    public let note: String

    public init(reasonID: UUID, note: String) {
        self.reasonID = reasonID
        self.note = note
    }

    enum CodingKeys: String, CodingKey { case note, reasonID = "reason_id" }
}

/// `RevenueDecisionIn`: APPROVE / REJECT an explanation, or CONFIRM the difference is real (5..2000 character note).
public struct RevenueDecisionIn: Codable, Hashable, Sendable {
    public let decision: String
    public let note: String

    public init(decision: String, note: String) {
        self.decision = decision
        self.note = note
    }
}

/// `NonRevenueActivityDto`: a non-billable work-log entry of a declared non-revenue type (e.g. movement) with the
/// status of its explanation. Until APPROVED the time counts as revenue.
public struct NonRevenueActivityDTO: Codable, Hashable, Sendable, Identifiable {
    public let activityID: UUID
    public let activityType: String
    /// NONE (not explained yet), PROPOSED, APPROVED, REJECTED.
    public let approvalStatus: String
    public let approvalID: UUID?
    public let jobID: UUID
    public let jobNumber: String?
    public let machineID: UUID
    public let machineCode: String?
    public let machineName: String?
    public let startedAt: Date
    public let endedAt: Date
    public let hours: DecimalString
    public let note: String?

    public var id: UUID { activityID }

    public init(activityID: UUID, activityType: String, approvalStatus: String, approvalID: UUID?, jobID: UUID,
                jobNumber: String? = nil, machineID: UUID, machineCode: String? = nil, machineName: String? = nil,
                startedAt: Date, endedAt: Date, hours: Decimal, note: String? = nil) {
        self.activityID = activityID
        self.activityType = activityType
        self.approvalStatus = approvalStatus
        self.approvalID = approvalID
        self.jobID = jobID
        self.jobNumber = jobNumber
        self.machineID = machineID
        self.machineCode = machineCode
        self.machineName = machineName
        self.startedAt = startedAt
        self.endedAt = endedAt
        self.hours = DecimalString(hours)
        self.note = note
    }

    enum CodingKeys: String, CodingKey {
        case hours, note, activityID = "activity_id", activityType = "activity_type", approvalStatus = "approval_status"
        case approvalID = "approval_id", jobID = "job_id", jobNumber = "job_number", machineID = "machine_id"
        case machineCode = "machine_code", machineName = "machine_name", startedAt = "started_at", endedAt = "ended_at"
    }
}

/// `NonRevenueApprovalIn`: explain one work-log entry as non-revenue (tenant reason + a 5..2000 character note).
public struct NonRevenueApprovalIn: Codable, Hashable, Sendable {
    public let activityID: UUID
    public let reasonID: UUID
    public let note: String

    public init(activityID: UUID, reasonID: UUID, note: String) {
        self.activityID = activityID
        self.reasonID = reasonID
        self.note = note
    }

    enum CodingKeys: String, CodingKey { case note, activityID = "activity_id", reasonID = "reason_id" }
}

/// `NonRevenueApprovalDto`: an explanation of non-revenue time awaiting (or past) a second person's decision.
public struct NonRevenueApprovalDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let activityID: UUID
    public let activityType: String
    public let jobID: UUID
    public let jobNumber: String?
    public let machineID: UUID
    public let machineCode: String?
    public let machineName: String?
    public let startedAt: Date
    public let endedAt: Date
    public let hours: DecimalString
    public let reasonID: UUID
    public let reasonName: String?
    public let note: String
    public let status: String
    public let proposedBy: UUID?
    public let proposedByName: String?
    public let proposedAt: Date
    public let decidedBy: UUID?
    public let decidedByName: String?
    public let decidedAt: Date?
    public let decisionNote: String?
    public let policyVersion: String

    enum CodingKeys: String, CodingKey {
        case id, hours, note, status, activityID = "activity_id", activityType = "activity_type", jobID = "job_id"
        case jobNumber = "job_number", machineID = "machine_id", machineCode = "machine_code", machineName = "machine_name"
        case startedAt = "started_at", endedAt = "ended_at", reasonID = "reason_id", reasonName = "reason_name"
        case proposedBy = "proposed_by", proposedByName = "proposed_by_name", proposedAt = "proposed_at"
        case decidedBy = "decided_by", decidedByName = "decided_by_name", decidedAt = "decided_at"
        case decisionNote = "decision_note", policyVersion = "policy_version"
    }
}

// MARK: - Daily machine sheet (R2)

/// `SheetFlag` values.
public enum SheetFlag {
    public static let missingDailyReport = "MISSING_DAILY_REPORT"
    public static let unexplainedHours = "UNEXPLAINED_HOURS"
    public static let engineOnWithoutJob = "ENGINE_ON_WITHOUT_JOB"
    public static let fuelAboveNorm = "FUEL_ABOVE_NORM"
    public static let revenueDifference = "REVENUE_DIFFERENCE"
}

/// `SheetJobDto`: a job that ran on the machine that day.
public struct SheetJobDTO: Codable, Hashable, Sendable {
    public let jobID: UUID
    public let jobNumber: String?
    public let status: String
    public let billingMode: String
    public let customerID: UUID?
    public let customerName: String?
    public let jobSiteID: UUID?
    public let jobSiteName: String?
    public let customerWorkHours: DecimalString
    public let revenueHours: DecimalString

    enum CodingKeys: String, CodingKey {
        case status, jobID = "job_id", jobNumber = "job_number", billingMode = "billing_mode", customerID = "customer_id"
        case customerName = "customer_name", jobSiteID = "job_site_id", jobSiteName = "job_site_name"
        case customerWorkHours = "customer_work_hours", revenueHours = "revenue_hours"
    }
}

/// `SheetMoneyDto`: expected revenue vs money attributed, per currency.
public struct SheetMoneyDTO: Codable, Hashable, Sendable {
    public let currency: String
    public let expected: DecimalString
    public let inProgress: DecimalString
    public let attributed: DecimalString
    public let difference: DecimalString
    public let unexplainedHours: DecimalString?
    public let unexplainedExpected: DecimalString?

    enum CodingKeys: String, CodingKey {
        case currency, expected, attributed, difference, inProgress = "in_progress", unexplainedHours = "unexplained_hours"
        case unexplainedExpected = "unexplained_expected"
    }
}

/// `SheetReadingDto`.
public struct SheetReadingDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let kind: String
    public let reading: DecimalString
    public let capturedAt: Date
    public let state: String
    public let jobID: UUID?
    public let jobNumber: String?

    enum CodingKeys: String, CodingKey {
        case id, kind, reading, state, capturedAt = "captured_at", jobID = "job_id", jobNumber = "job_number"
    }
}

/// `SheetSegmentDto`: one reading-to-reading interval's share of the day.
public struct SheetSegmentDTO: Codable, Hashable, Sendable {
    public let kind: String
    public let classification: String
    public let review: String
    public let startAt: Date
    public let endAt: Date
    public let hoursInDay: DecimalString
    public let customerWorkHoursInDay: DecimalString
    public let jobID: UUID?
    public let jobNumber: String?
    public let nonRevenueByType: [String: DecimalString]

    enum CodingKeys: String, CodingKey {
        case kind, classification, review, startAt = "start_at", endAt = "end_at", hoursInDay = "hours_in_day"
        case customerWorkHoursInDay = "customer_work_hours_in_day", jobID = "job_id", jobNumber = "job_number"
        case nonRevenueByType = "non_revenue_by_type"
    }
}

/// `SheetMoneySourceDto`: an invoice line or prepaid consumption counted as money attributed.
public struct SheetMoneySourceDTO: Codable, Hashable, Sendable {
    public let source: String
    public let amount: DecimalString
    public let currency: String
    public let hours: DecimalString?
    public let jobID: UUID
    public let jobNumber: String?
    public let parentID: UUID
    public let refID: UUID

    enum CodingKeys: String, CodingKey {
        case source, amount, currency, hours, jobID = "job_id", jobNumber = "job_number", parentID = "parent_id", refID = "ref_id"
    }
}

/// `SheetFlagRefDto`: the record behind a flag.
public struct SheetFlagRefDTO: Codable, Hashable, Sendable {
    public let flag: String
    public let recordID: UUID
    public let recordType: String

    enum CodingKeys: String, CodingKey { case flag, recordID = "record_id", recordType = "record_type" }
}

/// `SheetFuelDto`.
public struct SheetFuelDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let eventType: String
    public let litres: DecimalString
    public let occurredAt: Date
    public let jobID: UUID?

    enum CodingKeys: String, CodingKey { case id, litres, eventType = "event_type", occurredAt = "occurred_at", jobID = "job_id" }
}

/// `DailyMachineSheetRowDto` (and, with the drill-down lists, `DailyMachineSheetDetailDto`): one machine on one
/// tenant-local day. The drill-down lists are empty on a list row.
public struct DailyMachineSheetDTO: Codable, Hashable, Sendable, Identifiable {
    public let machineID: UUID
    public let machineCode: String?
    public let machineName: String?
    /// Tenant-local day (`YYYY-MM-DD`).
    public let day: String
    public let firstReading: DecimalString?
    public let lastReading: DecimalString?
    public let readingCount: Int
    public let engineHours: DecimalString
    public let customerWorkHours: DecimalString
    public let nonRevenueHours: DecimalString
    public let nonRevenueByType: [String: DecimalString]
    public let nonRevenuePendingHours: DecimalString
    public let revenueHours: DecimalString
    public let approvedNonCustomerHours: DecimalString
    public let identifiedVarianceHours: DecimalString
    public let unexplainedHours: DecimalString
    public let pendingReviewHours: DecimalString
    public let fuelLitres: DecimalString
    public let jobs: [SheetJobDTO]
    public let money: [SheetMoneyDTO]
    public let flags: [String]
    public let readings: [SheetReadingDTO]
    public let segments: [SheetSegmentDTO]
    public let moneySources: [SheetMoneySourceDTO]
    public let flagRecords: [SheetFlagRefDTO]
    public let fuelEvents: [SheetFuelDTO]

    public var id: String { "\(machineID.uuidString.lowercased()):\(day)" }

    public init(from decoder: any Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        machineID = try c.decode(UUID.self, forKey: .machineID)
        machineCode = try c.decodeIfPresent(String.self, forKey: .machineCode)
        machineName = try c.decodeIfPresent(String.self, forKey: .machineName)
        day = try c.decode(String.self, forKey: .day)
        firstReading = try c.decodeIfPresent(DecimalString.self, forKey: .firstReading)
        lastReading = try c.decodeIfPresent(DecimalString.self, forKey: .lastReading)
        readingCount = try c.decode(Int.self, forKey: .readingCount)
        engineHours = try c.decode(DecimalString.self, forKey: .engineHours)
        customerWorkHours = try c.decode(DecimalString.self, forKey: .customerWorkHours)
        nonRevenueHours = try c.decode(DecimalString.self, forKey: .nonRevenueHours)
        nonRevenueByType = try c.decodeIfPresent([String: DecimalString].self, forKey: .nonRevenueByType) ?? [:]
        nonRevenuePendingHours = try c.decodeIfPresent(DecimalString.self, forKey: .nonRevenuePendingHours) ?? DecimalString(0)
        revenueHours = try c.decode(DecimalString.self, forKey: .revenueHours)
        approvedNonCustomerHours = try c.decode(DecimalString.self, forKey: .approvedNonCustomerHours)
        identifiedVarianceHours = try c.decode(DecimalString.self, forKey: .identifiedVarianceHours)
        unexplainedHours = try c.decode(DecimalString.self, forKey: .unexplainedHours)
        pendingReviewHours = try c.decode(DecimalString.self, forKey: .pendingReviewHours)
        fuelLitres = try c.decode(DecimalString.self, forKey: .fuelLitres)
        jobs = try c.decodeIfPresent([SheetJobDTO].self, forKey: .jobs) ?? []
        money = try c.decodeIfPresent([SheetMoneyDTO].self, forKey: .money) ?? []
        flags = try c.decodeIfPresent([String].self, forKey: .flags) ?? []
        readings = try c.decodeIfPresent([SheetReadingDTO].self, forKey: .readings) ?? []
        segments = try c.decodeIfPresent([SheetSegmentDTO].self, forKey: .segments) ?? []
        moneySources = try c.decodeIfPresent([SheetMoneySourceDTO].self, forKey: .moneySources) ?? []
        flagRecords = try c.decodeIfPresent([SheetFlagRefDTO].self, forKey: .flagRecords) ?? []
        fuelEvents = try c.decodeIfPresent([SheetFuelDTO].self, forKey: .fuelEvents) ?? []
    }

    enum CodingKeys: String, CodingKey {
        case day, jobs, money, flags, readings, segments
        case machineID = "machine_id", machineCode = "machine_code", machineName = "machine_name"
        case firstReading = "first_reading", lastReading = "last_reading", readingCount = "reading_count"
        case engineHours = "engine_hours", customerWorkHours = "customer_work_hours", nonRevenueHours = "non_revenue_hours"
        case nonRevenueByType = "non_revenue_by_type", nonRevenuePendingHours = "non_revenue_pending_hours"
        case revenueHours = "revenue_hours", approvedNonCustomerHours = "approved_non_customer_hours"
        case identifiedVarianceHours = "identified_variance_hours", unexplainedHours = "unexplained_hours"
        case pendingReviewHours = "pending_review_hours", fuelLitres = "fuel_litres", moneySources = "money_sources"
        case flagRecords = "flag_records", fuelEvents = "fuel_events"
    }
}
