import AssetaModel
import Foundation

// Owner-only read DTOs the Android Owner app already shows (`MachineDto`, `ExpenseDto`, `AcknowledgementDto` in
// `contracts/openapi.json`). Only the fields the Owner screens use are decoded.

/// `GET /tenant/machines/{id}`: the register entry behind a fleet machine (make, model, ownership).
public struct OwnerMachineDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let assetCode: String
    public let name: String
    public let status: String
    public let ownership: String
    public let manufacturer: String?
    public let model: String?
    public let yearOfManufacture: Int?

    enum CodingKeys: String, CodingKey {
        case id, name, status, ownership, manufacturer, model
        case assetCode = "asset_code", yearOfManufacture = "year_of_manufacture"
    }

    /// "Caterpillar 320 2019", or nil when nothing is known.
    public var modelLine: String? {
        let parts = [manufacturer, model, yearOfManufacture.map(String.init)].compactMap { $0 }
        return parts.isEmpty ? nil : parts.joined(separator: " ")
    }
}

/// `GET /tenant/expenses/{id}`: the expense behind an expense approval (fetched on demand, never cached).
public struct ExpenseDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let amount: DecimalString
    public let currency: String
    public let description: String
    public let status: String
    public let incurredAt: Date
    public let paidFrom: String
    public let supplier: String?
    public let receiptAttachmentIDs: [UUID]

    enum CodingKeys: String, CodingKey {
        case id, amount, currency, description, status, supplier
        case incurredAt = "incurred_at", paidFrom = "paid_from", receiptAttachmentIDs = "receipt_attachment_ids"
    }

    public init(from decoder: any Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(UUID.self, forKey: .id)
        amount = try c.decode(DecimalString.self, forKey: .amount)
        currency = try c.decode(String.self, forKey: .currency)
        description = try c.decode(String.self, forKey: .description)
        status = try c.decode(String.self, forKey: .status)
        incurredAt = try c.decode(Date.self, forKey: .incurredAt)
        paidFrom = try c.decode(String.self, forKey: .paidFrom)
        supplier = try c.decodeIfPresent(String.self, forKey: .supplier)
        receiptAttachmentIDs = try c.decodeIfPresent([UUID].self, forKey: .receiptAttachmentIDs) ?? []
    }
}

/// `GET /tenant/jobs/{id}/acknowledgements`: the customer's sign-off of the hours.
public struct AcknowledgementDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let method: String
    public let signerName: String
    public let capturedAt: Date
    public let acknowledgedHours: DecimalString?
    public let signatureAttachmentID: UUID?

    enum CodingKeys: String, CodingKey {
        case id, method, signerName = "signer_name", capturedAt = "captured_at"
        case acknowledgedHours = "acknowledged_hours", signatureAttachmentID = "signature_attachment_id"
    }
}
