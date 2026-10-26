@testable import AssetaOwnerKit
import AssetaModel
import AssetaNetwork
import Foundation
import Testing

/// Owner app accountability: decisions (every kind), the dashboard summary, remittance with the amount received and the
/// new notification deep links. Same rules and wording as Android.
struct AccountabilityOwnerTests {
    static let me = "11111111-aaaa-4000-8000-000000000001"
    static let other = "22222222-aaaa-4000-8000-000000000002"
    static let machine = "bbbbbbbb-0000-4000-8000-000000000002"
    static func id(_ n: Int) -> String { String(format: "%08d-0000-4000-8000-000000000001", n) }

    static let samples: [(DecisionKind, String, String)] = [
        (.discount, "DiscountDto", """
        {"id":"\(id(1))","customer_id":"\(id(91))","percent":"10","effective_from":"2026-10-01T00:00:00Z","effective_to":null,
         "reason":"Loyal customer","reason_code_id":null,"status":"PROPOSED","proposed_by":"\(other)","proposed_at":"2026-10-24T08:00:00Z",
         "decided_by":null,"decided_at":null,"decision_note":null,"revoked_by":null,"revoked_at":null,"revoke_reason":null,"version":1}
        """),
        (.credit, "CreditArrangementDto", """
        {"id":"\(id(2))","customer_id":"\(id(91))","limit_amount":"5000000","currency":"TZS","effective_from":"2026-10-01T00:00:00Z",
         "effective_to":"2026-12-31T00:00:00Z","terms":"30 days","reason":"Contract customer","reason_code_id":null,"status":"PROPOSED",
         "proposed_by":"\(me)","proposed_at":"2026-10-24T08:00:00Z","decided_by":null,"decided_at":null,"decision_note":null,
         "revoked_by":null,"revoked_at":null,"revoke_reason":null,"version":1}
        """),
        (.hoursTransfer, "TransferDto", """
        {"id":"\(id(3))","client_id":null,"purchase_id":"\(id(92))","from_machine_id":"\(machine)","to_machine_id":"\(id(93))",
         "hours":"12.5","reason":"Machine broke down","reason_code_id":null,"status":"PENDING","requested_by":"\(other)",
         "requested_at":"2026-10-24T08:00:00Z","decided_by":null,"decided_at":null,"decision_note":null}
        """),
        (.cancellation, "CancellationDto", """
        {"id":"\(id(4))","purchase_id":"\(id(92))","reason":"Customer left","reason_code_id":null,"status":"PENDING",
         "requested_by":"\(other)","requested_at":"2026-10-24T08:00:00Z","decided_by":null,"decided_at":null,"decision_note":null}
        """),
        (.baseline, "BaselineDto", """
        {"id":"\(id(5))","machine_id":"\(machine)","machine_code":"EX-07","machine_name":"CAT 320","reading":"4521.0",
         "captured_at":"2026-10-24T07:00:00Z","source":"CAPTURE","source_capture_id":null,"photo_attachment_id":"\(id(94))",
         "latitude":null,"longitude":null,"accuracy_m":null,"note":"New meter","status":"PROPOSED","proposed_by":"\(other)",
         "proposed_by_name":"Juma Field","proposed_at":"2026-10-24T08:00:00Z","decided_by":null,"decided_at":null,"decision_note":null}
        """),
        (.classification, "ClassificationDto", """
        {"id":"\(id(6))","machine_id":"\(machine)","machine_code":"EX-07","start_ref":"a","end_ref":"b",
         "start_at":"2026-10-23T06:00:00Z","end_at":"2026-10-23T09:00:00Z","hours":"3","outcome":"APPROVED_NON_CUSTOMER",
         "reason_id":"\(id(95))","reason_name":"Maintenance","note":"Hydraulic service","status":"PROPOSED","proposed_by":"\(other)",
         "proposed_by_name":null,"proposed_at":"2026-10-24T08:00:00Z","decided_by":null,"decided_at":null,"decision_note":null,
         "policy_version":"v1"}
        """),
        (.correction, "CorrectionDto", """
        {"id":"\(id(7))","machine_id":"\(machine)","machine_code":"EX-07","job_id":null,"superseded_capture_id":"\(id(96))",
         "replacement_capture_id":"\(id(97))","old_reading":"4521.0","new_reading":"4512.0","reason":"Misread the tens digit",
         "status":"PROPOSED","proposed_by":"\(other)","proposed_by_name":"Juma Field","proposed_at":"2026-10-24T08:00:00Z",
         "decided_by":null,"decided_at":null,"decision_note":null,"policy_version":"v1"}
        """),
        (.writeOff, "CashVarianceDto", """
        {"id":"\(id(8))","source_type":"TRANSFER","source_id":"\(id(98))","staff_member_id":null,"counterparty_staff_id":null,
         "currency":"TZS","declared_amount":"50000","received_amount":"45000","amount":"5000","kind":"SHORTFALL","case_id":null,
         "opened_at":"2026-10-24T07:00:00Z","opened_by":null,"status":"WRITE_OFF_PROPOSED","reason_id":null,"proposed_by":"\(other)",
         "proposed_at":"2026-10-24T08:00:00Z","proposal_note":"Counting error","outcome":null,"resolved_by":null,"resolved_at":null,
         "resolution_note":null}
        """),
        (.retention, "CashRetentionDto", """
        {"id":"\(id(9))","staff_member_id":"\(id(99))","amount":"20000","currency":"TZS","reason_id":null,"reason":"Working float",
         "valid_until":null,"status":"PENDING","created_by":"\(other)","created_at":"2026-10-24T08:00:00Z","decided_by":null,
         "decided_at":null,"decision_note":null}
        """),
        (.adjustment, "CustodyAdjustmentDto", """
        {"id":"\(id(10))","staff_member_id":"\(id(99))","kind":"REVERSAL","amount":"-10000","currency":"TZS",
         "occurred_at":"2026-10-24T07:00:00Z","reason_id":null,"reason":"Double entry","reverses_entity_type":null,
         "reverses_entity_id":null,"status":"PENDING","created_by":"\(other)","created_at":"2026-10-24T08:00:00Z","decided_by":null,
         "decided_at":null,"decision_note":null}
        """),
        (.nonRevenue, "NonRevenueApprovalDto", """
        {"id":"\(id(11))","activity_id":"\(id(12))","activity_type":"MOBILIZATION","job_id":"\(id(13))","job_number":"J-12",
         "machine_id":"\(machine)","machine_code":"EX-07","machine_name":null,"started_at":"2026-10-24T06:00:00Z",
         "ended_at":"2026-10-24T07:30:00Z","hours":"1.50","reason_id":"\(id(14))","reason_name":"Move to site",
         "note":"Moved to site B","status":"PROPOSED","proposed_by":"\(other)","proposed_by_name":null,
         "proposed_at":"2026-10-24T08:00:00Z","decided_by":null,"decided_by_name":null,"decided_at":null,"decision_note":null,
         "policy_version":"r1"}
        """),
    ]

