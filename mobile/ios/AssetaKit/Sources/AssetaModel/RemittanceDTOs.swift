import Foundation

// Stronger remittances (DEC-031 D1–D3): company deposit accounts, how a remittance reached the company, its
// evidence photos and the holding allowance. Shapes follow `contracts/openapi.json` (`DepositAccountDto`,
// `SyncDepositAccountDto`, `CashHandoverIn`, `RemittanceOverdueDto`); same as Android `RemittanceDtos.kt`.

extension SyncCapability {
    /// `CASH_HANDOVER` accepts method, deposit_account_id, evidence_attachment_ids and evidence_upload_ids (purpose
    /// REMITTANCE_EVIDENCE); `SyncData.deposit_accounts` carries the account picker.
    public static let remittanceDetails = "REMITTANCE_DETAILS_V1"
}

/// How a remittance reached the company (`RemittanceMethod`). Nil on remittances recorded before DEC-031.
public enum RemittanceMethod: String, Codable, Hashable, Sendable, CaseIterable {
    case cashToOffice = "CASH_TO_OFFICE", bankDeposit = "BANK_DEPOSIT", mobileMoney = "MOBILE_MONEY"

    /// Bank and mobile-money remittances carry a transaction reference (the tenant may require it).
    public var isNonCash: Bool { self != .cashToOffice }
}

/// `DepositAccountType`.
public enum DepositAccountType: String, Codable, Hashable, Sendable, CaseIterable {
    case bank = "BANK", mobileMoney = "MOBILE_MONEY", cashOffice = "CASH_OFFICE"

    /// The remittance method an account of this type implies (server `ACCOUNT_TYPE_METHOD`).
    public var method: RemittanceMethod {
        switch self {
        case .bank: .bankDeposit
        case .mobileMoney: .mobileMoney
        case .cashOffice: .cashToOffice
        }
    }
}

/// `DepositAccountDto` / `SyncDepositAccountDto` (the sync form adds `sync_revision`): a company account a
/// remittance can be paid into. The account number is only ever sent masked ("•••• 4821").
public struct DepositAccountDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let name: String
    /// Kept as text so an account type added later never breaks the picker (``type`` is nil then).
    public let accountType: String
    public let institution: String?
    public let accountNumberMasked: String?
    public let currency: String
    public let note: String?
    public let isActive: Bool
    public let version: Int
    public let syncRevision: Int64?

    public init(id: UUID, name: String, accountType: String, institution: String?, accountNumberMasked: String?,
                currency: String, note: String? = nil, isActive: Bool = true, version: Int = 1, syncRevision: Int64? = nil) {
        self.id = id
        self.name = name
        self.accountType = accountType
        self.institution = institution
        self.accountNumberMasked = accountNumberMasked
        self.currency = currency
        self.note = note
        self.isActive = isActive
        self.version = version
        self.syncRevision = syncRevision
    }

    public var type: DepositAccountType? { DepositAccountType(rawValue: accountType) }

    enum CodingKeys: String, CodingKey {
        case id, name, institution, currency, note, version
        case accountType = "account_type", accountNumberMasked = "account_number_masked", isActive = "is_active"
        case syncRevision = "sync_revision"
    }
}

/// `OverdueReason` of a `RemittanceOverdueDto`: after the daily cut-off, or held longer than the allowance.
public enum OverdueReason: String, Codable, Hashable, Sendable {
    case cutoff = "CUTOFF", heldTooLong = "HELD_TOO_LONG"
}
