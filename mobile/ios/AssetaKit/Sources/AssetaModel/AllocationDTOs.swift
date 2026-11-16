import Foundation

// DEC-032 Phase 1 (every engine hour allocated): the work allocation ledger, allocation corrections and the daily
// operational report (reviewed in the Owner app). Shapes follow `contracts/openapi.json`.

extension SyncCapability {
    /// `SyncData.unbillable_reasons`: the tenant's unbillable reasons (still announced; the app stores them only).
    public static let unbillableReasons = "SYNC_UNBILLABLE_REASONS"
}

/// `AllocationKind` wire values (kept as strings so a newer server never breaks the app).
public enum AllocationKinds {
    public static let customerWork = "CUSTOMER_WORK"
    public static let authorizedActivity = "AUTHORIZED_ACTIVITY"
    public static let unexplained = "UNEXPLAINED"
}

/// `AllocationStatus` wire values.
public enum AllocationStatuses {
    public static let proposed = "PROPOSED"
    public static let active = "ACTIVE"
    public static let superseded = "SUPERSEDED"
    public static let rejected = "REJECTED"
}

/// `DailyReportStatus` wire values.
public enum DailyReportStatuses {
    public static let submitted = "SUBMITTED"
    public static let reviewed = "REVIEWED"
    public static let returned = "RETURNED"
    public static let superseded = "SUPERSEDED"
}

/// `UnbillableLineDto`.
public struct UnbillableLineDTO: Codable, Hashable, Sendable {
    public let reasonID: UUID
    public let reasonName: String?
    public let hours: DecimalString

    enum CodingKeys: String, CodingKey { case hours, reasonID = "reason_id", reasonName = "reason_name" }
}

/// `ReportAllocationDto`: one allocation of the machine-day, on a daily report or its pre-fill.
public struct ReportAllocationDTO: Codable, Hashable, Sendable, Identifiable {
    public let allocationID: UUID
    public let kind: String
    public let customerID: UUID?
    public let customerName: String?
    public let startReading: DecimalString
    public let endReading: DecimalString
    public let hours: DecimalString

    public var id: UUID { allocationID }

    enum CodingKeys: String, CodingKey {
        case kind, hours
        case allocationID = "allocation_id", customerID = "customer_id", customerName = "customer_name"
        case startReading = "start_reading", endReading = "end_reading"
    }
}

