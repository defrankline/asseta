import AssetaModel
import AssetaNetwork
import AssetaStore
import Foundation

// Supervisor customers (strings doc "Supervisor — customers"; Android `CustomerRules`, `FieldCustomers`, `CustomerTexts`):
// add customers and edit their details online (`tenant.customer.details`); payment terms only with `tenant.customer.write`.

/// `CustomerDto` as the Supervisor app shows and edits it.
public struct FieldCustomerDTO: Codable, Hashable, Sendable, Identifiable {
    public let id: UUID
    public let code: String
    public let name: String
    public let taxID: String?
    public let contactName: String?
    public let contactPhone: String?
    public let contactEmail: String?
    public let paymentTermsDays: Int
    public let isActive: Bool
    public let version: Int

    public init(id: UUID, code: String, name: String, taxID: String? = nil, contactName: String? = nil, contactPhone: String? = nil,
                contactEmail: String? = nil, paymentTermsDays: Int = 30, isActive: Bool = true, version: Int = 1) {
        self.id = id
        self.code = code
        self.name = name
        self.taxID = taxID
        self.contactName = contactName
        self.contactPhone = contactPhone
        self.contactEmail = contactEmail
        self.paymentTermsDays = paymentTermsDays
        self.isActive = isActive
        self.version = version
    }

    enum CodingKeys: String, CodingKey {
        case id, code, name, version
        case taxID = "tax_id", contactName = "contact_name", contactPhone = "contact_phone", contactEmail = "contact_email"
        case paymentTermsDays = "payment_terms_days", isActive = "is_active"
    }

    public init(from decoder: any Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decode(UUID.self, forKey: .id)
        code = try c.decode(String.self, forKey: .code)
        name = try c.decode(String.self, forKey: .name)
        taxID = try c.decodeIfPresent(String.self, forKey: .taxID)
        contactName = try c.decodeIfPresent(String.self, forKey: .contactName)
        contactPhone = try c.decodeIfPresent(String.self, forKey: .contactPhone)
        contactEmail = try c.decodeIfPresent(String.self, forKey: .contactEmail)
        paymentTermsDays = try c.decodeIfPresent(Int.self, forKey: .paymentTermsDays) ?? CustomerRules.defaultTerms
        isActive = try c.decodeIfPresent(Bool.self, forKey: .isActive) ?? true
        version = try c.decodeIfPresent(Int.self, forKey: .version) ?? 1
    }
}

/// `CustomerIn` (add) and `CustomerUpdateIn` (edit, with the version last read).
public struct CustomerWriteIn: Encodable, Sendable, Equatable {
    public let code: String
    public let name: String
    public let taxID: String?
    public let contactName: String?
    public let contactPhone: String?
    public let contactEmail: String?
    public let paymentTermsDays: Int
    public let version: Int?

    enum CodingKeys: String, CodingKey {
        case code, name, version
        case taxID = "tax_id", contactName = "contact_name", contactPhone = "contact_phone", contactEmail = "contact_email"
        case paymentTermsDays = "payment_terms_days"
    }

    public func encode(to encoder: any Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(code, forKey: .code)
        try c.encode(name, forKey: .name)
        try c.encode(taxID, forKey: .taxID)
        try c.encode(contactName, forKey: .contactName)
        try c.encode(contactPhone, forKey: .contactPhone)
        try c.encode(contactEmail, forKey: .contactEmail)
        try c.encode(paymentTermsDays, forKey: .paymentTermsDays)
        try c.encodeIfPresent(version, forKey: .version)
    }
}

/// A customer as typed in the add / edit form.
public struct CustomerDraft: Sendable, Equatable {
    public var code = ""
    public var name = ""
    public var taxID = ""
    public var contactName = ""
    public var phone = ""
    public var email = ""
    /// Payment terms as typed (editable only with `tenant.customer.write`).
    public var termsText = String(CustomerRules.defaultTerms)

    public init(code: String = "", name: String = "", taxID: String = "", contactName: String = "", phone: String = "", email: String = "",
                termsText: String = String(CustomerRules.defaultTerms)) {
        self.code = code
        self.name = name
        self.taxID = taxID
        self.contactName = contactName
        self.phone = phone
        self.email = email
        self.termsText = termsText
    }
}

/// The checked values sent to the server (blank optional fields are nil).
public struct CustomerValues: Sendable, Equatable {
    public let code: String
    public let name: String
    public let taxID: String?
    public let contactName: String?
    public let phone: String?
    public let email: String?
    public let paymentTermsDays: Int
}

