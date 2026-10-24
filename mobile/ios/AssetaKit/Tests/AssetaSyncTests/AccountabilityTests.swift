import AssetaCapture
import AssetaModel
import AssetaStore
@testable import AssetaSync
import Foundation
import Testing

/// Accountability field operations (customer hours, cash custody chain, engine hours), same rules as Android
/// `FieldAccess`, `AccountabilityRules` and `AccountabilityCapture`.
struct AccountabilityTests {
    static let all = ["SUPERVISOR_INBOX_V1", "OP_HOURS_PURCHASE", "OP_HOURS_TRANSFER_REQUEST", "OP_CASH_TRANSFER",
                      "METER_DAILY_READING", "OP_METER_BASELINE", "OP_METER_CORRECTION"]
    static let permissions: Set<String> = ["tenant.hours.purchase", "tenant.hours.transfer", "tenant.collection.record",
                                           "tenant.meter.capture"]
    static let hoursOn = CustomerHoursPolicyValues(enabled: true, walkInAllowed: true, transferRequiresApproval: true)
    static let cashOn = CashCustodyPolicyValues(recordersMayRecordForOthers: true, transferAckRequired: true,
                                                recorderReceiverCountsAsAck: true, floatAckRequired: true,
                                                remitFullBalance: true, retentionAllowed: true)

    static func supported(_ store: LocalStore, _ capabilities: [String] = all) throws {
        try store.syncState.setValue(capabilities.joined(separator: ","), for: SyncKey.capabilities,
                                     tenant: SyncFixtures.tenant.uuidString.lowercased())
    }

    // MARK: - Gating

    @Test func everyEntryNeedsCapabilityPermissionAndPolicy() {
        let full = FieldAccess(capabilities: Set(Self.all), permissions: Self.permissions, cash: Self.cashOn, hours: Self.hoursOn)
        #expect(full.sellHours && full.walkIn && full.requestHoursTransfer && full.transferCash && full.acknowledgeCash)
        #expect(full.recordForOthers && full.askToKeepCash && full.dailyReading && full.proposeBaseline && full.proposeCorrection)

        // Never synced: nothing that needs a capability.
        let unsynced = FieldAccess(capabilities: nil, permissions: Self.permissions, cash: Self.cashOn, hours: Self.hoursOn)
        #expect(!unsynced.sellHours && !unsynced.transferCash && !unsynced.dailyReading)
        #expect(unsynced.recordForOthers && unsynced.askToKeepCash) // policy + permission only

        // Unknown policy hides policy-gated options (today's screens unchanged).
        let noPolicy = FieldAccess(capabilities: Set(Self.all), permissions: Self.permissions)
        #expect(!noPolicy.sellHours && !noPolicy.requestHoursTransfer && !noPolicy.recordForOthers && !noPolicy.askToKeepCash)
        #expect(noPolicy.transferCash && noPolicy.dailyReading)

        // Policy off.
        let off = FieldAccess(capabilities: Set(Self.all), permissions: Self.permissions,
                              cash: CashCustodyPolicyValues(recordersMayRecordForOthers: false, transferAckRequired: false,
                                                            recorderReceiverCountsAsAck: false, floatAckRequired: false,
                                                            remitFullBalance: false, retentionAllowed: false),
                              hours: CustomerHoursPolicyValues(enabled: false, walkInAllowed: true, transferRequiresApproval: true))
        #expect(!off.sellHours && !off.walkIn && !off.requestHoursTransfer && !off.recordForOthers && !off.askToKeepCash)

        // Permission missing.
        let none = FieldAccess(capabilities: Set(Self.all), permissions: [], cash: Self.cashOn, hours: Self.hoursOn)
        #expect(!none.sellHours && !none.transferCash && !none.askToKeepCash && !none.dailyReading && !none.proposeCorrection)

        // Walk-in only when allowed.
        let noWalkIn = FieldAccess(capabilities: Set(Self.all), permissions: Self.permissions, cash: Self.cashOn,
                                   hours: CustomerHoursPolicyValues(enabled: true, walkInAllowed: false, transferRequiresApproval: false))
        #expect(noWalkIn.sellHours && !noWalkIn.walkIn)
    }

