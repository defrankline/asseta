import Foundation

/// Wording copied exactly from `docs/requirements/accountability-mobile-strings.md` (owner.mgmt.*, owner.emp.*, owner.lookup.*).
public enum ManagementTexts {
    public static let openWeb = "Open on the web"
    public static let none = "None"
    public static let periodNote = "Money and hours moved are for the period chosen. Balances and open queues are as they stand now."
    public static func oldest(_ date: String) -> String { "Oldest \(date)" }

    public static let hoursTitle = "Customer hours"
    public static let hoursPurchased = "Hours purchased"
    public static let hoursPurchasedValue = "Value of hours purchased"
    public static let hoursActivated = "Hours activated"
    public static let hoursConsumed = "Hours consumed"
    public static let hoursRemaining = "Hours remaining"
    public static let hoursUnpaid = "Unpaid purchases"
    public static let hoursUnconfirmed = "Purchases not confirmed"
    public static let hoursAwaiting = "Awaiting activation"
    public static let hoursByCustomer = "Remaining by customer"
    public static func hoursCustomersShown(_ shown: Int, _ total: Int) -> String { "Showing \(shown) of \(total) customers." }

    public static let opsTitle = "Excavator operations"
    public static let opsOperating = "Operating hours"
    public static let opsCustomer = "Customer hours"
    public static let opsAuthorized = "Authorized non-customer hours"
    public static let opsUnexplained = "Unexplained hours"
    public static let opsDiscrepancies = "Meter discrepancies"
    public static let opsPendingReports = "Daily reports to review"
    public static let opsReturnedReports = "Daily reports returned"
    public static let opsByExcavator = "Hours by excavator"
    public static func opsExcavatorRow(customer: String, authorized: String, unexplained: String) -> String {
        "Customer \(customer) h · Authorized \(authorized) h · Unexplained \(unexplained) h"
    }
    public static func opsDiscrepancy(_ type: String) -> String {
        switch type {
        case "METER_DECREASE": "Meter went down"
        case "IMPOSSIBLE_INCREMENT": "Impossible increase"
        case "CONTINUITY_GAP": "Gap between readings"
        case "TELEMETRY_MISMATCH": "Tracker disagrees"
        case "OVERLAPPING_ALLOCATION": "Overlapping allocation"
        default: OwnerFormat.humanize(type)
        }
    }

    public static let cashTitle = "Cash accountability"
    public static let cashCollected = "Cash collected"
    public static let cashTransferred = "Transferred between staff"
    public static let cashInTransit = "In transit"
    public static let cashDeclared = "Declared for remittance"
    public static let cashConfirmed = "Confirmed by the company"
    public static let cashOutstanding = "Outstanding with staff"
    public static let cashUnconfirmed = "Remittances not confirmed"
    public static let cashDisputedRemittances = "Remittances disputed"
    public static let cashDisputedTransfers = "Transfers disputed"
    public static let cashHeld = "Cash held by employee"
    /// In transit · Claimed · Float pending · Retained, non-zero parts only (owner.mgmt.cash.heldCaption = owner.emp.cashCaption).
    public static func heldCaption(transit: String?, claimed: String?, float: String?, retained: String?) -> String? {
        let parts = [transit.map { "In transit \($0)" }, claimed.map { "Claimed \($0)" }, float.map { "Float pending \($0)" }, retained.map { "Retained \($0)" }]
            .compactMap { $0 }
        return parts.isEmpty ? nil : parts.joined(separator: " · ")
    }

    public static let excTitle = "Exceptions and approvals"
    public static let excUnexplained = "Unexplained engine hours"
    public static let excShortages = "Shortages"
    public static let excOverages = "Overages"
    public static let excShortagesPeriod = "Shortages opened in period"
    public static let excOveragesPeriod = "Overages opened in period"
    public static let excUnconfirmedPayments = "Payments not confirmed"
    public static let excAttempts = "Refused attempts"
    public static func excAttemptsCaption(denied: Int, sod: Int) -> String { "Denied \(denied) · Second person required \(sod)" }
    public static let excMissingReports = "Daily reports missing"
    public static let excOverdueRemittances = "Remittances overdue today"
    public static let excChangeover = "Changeover jobs waiting"
    public static func excChangeoverCaption(_ days: Int) -> String { "Oldest \(days) days" }
    public static func excChangeoverRow(job: String, machine: String, customer: String) -> String { "\(job) · \(machine) · \(customer)" }
    public static func excChangeoverDays(_ days: Int) -> String { "\(days) days" }
    public static func excApprovals(_ total: Int) -> String { "Outstanding approvals (\(total))" }
    public static func excPending(_ total: Int) -> String { "Pending adjustments (\(total))" }
    public static func excVariances(_ total: Int) -> String { "Unresolved variances (\(total))" }
    public static func excVariance(_ source: String) -> String {
        switch source {
        case "TRANSFER": "Cash transfers"
        case "REMITTANCE": "Remittances"
        case "FLOAT": "Floats"
        case "CUSTOMER_HOUR": "Customer hours"
        case "REVENUE_DIFFERENCE": "Revenue differences"
        default: OwnerFormat.humanize(source)
        }
    }

