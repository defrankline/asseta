@testable import AssetaOwnerKit
import AssetaModel
import Foundation
import Testing

/// Follow-up F1 on the Owner app: ENGINE_HOURS and CASH_CUSTODY switched off hide sections, tiles, rows and screens.
/// Same rules as Android `CapabilitySwitchOwnerTest`.
struct CapabilitySwitchOwnerTests {
    static let permissions = ["tenant.finance.read", "tenant.meter.read", "tenant.hours.read", "tenant.approval.read",
                              "tenant.accountability.read", "tenant.collection.record"]
    static let on = OwnerFeatures(permissions: permissions)
    static let engineOff = OwnerFeatures(permissions: permissions, disabledCapabilities: [TenantCapability.engineHours])
    static let cashOff = OwnerFeatures(permissions: permissions, disabledCapabilities: [TenantCapability.cashCustody])

    static func summary(_ disabled: String = "[]") throws -> AccountabilitySummaryDTO {
        let json = """
        {"as_of":"2026-10-25T08:00:00Z","policy_version":"v3","disabled_capabilities":\(disabled),
         "outstanding_approvals":{"approval_requests":1,"payments_to_verify":0,"remittances_to_verify":2,"cash_retentions":1,
           "custody_adjustments":1,"write_offs":1,"total":6},
         "cash":{"custodians":[],"transfers_awaiting_acknowledgement":[],"floats_awaiting_acknowledgement":[],
           "remittances_awaiting_confirmation":[],"partial_remittances_in_window":1,"remittance_cutoff_hour":18,
           "remittances_overdue_today":2},
         "discrepancies":{"open_variances":[],"write_offs_proposed":1,"sync_conflicts_unresolved":3},
         "engine_hours":{"machines":2,"by_status":{}},"unexplained_hours":{"hours":"1","items":[]},"missing_daily_reports":{"items":[]}}
        """
        return try AssetaJSON.decoder().decode(AccountabilitySummaryDTO.self, from: Data(json.utf8))
    }

    @Test func engineHoursOffHidesTheMeterDecisionSections() {
        let kinds = Self.engineOff.decisionKinds
        #expect(!kinds.contains(.baseline) && !kinds.contains(.classification) && !kinds.contains(.correction))
        #expect(kinds.contains(.writeOff) && kinds.contains(.discount))
        #expect(Self.on.decisionKinds.contains(.baseline))
        #expect(!Self.engineOff.engineHours && Self.engineOff.cashCustody)
    }

    @Test func cashCustodyOffHidesWriteOffsRetentionsAndAdjustments() {
        let kinds = Self.cashOff.decisionKinds
        #expect(!kinds.contains(.writeOff) && !kinds.contains(.retention) && !kinds.contains(.adjustment))
        #expect(kinds.contains(.baseline))
        #expect(!Self.cashOff.cashCustody && Self.cashOff.engineHours)
    }

    @Test func deepLinksToHiddenKindsFallBackToTheList() {
        let id = UUID()
        let baseline = OwnerRoute.decision(.baseline, id)
        #expect(Self.engineOff.route(baseline) == .approvals)
        #expect(Self.on.route(baseline) == baseline && Self.cashOff.route(baseline) == baseline)
        #expect(Self.cashOff.route(.decision(.retention, id)) == .approvals)
        #expect(Self.cashOff.route(.cashTransfer(id)) == .cash)
        #expect(Self.cashOff.route(.cashFloat(id)) == .cash)
        #expect(Self.cashOff.route(.overdueRemittance(id)) == .cash)
        #expect(Self.cashOff.route(.overdueRemittances) == .cash)
        #expect(!Self.cashOff.allows(.cashTransfer(id)) && !Self.cashOff.allows(.overdueRemittances))
        // The cash basics stay.
        #expect(Self.cashOff.route(.handover(id)) == .handover(id) && Self.cashOff.allows(.handover(id)) && Self.cashOff.allows(.cash))
        let hoursOff = OwnerFeatures(permissions: Self.permissions, disabledCapabilities: [TenantCapability.customerHours])
        #expect(hoursOff.route(.decision(.discount, id)) == .approvals)
    }

    @Test func engineHoursOffFromMeOrTheSummaryHidesTheEngineHourTiles() throws {
        let all = AccountabilityDashboard.tiles(try Self.summary()).map(\.id)
        #expect(["engine_hours", "unexplained_hours", "missing_daily_reports"].allSatisfy(all.contains))
        for tiles in [AccountabilityDashboard.tiles(try Self.summary(), disabled: [TenantCapability.engineHours]),
                      AccountabilityDashboard.tiles(try Self.summary(#"["ENGINE_HOURS"]"#))] {
            let ids = tiles.map(\.id)
            #expect(!ids.contains("engine_hours") && !ids.contains("unexplained_hours") && !ids.contains("missing_daily_reports"))
            #expect(ids.contains("cash"))
        }
    }

    @Test func cashCustodyOffKeepsTheCashBasicsAndHidesTheCustodyAdditions() throws {
        let full = Dictionary(uniqueKeysWithValues: AccountabilityDashboard.tiles(try Self.summary()).map { ($0.id, $0) })
        #expect(full["cash"]?.rows.contains { $0.label == "Remittances overdue today" } == true)
        for tiles in [AccountabilityDashboard.tiles(try Self.summary(), disabled: [TenantCapability.cashCustody]),
                      AccountabilityDashboard.tiles(try Self.summary(#"["CASH_CUSTODY"]"#))] {
            let byID = Dictionary(uniqueKeysWithValues: tiles.map { ($0.id, $0) })
            let cash = try #require(byID["cash"])
            #expect(cash.rows.map(\.label) == ["Remittances awaiting confirmation"])
            #expect(cash.moreLinks.isEmpty && cash.footer == nil)
            #expect(byID["outstanding_approvals"]?.rows.map(\.label)
                == ["Total", "Approval requests", "Payments to verify", "Remittances to verify"])
            #expect(byID["discrepancies"]?.rows.map(\.label) == ["Sync conflicts to review"])
        }
    }
}
