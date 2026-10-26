import AssetaCapture
import AssetaModel
import AssetaStore
import Foundation

/// CASH_CUSTODY remittance requirements the hand-over form enforces (DEC-031 D2; the server re-checks them).
public struct RemittanceRequirements: Sendable, Equatable {
    /// A company deposit account must be chosen.
    public var account: Bool
    /// Bank deposit / mobile money need a transaction reference (cash to the office never does).
    public var reference: Bool
    /// At least one photo of the deposit slip or payment confirmation.
    public var evidence: Bool

    public init(account: Bool = false, reference: Bool = false, evidence: Bool = false) {
        self.account = account
        self.reference = reference
        self.evidence = evidence
    }
}

/// Offline checks of the remittance details (same rules, wording and order as Android `RemittanceRules`).
public enum RemittanceRules {
    public static let maxEvidence = 10
    public static let errAccountMismatch = "The account you chose does not match how the money was handed over."
    public static let errAccountCurrency = "The account you chose holds a different currency."
    public static let errAccountGone = "The account you chose is no longer in use. Choose another one."

    /// The account type that matches each method (`CASH_TO_OFFICE` ↔ `CASH_OFFICE`, ...).
    public static func accountType(for method: RemittanceMethod) -> DepositAccountType {
        switch method {
        case .cashToOffice: .cashOffice
        case .bankDeposit: .bank
        case .mobileMoney: .mobileMoney
        }
    }

    /// Picker rows: active accounts of the form's currency (case-insensitive) whose type matches the method, by name.
    public static func accounts(_ all: [DepositAccountDTO], currency: String, method: RemittanceMethod) -> [DepositAccountDTO] {
        all.filter { $0.isActive && $0.type == accountType(for: method) && sameCurrency($0.currency, currency) }
            .sorted { $0.name.lowercased() < $1.name.lowercased() }
    }

    /// Row subtitle: "{institution} · {account_number_masked}", missing parts left out (empty when both are).
    public static func subtitle(_ account: DepositAccountDTO) -> String {
        [account.institution, account.accountNumberMasked]
            .compactMap { $0 }.filter { !$0.trimmingCharacters(in: .whitespaces).isEmpty }.joined(separator: " · ")
    }

    public static func referenceRequired(_ requirements: RemittanceRequirements, method: RemittanceMethod) -> Bool {
        requirements.reference && method.isNonCash
    }

    /// Why the remittance cannot be saved yet (empty = fine). `account` is the chosen account (nil = none);
    /// `accountID` set with `account` nil means it is no longer on the phone (deactivated).
    public static func check(_ requirements: RemittanceRequirements, method: RemittanceMethod, accountID: UUID?,
                             account: DepositAccountDTO?, currency: String, reference: String, photoCount: Int) -> [String] {
        typealias T = FieldAccountabilityTexts
        var messages: [String] = []
        if accountID != nil && (account == nil || account?.isActive == false) {
            messages.append(errAccountGone)
        } else if let account, account.type != accountType(for: method) {
            messages.append(errAccountMismatch)
        } else if let account, !sameCurrency(account.currency, currency) {
            messages.append(errAccountCurrency)
        } else if accountID == nil && requirements.account {
            messages.append(T.remitErrAccount)
        }
        if referenceRequired(requirements, method: method) && reference.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            messages.append(T.remitErrReference)
        }
        if requirements.evidence && photoCount == 0 { messages.append(T.remitErrEvidence) }
        if photoCount > maxEvidence { messages.append("At most \(maxEvidence) photos per handover.") }
        return messages
    }

    static func depositAccount(_ id: UUID, store: LocalStore, tenantID: UUID) throws -> DepositAccountDTO? {
        try store.syncState.entity(type: "deposit_account", id: id, tenantID: tenantID)
            .flatMap { try? AssetaJSON.decoder().decode(DepositAccountDTO.self, from: Data($0.json.utf8)) }
    }

    static func sameCurrency(_ a: String, _ b: String) -> Bool {
        a.caseInsensitiveCompare(b.trimmingCharacters(in: .whitespaces)) == .orderedSame
    }
}

extension FieldDirectory {
    /// Company deposit accounts synced to this phone (active ones), by name.
    public func depositAccounts() throws -> [DepositAccountDTO] {
        try allDepositAccounts().filter(\.isActive)
    }

    /// One synced deposit account (also a deactivated one), or nil when it is not on this phone.
    public func depositAccount(_ id: UUID) throws -> DepositAccountDTO? {
        try RemittanceRules.depositAccount(id, store: store, tenantID: tenantID)
    }

    /// Every synced deposit account, deactivated ones included (a chosen account that was deactivated reads as gone).
    public func allDepositAccounts() throws -> [DepositAccountDTO] {
        try store.syncState.entities(type: "deposit_account", tenantID: tenantID)
            .compactMap { try? AssetaJSON.decoder().decode(DepositAccountDTO.self, from: Data($0.json.utf8)) }
            .sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }
    }
}

/// What the hand-over form shows for the remittance details (pure, unit-tested; same as Android `RemittanceForm`).
public enum RemittanceForm {
    typealias T = FieldAccountabilityTexts

    /// Choosing an account sets the method from its type; clearing it keeps the method.
    public static func selectAccount(_ draft: inout RemittanceDraft, accountID: UUID?, accounts: [DepositAccountDTO]) {
        let account = accounts.first { $0.id == accountID }
        draft.accountID = accountID
        if let method = account?.type?.method { draft.method = method }
    }

    /// A new method drops an account of another type.
    public static func selectMethod(_ draft: inout RemittanceDraft, method: RemittanceMethod, accounts: [DepositAccountDTO]) {
        let account = accounts.first { $0.id == draft.accountID }
        draft.method = method
        if let account, account.type != RemittanceRules.accountType(for: method) { draft.accountID = nil }
    }

    public static func issues(_ draft: RemittanceDraft, requirements: RemittanceRequirements, accounts: [DepositAccountDTO],
                              currency: String, reference: String, photoCount: Int) -> [String] {
        RemittanceRules.check(requirements, method: draft.method, accountID: draft.accountID,
                              account: accounts.first { $0.id == draft.accountID }, currency: currency, reference: reference,
                              photoCount: photoCount)
    }

    public static func accountLabel(_ r: RemittanceRequirements) -> String { r.account ? T.remitAccount : T.remitAccountOptional }

    public static func referenceLabel(_ r: RemittanceRequirements, method: RemittanceMethod) -> String {
        RemittanceRules.referenceRequired(r, method: method) ? T.remitReference : T.remitReferenceOptional
    }

    public static func photosLabel(_ r: RemittanceRequirements) -> String { r.evidence ? T.remitPhotos : T.remitPhotosOptional }
}

/// Method and account chosen on the hand-over form.
public struct RemittanceDraft: Sendable, Equatable {
    public var method: RemittanceMethod
    public var accountID: UUID?

    public init(method: RemittanceMethod = .cashToOffice, accountID: UUID? = nil) {
        self.method = method
        self.accountID = accountID
    }
}
