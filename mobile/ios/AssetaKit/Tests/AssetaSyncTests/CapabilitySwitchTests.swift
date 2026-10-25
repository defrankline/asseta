import AssetaModel
import AssetaNetwork
import AssetaStore
@testable import AssetaSync
import Foundation
import Testing

/// Follow-up F1/F2 on the field side: ENGINE_HOURS and CASH_CUSTODY switched off in `/me` hide their Supervisor entry
/// points; their sync conflicts read in plain words; the "Overdue remittance" screen. Same rules as Android
/// (`CapabilitySwitchDomainTest`, `RemittanceOverdueText`).
struct CapabilitySwitchTests {
    static let caps = Set(AccountabilityTests.all + ["OP_CASH_RETENTION_REQUEST"])
    static let on = FieldAccess(capabilities: caps, permissions: AccountabilityTests.permissions, cash: AccountabilityTests.cashOn,
                                hours: AccountabilityTests.hoursOn)

    static func access(_ disabled: Set<String>) -> FieldAccess {
        FieldAccess(capabilities: caps, permissions: AccountabilityTests.permissions, cash: AccountabilityTests.cashOn,
                    hours: AccountabilityTests.hoursOn, disabledCapabilities: disabled)
    }

    @Test func everythingShowsWhileNoSwitchIsOff() {
        let a = Self.on
        #expect(a.engineHoursOn && a.cashCustodyOn)
        #expect(a.transferCash && a.acknowledgeCash && a.recordForOthers && a.askToKeepCash && a.retentionOffline)
        #expect(a.dailyReading && a.proposeBaseline && a.proposeCorrection)
    }

    @Test func engineHoursOffHidesDailyReadingBaselineAndCorrectionOnly() {
        let off = Self.access([TenantCapability.engineHours])
        #expect(!off.engineHoursOn && !off.dailyReading && !off.proposeBaseline && !off.proposeCorrection)
        #expect(off.transferCash && off.askToKeepCash && off.recordForOthers && off.sellHours)
    }

    @Test func cashCustodyOffHidesTransferAcknowledgementKeepCashAndRecordingForOthersOnly() {
        let off = Self.access([TenantCapability.cashCustody])
        #expect(!off.cashCustodyOn && !off.transferCash && !off.acknowledgeCash && !off.recordForOthers)
        #expect(!off.askToKeepCash && !off.retentionOffline)
        #expect(off.dailyReading && off.proposeBaseline && off.proposeCorrection && off.sellHours)
    }

    @Test func switchedOffConflictsAreConflictsInPlainWords() {
        for code in ["ENGINE_HOURS_DISABLED", "CASH_CUSTODY_DISABLED"] {
            let result = OperationResultDTO(id: UUID(), status: .duplicate, error: .object(["code": .string(code)]))
            #expect(PushOutcomeApplier.classify(result) == .conflict(code: code))
        }
        #expect(FieldAccountabilityTexts.conflictText("ENGINE_HOURS_DISABLED")
            == "Your company has switched off engine-hour controls, so this was not accepted.")
        #expect(FieldAccountabilityTexts.conflictText("CASH_CUSTODY_DISABLED")
            == "Your company has switched off cash custody controls, so this was not accepted.")
    }

    static let overdueJSON = """
    {"id":"77777777-0000-4000-8000-000000000001","staff_member_id":"33333333-aaaa-4000-8000-000000000003",
     "staff_member_name":"Juma Field","local_day":"2026-10-24","cutoff_hour":7,
     "amounts":[{"currency":"TZS","amount":"150000"},{"currency":"USD","amount":"20"}],"flagged_at":"2026-10-24T04:05:00Z",
     "policy_version":"c3"}
    """

    @Test func overdueRemittanceScreenRowsAndFooter() throws {
        let o = try AssetaJSON.decoder().decode(RemittanceOverdueDTO.self, from: Data(Self.overdueJSON.utf8))
        let rows = RemittanceOverduePresentation.rows(o, flagged: { _ in "24 Oct 2026, 07:05" })
        #expect(rows.map(\.label) == ["Cash held by", "Not remitted", "Day", "Cut-off", "Flagged"])
        #expect(rows.map(\.value) == ["Juma Field", "TZS 150,000.00, USD 20.00", "2026-10-24", "07:00", "24 Oct 2026, 07:05"])
        #expect(RemittanceOverduePresentation.footer(o)
            == "Still held after the 07:00 cut-off on 2026-10-24. Remit this cash to the office as soon as you can.")
        #expect(FieldAccountabilityTexts.titleRemittanceOverdue == "Overdue remittance")

        // No name: the short id; blank values are left out.
        let unnamed = try AssetaJSON.decoder().decode(RemittanceOverdueDTO.self, from: Data(Self.overdueJSON
            .replacingOccurrences(of: #""staff_member_name":"Juma Field""#, with: #""staff_member_name":null"#)
            .replacingOccurrences(of: #"[{"currency":"TZS","amount":"150000"},{"currency":"USD","amount":"20"}]"#, with: "[]").utf8))
        let short = RemittanceOverduePresentation.rows(unnamed, flagged: { _ in "x" })
        #expect(short.first?.value == "33333333")
        #expect(!short.map(\.label).contains("Not remitted"))
    }

    @Test func overdueRemittanceTapsOpenTheRecord() {
        let id = UUID()
        #expect(InboxLink.from(record: RecordRef(kind: .remittanceOverdue, id: id)) == .remittanceOverdue(id))
        #expect(InboxLink.from(entity: "cash_remittance_overdue", id: id.lowercased) == .remittanceOverdue(id))
        #expect(InboxLink.from(entity: "cash_remittance_overdue", id: nil) == .money)
    }
}
