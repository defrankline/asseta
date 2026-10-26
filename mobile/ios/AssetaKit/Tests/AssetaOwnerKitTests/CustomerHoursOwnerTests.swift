@testable import AssetaOwnerKit
import AssetaModel
import AssetaNetwork
import Foundation
import Testing

/// DEC-031 Phases 2 and 4 on the Owner side: fuel per engine hour and the machine-day case on the daily sheet, the new
/// rule labels, the prepaid-hours purchase (hours in use by running jobs, low-balance warnings), the customer hours
/// statement, gating and the HOURS_PURCHASE deep links. Strings doc "DEC-031 Phases 2 and 4".
struct CustomerHoursOwnerTests {
    static let purchaseID = UUID(uuidString: "a7000000-0000-4000-8000-000000000001")!
    static let customerID = UUID(uuidString: "c7000000-0000-4000-8000-000000000001")!
    static let machineID = UUID(uuidString: "aaaaaaaa-0000-4000-8000-000000000001")!
    static let otherMachine = UUID(uuidString: "aaaaaaaa-0000-4000-8000-000000000002")!
    static let caseID = UUID(uuidString: "f6000000-0000-4000-8000-000000000009")!
    let utc = TimeZone(identifier: "UTC")!

    static func id(_ u: UUID) -> String { u.uuidString.lowercased() }

    static func machineHours(_ machine: UUID, remaining: String, provisional: String) -> String {
        """
        {"machine_id":"\(id(machine))","machine_code":null,"machine_name":null,"activated":"50","transferred_in":"0","consumed":"30",
         "transferred_out":"0","expired":"0","reversed":"0","remaining":"\(remaining)","provisional":"\(provisional)"}
        """
    }

    static func purchase(provisional: String? = "6.5", twoMachines: Bool = false) -> String {
        let machines = [machineHours(machineID, remaining: "13.5", provisional: provisional ?? "0")]
            + (twoMachines ? [machineHours(otherMachine, remaining: "4", provisional: "0")] : [])
        return """
        {"id":"\(id(purchaseID))","purchase_number":"HP-2026-00012","client_id":null,"customer_id":"\(id(customerID))",
         "customer_name":"Mjenzi Ltd","customer_kind":null,"machine_id":"\(id(machineID))","machine_code":"EX-01",
         "machine_name":"Excavator","job_site_id":null,"job_site_name":null,"hours":"50","currency":"TZS",
         "rate_card_id":"a8000000-0000-4000-8000-000000000001","hourly_rate":"100000","discount_id":null,"discount_percent":"0",
         "effective_rate":"100000","amount":"5000000","note":null,"source":"OFFICE","policy_version":"h1","created_by":null,
         "created_by_name":"Asha","created_at":"2026-10-01T07:00:00Z","cancelled_at":null,"cancellation_id":null,"status":"ACTIVE",
         "payment":null,"allocations":[],"machines":[\(machines.joined(separator: ","))],
         "totals":{"purchased":"50","activated":"50","activated_from_payments":"50","activated_on_credit":"0",
         "awaiting_activation":"0","consumed":"30","transferred":"0","expired":"0","reversed":"0","remaining":"13.5",
         \(provisional.map { "\"provisional\":\"\($0)\"," } ?? "")
         "amount_verified":"5000000","amount_claimed_unverified":"0","amount_outstanding":"0"}}
        """
    }

    static let alert = """
    {"id":"a9000000-0000-4000-8000-000000000001","purchase_id":"\(id(purchaseID))","purchase_number":"HP-2026-00012",
     "customer_id":"\(id(customerID))","customer_name":"Mjenzi Ltd","machine_id":"\(id(machineID))","machine_code":"EX-01",
     "machine_name":"Excavator","sequence":1,"threshold_hours":"15","remaining_hours":"13.5","available_hours":"13.5",
     "crossed_at":"2026-10-26T14:05:00Z","notify_customer":true,"customer_sms_status":"SENT","customer_sms_id":null,
     "rearmed_at":null,"policy_version":"h2"}
    """

