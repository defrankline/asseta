import AssetaModel
@testable import AssetaOwnerKit
import Foundation
import Testing

/// Real server responses (`contracts/fixtures`, written by backend `tests/api/test_contract_fixtures.py`) decoded with the
/// apps' decoder (Android `ContractFixturesTest`): every fixture must decode, so a DTO that disagrees with what the
/// server really sends fails here instead of on a screen.
@Suite("Contract fixtures: real responses decode")
struct ContractFixturesTests {
    static var fixtures: URL {
        URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("contracts/fixtures")
    }

    static func decode<T: Decodable>(_ type: T.Type, _ path: String) throws -> T {
        let data = try Data(contentsOf: fixtures.appendingPathComponent(path))
        return try AssetaJSON.decoder().decode(T.self, from: data)
    }

    /// The Supervisor app's ADR-008 snapshot lists, typed as the app reads them.
    struct Snapshot: Decodable {
        let machineReportReasons: [MachineReportReasonDTO]
        let machineReportStates: [MachineReportStatusDTO]
        let machineReportHours: [AvailableHoursDTO]
        let myMachineReports: [MachineReportDTO]
        let openCreditInvoices: [CreditInvoiceDTO]

        enum CodingKeys: String, CodingKey {
            case machineReportReasons = "machine_report_reasons", machineReportStates = "machine_report_states"
            case machineReportHours = "machine_report_hours", myMachineReports = "my_machine_reports"
            case openCreditInvoices = "open_credit_invoices"
        }
    }

    @Test func everyMachineReportFixtureDecodes() throws {
        let opening = try Self.decode(MachineReportDTO.self, "machine-reports/report-opening-submitted.json")
        #expect(opening.isOpening && opening.startSource == "OPENING" && opening.lines.isEmpty && opening.state == .submitted)
        let submitted = try Self.decode(MachineReportDTO.self, "machine-reports/report-submitted.json")
        #expect(!submitted.isOpening && submitted.lines.count == 2 && submitted.lines.contains { $0.availableHours != nil })
        let rejected = try Self.decode(MachineReportDTO.self, "machine-reports/report-rejected.json")
        // A rejected report is final: no correction link; a new report comes with its own reading.
        #expect(rejected.state == .rejected && rejected.correctedByID == nil && rejected.decisionNote != nil)
        #expect(rejected.sincePreviousVisitSeconds == nil && rejected.previousVisit == nil)
        #expect(rejected.visit?.place == "Mbezi Beach, Kinondoni, Dar es Salaam")
        let approved = try Self.decode(MachineReportDTO.self, "machine-reports/report-approved.json")
        #expect(approved.state == .approved && approved.correctsID == nil)
        // ADR-008 visits: the previous visit (with the phone's place) and this report's reading.
        #expect(approved.sincePreviousVisitSeconds == 3600)
        #expect(approved.previousVisit?.place == "Mbezi Beach, Kinondoni, Dar es Salaam" && approved.previousVisit?.accuracyM == 8)
        #expect(approved.visit?.latitude == -6.8 && approved.visit?.at == approved.endAt && approved.visit?.place == nil)
        #expect(ReportPresentation.sinceLastVisit(approved) == "Since last visit: 1 h")
        #expect(ReportPresentation.sinceLastVisit(rejected) == "Since last visit: First visit")
        #expect(VisitTexts.whereLine(approved.visit) == "Where: -6.8000, 39.2800 (±8 m)")
        #expect(VisitTexts.whereLine(approved.previousVisit) == "Where: Mbezi Beach, Kinondoni, Dar es Salaam · -6.8000, 39.2800 (±8 m)")
        // A decoded report encodes back with the same visit fields (the Owner cache).
        let again = try AssetaJSON.decoder().decode(MachineReportDTO.self, from: try AssetaJSON.encoder().encode(approved))
        #expect(again == approved)
        let pending = try Self.decode(Page<MachineReportDTO>.self, "machine-reports/list-pending.json")
        #expect(pending.items.contains { $0.isOpening } && pending.items.allSatisfy { $0.state == .submitted })
        #expect(try Self.decode(Page<MachineReportDTO>.self, "machine-reports/list-all.json").items.count == 4)
        #expect(try Self.decode(Page<MachineReportDTO>.self, "machine-reports/list-mine.json").items.count == 4)
    }

