import AssetaModel
import AssetaStore
@testable import AssetaSync
import Foundation
import Testing

/// DEC-030 gap pass on the field side: capabilities switched off by the tenant (G1), names on the synced DTOs (G2),
/// "Ask to keep cash" through the outbox (G3) and exact-record notification taps (G5). Same rules as Android.
struct AccountabilityGapTests {
    static let withRetention = AccountabilityTests.all + ["OP_CASH_RETENTION_REQUEST"]

    // MARK: - G1 capabilities

    @Test func customerHoursSwitchedOffHidesItsEntries() {
        let on = FieldAccess(capabilities: Set(AccountabilityTests.all), permissions: AccountabilityTests.permissions,
                             cash: AccountabilityTests.cashOn, hours: AccountabilityTests.hoursOn)
        #expect(on.sellHours && on.requestHoursTransfer && on.customerHoursOn)
        let off = FieldAccess(capabilities: Set(AccountabilityTests.all), permissions: AccountabilityTests.permissions,
                              cash: AccountabilityTests.cashOn, hours: AccountabilityTests.hoursOn,
                              disabledCapabilities: [TenantCapability.customerHours])
        #expect(!off.sellHours && !off.walkIn && !off.requestHoursTransfer && !off.customerHoursOn)
        // Cash and meter entries are not affected.
        #expect(off.transferCash && off.askToKeepCash && off.dailyReading)
    }

