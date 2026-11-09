import AssetaModel
import AssetaStore
import Foundation

// DEC-032 Phase 3 on the Supervisor app (strings doc "independence and evidence"): what a collection pays for and why
// part of the cash stays with the custodian. Offline first; the server re-checks everything when the op arrives.

/// One row of the collection's "Pays for" picker: a synced purchase, or a sale still in this phone's outbox.
public struct CollectionLinkOption: Sendable, Equatable, Identifiable {
    /// The purchase id, or the offline sale's client id (the server accepts either).
    public let id: UUID
    public let title: String
    public let subtitle: String?
    /// The outbox operation the collection must wait for (nil = the server already has the purchase).
    public let operationID: UUID?
    /// Set when this row is an open invoice: the collection sends `allocations` instead of `purchase_id`.
    public var invoice: SyncOpenInvoiceDTO? = nil
}

public enum CollectionLinks {
    typealias T = FieldAccountabilityTexts

    /// The customer's open purchases, newest first, then this phone's unsynced sales of that customer, then the open
    /// invoices in the form's currency (soonest due first). Nil customer: none.
    public static func options(purchases: [HoursPurchaseDTO], unsynced: [ClientOperation], customerID: UUID?,
                               invoices: [SyncOpenInvoiceDTO] = [], currency: String = "") -> [CollectionLinkOption] {
        guard let customerID else { return [] }
        let synced = purchases.filter { $0.customerID == customerID && $0.status != "CANCELLED" }
        let known = Set(synced.compactMap(\.clientID))
        let local: [CollectionLinkOption] = unsynced.compactMap { op in
            guard op.opType == OperationType.hoursPurchase.rawValue, !known.contains(op.entityID),
                  let p = try? JSONValue.parse(op.payloadJSON).decode(as: HoursPurchasePayload.self), p.customerID == customerID
            else { return nil }
            return CollectionLinkOption(id: p.clientID, title: T.collectionUnsynced(hours: DecimalInput.format(p.hours.value)), subtitle: nil, operationID: op.id)
        }
        return synced.map {
            CollectionLinkOption(id: $0.id, title: $0.purchaseNumber, subtitle: T.collectionLinkLeft(hours: DecimalInput.format($0.totals.remaining.value)),
                                 operationID: nil)
        } + local + OpenInvoices.options(invoices, customerID: customerID, currency: currency).map {
            CollectionLinkOption(id: $0.id, title: $0.invoiceNumber, subtitle: T.collectionInvoiceRow(balance: "\(DecimalInput.format($0.balance.value)) \($0.currency)"),
                                 operationID: nil, invoice: $0)
        }
    }
}

extension AccountabilityDirectory {
    /// "Pays for" rows of one customer: cached purchases plus this phone's sales the server does not have yet.
    public func collectionLinks(customerID: UUID?, currency: String = "") -> [CollectionLinkOption] {
        let waiting = (try? store.outbox.operations(tenantID: tenantID, owner: owner?.subject,
                                                    statuses: [.pending, .sent, .quarantined])) ?? []
        let invoices = (try? OpenInvoices.load(store: store, tenantID: tenantID)) ?? []
        return CollectionLinks.options(purchases: purchases(), unsynced: waiting, customerID: customerID, invoices: invoices, currency: currency)
    }
}

/// Whether the hand-over form asks why part of the cash stays with the custodian.
public enum PartialRemittanceNeed: Sendable, Equatable {
    case hidden
    /// Less than the phone's estimate of their cash, with the full balance required.
    case required(balance: Decimal)
    /// Recording for another holder: what they hold is unknown here, so the reason is optional.
    case optional
}

public enum PartialRemittance {
    public static let minReason = 3

    public static func need(access: FieldAccess, amountText: String, estimate: Decimal?, otherHolder: Bool) -> PartialRemittanceNeed {
        guard access.partialReason else { return .hidden }
        if otherHolder { return .optional }
        guard let estimate, let amount = AccountabilityRules.value(amountText, decimals: AccountabilityRules.moneyDecimals),
              amount < estimate else { return .hidden }
        return .required(balance: estimate)
    }

    /// The phone's estimate of the custodian's cash in `currency`.
    public static func estimate(_ summary: CashSummary?, currency: String) -> Decimal? {
        let code = currency.trimmingCharacters(in: .whitespaces)
        return summary?.lines.first { $0.currency.caseInsensitiveCompare(code) == .orderedSame }?.estimatedInHand
    }

    /// Valid when the reason is optional and left empty, or at least 3 characters (same as Android `partialReasonOk`).
    public static func issues(_ need: PartialRemittanceNeed, reason: String) -> [String] {
        let text = reason.trimmingCharacters(in: .whitespacesAndNewlines)
        if need == .hidden || (need == .optional && text.isEmpty) || text.count >= minReason { return [] }
        return [FieldAccountabilityTexts.handoverPartialError]
    }
}