    static let statement = """
    {"customer_id":"\(id(customerID))","customer_name":"Mjenzi Ltd","machine_id":"\(id(machineID))","machine_code":"EX-01",
     "machine_name":"Excavator","date_from":"2026-10-01","date_to":"2026-10-26","timezone":"Africa/Dar_es_Salaam",
     "generated_at":"2026-10-26T15:00:00Z","pdf_path":"/api/v1/tenant/customers/\(id(customerID))/hours-statement.pdf",
     "totals":{"opening_balance":"0","bought":"50","activated":"50","used":"30","transferred_in":"0","transferred_out":"0",
     "expired":"0","cancelled":"0","closing_balance":"13.5","provisional_at_close":"6.5","awaiting_activation":"0"},
     "purchases":[{"purchase_id":"\(id(purchaseID))","purchase_number":"HP-2026-00012","machine_id":"\(id(machineID))",
     "machine_code":"EX-01","machine_name":"Excavator","bought_at":"2026-10-01T07:00:00Z","hours":"50","currency":"TZS",
     "effective_rate":"100000","amount":"5000000","status":"ACTIVE","activated":"50","remaining_at_close":"13.5",
     "next_expiry_at":"2026-11-30T21:00:00Z","expiring_hours":"13.5","cancelled_at":null}],
     "usage":[{"day":"2026-10-20","job_id":"bbbbbbbb-0000-4000-8000-000000000001","job_number":"J-12","machine_id":"\(id(machineID))",
     "machine_code":"EX-01","machine_name":"Excavator","hours":"30","basis":"FINAL","job_running":false},
     {"day":"2026-10-26","job_id":"bbbbbbbb-0000-4000-8000-000000000002","job_number":"J-13","machine_id":"\(id(machineID))",
     "machine_code":"EX-01","machine_name":"Excavator","hours":"6.5","basis":"DAILY","job_running":true}],
     "lines":[{"entry_id":"ab000000-0000-4000-8000-000000000001","day":"2026-10-26","occurred_at":"2026-10-26T14:00:00Z",
     "entry_type":"PROVISIONAL","purchase_id":"\(id(purchaseID))","purchase_number":"HP-2026-00012","machine_id":"\(id(machineID))",
     "machine_code":"EX-01","machine_name":"Excavator","job_id":null,"job_number":null,"hours":"-6.5","balance_after":"13.5","reason":null}]}
    """

    static func decode<T: Decodable>(_ type: T.Type, _ json: String) throws -> T {
        try AssetaJSON.decoder().decode(T.self, from: Data(json.utf8))
    }

    // MARK: Phase 2

