import AssetaModel
import AssetaStore
@testable import AssetaSync
import Foundation
import Testing

/// "Book the job" with an hours sale (OP_HOURS_SALE_BOOKING); same cases as Android `SaleBookingTest`,
/// `AccountabilitySyncTest` and `AccountabilityPresentationTest`.
struct SaleBookingTests {
    typealias T = FieldAccountabilityTexts
    static let caps: Set<String> = [SyncCapability.hoursPurchase, SyncCapability.hoursSaleBooking]
    static let perms: Set<String> = [FieldAccess.hoursPurchase, FieldAccess.jobRequest]
    let start = Date(timeIntervalSince1970: 1_800_000_000)

    func sale(_ job: SaleJobDraft?) -> HoursSaleDraft {
        var d = HoursSaleDraft()
        d.customerID = UUID()
        d.machineID = UUID()
        d.hoursText = "6"
        d.payments = [PaymentLine(method: "CASH", amountText: "570000")]
        d.job = job
        return d
    }

    @Test func bookTheJobNeedsTheCapabilityTheJobRequestPermissionAndHoursSales() {
        let hours = AccountabilityTests.hoursOn
        #expect(FieldAccess(capabilities: Self.caps, permissions: Self.perms, hours: hours).bookSaleJob)
        #expect(!FieldAccess(capabilities: Self.caps.subtracting([SyncCapability.hoursSaleBooking]), permissions: Self.perms, hours: hours).bookSaleJob)
        #expect(!FieldAccess(capabilities: Self.caps, permissions: Self.perms.subtracting([FieldAccess.jobRequest]), hours: hours).bookSaleJob)
        #expect(!FieldAccess(capabilities: Self.caps, permissions: Self.perms.subtracting([FieldAccess.hoursPurchase]), hours: hours).bookSaleJob)
        #expect(!FieldAccess(capabilities: Self.caps, permissions: Self.perms, hours: hours, disabledCapabilities: ["CUSTOMER_HOURS"]).bookSaleJob)
        #expect(!FieldAccess(capabilities: nil, permissions: Self.perms, hours: hours).bookSaleJob)
    }

    @Test func theStartOpensTomorrowAt0800AndTheEndOfferedIsTheSaleHoursLater() throws {
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = try #require(TimeZone(identifier: "Africa/Dar_es_Salaam"))
        let now = try #require(calendar.date(from: DateComponents(year: 2026, month: 11, day: 11, hour: 21, minute: 48)))
        let expected = try #require(calendar.date(from: DateComponents(year: 2026, month: 11, day: 12, hour: 8)))
        #expect(SaleBooking.defaultStart(now: now, calendar: calendar) == expected)
        #expect(SaleBooking.endAfterHours(start: start, hoursText: "6") == start.addingTimeInterval(6 * 3600))
        #expect(SaleBooking.endAfterHours(start: start, hoursText: "2.5") == start.addingTimeInterval(150 * 60))
        #expect(SaleBooking.endAfterHours(start: start, hoursText: "") == nil)
        #expect(SaleBooking.endAfterHours(start: start, hoursText: "0") == nil)
    }

    @Test func theEndMustBeAfterTheStartAndAContractIsChosenWhenOffered() throws {
        let site = UUID()
        guard case let .success(ok) = AccountabilityRules.hoursSale(
            sale(SaleJobDraft(start: start, end: start.addingTimeInterval(1), siteID: site, note: "  dig the trench  ")), walkInAllowed: true)
        else { Issue.record("expected valid"); return }
        #expect(ok.job == SaleJobValues(start: start, end: start.addingTimeInterval(1), siteID: site, contractID: nil, note: "dig the trench"))
        guard case let .success(none) = AccountabilityRules.hoursSale(sale(nil), walkInAllowed: true) else { Issue.record("valid"); return }
        #expect(none.job == nil)

        guard case let .failure(same) = AccountabilityRules.hoursSale(sale(SaleJobDraft(start: start, end: start)), walkInAllowed: true)
        else { Issue.record("expected invalid"); return }
        #expect(same.messages == [T.hoursErrJobEnd])
        #expect(AccountabilityRules.hoursSaleBlockers(sale(SaleJobDraft(start: start, end: start.addingTimeInterval(-60))), walkInAllowed: true)
            == "To save: set the job's end after its start.")

        let choose = sale(SaleJobDraft(start: start, contractRequired: true))
        guard case let .failure(missing) = AccountabilityRules.hoursSale(choose, walkInAllowed: true) else { Issue.record("invalid"); return }
        #expect(missing.messages == [T.hoursErrJobContract])
        #expect(AccountabilityRules.hoursSaleBlockers(choose, walkInAllowed: true) == "To save: choose the job's contract.")

