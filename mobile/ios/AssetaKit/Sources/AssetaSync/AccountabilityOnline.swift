import AssetaModel
import AssetaNetwork
import AssetaStore
import Foundation

/// A value fetched online and saved for offline use (encrypted in `sync_kv`, cleared with the tenant's state).
/// `forbidden` records that the server refused the read for this user (a 403), as opposed to never fetched.
public struct SavedOnline<Value: Codable & Sendable>: Codable, Sendable {
    public let value: Value?
    public let forbidden: Bool
    public let fetchedAt: Date

    enum CodingKeys: String, CodingKey { case value, forbidden, fetchedAt = "fetched_at" }

    static func read(_ store: LocalStore, _ tenantID: UUID, _ key: String) -> SavedOnline? {
        guard let text = try? store.syncState.value(key, tenant: tenantID.uuidString.lowercased()) else { return nil }
        return try? AssetaJSON.decoder().decode(SavedOnline.self, from: Data(text.utf8))
    }

    static func write(_ saved: SavedOnline, _ store: LocalStore, _ tenantID: UUID, _ key: String) throws {
        let data = try AssetaJSON.encoder().encode(saved)
        try store.syncState.setValue(String(decoding: data, as: UTF8.self), for: key, tenant: tenantID.uuidString.lowercased())
    }
}

enum AccountabilityKey {
    static let cashPolicy = "policy_cash_custody"
    static let hoursPolicy = "policy_customer_hours"
    static let custodians = "cash_custodians_cache"
    static let pendingTransfers = "cash_transfers_pending_cache"
    static let pendingFloats = "cash_floats_pending_cache"
    static let purchases = "hours_purchases_cache"
    static let retentions = "cash_retentions_cache"
    static let transfers = "cash_transfers_cache"
    static let transferReasons = "hours_transfer_reasons_cache"
    static let retentionReasons = "cash_retention_reasons_cache"
}

/// Saved accountability lookups of the signed-in user (read side; works offline).
public struct AccountabilityDirectory: Sendable {
    let store: LocalStore
    let tenantID: UUID
    let owner: AccountIdentity?

    public init(store: LocalStore, tenantID: UUID, owner: AccountIdentity?) {
        self.store = store
        self.tenantID = tenantID
        self.owner = owner
    }

    public var cashPolicy: CashCustodyPolicyValues? { SavedOnline<CashCustodyPolicyValues>.read(store, tenantID, AccountabilityKey.cashPolicy)?.value }
    public var hoursPolicy: SavedOnline<CustomerHoursPolicyValues>? { SavedOnline.read(store, tenantID, AccountabilityKey.hoursPolicy) }
    public var custodians: [CustodianDTO] {
        SavedOnline<[CustodianDTO]>.read(store, tenantID, AccountabilityKey.custodians)?.value?.filter(\.isActive) ?? []
    }
    public var retentions: [CashRetentionDTO] { SavedOnline<[CashRetentionDTO]>.read(store, tenantID, AccountabilityKey.retentions)?.value ?? [] }

    public func access(permissions: [String]) -> FieldAccess {
        let capabilities = (try? store.syncState.value(SyncKey.capabilities, tenant: tenantID.uuidString.lowercased()))
            .map { Set($0.split(separator: ",").map(String.init)) }
        return FieldAccess(capabilities: capabilities, permissions: Set(permissions), cash: cashPolicy, hours: hoursPolicy?.value)
    }

    public var transferReasons: [ReasonCodeDTO] {
        SavedOnline<[ReasonCodeDTO]>.read(store, tenantID, AccountabilityKey.transferReasons)?.value?.filter(\.isActive) ?? []
    }

    public var retentionReasons: [CashReasonDTO] {
        SavedOnline<[CashReasonDTO]>.read(store, tenantID, AccountabilityKey.retentionReasons)?.value?.filter(\.isActive) ?? []
    }

    /// Cash transfers I sent or received (server copies, newest first) and when they were fetched.
    public var transfers: (items: [CashTransferDTO], fetchedAt: Date?) {
        let saved = SavedOnline<[CashTransferDTO]>.read(store, tenantID, AccountabilityKey.transfers)
        return ((saved?.value ?? []).sorted { $0.transferredAt > $1.transferredAt }, saved?.fetchedAt)
    }