    @Test func meDecodesDisabledCapabilitiesTolerantly() throws {
        func tenant(_ extra: String) throws -> TenantMembership {
            let json = #"{"tenant_id":"11111111-1111-4111-8111-111111111111","name":"Acme","status":"ACTIVE","access_state":"FULL","permissions":[],"menus":[],"menu_groups":[]"# + extra + "}"
            return try AssetaJSON.decoder().decode(TenantMembership.self, from: Data(json.utf8))
        }
        #expect(try tenant("").disabledCapabilities.isEmpty)
        #expect(try tenant(#","disabled_capabilities":null"#).disabledCapabilities.isEmpty)
        let off = try tenant(#","disabled_capabilities":["CUSTOMER_HOURS"]"#)
        #expect(off.isDisabled(TenantCapability.customerHours) && off.disabledCapabilities == ["CUSTOMER_HOURS"])
        // Round trip (the profile cache encodes it).
        let again = try AssetaJSON.decoder().decode(TenantMembership.self, from: AssetaJSON.encoder().encode(off))
        #expect(again == off)
    }

    // MARK: - G2 names

    @Test func fieldDTOsDecodeNamesAndToleratesOlderServers() throws {
        let transfer = #"{"id":"aaaaaaaa-0000-4000-8000-000000000001","client_id":null,"from_staff_id":"bbbbbbbb-0000-4000-8000-000000000002","to_staff_id":"cccccccc-0000-4000-8000-000000000003","amount_declared":"100","currency":"TZS","transferred_at":"2026-10-24T08:00:00Z","note":null,"status":"PENDING_ACKNOWLEDGEMENT","source":"SYNC","recorded_by":null,"recorded_at":"2026-10-24T08:00:00Z","amount_received":null,"ack_method":null,"acknowledged_by":null,"acknowledged_at":null,"ack_note":null,"variance_id":null"#
        let named = try AssetaJSON.decoder().decode(CashTransferDTO.self,
                                                    from: Data((transfer + #","from_staff_name":"Asha","to_staff_name":null}"#).utf8))
        #expect(named.fromStaffName == "Asha" && named.toStaffName == nil)
        let old = try AssetaJSON.decoder().decode(CashTransferDTO.self, from: Data((transfer + "}").utf8))
        #expect(old.fromStaffName == nil && old.recordedByName == nil)
        #expect(DisplayName.or(named.fromStaffName, id: named.fromStaffID) == "Asha")
        #expect(DisplayName.or(named.toStaffName, id: named.toStaffID) == "cccccccc")
        #expect(DisplayName.machine(code: "EX-07", name: "Excavator", id: nil) == "EX-07 · Excavator")
        #expect(DisplayName.machine(code: nil, name: nil, id: named.toStaffID) == "cccccccc")
    }

    // MARK: - G3 retention through the outbox

    @Test func retentionIsQueuedOfflineWithItsClientID() async throws {
        let h = try SyncHarness()
        h.server.mutate { $0.capabilities = Self.withRetention }
        let engine = h.engine()
        _ = try await engine.sync()
        let access = FieldAccess(capabilities: Set(Self.withRetention), permissions: AccountabilityTests.permissions,
                                 cash: AccountabilityTests.cashOn)
        #expect(access.retentionOffline)

        let clientID = UUID(), holder = UUID()
        #expect(throws: FieldRecorderError.self) {
            try h.recorder.requestRetention(amountText: "0", currency: "TZS", reason: "Fuel", reasonID: nil, staffMemberID: nil,
                                            validUntil: nil, clientID: clientID)
        }
        let op = try h.recorder.requestRetention(amountText: "25000", currency: "tzs", reason: "  Fuel for tomorrow  ",
                                                 reasonID: nil, staffMemberID: holder, validUntil: nil, clientID: clientID)
        #expect(op.opType == "CASH_RETENTION_REQUEST" && op.entityID == clientID && op.entityType == "cash_retention")
        let p = try JSONValue.parse(op.payloadJSON)
        #expect(p["client_id"]?.stringValue == clientID.lowercased && p["amount"]?.stringValue == "25000")
        #expect(p["currency"]?.stringValue == "TZS" && p["reason"]?.stringValue == "Fuel for tomorrow")
        #expect(p["staff_member_id"]?.stringValue == holder.lowercased && p["valid_until"] == nil)
        // One request per form visit.
        #expect(throws: FieldRecorderError.notAllowed(FieldAccountabilityTexts.alreadySaved)) {
            try h.recorder.requestRetention(amountText: "25000", currency: "TZS", reason: "Fuel", reasonID: nil,
                                            staffMemberID: nil, validUntil: nil, clientID: clientID)
        }
        let directory = AccountabilityDirectory(store: h.store, tenantID: SyncFixtures.tenant, owner: nil)
        let queued = try #require(directory.myRetentions().first)
        #expect(queued.matches(clientID) && queued.serverID == nil && queued.syncStatus == .pending && queued.amount == 25000)
        #expect(FieldAccountabilityTexts.operationTitle(.cashRetentionRequest, payload: nil) == "Request to keep cash")

        _ = try await engine.sync(force: true)
        #expect(try h.status(op.id) == .acked)
        let acked = try #require(directory.myRetentions().first)
        #expect(acked.syncStatus == nil && acked.status == "PENDING" && acked.serverID != nil)
        #expect(acked.matches(try #require(acked.serverID)) && acked.matches(clientID))
        #expect(FieldAccountabilityTexts.retentionStatusText("PENDING") == "Waiting for approval")
    }

    @Test func retentionNeedsTheServerCapability() throws {
        let h = try SyncHarness()
        try AccountabilityTests.supported(h.store) // no OP_CASH_RETENTION_REQUEST
        #expect(throws: FieldRecorderError.notAllowed(FieldAccountabilityTexts.serverTooOld)) {
            try h.recorder.requestRetention(amountText: "100", currency: "TZS", reason: "Fuel", reasonID: nil, staffMemberID: nil,
                                            validUntil: nil)
        }
        let access = FieldAccess(capabilities: Set(AccountabilityTests.all), permissions: AccountabilityTests.permissions,
                                 cash: AccountabilityTests.cashOn)
        #expect(access.askToKeepCash && !access.retentionOffline) // the online request is used then
    }

    @Test func retentionTurnedOffIsAConflictInPlainWords() async throws {
        let h = try SyncHarness()
        h.server.mutate { $0.capabilities = Self.withRetention; $0.retentionAllowed = false }
        let engine = h.engine()
        _ = try await engine.sync()
        let op = try h.recorder.requestRetention(amountText: "100", currency: "TZS", reason: "Fuel", reasonID: nil,
                                                 staffMemberID: nil, validUntil: nil)
        _ = try await engine.sync(force: true)
        #expect(try h.status(op.id) == .conflict)
        #expect(try h.store.outbox.operation(id: op.id)?.errorCode == "RETENTION_NOT_ALLOWED")
        #expect(FieldAccountabilityTexts.conflictText("RETENTION_NOT_ALLOWED")
            == "Your company does not allow keeping cash, so this request was not accepted.")
        #expect(FieldAccountabilityTexts.conflictText("DUPLICATE_RETENTION") == "This request to keep cash was already sent.")
        #expect(FieldAccountabilityTexts.conflictText("VALIDATION_FAILED") == nil)
        let item = try #require(AccountabilityDirectory(store: h.store, tenantID: SyncFixtures.tenant, owner: nil).myRetentions().first)
        #expect(item.syncStatus == .conflict && item.errorCode == "RETENTION_NOT_ALLOWED")
    }

    @Test func duplicateOfAConflictingRetentionStaysAConflict() {
        for code in ["RETENTION_NOT_ALLOWED", "DUPLICATE_RETENTION"] {
            let result = OperationResultDTO(id: UUID(), status: .duplicate, error: .object(["code": .string(code)]))
            #expect(PushOutcomeApplier.classify(result) == .conflict(code: code))
        }
    }

