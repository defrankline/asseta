import Foundation

// DEC-032 Phase 4 management view: the period-aware sections of `AccountabilitySummaryDto`. Shapes follow
// `contracts/openapi.json`; same as Android. Flows follow the period, balances and open queues are position now.

public struct PeriodDTO: Codable, Hashable, Sendable {
    public let dateFrom: String?
    public let dateTo: String?

    enum CodingKeys: String, CodingKey { case dateFrom = "date_from", dateTo = "date_to" }
}

public struct MoneyLineDTO: Codable, Hashable, Sendable {
    public let currency: String
    public let count: Int
    public let amount: DecimalString
}

public struct MoneyFigureDTO: Codable, Hashable, Sendable {
    public let lines: [MoneyLineDTO]
    public let count: Int
    public let route: String
}

public struct HoursFigureDTO: Codable, Hashable, Sendable {
    public let hours: DecimalString
    public let count: Int
    public let route: String
}

public struct CountFigureDTO: Codable, Hashable, Sendable {
    public let count: Int
    public let route: String
}

public struct PurchaseQueueItemDTO: Codable, Hashable, Sendable, Identifiable {
    public var id: UUID { purchaseID }
    public let purchaseID: UUID
    public let purchaseNumber: String?
    public let customerID: UUID
    public let customerName: String?
    public let hoursAwaiting: DecimalString
    public let amountOpen: DecimalString
    public let currency: String
    public let createdAt: Date
    public let route: String

    enum CodingKeys: String, CodingKey {
        case currency, route
        case purchaseID = "purchase_id", purchaseNumber = "purchase_number", customerID = "customer_id"
        case customerName = "customer_name", hoursAwaiting = "hours_awaiting", amountOpen = "amount_open", createdAt = "created_at"
    }
}

public struct PurchaseQueueDTO: Codable, Hashable, Sendable {
    public let count: Int
    public let hours: DecimalString
    public let amounts: [MoneyLineDTO]
    public let items: [PurchaseQueueItemDTO]
    public let route: String
}

public struct CustomerRemainingDTO: Codable, Hashable, Sendable, Identifiable {
    public var id: UUID { customerID }
    public let customerID: UUID
    public let customerName: String?
    public let remaining: DecimalString
    public let activated: DecimalString
    public let consumed: DecimalString
    public let route: String

    enum CodingKeys: String, CodingKey {
        case remaining, activated, consumed, route, customerID = "customer_id", customerName = "customer_name"
    }
}

public struct CustomerHoursSectionDTO: Codable, Hashable, Sendable {
    public let purchased: HoursFigureDTO
    public let purchasedValue: MoneyFigureDTO
    public let activated: HoursFigureDTO
    public let consumed: HoursFigureDTO
    public let remaining: HoursFigureDTO
    public let remainingByCustomer: [CustomerRemainingDTO]
    public let remainingCustomersTotal: Int
    public let unpaidPurchases: PurchaseQueueDTO
    public let unconfirmedPurchases: PurchaseQueueDTO
    public let awaitingActivation: PurchaseQueueDTO

    enum CodingKeys: String, CodingKey {
        case purchased, activated, consumed, remaining
        case purchasedValue = "purchased_value", remainingByCustomer = "remaining_by_customer"
        case remainingCustomersTotal = "remaining_customers_total", unpaidPurchases = "unpaid_purchases"
        case unconfirmedPurchases = "unconfirmed_purchases", awaitingActivation = "awaiting_activation"
    }
}

public struct ExcavatorHoursDTO: Codable, Hashable, Sendable, Identifiable {
    public var id: UUID { machineID }
    public let machineID: UUID
    public let machineCode: String?
    public let machineName: String?
    public let operatingHours: DecimalString
    public let customerHours: DecimalString
    public let authorizedHours: DecimalString
    public let unexplainedHours: DecimalString
    public let route: String

    enum CodingKeys: String, CodingKey {
        case route, machineID = "machine_id", machineCode = "machine_code", machineName = "machine_name"
        case operatingHours = "operating_hours", customerHours = "customer_hours"
        case authorizedHours = "authorized_hours", unexplainedHours = "unexplained_hours"
    }
}

public struct TypeCountDTO: Codable, Hashable, Sendable {
    public let type: String
    public let count: Int
    public let route: String
}