    @Test func statusAvailableHoursReadingAndSnapshotDecode() throws {
        let statuses = try Self.decode([MachineReportStatusDTO].self, "machine-reports/status.json")
        #expect(statuses.count == 2 && statuses.contains { $0.pendingReportID != nil })
        #expect(statuses.allSatisfy { $0.lastVisit?.at != nil && $0.lastVisit?.latitude == -6.8 && $0.lastVisit?.place == nil })
        let cached = try AssetaJSON.decoder().decode([MachineReportStatusDTO].self, from: try AssetaJSON.encoder().encode(statuses))
        #expect(cached == statuses)
        #expect(try !Self.decode([AvailableHoursDTO].self, "machine-reports/available-hours.json").isEmpty)
        let capture = try Self.decode(ReportCaptureDTO.self, "machine-reports/meter-capture-opening.json")
        #expect(capture.accuracyM == 900 && capture.captureMode == "MANUAL")
        #expect(try Self.decode(MeterCaptureDTO.self, "machine-reports/meter-capture-opening.json").placeName == nil)
        let snapshot = try Self.decode(Snapshot.self, "machine-reports/sync-snapshot.json")
        #expect(snapshot.myMachineReports.contains { $0.isOpening })
        #expect(!snapshot.machineReportStates.isEmpty && !snapshot.machineReportReasons.isEmpty && !snapshot.openCreditInvoices.isEmpty)
        #expect(!snapshot.machineReportHours.isEmpty)
    }

    @Test func creditSaleCreditInvoiceAndCustomerHoursDecode() throws {
        let toActivate = try #require(try Self.decode(Page<HoursPurchaseDTO>.self, "credit-sales/hours-purchases-credit-to-activate.json")
            .items.first)
        #expect(toActivate.creditAmount?.value == 450_000 && toActivate.creditStatus == "AWAITING_ACTIVATION")
        #expect(toActivate.payments?.map(\.method) == ["CASH"])
        #expect(try Self.decode(Page<HoursPurchaseDTO>.self, "credit-sales/hours-purchases-awaiting-activation.json").items.count == 1)
        let invoices = try Self.decode(Page<CreditInvoiceDTO>.self, "credit-sales/credit-invoices.json")
        #expect(invoices.items.first?.status == "PART_PAID")
        let invoice = try Self.decode(CreditInvoiceDTO.self, "credit-sales/credit-invoice.json")
        #expect(invoice.payments.map(\.method) == ["MOBILE_MONEY"])
        #expect(try !Self.decode([CustomerHoursSummaryDTO].self, "credit-sales/customer-hours.json").isEmpty)
    }

    @Test func anOpeningReportReadsAsTheFirstReading() throws {
        let r = try Self.decode(MachineReportDTO.self, "machine-reports/report-opening-submitted.json")
        let capture = try Self.decode(ReportCaptureDTO.self, "machine-reports/meter-capture-opening.json")
        #expect(ReportPresentation.readings(r) == "1,520.4 h")
        #expect(ReportPresentation.readLine(r, capture: capture) == "First reading — starting point · typed by hand")
        #expect(ReportPresentation.gpsLine(capture) == "GPS: ±900 m")
        #expect(ReportPresentation.tracker(r) == ReportTexts.openingNote)
        #expect(ReportPresentation.split(r) == ReportTexts.firstReading)
        #expect(ReportPresentation.rowTitle(r) == "OPEN-000 · sup-FIX-1")
        #expect(ReportPresentation.decided(r, approved: true) == ReportTexts.openingApproved)
        let rows = AttentionRow.rows(pending: [r], states: [], reminderDays: nil)
        #expect(rows.first?.title == "OPEN-000 first reading · 1,520.4 h")
    }
}
