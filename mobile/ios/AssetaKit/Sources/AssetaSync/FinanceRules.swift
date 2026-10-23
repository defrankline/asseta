import AssetaModel
import AssetaStore
import Foundation

/// An `EXPENSE_CAPTURE` policy snapshot the device enforces offline (tenant scope).
public struct ExpensePolicySnapshot: Sendable, Equatable {
    public static let policyType = "EXPENSE_CAPTURE"
    public let scopeKey: String
    public let versionIDs: [UUID]
    public let versionStamp: String
    public let policy: ExpenseCapturePolicy
    public let validUntil: Date

    public init(scopeKey: String = "tenant", versionIDs: [UUID], versionStamp: String, policy: ExpenseCapturePolicy,
                validUntil: Date) {
        self.scopeKey = scopeKey
        self.versionIDs = versionIDs
        self.versionStamp = versionStamp
        self.policy = policy
        self.validUntil = validUntil
    }

    /// Decodes a stored snapshot; nil if its values do not form a valid policy (fails closed: money
    /// thresholds must arrive as decimal strings).
    public init?(_ stored: StoredPolicySnapshot) {
        guard stored.policyType == Self.policyType,
              let ids = try? JSONDecoder().decode([UUID].self, from: Data(stored.versionIDsJSON.utf8)),
              let policy = try? AssetaJSON.decoder().decode(ExpenseCapturePolicy.self, from: Data(stored.valuesJSON.utf8)),
              policy.gpsMaxAccuracyM > 0
        else { return nil }
        self.init(scopeKey: stored.scopeKey, versionIDs: ids, versionStamp: stored.versionStamp, policy: policy,
                  validUntil: stored.validUntil)
    }
}

/// Whether a new expense may be recorded offline, and under which rules. Same freshness rules as
/// meter captures: an unexpired snapshot and an unexpired offline grant, judged on trusted time.
public enum ExpenseGate: Sendable, Equatable {
    case allowed(ExpensePolicySnapshot)
    case blocked(CaptureBlockReason)

    public static func evaluate(snapshot: ExpensePolicySnapshot?, offlineGrantUntil: Date?, now: Date) -> ExpenseGate {
        guard let snapshot else { return .blocked(.noSnapshot) }
        if now > snapshot.validUntil { return .blocked(.snapshotExpired(validUntil: snapshot.validUntil)) }
        if let grant = offlineGrantUntil, now > grant { return .blocked(.offlineGrantExpired(until: grant)) }
        return .allowed(snapshot)
    }
}

extension CaptureBlockReason {
    /// The same reasons, worded for expenses.
    public var expenseMessage: String {
        switch self {
        case .noSnapshot: "Connect to refresh rules. Your company's expense rules have not been downloaded yet."
        case let .snapshotExpired(date): "Connect to refresh rules. The expense rules expired \(date.formatted(date: .abbreviated, time: .shortened))."
        case .offlineGrantExpired: message
        }
    }
}

/// Strict, locale-independent decimal entry for money and quantities (never via Double).
public enum DecimalInput {
    public enum Failure: Error, Equatable, Sendable { case empty, notANumber, tooManyDecimals(Int), notPositive, negative }

    /// Accepts `123`, `123.45` or `123,45`; rejects signs, exponents, grouping and > `maxFractionDigits` decimals.
    public static func parse(_ text: String, maxFractionDigits: Int, allowZero: Bool = false) -> Result<Decimal, Failure> {
        let trimmed = text.trimmingCharacters(in: .whitespaces).replacingOccurrences(of: ",", with: ".")
        guard !trimmed.isEmpty else { return .failure(.empty) }
        if trimmed.hasPrefix("-") { return .failure(.negative) }
        let parts = trimmed.split(separator: ".", omittingEmptySubsequences: false)
        guard (1...2).contains(parts.count), !parts[0].isEmpty,
              parts.allSatisfy({ $0.allSatisfy { $0.isASCII && $0.isNumber } }),
              parts.count == 1 || !parts[1].isEmpty,
              let value = Decimal(string: trimmed, locale: Locale(identifier: "en_US_POSIX"))
        else { return .failure(.notANumber) }
        if parts.count == 2, parts[1].count > maxFractionDigits { return .failure(.tooManyDecimals(maxFractionDigits)) }
        if value < 0 { return .failure(.negative) }
        if value == 0 && !allowZero { return .failure(.notPositive) }
        return .success(value)
    }

    /// Plain `1234.5` text for display (never localized grouping, which could be misread).
    public static func format(_ value: Decimal) -> String { DecimalString(value).description }
}