/// Offline checks of the customer form, as the server (`CustomerIn`). Same as Android `CustomerRules`.
public enum CustomerRules {
    public static let defaultTerms = 30
    public static let details = "tenant.customer.details"
    public static let write = "tenant.customer.write"

    public static func canEdit(_ permissions: Set<String>) -> Bool { permissions.contains(details) || permissions.contains(write) }
    public static func termsEditable(_ permissions: Set<String>) -> Bool { permissions.contains(write) }

    public static func check(_ d: CustomerDraft, termsEditable: Bool, currentTerms: Int = defaultTerms) -> Result<CustomerValues, AccountabilityRules.Problems> {
        var m: [String] = []
        func clean(_ text: String) -> String { text.trimmingCharacters(in: .whitespacesAndNewlines) }
        func optional(_ text: String) -> String? { let t = clean(text); return t.isEmpty ? nil : t }
        let code = clean(d.code)
        if code.isEmpty || code.count > 32 { m.append(CustomerTexts.errCode) }
        let name = clean(d.name)
        if name.isEmpty || name.count > 200 { m.append(CustomerTexts.errName) }
        let taxID = optional(d.taxID), contact = optional(d.contactName), phone = optional(d.phone)
        if (taxID?.count ?? 0) > 64 || (contact?.count ?? 0) > 200 || (phone?.count ?? 0) > 40 { m.append(CustomerTexts.errLong) }
        let email = optional(d.email)
        if let email, !validEmail(email) { m.append(CustomerTexts.errEmail) }
        var terms = currentTerms
        if termsEditable {
            if let value = Int(clean(d.termsText)), (0...365).contains(value) { terms = value } else { m.append(CustomerTexts.errTerms) }
        }
        guard m.isEmpty else { return .failure(AccountabilityRules.Problems(messages: m)) }
        return .success(CustomerValues(code: code, name: name, taxID: taxID, contactName: contact, phone: phone, email: email,
                                       paymentTermsDays: terms))
    }

    /// One "@" with text on both sides, no spaces, at most 320 characters.
    public static func validEmail(_ email: String) -> Bool {
        guard email.count <= 320, !email.contains(where: \.isWhitespace) else { return false }
        let parts = email.split(separator: "@", omittingEmptySubsequences: false)
        return parts.count == 2 && !parts[0].isEmpty && !parts[1].isEmpty
    }
}

/// Wording of the Supervisor customers screens, word for word as Android `CustomerTexts`.
public enum CustomerTexts {
    public static let section = "Customers"
    public static let row = "Customers"
    public static let title = "Customers"
    public static let search = "Search by name or code"
    public static let empty = "No customers found."
    public static let offline = "Customers need a connection. Connect to see, add or edit them."
    public static let loadFailed = "The customers could not be loaded. Pull to try again."
    public static let add = "Add a customer"
    public static let titleAdd = "Add a customer"
    public static let titleEdit = "Edit customer"
    public static let titleDetail = "Customer"
    public static let edit = "Edit details"
    public static let code = "Code"
    public static let name = "Name"
    public static let taxID = "Tax ID (optional)"
    public static let contactName = "Contact name (optional)"
    public static let phone = "Phone (optional)"
    public static let email = "Email (optional)"
    public static let labelTaxID = "Tax ID"
    public static let labelContact = "Contact"
    public static let labelPhone = "Phone"
    public static let labelEmail = "Email"
    public static let terms = "Payment terms"
    public static func termsDays(_ n: Int) -> String { "\(n) days" }
    public static func termsByOffice(_ n: Int) -> String { "\(n) days · Set by the office" }
    public static let footer = "Contracts, rates and payment terms stay with the office. Once saved, the customer is on this phone for hours sales and cash collections."
    public static let saved = "Customer saved."
    public static let stale = "Someone else changed this customer. Reload to see it."
    public static let errCode = "Enter a code (at most 32 characters)."
    public static let errName = "Enter the name (at most 200 characters)."
    public static let errEmail = "Enter a valid email address."
    public static let errTerms = "Enter payment terms between 0 and 365 days."
    public static let errLong = "Shorten the tax ID, contact name or phone."

    /// "{code} · {contact}" under a customer's name.
    public static func rowDetail(_ c: FieldCustomerDTO) -> String {
        ([c.code, c.contactName?.trimmingCharacters(in: .whitespaces).isEmpty == false ? c.contactName : nil] as [String?])
            .compactMap { $0 }.joined(separator: " · ")
    }