    @Test func serverStatusReplacesTheSyncStateOnceKnown() throws {
        let h = try SyncHarness()
        try AccountabilityTests.supported(h.store, Self.withRetention)
        let clientID = UUID(), serverID = UUID(), other = UUID()
        _ = try h.recorder.requestRetention(amountText: "100", currency: "TZS", reason: "Fuel", reasonID: nil, staffMemberID: nil,
                                            validUntil: nil, clientID: clientID)
        func retention(_ id: UUID, client: UUID?, status: String, at: String) -> [String: Any] {
            ["id": id.lowercased, "client_id": client.map { $0.lowercased as Any } ?? NSNull(), "staff_member_id": UUID().lowercased,
             "amount": "100", "currency": "TZS", "reason": "Fuel", "valid_until": NSNull(), "status": status,
             "created_by": NSNull(), "created_at": at, "decided_by": NSNull(), "decided_at": NSNull(),
             "decision_note": "Ok for one day", "decided_by_name": "Owner One"]
        }
        let doc: [String: Any] = ["value": [retention(serverID, client: clientID, status: "APPROVED", at: "2026-10-24T09:00:00Z"),
                                            retention(other, client: nil, status: "REJECTED", at: "2026-10-20T09:00:00Z")],
                                  "forbidden": false, "fetched_at": "2026-10-24T10:00:00Z"]
        try h.store.syncState.setValue(String(decoding: try JSONSerialization.data(withJSONObject: doc), as: UTF8.self),
                                       for: AccountabilityKey.retentions, tenant: SyncFixtures.tenant.uuidString.lowercased())
        let items = AccountabilityDirectory(store: h.store, tenantID: SyncFixtures.tenant, owner: nil).myRetentions()
        #expect(items.count == 2)
        let mine = try #require(items.first { $0.matches(clientID) })
        #expect(mine.serverID == serverID && mine.status == "APPROVED" && mine.decidedByName == "Owner One")
        #expect(mine.matches(serverID))
        #expect(items.contains { $0.id == other && $0.status == "REJECTED" && $0.syncStatus == nil })
    }

    // MARK: - G5 exact records

    @Test func notificationTapsOpenTheExactRecord() throws {
        let id = UUID()
        func note(kind: String?, record: UUID?, entity: String?, target: UUID?) throws -> NotificationDTO {
            var data: [String: Any] = [:]
            if let kind { data["kind"] = kind }
            if let record { data["record_id"] = record.lowercased }
            var json: [String: Any] = [
                "id": UUID().lowercased, "type": "X", "category": "CASH", "severity": "INFO", "priority": "NORMAL", "title": "t",
                "body": "b", "created_at": "2026-10-24T08:00:00Z", "read_at": NSNull(), "tenant_id": NSNull(), "data": data]
            if let entity {
                json["target"] = ["entity": entity, "id": target.map { $0.lowercased as Any } ?? NSNull(), "path": NSNull()] as [String: Any]
            } else {
                json["target"] = NSNull()
            }
            return try AssetaJSON.decoder().decode(NotificationDTO.self, from: JSONSerialization.data(withJSONObject: json))
        }
        #expect(InboxLink.from(try note(kind: "CASH_TRANSFER", record: id, entity: nil, target: nil)) == .cashToAcknowledge(id, isFloat: false))
        #expect(InboxLink.from(try note(kind: "CASH_FLOAT", record: id, entity: "supervisor_cash_custody", target: UUID()))
            == .cashToAcknowledge(id, isFloat: true))
        #expect(InboxLink.from(try note(kind: "CASH_RETENTION", record: id, entity: nil, target: nil)) == .retention(id))
        #expect(InboxLink.from(try note(kind: "REMITTANCE_OVERDUE", record: id, entity: nil, target: nil)) == .money)
        // Older notifications: the target names the record.
        #expect(InboxLink.from(try note(kind: nil, record: nil, entity: "cash_retention", target: id)) == .retention(id))
        #expect(InboxLink.from(try note(kind: nil, record: nil, entity: "supervisor_cash_custody", target: id))
            == .cashToAcknowledge(id, isFloat: true))
        // Kinds the field app does not show fall back as before.
        #expect(InboxLink.from(try note(kind: "HOURS_DISCOUNT", record: id, entity: "job", target: id)) == .job(id))
        #expect(InboxLink.from(try note(kind: "UNKNOWN_KIND", record: id, entity: nil, target: nil)) == .none)
        #expect(InboxLink.from(try note(kind: "CASH_VARIANCE", record: id, entity: nil, target: nil)) == .none)

        // A push names the record directly.
        let push = try #require(RecordRef(pushPayload: ["kind": "CASH_RETENTION", "record_id": id.lowercased, "link": "/x"]))
        #expect(push == RecordRef(kind: .cashRetention, id: id) && InboxLink.from(record: push) == .retention(id))
        #expect(RecordRef(pushPayload: ["entity": "cash_transfer", "entity_id": id.lowercased]) == RecordRef(kind: .cashTransfer, id: id))
        #expect(RecordRef(pushPayload: ["kind": "CASH_RETENTION", "record_id": "not-a-uuid"]) == nil)
    }
}