    static let summary = """
    {"as_of":"2026-10-24T09:00:00Z","policy_version":"o1","hidden_tiles":["payments"],"unavailable_tiles":[],
     "customer_hours":{"activated":"40","consumed":"12.5","remaining":"27.5","awaiting_activation":"10","expired":"0","open_overruns":1},
     "hours_awaiting_activation":{"count":1,"hours":"10","purchases_awaiting_payment":1,"purchases_partly_active":0,"items":[]},
     "engine_hours":{"machines":3,"by_status":{"RECONCILED":2,"NO_BASELINE":1},"items":[]},
     "unexplained_hours":{"machines":1,"hours":"4","items":[{"machine_id":"\(machine)","machine_code":"EX-07","unexplained_hours":"4","oldest_open_item_days":5}]},
     "missing_daily_reports":{"count":1,"items":[{"machine_id":"\(machine)","machine_code":"EX-07","day":"2026-10-23","basis":"JOB","job_id":null}]},
     "investigations":{"open":2,"in_review":1},
     "cash":{"custodians":[{"staff_member_id":"\(id(99))","staff_name":"Juma Field","currency":"TZS","outstanding":"150000",
       "in_transit_out":"20000","claimed_unverified_handovers":"0","pending_floats":"0"}],
       "transfers_awaiting_acknowledgement":[{"currency":"TZS","count":1,"amount":"20000"}],"floats_awaiting_acknowledgement":[],
       "remittances_awaiting_confirmation":[{"currency":"TZS","count":2,"amount":"300000"}],"partial_remittances_in_window":1},
     "payments":null,
     "discrepancies":{"open_variances":[{"currency":"TZS","count":1,"amount":"5000"}],"write_offs_proposed":1,"sync_conflicts_unresolved":0},
     "unauthorized_attempts":{"window_days":30,"permission_denied":3,"segregation_of_duties":1},
     "outstanding_approvals":{"approval_requests":1,"cash_retentions":1,"custody_adjustments":0,"write_offs":1,"payments_to_verify":2,
       "remittances_to_verify":2,"total":7}}
    """