    /// The customer's details in screen order; empty values left out.
    public static func fields(_ c: FieldCustomerDTO, termsEditable: Bool) -> [(label: String, value: String)] {
        func value(_ text: String?) -> String? { text?.trimmingCharacters(in: .whitespaces).isEmpty == false ? text : nil }
        var rows: [(label: String, value: String)] = [(code, c.code)]
        if let v = value(c.taxID) { rows.append((labelTaxID, v)) }
        if let v = value(c.contactName) { rows.append((labelContact, v)) }
        if let v = value(c.contactPhone) { rows.append((labelPhone, v)) }
        if let v = value(c.contactEmail) { rows.append((labelEmail, v)) }
        rows.append((terms, termsEditable ? termsDays(c.paymentTermsDays) : termsByOffice(c.paymentTermsDays)))
        return rows
    }

    /// A customer's details back in the form.
    public static func draft(_ c: FieldCustomerDTO) -> CustomerDraft {
        CustomerDraft(code: c.code, name: c.name, taxID: c.taxID ?? "", contactName: c.contactName ?? "", phone: c.contactPhone ?? "",
                      email: c.contactEmail ?? "", termsText: String(c.paymentTermsDays))
    }
}

/// An online customer read or save.
public enum CustomerResult<T: Sendable>: Sendable {
    case done(T)
    /// No connection: nothing was sent (and nothing is queued).
    case offline
    /// The server refused it: its own words; `stale` when someone else changed the customer meanwhile.
    case refused(message: String, code: String?, stale: Bool)
}

extension SupervisorOnline {
    /// Active customers, searchable by name or code (`GET /tenant/customers`).
    public func customers(query: String) async -> CustomerResult<[FieldCustomerDTO]> {
        var items = [URLQueryItem(name: "page", value: "1"), URLQueryItem(name: "page_size", value: "50")]
        let q = query.trimmingCharacters(in: .whitespacesAndNewlines)
        if !q.isEmpty { items.append(URLQueryItem(name: "q", value: q)) }
        let result = await call { try await client.send(APIRequest<Page<FieldCustomerDTO>>.get("\(Self.tenant)/customers", query: items)).items.filter(\.isActive) }
        if case let .done(list) = result { remember(list) }
        return result
    }

    public func customer(_ id: UUID) async -> CustomerResult<FieldCustomerDTO> {
        let result = await call { try await client.send(APIRequest<FieldCustomerDTO>.get("\(Self.tenant)/customers/\(id.lowercased)")) }
        if case let .done(c) = result { remember([c]) }
        return result
    }

    /// Add (`id` nil) or edit with the version last read.
    public func saveCustomer(id: UUID?, values: CustomerValues, version: Int?) async -> CustomerResult<FieldCustomerDTO> {
        let body = CustomerWriteIn(code: values.code, name: values.name, taxID: values.taxID, contactName: values.contactName,
                                   contactPhone: values.phone, contactEmail: values.email, paymentTermsDays: values.paymentTermsDays,
                                   version: id == nil ? nil : version)
        let result = await call {
            if let id {
                try await client.send(APIRequest<FieldCustomerDTO>.mutation(.put, "\(Self.tenant)/customers/\(id.lowercased)", body: body, idempotencyKey: UUID()))
            } else {
                try await client.send(APIRequest<FieldCustomerDTO>.mutation(.post, "\(Self.tenant)/customers", body: body, idempotencyKey: UUID()))
            }
        }
        if case let .done(c) = result { remember([c]) }
        return result
    }

    /// Sync delivers only the customers on my jobs' contracts: a customer read or saved here is written into the synced
    /// customer list, where the hours sale and cash collection pickers find it (an inactive one leaves the pickers).
    func remember(_ customers: [FieldCustomerDTO]) {
        guard !customers.isEmpty else { return }
        let raw: String? = (try? store.syncState.value(SyncKey.cursor, tenant: tenantID.uuidString.lowercased())) ?? nil
        let revision = raw.flatMap { Int64($0) } ?? 0
        let rows = customers.compactMap { c -> StoredEntity? in
            guard let data = try? AssetaJSON.encoder().encode(c) else { return nil }
            return StoredEntity(entityType: "customer", id: c.id, revision: revision, version: Int64(c.version), json: String(decoding: data, as: UTF8.self))
        }
        _ = try? store.syncState.upsert(rows, tenantID: tenantID)
    }

    private func call<T: Sendable>(_ block: () async throws -> T) async -> CustomerResult<T> {
        do {
            return .done(try await block())
        } catch let error as APIError {
            switch error {
            case .transport: return .offline
            case let .server(_, body): return .refused(message: body.message, code: body.code, stale: body.code == "STALE_VERSION")
            default: return .refused(message: "Unexpected response from the server. Please try again.", code: error.code, stale: false)
            }
        } catch {
            return .refused(message: "Unexpected response from the server. Please try again.", code: nil, stale: false)
        }
    }
}
