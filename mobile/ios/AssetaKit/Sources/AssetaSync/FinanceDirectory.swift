import AssetaModel
import AssetaStore
import Foundation

/// A finance item recorded on this phone that affects cash custody but is not yet confirmed by the
/// server. Shown as unverified; never added into the synced balance as if it were confirmed.
public struct LocalCashItem: Sendable, Equatable, Identifiable {
    public enum Kind: String, Sendable { case collection, custodyExpense, handover }
    public let id: UUID
    public let kind: Kind
    public let amount: Decimal
    /// nil = the tenant's currency.
    public let currency: String?
    public let at: Date
    public let status: ClientOperationStatus
    public let errorCode: String?

    /// +1 for cash coming in, −1 for cash going out.
    public var sign: Decimal { kind == .collection ? 1 : -1 }
    public var title: String {
        switch kind {
        case .collection: "Cash collection"
        case .custodyExpense: "Expense paid from my cash"
        case .handover: "Cash handover"
        }
    }
}

/// One currency of "My cash": the synced balance plus what this phone still has to send.
public struct CashLine: Sendable, Equatable, Identifiable {
    public let currency: String
    /// Server balance (nil when the server has sent none for this currency yet).
    public let synced: CashCustodyBalanceDTO?
    /// Local, not yet confirmed items (all positive amounts).
    public let pendingCollections: Decimal
    public let pendingHandovers: Decimal
    public let pendingCashExpenses: Decimal
    public var id: String { currency }

    public init(currency: String, synced: CashCustodyBalanceDTO?, pendingCollections: Decimal = 0,
                pendingHandovers: Decimal = 0, pendingCashExpenses: Decimal = 0) {
        self.currency = currency
        self.synced = synced
        self.pendingCollections = pendingCollections
        self.pendingHandovers = pendingHandovers
        self.pendingCashExpenses = pendingCashExpenses
    }

    /// Net of local, not yet confirmed items (collections − custody expenses − handovers).
    public var unverifiedNet: Decimal { pendingCollections - pendingHandovers - pendingCashExpenses }
    /// What the balance will be if the server accepts every pending item (unverified).
    public var projected: Decimal { (synced?.outstanding.value ?? 0) + unverifiedNet }
    /// Estimate of the cash physically held (never a verified figure): the synced outstanding minus
    /// claimed handovers and expenses awaiting approval (already out of hand), plus the unsynced net.
    public var estimatedInHand: Decimal {
        let held = synced.map { $0.outstanding.value - $0.claimedUnverifiedHandovers.value - $0.pendingSpending.value } ?? 0
        return held + unverifiedNet
    }
}

public struct CashSummary: Sendable, Equatable {
    public let lines: [CashLine]
    /// Waiting to sync (PENDING/SENT, or held while the subscription is read-only).
    public let pending: [LocalCashItem]
    /// Rejected or in conflict: not counted anywhere until resolved.
    public let needsAttention: [LocalCashItem]
    public let baseCurrency: String?
}