    @Test func samplesMatchTheContract() throws {
        for (_, schema, json) in Self.samples { #expect(try Contract.missingRequired(schema: schema, json: json) == [], "\(schema)") }
        #expect(try Contract.missingRequired(schema: "AccountabilitySummaryDto", json: Self.summary) == [])
        #expect(try Contract.missingRequired(schema: "CashHandoverDto", json: RemoteBossTests.handover()) == [])
    }

    @Test func everyKindNormalizesForTheRowAndDecisionScreen() throws {
        let utc = TimeZone(identifier: "UTC")!
        var byKind: [DecisionKind: PendingDecision] = [:]
        for (kind, _, json) in Self.samples {
            let item = try #require(PendingDecision.from(try JSONValue.parse(json), kind: kind, timeZone: utc), "\(kind)")
            #expect(item.isPending && item.kind == kind)
            byKind[kind] = item
        }
        #expect(byKind.count == DecisionKind.allCases.count)
        #expect(byKind[.discount]?.headline == "10% discount")
        #expect(byKind[.credit]?.headline.hasPrefix("Credit limit ") == true)
        #expect(byKind[.hoursTransfer]?.headline == "Move 12.5 h to another machine")
        #expect(byKind[.cancellation]?.headline == "Cancel an hours purchase")
        #expect(byKind[.baseline]?.headline == "Baseline 4521 h · EX-07")
        #expect(byKind[.baseline]?.photoAttachmentID != nil && byKind[.baseline]?.proposedByName == "Juma Field")
        #expect(byKind[.classification]?.headline == "3 h · Maintenance")
        #expect(byKind[.classification]?.fields.contains(DecisionField(label: "Outcome", value: "Approved non-customer work")) == true)
        #expect(byKind[.correction]?.headline == "4521 → 4512 h · EX-07")
        #expect(byKind[.writeOff]?.headline.hasPrefix("Write off ") == true && byKind[.writeOff]?.reason == "Counting error")
        #expect(byKind[.retention]?.headline.hasPrefix("Keep ") == true)
        #expect(byKind[.adjustment]?.headline.hasPrefix("Reversal ") == true)
        // Proposer != approver: my own credit proposal is flagged so Approve is disabled.
        let mine = try #require(UUID(uuidString: Self.me))
        #expect(byKind[.credit]?.isOwn(userID: mine) == true && byKind[.discount]?.isOwn(userID: mine) == false)
    }

    @Test func listsAndDecisionsUseTheContractPathsAndBodies() throws {
        for kind in DecisionKind.allCases {
            let path = OwnerAPI.decisions(kind, pendingOnly: true).path
            let operation = try #require((try Contract.root()["paths"] as? [String: Any])?[path] as? [String: Any], "\(path)")
            #expect(operation["get"] != nil)
            let rid = UUID()
            let request = try OwnerAPI.decide(kind, id: rid, approve: false, note: " Not agreed ", idempotencyKey: UUID())
            let template = request.path.replacingOccurrences(of: rid.uuidString.lowercased(), with: "{id}")
            let paths = try #require(try Contract.root()["paths"] as? [String: Any])
            #expect(paths.keys.contains { $0.replacingOccurrences(of: #"\{[a-z_]+\}"#, with: "{id}", options: .regularExpression) == template },
                    "\(template)")
            let body = try #require(request.body.flatMap { try JSONSerialization.jsonObject(with: $0) as? [String: Any] })
            if kind.usesMeterDecision {
                #expect(body["decision"] as? String == "REJECT" && body["note"] as? String == "Not agreed")
            } else {
                #expect(body["approve"] as? Bool == false && body["note"] as? String == "Not agreed")
            }
        }
        let approve = try OwnerAPI.decide(.retention, id: UUID(), approve: true, note: "  ", idempotencyKey: UUID())
        #expect(try #require(approve.body.flatMap { try JSONSerialization.jsonObject(with: $0) as? [String: Any] })["note"] == nil)
        #expect(OwnerAPI.decisions(.writeOff, pendingOnly: true).queryItems.contains(URLQueryItem(name: "status", value: "WRITE_OFF_PROPOSED")))
    }