    /// Cash waiting for my acknowledgement (transfers to me and floats issued to me), from the last online fetch,
    /// minus what this phone already acknowledged or disputed (until the next fetch confirms it).
    public func toAcknowledge(myStaffID: UUID?) -> (transfers: [CashTransferDTO], floats: [CashFloatDTO], fetchedAt: Date?) {
        let transfers = SavedOnline<[CashTransferDTO]>.read(store, tenantID, AccountabilityKey.pendingTransfers)
        let floats = SavedOnline<[CashFloatDTO]>.read(store, tenantID, AccountabilityKey.pendingFloats)
        let queued = Set(((try? store.outbox.operations(tenantID: tenantID, owner: owner?.subject,
                                                        statuses: Set(ClientOperationStatus.allCases))) ?? [])
            .filter { ($0.opType == OperationType.cashTransferAcknowledgement.rawValue
                        || $0.opType == OperationType.cashFloatAcknowledgement.rawValue) && JobProgress.live($0) }
            .map(\.entityID))
        let pendingTransfers = (transfers?.value ?? []).filter {
            $0.status == "PENDING_ACKNOWLEDGEMENT" && !queued.contains($0.id) && (myStaffID == nil || $0.fromStaffID != myStaffID)
        }
        let pendingFloats = (floats?.value ?? []).filter { $0.ackStatus != "ACKNOWLEDGED" && $0.ackStatus != "DISPUTED" && !queued.contains($0.id) }
        return (pendingTransfers, pendingFloats, transfers?.fetchedAt ?? floats?.fetchedAt)
    }

    /// Hours purchases a transfer may draw from: the office list when this user may read it, plus the purchases this
    /// phone recorded (acknowledged by the server).
    public func purchases() -> [HoursPurchaseDTO] {
        var byID: [UUID: HoursPurchaseDTO] = [:]
        for p in SavedOnline<[HoursPurchaseDTO]>.read(store, tenantID, AccountabilityKey.purchases)?.value ?? [] { byID[p.id] = p }
        let ops = (try? store.outbox.operations(tenantID: tenantID, owner: owner?.subject, statuses: [.acked])) ?? []
        for op in ops where op.opType == OperationType.hoursPurchase.rawValue {
            guard let entity = op.serverResultJSON.flatMap({ try? JSONValue.parse($0) })?["entity"],
                  let dto = try? entity.decode(as: HoursPurchaseDTO.self), byID[dto.id] == nil else { continue }
            byID[dto.id] = dto
        }
        return byID.values.filter { $0.status != "CANCELLED" }.sorted { $0.createdAt > $1.createdAt }
    }
}