/// `DailyReportDto`.
public struct DailyReportDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let machineID: UUID
    public let machineCode: String?
    public let machineName: String?
    /// `YYYY-MM-DD`, tenant-local.
    public let reportDate: String
    public let openingRef: UUID
    public let closingRef: UUID
    public let openingReading: DecimalString
    public let closingReading: DecimalString
    public let totalHours: DecimalString
    public let billableHours: DecimalString
    public let unbillableHours: DecimalString
    public let differenceHours: DecimalString
    public let unbillable: [UnbillableLineDTO]
    public let allocations: [ReportAllocationDTO]
    public let note: String?
    public let evidenceAttachmentIDs: [UUID]
    public let status: String
    public let source: String
    public let policyVersion: String
    public let isDuplicate: Bool
    public let duplicateOfID: UUID?
    public let isLate: Bool
    public let supersedesID: UUID?
    public let submittedAt: Date
    public let submittedBy: UUID?
    public let submittedByName: String?
    public let clientCreatedAt: Date
    public let reviewedAt: Date?
    public let reviewedBy: UUID?
    public let reviewedByName: String?
    public let reviewNote: String?

    public init(from decoder: any Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(UUID.self, forKey: .id)
        machineID = try c.decode(UUID.self, forKey: .machineID)
        machineCode = try c.decodeIfPresent(String.self, forKey: .machineCode)
        machineName = try c.decodeIfPresent(String.self, forKey: .machineName)
        reportDate = try c.decode(String.self, forKey: .reportDate)
        openingRef = try c.decode(UUID.self, forKey: .openingRef)
        closingRef = try c.decode(UUID.self, forKey: .closingRef)
        openingReading = try c.decode(DecimalString.self, forKey: .openingReading)
        closingReading = try c.decode(DecimalString.self, forKey: .closingReading)
        totalHours = try c.decode(DecimalString.self, forKey: .totalHours)
        billableHours = try c.decode(DecimalString.self, forKey: .billableHours)
        unbillableHours = try c.decode(DecimalString.self, forKey: .unbillableHours)
        differenceHours = try c.decode(DecimalString.self, forKey: .differenceHours)
        unbillable = try c.decodeIfPresent([UnbillableLineDTO].self, forKey: .unbillable) ?? []
        allocations = try c.decodeIfPresent([ReportAllocationDTO].self, forKey: .allocations) ?? []
        note = try c.decodeIfPresent(String.self, forKey: .note)
        evidenceAttachmentIDs = try c.decodeIfPresent([UUID].self, forKey: .evidenceAttachmentIDs) ?? []
        status = try c.decode(String.self, forKey: .status)
        source = try c.decodeIfPresent(String.self, forKey: .source) ?? ""
        policyVersion = try c.decodeIfPresent(String.self, forKey: .policyVersion) ?? ""
        isDuplicate = try c.decodeIfPresent(Bool.self, forKey: .isDuplicate) ?? false
        duplicateOfID = try c.decodeIfPresent(UUID.self, forKey: .duplicateOfID)
        isLate = try c.decodeIfPresent(Bool.self, forKey: .isLate) ?? false
        supersedesID = try c.decodeIfPresent(UUID.self, forKey: .supersedesID)
        submittedAt = try c.decode(Date.self, forKey: .submittedAt)
        submittedBy = try c.decodeIfPresent(UUID.self, forKey: .submittedBy)
        submittedByName = try c.decodeIfPresent(String.self, forKey: .submittedByName)
        clientCreatedAt = try c.decode(Date.self, forKey: .clientCreatedAt)
        reviewedAt = try c.decodeIfPresent(Date.self, forKey: .reviewedAt)
        reviewedBy = try c.decodeIfPresent(UUID.self, forKey: .reviewedBy)
        reviewedByName = try c.decodeIfPresent(String.self, forKey: .reviewedByName)
        reviewNote = try c.decodeIfPresent(String.self, forKey: .reviewNote)
    }

    enum CodingKeys: String, CodingKey {
        case id, unbillable, allocations, note, status, source
        case machineID = "machine_id", machineCode = "machine_code", machineName = "machine_name"
        case reportDate = "report_date", openingRef = "opening_ref", closingRef = "closing_ref"
        case openingReading = "opening_reading", closingReading = "closing_reading", totalHours = "total_hours"
        case billableHours = "billable_hours", unbillableHours = "unbillable_hours", differenceHours = "difference_hours"
        case evidenceAttachmentIDs = "evidence_attachment_ids", policyVersion = "policy_version"
        case isDuplicate = "is_duplicate", duplicateOfID = "duplicate_of_id", isLate = "is_late"
        case supersedesID = "supersedes_id", submittedAt = "submitted_at", submittedBy = "submitted_by"
        case submittedByName = "submitted_by_name", clientCreatedAt = "client_created_at", reviewedAt = "reviewed_at"
        case reviewedBy = "reviewed_by", reviewedByName = "reviewed_by_name", reviewNote = "review_note"
    }
}

/// `DailyReportPrefillDto`: what the server already knows of the machine-day.
public struct DailyReportPrefillDTO: Codable, Hashable, Sendable {
    public let machineID: UUID
    public let machineCode: String?
    public let machineName: String?
    public let reportDate: String
    public let openingRef: UUID?
    public let openingReading: DecimalString?
    public let openingAt: Date?
    public let closingRef: UUID?
    public let closingReading: DecimalString?
    public let closingAt: Date?
    public let totalHours: DecimalString?
    public let customerHours: DecimalString
    public let authorizedHours: DecimalString
    public let unexplainedHours: DecimalString
    public let allocations: [ReportAllocationDTO]
    public let existingReportIDs: [UUID]

    enum CodingKeys: String, CodingKey {
        case allocations
        case machineID = "machine_id", machineCode = "machine_code", machineName = "machine_name"
        case reportDate = "report_date", openingRef = "opening_ref", openingReading = "opening_reading"
        case openingAt = "opening_at", closingRef = "closing_ref", closingReading = "closing_reading"
        case closingAt = "closing_at", totalHours = "total_hours", customerHours = "customer_hours"
        case authorizedHours = "authorized_hours", unexplainedHours = "unexplained_hours"
        case existingReportIDs = "existing_report_ids"
    }
}

/// `DailyReportReviewIn` (`REVIEWED` / `RETURNED`).
public struct DailyReportReviewIn: Encodable, Sendable {
    public let decision: String
    public let note: String

    public init(decision: String, note: String) {
        self.decision = decision
        self.note = note
    }
}

