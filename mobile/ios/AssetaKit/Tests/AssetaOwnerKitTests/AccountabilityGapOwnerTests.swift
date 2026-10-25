@testable import AssetaOwnerKit
import AssetaModel
import AssetaNetwork
import Foundation
import Testing

/// DEC-030 gap pass in the Owner app: capabilities switched off (G1), names beside ids (G2), the remittance cut-off
/// (G4) and exact-record links (G5). Same rules and wording as Android.
struct AccountabilityGapOwnerTests {
    typealias S = AccountabilityOwnerTests
    static let custodian = "33333333-aaaa-4000-8000-000000000003"

    static let overdue = """
    {"id":"\(S.id(70))","staff_member_id":"\(custodian)","staff_member_name":"Juma Field","local_day":"2026-10-24","cutoff_hour":7,
     "amounts":[{"currency":"TZS","amount":"150000"},{"currency":"USD","amount":"20"}],"flagged_at":"2026-10-24T04:05:00Z",
     "policy_version":"c3"}
    """

    static let transfer = """
    {"id":"\(S.id(71))","client_id":null,"from_staff_id":"\(custodian)","to_staff_id":"\(S.other)","amount_declared":"40000",
     "currency":"TZS","transferred_at":"2026-10-24T08:00:00Z","note":"Fuel money","status":"PENDING_ACKNOWLEDGEMENT",
     "source":"SYNC","recorded_by":"\(S.me)","recorded_at":"2026-10-24T08:01:00Z","amount_received":null,"ack_method":null,
     "acknowledged_by":null,"acknowledged_at":null,"ack_note":null,"variance_id":null,"from_staff_name":"Juma Field",
     "to_staff_name":null,"recorded_by_name":"Owner One","acknowledged_by_name":null}
    """

    // MARK: - G1

    @Test func customerHoursOffHidesItsApprovalsAndTiles() throws {
        let permissions = ["tenant.hours.read", "tenant.meter.read", "tenant.finance.read", "tenant.accountability.read"]
        let on = OwnerFeatures(permissions: permissions)
        #expect(on.customerHours && on.decisionKinds.contains(.discount) && on.decisionKinds.contains(.cancellation))
        let off = OwnerFeatures(permissions: permissions, disabledCapabilities: [TenantCapability.customerHours])
        #expect(!off.customerHours)
        #expect(off.decisionKinds == [.baseline, .classification, .correction, .writeOff, .retention, .adjustment])
        #expect(!off.allows(.decision(.discount, UUID())) && off.allows(.decision(.retention, UUID())))
        let tenant = TenantMembership(tenantID: UUID(), name: "Acme", status: .active, accessState: .full, permissions: permissions,
                                      menus: [], disabledCapabilities: ["CUSTOMER_HOURS"])
        #expect(OwnerFeatures(tenant) == off)

        let summary = try AssetaJSON.decoder().decode(AccountabilitySummaryDTO.self, from: Data(S.summary.utf8))
        let all = AccountabilityDashboard.tiles(summary).map(\.id)
        #expect(all.contains("customer_hours") && all.contains("hours_awaiting_activation"))
        let hidden = AccountabilityDashboard.tiles(summary, customerHours: false).map(\.id)
        #expect(!hidden.contains("customer_hours") && !hidden.contains("hours_awaiting_activation") && hidden.contains("engine_hours"))
    }

    // MARK: - G2