extension FieldDirectory {
    public func expenseCategories() throws -> [ExpenseCategoryDTO] {
        try decodeAll("expense_category", as: ExpenseCategoryDTO.self).filter(\.isActive)
            .sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }
    }

    /// Customers of the supervisor's jobs (deactivated ones are hidden).
    public func customers() throws -> [CustomerDTO] {
        try decodeAll("customer", as: CustomerDTO.self).filter { $0.isActive != false }
            .sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }
    }

    /// Machines synced to this device (assigned machines and the machines of assigned jobs).
    public func machines() throws -> [MachineDTO] {
        try decodeAll("machine", as: MachineDTO.self).sorted { $0.assetCode < $1.assetCode }
    }

    public func expensePolicy() throws -> ExpensePolicySnapshot? {
        try store.syncState.policySnapshots(policyType: ExpensePolicySnapshot.policyType, tenantID: tenantID)
            .compactMap(ExpensePolicySnapshot.init).first { $0.scopeKey == "tenant" }
    }

    /// Whether a new expense may be recorded now, and under which rules.
    public func expenseGate() throws -> ExpenseGate {
        let now = ClockMonitor.enforcementNow(clockReference(), source: clock)
        return ExpenseGate.evaluate(snapshot: try expensePolicy(), offlineGrantUntil: offlineGrantUntil(), now: now)
    }

    public func custodyBalances() throws -> [CashCustodyBalanceDTO] {
        try store.syncState.custody(tenantID: tenantID)
            .compactMap { try? AssetaJSON.decoder().decode(CashCustodyBalanceDTO.self, from: Data($0.json.utf8)) }
    }

    /// The tenant currency when the synced custody makes it unambiguous (a single currency).
    public func baseCurrency() -> String? {
        let currencies = Set(((try? custodyBalances()) ?? []).map(\.currency))
        return currencies.count == 1 ? currencies.first : nil
    }

    public func cashSummary() throws -> CashSummary {
        let balances = try custodyBalances()
        let base = baseCurrency()
        let open: Set<ClientOperationStatus> = [.pending, .sent, .quarantined]
        let types: Set<String> = [OperationType.cashCollection.rawValue, OperationType.cashHandover.rawValue,
                                  OperationType.expense.rawValue]
        let items = try store.outbox.operations(tenantID: tenantID, owner: owner?.subject,
                                                statuses: open.union([.failed, .conflict]))
            .filter { types.contains($0.opType) }
            .compactMap(Self.cashItem)
        let pending = items.filter { open.contains($0.status) }
        var sums: [String: [LocalCashItem.Kind: Decimal]] = [:]
        for item in pending { sums[item.currency ?? base ?? "", default: [:]][item.kind, default: 0] += item.amount }
        var currencies = balances.map(\.currency)
        for key in sums.keys.sorted() where !currencies.contains(key) { currencies.append(key) }
        let lines = currencies.map { code in
            CashLine(currency: code, synced: balances.first { $0.currency == code },
                     pendingCollections: sums[code]?[.collection] ?? 0, pendingHandovers: sums[code]?[.handover] ?? 0,
                     pendingCashExpenses: sums[code]?[.custodyExpense] ?? 0)
        }
        return CashSummary(lines: lines, pending: pending, needsAttention: items.filter { !open.contains($0.status) },
                           baseCurrency: base)
    }

    static func cashItem(_ op: ClientOperation) -> LocalCashItem? {
        guard let payload = try? JSONValue.parse(op.payloadJSON) else { return nil }
        // Recorded for another custodian: not in my custody.
        if payload["staff_member_id"]?.stringValue != nil { return nil }
        guard let amount = payload["amount"]?.stringValue.flatMap(DecimalString.init(string:))?.value else { return nil }
        let kind: LocalCashItem.Kind
        let date: String?
        switch OperationType(rawValue: op.opType) {
        case .cashCollection: kind = .collection; date = payload["received_at"]?.stringValue
        case .cashHandover: kind = .handover; date = payload["handed_at"]?.stringValue
        case .expense where payload["paid_from"]?.stringValue == ExpensePaidFrom.cashCustody.rawValue:
            kind = .custodyExpense; date = payload["incurred_at"]?.stringValue
        default: return nil
        }
        return LocalCashItem(id: op.id, kind: kind, amount: amount, currency: payload["currency"]?.stringValue,
                             at: date.flatMap(AssetaJSON.parseInstant) ?? op.createdAtDevice, status: op.status,
                             errorCode: op.errorCode)
    }

    private func decodeAll<T: Decodable>(_ type: String, as: T.Type) throws -> [T] {
        try store.syncState.entities(type: type, tenantID: tenantID)
            .compactMap { try? AssetaJSON.decoder().decode(T.self, from: Data($0.json.utf8)) }
    }
}