/// Everything the expense screen has collected so far.
public struct ExpenseDraft: Sendable, Equatable {
    public var categoryID: UUID?
    public var amountText = ""
    /// ISO code; prefilled with the tenant currency when known (required, as on Android).
    public var currency = ""
    public var description = ""
    public var supplier = ""
    public var machineID: UUID?
    public var jobID: UUID?
    /// The machine of the selected job (the server attributes a job's cost to its machine).
    public var jobMachineID: UUID?
    public var paidFrom: ExpensePaidFrom = .cashCustody
    public var receiptCount = 0
    /// nil while the GPS attempt is still running.
    public var gps: GpsPayload?

    public init() {}
}

public enum ExpenseIssue: Sendable, Equatable, CustomStringConvertible {
    case categoryMissing
    case amount(DecimalInput.Failure)
    /// `example`: the tenant currency when known, shown in the message.
    case currencyInvalid(example: String?)
    case descriptionMissing
    case receiptRequired(reason: String)
    case gpsPending
    case gpsRequired(status: GpsStatus)
    case gpsTooInaccurate(accuracyM: Double, maxM: Double)
    case attributionMismatch

    public var description: String {
        switch self {
        case .categoryMissing: "Choose a category."
        case let .amount(failure): Self.describe(failure, what: "Amount")
        case let .currencyInvalid(example): "Enter a 3-letter currency code (e.g. \(example ?? "USD"))."
        case .descriptionMissing: "Describe what was paid for."
        case let .receiptRequired(reason): "A receipt photo is required \(reason)."
        case .gpsPending: "Waiting for the location fix…"
        case let .gpsRequired(status): "Your company requires a GPS fix for expenses (\(status.rawValue)). Try location again outdoors."
        case let .gpsTooInaccurate(accuracy, maxM):
            "The location is accurate to ±\(Int(accuracy.rounded())) m; your company requires ±\(Int(maxM)) m or better. Try location again."
        case .attributionMismatch: "The machine does not match the selected job's machine."
        }
    }

    public static func describe(_ failure: DecimalInput.Failure, what: String) -> String {
        switch failure {
        case .empty: "Enter the \(what.lowercased())."
        case .notANumber: "\(what) must be a number such as 1250.50."
        case let .tooManyDecimals(places): "\(what) may have at most \(places) decimals."
        case .notPositive: "\(what) must be more than zero."
        case .negative: "\(what) cannot be negative."
        }
    }
}

/// Result of checking a draft against the offline policy snapshot.
public struct ExpenseAssessment: Sendable, Equatable {
    public let amount: Decimal?
    public let currency: String?
    public let isForeignCurrency: Bool
    public let receiptRequired: Bool
    /// Above the auto-approve limit (or foreign currency): the expense is recorded as PENDING_APPROVAL.
    public let needsApproval: Bool
    public let issues: [ExpenseIssue]

    public var canSave: Bool { issues.isEmpty }
}

/// Offline enforcement of the `EXPENSE_CAPTURE` policy, mirroring `ExpenseService.submit`:
/// receipt required when amount > `receipt_required_above` (or in a foreign currency); GPS FIX with
/// accuracy ≤ `gps_max_accuracy_m` when `gps_required`; auto-approved only when amount ≤
/// `auto_approve_limit` in the base currency. The server re-checks everything.
public enum ExpenseRules {
    /// Same limit as the server's money columns and the Android app (4 decimals).
    public static let moneyDecimals = 4

    /// `baseCurrency`: the tenant currency when known (from the synced custody balances).
    public static func assess(_ draft: ExpenseDraft, policy: ExpenseCapturePolicy, baseCurrency: String?) -> ExpenseAssessment {
        var issues: [ExpenseIssue] = []
        if draft.categoryID == nil { issues.append(.categoryMissing) }
        var amount: Decimal?
        switch DecimalInput.parse(draft.amountText, maxFractionDigits: moneyDecimals) {
        case let .success(value): amount = value
        case let .failure(failure): issues.append(.amount(failure))
        }
        let code = draft.currency.trimmingCharacters(in: .whitespaces).uppercased()
        let currency: String? = CurrencyCode.isValid(code) ? code : nil
        if currency == nil { issues.append(.currencyInvalid(example: baseCurrency)) }
        // Unknown base currency + an explicit code: treat as foreign (stricter; the server decides).
        let foreign = currency.map { $0 != baseCurrency } ?? false
        if draft.description.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { issues.append(.descriptionMissing) }
        if let job = draft.jobMachineID, let machine = draft.machineID, job != machine { issues.append(.attributionMismatch) }

        let threshold = policy.receiptRequiredAbove.value
        let receiptRequired = foreign || (amount.map { $0 > threshold } ?? (threshold == 0))
        if receiptRequired && draft.receiptCount == 0 {
            issues.append(.receiptRequired(reason: foreign ? "for an expense in another currency"
                                           : threshold == 0 ? "for every expense"
                                           : "above \(DecimalInput.format(threshold)) \(baseCurrency ?? "")".trimmingCharacters(in: .whitespaces)))
        }
        if policy.gpsRequired {
            switch draft.gps {
            case nil: issues.append(.gpsPending)
            case let gps? where gps.status != .fix || gps.accuracyM == nil: issues.append(.gpsRequired(status: gps.status))
            case let gps?:
                if let accuracy = gps.accuracyM, accuracy > policy.gpsMaxAccuracyM {
                    issues.append(.gpsTooInaccurate(accuracyM: accuracy, maxM: policy.gpsMaxAccuracyM))
                }
            }
        } else if draft.gps == nil {
            issues.append(.gpsPending) // the attempt is always made and its real result recorded
        }
        let needsApproval = foreign || (amount.map { $0 > policy.autoApproveLimit.value } ?? false)
        return ExpenseAssessment(amount: amount, currency: currency, isForeignCurrency: foreign,
                                 receiptRequired: receiptRequired, needsApproval: needsApproval, issues: issues)
    }