    @Test func decisionRules() {
        #expect(!DecisionRules.canDecide(.baseline, approve: true, note: "ok"))
        #expect(DecisionRules.canDecide(.baseline, approve: false, note: "Photo unclear"))
        #expect(DecisionRules.canDecide(.discount, approve: true, note: ""))
        #expect(!DecisionRules.canDecide(.discount, approve: false, note: "  "))
        #expect(DecisionRules.noteLabel(.correction) == "Note (at least 5 characters)")
        #expect(DecisionRules.noteLabel(.retention) == "Note (optional to approve, required to reject)")
        let sod = APIError.server(status: 403, body: ErrorBody(code: "SEGREGATION_OF_DUTIES", message: "x", correlationID: "c"))
        #expect(DecisionRules.message(for: sod) == "Someone else must decide your own request")
        #expect(DecisionRules.needsReload(APIError.server(status: 409, body: ErrorBody(code: "RETENTION_ALREADY_DECIDED", message: "x",
                                                                                         correlationID: "c"))))
    }

    @Test func featuresGateEachKindByPermission() {
        let viewer = OwnerFeatures(permissions: ["tenant.hours.read", "tenant.meter.read"])
        #expect(viewer.decisionKinds == [.discount, .credit, .hoursTransfer, .cancellation, .baseline, .classification, .correction])
        #expect(viewer.approvalsScreen && !viewer.approvals && !viewer.canDecide(.discount) && !viewer.accountability)
        let boss = OwnerFeatures(permissions: ["tenant.finance.read", "tenant.finance.writeoff", "tenant.accountability.read"])
        #expect(boss.decisionKinds == [.writeOff, .retention, .adjustment] && boss.canDecide(.writeOff) && !boss.canDecide(.retention))
        #expect(boss.allows(.accountability) && boss.allows(.decision(.retention, UUID())) && !boss.allows(.decision(.baseline, UUID())))
        #expect(boss.moreEntries.prefix(2) == ["Approvals", "Accountability"])
        #expect(OwnerFeatures(permissions: []).decisionKinds.isEmpty && !OwnerFeatures(permissions: []).approvalsScreen)
    }

    @Test func dashboardTilesFollowTheSummary() throws {
        let s = try AssetaJSON.decoder().decode(AccountabilitySummaryDTO.self, from: Data(Self.summary.utf8))
        let tiles = AccountabilityDashboard.tiles(s, timeZone: TimeZone(identifier: "UTC")!)
        #expect(tiles.map(\.id) == ["outstanding_approvals", "cash", "discrepancies", "investigations", "unauthorized_attempts",
                                    "customer_hours", "hours_awaiting_activation", "engine_hours", "unexplained_hours",
                                    "missing_daily_reports"])
        #expect(tiles.first?.rows.first == DashboardTile.Row("Total", "7"))
        let custodian = tiles.first { $0.id == "cash" }?.rows.first { $0.label == "Juma Field" }
        #expect(custodian?.value.contains(" outstanding · ") == true && custodian?.value.hasSuffix(" in transit") == true && custodian?.detail == nil)
        #expect(tiles.first { $0.id == "engine_hours" }?.rows.map(\.label) == ["Machines", "No baseline", "Reconciled"])
        #expect(tiles.first { $0.id == "unexplained_hours" }?.rows.last?.value == "4 h · oldest 5 days")
        #expect(tiles.first { $0.id == "missing_daily_reports" }?.rows.last?.label == "EX-07 · 2026-10-23")
        let attempts = tiles.first { $0.id == "unauthorized_attempts" }
        #expect(attempts?.footer == "Last 30 days" && attempts?.rows.allSatisfy { $0.detail == nil } == true)
        #expect(AccountabilityDashboard.showsHiddenNote(s))
        #expect(AccountabilityDashboard.footer(s, timeZone: TimeZone(identifier: "UTC")!) == "Policy o1 · As of 24 Oct 2026, 09:00")
        // A tile that does not decode is left out; the dashboard still opens.
        let broken = Self.summary.replacingOccurrences(of: #""investigations":{"open":2,"in_review":1}"#, with: #""investigations":{"open":"x"}"#)
        let partial = try AssetaJSON.decoder().decode(AccountabilitySummaryDTO.self, from: Data(broken.utf8))
        #expect(partial.investigations == nil && partial.cash != nil)
    }

    @Test func remittanceConfirmSendsTheAmountReceived() throws {
        let id = UUID()
        let confirm = try OwnerAPI.decideHandover(id, confirm: true, note: nil, amountReceived: Decimal(string: "149500.5"),
                                                  idempotencyKey: UUID())
        let body = try #require(confirm.body.flatMap { try JSONSerialization.jsonObject(with: $0) as? [String: Any] })
        #expect(body["verified"] as? Bool == true && body["amount_received"] as? String == "149500.5")
        let dispute = try OwnerAPI.decideHandover(id, confirm: false, note: "Short", amountReceived: 1, idempotencyKey: UUID())
        let disputeBody = try #require(dispute.body.flatMap { try JSONSerialization.jsonObject(with: $0) as? [String: Any] })
        #expect(disputeBody["amount_received"] == nil)
        #expect(HandoverText.parseReceived("0") == 0 && HandoverText.parseReceived("150,000.50") == Decimal(string: "150000.5"))
        #expect(HandoverText.parseReceived("-1") == nil && HandoverText.parseReceived("") == nil)
        #expect(!HandoverText.canConfirm(amountReceived: "abc", text: "") && HandoverText.canConfirm(amountReceived: "10", text: ""))
        let h = try AssetaJSON.decoder().decode(CashHandoverDTO.self, from: Data(RemoteBossTests.handover().utf8))
        #expect(HandoverText.prefill(h) == "150000" && h.amountReceived == nil)
    }

    @Test func newNotificationTypesDeepLink() {
        let rid = UUID()
        let r = rid.uuidString.lowercased()
        #expect(DeepLinkParser.route(entity: "customer_discount", id: r, path: nil) == .decision(.discount, rid))
        #expect(DeepLinkParser.route(entity: "hours_cancellation", id: r, path: nil) == .decision(.cancellation, rid))
        #expect(DeepLinkParser.route(entity: "baseline", id: r, path: nil) == .decision(.baseline, rid))
        #expect(DeepLinkParser.route(entity: "classification", id: r, path: nil) == .decision(.classification, rid))
        #expect(DeepLinkParser.route(entity: "cash_retention", id: r, path: nil) == .decision(.retention, rid))
        #expect(DeepLinkParser.route(entity: "cash_variance", id: r, path: nil) == .decision(.writeOff, rid))
        #expect(DeepLinkParser.route(entity: "job_exception", id: r, path: nil) == .exception(rid))
        #expect(DeepLinkParser.route(entity: "machine", id: r, path: nil) == .machine(rid))
        #expect(DeepLinkParser.route(entity: "cash_handover", id: r, path: nil) == .handover(rid))
        #expect(DeepLinkParser.route(entity: "cash_transfer", id: r, path: nil) == .cashTransfer(rid))
        #expect(DeepLinkParser.route(entity: "supervisor_cash_custody", id: r, path: nil) == .cashFloat(rid))
        #expect(DeepLinkParser.route(entity: "cash_transfer", id: nil, path: nil) == .cash)
        #expect(DeepLinkParser.route(entity: "hours_purchase", id: r, path: nil) == .accountability)
        #expect(DeepLinkParser.route(type: "CASH_VARIANCE_OPENED") == .approvals)
        #expect(DeepLinkParser.route(type: "HOURS_EXPIRING") == .accountability)
        #expect(DeepLinkParser.route(path: "/tenant/engine-hours/machines/\(r)") == .machine(rid))
        #expect(DeepLinkParser.route(path: "/tenant/meter-baselines") == .approvals)
        let push = DeepLinkParser.parse(pushPayload: ["type": "CASH_VARIANCE_OPENED", "entity": "cash_variance", "entity_id": r])
        #expect(push?.route == .approvals)
        let partial = DeepLinkParser.parse(pushPayload: ["type": "PARTIAL_REMITTANCE", "entity": "cash_handover", "entity_id": r])
        #expect(partial?.route == .handover(rid))
        #expect(OwnerRoute.decision(.baseline, rid).identifiesRecord && !OwnerRoute.accountability.identifiesRecord)
    }

    /// Partial mappings: every key a decision DTO maps exists on its contract schema (the DTOs map only what the app shows).
    @Test func partialMappingsUseContractProperties() throws {
        func keys<D: Codable>(_ type: D.Type, _ json: String) throws -> [String] {
            let value = try AssetaJSON.decoder().decode(D.self, from: Data(json.utf8))
            let data = try AssetaJSON.encoder().encode(value)
            return Array((try JSONSerialization.jsonObject(with: data) as? [String: Any] ?? [:]).keys)
        }
        let samples = Dictionary(uniqueKeysWithValues: Self.samples.map { ($0.0, ($0.1, $0.2)) })
        let mapped: [(DecisionKind, [String])] = [
            (.discount, try keys(DiscountDTO.self, samples[.discount]!.1)),
            (.credit, try keys(CreditArrangementDTO.self, samples[.credit]!.1)),
            (.hoursTransfer, try keys(HoursTransferDTO.self, samples[.hoursTransfer]!.1)),
            (.cancellation, try keys(CancellationDTO.self, samples[.cancellation]!.1)),
            (.baseline, try keys(BaselineDTO.self, samples[.baseline]!.1)),
            (.classification, try keys(ClassificationDTO.self, samples[.classification]!.1)),
            (.correction, try keys(CorrectionDTO.self, samples[.correction]!.1)),
            (.writeOff, try keys(CashVarianceDTO.self, samples[.writeOff]!.1)),
            (.adjustment, try keys(CustodyAdjustmentDTO.self, samples[.adjustment]!.1)),
        ]
        for (kind, mappedKeys) in mapped {
            let schema = samples[kind]!.0
            let props = try #require((Contract.schemas[schema] as? [String: Any])?["properties"] as? [String: Any])
            for key in mappedKeys { #expect(props[key] != nil, "\(schema).\(key)") }
        }
        let summaryProps = try #require((Contract.schemas["AccountabilitySummaryDto"] as? [String: Any])?["properties"] as? [String: Any])
        let summary = try AssetaJSON.decoder().decode(AccountabilitySummaryDTO.self, from: Data(Self.summary.utf8))
        let encoded = try #require(try JSONSerialization.jsonObject(with: try AssetaJSON.encoder().encode(summary)) as? [String: Any])
        for key in encoded.keys { #expect(summaryProps[key] != nil, "AccountabilitySummaryDto.\(key)") }
        let remittance = try #require((Contract.schemas["RemittanceDecisionIn"] as? [String: Any])?["properties"] as? [String: Any])
        for key in ["verified", "note", "amount_received"] { #expect(remittance[key] != nil) }
        for (schema, fields) in [("DecisionIn", ["approve", "note"]), ("MeterDecisionIn", ["decision", "note"])] {
            let props = try #require((Contract.schemas[schema] as? [String: Any])?["properties"] as? [String: Any])
            for key in fields { #expect(props[key] != nil, "\(schema).\(key)") }
        }
    }

    @Test func machineNamesAndCapturedTimeOnTheDecisionScreen() throws {
        let from = try #require(UUID(uuidString: Self.machine)), to = try #require(UUID(uuidString: Self.id(93)))
        _ = (from, to)
        let transfer = try #require(PendingDecision.from(try JSONValue.parse(Self.samples[2].2), kind: .hoursTransfer))
        #expect(transfer.fields.map(\.label) == ["Purchase", "Hours", "From machine", "To machine", "Requested by"])
        #expect(transfer.fields.first?.value == "00000092" && transfer.proposedByName == "22222222")
        // An older server without machine names: the short ids stand in (as Android).
        #expect(transfer.fields[2].value == "bbbbbbbb" && transfer.fields[3].value == "00000093")
        let baseline = try #require(PendingDecision.from(try JSONValue.parse(Self.samples[4].2), kind: .baseline,
                                                         timeZone: TimeZone(identifier: "UTC")!))
        #expect(baseline.fields.map(\.label) == ["Machine", "Reading", "Proposed by", "Captured"])
        #expect(baseline.fields.last?.value == "24 Oct 2026, 07:00" && baseline.reason == "New meter")
    }
}