    /// `owner.mgmt.kind.*`, in the strings doc's order.
    public static let kindOrder = ["adjustment_requests", "hours_transfers", "hours_cancellations", "credit_arrangements", "discounts",
                                   "meter_corrections", "allocation_corrections", "classifications", "non_revenue_approvals",
                                   "custody_adjustments", "write_offs", "variance_closures", "meter_baselines", "meter_resets",
                                   "cash_retentions", "partial_reasons", "approval_requests", "payments_to_verify",
                                   "remittances_to_verify", "jobs_awaiting_approval", "daily_reports_to_review", "case_closures",
                                   "revenue_decisions"]
    public static func kind(_ wire: String) -> String {
        switch wire {
        case "adjustment_requests": "Adjustment requests"
        case "hours_transfers": "Hours transfers"
        case "hours_cancellations": "Hours cancellations"
        case "credit_arrangements": "Credit arrangements"
        case "discounts": "Discounts"
        case "meter_corrections": "Meter corrections"
        case "allocation_corrections": "Allocation corrections"
        case "classifications": "Engine-hour classifications"
        case "non_revenue_approvals": "Non-revenue time"
        case "custody_adjustments": "Custody adjustments"
        case "write_offs": "Write-offs"
        case "variance_closures": "Variance closures"
        case "meter_baselines": "Meter baselines"
        case "meter_resets": "Meter resets"
        case "cash_retentions": "Cash retentions"
        case "partial_reasons": "Partial remittance reasons"
        case "approval_requests": "Expense approvals"
        case "payments_to_verify": "Payments to verify"
        case "remittances_to_verify": "Remittances to verify"
        case "jobs_awaiting_approval": "Jobs awaiting approval"
        case "daily_reports_to_review": "Daily reports to review"
        case "case_closures": "Case closures"
        case "revenue_decisions": "Revenue decisions"
        default: OwnerFormat.humanize(wire)
        }
    }

    public static let employeeOpen = "Employee accountability"
    public static let employeeTitle = "Employee accountability"
    public static let employeeCode = "Employee code"
    public static let employeeRoles = "Roles"
    public static let employeePhone = "Phone"
    public static let employeeInactive = "Inactive"
    public static let employeeFigures = "Figures"
    public static let employeeCashHeld = "Cash held now"
    public static func employeeCountMoney(_ count: Int, _ money: String) -> String { "\(count) · \(money)" }
    public static let employeeTruncated = "Some lists are shortened. Open the web for all records."
    public static let employeeListCollections = "Collections"
    public static let employeeListFloats = "Floats"
    public static let employeeListTransfersIn = "Transfers in"
    public static let employeeListTransfersOut = "Transfers out"
    public static let employeeListRemittances = "Remittances"
    public static let employeeListSpending = "Spending"
    public static let employeeListRetentions = "Retentions"
    public static let employeeListDifferences = "Differences"
    public static let employeeListCustodyAdjustments = "Custody adjustments"
    public static let employeeListReports = "Daily reports submitted"
    public static let employeeListApprovals = "Approvals made"
    public static let employeeListAdjustmentsRequested = "Adjustments requested"
    public static let employeeListAdjustmentsDecided = "Adjustments decided"
    public static let employeeListScorecard = "Scorecard items"

    public static let lookupMore = "Find a reference"
    public static let lookupTitle = "Find a reference"
    public static let lookupHint = "Number or outside reference"
    public static let lookupSearch = "Search"
    public static let lookupEmpty = "Nothing found for this reference."
    public static let lookupOffline = "Searching needs a connection. Try again when online."
    public static let lookupRecordedBy = "Recorded by"
    public static let lookupDecidedBy = "Decided by"
    public static let lookupCustomer = "Customer"
    public static let lookupMachine = "Machine"
    public static let lookupStaff = "Employee"
    public static let lookupAmount = "Amount"
    public static let lookupBalance = "Balance"
    public static let lookupHoursRemaining = "Hours remaining"
    public static func lookupType(_ wire: String) -> String {
        switch wire {
        case "hours_purchase": "Hours purchase"
        case "hire_invoice": "Invoice"
        case "job": "Job"
        case "customer_payment": "Collection"
        case "cash_handover": "Remittance"
        case "cash_transfer": "Cash transfer"
        case "hours_transfer": "Hours transfer"
        case "cash_retention": "Cash retention"
        case "custody_adjustment": "Custody adjustment"
        case "adjustment_request": "Adjustment request"
        case "adjustment_entry": "Ledger adjustment"
        case "anomaly_case": "Investigation"
        case "cash_variance": "Variance"
        case "daily_report": "Daily report"
        case "meter_correction": "Meter correction"
        case "classification": "Engine-hour classification"
        case "non_revenue_approval": "Non-revenue approval"
        case "meter_reset": "Meter reset"
        case "revenue_difference": "Revenue difference"
        case "hours_cancellation": "Hours cancellation"
        case "approval_request": "Expense approval"
        case "expense": "Expense"
        default: OwnerFormat.humanize(wire)
        }
    }
}