    @Test func sheetShowsLitresPerEngineHourAndLinksTheMachineDayCase() throws {
        let json = RevenueOwnerTests.sheetDay
            .replacingOccurrences(of: #""fuel_litres":"42.5","#, with: #""fuel_litres":"42.5","fuel_litres_per_engine_hour":"4.05","#)
            .replacingOccurrences(of: #""flags":["UNEXPLAINED_HOURS","SOMETHING_NEW"]"#,
                                  with: #""flags":["ENGINE_ON_WITHOUT_JOB","FUEL_ABOVE_NORM"]"#)
            .replacingOccurrences(of: #""flag_records":[]"#, with: """
            "flag_records":[{"flag":"ENGINE_ON_WITHOUT_JOB","record_id":"\(Self.id(Self.caseID))","record_type":"anomaly_case"},
            {"flag":"FUEL_ABOVE_NORM","record_id":"f6000000-0000-4000-8000-00000000000a","record_type":"fuel_event"}]
            """)
        #expect(try Contract.missingRequired(schema: "DailyMachineSheetDetailDto", json: json) == [])
        let s = try Self.decode(DailyMachineSheetDTO.self, json)
        #expect(RevenuePresentation.sheetFuelFields(s) == [
            DecisionField(label: "Fuel", value: "42.5 L"), DecisionField(label: "Litres per engine hour", value: "4.05 L/h"),
        ])
        #expect(RevenuePresentation.sheetFlags(s) == ["Engine on without a job", "Fuel above norm"])
        #expect(RevenuePresentation.caseIDs(s) == [Self.caseID])
        // Without engine hours the rate is null and only the litres show.
        let plain = try Self.decode(DailyMachineSheetDTO.self, RevenueOwnerTests.sheetDay)
        #expect(plain.fuelLitresPerEngineHour == nil && RevenuePresentation.sheetFuelFields(plain).count == 1)
    }

    @Test func newRulesReadInPlainWords() {
        #expect(CaseText.signal("ENGINE_RUNNING_WITHOUT_WORK") == "Engine running without work during the day")
        #expect(CaseText.signal("MACHINE_FUEL_ABOVE_NORM") == "Fuel above the norm for the engine hours")
        #expect(CaseText.signal("FUEL_ALLOWANCE_EXCEEDED") == "Fuel allowance exceeded")
    }

    // MARK: Phase 4 purchase

    @Test func purchaseDecodesAgainstTheContractWithAndWithoutProvisional() throws {
        #expect(try Contract.missingRequired(schema: "HoursPurchaseDto", json: Self.purchase()) == [])
        let p = try Self.decode(HoursPurchaseDTO.self, Self.purchase())
        #expect(p.totals.provisional.value == Decimal(string: "6.5"))
        #expect(p.provisional(on: Self.machineID) == Decimal(string: "6.5"))
        // A server before daily drawdown sends no `provisional`: nothing is in use.
        let old = try Self.decode(HoursPurchaseDTO.self, Self.purchase(provisional: nil)
            .replacingOccurrences(of: #","provisional":"0"}"#, with: "}"))
        #expect(old.totals.provisional.value == 0 && old.machines?.first?.provisional.value == 0)
    }

    @Test func purchaseListAndScreen() throws {
        let p = try Self.decode(HoursPurchaseDTO.self, Self.purchase())
        let row = CustomerHoursPresentation.row(p)
        #expect(row.title == "HP-2026-00012 · Mjenzi Ltd" && row.machine == "EX-01 · Excavator")
        #expect(row.left == "13.5 h left · 6.5 h in use by running jobs")
        #expect(CustomerHoursPresentation.purchaseRows(p) == [
            DecisionField(label: "Customer", value: "Mjenzi Ltd"), DecisionField(label: "Machine", value: "EX-01 · Excavator"),
            DecisionField(label: "Status", value: "Active"), DecisionField(label: "Bought", value: OwnerFormat.hours(DecimalString(50))),
            DecisionField(label: "Activated", value: OwnerFormat.hours(DecimalString(50))),
            DecisionField(label: "Used", value: OwnerFormat.hours(DecimalString(30))),
            DecisionField(label: "In use by running jobs", value: OwnerFormat.hours(DecimalString(Decimal(string: "6.5")!))),
            DecisionField(label: "Left", value: OwnerFormat.hours(DecimalString(Decimal(string: "13.5")!))),
        ])
        #expect(CustomerHoursPresentation.machineRows(p).isEmpty)
        let two = try Self.decode(HoursPurchaseDTO.self, Self.purchase(twoMachines: true))
        #expect(CustomerHoursPresentation.machineRows(two).map(\.value) == ["13.5 h left · 6.5 h in use by running jobs", "4 h left"])
        let none = try Self.decode(HoursPurchaseDTO.self, Self.purchase(provisional: "0"))
        #expect(!CustomerHoursPresentation.purchaseRows(none).map(\.label).contains("In use by running jobs"))
        #expect(CustomerHoursTexts.purchaseStatus("CONSUMED") == "Used up")
    }

    @Test func openListKeepsHoursLeftOrInUse() throws {
        let inUseOnly = try Self.decode(HoursPurchaseDTO.self, Self.purchase()
            .replacingOccurrences(of: #""remaining":"13.5","#, with: #""remaining":"0","#))
        let usedUp = try Self.decode(HoursPurchaseDTO.self, Self.purchase(provisional: "0")
            .replacingOccurrences(of: #""remaining":"13.5","#, with: #""remaining":"0","#))
        let cancelled = try Self.decode(HoursPurchaseDTO.self, Self.purchase()
            .replacingOccurrences(of: #""cancelled_at":null"#, with: #""cancelled_at":"2026-10-20T00:00:00Z""#))
        #expect(CustomerHoursPresentation.open([usedUp, inUseOnly, cancelled]) == [inUseOnly])
        let request = OwnerAPI.hoursPurchases()
        #expect(request.path == "/api/v1/tenant/hours-purchases" && request.queryItems.first?.value == "false")
    }

    // MARK: Phase 4 statement

    @Test func statementDecodesAndReads() throws {
        #expect(try Contract.missingRequired(schema: "HoursStatementDto", json: Self.statement) == [])
        let s = try Self.decode(HoursStatementDTO.self, Self.statement)
        #expect(CustomerHoursPresentation.header(s, fallbackName: nil) == "Mjenzi Ltd · 1 Oct 2026 – 26 Oct 2026")
        #expect(CustomerHoursPresentation.totals(s).map(\.label) == [
            "Opening balance", "Bought", "Activated", "Used", "Of which in use by running jobs", "Closing balance",
        ])
        let usage = CustomerHoursPresentation.usage(s)
        #expect(usage.map(\.label) == ["26 Oct 2026 · J-13", "20 Oct 2026 · J-12"])
        #expect(usage.map(\.caption) == ["EX-01 · Excavator · Drawn day by day · Job still running", "EX-01 · Excavator · Final"])
        #expect(CustomerHoursPresentation.footer(s, timeZone: utc) == "Times are in Africa/Dar_es_Salaam. Generated 26 Oct 2026, 15:00.")
        #expect(s.lines.first?.entryType == HoursLedgerEntryType.provisional)
        #expect(try Contract.missingRequired(schema: "LowBalanceAlertDto", json: Self.alert) == [])
        #expect(try Self.decode(LowBalanceAlertDTO.self, Self.alert).thresholdHours.value == 15)
    }

    @Test func statementPeriods() {
        let now = Date(timeIntervalSince1970: 1_793_000_000) // 2026-10-26
        #expect(StatementPeriod.allCases.map(\.label) == ["This month", "Last month", "Last 3 months", "This year"])
        #expect(StatementPeriod.thisMonth.range(now: now, timeZone: utc) == (from: "2026-10-01", to: "2026-10-26"))
        #expect(StatementPeriod.lastMonth.range(now: now, timeZone: utc) == (from: "2026-09-01", to: "2026-09-30"))
        #expect(StatementPeriod.last3Months.range(now: now, timeZone: utc) == (from: "2026-08-01", to: "2026-10-26"))
        #expect(StatementPeriod.thisYear.range(now: now, timeZone: utc) == (from: "2026-01-01", to: "2026-10-26"))
        let request = OwnerAPI.hoursStatement(customerID: Self.customerID, from: "2026-10-01", to: "2026-10-26")
        #expect(request.path == "/api/v1/tenant/customers/\(Self.id(Self.customerID))/hours-statement")
        #expect(request.queryItems.map(\.name) == ["date_from", "date_to"])
        #expect(OwnerAPI.hoursStatementPDF(customerID: Self.customerID, from: "2026-10-01", to: "2026-10-26").path
            == "/api/v1/tenant/customers/\(Self.id(Self.customerID))/hours-statement.pdf")
    }

    // MARK: Gating and links

    @Test func gatedByCustomerHoursAndHoursRead() {
        let route = OwnerRoute.hoursPurchase(Self.purchaseID)
        let reader = OwnerFeatures(permissions: ["tenant.hours.read", "tenant.accountability.read"])
        #expect(reader.allows(route) && reader.allows(.customerHours) && reader.allows(.hoursStatement(customer: Self.customerID, name: nil)))
        #expect(reader.moreEntries.contains("Customer hours"))
        let noRead = OwnerFeatures(permissions: ["tenant.accountability.read"])
        #expect(!noRead.allows(route) && !noRead.moreEntries.contains("Customer hours") && noRead.route(route) == .accountability)
        let off = OwnerFeatures(permissions: ["tenant.hours.read"], disabledCapabilities: [TenantCapability.customerHours])
        #expect(!off.allows(route) && off.route(route) == .accountability && off.route(.customerHours) == .accountability)
        #expect(reader.route(route) == route)
    }

    @Test func hoursPurchaseNotificationsOpenThePurchase() throws {
        let id = Self.id(Self.purchaseID)
        #expect(RecordKind.resolve(kind: "HOURS_PURCHASE", recordID: id, entity: nil, entityID: nil)
            == RecordRef(kind: .hoursPurchase, id: Self.purchaseID))
        let push = DeepLinkParser.parse(pushPayload: ["kind": "HOURS_PURCHASE", "record_id": id, "type": "HOURS_LOW_BALANCE",
                                                      "link": "/tenant/hours/purchases/\(id)"])
        #expect(push?.route == .hoursPurchase(Self.purchaseID))
        #expect(DeepLinkParser.route(path: "/tenant/hours/purchases/\(id)") == .hoursPurchase(Self.purchaseID))
        #expect(DeepLinkParser.route(path: "/tenant/hours/purchases") == .customerHours)
        #expect(DeepLinkParser.route(entity: "hours_purchase", id: id, path: nil) == .hoursPurchase(Self.purchaseID))
        #expect(DeepLinkParser.route(entity: "hours_purchase", id: nil, path: nil) == .customerHours)
        #expect(OwnerRoute.hoursPurchase(Self.purchaseID).identifiesRecord && !OwnerRoute.customerHours.identifiesRecord)
    }
}