/// `AllocationLotDto`: the prepaid purchase hours an allocation drew from.
public struct AllocationLotDTO: Codable, Hashable, Sendable {
    public let purchaseID: UUID
    public let purchaseNumber: String?
    public let hours: DecimalString

    enum CodingKeys: String, CodingKey { case hours, purchaseID = "purchase_id", purchaseNumber = "purchase_number" }
}

/// `WorkAllocationDto`: one append-only entry of the work allocation ledger.
public struct WorkAllocationDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let machineID: UUID
    public let machineCode: String?
    public let machineName: String?
    /// `YYYY-MM-DD`, tenant-local.
    public let workDate: String
    public let kind: String
    public let status: String
    public let source: String
    public let hours: DecimalString
    public let startRef: UUID?
    public let startReading: DecimalString
    public let startAt: Date
    public let endRef: UUID?
    public let endReading: DecimalString
    public let endAt: Date
    public let customerID: UUID?
    public let customerName: String?
    public let reasonID: UUID?
    public let reasonName: String?
    public let lots: [AllocationLotDTO]
    public let evidenceAttachmentIDs: [UUID]
    public let correctionGroupID: UUID?
    public let correctionReason: String?
    public let supersedesID: UUID?
    public let supersededAt: Date?
    public let supersededByIDs: [UUID]
    public let recordedBy: UUID?
    public let recordedByName: String?
    public let decidedAt: Date?
    public let decidedBy: UUID?
    public let decidedByName: String?
    public let decisionNote: String?
    public let createdAt: Date

    public init(from decoder: any Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(UUID.self, forKey: .id)
        machineID = try c.decode(UUID.self, forKey: .machineID)
        machineCode = try c.decodeIfPresent(String.self, forKey: .machineCode)
        machineName = try c.decodeIfPresent(String.self, forKey: .machineName)
        workDate = try c.decode(String.self, forKey: .workDate)
        kind = try c.decode(String.self, forKey: .kind)
        status = try c.decode(String.self, forKey: .status)
        source = try c.decodeIfPresent(String.self, forKey: .source) ?? ""
        hours = try c.decode(DecimalString.self, forKey: .hours)
        startRef = try c.decodeIfPresent(UUID.self, forKey: .startRef)
        startReading = try c.decode(DecimalString.self, forKey: .startReading)
        startAt = try c.decode(Date.self, forKey: .startAt)
        endRef = try c.decodeIfPresent(UUID.self, forKey: .endRef)
        endReading = try c.decode(DecimalString.self, forKey: .endReading)
        endAt = try c.decode(Date.self, forKey: .endAt)
        customerID = try c.decodeIfPresent(UUID.self, forKey: .customerID)
        customerName = try c.decodeIfPresent(String.self, forKey: .customerName)
        reasonID = try c.decodeIfPresent(UUID.self, forKey: .reasonID)
        reasonName = try c.decodeIfPresent(String.self, forKey: .reasonName)
        lots = try c.decodeIfPresent([AllocationLotDTO].self, forKey: .lots) ?? []
        evidenceAttachmentIDs = try c.decodeIfPresent([UUID].self, forKey: .evidenceAttachmentIDs) ?? []
        correctionGroupID = try c.decodeIfPresent(UUID.self, forKey: .correctionGroupID)
        correctionReason = try c.decodeIfPresent(String.self, forKey: .correctionReason)
        supersedesID = try c.decodeIfPresent(UUID.self, forKey: .supersedesID)
        supersededAt = try c.decodeIfPresent(Date.self, forKey: .supersededAt)
        supersededByIDs = try c.decodeIfPresent([UUID].self, forKey: .supersededByIDs) ?? []
        recordedBy = try c.decodeIfPresent(UUID.self, forKey: .recordedBy)
        recordedByName = try c.decodeIfPresent(String.self, forKey: .recordedByName)
        decidedAt = try c.decodeIfPresent(Date.self, forKey: .decidedAt)
        decidedBy = try c.decodeIfPresent(UUID.self, forKey: .decidedBy)
        decidedByName = try c.decodeIfPresent(String.self, forKey: .decidedByName)
        decisionNote = try c.decodeIfPresent(String.self, forKey: .decisionNote)
        createdAt = try c.decode(Date.self, forKey: .createdAt)
    }

    enum CodingKeys: String, CodingKey {
        case id, kind, status, source, hours, lots
        case machineID = "machine_id", machineCode = "machine_code", machineName = "machine_name", workDate = "work_date"
        case startRef = "start_ref", startReading = "start_reading", startAt = "start_at", endRef = "end_ref"
        case endReading = "end_reading", endAt = "end_at", customerID = "customer_id", customerName = "customer_name"
        case reasonID = "reason_id", reasonName = "reason_name", evidenceAttachmentIDs = "evidence_attachment_ids"
        case correctionGroupID = "correction_group_id", correctionReason = "correction_reason"
        case supersedesID = "supersedes_id", supersededAt = "superseded_at", supersededByIDs = "superseded_by_ids"
        case recordedBy = "recorded_by", recordedByName = "recorded_by_name", decidedAt = "decided_at"
        case decidedBy = "decided_by", decidedByName = "decided_by_name", decisionNote = "decision_note"
        case createdAt = "created_at"
    }
}