public struct DiscrepanciesFigureDTO: Codable, Hashable, Sendable {
    public let count: Int
    public let byType: [TypeCountDTO]
    public let route: String

    enum CodingKeys: String, CodingKey { case count, route, byType = "by_type" }
}

public struct ExcavatorOperationsSectionDTO: Codable, Hashable, Sendable {
    public let operatingHours: HoursFigureDTO
    public let customerHours: HoursFigureDTO
    public let authorizedNonCustomerHours: HoursFigureDTO
    public let unexplainedHours: HoursFigureDTO
    public let byExcavator: [ExcavatorHoursDTO]
    public let meterDiscrepancies: DiscrepanciesFigureDTO
    public let pendingReports: CountFigureDTO
    public let returnedReports: CountFigureDTO

    enum CodingKeys: String, CodingKey {
        case operatingHours = "operating_hours", customerHours = "customer_hours"
        case authorizedNonCustomerHours = "authorized_non_customer_hours", unexplainedHours = "unexplained_hours"
        case byExcavator = "by_excavator", meterDiscrepancies = "meter_discrepancies"
        case pendingReports = "pending_reports", returnedReports = "returned_reports"
    }
}

public struct EmployeeCashDTO: Codable, Hashable, Sendable {
    public let staffMemberID: UUID
    public let staffMemberName: String?
    public let currency: String
    public let outstanding: DecimalString
    public let inTransitOut: DecimalString
    public let claimedUnverifiedHandovers: DecimalString
    public let pendingFloats: DecimalString
    public let approvedRetention: DecimalString
    public let route: String

    enum CodingKeys: String, CodingKey {
        case currency, outstanding, route
        case staffMemberID = "staff_member_id", staffMemberName = "staff_member_name", inTransitOut = "in_transit_out"
        case claimedUnverifiedHandovers = "claimed_unverified_handovers", pendingFloats = "pending_floats"
        case approvedRetention = "approved_retention"
    }
}

public struct CashSectionDTO: Codable, Hashable, Sendable {
    public let collected: MoneyFigureDTO
    public let heldByEmployee: [EmployeeCashDTO]
    public let transferred: MoneyFigureDTO
    public let inTransit: MoneyFigureDTO
    public let declaredForRemittance: MoneyFigureDTO
    public let confirmedByCompany: MoneyFigureDTO
    public let outstanding: MoneyFigureDTO
    public let unconfirmedRemittances: MoneyFigureDTO
    public let disputedRemittances: MoneyFigureDTO
    public let disputedTransfers: MoneyFigureDTO

    enum CodingKeys: String, CodingKey {
        case collected, transferred, outstanding
        case heldByEmployee = "held_by_employee", inTransit = "in_transit", declaredForRemittance = "declared_for_remittance"
        case confirmedByCompany = "confirmed_by_company", unconfirmedRemittances = "unconfirmed_remittances"
        case disputedRemittances = "disputed_remittances", disputedTransfers = "disputed_transfers"
    }
}

public struct KindCountDTO: Codable, Hashable, Sendable {
    public let kind: String
    public let count: Int
    public let oldestAt: Date?
    public let route: String

    enum CodingKeys: String, CodingKey { case kind, count, route, oldestAt = "oldest_at" }
}

/// One approval or adjustment still waiting (`PendingItemDto`).
public struct PendingItemDTO: Codable, Hashable, Sendable, Identifiable {
    public let kind: String
    public let recordType: String
    public let id: UUID
    public let reference: String?
    public let status: String
    public let requestedBy: UUID?
    public let requestedByName: String?
    public let requestedAt: Date
    public let amount: DecimalString?
    public let unit: String?
    public let currency: String?
    public let customerID: UUID?
    public let customerName: String?
    public let machineID: UUID?
    public let machineCode: String?
    public let machineName: String?
    public let staffMemberID: UUID?
    public let staffMemberName: String?
    public let route: String?

    enum CodingKeys: String, CodingKey {
        case kind, id, reference, status, amount, unit, currency, route
        case recordType = "record_type", requestedBy = "requested_by", requestedByName = "requested_by_name"
        case requestedAt = "requested_at", customerID = "customer_id", customerName = "customer_name", machineID = "machine_id"
        case machineCode = "machine_code", machineName = "machine_name", staffMemberID = "staff_member_id"
        case staffMemberName = "staff_member_name"
    }
}

