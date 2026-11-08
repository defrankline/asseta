@testable import AssetaOwnerKit
import AssetaModel
import AssetaNetwork
import Foundation
import Testing

/// DEC-032 Phase 3 on the Owner side: module switches, partial remittance reasons, variance closures and the variance
/// screen, remittance evidence status. Strings doc "DEC-032 Phase 3 — independence and evidence".
struct VarianceOwnerTests {
    typealias T = VarianceTexts
    static let id = UUID(uuidString: "e1000000-0000-4000-8000-000000000001")!
    static let user = UUID(uuidString: "e2000000-0000-4000-8000-000000000001")!
    static let utc = TimeZone(identifier: "UTC")!

    static func variance(status: String = "CLOSURE_PROPOSED", unit: String = "MONEY", extra: String = "") -> String {
        """
        {"id":"\(id.uuidString.lowercased())","source_type":"REMITTANCE","source_id":"\(UUID().uuidString.lowercased())",
         "staff_member_id":null,"counterparty_staff_id":null,"currency":"TZS","declared_amount":"100","received_amount":"80","amount":"20",
         "case_id":null,"opened_at":"2026-11-01T08:00:00Z","opened_by":null,"status":"\(status)","reason_id":null,
         "proposed_by":"\(user.uuidString.lowercased())","proposed_by_name":"Asha","proposed_at":"2026-11-02T08:00:00Z","proposal_note":"Counted again",
         "outcome":null,"resolved_by":null,"resolved_at":null,"resolution_note":null,"kind":"SHORTFALL","unit":"\(unit)",
         "proposed_outcome":"RECOVERED"\(extra)}
        """
    }

    static func handover(partial: String = "null", extra: String = "") -> String {
        """
        {"id":"\(id.uuidString.lowercased())","client_id":null,"staff_member_id":"\(user.uuidString.lowercased())","staff_member_name":"Juma",
         "amount":"100","currency":"TZS","handed_at":"2026-11-01T08:00:00Z","reference":"DS-1","note":null,"status":"CLAIMED","source":"MOBILE",
         "recorded_by":null,"recorded_at":"2026-11-01T08:00:00Z","verified_by":null,"verified_at":null,"decision_note":null,
         "partial_shortfall":"50","partial_approval":\(partial)\(extra)}
        """
    }

    static func partial(status: String = "PENDING") -> String {
        """
        {"id":"\(UUID().uuidString.lowercased())","status":"\(status)","reason_id":null,"reason":"Kept for fuel","created_by":"\(user.uuidString.lowercased())",
         "created_by_name":"Asha","created_at":"2026-11-01T09:00:00Z","decided_by":null,"decided_at":null,"decision_note":null}
        """
    }

    static func value(_ json: String) throws -> JSONValue { try JSONValue.parse(json) }

    // MARK: - Switches

    static let permissions = ["tenant.fleet.read", "tenant.job.read", "tenant.case.read", "tenant.finance.read", "tenant.fleet.alert_manage"]

    @Test func trackingOffHidesAlertsAndFallsBackHome() {
        let off = OwnerFeatures(permissions: Self.permissions, disabledCapabilities: [TenantCapability.tracking])
        #expect(!off.tracking && !off.alertsOn && !off.manageAlerts && off.fleet)
        #expect(!off.tabs.contains(.alerts) && off.tabs.contains(.fleet))
        #expect(!off.allows(.alerts) && !off.allows(.alert(Self.id)) && off.allows(.machine(Self.id)))
        #expect(off.route(.alerts) == .overview && off.route(.alert(Self.id)) == .overview)
        let on = OwnerFeatures(permissions: Self.permissions)
        #expect(on.alertsOn && on.tabs.contains(.alerts) && on.route(.alert(Self.id)) == .alert(Self.id))
    }

    @Test func investigationsOffHidesCasesAndFallsBackHome() {
        let off = OwnerFeatures(permissions: Self.permissions, disabledCapabilities: [TenantCapability.investigations])
        #expect(!off.cases && !off.allows(.investigations) && !off.moreEntries.contains("Investigations"))
        #expect(off.route(.investigations) == .overview && off.route(.investigation(Self.id)) == .overview)
    }