/// `AllocationDayDto`: one machine-day of the allocation reconciliation.
public struct AllocationDayDTO: Codable, Hashable, Sendable {
    public let machineID: UUID
    public let machineCode: String?
    public let machineName: String?
    /// `YYYY-MM-DD`.
    public let day: String
    public let totalEngineHours: DecimalString
    public let customerHours: DecimalString
    public let authorizedHours: DecimalString
    public let unexplainedHours: DecimalString
    public let allocatedHours: DecimalString
    public let differenceHours: DecimalString
    public let reconciled: Bool

    enum CodingKeys: String, CodingKey {
        case day, reconciled
        case machineID = "machine_id", machineCode = "machine_code", machineName = "machine_name"
        case totalEngineHours = "total_engine_hours", customerHours = "customer_hours", authorizedHours = "authorized_hours"
        case unexplainedHours = "unexplained_hours", allocatedHours = "allocated_hours", differenceHours = "difference_hours"
    }
}

/// `AllocationCorrectionDto`: a correction group (the proposed entries that replace one allocation).
public struct AllocationCorrectionDTO: Codable, Hashable, Sendable, Identifiable {
    public let groupID: UUID
    public let status: String
    public let supersedesID: UUID?
    public let entries: [WorkAllocationDTO]

    public var id: UUID { groupID }

    enum CodingKeys: String, CodingKey { case status, entries, groupID = "group_id", supersedesID = "supersedes_id" }
}

/// `AllocationPartIn`: one part of a proposed correction.
public struct AllocationPartIn: Encodable, Hashable, Sendable {
    public let hours: DecimalString
    public let kind: String
    public let customerID: UUID?
    public let reasonID: UUID?

    public init(hours: Decimal, kind: String, customerID: UUID? = nil, reasonID: UUID? = nil) {
        self.hours = DecimalString(hours)
        self.kind = kind
        self.customerID = customerID
        self.reasonID = reasonID
    }

    enum CodingKeys: String, CodingKey { case hours, kind, customerID = "customer_id", reasonID = "reason_id" }
}

/// `AllocationCorrectionIn`.
public struct AllocationCorrectionIn: Encodable, Sendable {
    public let parts: [AllocationPartIn]
    public let reason: String
    public let evidenceAttachmentIDs: [UUID]

    public init(parts: [AllocationPartIn], reason: String, evidenceAttachmentIDs: [UUID] = []) {
        self.parts = parts
        self.reason = reason
        self.evidenceAttachmentIDs = evidenceAttachmentIDs
    }

    enum CodingKeys: String, CodingKey { case parts, reason, evidenceAttachmentIDs = "evidence_attachment_ids" }
}

/// `EngineHourReasonDto` (the tenant's reason lists, kind `UNBILLABLE_REASON` for daily reports).
public struct EngineHourReasonDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let kind: String
    public let code: String
    public let name: String
    public let description: String?
    public let isActive: Bool

    public init(id: UUID, kind: String, code: String, name: String, description: String?, isActive: Bool) {
        self.id = id
        self.kind = kind
        self.code = code
        self.name = name
        self.description = description
        self.isActive = isActive
    }

    enum CodingKeys: String, CodingKey { case id, kind, code, name, description, isActive = "is_active" }
}

/// `SyncUnbillableReasonDto`: one entry of the tenant's unbillable reasons.
public struct SyncUnbillableReasonDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let code: String
    public let name: String
    public let description: String?
    public let isActive: Bool

    enum CodingKeys: String, CodingKey { case id, code, name, description, isActive = "is_active" }
}