    @Test func policiesParseStrictly() throws {
        let complete = #"{"recorders_may_record_for_others":true,"transfer_ack_required":true,"recorder_receiver_counts_as_ack":false,"float_ack_required":true,"remit_full_balance":true,"retention_allowed":false,"remittance_cutoff_hour":null}"#
        let cash = try AssetaJSON.decoder().decode(CashCustodyPolicyValues.self, from: Data(complete.utf8))
        #expect(cash.recordersMayRecordForOthers && !cash.retentionAllowed)
        #expect(throws: (any Error).self) {
            try AssetaJSON.decoder().decode(CashCustodyPolicyValues.self, from: Data(#"{"transfer_ack_required":true}"#.utf8))
        }
        #expect(throws: (any Error).self) {
            try AssetaJSON.decoder().decode(CustomerHoursPolicyValues.self, from: Data(#"{"enabled":"yes"}"#.utf8))
        }
    }

    // MARK: - Rules

    @Test func hoursSaleRules() {
        var d = HoursSaleDraft()
        guard case let .failure(p) = AccountabilityRules.hoursSale(d, walkInAllowed: true) else { Issue.record("valid"); return }
        #expect(p.messages == [FieldAccountabilityTexts.hoursErrCustomer, FieldAccountabilityTexts.hoursErrMachine,
                               FieldAccountabilityTexts.hoursErrHours, FieldAccountabilityTexts.hoursErrAmount])
        d.walkIn = true
        d.walkInPhone = "12"
        d.machineID = UUID()
        d.hoursText = "5.555"
        d.method = "MOBILE_MONEY"
        d.amountText = "100"
        guard case let .failure(p2) = AccountabilityRules.hoursSale(d, walkInAllowed: false) else { Issue.record("valid"); return }
        #expect(p2.messages == [FieldAccountabilityTexts.hoursErrWalkInOff, FieldAccountabilityTexts.hoursErrWalkInName,
                                FieldAccountabilityTexts.hoursErrPhone, FieldAccountabilityTexts.hoursErrHours,
                                FieldAccountabilityTexts.hoursErrReference])
        d.walkInName = "  Asha  "
        d.walkInPhone = "0712 000 111"
        d.hoursText = "5.5"
        d.reference = " MM-778 "
        guard case let .success(v) = AccountabilityRules.hoursSale(d, walkInAllowed: true) else { Issue.record("invalid"); return }
        #expect(v.hours == Decimal(string: "5.5")! && v.amount == 100 && v.reference == "MM-778" && v.walkInName == "Asha")
        d.paidNow = false
        d.amountText = ""
        guard case let .success(unpaid) = AccountabilityRules.hoursSale(d, walkInAllowed: true) else { Issue.record("invalid"); return }
        #expect(unpaid.amount == nil && unpaid.reference == nil)
    }

    @Test func transferCashAckAndRetentionRules() {
        let a = UUID(), b = UUID()
        if case let .failure(p) = AccountabilityRules.hoursTransfer(purchaseID: a, fromMachineID: b, toMachineID: b, hoursText: "8",
                                                                     remaining: 7.5, reason: "ok", reasonCodeID: nil,
                                                                     reasonCodeRequired: true) {
            #expect(p.messages == [FieldAccountabilityTexts.transferErrSameMachine, "Only 7.5 h are left on this purchase.",
                                   FieldAccountabilityTexts.transferErrReason, FieldAccountabilityTexts.transferErrCategory])
        } else { Issue.record("valid") }
        if case let .failure(p) = AccountabilityRules.cashTransfer(fromID: a, toID: a, amountText: "0", currency: "tz",
                                                                    receiverIsMe: true, selfAck: true, receivedText: "", note: "") {
            #expect(p.messages == [FieldAccountabilityTexts.cashTransferErrSame, FieldAccountabilityTexts.cashTransferErrAmount,
                                   FieldAccountabilityTexts.currencyError, FieldAccountabilityTexts.cashTransferErrReceived])
        } else { Issue.record("valid") }
        guard case let .success(t) = AccountabilityRules.cashTransfer(fromID: a, toID: b, amountText: "50000", currency: "tzs",
                                                                      receiverIsMe: false, selfAck: true, receivedText: "",
                                                                      note: "  ") else { Issue.record("invalid"); return }
        #expect(t.amount == 50000 && t.currency == "TZS" && t.received == nil && t.note == nil)
        if case let .failure(p) = AccountabilityRules.acknowledgement(acknowledge: true, receivedText: "", note: "") {
            #expect(p.messages == [FieldAccountabilityTexts.ackErrReceived])
        } else { Issue.record("valid") }
        if case let .failure(p) = AccountabilityRules.acknowledgement(acknowledge: false, receivedText: "", note: " ") {
            #expect(p.messages == [FieldAccountabilityTexts.ackErrReason])
        } else { Issue.record("valid") }
        if case let .success(ack) = AccountabilityRules.acknowledgement(acknowledge: true, receivedText: "0", note: "") {
            #expect(ack.received == 0)
        } else { Issue.record("invalid") }
        if case let .failure(p) = AccountabilityRules.retention(amountText: "", currency: "TZS", reason: "x") {
            #expect(p.messages == [FieldAccountabilityTexts.retentionErrAmount, FieldAccountabilityTexts.retentionErrReason])
        } else { Issue.record("valid") }
        #expect(!AccountabilityRules.correctionReasonValid("too short"))
        #expect(AccountabilityRules.correctionReasonValid("Misread the last digit"))
    }

    @Test func walkInClientIDMatchesAndroidNameUUID() {
        // Java: UUID.nameUUIDFromBytes("walk-in:00000000-0000-4000-8000-000000000001".getBytes())
        let id = AccountabilityRules.walkInClientID(saleClientID: UUID(uuidString: "00000000-0000-4000-8000-000000000001")!)
        #expect(id.uuidString.lowercased() == "2fb7fce7-1381-37e1-8f43-e4006502575d")
    }

    // MARK: - Recorder

    @Test func operationsNeedTheServerCapability() throws {
        let h = try SyncHarness()
        #expect(h.recorder.unavailable(SyncCapability.hoursPurchase) == FieldAccountabilityTexts.needsRules)
        try Self.supported(h.store, ["SUPERVISOR_INBOX_V1"])
        #expect(h.recorder.unavailable(SyncCapability.cashTransfer) == FieldAccountabilityTexts.serverTooOld)
        #expect(throws: FieldRecorderError.notAllowed(FieldAccountabilityTexts.serverTooOld)) {
            try h.recorder.acknowledgeCash(targetID: UUID(), isFloat: false, acknowledge: true, receivedText: "1", note: "")
        }
    }

    @Test func hoursSaleWithEvidenceWaitsForUploadThenAcks() async throws {
        let h = try SyncHarness().withFinanceData()
        h.server.mutate { $0.capabilities = Self.all }
        let engine = h.engine()
        _ = try await engine.sync()
        let receipt = try h.evidence.store(Data((0..<1800).map { UInt8($0 % 199) }), fileExtension: "jpg", contentType: "image/jpeg")
        var draft = HoursSaleDraft()
        draft.walkIn = true
        draft.walkInName = "Asha Mussa"
        draft.machineID = SyncFixtures.machineID
        draft.hoursText = "10"
        draft.amountText = "250000"
        let holder = UUID(), clientID = UUID()
        let op = try h.recorder.recordHoursSale(draft, walkInAllowed: true, cashHolderID: holder, evidence: [receipt],
                                                receivedAt: h.clock.wallNow, clientID: clientID)
        #expect(op.opType == "HOURS_PURCHASE" && op.entityID == clientID)
        #expect(throws: FieldRecorderError.notAllowed(FieldAccountabilityTexts.alreadySaved)) {
            try h.recorder.recordHoursSale(draft, walkInAllowed: true, cashHolderID: nil, evidence: [], receivedAt: h.clock.wallNow,
                                           clientID: clientID)
        }
        // Not sendable before its evidence has uploaded.
        #expect(try h.store.outbox.readyToSend(tenantID: SyncFixtures.tenant, now: h.clock.wallNow, limit: 10).isEmpty)
        _ = try await engine.sync(force: true)
        #expect(try h.status(op.id) == .acked)
        let applied = try #require(h.server.read { $0.appliedPayloads[op.id] })
        let session = try #require(h.server.read { $0.blobs.keys.first })
        #expect(applied["evidence_upload_ids"] as? [String] == [session.lowercased])
        #expect(applied["client_id"] as? String == clientID.lowercased)
        #expect(applied["hours"] as? String == "10")
        #expect(applied["customer_id"] == nil)
        let walkIn = try #require(applied["walk_in"] as? [String: Any])
        #expect(walkIn["name"] as? String == "Asha Mussa"
                && walkIn["client_id"] as? String == AccountabilityRules.walkInClientID(saleClientID: clientID).lowercased)
        let payment = try #require(applied["payment"] as? [String: Any])
        #expect(payment["method"] as? String == "CASH" && payment["amount"] as? String == "250000")
        #expect(payment["staff_member_id"] as? String == holder.lowercased)
        #expect(h.server.read { $0.blobs.values.first?.purpose } == "PAYMENT_EVIDENCE")
    }

    @Test func transferAcknowledgementAndCashTransferPayloads() throws {
        let h = try SyncHarness()
        try Self.supported(h.store)
        let me = UUID(), other = UUID(), transfer = UUID(), entry = UUID()
        let cash = try h.recorder.recordCashTransfer(fromStaffID: nil, toStaffID: other, myStaffID: me, amountText: "40000",
                                                     currency: "tzs", selfAck: true, receivedText: "", note: " Fuel money ",
                                                     transferredAt: h.clock.wallNow)
        let p = try JSONValue.parse(cash.payloadJSON)
        #expect(p["to_staff_id"]?.stringValue == other.lowercased && p["from_staff_id"] == nil)
        #expect(p["amount"]?.stringValue == "40000" && p["currency"]?.stringValue == "TZS" && p["note"]?.stringValue == "Fuel money")
        #expect(p["amount_received"] == nil)
        // I receive it and the tenant counts that as my acknowledgement: the received amount is required.
        #expect(throws: FieldRecorderError.invalid(FieldAccountabilityTexts.cashTransferErrReceived)) {
            try h.recorder.recordCashTransfer(fromStaffID: other, toStaffID: me, myStaffID: me, amountText: "100", currency: "TZS",
                                              selfAck: true, receivedText: "", note: "", transferredAt: h.clock.wallNow)
        }
        let received = try h.recorder.recordCashTransfer(fromStaffID: other, toStaffID: me, myStaffID: me, amountText: "100",
                                                         currency: "TZS", selfAck: true, receivedText: "90", note: "",
                                                         transferredAt: h.clock.wallNow)
        #expect(try JSONValue.parse(received.payloadJSON)["amount_received"]?.stringValue == "90")

        let ack = try h.recorder.acknowledgeCash(targetID: transfer, isFloat: false, acknowledge: true, receivedText: "39000",
                                                 note: "")
        let a = try JSONValue.parse(ack.payloadJSON)
        #expect(ack.opType == "CASH_TRANSFER_ACKNOWLEDGEMENT" && a["transfer_id"]?.stringValue == transfer.lowercased)
        #expect(a["acknowledged"]?.boolValue == true && a["amount_received"]?.stringValue == "39000" && a["entry_id"] == nil)
        #expect(throws: FieldRecorderError.notAllowed(FieldAccountabilityTexts.alreadySaved)) {
            try h.recorder.acknowledgeCash(targetID: transfer, isFloat: false, acknowledge: false, receivedText: "", note: "Short")
        }
        let dispute = try h.recorder.acknowledgeCash(targetID: entry, isFloat: true, acknowledge: false, receivedText: "",
                                                     note: "Envelope was empty")
        let d = try JSONValue.parse(dispute.payloadJSON)
        #expect(dispute.opType == "CASH_FLOAT_ACKNOWLEDGEMENT" && d["entry_id"]?.stringValue == entry.lowercased)
        #expect(d["acknowledged"]?.boolValue == false && d["note"]?.stringValue == "Envelope was empty" && d["amount_received"] == nil)
    }

    @Test func dailyBaselineAndCorrectionThroughTheEngine() async throws {
        let h = try SyncHarness()
        h.server.mutate { $0.capabilities = Self.all }
        let engine = h.engine()
        _ = try await engine.sync()
        let gps = GpsPayload.fix(latitude: -6.8, longitude: 39.3, accuracyM: 7, capturedAt: h.clock.wallNow)
        let photo = { try h.evidence.store(Data((0..<1500).map { UInt8($0 % 97) }), fileExtension: "jpg", contentType: "image/jpeg") }
        let daily = try h.recorder.recordDailyReading(machineID: SyncFixtures.machineID, mode: .manual, reading: "1300.0", ocr: nil,
                                                      photo: try photo(), gps: gps, capturedAt: h.clock.wallNow,
                                                      snapshot: SyncFixtures.meterSnapshot)
        let baselineID = UUID()
        let baseline = try h.recorder.proposeBaseline(machineID: SyncFixtures.machineID, reading: "1200.0", photo: try photo(),
                                                      gps: gps, note: "  New hour meter  ", capturedAt: h.clock.wallNow,
                                                      baselineID: baselineID)
        #expect(baseline.id == baselineID)
        _ = try await engine.sync(force: true)
        #expect(try h.status(daily.id) == .acked && h.status(baseline.id) == .acked)
        let d = try #require(h.server.read { $0.appliedPayloads[daily.id] })
        #expect(d["kind"] as? String == "DAILY" && d["job_id"] == nil && d["machine_id"] as? String == SyncFixtures.machineID.lowercased)
        #expect(d["photo_attachment_id"] as? String != nil)
        let b = try #require(h.server.read { $0.appliedPayloads[baseline.id] })
        #expect(b["id"] as? String == baselineID.lowercased && b["note"] as? String == "New hour meter")
        #expect(b["photo_attachment_id"] as? String != nil && b["reading"] as? String == "1200.0")

        // A correction of the synced DAILY reading (the server copy says it still counts).
        let server: [String: Any] = [
            "id": daily.entityID.lowercased, "job_id": NSNull(), "machine_id": SyncFixtures.machineID.lowercased, "kind": "DAILY",
            "capture_mode": "MANUAL", "reading": "1300.0", "state": "ACCEPTED", "gps_status": "FIX", "latitude": NSNull(),
            "longitude": NSNull(), "accuracy_m": NSNull(), "location_captured_at": NSNull(), "photo_attachment_id": NSNull(),
            "photo_sha256": NSNull(), "ocr_value": NSNull(), "ocr_confidence": NSNull(), "manually_corrected": false,
            "policy_version": "p", "supersedes_id": NSNull(), "tracker_comparison": NSNull(),
            "captured_at": AssetaJSON.formatInstant(h.clock.wallNow), "received_at": AssetaJSON.formatInstant(h.clock.wallNow),
            "sync_revision": 9, "review_status": "NONE", "findings": []]
        let dto = try AssetaJSON.decoder().decode(SyncMeterCaptureDTO.self, from: JSONSerialization.data(withJSONObject: server))
        let reading = ReadingItem(id: dto.id, jobID: nil, machineID: dto.machineID, kind: "DAILY", reading: "1300.0",
                                  captureMode: "MANUAL", at: h.clock.wallNow, status: .accepted, server: dto, op: nil,
                                  localPayload: nil)
        #expect(throws: FieldRecorderError.invalid(FieldAccountabilityTexts.meterErrCorrectionReason)) {
            try h.recorder.proposeCorrection(of: reading, machineID: SyncFixtures.machineID, mode: .manual, value: "1310.0", ocr: nil,
                                             photo: nil, gps: gps, capturedAt: h.clock.wallNow, reason: "typo",
                                             snapshot: SyncFixtures.meterSnapshot)
        }
        let correction = try h.recorder.proposeCorrection(of: reading, machineID: SyncFixtures.machineID, mode: .manual,
                                                          value: "1310.0", ocr: nil, photo: try photo(), gps: gps,
                                                          capturedAt: h.clock.wallNow, reason: "Misread the tens digit",
                                                          snapshot: SyncFixtures.meterSnapshot)
        _ = try await engine.sync(force: true)
        #expect(try h.status(correction.id) == .acked)
        let c = try #require(h.server.read { $0.appliedPayloads[correction.id] })
        let replacement = try #require(c["replacement"] as? [String: Any])
        #expect(c["superseded_capture_id"] as? String == daily.entityID.lowercased && c["reason"] as? String == "Misread the tens digit")
        #expect(replacement["kind"] as? String == "DAILY" && replacement["job_id"] == nil)
        #expect(replacement["photo_attachment_id"] as? String != nil && c["photo_attachment_id"] == nil)
        #expect(FieldRecorder.correctionBlocked(ReadingItem(id: UUID(), jobID: nil, machineID: nil, kind: "DAILY", reading: "1",
                                                            captureMode: "MANUAL", at: .now, status: .notSynced, server: nil,
                                                            op: nil, localPayload: nil)) == FieldAccountabilityTexts.meterCorrectionNotSynced)
    }
}
