import Foundation

// DEC-032 Phase 4: employee accountability (`EmployeeAccountabilityDto`), reference lookup (`LookupResultDto`) and the
// open invoices synced to collection recorders (`SyncOpenInvoiceDto`). Same as Android.

extension SyncCapability {
    /// `SyncData.open_invoices`: a full snapshot on every pull (replaces the local set; collection recorders only).
    public static let syncOpenInvoices = "SYNC_OPEN_INVOICES"
}

/// Issued invoice with money still owed, so a field collection can be linked to it.
public struct SyncOpenInvoiceDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let invoiceNumber: String
    public let customerID: UUID
    public let customerName: String
    public let currency: String
    public let total: DecimalString
    public let paid: DecimalString
    public let balance: DecimalString
    public let dueDate: String?
    public let issuedAt: Date

    enum CodingKeys: String, CodingKey {
        case id, currency, total, paid, balance
        case invoiceNumber = "invoice_number", customerID = "customer_id", customerName = "customer_name"
        case dueDate = "due_date", issuedAt = "issued_at"
    }
}

public struct EmployeeIdentityDTO: Codable, Hashable, Sendable {
    public let staffMemberID: UUID
    public let userID: UUID?
    public let fullName: String
    public let employeeCode: String?
    public let kind: String
    public let phone: String?
    public let loginEmail: String?
    public let isActive: Bool
    public let roles: [String]

    enum CodingKeys: String, CodingKey {
        case kind, phone, roles
        case staffMemberID = "staff_member_id", userID = "user_id", fullName = "full_name"
        case employeeCode = "employee_code", loginEmail = "login_email", isActive = "is_active"
    }
}

/// One line of an employee's record (`EmployeeRecordDto`); `id` is nil for rows that have no record of their own.
public struct EmployeeRecordDTO: Codable, Hashable, Sendable {
    public let recordType: String
    public let id: UUID?
    public let reference: String?
    public let status: String?
    public let occurredAt: Date
    public let amount: DecimalString?
    public let unit: String?
    public let currency: String?
    public let label: String?
    public let counterpartyStaffID: UUID?
    public let counterpartyStaffName: String?
    public let route: String?

    enum CodingKeys: String, CodingKey {
        case id, reference, status, amount, unit, currency, label, route
        case recordType = "record_type", occurredAt = "occurred_at"
        case counterpartyStaffID = "counterparty_staff_id", counterpartyStaffName = "counterparty_staff_name"
    }
}

public struct EmployeeAccountabilityDTO: Codable, Hashable, Sendable {
    public let identity: EmployeeIdentityDTO
    public let dateFrom: String
    public let dateTo: String
    public let cashHeld: [CashCustodyBalanceDTO]
    public let collections: [EmployeeRecordDTO]
    public let floats: [EmployeeRecordDTO]
    public let transfersIn: [EmployeeRecordDTO]
    public let transfersOut: [EmployeeRecordDTO]
    public let remittances: [EmployeeRecordDTO]
    public let spending: [EmployeeRecordDTO]
    public let retentions: [EmployeeRecordDTO]
    public let differences: [EmployeeRecordDTO]
    public let custodyAdjustments: [EmployeeRecordDTO]
    public let reportsSubmitted: [EmployeeRecordDTO]
    public let approvalsMade: [EmployeeRecordDTO]
    public let adjustmentsRequested: [EmployeeRecordDTO]
    public let adjustmentsDecided: [EmployeeRecordDTO]
    public let scorecardItems: [EmployeeRecordDTO]
    public let scorecardVisible: Bool
    /// Lists cut off at the server's row limit.
    public let truncated: [String]

    enum CodingKeys: String, CodingKey {
        case identity, collections, floats, remittances, spending, retentions, differences, truncated
        case dateFrom = "date_from", dateTo = "date_to", cashHeld = "cash_held", transfersIn = "transfers_in"
        case transfersOut = "transfers_out", custodyAdjustments = "custody_adjustments", reportsSubmitted = "reports_submitted"
        case approvalsMade = "approvals_made", adjustmentsRequested = "adjustments_requested"
        case adjustmentsDecided = "adjustments_decided", scorecardItems = "scorecard_items", scorecardVisible = "scorecard_visible"
    }
}

/// One record a reference number points at.
public struct LookupMatchDTO: Codable, Hashable, Sendable, Identifiable {
    public let recordType: String
    public let id: UUID
    public let reference: String?
    public let route: String?
    public let status: String?
    public let recordedBy: UUID?
    public let recordedByName: String?
    public let recordedAt: Date?
    public let decidedBy: UUID?
    public let decidedByName: String?
    public let decidedAt: Date?
    public let customerID: UUID?
    public let customerName: String?
    public let machineID: UUID?
    public let machineCode: String?
    public let machineName: String?
    public let staffMemberID: UUID?
    public let staffMemberName: String?
    public let amount: DecimalString?
    public let currency: String?
    public let balanceOutstanding: DecimalString?
    public let balanceUnit: String?
    public let hoursRemaining: DecimalString?

    enum CodingKeys: String, CodingKey {
        case id, reference, route, status, amount, currency
        case recordType = "record_type", recordedBy = "recorded_by", recordedByName = "recorded_by_name"
        case recordedAt = "recorded_at", decidedBy = "decided_by", decidedByName = "decided_by_name", decidedAt = "decided_at"
        case customerID = "customer_id", customerName = "customer_name", machineID = "machine_id", machineCode = "machine_code"
        case machineName = "machine_name", staffMemberID = "staff_member_id", staffMemberName = "staff_member_name"
        case balanceOutstanding = "balance_outstanding", balanceUnit = "balance_unit", hoursRemaining = "hours_remaining"
    }
}

public struct LookupResultDTO: Codable, Hashable, Sendable {
    public let reference: String
    public let matches: [LookupMatchDTO]
}
