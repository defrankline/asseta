import Foundation

// MARK: - DEC-031 Phase 4: prepaid hours over days (balances, statement, low-balance warnings)

/// `LedgerEntryType` values the apps name (unknown values are shown humanized).
public enum HoursLedgerEntryType {
    public static let activated = "ACTIVATED"
    public static let consumed = "CONSUMED"
    public static let transferOut = "TRANSFER_OUT"
    public static let transferIn = "TRANSFER_IN"
    public static let expired = "EXPIRED"
    public static let reversal = "REVERSAL"
    /// Hours a running job used on a day (daily drawdown); replaced by CONSUMED when the job completes.
    public static let provisional = "PROVISIONAL"
    public static let provisionalReversed = "PROVISIONAL_REVERSED"
}

/// `HoursBalanceDto`: one customer's prepaid hours on one machine.
public struct HoursBalanceDTO: Codable, Hashable, Sendable, Identifiable {
    public let customerID: UUID
    public let customerName: String?
    public let machineID: UUID
    public let machineCode: String?
    public let machineName: String?
    public let purchases: Int
    public let activated: DecimalString
    public let consumed: DecimalString
    public let remaining: DecimalString
    public let awaitingActivation: DecimalString
    public let expired: DecimalString
    public let reversed: DecimalString
    public let transferredIn: DecimalString
    public let transferredOut: DecimalString
    /// Hours held by running jobs (daily drawdown), already out of `remaining`; 0 when absent.
    public let provisional: DecimalString

    public var id: String { "\(customerID.uuidString):\(machineID.uuidString)" }

    public init(from decoder: any Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        let zero = DecimalString(0)
        customerID = try c.decode(UUID.self, forKey: .customerID)
        customerName = try c.decodeIfPresent(String.self, forKey: .customerName)
        machineID = try c.decode(UUID.self, forKey: .machineID)
        machineCode = try c.decodeIfPresent(String.self, forKey: .machineCode)
        machineName = try c.decodeIfPresent(String.self, forKey: .machineName)
        purchases = try c.decodeIfPresent(Int.self, forKey: .purchases) ?? 0
        activated = try c.decodeIfPresent(DecimalString.self, forKey: .activated) ?? zero
        consumed = try c.decodeIfPresent(DecimalString.self, forKey: .consumed) ?? zero
        remaining = try c.decode(DecimalString.self, forKey: .remaining)
        awaitingActivation = try c.decodeIfPresent(DecimalString.self, forKey: .awaitingActivation) ?? zero
        expired = try c.decodeIfPresent(DecimalString.self, forKey: .expired) ?? zero
        reversed = try c.decodeIfPresent(DecimalString.self, forKey: .reversed) ?? zero
        transferredIn = try c.decodeIfPresent(DecimalString.self, forKey: .transferredIn) ?? zero
        transferredOut = try c.decodeIfPresent(DecimalString.self, forKey: .transferredOut) ?? zero
        provisional = try c.decodeIfPresent(DecimalString.self, forKey: .provisional) ?? zero
    }

    enum CodingKeys: String, CodingKey {
        case purchases, activated, consumed, remaining, expired, reversed, provisional
        case customerID = "customer_id", customerName = "customer_name", machineID = "machine_id"
        case machineCode = "machine_code", machineName = "machine_name", awaitingActivation = "awaiting_activation"
        case transferredIn = "transferred_in", transferredOut = "transferred_out"
    }
}

/// `HoursStatementDto` (`GET /tenant/customers/{id}/hours-statement`): what a customer bought and used in a period.
public struct HoursStatementDTO: Codable, Hashable, Sendable {
    public let customerID: UUID
    public let customerName: String?
    public let machineID: UUID?
    public let machineCode: String?
    public let machineName: String?
    public let dateFrom: String
    public let dateTo: String
    public let timezone: String
    public let generatedAt: Date
    /// API path of the same statement as a PDF.
    public let pdfPath: String
    public let totals: Totals
    public let purchases: [Purchase]
    public let usage: [Usage]
    public let lines: [Line]

    public struct Totals: Codable, Hashable, Sendable {
        public let openingBalance: DecimalString
        public let bought: DecimalString
        public let activated: DecimalString
        public let used: DecimalString
        public let transferredIn: DecimalString
        public let transferredOut: DecimalString
        public let expired: DecimalString
        public let cancelled: DecimalString
        public let closingBalance: DecimalString
        public let provisionalAtClose: DecimalString
        public let awaitingActivation: DecimalString

        enum CodingKeys: String, CodingKey {
            case bought, activated, used, expired, cancelled
            case openingBalance = "opening_balance", transferredIn = "transferred_in", transferredOut = "transferred_out"
            case closingBalance = "closing_balance", provisionalAtClose = "provisional_at_close"
            case awaitingActivation = "awaiting_activation"
        }
    }

