import AssetaModel
import AssetaStore
import Foundation

// DEC-032 Phase 4 on the Supervisor app: invoices a field collection can name (SYNC_OPEN_INVOICES). The list is the
// server's full snapshot for this recorder; the server re-checks balance, customer and currency when the op arrives.

public enum OpenInvoices {
    /// `sync_entity.entity_type` of the snapshot.
    public static let entityType = "open_invoice"

    /// The customer's open invoices in the collection's currency (the server refuses another; none until one is entered),
    /// with money still owed, in the server's order: soonest due first, no due date last, then by issue date.
    public static func options(_ invoices: [SyncOpenInvoiceDTO], customerID: UUID?, currency: String) -> [SyncOpenInvoiceDTO] {
        guard let customerID else { return [] }
        let code = currency.trimmingCharacters(in: .whitespaces).uppercased()
        return invoices.filter { $0.customerID == customerID && $0.currency == code && $0.balance.value > 0 }.sorted { a, b in
            switch (a.dueDate, b.dueDate) {
            case let (x?, y?) where x != y: x < y
            case (_?, nil): true
            case (nil, _?): false
            default: a.issuedAt < b.issuedAt
            }
        }
    }

    static func load(store: LocalStore, tenantID: UUID) throws -> [SyncOpenInvoiceDTO] {
        try store.syncState.entities(type: entityType, tenantID: tenantID)
            .compactMap { try? AssetaJSON.decoder().decode(SyncOpenInvoiceDTO.self, from: Data($0.json.utf8)) }
    }

    /// How much of the collection goes on the invoice: all of it, up to the invoice's open balance.
    public static func allocation(amount: Decimal, invoice: SyncOpenInvoiceDTO) -> Decimal { min(amount, invoice.balance.value) }
}

extension FieldDirectory {
    /// The open invoices synced to this phone.
    public func openInvoices() throws -> [SyncOpenInvoiceDTO] {
        try OpenInvoices.load(store: store, tenantID: tenantID)
    }
}