public struct PendingAdjustmentsDTO: Codable, Hashable, Sendable {
    public let total: Int
    public let byKind: [KindCountDTO]
    public let oldest: [PendingItemDTO]
    public let route: String

    enum CodingKeys: String, CodingKey { case total, oldest, route, byKind = "by_kind" }
}

public struct OutstandingApprovalsDTO: Codable, Hashable, Sendable {
    public let total: Int
    public let byKind: [KindCountDTO]

    enum CodingKeys: String, CodingKey { case total, byKind = "by_kind" }
}

public struct OverdueReportsDTO: Codable, Hashable, Sendable {
    public let total: Int
    public let missingDailyReports: CountFigureDTO
    public let remittancesOverdueToday: CountFigureDTO

    enum CodingKeys: String, CodingKey {
        case total, missingDailyReports = "missing_daily_reports", remittancesOverdueToday = "remittances_overdue_today"
    }
}

public struct VarianceSourceDTO: Codable, Hashable, Sendable {
    public let source: String
    public let unit: String
    public let count: Int
    public let amounts: [MoneyLineDTO]
    public let route: String
}

public struct UnresolvedVariancesDTO: Codable, Hashable, Sendable {
    public let total: Int
    public let bySource: [VarianceSourceDTO]

    enum CodingKeys: String, CodingKey { case total, bySource = "by_source" }
}

public struct AttemptsFigureDTO: Codable, Hashable, Sendable {
    public let permissionDenied: Int
    public let segregationOfDuties: Int
    public let since: Date
    public let route: String

    enum CodingKeys: String, CodingKey {
        case since, route, permissionDenied = "permission_denied", segregationOfDuties = "segregation_of_duties"
    }
}

/// A next job left unapproved after a changeover: its hours stay unbilled while it waits.
public struct ChangeoverWaitingJobDTO: Codable, Hashable, Sendable, Identifiable {
    public var id: UUID { jobID }
    public let jobID: UUID
    public let jobNumber: String?
    public let machineID: UUID
    public let machineCode: String?
    public let machineName: String?
    public let customerID: UUID
    public let customerName: String?
    public let changedOverAt: Date
    public let daysWaiting: Int
    public let route: String

    enum CodingKeys: String, CodingKey {
        case route, jobID = "job_id", jobNumber = "job_number", machineID = "machine_id", machineCode = "machine_code"
        case machineName = "machine_name", customerID = "customer_id", customerName = "customer_name"
        case changedOverAt = "changed_over_at", daysWaiting = "days_waiting"
    }
}

public struct ChangeoverJobsWaitingDTO: Codable, Hashable, Sendable {
    public let count: Int
    public let oldestDays: Int?
    public let items: [ChangeoverWaitingJobDTO]

    enum CodingKeys: String, CodingKey { case count, items, oldestDays = "oldest_days" }
}

public struct ExceptionsSectionDTO: Codable, Hashable, Sendable {
    public let unexplainedEngineHours: HoursFigureDTO
    public let shortages: MoneyFigureDTO
    public let overages: MoneyFigureDTO
    public let shortagesOpenedInPeriod: MoneyFigureDTO
    public let overagesOpenedInPeriod: MoneyFigureDTO
    public let pendingAdjustments: PendingAdjustmentsDTO
    public let unauthorizedAttempts: AttemptsFigureDTO
    public let unconfirmedPayments: MoneyFigureDTO
    public let outstandingApprovals: OutstandingApprovalsDTO
    public let overdueReports: OverdueReportsDTO
    public let unresolvedVariances: UnresolvedVariancesDTO
    public let changeoverJobsAwaitingApproval: ChangeoverJobsWaitingDTO

    enum CodingKeys: String, CodingKey {
        case shortages, overages
        case unexplainedEngineHours = "unexplained_engine_hours", shortagesOpenedInPeriod = "shortages_opened_in_period"
        case overagesOpenedInPeriod = "overages_opened_in_period", pendingAdjustments = "pending_adjustments"
        case unauthorizedAttempts = "unauthorized_attempts", unconfirmedPayments = "unconfirmed_payments"
        case outstandingApprovals = "outstanding_approvals", overdueReports = "overdue_reports"
        case unresolvedVariances = "unresolved_variances", changeoverJobsAwaitingApproval = "changeover_jobs_awaiting_approval"
    }
}
