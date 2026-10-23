import AssetaModel
import Foundation
import Testing

/// Sync inbox DTOs against `contracts/openapi.json` (read in place), like Android `SyncContractTest`:
/// a contract-shaped sample decodes; re-encoding it writes only properties the contract defines and
/// every required one (unless null), and array properties agree on their item kind (objects vs values).
struct SyncContractTests {
    static var repositoryRoot: URL {
        URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
    }

    nonisolated(unsafe) static let schemas: [String: Any] = {
        let url = repositoryRoot.appendingPathComponent("contracts/openapi.json")
        guard let data = try? Data(contentsOf: url),
              let root = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let components = root["components"] as? [String: Any],
              let schemas = components["schemas"] as? [String: Any] else { return [:] }
        return schemas
    }()

    static let ids = (0..<12).map { _ in UUID().uuidString.lowercased() }

    nonisolated(unsafe) static let finding: [String: Any] = [
        "id": ids[0], "exception_type": "SOMETHING_NEW", "severity": "HIGH", "blocking": true, "status": "OPEN", "machine_id": ids[1],
        "job_id": ids[2], "meter_capture_id": ids[3], "policy_version": NSNull(), "review_note": NSNull(), "reviewed_at": NSNull(),
        "created_at": "2026-10-23T08:00:00Z", "evidence": ["delta": "12"]]
    nonisolated(unsafe) static let capture: [String: Any] = [
        "id": ids[3], "job_id": ids[2], "machine_id": ids[1], "kind": "OPENING", "capture_mode": "AUTOMATIC", "reading": "1234.5",
        "state": "PROVISIONAL", "gps_status": "FIX", "latitude": -6.8, "longitude": 39.2, "accuracy_m": 12.0,
        "location_captured_at": "2026-10-23T07:59:00Z", "photo_attachment_id": ids[4], "photo_sha256": "ab", "ocr_value": "1234.5",
        "ocr_confidence": 0.91, "manually_corrected": false, "policy_version": "p1", "supersedes_id": NSNull(),
        "tracker_comparison": NSNull(), "captured_at": "2026-10-23T07:59:30Z", "received_at": "2026-10-23T08:00:00Z",
        "sync_revision": 42, "review_status": "PENDING_REVIEW", "findings": [finding]]
    nonisolated(unsafe) static let reset: [String: Any] = [
        "id": ids[5], "machine_id": ids[1], "old_reading": "9999.9", "new_reading": "0.0", "effective_at": "2026-10-23T08:00:00Z",
        "reason": "Meter replaced by workshop", "status": "PENDING", "evidence_attachment_id": ids[4], "requested_by": NSNull(),
        "decided_by": NSNull(), "decided_at": NSNull(), "created_at": "2026-10-23T08:00:00Z", "sync_revision": 3]
    nonisolated(unsafe) static let activity: [String: Any] = [
        "id": ids[6], "job_id": ids[2], "client_id": ids[7], "activity_type": "WORK", "started_at": "2026-10-23T06:00:00Z",
        "ended_at": "2026-10-23T08:00:00Z", "duration_minutes": 120, "billable": true, "note": NSNull(), "recorded_by": NSNull(),
        "received_at": "2026-10-23T08:01:00Z", "sync_revision": 4]
    nonisolated(unsafe) static let acknowledgement: [String: Any] = [
        "id": ids[8], "job_id": ids[2], "client_id": ids[9], "method": "SIGNATURE", "signer_name": "Asha",
        "signer_phone": NSNull(), "acknowledged_hours": "8.50", "signature_attachment_id": ids[4],
        "captured_at": "2026-10-23T09:00:00Z", "recorded_by": NSNull(), "received_at": "2026-10-23T09:01:00Z", "sync_revision": 5]
    nonisolated(unsafe) static let expense: [String: Any] = [
        "id": ids[10], "client_id": ids[11], "category_id": ids[0], "description": "Diesel", "supplier": NSNull(),
        "amount": "25000.00", "currency": "TZS", "paid_from": "CASH_CUSTODY", "status": "REJECTED", "decision_note": "No receipt",
        "decided_at": "2026-10-23T09:00:00Z", "decided_by": NSNull(), "incurred_at": "2026-10-23T07:00:00Z",
        "submitted_at": "2026-10-23T07:10:00Z", "submitted_by": NSNull(), "custodian_staff_id": NSNull(), "job_id": NSNull(),
        "machine_id": NSNull(), "gps_status": "FIX", "gps_accuracy_m": 5.0, "latitude": 1.0, "longitude": 2.0,
        "policy_version": "p", "receipt_required": true, "source": "SYNC", "receipt_attachment_ids": [ids[4]],
        "approval_request_id": ids[5], "sync_revision": 7]
    nonisolated(unsafe) static let fuel: [String: Any] = [
        "id": ids[6], "client_id": ids[7], "event_type": "ISSUE", "litres": "120.000", "unit_price": NSNull(),
        "attributed_cost": "0.00", "currency": "TZS", "machine_id": ids[1], "job_id": ids[2], "expense_id": NSNull(),
        "meter_reading": NSNull(), "supplier": NSNull(), "note": NSNull(), "occurred_at": "2026-10-23T07:00:00Z",
        "recorded_by": NSNull(), "source": "SYNC", "sync_revision": 8]
    nonisolated(unsafe) static let allocation: [String: Any] = [
        "id": ids[0], "invoice_id": ids[1], "amount": "10", "created_at": "2026-10-23T10:00:00Z", "released_at": NSNull(),
        "release_reason": NSNull()]
    nonisolated(unsafe) static let collection: [String: Any] = [
        "id": ids[2], "client_id": ids[3], "customer_id": ids[4], "amount": "10", "currency": "TZS", "method": "CASH",
        "status": "VERIFIED", "decision_note": NSNull(), "reference": NSNull(), "note": NSNull(), "received_at": "2026-10-23T07:00:00Z",
        "received_by_staff_id": ids[5], "recorded_at": "2026-10-23T07:00:00Z", "recorded_by": NSNull(),
        "verified_at": "2026-10-23T10:00:00Z", "verified_by": NSNull(), "source": "SYNC", "allocations": [allocation],
        "sync_revision": 3]
    nonisolated(unsafe) static let handover: [String: Any] = [
        "id": ids[6], "client_id": NSNull(), "staff_member_id": ids[5], "amount": "100000.0000", "currency": "TZS",
        "status": "REJECTED", "decision_note": "Amount does not match", "reference": "R-1", "note": NSNull(),
        "handed_at": "2026-10-23T07:00:00Z", "recorded_at": "2026-10-23T07:01:00Z", "recorded_by": NSNull(),
        "verified_at": NSNull(), "verified_by": NSNull(), "source": "SYNC", "sync_revision": 21]
    nonisolated(unsafe) static let day: [String: Any] = [
        "day": "2026-10-23", "opening": "0", "floats_issued": "100000", "collections": "50000", "approved_spending": "20000",
        "verified_handovers": "30000", "outstanding": "100000", "claimed_unverified_handovers": "10000", "pending_spending": "5000",
        "unverified_collections": "0", "outstanding_if_claims_verified": "90000"]
    nonisolated(unsafe) static let reconciliation: [String: Any] = ["staff_member_id": ids[5], "currency": "TZS", "timezone": "Africa/Dar_es_Salaam",
                                                "days": [day]]