    @Test func machineStatusRowsDropTrackerFieldsWhenTrackingIsOff() throws {
        let m = try AssetaJSON.decoder().decode(MachineMapDTO.self, from: Data(Samples.machineJSON(connectivity: "LIVE", isLive: true, lastMessage: "2026-10-22T07:58:00Z", alerts: 1).utf8))
        let on = MachineText.statusRows(m, info: nil, dataIsCached: false).map(\.0)
        let off = MachineText.statusRows(m, info: nil, dataIsCached: false, tracking: false).map(\.0)
        #expect(on.contains("Engine (tracker)") && on.contains("Last seen"))
        #expect(!off.contains("Engine (tracker)") && !off.contains("Motion (tracker)") && !off.contains("Last seen")
            && !off.contains("Tracker") && !off.contains("Position time"))
        #expect(off.contains("Reported work status") && off.contains("Machine"))
    }

    // MARK: - Partial reason

    @Test func partialReasonRowAndDecisionFields() throws {
        let item = try #require(PendingDecision.from(try Self.value(Self.handover(partial: Self.partial())), kind: .partialRemittance))
        #expect(item.headline.hasSuffix("not remitted · Juma") && item.isPending && item.reason == "Kept for fuel")
        #expect(item.fields.map(\.label) == ["Cash held by", "Remitted", "Not remitted", "Reason", "Proposed by"])
        #expect(item.reasonLine == nil && item.isOwn(userID: Self.user))
        // A handover without a reason is not a decision; a decided reason no longer waits.
        #expect(PendingDecision.from(try Self.value(Self.handover()), kind: .partialRemittance) == nil)
        #expect(PendingDecision.from(try Self.value(Self.handover(partial: Self.partial(status: "APPROVED"))), kind: .partialRemittance)?.isPending == false)
    }

    @Test func partialReasonListsAllHandoversAndPostsItsOwnDecision() throws {
        let list = OwnerAPI.decisions(.partialRemittance, pendingOnly: true)
        #expect(list.path == "/api/v1/tenant/cash/handovers" && !list.queryItems.contains { $0.name == "status" })
        let decide = try OwnerAPI.decide(.partialRemittance, id: Self.id, approve: false, note: "No", idempotencyKey: UUID())
        #expect(decide.path.hasSuffix("/cash/handovers/\(Self.id.uuidString.lowercased())/partial-reason-decision"))
        #expect(DecisionKind.partialRemittance.decidePermission == "tenant.finance.retention_approve")
        #expect(DecisionKind.partialRemittance.capability == TenantCapability.cashCustody)
    }

    // MARK: - Variance

    @Test func closureRowFieldsAndHours() throws {
        let item = try #require(PendingDecision.from(try Self.value(Self.variance()), kind: .varianceClosure, timeZone: Self.utc))
        #expect(item.headline.hasPrefix("Close ") && item.headline.hasSuffix("(Recovered)") && item.isPending)
        #expect(item.fields.contains { $0.label == "Proposed outcome" && $0.value == "Recovered" })
        #expect(item.reason == "Counted again")
        let hours = try #require(PendingDecision.from(try Self.value(Self.variance(unit: "HOURS")), kind: .varianceClosure, timeZone: Self.utc))
        #expect(hours.headline == "Close 20 h (Recovered)" && hours.fields.contains { $0.label == "Declared" && $0.value == "100 h" })
    }

    @Test func aVarianceIsDecidedByWhatItWaitsFor() {
        #expect(DecisionKind.writeOff.effective(varianceStatus: "CLOSURE_PROPOSED") == .varianceClosure)
        #expect(DecisionKind.varianceClosure.effective(varianceStatus: "WRITE_OFF_PROPOSED") == .writeOff)
        #expect(DecisionKind.writeOff.effective(varianceStatus: "OPEN") == .writeOff)
        #expect(DecisionKind.retention.effective(varianceStatus: "CLOSURE_PROPOSED") == .retention)
        #expect(DecisionKind.writeOff.varianceTitle(status: "CLOSURE_PROPOSED") == "Variance closure")
        #expect(DecisionKind.writeOff.varianceTitle(status: "WRITE_OFF_PROPOSED") == "Cash write-off")
        #expect(DecisionKind.writeOff.varianceTitle(status: "RESOLVED") == "Variance")
    }

    @Test func closureGoesToItsOwnEndpointAndNeedsItsOwnPermission() throws {
        #expect(OwnerAPI.decisions(.varianceClosure, pendingOnly: true).queryItems.contains(URLQueryItem(name: "status", value: "CLOSURE_PROPOSED")))
        let decide = try OwnerAPI.decide(.varianceClosure, id: Self.id, approve: true, note: "", idempotencyKey: UUID())
        #expect(decide.path.hasSuffix("/closure-decision"))
        #expect(DecisionKind.varianceClosure.decidePermission == "tenant.finance.variance_close" && DecisionKind.varianceClosure.capability == nil)
        let reader = OwnerFeatures(permissions: ["tenant.finance.read"], disabledCapabilities: [TenantCapability.cashCustody])
        #expect(reader.decisionKinds.contains(.varianceClosure) && !reader.decisionKinds.contains(.partialRemittance) && !reader.canDecide(.varianceClosure))
    }

    @Test func refusalsInTheirOwnWords() {
        func error(_ code: String) -> APIError { .server(status: 409, body: ErrorBody(code: code, message: "x", correlationID: "c")) }
        #expect(DecisionRules.message(for: error("SEGREGATION_OF_DUTIES"), kind: .varianceClosure) == "You proposed this closure, so someone else must decide it.")
        #expect(DecisionRules.message(for: error("SEGREGATION_OF_DUTIES"), kind: .partialRemittance) == "You recorded this remittance, so someone else must decide its reason.")
        #expect(DecisionRules.message(for: error("CLOSURE_NOT_PROPOSED"), kind: .varianceClosure) == "This closure was already decided. Reload to see it.")
        #expect(DecisionRules.needsReload(error("CLOSURE_NOT_PROPOSED")) && DecisionRules.needsReload(error("PARTIAL_APPROVAL_NOT_FOUND")))
        #expect(AdjustmentTexts.error("ZERO_AMOUNT_PENDING") == "A request for this purchase already waits for a decision.")
        #expect(AdjustmentTexts.type("ZERO_AMOUNT_ACTIVATION") == "Purchase with nothing to pay")
    }

    @Test func investigationRowsCheckAndHistory() throws {
        let json = Self.variance(status: "OPEN", extra: #","assignee_user_id":"\#(Self.user.uuidString.lowercased())","assignee_user_name":"Neema","explanation":"Till error","check_code":"NEGATIVE_REMAINING","purchase_number":"P-9","purchase_id":"\#(UUID().uuidString.lowercased())""#)
        let v = try AssetaJSON.decoder().decode(CashVarianceDTO.self, from: Data(json.utf8))
        #expect(VariancePresentation.investigation(v).map(\.label) == ["Assigned to", "Explanation"])
        let item = try #require(PendingDecision.from(try Self.value(json), kind: .writeOff, timeZone: Self.utc))
        #expect(item.fields.contains { $0.label == "What was found" && $0.value == "Negative hours remaining" })
        #expect(item.fields.contains { $0.label == "Purchase" && $0.value == "P-9" } && !item.isPending)
        let event = try AssetaJSON.decoder().decode(VarianceEventDTO.self, from: Data(#"{"id":"\#(UUID().uuidString.lowercased())","action":"CLOSURE_PROPOSED","actor_user_id":null,"actor_user_name":"Asha","note":null,"data":{},"occurred_at":"2026-11-01T08:00:00Z"}"#.utf8))
        #expect(VariancePresentation.historyRow(event, timeZone: Self.utc).hasSuffix(" · Closure proposed · Asha"))
    }

    // MARK: - Remittance card and numbers

    @Test func remittanceEvidenceRowsHideAZeroDifference() throws {
        let extra = #","remittance_number":"RMT-7","evidence_status":"SUPPORTED","outstanding_difference":"0","evidence_attachment_ids":[]"#
        let h = try AssetaJSON.decoder().decode(CashHandoverDTO.self, from: Data(Self.handover(partial: Self.partial(), extra: extra).utf8))
        #expect(HandoverText.evidenceRows(h).map(\.value) == ["RMT-7", "Supported by evidence"])
        #expect(HandoverText.rowCaption(h) == "RMT-7 · Supported by evidence")
        #expect(HandoverText.partialRows(h).map(\.label) == ["Why part stayed with the custodian", "Reason status"])
        let open = try AssetaJSON.decoder().decode(CashHandoverDTO.self, from: Data(Self.handover(extra: #","outstanding_difference":"12""#).utf8))
        #expect(HandoverText.evidenceRows(open).map(\.label) == ["Difference still open"] && HandoverText.partialRows(open).isEmpty)
    }

    @Test func deepLinksReachTheVarianceAndRemittance() {
        let r = Self.id.uuidString.lowercased()
        #expect(DeepLinkParser.route(path: "/tenant/finance/cash/variances/\(r)") == .decision(.writeOff, Self.id))
        #expect(DeepLinkParser.route(path: "/tenant/finance/cash/remittances/\(r)") == .handover(Self.id))
    }
}