    @Test func decisionsShowNamesAndFallBackToShortIDs() throws {
        let named = """
        {"id":"\(S.id(3))","client_id":null,"purchase_id":"\(S.id(92))","from_machine_id":"\(S.machine)","to_machine_id":"\(S.id(93))",
         "hours":"12.5","reason":"Machine broke down","reason_code_id":null,"status":"PENDING","requested_by":"\(S.other)",
         "requested_at":"2026-10-24T08:00:00Z","decided_by":null,"decided_at":null,"decision_note":null,
         "customer_name":"Mbeya Builders","purchase_number":"HP-2026-00012","from_machine_name":"EX-07 · CAT 320",
         "to_machine_name":"EX-09 · CAT 330","requested_by_name":"Juma Field","decided_by_name":null}
        """
        #expect(try Contract.missingRequired(schema: "TransferDto", json: named) == [])
        let t = try #require(PendingDecision.from(try JSONValue.parse(named), kind: .hoursTransfer))
        #expect(t.fields.map(\.label) == ["Customer", "Purchase", "Hours", "From machine", "To machine", "Requested by"])
        #expect(t.fields.map(\.value) == ["Mbeya Builders", "HP-2026-00012", "12.5", "EX-07 · CAT 320", "EX-09 · CAT 330", "Juma Field"])
        #expect(t.proposedByName == "Juma Field")

        // Retention: custodian and requester by name; the decider once decided.
        let retention = """
        {"id":"\(S.id(9))","client_id":"\(S.id(66))","staff_member_id":"\(Self.custodian)","staff_member_name":"Juma Field",
         "amount":"20000","currency":"TZS","reason_id":null,"reason":"Fuel","valid_until":null,"status":"APPROVED",
         "created_by":"\(S.other)","created_by_name":null,"created_at":"2026-10-24T08:00:00Z","decided_by":"\(S.me)",
         "decided_by_name":"Owner One","decided_at":"2026-10-24T09:00:00Z","decision_note":"One day only"}
        """
        #expect(try Contract.missingRequired(schema: "CashRetentionDto", json: retention) == [])
        let r = try #require(PendingDecision.from(try JSONValue.parse(retention), kind: .retention))
        #expect(!r.isPending)
        #expect(r.fields.first == DecisionField(label: "Cash held by", value: "Juma Field"))
        #expect(r.fields.contains(DecisionField(label: "Requested by", value: "22222222")))
        #expect(r.fields.contains(DecisionField(label: "Decided by", value: "Owner One")))
        #expect(r.fields.contains(DecisionField(label: "Decision note", value: "One day only")))
        #expect(OwnerAccountabilityTexts.approvalsProposedBy("24 Oct 2026, 08:00", "Juma Field") == "Proposed 24 Oct 2026, 08:00 by Juma Field")

        // Handover rows: the server's custodian name wins over the cash-summary lookup.
        let json = RemoteBossTests.handover().replacingOccurrences(of: "\"decision_note\":null",
                                                                    with: "\"decision_note\":null,\"staff_member_name\":\"Asha Mrema\"")
        let h = try AssetaJSON.decoder().decode(CashHandoverDTO.self, from: Data(json.utf8))
        #expect(HandoverText.title(h, supervisor: "Old name", money: { _, _ in "TZS 1" }) == "Asha Mrema handed over TZS 1")
    }

    // MARK: - G4

    @Test func cashTileShowsOverdueRemittancesOnlyWithACutoff() throws {
        var summary = try AssetaJSON.decoder().decode(AccountabilitySummaryDTO.self, from: Data(S.summary.utf8))
        #expect(summary.cash?.remittancesOverdueToday == nil)
        #expect(AccountabilityDashboard.tiles(summary).first { $0.id == "cash" }?.rows.contains { $0.label == "Remittances overdue today" } == false)

        let withCutoff = S.summary.replacingOccurrences(of: "\"partial_remittances_in_window\":1",
                                                        with: "\"partial_remittances_in_window\":1,\"remittance_cutoff_hour\":7,\"remittances_overdue_today\":2")
        #expect(try Contract.missingRequired(schema: "AccountabilitySummaryDto", json: withCutoff) == [])
        summary = try AssetaJSON.decoder().decode(AccountabilitySummaryDTO.self, from: Data(withCutoff.utf8))
        let row = try #require(AccountabilityDashboard.tiles(summary).first { $0.id == "cash" }?.rows.first { $0.label == "Remittances overdue today" })
        #expect(row.value == "2" && row.detail == "Cut-off 07:00" && row.route == .overdueRemittances)
    }