    public struct Purchase: Codable, Hashable, Sendable, Identifiable {
        public let purchaseID: UUID
        public let purchaseNumber: String?
        public let machineID: UUID
        public let machineCode: String?
        public let machineName: String?
        public let boughtAt: Date
        public let hours: DecimalString
        public let activated: DecimalString
        public let amount: DecimalString
        public let currency: String
        public let effectiveRate: DecimalString
        public let status: String
        public let remainingAtClose: DecimalString
        public let expiringHours: DecimalString
        public let nextExpiryAt: Date?
        public let cancelledAt: Date?

        public var id: UUID { purchaseID }

        enum CodingKeys: String, CodingKey {
            case hours, activated, amount, currency, status
            case purchaseID = "purchase_id", purchaseNumber = "purchase_number", machineID = "machine_id"
            case machineCode = "machine_code", machineName = "machine_name", boughtAt = "bought_at"
            case effectiveRate = "effective_rate", remainingAtClose = "remaining_at_close"
            case expiringHours = "expiring_hours", nextExpiryAt = "next_expiry_at", cancelledAt = "cancelled_at"
        }
    }

    /// Hours used on one day by one job: `DAILY` (provisional while the job runs) or `FINAL` (job completed).
    public struct Usage: Codable, Hashable, Sendable {
        public let day: String
        public let jobID: UUID?
        public let jobNumber: String?
        public let machineID: UUID
        public let machineCode: String?
        public let machineName: String?
        public let hours: DecimalString
        public let basis: String
        public let jobRunning: Bool

        enum CodingKeys: String, CodingKey {
            case day, hours, basis
            case jobID = "job_id", jobNumber = "job_number", machineID = "machine_id", machineCode = "machine_code"
            case machineName = "machine_name", jobRunning = "job_running"
        }
    }

    /// One ledger movement with the running balance after it.
    public struct Line: Codable, Hashable, Sendable, Identifiable {
        public let entryID: UUID
        public let occurredAt: Date
        public let day: String
        public let entryType: String
        public let hours: DecimalString
        public let balanceAfter: DecimalString
        public let purchaseID: UUID
        public let purchaseNumber: String?
        public let machineID: UUID
        public let machineCode: String?
        public let machineName: String?
        public let jobID: UUID?
        public let jobNumber: String?
        public let reason: String?

        public var id: UUID { entryID }

        enum CodingKeys: String, CodingKey {
            case day, hours, reason
            case entryID = "entry_id", occurredAt = "occurred_at", entryType = "entry_type", balanceAfter = "balance_after"
            case purchaseID = "purchase_id", purchaseNumber = "purchase_number", machineID = "machine_id"
            case machineCode = "machine_code", machineName = "machine_name", jobID = "job_id", jobNumber = "job_number"
        }
    }

    enum CodingKeys: String, CodingKey {
        case timezone, totals, purchases, usage, lines
        case customerID = "customer_id", customerName = "customer_name", machineID = "machine_id"
        case machineCode = "machine_code", machineName = "machine_name", dateFrom = "date_from", dateTo = "date_to"
        case generatedAt = "generated_at", pdfPath = "pdf_path"
    }
}

/// `HoursStatementUsageDto.basis` values.
public enum HoursUsageBasis {
    public static let daily = "DAILY"
    public static let final = "FINAL"
}

/// `LowBalanceAlertDto`: a purchase's available hours crossed the tenant's low-balance threshold.
public struct LowBalanceAlertDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let purchaseID: UUID
    public let purchaseNumber: String?
    public let customerID: UUID
    public let customerName: String?
    public let machineID: UUID
    public let machineCode: String?
    public let machineName: String?
    public let sequence: Int
    public let thresholdHours: DecimalString
    public let remainingHours: DecimalString
    public let availableHours: DecimalString
    public let crossedAt: Date
    public let rearmedAt: Date?
    public let notifyCustomer: Bool
    public let customerSmsStatus: String
    public let customerSmsID: UUID?
    public let policyVersion: String

    enum CodingKeys: String, CodingKey {
        case id, sequence
        case purchaseID = "purchase_id", purchaseNumber = "purchase_number", customerID = "customer_id"
        case customerName = "customer_name", machineID = "machine_id", machineCode = "machine_code"
        case machineName = "machine_name", thresholdHours = "threshold_hours", remainingHours = "remaining_hours"
        case availableHours = "available_hours", crossedAt = "crossed_at", rearmedAt = "rearmed_at"
        case notifyCustomer = "notify_customer", customerSmsStatus = "customer_sms_status"
        case customerSmsID = "customer_sms_id", policyVersion = "policy_version"
    }
}