    static func roundTrip<T: Codable>(_ type: T.Type, _ sample: [String: Any]) throws -> [String: Any] {
        let value = try AssetaJSON.decoder().decode(T.self, from: try JSONSerialization.data(withJSONObject: sample))
        let encoded = try AssetaJSON.encoder().encode(value)
        return try #require(try JSONSerialization.jsonObject(with: encoded) as? [String: Any])
    }

    static func check(_ schemaName: String, encoded: [String: Any], sample: [String: Any]) throws {
        let schema = try #require(schemas[schemaName] as? [String: Any], "schema \(schemaName) missing from contract")
        let properties = schema["properties"] as? [String: [String: Any]] ?? [:]
        let required = Set(schema["required"] as? [String] ?? [])
        for key in required { #expect(sample[key] != nil, "\(schemaName) sample lacks required \(key)") }
        for key in encoded.keys { #expect(properties[key] != nil, "\(schemaName) has no property '\(key)'") }
        for key in required where !(sample[key] is NSNull) {
            #expect(encoded[key] != nil, "\(schemaName).\(key) required by the contract but not mapped")
        }
        for (key, value) in encoded {
            guard let array = value as? [Any], let first = array.first, let property = properties[key],
                  let items = arrayItems(property) else { continue }
            let target = (items["$ref"] as? String).flatMap { schemas[String($0.split(separator: "/").last ?? "")] as? [String: Any] }
                ?? items
            let objectItems = target["type"] as? String == "object" || target["properties"] != nil
            #expect(objectItems == (first is [String: Any]), "\(schemaName).\(key) item kind")
        }
    }

    static func arrayItems(_ property: [String: Any]) -> [String: Any]? {
        if property["type"] as? String == "array" { return property["items"] as? [String: Any] }
        return (property["anyOf"] as? [[String: Any]])?.lazy.compactMap(arrayItems).first
    }

    @Test func contractIsAvailable() { #expect(Self.schemas["SyncData"] != nil, "contracts/openapi.json not found") }

    @Test func inboxDTOsMatchTheContract() throws {
        try Self.check("ExceptionDto", encoded: Self.roundTrip(FindingDTO.self, Self.finding), sample: Self.finding)
        try Self.check("SyncMeterCaptureDto", encoded: Self.roundTrip(SyncMeterCaptureDTO.self, Self.capture), sample: Self.capture)
        try Self.check("SyncMeterResetDto", encoded: Self.roundTrip(SyncMeterResetDTO.self, Self.reset), sample: Self.reset)
        try Self.check("SyncJobActivityDto", encoded: Self.roundTrip(SyncJobActivityDTO.self, Self.activity), sample: Self.activity)
        try Self.check("SyncAcknowledgementDto", encoded: Self.roundTrip(SyncAcknowledgementDTO.self, Self.acknowledgement),
                       sample: Self.acknowledgement)
        try Self.check("SyncExpenseDto", encoded: Self.roundTrip(SyncExpenseDTO.self, Self.expense), sample: Self.expense)
        try Self.check("SyncFuelEventDto", encoded: Self.roundTrip(SyncFuelEventDTO.self, Self.fuel), sample: Self.fuel)
        try Self.check("HireAllocationDto", encoded: Self.roundTrip(HireAllocationDTO.self, Self.allocation), sample: Self.allocation)
        try Self.check("SyncCashCollectionDto", encoded: Self.roundTrip(SyncCashCollectionDTO.self, Self.collection),
                       sample: Self.collection)
        try Self.check("SyncCashHandoverDto", encoded: Self.roundTrip(SyncCashHandoverDTO.self, Self.handover), sample: Self.handover)
        try Self.check("CashReconciliationDto", encoded: Self.roundTrip(CashReconciliationDTO.self, Self.reconciliation),
                       sample: Self.reconciliation)
        try Self.check("CashReconciliationDayDto", encoded: Self.roundTrip(CashReconciliationDayDTO.self, Self.day), sample: Self.day)
    }

    @Test func syncDataListsAndCapabilitiesMatchTheContract() throws {
        let data: [String: Any] = ["jobs": [], "my_meter_captures": [Self.capture], "my_expenses": [Self.expense],
                                   "my_cash_collections": [Self.collection]]
        let encoded = try Self.roundTrip(SyncData.self, data)
        try Self.check("SyncData", encoded: encoded, sample: data)
        let changes: [String: Any] = ["capabilities": ["SUPERVISOR_INBOX_V1", "OP_METER_RESET_REQUEST"],
                                      "server_time": "2026-10-23T08:00:00Z", "cursor": 9, "has_more": true, "data": data,
                                      "policy_snapshots": []]
        let dto = try AssetaJSON.decoder().decode(ChangesDTO.self, from: try JSONSerialization.data(withJSONObject: changes))
        #expect(dto.capabilities?.contains(SyncCapability.supervisorInbox) == true)
        #expect(dto.data.inbox[.meterCaptures]?.count == 1)
        #expect(dto.data.inbox[.fuelEvents] == nil)
        try Self.check("ChangesDto", encoded: Self.roundTrip(ChangesDTO.self, changes), sample: changes)
    }

    @Test func olderServerWithoutInboxListsLeavesThemAbsent() throws {
        let changes: [String: Any] = ["server_time": "2026-10-23T08:00:00Z", "cursor": 5, "has_more": false, "data": [:],
                                      "policy_snapshots": []]
        let dto = try AssetaJSON.decoder().decode(ChangesDTO.self, from: try JSONSerialization.data(withJSONObject: changes))
        #expect(dto.capabilities == nil)
        #expect(!dto.data.hasInbox)
    }

    @Test func captureKeepsFindingsAndUnknownValues() throws {
        let dto = try AssetaJSON.decoder().decode(SyncMeterCaptureDTO.self,
                                                  from: try JSONSerialization.data(withJSONObject: Self.capture))
        #expect(dto.reviewStatus == "PENDING_REVIEW")
        #expect(dto.findings.first?.exceptionType == "SOMETHING_NEW")
        #expect(dto.findings.first?.blocking == true)
        #expect(dto.syncRevision == 42)
        let expense = try AssetaJSON.decoder().decode(SyncExpenseDTO.self, from: try JSONSerialization.data(withJSONObject: Self.expense))
        #expect(expense.decisionNote == "No receipt" && expense.receiptAttachmentIDs.count == 1)
    }
}