    @Test func overdueRemittanceDecodesAndReads() throws {
        #expect(try Contract.missingRequired(schema: "RemittanceOverdueDto", json: Self.overdue) == [])
        let o = try AssetaJSON.decoder().decode(RemittanceOverdueDTO.self, from: Data(Self.overdue.utf8))
        let row = CashRecordPresentation.overdueRow(o)
        #expect(row.title == "Juma Field" && row.line == "Still held after the 07:00 cut-off on 2026-10-24.")
        #expect(row.amounts.contains("150,000") && row.amounts.contains("\n"))
        let fields = CashRecordPresentation.overdue(o, timeZone: TimeZone(identifier: "UTC")!)
        #expect(fields.map(\.label) == ["Cash held by", "Day", "Cut-off", "Not remitted", "Flagged"])
        #expect(fields[2].value == "07:00" && fields[4].value == "24 Oct 2026, 04:05")
        // Paths and query of the contract.
        let list = OwnerAPI.remittanceOverdue(day: "2026-10-24")
        #expect(list.path == "/api/v1/tenant/cash/remittance-overdue")
        #expect(list.queryItems.contains(URLQueryItem(name: "day_from", value: "2026-10-24"))
            && list.queryItems.contains(URLQueryItem(name: "day_to", value: "2026-10-24")))
        let paths = try #require(try Contract.root()["paths"] as? [String: Any])
        for request in [OwnerAPI.remittanceOverdue(UUID()).path, OwnerAPI.cashTransfer(UUID()).path, OwnerAPI.cashFloat(UUID()).path,
                        OwnerAPI.cashHandover(UUID()).path] + DecisionKind.allCases.map({ OwnerAPI.decision($0, id: UUID()).path }) {
            let template = request.replacingOccurrences(of: #"[0-9a-f-]{36}$"#, with: "{id}", options: .regularExpression)
            #expect(paths.keys.contains { $0.replacingOccurrences(of: #"\{[a-z_]+\}"#, with: "{id}", options: .regularExpression) == template },
                    "\(template)")
        }
        #expect(CashRecordPresentation.localDay(Date(timeIntervalSince1970: 1_792_000_000), timeZone: TimeZone(identifier: "UTC")!)
            == "2026-10-14")
    }

    @Test func cashTransferRecordShowsNames() throws {
        #expect(try Contract.missingRequired(schema: "CashTransferDto", json: Self.transfer) == [])
        let t = try AssetaJSON.decoder().decode(CashTransferDTO.self, from: Data(Self.transfer.utf8))
        let fields = CashRecordPresentation.transfer(t, timeZone: TimeZone(identifier: "UTC")!)
        #expect(fields.first == DecisionField(label: "From", value: "Juma Field"))
        #expect(fields[1] == DecisionField(label: "To", value: "22222222"))
        #expect(fields.contains(DecisionField(label: "Recorded by", value: "Owner One")))
        #expect(!fields.contains { $0.label == "Acknowledged by" })
    }

    // MARK: - G5

    @Test func everyRecordKindOpensItsScreen() throws {
        let rid = UUID(), r = rid.uuidString.lowercased()
        let expected: [String: OwnerRoute] = [
            "CASH_TRANSFER": .cashTransfer(rid), "CASH_FLOAT": .cashFloat(rid), "CASH_VARIANCE": .decision(.writeOff, rid),
            "CASH_RETENTION": .decision(.retention, rid), "CUSTODY_ADJUSTMENT": .decision(.adjustment, rid),
            "CASH_REMITTANCE": .handover(rid), "REMITTANCE_OVERDUE": .overdueRemittance(rid),
            "HOURS_DISCOUNT": .decision(.discount, rid), "HOURS_CREDIT": .decision(.credit, rid),
            "HOURS_TRANSFER": .decision(.hoursTransfer, rid), "HOURS_CANCELLATION": .decision(.cancellation, rid),
            "METER_BASELINE": .decision(.baseline, rid), "METER_CORRECTION": .decision(.correction, rid),
            "ENGINE_HOURS_CLASSIFICATION": .decision(.classification, rid),
        ]
        #expect(Set(expected.keys) == Set(RecordKind.allCases.map(\.rawValue)))
        for (kind, route) in expected {
            // Push: kind + record_id win over the type and the link.
            let push = DeepLinkParser.parse(pushPayload: ["kind": kind, "record_id": r, "type": "CASH_VARIANCE_OPENED",
                                                          "link": "/tenant/alerts", "notification_id": UUID().uuidString])
            #expect(push?.route == route, "\(kind)")
            #expect(route.identifiesRecord)
            // Inbox: data.kind + record_id.
            #expect(DeepLinkParser.route(for: try Self.note(type: "X", data: ["kind": kind, "record_id": r])) == route, "\(kind)")
        }
        // Unknown kinds fall back as before (type, target, link, inbox).
        #expect(DeepLinkParser.parse(pushPayload: ["kind": "NEW_KIND", "record_id": r, "link": "/tenant/alerts"])?.route == .alerts)
        #expect(DeepLinkParser.route(for: try Self.note(type: "CASH_VARIANCE_OPENED", data: [:], entity: "cash_variance", id: r)) == .approvals)
        #expect(DeepLinkParser.route(for: try Self.note(type: "REMITTANCE_OVERDUE", data: [:])) == .overdueRemittances)
        #expect(DeepLinkParser.route(for: try Self.note(type: "X", data: ["kind": "NEW_KIND", "record_id": r])) == .notifications)
    }

    @Test func webDetailRoutesOpenTheRecord() {
        let rid = UUID(), r = rid.uuidString.lowercased()
        #expect(DeepLinkParser.route(path: "/tenant/finance/cash/transfers/\(r)") == .cashTransfer(rid))
        #expect(DeepLinkParser.route(path: "/tenant/finance/cash/floats/\(r)") == .cashFloat(rid))
        #expect(DeepLinkParser.route(path: "/tenant/finance/cash/variances/\(r)") == .decision(.writeOff, rid))
        #expect(DeepLinkParser.route(path: "/tenant/finance/cash/retentions/\(r)") == .decision(.retention, rid))
        #expect(DeepLinkParser.route(path: "/tenant/finance/cash/adjustments/\(r)") == .decision(.adjustment, rid))
        #expect(DeepLinkParser.route(path: "/tenant/finance/cash/remittances/\(r)") == .handover(rid))
        #expect(DeepLinkParser.route(path: "/tenant/finance/cash/remittance-overdue/\(r)") == .overdueRemittance(rid))
        #expect(DeepLinkParser.route(path: "/tenant/finance/cash/remittance-overdue") == .overdueRemittances)
        #expect(DeepLinkParser.route(path: "/tenant/finance/cash/transfers") == .cash)
        #expect(DeepLinkParser.route(path: "/tenant/finance/cash/retentions") == .approvals)
        #expect(DeepLinkParser.route(path: "/tenant/hours/discounts/\(r)") == .decision(.discount, rid))
        #expect(DeepLinkParser.route(path: "/tenant/hours/credit/\(r)") == .decision(.credit, rid))
        #expect(DeepLinkParser.route(path: "/tenant/hours/transfers/\(r)") == .decision(.hoursTransfer, rid))
        #expect(DeepLinkParser.route(path: "/tenant/hours/cancellations/\(r)") == .decision(.cancellation, rid))
        #expect(DeepLinkParser.route(path: "/tenant/meter-corrections/\(r)") == .decision(.correction, rid))
        #expect(DeepLinkParser.route(path: "/tenant/engine-hours/classifications/\(r)") == .decision(.classification, rid))
        #expect(DeepLinkParser.route(path: "/tenant/cash/transfers/\(r)") == .cashTransfer(rid))
        #expect(DeepLinkParser.route(path: "/tenant/cash/handovers/\(r)") == .handover(rid))
        #expect(DeepLinkParser.route(entity: "cash_remittance_overdue", id: nil, path: nil) == .overdueRemittances)
    }

    static func note(type: String, data: [String: Any], entity: String? = nil, id: String? = nil) throws -> NotificationDTO {
        var json: [String: Any] = [
            "id": UUID().uuidString.lowercased(), "type": type, "category": "CASH", "severity": "INFO", "priority": "NORMAL",
            "title": "t", "body": "b", "created_at": "2026-10-24T08:00:00Z", "read_at": NSNull(), "tenant_id": NSNull(), "data": data]
        if let entity {
            json["target"] = ["entity": entity, "id": id as Any? ?? NSNull(), "path": NSNull()] as [String: Any]
        } else {
            json["target"] = NSNull()
        }
        return try AssetaJSON.decoder().decode(NotificationDTO.self, from: JSONSerialization.data(withJSONObject: json))
    }
}