extension SupervisorOnline {
    /// Refreshes the tenant policies and lists the accountability screens use and saves them for offline use. Each
    /// read is independent: a refusal (403) is saved as such, any other failure keeps the saved copy.
    public func refreshAccountability(permissions: [String], myStaffID: UUID?) async {
        let has = Set(permissions)
        let record = has.contains(FieldAccess.collectionRecord)
        if record {
            await save(AccountabilityKey.cashPolicy,
                       APIRequest<EffectivePolicyDTO<CashCustodyPolicyValues>>.get("\(Self.tenant)/policies/CASH_CUSTODY/effective")) { $0.values }
            await save(AccountabilityKey.custodians,
                       APIRequest<Page<CustodianDTO>>.get("\(Self.tenant)/cash/custodians", query: Self.page(200))) { $0.items }
            await save(AccountabilityKey.pendingTransfers, APIRequest<Page<CashTransferDTO>>.get(
                "\(Self.tenant)/cash/transfers",
                query: Self.page(100) + [URLQueryItem(name: "status", value: "PENDING_ACKNOWLEDGEMENT")])) { $0.items }
            var transferQuery = Self.page(100)
            if let myStaffID { transferQuery.append(URLQueryItem(name: "staff_member_id", value: myStaffID.lowercased)) }
            await save(AccountabilityKey.transfers,
                       APIRequest<Page<CashTransferDTO>>.get("\(Self.tenant)/cash/transfers", query: transferQuery)) { $0.items }
            await save(AccountabilityKey.retentionReasons, APIRequest<Page<CashReasonDTO>>.get(
                "\(Self.tenant)/cash/reasons", query: Self.page(100) + [URLQueryItem(name: "kind", value: "RETENTION")])) { $0.items }
            var floatQuery = Self.page(100) + [URLQueryItem(name: "awaiting_acknowledgement", value: "true")]
            if let myStaffID { floatQuery.append(URLQueryItem(name: "staff_member_id", value: myStaffID.lowercased)) }
            await save(AccountabilityKey.pendingFloats,
                       APIRequest<Page<CashFloatDTO>>.get("\(Self.tenant)/cash/floats", query: floatQuery)) { $0.items }
            var retentionQuery = Self.page(50)
            if let myStaffID { retentionQuery.append(URLQueryItem(name: "staff_member_id", value: myStaffID.lowercased)) }
            await save(AccountabilityKey.retentions,
                       APIRequest<Page<CashRetentionDTO>>.get("\(Self.tenant)/cash/retentions", query: retentionQuery)) { $0.items }
        }
        if has.contains(FieldAccess.hoursPurchase) || has.contains(FieldAccess.hoursTransfer) {
            await save(AccountabilityKey.hoursPolicy,
                       APIRequest<EffectivePolicyDTO<CustomerHoursPolicyValues>>.get("\(Self.tenant)/policies/CUSTOMER_HOURS/effective")) { $0.values }
        }
        if has.contains(FieldAccess.hoursTransfer) && has.contains(FieldAccess.hoursRead) {
            await save(AccountabilityKey.purchases, APIRequest<Page<HoursPurchaseDTO>>.get(
                "\(Self.tenant)/hours-purchases", query: Self.page(100) + [URLQueryItem(name: "cancelled", value: "false")])) { $0.items }
            await save(AccountabilityKey.transferReasons, APIRequest<Page<ReasonCodeDTO>>.get(
                "\(Self.tenant)/hours-reason-codes", query: Self.page(100) + [URLQueryItem(name: "kind", value: "TRANSFER")])) { $0.items }
        }
    }

    /// Asks to keep some cash instead of remitting it (online only; someone else decides). Throws
    /// ``FieldRecorderError/invalid(_:)`` with every form problem, or the server's ``APIError``.
    public func requestRetention(amountText: String, currency: String, reason: String, reasonID: UUID?,
                                 staffMemberID: UUID?, validUntil: Date?) async throws -> CashRetentionDTO {
        let values: (amount: Decimal, currency: String, reason: String)
        switch AccountabilityRules.retention(amountText: amountText, currency: currency, reason: reason) {
        case let .failure(problems): throw FieldRecorderError.invalid(problems.text)
        case let .success(checked): values = checked
        }
        let body = CashRetentionIn(amount: values.amount, currency: values.currency, reason: values.reason, reasonID: reasonID,
                                   staffMemberID: staffMemberID, validUntil: validUntil)
        let created = try await client.send(try APIRequest<CashRetentionDTO>.mutation(
            .post, "\(Self.tenant)/cash/retentions", body: body, idempotencyKey: UUID()))
        let saved = SavedOnline<[CashRetentionDTO]>.read(store, tenantID, AccountabilityKey.retentions)?.value ?? []
        try? SavedOnline.write(SavedOnline(value: [created] + saved.filter { $0.id != created.id }, forbidden: false, fetchedAt: now()),
                               store, tenantID, AccountabilityKey.retentions)
        return created
    }

    private func save<Response: Decodable & Sendable, Value: Codable & Sendable>(
        _ key: String, _ request: APIRequest<Response>, _ map: (Response) -> Value
    ) async {
        do {
            let response = try await client.send(request)
            try SavedOnline.write(SavedOnline(value: map(response), forbidden: false, fetchedAt: now()), store, tenantID, key)
        } catch let error as APIError where error.httpStatus == 403 || error.httpStatus == 404 {
            try? SavedOnline<Value>.write(SavedOnline(value: nil, forbidden: true, fetchedAt: now()), store, tenantID, key)
        } catch {
            // Offline or server trouble: keep the saved copy.
        }
    }

    static func page(_ size: Int) -> [URLQueryItem] {
        [URLQueryItem(name: "page", value: "1"), URLQueryItem(name: "page_size", value: String(size))]
    }
}