    /// Explanation shown before saving when the expense will wait for a manager.
    public static func approvalNote(_ assessment: ExpenseAssessment, policy: ExpenseCapturePolicy, baseCurrency: String?) -> String? {
        guard assessment.needsApproval else { return nil }
        if assessment.isForeignCurrency {
            return "Expenses in another currency always need a manager's approval. It is recorded now and stays pending until approved."
        }
        let limit = policy.autoApproveLimit.value
        if limit == 0 { return "Every expense needs a manager's approval. It is recorded now and stays pending until approved." }
        let currency = baseCurrency.map { " \($0)" } ?? ""
        return "Above the auto-approval limit of \(DecimalInput.format(limit))\(currency): a manager must approve it. It is recorded now and stays pending until approved."
    }
}

public enum CurrencyCode {
    public static func isValid(_ code: String) -> Bool {
        code.count == 3 && code.allSatisfy { $0.isASCII && $0.isUppercase }
    }
}

/// Validation of the other finance forms (the recorder re-checks before writing to the outbox).
public enum FinanceRules {
    public static let litresDecimals = 3
    public static let unitPriceDecimals = 4
    public static let meterDecimals = 2

    /// Trims, drops empty text and caps the length (server limits: references 120, notes 1000, supplier 200).
    public static func clean(_ text: String?, max: Int) -> String? {
        guard let trimmed = text?.trimmingCharacters(in: .whitespacesAndNewlines), !trimmed.isEmpty else { return nil }
        return String(trimmed.prefix(max))
    }

    /// Required 3-letter code (cash collection, handover, fuel), as on Android.
    public static func currency(_ text: String) throws -> String {
        let code = text.trimmingCharacters(in: .whitespaces).uppercased()
        guard CurrencyCode.isValid(code) else { throw FieldRecorderError.invalid("Enter a 3-letter currency code.") }
        return code
    }

    public static func amount(_ text: String, what: String = "Amount", decimals: Int = ExpenseRules.moneyDecimals,
                              allowZero: Bool = false) throws -> Decimal {
        switch DecimalInput.parse(text, maxFractionDigits: decimals, allowZero: allowZero) {
        case let .success(value): return value
        case let .failure(failure): throw FieldRecorderError.invalid(ExpenseIssue.describe(failure, what: what))
        }
    }

    /// Fuel event shape rules from `FuelEventIn`: ISSUE/USAGE need a machine or job; PURCHASE/ISSUE
    /// need a unit price; USAGE carries no price.
    public static func fuelIssues(type: FuelEventType, litres: String, unitPrice: String, meterReading: String,
                                  machineID: UUID?, jobID: UUID?) -> [String] {
        var issues: [String] = []
        if case let .failure(f) = DecimalInput.parse(litres, maxFractionDigits: litresDecimals) {
            issues.append(ExpenseIssue.describe(f, what: "Litres"))
        }
        if type != .usage, case let .failure(f) = DecimalInput.parse(unitPrice, maxFractionDigits: unitPriceDecimals, allowZero: true) {
            issues.append(ExpenseIssue.describe(f, what: "Unit price"))
        }
        if !meterReading.trimmingCharacters(in: .whitespaces).isEmpty,
           case let .failure(f) = DecimalInput.parse(meterReading, maxFractionDigits: meterDecimals, allowZero: true) {
            issues.append(ExpenseIssue.describe(f, what: "Meter reading"))
        }
        if type != .purchase && machineID == nil && jobID == nil { issues.append("Choose the machine or job the fuel went to.") }
        return issues
    }
}