        var both = sale(SaleJobDraft(start: start, end: start, contractRequired: true))
        both.machineID = nil
        #expect(AccountabilityRules.hoursSaleBlockers(both, walkInAllowed: true)
            == "To save: choose the machine, set the job's end after its start and choose the job's contract.")
    }

    @Test func theBookingJoinsTheDraftOnlyWhenOnAndOffersTheContractOnlyForSeveral() throws {
        let c1 = UUID(), c2 = UUID()
        func contract(_ customer: UUID, _ number: String) throws -> FieldContractDTO {
            try JSONValue.object(["id": .string(UUID().uuidString.lowercased()), "contract_number": .string(number),
                                  "customer_id": .string(customer.uuidString.lowercased())]).decode(as: FieldContractDTO.self)
        }
        let contracts = [try contract(c1, "CT-1"), try contract(c1, "CT-2"), try contract(c2, "CT-3")]
        let choices = SaleBooking.contractChoices(contracts, customerID: c1, walkIn: false)
        #expect(choices.map(\.contractNumber) == ["CT-1", "CT-2"])
        #expect(SaleBooking.contractChoices(contracts, customerID: c2, walkIn: false).isEmpty)
        #expect(SaleBooking.contractChoices(contracts, customerID: c1, walkIn: true).isEmpty)
        #expect(SaleBooking.job(on: false, start: start, end: nil, siteID: nil, contractID: nil, note: "", choices: choices) == nil)
        let other = SaleBooking.job(on: true, start: start, end: nil, siteID: nil, contractID: contracts[2].id, note: "", choices: choices)
        #expect(other?.contractRequired == true && other?.contractID == nil) // another customer's contract is dropped
        #expect(SaleBooking.job(on: true, start: start, end: nil, siteID: nil, contractID: contracts[1].id, note: "", choices: choices)?
            .contractID == contracts[1].id)
        #expect(SaleBooking.job(on: true, start: start, end: nil, siteID: nil, contractID: nil, note: "", choices: [])?.contractRequired == false)
    }

    @Test func aSaleThatBooksItsJobIsTitledSoAndShowsTheBookedJobOnceSynced() throws {
        #expect(T.hoursSaleOutbox(try JSONValue.parse(#"{"payment":{"method":"CASH","amount":"520000"},"job":{"planned_start":"2026-11-12T05:00:00Z"}}"#))
            == "Hours sale + job booking · Cash 520,000")
        #expect(T.hoursSaleOutbox(try JSONValue.parse(#"{"job":{"planned_start":"2026-11-12T05:00:00Z"}}"#)) == "Hours sale + job booking · Not paid yet")
        #expect(T.hoursSaleOutbox(try JSONValue.parse(#"{"job":null}"#)) == "Hours sale · Not paid yet")
        #expect(T.hoursSaleJob(try JSONValue.parse(#"{"entity":{"id":"p1","job":{"id":"j1","job_number":"JB-2026-00042","status":"APPROVED"}}}"#))
            == "Job JB-2026-00042 · Approved")
        #expect(T.hoursSaleJob(try JSONValue.parse(#"{"result":{"entity":{"job":{"job_number":"JB-2026-00043","status":"PENDING_APPROVAL"}}}}"#))
            == "Job JB-2026-00043 · Waiting for approval")
        #expect(T.hoursSaleJob(try JSONValue.parse(#"{"entity":{"id":"p1","job":null}}"#)) == nil)
        #expect(T.hoursSaleJob(nil) == nil)
        #expect(T.jobEndFromHours(6) == "End after the sale hours (6 h)")
    }

    @Test func aRefusedBookingAndABusyMachineReadInPlainWords() {
        #expect(T.conflictText("CONTRACT_REQUIRED")
            == "This customer has no contract yet; the office creates one. The sale and its booking are kept for review.")
        for code in ["CONTRACT_CHOICE_REQUIRED", "CONTRACT_CUSTOMER_MISMATCH", "CONTRACT_NOT_ACTIVE", "JOB_REQUEST_NOT_PERMITTED", "NO_STAFF_RECORD"] {
            let text = T.conflictText(code) ?? ""
            #expect(text.hasSuffix("The sale and its booking are kept for review.") || text.contains("kept for review;"), "\(code)")
        }
        #expect(T.conflictText("MACHINE_BUSY") == "Another job is running on this machine; finish it first.")
    }

    @Test func aBookedSaleCarriesTheJobNeedsTheCapabilityAndKeepsARefusalCode() async throws {
        let h = try SyncHarness().withFinanceData()
        let engine = h.engine()
        _ = try await engine.sync()
        var draft = HoursSaleDraft()
        draft.customerID = FinanceFixtures.customerID
        draft.machineID = SyncFixtures.machineID
        draft.hoursText = "6"
        draft.payments = [PaymentLine(method: "CASH", amountText: "520000")]
        let site = UUID()
        draft.job = SaleJobDraft(start: start, end: start.addingTimeInterval(6 * 3600), siteID: site, note: " Dig the trench ")
        // A server without OP_HOURS_SALE_BOOKING would drop the job: the sale with a booking is not saved.
        #expect(throws: FieldRecorderError.notAllowed(T.serverTooOld)) {
            try h.recorder.recordHoursSale(draft, walkInAllowed: false, cashHolderID: nil, evidence: [], receivedAt: h.clock.wallNow)
        }
        h.server.mutate { $0.capabilities = AccountabilityTests.all + [SyncCapability.hoursSaleBooking] }
        _ = try await engine.sync(force: true)
        let op = try h.recorder.recordHoursSale(draft, walkInAllowed: false, cashHolderID: nil, evidence: [], receivedAt: h.clock.wallNow)
        let job = try JSONValue.parse(op.payloadJSON)["job"]
        #expect(job?["planned_start"]?.stringValue.flatMap(AssetaJSON.parseInstant) == start)
        #expect(job?["planned_end"]?.stringValue.flatMap(AssetaJSON.parseInstant) == start.addingTimeInterval(6 * 3600))
        #expect(job?["job_site_id"]?.stringValue == site.uuidString.lowercased())
        #expect(job?["note"]?.stringValue == "Dig the trench")
        // Offline the contract stays empty: the server uses the customer's only contract.
        #expect(job?["contract_id"] == nil)
        h.server.mutate { $0.script[op.id] = ["CONFLICT:CONTRACT_REQUIRED"] }
        _ = try await engine.sync(force: true)
        let stored = try h.store.outbox.operation(id: op.id)
        #expect(stored?.status == .conflict && stored?.errorCode == "CONTRACT_REQUIRED")
    }
}
